"""Pure, deterministic generation of evidence-bound serial campaigns."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .campaign import release_contract_hash_v2
from .release_loader import load_release
from .route_qualification import (
    AccessProbeReceipt,
    ModelRoute,
    RouteQualificationError,
    RouteSet,
    require_campaign_eligible_receipt,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_V2_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "campaign.v2.schema.json"


def generate_campaign_payload(
    route_set: RouteSet,
    receipts: Mapping[str, AccessProbeReceipt],
    *,
    route_ids: list[str],
    release_file: str,
    campaign_id: str,
    results_dir: str,
    as_of: datetime,
    seed: int = 20260731,
    temperature: float = 0.0,
    allow_unknown_quota: bool = False,
    minimum_available_memory_fraction: float = 0.30,
    minimum_available_memory_gib: float = 4,
    minimum_free_disk_gib: float = 10,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Build a byte-stable campaign payload without contacting a provider or writing run state."""
    root = repository_root.resolve()
    release_path = _repository_path(release_file, root, "releases")
    release = load_release(release_path)
    instant = _as_utc(as_of)
    selected_ids = sorted(route_ids)
    if not selected_ids:
        raise RouteQualificationError("At least one route_id is required.")
    if len(selected_ids) != len(set(selected_ids)):
        raise RouteQualificationError("route_id selections must be unique.")
    if set(receipts) != set(selected_ids):
        missing = sorted(set(selected_ids).difference(receipts))
        extra = sorted(set(receipts).difference(selected_ids))
        raise RouteQualificationError(f"Receipt selection mismatch; missing={missing}, extra={extra}.")

    selected: list[tuple[Any, AccessProbeReceipt]] = []
    surfaces: set[tuple[str, str, str | None, str | None]] = set()
    for route_id in selected_ids:
        route = route_set.route(route_id)
        receipt = receipts[route_id]
        require_campaign_eligible_receipt(
            receipt,
            route,
            as_of=instant,
            allow_unknown_quota=allow_unknown_quota,
        )
        surfaces.add((route.adapter, route.provider, route.api_key_env, route.base_url))
        selected.append((route, receipt))
    if len(surfaces) != 1:
        raise RouteQualificationError(
            "Generated campaigns must use one adapter/provider/credential surface; split the route selection."
        )

    attempts = release.expected_attempts_per_task
    payload: dict[str, Any] = {
        "schema_version": "medeval.campaign.v2",
        "campaign_id": campaign_id,
        "generated_at": _format_timestamp(instant),
        "release_file": release_file,
        "release_id": release.release_id,
        "release_contract_hash_v2": release_contract_hash_v2(release, attempts),
        "fleet_file": route_set.fleet_file,
        "fleet_id": route_set.fleet_id,
        "route_set_file": route_set.source_label,
        "route_set_id": route_set.route_set_id,
        "allow_unknown_quota": allow_unknown_quota,
        "results_dir": _repository_label(results_dir, "runs"),
        "attempts": attempts,
        "execution": {
            "max_parallel_models": 1,
            "process_isolation": True,
            "resume": True,
            "fail_fast_attempts": True,
            "continue_on_model_failure": True,
        },
        "resource_limits": {
            "minimum_available_memory_fraction": minimum_available_memory_fraction,
            "minimum_available_memory_gib": minimum_available_memory_gib,
            "minimum_free_disk_gib": minimum_free_disk_gib,
        },
        "models": [
            _model_payload(route, receipt, seed=seed, temperature=temperature) for route, receipt in selected
        ],
    }
    _validate_campaign_v2(payload)
    return payload


def dump_campaign_yaml(payload: Mapping[str, Any]) -> str:
    """Serialize a generated campaign deterministically."""
    return yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=False, width=120)


def write_campaign_manifest(path: str | Path, payload: Mapping[str, Any]) -> bool:
    """Write once; an identical existing manifest is a deterministic no-op."""
    destination = Path(path)
    content = dump_campaign_yaml(payload)
    if destination.exists():
        if destination.read_text(encoding="utf-8") == content:
            return False
        raise RouteQualificationError(f"Refusing to overwrite a different campaign manifest: {destination}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return True


def _model_payload(route: ModelRoute, receipt: AccessProbeReceipt, *, seed: int, temperature: float) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "configuration_id": route.route_id,
        "base_model_id": route.base_model_id,
        "route_id": route.route_id,
        "route_spec_sha256": route.route_spec_sha256,
        "access_receipt_path": receipt.source_label,
        "access_receipt_sha256": receipt.content_sha256,
        "quota_assessment": receipt.quota_status,
        "adapter": route.adapter,
        "provider": route.provider,
        "model": route.model,
        "model_revision": route.model_revision,
        "response_format": route.response_format,
        "strict_schema": route.strict_schema,
        "timeout_seconds": route.timeout_seconds,
        "seed": seed,
        "temperature": temperature,
        "max_tokens": route.max_tokens,
    }
    optional = {
        "base_url": route.base_url,
        "api_key_env": route.api_key_env,
        "reasoning_effort": route.reasoning_effort,
        "ollama_keep_alive": route.ollama_keep_alive,
        "ollama_num_ctx": route.ollama_num_ctx,
        "max_rate_limit_retries": route.max_rate_limit_retries,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    return payload


def _validate_campaign_v2(payload: dict[str, Any]) -> None:
    schema = json.loads(CAMPAIGN_V2_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    details = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{location}: {error.message}")
    raise RouteQualificationError("Generated campaign violates campaign.v2:\n" + "\n".join(details))


def _repository_path(value: str, root: Path, prefix: str) -> Path:
    label = _repository_label(value, prefix)
    path = (root / Path(*PurePosixPath(label).parts)).resolve()
    if not path.is_relative_to((root / prefix).resolve()):
        raise RouteQualificationError(f"Path {value!r} escapes {prefix}/.")
    return path


def _repository_label(value: str, prefix: str) -> str:
    pure = PurePosixPath(value)
    prefix_parts = PurePosixPath(prefix).parts
    if pure.is_absolute() or ".." in pure.parts or pure.parts[: len(prefix_parts)] != prefix_parts:
        raise RouteQualificationError(f"Path {value!r} must be repository-relative under {prefix}/.")
    return pure.as_posix()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RouteQualificationError("Campaign as_of must include a timezone.")
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
