"""Executable model routes and immutable, non-scoring access evidence."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from .json_utils import decode_strict_json_object, stable_hash

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROUTE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "model-route.v1.schema.json"
RECEIPT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "access-probe-receipt.v1.schema.json"
_SECRET_KEY = re.compile(
    r"(?:^|_)(?:api_?key|secret|token|access_?token|auth(?:orization)?|bearer|password|credential)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(r"^(?:sk-|gsk_|ghp_|hf_|xox[pbar]-)", re.IGNORECASE)
OPENAI_ACCESS_PROBE_V2_PATH = "scripts/probes/openai_access_probe_v2.py"
OPENAI_ACCESS_PROBE_V2_DEPENDENCIES = (
    "scripts/probes/openai_access_probe.py",
    "src/medphys_agentbench/adapters/openai_compatible.py",
    "src/medphys_agentbench/json_utils.py",
    "src/medphys_agentbench/route_qualification.py",
)


class RouteQualificationError(ValueError):
    """Raised when route or access evidence cannot be trusted."""


@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    base_model_id: str
    adapter: str
    provider: str
    model: str
    model_revision: str
    revision_basis: str
    response_format: str
    strict_schema: bool
    timeout_seconds: int
    max_tokens: int
    access_ttl_seconds: int
    modalities: tuple[str, ...]
    route_spec_sha256: str
    base_url: str | None = None
    api_key_env: str | None = None
    reasoning_effort: str | None = None
    ollama_keep_alive: str | int | None = None
    ollama_num_ctx: int | None = None
    max_rate_limit_retries: int | None = None
    send_temperature: bool = True
    send_seed: bool = True
    completion_limit_field: str = "max_completion_tokens"
    response_format_dialect: str = "openai"
    send_reasoning_effort: bool = True


@dataclass(frozen=True)
class RouteSet:
    route_set_id: str
    fleet_file: str
    fleet_id: str
    frozen_at: datetime
    source_path: Path
    source_label: str
    routes: tuple[ModelRoute, ...]

    def route(self, route_id: str) -> ModelRoute:
        matches = [route for route in self.routes if route.route_id == route_id]
        if len(matches) != 1:
            raise RouteQualificationError(f"Expected exactly one route {route_id!r}; found {len(matches)}.")
        return matches[0]


@dataclass(frozen=True)
class AccessProbeReceipt:
    source_path: Path
    source_label: str
    payload: dict[str, Any]
    content_sha256: str
    started_at: datetime
    completed_at: datetime
    expires_at: datetime

    @property
    def route_id(self) -> str:
        return str(self.payload["route_id"])

    @property
    def outcome(self) -> str:
        return str(self.payload["outcome"])

    @property
    def quota_status(self) -> str:
        return str(self.payload["quota"]["status"])


def load_route_set(path: str | Path, *, repository_root: Path = REPOSITORY_ROOT) -> RouteSet:
    """Load and semantically bind executable routes to the frozen model fleet."""
    root = repository_root.resolve()
    source_path = Path(path).resolve()
    payload = _load_yaml(source_path)
    _reject_secret_material(payload, allow_api_key_env=True)
    _validate_schema(payload, ROUTE_SCHEMA_PATH, source_path)

    source_label = _relative_label(source_path, root, "fleet")
    fleet_path = _repository_path(str(payload["fleet_file"]), root, "fleet")
    fleet = _load_yaml(fleet_path)
    if fleet.get("fleet_id") != payload["fleet_id"]:
        raise RouteQualificationError("Route set fleet_id does not match the referenced fleet manifest.")
    fleet_index = {
        str(item["base_model_id"]): item
        for item in fleet.get("models", [])
        if isinstance(item, dict) and item.get("base_model_id")
    }

    route_ids: set[str] = set()
    identity_keys: set[tuple[str, str, str, str, str | None, bool, bool, str, str, bool]] = set()
    routes: list[ModelRoute] = []
    for item in payload["routes"]:
        route_id = str(item["route_id"])
        if route_id in route_ids:
            raise RouteQualificationError(f"Duplicate route_id {route_id!r}.")
        route_ids.add(route_id)
        base_model_id = str(item["base_model_id"])
        planned = fleet_index.get(base_model_id)
        if planned is None:
            raise RouteQualificationError(f"Route {route_id!r} references a model outside the frozen fleet.")
        planned_routes = {str(value) for value in planned.get("planned_routes", [])}
        if str(item["provider"]) not in planned_routes and str(item["adapter"]) not in planned_routes:
            raise RouteQualificationError(
                f"Route {route_id!r} uses an undeclared provider/adapter for {base_model_id!r}."
            )
        _validate_base_url(item, route_id)
        identity = (
            str(item["adapter"]),
            str(item["provider"]),
            str(item["model"]),
            str(item["model_revision"]),
            str(item["reasoning_effort"]) if item.get("reasoning_effort") else None,
            bool(item.get("send_temperature", True)),
            bool(item.get("send_seed", True)),
            str(item.get("completion_limit_field", "max_completion_tokens")),
            str(item.get("response_format_dialect", "openai")),
            bool(item.get("send_reasoning_effort", True)),
        )
        if identity in identity_keys:
            raise RouteQualificationError(f"Route set contains duplicate executable identity {identity!r}.")
        identity_keys.add(identity)
        if item.get("response_format_dialect", "openai") == "omit" and bool(item["strict_schema"]):
            raise RouteQualificationError(
                f"Route {route_id!r} cannot claim strict_schema when response_format is omitted."
            )
        if not bool(item.get("send_reasoning_effort", True)) and item.get("reasoning_effort") is not None:
            raise RouteQualificationError(
                f"Route {route_id!r} cannot declare reasoning_effort when the request field is omitted."
            )
        if str(item["adapter"]) == "ollama" and (
            not bool(item.get("send_temperature", True))
            or not bool(item.get("send_seed", True))
            or str(item.get("completion_limit_field", "max_completion_tokens")) != "max_completion_tokens"
            or str(item.get("response_format_dialect", "openai")) != "openai"
            or not bool(item.get("send_reasoning_effort", True))
        ):
            raise RouteQualificationError(f"Ollama route {route_id!r} must not declare an OpenAI request dialect.")
        routes.append(
            ModelRoute(
                **{
                    **item,
                    "modalities": tuple(item["modalities"]),
                    "route_spec_sha256": stable_hash(item),
                }
            )
        )
    return RouteSet(
        route_set_id=str(payload["route_set_id"]),
        fleet_file=str(payload["fleet_file"]),
        fleet_id=str(payload["fleet_id"]),
        frozen_at=_parse_timestamp(str(payload["frozen_at"]), "frozen_at"),
        source_path=source_path,
        source_label=source_label,
        routes=tuple(sorted(routes, key=lambda route: route.route_id)),
    )


def load_access_probe_receipt(
    path: str | Path,
    route_set: RouteSet,
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> AccessProbeReceipt:
    """Validate a content-addressed receipt against exactly one executable route."""
    root = repository_root.resolve()
    source_path = Path(path).resolve()
    try:
        payload = decode_strict_json_object(source_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RouteQualificationError(f"Cannot read access receipt {source_path}: {error}") from error
    _reject_secret_material(payload, allow_api_key_env=False)
    _validate_schema(payload, RECEIPT_SCHEMA_PATH, source_path)
    source_label = _relative_label(source_path, root, "receipts/access")

    claimed_hash = str(payload["content_sha256"])
    hash_payload = {key: value for key, value in payload.items() if key != "content_sha256"}
    if stable_hash(hash_payload) != claimed_hash:
        raise RouteQualificationError(f"Access receipt content hash mismatch: {source_label}.")
    implementation_path = _repository_path(
        str(payload["probe_implementation_path"]),
        root,
        "scripts/probes",
    )
    if not implementation_path.is_file():
        raise RouteQualificationError(f"Access receipt probe implementation is missing: {implementation_path}.")
    implementation_hash = sha256(implementation_path.read_bytes()).hexdigest()
    if implementation_hash != payload["probe_implementation_sha256"]:
        raise RouteQualificationError("Access receipt probe implementation hash mismatch.")
    dependencies = payload.get("probe_dependencies", [])
    if payload["probe_version"] == "openai-access-probe-v2":
        if payload["probe_implementation_path"] != OPENAI_ACCESS_PROBE_V2_PATH:
            raise RouteQualificationError("OpenAI access probe v2 receipt uses an unexpected implementation path.")
        dependency_paths = [str(dependency["path"]) for dependency in dependencies]
        if len(dependency_paths) != len(set(dependency_paths)) or set(dependency_paths) != set(
            OPENAI_ACCESS_PROBE_V2_DEPENDENCIES
        ):
            raise RouteQualificationError("OpenAI access probe v2 receipt dependency set mismatch.")
    for dependency in dependencies:
        dependency_path = _probe_dependency_path(str(dependency["path"]), root)
        if not dependency_path.is_file():
            raise RouteQualificationError(f"Access receipt probe dependency is missing: {dependency_path}.")
        dependency_hash = sha256(dependency_path.read_bytes()).hexdigest()
        if dependency_hash != dependency["content_sha256"]:
            raise RouteQualificationError("Access receipt probe dependency hash mismatch.")
    route = route_set.route(str(payload["route_id"]))
    expected = {
        "route_spec_sha256": route.route_spec_sha256,
        "route_set_id": route_set.route_set_id,
        "fleet_id": route_set.fleet_id,
        "base_model_id": route.base_model_id,
        "adapter": route.adapter,
        "provider": route.provider,
        "model": route.model,
        "model_revision": route.model_revision,
    }
    mismatches = [key for key, value in expected.items() if payload.get(key) != value]
    if mismatches:
        raise RouteQualificationError(
            f"Access receipt identity mismatch for {route.route_id!r}: {', '.join(sorted(mismatches))}."
        )
    _validate_source_commit(payload, route_set, route, root)
    started = _parse_timestamp(str(payload["started_at"]), "started_at")
    completed = _parse_timestamp(str(payload["completed_at"]), "completed_at")
    expires = _parse_timestamp(str(payload["expires_at"]), "expires_at")
    if completed < started:
        raise RouteQualificationError("Access receipt completed_at precedes started_at.")
    if expires <= completed:
        raise RouteQualificationError("Access receipt expires_at must be after completed_at.")
    if completed < route_set.frozen_at:
        raise RouteQualificationError("Access receipt predates the frozen route set.")
    if (expires - completed).total_seconds() > route.access_ttl_seconds:
        raise RouteQualificationError("Access receipt lifetime exceeds the route access_ttl_seconds contract.")
    if payload["outcome"] == "available" and payload["quota"]["status"] == "insufficient":
        raise RouteQualificationError("An available receipt cannot claim insufficient quota.")
    if payload["outcome"] == "available":
        if route.response_format_dialect == "omit":
            raise RouteQualificationError(
                "An available receipt cannot prove a provider response contract when response_format is omitted."
            )
        observed = {str(value) for value in payload["capabilities"]["observed"]}
        response_contract = payload["sanitized_metadata"].get("response_contract")
        if route.response_format not in observed or response_contract != route.response_format:
            raise RouteQualificationError(
                f"Available receipt does not prove route response contract {route.response_format!r}."
            )
        if route.strict_schema and "strict_schema" not in observed:
            raise RouteQualificationError("Available receipt does not prove the route's strict-schema capability.")
    return AccessProbeReceipt(
        source_path=source_path,
        source_label=source_label,
        payload=payload,
        content_sha256=claimed_hash,
        started_at=started,
        completed_at=completed,
        expires_at=expires,
    )


def require_campaign_eligible_receipt(
    receipt: AccessProbeReceipt,
    route: ModelRoute,
    *,
    as_of: datetime,
    allow_unknown_quota: bool = False,
) -> None:
    """Fail closed unless access evidence supports a run at the declared instant."""
    instant = _as_utc(as_of)
    if receipt.route_id != route.route_id:
        raise RouteQualificationError(f"Receipt does not belong to route {route.route_id!r}.")
    if receipt.outcome != "available":
        raise RouteQualificationError(
            f"Route {route.route_id!r} is not campaign eligible: receipt outcome is {receipt.outcome!r}."
        )
    if receipt.completed_at > instant:
        raise RouteQualificationError(f"Route {route.route_id!r} has a future-dated access receipt.")
    if receipt.expires_at < instant:
        raise RouteQualificationError(f"Route {route.route_id!r} has an expired access receipt.")
    if receipt.quota_status == "insufficient":
        raise RouteQualificationError(f"Route {route.route_id!r} has insufficient provider quota.")
    if receipt.quota_status == "unknown" and not allow_unknown_quota:
        raise RouteQualificationError(
            f"Route {route.route_id!r} has unknown quota; an explicit recorded override is required."
        )


def receipt_payload_with_hash(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a content-addressed receipt payload; useful to probe implementations and tests."""
    if "content_sha256" in payload:
        raise RouteQualificationError("Receipt payload must not already contain content_sha256.")
    return {**payload, "content_sha256": stable_hash(payload)}


def _validate_schema(payload: Any, schema_path: Path, source_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    details = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{source_path}:{location}: {error.message}")
    raise RouteQualificationError("Invalid route/access contract:\n" + "\n".join(details))


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RouteQualificationError(f"Cannot read YAML contract {path}: {error}") from error
    if not isinstance(payload, dict):
        raise RouteQualificationError(f"YAML contract must contain a mapping: {path}.")
    return payload


def _repository_path(value: str, root: Path, prefix: str) -> Path:
    pure = PurePosixPath(value)
    prefix_parts = PurePosixPath(prefix).parts
    if pure.is_absolute() or ".." in pure.parts or pure.parts[: len(prefix_parts)] != prefix_parts:
        raise RouteQualificationError(f"Path {value!r} must be repository-relative under {prefix}/.")
    resolved = (root / Path(*pure.parts)).resolve()
    if not resolved.is_relative_to((root / prefix).resolve()):
        raise RouteQualificationError(f"Path {value!r} escapes {prefix}/.")
    return resolved


def _relative_label(path: Path, root: Path, prefix: str) -> str:
    try:
        label = path.relative_to(root).as_posix()
    except ValueError as error:
        raise RouteQualificationError(f"Path {path} must be inside repository root {root}.") from error
    _repository_path(label, root, prefix)
    return label


def _probe_dependency_path(value: str, root: Path) -> Path:
    for prefix in ("scripts/probes", "src/medphys_agentbench"):
        try:
            return _repository_path(value, root, prefix)
        except RouteQualificationError:
            continue
    raise RouteQualificationError(
        f"Probe dependency path {value!r} must stay under scripts/probes/ or src/medphys_agentbench/."
    )


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as error:
        raise RouteQualificationError(f"Invalid {field} timestamp {value!r}.") from error


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RouteQualificationError("Timestamps must include a timezone.")
    return value.astimezone(UTC)


def _validate_base_url(item: dict[str, Any], route_id: str) -> None:
    if not item.get("base_url"):
        return
    parsed = urlsplit(str(item["base_url"]))
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RouteQualificationError(
            f"base_url for route {route_id!r} must not contain credentials, query parameters, or fragments."
        )


def _validate_source_commit(
    payload: dict[str, Any],
    route_set: RouteSet,
    route: ModelRoute,
    root: Path,
) -> None:
    """When Git history is present, prove the source commit contains the bound implementation and route."""
    if not (root / ".git").exists():
        return
    commit = str(payload["source_commit"])
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        implementation = subprocess.run(
            ["git", "show", f"{commit}:{payload['probe_implementation_path']}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        route_set_bytes = subprocess.run(
            ["git", "show", f"{commit}:{route_set.source_label}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        raise RouteQualificationError(
            "Access receipt source_commit is missing required probe/route artifacts."
        ) from error
    if sha256(implementation).hexdigest() != payload["probe_implementation_sha256"]:
        raise RouteQualificationError("Access receipt source_commit contains different probe implementation bytes.")
    for dependency in payload.get("probe_dependencies", []):
        try:
            committed_dependency = subprocess.run(
                ["git", "show", f"{commit}:{dependency['path']}"],
                cwd=root,
                check=True,
                capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as error:
            raise RouteQualificationError(
                "Access receipt source_commit is missing a declared probe dependency."
            ) from error
        if sha256(committed_dependency).hexdigest() != dependency["content_sha256"]:
            raise RouteQualificationError("Access receipt source_commit contains different probe dependency bytes.")
    committed_route_set = yaml.safe_load(route_set_bytes.decode("utf-8"))
    committed_routes = committed_route_set.get("routes", []) if isinstance(committed_route_set, dict) else []
    committed_matches = [
        item for item in committed_routes if isinstance(item, dict) and item.get("route_id") == route.route_id
    ]
    if len(committed_matches) != 1 or stable_hash(committed_matches[0]) != route.route_spec_sha256:
        raise RouteQualificationError("Access receipt source_commit contains a different executable route contract.")


def _reject_secret_material(value: Any, *, allow_api_key_env: bool, trail: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if not (allow_api_key_env and key_text == "api_key_env") and _SECRET_KEY.search(key_text):
                location = ".".join((*trail, key_text))
                raise RouteQualificationError(f"Route/access artifacts may not contain secret-like field {location!r}.")
            _reject_secret_material(child, allow_api_key_env=allow_api_key_env, trail=(*trail, key_text))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_material(child, allow_api_key_env=allow_api_key_env, trail=(*trail, f"[{index}]"))
        return
    if isinstance(value, str) and _SECRET_VALUE.match(value.strip()):
        location = ".".join(trail) or "<root>"
        raise RouteQualificationError(f"Route/access artifacts may not contain secret-like values at {location!r}.")
