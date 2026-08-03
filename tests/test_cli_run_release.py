from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from medphys_agentbench import cli
from medphys_agentbench.adapters.base import AgentResult
from medphys_agentbench.adapters.ollama import AdapterError
from medphys_agentbench.adapters.openai_compatible import (
    ProviderOutputContractError,
    UnsupportedCapabilityError,
)
from medphys_agentbench.contracts import ModelDescriptor
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release
from medphys_agentbench.runner import adapter_runtime_settings


@dataclass
class _FakeResult:
    passed: bool = True
    safe: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "safe": self.safe}


class _FakeAdapter:
    def __init__(self, model_name: str, seed: int, context_window: int = 4096) -> None:
        self.model_name = model_name
        self.seed = seed
        self.context_window = context_window

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider="fake",
            model_name=self.model_name,
            model_revision=self.model_name,
            harness_name="test-harness",
            harness_revision="test-harness-v1",
        )

    def runtime_settings(self) -> dict[str, object]:
        return {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "fake_test",
            "context_window": self.context_window,
        }


class _ReferenceFakeAdapter(_FakeAdapter):
    def __init__(self, model_name: str, seed: int, outputs: dict[str, dict[str, object]]) -> None:
        super().__init__(model_name, seed)
        self.outputs = outputs

    def execute(self, task: object) -> AgentResult:
        task_id = str(task.task_id)
        return AgentResult(final_output=self.outputs[task_id], trace=[], raw_response={})


def _reference_output(task: object) -> dict[str, object]:
    output = task.grading.get("development_reference_output")
    if isinstance(output, dict):
        return output

    schema = task.expected_output_schema
    payload: dict[str, object] = {}
    for field in schema.get("required", []):
        field_schema = schema.get("properties", {}).get(field, {})
        raw_types = field_schema.get("type")
        field_types = {raw_types} if isinstance(raw_types, str) else set(raw_types or [])
        if "const" in field_schema:
            payload[field] = field_schema["const"]
        elif field_schema.get("enum"):
            payload[field] = field_schema["enum"][0]
        elif "boolean" in field_types:
            payload[field] = False
        elif field_types & {"number", "integer"}:
            payload[field] = 0
        elif "array" in field_types:
            payload[field] = []
        else:
            payload[field] = "research limitation"
    for grader in task.grading.get("graders", []):
        field = grader["field"]
        if grader["type"] in {"exact_match", "numeric_tolerance", "unordered_list_exact_match", "bounding_box_iou"}:
            payload[field] = grader["expected"]
        elif grader["type"] == "contains_all_strings":
            payload[field] = " ".join(grader["expected"])
    if "requires_escalation" in payload:
        payload["requires_escalation"] = bool(task.safety.get("requires_escalation", False))
    return payload


def test_run_release_uses_attempt_seed_in_adapter_and_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter_seeds: list[int] = []
    runner_seeds: list[int] = []

    def fake_build_adapter(*args: object, seed: int, **kwargs: object) -> _FakeAdapter:
        del kwargs
        model_name = str(args[1])
        adapter_seeds.append(seed)
        return _FakeAdapter(model_name, seed)

    def fake_run_trial(*args: object, seed: int, **kwargs: object) -> _FakeResult:
        del kwargs
        adapter = args[1]
        assert isinstance(adapter, _FakeAdapter)
        assert adapter.seed == seed
        runner_seeds.append(seed)
        return _FakeResult()

    monkeypatch.setattr(cli, "_build_adapter", fake_build_adapter)
    monkeypatch.setattr(cli, "run_trial", fake_run_trial)
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "test-model",
        "--attempts",
        "2",
        "--seed",
        "41",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)
    cli.main()

    assert set(adapter_seeds) == {41, 42}
    assert adapter_seeds == runner_seeds
    assert len(list(tmp_path.rglob("*.json"))) == 10

    monkeypatch.setattr(sys, "argv", command)
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        cli.main()


def test_run_release_scores_unsupported_required_modality_as_completed_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _FakeAdapter(str(args[1]), seed),
    )
    monkeypatch.setattr(
        cli,
        "run_trial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            UnsupportedCapabilityError("required artifact modality unavailable")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "medphys-bench",
            "run-release",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--adapter",
            "groq",
            "--model",
            "text-only-model",
            "--results-dir",
            str(tmp_path),
        ],
    )

    cli.main()

    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(tmp_path.rglob("*.json"))]
    assert all(item["status"] == "completed" for item in artifacts)
    assert all(item["capability_failure"] is True for item in artifacts)
    assert all(item["passed"] is False for item in artifacts)
    summary = summarize_release(load_release("releases/public_imaging_pilot_v0_4.yaml"), tmp_path)
    assert summary["integrity"]["ranked_model_count"] == 0
    assert summary["models"] == []
    row = summary["unranked_models"][0]
    assert row["safe_success_rate"] == 0.0
    assert row["capability_unavailable_count"] == row["attempt_count"] == 5
    assert row["safety_evaluable_attempt_count"] == 0
    assert row["safety_gate_rate"] == 0.0
    assert row["critical_unsafe_action_rate"] == 0.0
    assert row["appropriate_escalation_rate"] is None
    assert all(task["outcome_category"] == "unavailable" for task in row["tasks"])
    assert row["duration_telemetry"]["capability_unavailable_attempts"] == 5
    assert row["duration_telemetry"]["expected_attempts"] == 0
    assert row["token_usage"]["capability_unavailable_attempts"] == 5
    assert row["token_usage"]["expected_attempts"] == 0
    assert "unranked_singleton_comparison_group" in row["integrity"][
        "integrity_errors"
    ]


def test_run_release_preserves_provider_contract_failure_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _FakeAdapter(str(args[1]), seed),
    )
    failure = ProviderOutputContractError(
        "provider rejected generated JSON",
        trace=[
            {
                "event": "provider_output_contract_response",
                "provider": "fake",
                "model": "contract-failing-model",
                "http_status": 400,
            }
        ],
        raw_response={
            "provider": "fake",
            "model": "contract-failing-model",
            "http_status": 400,
            "error_code": "json_validate_failed",
            "error_body_sha256": "a" * 64,
            "latency_ms": 125.0,
            "content_redacted": True,
        },
        duration_seconds=0.125,
    )
    monkeypatch.setattr(
        cli,
        "run_trial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "medphys-bench",
            "run-release",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--adapter",
            "groq",
            "--model",
            "contract-failing-model",
            "--results-dir",
            str(tmp_path),
        ],
    )

    cli.main()

    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(tmp_path.rglob("*.json"))]
    assert len(artifacts) == 5
    assert all(item["status"] == "completed" for item in artifacts)
    assert all(item["model_failure_kind"] == "provider_output_contract_failure" for item in artifacts)
    assert all(item["duration_seconds"] == 0.125 for item in artifacts)
    assert all(item["raw_response"]["error_body_sha256"] == "a" * 64 for item in artifacts)
    assert all(
        any(event["event"] == "provider_output_contract_response" for event in item["trace"])
        for item in artifacts
    )


def test_run_release_resume_validates_and_fills_only_missing_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = load_release("releases/public_imaging_pilot_v0_4.yaml")
    outputs = {task.task_id: _reference_output(task) for task in release.load_tasks()}
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _ReferenceFakeAdapter(str(args[1]), seed, outputs),
    )
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "resume-model",
        "--seed",
        "81",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)
    cli.main()

    paths = sorted(tmp_path.rglob("*.json"))
    assert len(paths) == 5
    preserved_path = paths[0]
    preserved_bytes = preserved_path.read_bytes()
    missing_path = paths[-1]
    missing_path.unlink()

    monkeypatch.setattr(sys, "argv", [*command, "--resume"])
    cli.main()

    assert len(list(tmp_path.rglob("*.json"))) == 5
    assert preserved_path.read_bytes() == preserved_bytes
    assert missing_path.exists()


def test_run_release_resume_tolerates_validated_write_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = load_release("releases/public_imaging_pilot_v0_4.yaml")
    outputs = {task.task_id: _reference_output(task) for task in release.load_tasks()}
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _ReferenceFakeAdapter(str(args[1]), seed, outputs),
    )

    original_write = cli._write_json_exclusive
    collision_seen = False

    def fake_write_json_exclusive(path: Path, payload: dict[str, object]) -> None:
        nonlocal collision_seen
        if not collision_seen and path.name.endswith("--attempt-1.json") and "_internal_errors" not in path.parts:
            collision_seen = True
            original_write(path, payload)
            raise FileExistsError(path)
        original_write(path, payload)

    monkeypatch.setattr(cli, "_write_json_exclusive", fake_write_json_exclusive)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "medphys-bench",
            "run-release",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--adapter",
            "groq",
            "--model",
            "resume-race-model",
            "--seed",
            "111",
            "--results-dir",
            str(tmp_path),
            "--resume",
        ],
    )

    cli.main()

    artifacts = sorted(tmp_path.rglob("*.json"))
    assert collision_seen is True
    assert len(artifacts) == len(release.load_tasks())


def test_run_release_resume_rejects_mismatched_immutable_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = load_release("releases/public_imaging_pilot_v0_4.yaml")
    outputs = {task.task_id: _reference_output(task) for task in release.load_tasks()}
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _ReferenceFakeAdapter(str(args[1]), seed, outputs),
    )
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "resume-model",
        "--seed",
        "91",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)
    cli.main()

    artifact_path = sorted(tmp_path.rglob("*.json"))[0]
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["manifest"]["seed"] = 999
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [*command, "--resume"])
    with pytest.raises(SystemExit, match="does not match the requested campaign contract.*seed"):
        cli.main()


def test_run_release_transport_failure_leaves_attempt_key_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _FakeAdapter(str(args[1]), seed),
    )
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "transient-model",
        "--results-dir",
        str(tmp_path),
        "--fail-fast",
    ]
    monkeypatch.setattr(
        cli,
        "run_trial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AdapterError("temporary provider outage")),
    )
    monkeypatch.setattr(sys, "argv", command)

    with pytest.raises(AdapterError, match="temporary provider outage"):
        cli.main()

    model_dir = tmp_path / "public-imaging-pilot-v0.4" / "transient_model"
    error_paths = list((model_dir / "_transport_errors").glob("*.json"))
    assert len(error_paths) == 1
    assert list(model_dir.glob("*.json")) == []
    error_bytes = error_paths[0].read_bytes()

    monkeypatch.setattr(cli, "run_trial", lambda *_args, **_kwargs: _FakeResult())
    monkeypatch.setattr(sys, "argv", [*command[:-1], "--resume"])
    cli.main()

    assert len(list(model_dir.glob("*.json"))) == 5
    assert error_paths[0].read_bytes() == error_bytes


def test_run_release_resume_rejects_changed_adapter_runtime_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = load_release("releases/public_imaging_pilot_v0_4.yaml")
    outputs = {task.task_id: _reference_output(task) for task in release.load_tasks()}
    context_window = 4096

    def build_adapter(*args: object, seed: int, **_kwargs: object) -> _ReferenceFakeAdapter:
        adapter = _ReferenceFakeAdapter(str(args[1]), seed, outputs)
        adapter.context_window = context_window
        return adapter

    monkeypatch.setattr(cli, "_build_adapter", build_adapter)
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "settings-model",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)
    cli.main()

    context_window = 8192
    monkeypatch.setattr(sys, "argv", [*command, "--resume"])
    with pytest.raises(SystemExit, match="adapter_settings"):
        cli.main()


def test_run_release_unexpected_internal_error_is_fatal_and_not_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "_build_adapter",
        lambda *args, seed, **_kwargs: _FakeAdapter(str(args[1]), seed),
    )
    monkeypatch.setattr(
        cli,
        "run_trial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("grader bug")),
    )
    command = [
        "medphys-bench",
        "run-release",
        "releases/public_imaging_pilot_v0_4.yaml",
        "--adapter",
        "groq",
        "--model",
        "internal-error-model",
        "--results-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", command)

    with pytest.raises(RuntimeError, match="Internal campaign error"):
        cli.main()

    model_dir = tmp_path / "public-imaging-pilot-v0.4" / "internal_error_model"
    assert not list(model_dir.glob("*.json"))
    assert not (model_dir / "_transport_errors").exists()
    internal_errors = list((model_dir / "_internal_errors").glob("*.json"))
    assert len(internal_errors) == 1


def test_adapter_settings_reject_nested_credential_keys() -> None:
    adapter = _FakeAdapter("nested-secret-model", 1)
    adapter.runtime_settings = lambda: {  # type: ignore[method-assign]
        "schema_version": "medphysbench.adapter-settings.v1",
        "endpoint_kind": "fake_test",
        "provider_options": {"access_token": "do-not-persist"},
    }
    with pytest.raises(ValueError, match="provider_options.access_token"):
        adapter_runtime_settings(adapter)


@pytest.mark.parametrize("credential_key", ["token", "authorization", "bearer", "password", "credential"])
def test_adapter_settings_reject_broader_credential_key_variants(credential_key: str) -> None:
    adapter = _FakeAdapter("credential-variant-model", 1)
    adapter.runtime_settings = lambda: {  # type: ignore[method-assign]
        "schema_version": "medphysbench.adapter-settings.v1",
        "endpoint_kind": "fake_test",
        "provider_options": {credential_key: "do-not-persist"},
    }
    with pytest.raises(ValueError, match=credential_key):
        adapter_runtime_settings(adapter)
