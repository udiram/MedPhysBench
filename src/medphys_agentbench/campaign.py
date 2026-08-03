"""Schema-driven, serial campaign orchestration for immutable release runs."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .json_utils import stable_hash
from .release_loader import BenchmarkRelease, load_release
from .reporting import _release_contract_hash
from .runner import (
    grader_hash_for_task,
    prompt_hash_for_task,
    runtime_task_hash_for_task,
    system_prompt_hash,
    tool_schema_hash_for_task,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "campaign.v1.schema.json"
_ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SECRET_KEY = re.compile(
    r"(?:^|_)(?:api_?key|secret|token|access_?token|auth(?:orization)?|bearer|password|credential)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(r"^(?:sk-|gsk_|ghp_|hf_|xox[pbar]-)", re.IGNORECASE)


class CampaignError(ValueError):
    """Raised when a campaign contract cannot be validated or resumed safely."""


class CampaignExecutionError(RuntimeError):
    """Raised after an execution or resource failure has been recorded."""


@dataclass(frozen=True)
class CampaignResourceLimits:
    minimum_available_memory_fraction: float
    minimum_available_memory_gib: float
    minimum_free_disk_gib: float


@dataclass(frozen=True)
class CampaignExecution:
    max_parallel_models: int
    process_isolation: bool
    resume: bool
    fail_fast_attempts: bool
    continue_on_model_failure: bool


@dataclass(frozen=True)
class CampaignModel:
    configuration_id: str
    base_model_id: str
    adapter: str
    provider: str
    model: str
    model_revision: str
    response_format: str
    strict_schema: bool
    timeout_seconds: int
    seed: int
    temperature: float
    max_tokens: int
    base_url: str | None = None
    api_key_env: str | None = None
    reasoning_effort: str | None = None
    ollama_keep_alive: str | int | None = None
    ollama_num_ctx: int | None = None


@dataclass(frozen=True)
class CampaignSpec:
    schema_version: str
    campaign_id: str
    source_path: Path
    manifest_hash: str
    release_file: str
    release_path: Path
    release_id: str
    release_contract_hash_v2: str
    release: BenchmarkRelease
    fleet_file: str
    fleet_id: str
    results_dir_label: str
    results_dir: Path
    attempts: int
    execution: CampaignExecution
    resource_limits: CampaignResourceLimits
    models: tuple[CampaignModel, ...]


@dataclass(frozen=True)
class ResourceSnapshot:
    total_memory_bytes: int | None
    available_memory_bytes: int | None
    free_disk_bytes: int
    memory_source: str
    disk_path: str

    @property
    def available_memory_fraction(self) -> float | None:
        if not self.total_memory_bytes or self.available_memory_bytes is None:
            return None
        return self.available_memory_bytes / self.total_memory_bytes

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "available_memory_fraction": self.available_memory_fraction}


def load_campaign(path: str | Path) -> CampaignSpec:
    """Validate a campaign and bind it to the current frozen release and fleet."""
    source_path = Path(path).resolve()
    try:
        payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CampaignError(f"Cannot read campaign manifest {source_path}: {error}") from error
    if not isinstance(payload, dict):
        raise CampaignError("Campaign manifest must contain a mapping at the document root.")
    _reject_secret_material(payload)
    schema = json.loads(CAMPAIGN_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            details.append(f"{location}: {error.message}")
        raise CampaignError("Invalid campaign manifest:\n" + "\n".join(details))

    release_path = _repository_path(str(payload["release_file"]), "releases")
    fleet_path = _repository_path(str(payload["fleet_file"]), "fleet")
    results_dir = _repository_path(str(payload["results_dir"]), "runs")
    release = load_release(release_path)
    if release.release_id != payload["release_id"]:
        raise CampaignError(
            f"campaign release_id {payload['release_id']!r} does not match {release.release_id!r}."
        )
    attempts = int(payload["attempts"])
    if attempts != release.expected_attempts_per_task:
        raise CampaignError(
            "Campaign attempts must equal the frozen release expected_attempts_per_task "
            f"({release.expected_attempts_per_task}); received {attempts}."
        )
    observed_hash = release_contract_hash_v2(release, attempts)
    if payload["release_contract_hash_v2"] != observed_hash:
        raise CampaignError(
            "campaign release_contract_hash_v2 does not match the current frozen release contract."
        )

    fleet = yaml.safe_load(fleet_path.read_text(encoding="utf-8"))
    if not isinstance(fleet, dict) or fleet.get("fleet_id") != payload["fleet_id"]:
        raise CampaignError("campaign fleet_id does not match the referenced fleet manifest.")
    fleet_ids = {
        str(item["base_model_id"])
        for item in fleet.get("models", [])
        if isinstance(item, dict) and item.get("base_model_id")
    }
    models = tuple(CampaignModel(**item) for item in payload["models"])
    configuration_ids = [model.configuration_id for model in models]
    if len(configuration_ids) != len(set(configuration_ids)):
        raise CampaignError("Campaign configuration_id values must be unique.")
    identities = [
        (model.adapter, model.provider, model.model, model.model_revision, model.reasoning_effort)
        for model in models
    ]
    if len(identities) != len(set(identities)):
        raise CampaignError("Campaign contains a duplicate evaluated system identity.")
    result_slugs = [_slugify(model.model) for model in models]
    if len(result_slugs) != len(set(result_slugs)):
        raise CampaignError(
            "Campaign model handles must resolve to unique result directories; "
            "put alternate revisions or effort settings in a separate campaign/results_dir."
        )
    unknown = sorted({model.base_model_id for model in models}.difference(fleet_ids))
    if unknown:
        raise CampaignError(
            f"Campaign references base_model_id not present in {payload['fleet_id']!r}: {unknown[0]!r}."
        )
    for model in models:
        _validate_model(model)

    return CampaignSpec(
        schema_version=str(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        source_path=source_path,
        manifest_hash=stable_hash(payload),
        release_file=str(payload["release_file"]),
        release_path=release_path,
        release_id=release.release_id,
        release_contract_hash_v2=observed_hash,
        release=release,
        fleet_file=str(payload["fleet_file"]),
        fleet_id=str(payload["fleet_id"]),
        results_dir_label=str(payload["results_dir"]),
        results_dir=results_dir,
        attempts=attempts,
        execution=CampaignExecution(**payload["execution"]),
        resource_limits=CampaignResourceLimits(**payload["resource_limits"]),
        models=models,
    )


def release_contract_hash_v2(release: BenchmarkRelease, attempts: int) -> str:
    tasks = release.load_tasks()
    hashes = {
        task.task_id: {
            "prompt_hash": prompt_hash_for_task(task),
            "tool_schema_hash": tool_schema_hash_for_task(task),
            "runtime_task_hash": runtime_task_hash_for_task(task),
            "system_prompt_hash": system_prompt_hash(),
            "grader_hash": grader_hash_for_task(task),
        }
        for task in tasks
    }
    return _release_contract_hash(
        release_id=release.release_id,
        expected_attempts=attempts,
        tasks=tasks,
        task_hash_catalog=hashes,
    )


def build_model_command(spec: CampaignSpec, model: CampaignModel) -> list[str]:
    """Build one shell-free child command; credential values are never arguments."""
    command = [
        sys.executable,
        "-m",
        "medphys_agentbench.cli",
        "run-release",
        str(spec.release_path),
        "--adapter",
        model.adapter,
        "--model",
        model.model,
        "--model-revision",
        model.model_revision,
        "--results-dir",
        str(spec.results_dir),
        "--attempts",
        str(spec.attempts),
        "--provider",
        model.provider,
        "--response-format",
        model.response_format,
        "--timeout",
        str(model.timeout_seconds),
        "--seed",
        str(model.seed),
        "--temperature",
        str(model.temperature),
        "--max-tokens",
        str(model.max_tokens),
        "--resume",
    ]
    if model.base_url:
        command.extend(["--base-url", model.base_url])
    if model.api_key_env:
        command.extend(["--api-key-env", model.api_key_env])
    if not model.strict_schema:
        command.append("--best-effort-schema")
    if model.reasoning_effort:
        command.extend(["--reasoning-effort", model.reasoning_effort])
    if model.adapter == "ollama":
        command.extend(
            ["--ollama-keep-alive", str(model.ollama_keep_alive), "--ollama-num-ctx", str(model.ollama_num_ctx)]
        )
    if spec.execution.fail_fast_attempts:
        command.append("--fail-fast")
    return command


def capture_resource_snapshot(results_dir: Path) -> ResourceSnapshot:
    total = _total_memory_bytes()
    available, source = _available_memory_bytes(total)
    disk_anchor = _existing_parent(results_dir)
    return ResourceSnapshot(
        total_memory_bytes=total,
        available_memory_bytes=available,
        free_disk_bytes=shutil.disk_usage(disk_anchor).free,
        memory_source=source,
        disk_path=str(disk_anchor),
    )


def resource_limit_failures(snapshot: ResourceSnapshot, limits: CampaignResourceLimits) -> list[str]:
    failures: list[str] = []
    fraction = snapshot.available_memory_fraction
    if fraction is None:
        failures.append("available system memory could not be measured")
    elif fraction < limits.minimum_available_memory_fraction:
        failures.append(
            f"available memory fraction {fraction:.3f} is below {limits.minimum_available_memory_fraction:.3f}"
        )
    gib = 1024**3
    if snapshot.available_memory_bytes is not None and (
        snapshot.available_memory_bytes < limits.minimum_available_memory_gib * gib
    ):
        failures.append(
            f"available memory {snapshot.available_memory_bytes / gib:.2f} GiB is below "
            f"{limits.minimum_available_memory_gib:.2f} GiB"
        )
    if snapshot.free_disk_bytes < limits.minimum_free_disk_gib * gib:
        failures.append(
            f"free disk {snapshot.free_disk_bytes / gib:.2f} GiB is below {limits.minimum_free_disk_gib:.2f} GiB"
        )
    return failures


def campaign_plan(
    spec: CampaignSpec,
    *,
    environ: Mapping[str, str] | None = None,
    snapshot: ResourceSnapshot | None = None,
) -> dict[str, object]:
    environment = os.environ if environ is None else environ
    observed = snapshot or capture_resource_snapshot(spec.results_dir)
    return {
        "schema_version": "medphysbench.campaign-plan.v1",
        "campaign_id": spec.campaign_id,
        "manifest_hash": spec.manifest_hash,
        "release_id": spec.release_id,
        "release_contract_hash_v2": spec.release_contract_hash_v2,
        "fleet_id": spec.fleet_id,
        "base_model_count": len({model.base_model_id for model in spec.models}),
        "system_configuration_count": len(spec.models),
        "expected_attempt_count": len(spec.release.load_tasks()) * spec.attempts * len(spec.models),
        "serial": True,
        "process_isolation": True,
        "resource_snapshot": observed.to_dict(),
        "resource_failures": resource_limit_failures(observed, spec.resource_limits),
        "models": [
            {
                "configuration_id": model.configuration_id,
                "base_model_id": model.base_model_id,
                "provider": model.provider,
                "model": model.model,
                "model_revision": model.model_revision,
                "credential_env": model.api_key_env,
                "credential_present": model.api_key_env is None or bool(environment.get(model.api_key_env)),
            }
            for model in spec.models
        ],
    }


def execute_campaign(
    spec: CampaignSpec,
    *,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
    snapshot_provider: Callable[[Path], ResourceSnapshot] = capture_resource_snapshot,
    command_runner: Callable[[list[str], Path], int] | None = None,
    completion_verifier: Callable[[CampaignSpec, CampaignModel], dict[str, object]] | None = None,
) -> dict[str, object]:
    """Execute one model process at a time; result artifacts remain resume authority."""
    environment = os.environ if environ is None else environ
    initial_snapshot = snapshot_provider(spec.results_dir)
    plan = campaign_plan(spec, environ=environment, snapshot=initial_snapshot)
    if dry_run:
        return {**plan, "dry_run": True, "commands": [build_model_command(spec, model) for model in spec.models]}
    missing = sorted(
        {
            model.api_key_env
            for model in spec.models
            if model.api_key_env is not None and not environment.get(model.api_key_env)
        }
    )
    if missing:
        raise CampaignExecutionError(
            "Required provider credential environment variable(s) are unset: " + ", ".join(missing) + "."
        )
    state_dir = spec.results_dir / "_campaigns" / spec.campaign_id
    runner = command_runner or _run_child
    verifier = completion_verifier or verify_model_completion
    completed = 0
    failed = 0
    with _campaign_lock(state_dir):
        _initialize_state(spec, state_dir)
        failures = resource_limit_failures(initial_snapshot, spec.resource_limits)
        if failures:
            _append_event(
                spec,
                state_dir,
                "campaign_preflight_failed",
                {"failures": failures, "resource_snapshot": initial_snapshot.to_dict()},
            )
            raise CampaignExecutionError("Campaign resource preflight failed: " + "; ".join(failures))
        _append_event(spec, state_dir, "campaign_started", {"model_count": len(spec.models)})
        for model in spec.models:
            snapshot = snapshot_provider(spec.results_dir)
            failures = resource_limit_failures(snapshot, spec.resource_limits)
            if failures:
                _append_event(
                    spec,
                    state_dir,
                    "resource_blocked",
                    {
                        "configuration_id": model.configuration_id,
                        "failures": failures,
                        "resource_snapshot": snapshot.to_dict(),
                    },
                )
                raise CampaignExecutionError(
                    f"Resource guard stopped before {model.configuration_id}: {'; '.join(failures)}"
                )
            _append_event(
                spec,
                state_dir,
                "model_started",
                {
                    "configuration_id": model.configuration_id,
                    "base_model_id": model.base_model_id,
                    "resource_snapshot": snapshot.to_dict(),
                },
            )
            return_code = runner(build_model_command(spec, model), REPOSITORY_ROOT)
            completion = verifier(spec, model) if return_code == 0 else {
                "complete": False,
                "completed_attempts": 0,
                "missing_attempts": len(spec.release.load_tasks()) * spec.attempts,
                "transport_error_count": 0,
            }
            if return_code == 0 and completion["complete"] is True:
                completed += 1
                _append_event(
                    spec,
                    state_dir,
                    "model_completed",
                    {
                        "configuration_id": model.configuration_id,
                        "return_code": 0,
                        "completion": completion,
                    },
                )
                continue
            failed += 1
            failure_kind = "child_exit_nonzero" if return_code != 0 else "canonical_matrix_incomplete"
            _append_event(
                spec,
                state_dir,
                "model_failed",
                {
                    "configuration_id": model.configuration_id,
                    "return_code": return_code,
                    "failure_kind": failure_kind,
                    "completion": completion,
                },
            )
            if not spec.execution.continue_on_model_failure:
                raise CampaignExecutionError(
                    f"Campaign stopped after {model.configuration_id}: {failure_kind} "
                    f"(child exit {return_code})."
                )
        status = "completed" if failed == 0 else "completed_with_failures"
        _append_event(
            spec,
            state_dir,
            "campaign_finished",
            {"status": status, "completed_models": completed, "failed_models": failed},
        )
    return {**plan, "dry_run": False, "status": status, "completed_models": completed, "failed_models": failed}


def verify_model_completion(spec: CampaignSpec, model: CampaignModel) -> dict[str, object]:
    """Verify that a zero-exit child produced every canonical task/attempt key."""
    model_dir = spec.results_dir / spec.release_id / _slugify(model.model)
    expected = [
        (task, attempt_index, model_dir / f"{_slugify(task.task_id)}--attempt-{attempt_index + 1}.json")
        for task in spec.release.load_tasks()
        for attempt_index in range(spec.attempts)
    ]
    completed = 0
    invalid: list[str] = []
    for task, attempt_index, path in expected:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid.append(str(path))
            continue
        manifest = payload.get("manifest") if isinstance(payload, dict) else None
        descriptor = manifest.get("model") if isinstance(manifest, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("status") != "completed"
            or payload.get("attempt_index") != attempt_index
            or not isinstance(manifest, dict)
            or manifest.get("task_id") != task.task_id
            or not isinstance(descriptor, dict)
            or descriptor.get("model_name") != model.model
            or descriptor.get("model_revision") != model.model_revision
        ):
            invalid.append(str(path))
            continue
        completed += 1
    transport_errors = len(list((model_dir / "_transport_errors").glob("*.json")))
    return {
        "complete": completed == len(expected) and not invalid,
        "expected_attempts": len(expected),
        "completed_attempts": completed,
        "missing_attempts": len(expected) - completed,
        "invalid_attempt_count": len(invalid),
        "transport_error_count": transport_errors,
    }


def validate_event_ledger(path: Path, *, expected_campaign_hash: str | None = None) -> list[dict[str, Any]]:
    """Validate sequence, manifest binding, and the complete event hash chain."""
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise CampaignError(f"Invalid campaign event ledger JSON at line {line_number}.") from error
        if not isinstance(event, dict):
            raise CampaignError(f"Campaign event ledger line {line_number} is not an object.")
        event_hash = event.pop("event_sha256", None)
        if event.get("sequence") != len(events) + 1:
            raise CampaignError(f"Campaign event ledger sequence mismatch at line {line_number}.")
        if event.get("previous_event_sha256") != previous_hash:
            raise CampaignError(f"Campaign event ledger hash chain mismatch at line {line_number}.")
        if expected_campaign_hash is not None and event.get("campaign_manifest_sha256") != expected_campaign_hash:
            raise CampaignError(f"Campaign event ledger manifest hash mismatch at line {line_number}.")
        if event_hash != stable_hash(event):
            raise CampaignError(f"Campaign event ledger content hash mismatch at line {line_number}.")
        event["event_sha256"] = event_hash
        previous_hash = str(event_hash)
        events.append(event)
    return events


def _validate_model(model: CampaignModel) -> None:
    if model.api_key_env and not _ENVIRONMENT_NAME.fullmatch(model.api_key_env):
        raise CampaignError(f"Invalid credential environment variable name for {model.configuration_id}.")
    if model.base_url:
        parsed = urlsplit(model.base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise CampaignError(
                f"base_url for {model.configuration_id} must not contain credentials, query parameters, or fragments."
            )
    if model.adapter == "ollama":
        if model.api_key_env is not None:
            raise CampaignError(f"Ollama configuration {model.configuration_id} must not declare api_key_env.")
        if str(model.ollama_keep_alive) != "0":
            raise CampaignError(f"Ollama configuration {model.configuration_id} must use ollama_keep_alive=0.")
        if model.ollama_num_ctx is None:
            raise CampaignError(f"Ollama configuration {model.configuration_id} must declare ollama_num_ctx.")
    else:
        if model.api_key_env is None:
            raise CampaignError(f"Hosted configuration {model.configuration_id} must declare api_key_env.")
        if model.adapter == "openai-compatible" and model.base_url is None:
            raise CampaignError(
                f"OpenAI-compatible configuration {model.configuration_id} must declare base_url."
            )


def _reject_secret_material(value: Any, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text != "api_key_env" and _SECRET_KEY.search(key_text):
                location = ".".join((*trail, key_text))
                raise CampaignError(f"Campaign manifests may not contain secret-like field {location!r}.")
            _reject_secret_material(child, (*trail, key_text))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_material(child, (*trail, f"[{index}]"))
        return
    if isinstance(value, str) and _SECRET_VALUE.match(value.strip()):
        location = ".".join(trail) or "<root>"
        raise CampaignError(f"Campaign manifests may not contain secret-like values at {location!r}.")


def _repository_path(value: str, prefix: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != prefix:
        raise CampaignError(f"Path {value!r} must be repository-relative under {prefix}/.")
    resolved = (REPOSITORY_ROOT / Path(*pure.parts)).resolve()
    if not resolved.is_relative_to((REPOSITORY_ROOT / prefix).resolve()):
        raise CampaignError(f"Path {value!r} escapes {prefix}/.")
    return resolved


def _total_memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _available_memory_bytes(total: int | None) -> tuple[int | None, str]:
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024, "proc_meminfo"
    try:
        return (
            int(os.sysconf("SC_AVPHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE")),
            "sysconf_avphys",
        )
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    if sys.platform == "darwin" and total:
        try:
            completed = subprocess.run(
                ["memory_pressure", "-Q"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            match = re.search(r"System-wide memory free percentage:\s*(\d+)%", completed.stdout)
            if completed.returncode == 0 and match:
                return int(total * int(match.group(1)) / 100), "macos_memory_pressure"
        except (OSError, subprocess.SubprocessError):
            pass
    return None, "unavailable"


def _existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _run_child(command: list[str], cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False).returncode


def _slugify(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_").lower()


@contextmanager
def _campaign_lock(state_dir: Path) -> Any:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "run.lock").open("a+", encoding="utf-8") as handle:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, BlockingIOError) as error:
            raise CampaignExecutionError(f"Campaign {state_dir.name!r} is already running.") from error
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _initialize_state(spec: CampaignSpec, state_dir: Path) -> None:
    state_path = state_dir / "campaign.json"
    expected = {
        "schema_version": "medphysbench.campaign-state.v1",
        "campaign_id": spec.campaign_id,
        "campaign_manifest_sha256": spec.manifest_hash,
        "release_id": spec.release_id,
        "release_contract_hash_v2": spec.release_contract_hash_v2,
        "fleet_id": spec.fleet_id,
        "results_dir": spec.results_dir_label,
    }
    if state_path.exists():
        try:
            existing = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CampaignError(f"Cannot resume from unreadable campaign state {state_path}.") from error
        mismatches = [key for key, value in expected.items() if existing.get(key) != value]
        if mismatches:
            raise CampaignError(
                "Cannot resume: immutable campaign state differs from the requested manifest "
                f"({', '.join(mismatches)})."
            )
    else:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("x", encoding="utf-8") as handle:
            json.dump({**expected, "created_at": datetime.now(UTC).isoformat()}, handle, indent=2, sort_keys=True)
            handle.write("\n")
    validate_event_ledger(state_dir / "events.jsonl", expected_campaign_hash=spec.manifest_hash)


def _append_event(spec: CampaignSpec, state_dir: Path, event_type: str, details: dict[str, object]) -> None:
    path = state_dir / "events.jsonl"
    events = validate_event_ledger(path, expected_campaign_hash=spec.manifest_hash)
    event: dict[str, object] = {
        "schema_version": "medphysbench.campaign-event.v1",
        "sequence": len(events) + 1,
        "event_id": str(uuid4()),
        "recorded_at": datetime.now(UTC).isoformat(),
        "campaign_id": spec.campaign_id,
        "campaign_manifest_sha256": spec.manifest_hash,
        "previous_event_sha256": events[-1]["event_sha256"] if events else None,
        "event_type": event_type,
        "details": details,
    }
    event["event_sha256"] = stable_hash(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
