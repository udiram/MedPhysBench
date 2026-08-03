#!/usr/bin/env python3
"""Probe one local Ollama route without loading benchmark tasks or storing raw responses."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from medphys_agentbench.json_utils import decode_strict_json_object
from medphys_agentbench.route_qualification import (
    ModelRoute,
    RouteQualificationError,
    load_access_probe_receipt,
    load_route_set,
    receipt_payload_with_hash,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_LABEL = "scripts/probes/ollama_access_probe.py"
PROBE_VERSION = "ollama-access-probe-v1"
DEPENDENCY_LABELS = (
    "src/medphys_agentbench/adapters/ollama.py",
    "src/medphys_agentbench/json_utils.py",
    "src/medphys_agentbench/route_qualification.py",
)


def probe_ollama_route(
    route_set_path: str | Path,
    route_id: str,
    *,
    output_root: str | Path = "receipts/access",
    repository_root: Path = REPOSITORY_ROOT,
    opener: Callable[..., Any] = urllib.request.urlopen,
    now: Callable[[], datetime] | None = None,
    source_commit: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write one content-addressed local-runtime receipt without loading a benchmark task."""
    root = repository_root.resolve()
    route_set = load_route_set(route_set_path, repository_root=root)
    route = route_set.route(route_id)
    if route.adapter != "ollama":
        raise RouteQualificationError(f"Route {route_id!r} is not an Ollama route.")
    if not route.base_url:
        raise RouteQualificationError(f"Route {route_id!r} has no frozen local endpoint.")
    clock = now or (lambda: datetime.now(UTC))
    started = _as_utc(clock())
    started_perf = time.perf_counter()

    try:
        served_model, served_revision = _resolve_route_identity(route, opener)
        observed_modalities = _observed_modalities(route, opener)
        outcome, metadata, observed, quota = _run_json_canary(
            route,
            opener,
            started_perf,
            served_model=served_model,
            served_revision=served_revision,
            observed_modalities=observed_modalities,
        )
    except _ProbeFailure as failure:
        outcome = failure.outcome
        metadata = failure.metadata
        observed = failure.observed
        quota = failure.quota

    completed = _as_utc(clock())
    if completed < started:
        completed = started
    implementation_path = root / IMPLEMENTATION_LABEL
    if not implementation_path.is_file():
        raise RouteQualificationError(f"Probe implementation is missing: {implementation_path}.")
    dependencies = [
        {"path": label, "content_sha256": sha256((root / label).read_bytes()).hexdigest()}
        for label in DEPENDENCY_LABELS
    ]
    payload = receipt_payload_with_hash(
        {
            "schema_version": "medphysbench.access-probe-receipt.v1",
            "receipt_id": f"{route.route_id}-{completed.strftime('%Y%m%dt%H%M%Sz').lower()}",
            "route_id": route.route_id,
            "route_spec_sha256": route.route_spec_sha256,
            "route_set_id": route_set.route_set_id,
            "fleet_id": route_set.fleet_id,
            "base_model_id": route.base_model_id,
            "adapter": route.adapter,
            "provider": route.provider,
            "model": route.model,
            "model_revision": route.model_revision,
            "probe_version": PROBE_VERSION,
            "probe_implementation_path": IMPLEMENTATION_LABEL,
            "probe_implementation_sha256": sha256(implementation_path.read_bytes()).hexdigest(),
            "probe_dependencies": dependencies,
            "source_commit": source_commit
            or _source_commit(
                root,
                required_paths=[
                    IMPLEMENTATION_LABEL,
                    *DEPENDENCY_LABELS,
                    route_set.source_label,
                    route_set.fleet_file,
                ],
            ),
            "started_at": _format_timestamp(started),
            "completed_at": _format_timestamp(completed),
            "expires_at": _format_timestamp(completed + timedelta(seconds=route.access_ttl_seconds)),
            "outcome": outcome,
            "capabilities": {"observed": sorted(observed), "inferred": sorted(route.modalities)},
            "quota": quota,
            "sanitized_metadata": metadata,
        }
    )
    destination_root = _receipt_root(output_root, root)
    destination = (
        destination_root
        / route.route_id
        / (f"{completed.strftime('%Y%m%dT%H%M%SZ')}-{payload['content_sha256'][:12]}.json")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    load_access_probe_receipt(destination, route_set, repository_root=root)
    return destination, payload


class _ProbeFailure(Exception):
    def __init__(
        self,
        *,
        outcome: str,
        metadata: dict[str, object],
        observed: list[str] | None = None,
        quota: dict[str, str] | None = None,
    ) -> None:
        self.outcome = outcome
        self.metadata = metadata
        self.observed = observed or []
        self.quota = quota or {"status": "unknown", "source": "local_runtime"}


def _resolve_route_identity(route: ModelRoute, opener: Callable[..., Any]) -> tuple[str, str]:
    request = urllib.request.Request(f"{route.base_url.rstrip('/')}/api/tags", method="GET")
    try:
        with opener(request, timeout=min(route.timeout_seconds, 30)) as response:
            body = response.read().decode("utf-8")
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as error:
        raise _ProbeFailure(
            outcome="network_error",
            metadata=_metadata(route, int(error.code), 0.0, error_code=f"ollama_tags_http_{error.code}"),
        ) from error
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise _ProbeFailure(
            outcome="network_error",
            metadata=_metadata(route, None, 0.0, error_code="ollama_tags_unreachable"),
        ) from error

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, status, 0.0, error_code="ollama_tags_invalid_json"),
        ) from error
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, status, 0.0, error_code="ollama_tags_missing_model_list"),
        )
    for item in models:
        if not isinstance(item, dict):
            continue
        if item.get("name") != route.model and item.get("model") != route.model:
            continue
        digest = item.get("digest")
        normalized_digest = _normalize_sha256(digest)
        if normalized_digest is None:
            raise _ProbeFailure(
                outcome="contract_unsupported",
                metadata=_metadata(route, status, 0.0, error_code="ollama_tags_invalid_digest"),
            )
        served_revision = f"sha256:{normalized_digest}"
        if not _digest_matches_route(route.model_revision, served_revision):
            raise _ProbeFailure(
                outcome="contract_unsupported",
                metadata=_metadata(
                    route,
                    status,
                    0.0,
                    served_model=str(item.get("model") or item.get("name") or route.model),
                    served_revision=served_revision,
                    error_code="ollama_digest_mismatch",
                ),
            )
        return str(item.get("model") or item.get("name") or route.model), served_revision
    raise _ProbeFailure(
        outcome="model_not_found",
        metadata=_metadata(route, status, 0.0, error_code="ollama_model_not_found"),
    )


def _observed_modalities(route: ModelRoute, opener: Callable[..., Any]) -> tuple[str, ...]:
    request = urllib.request.Request(
        f"{route.base_url.rstrip('/')}/api/show",
        data=json.dumps({"model": route.model}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=min(route.timeout_seconds, 30)) as response:
            body = response.read().decode("utf-8")
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        OSError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, None, 0.0, error_code="ollama_show_unavailable"),
        ) from error
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, None, 0.0, error_code="ollama_show_invalid_json"),
        ) from error
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, None, 0.0, error_code="ollama_show_missing_capabilities"),
        )
    observed = {"text"}
    lowered = {value.lower() for value in capabilities}
    if "vision" in lowered:
        observed.add("image")
    if "image" in route.modalities and "image" not in observed:
        raise _ProbeFailure(
            outcome="contract_unsupported",
            metadata=_metadata(route, None, 0.0, error_code="ollama_capability_mismatch"),
            observed=sorted(observed),
        )
    return tuple(sorted(observed))


def _run_json_canary(
    route: ModelRoute,
    opener: Callable[..., Any],
    started_perf: float,
    *,
    served_model: str,
    served_revision: str,
    observed_modalities: tuple[str, ...],
) -> tuple[str, dict[str, object], list[str], dict[str, str]]:
    request_payload = {
        "model": route.model,
        "stream": False,
        "think": False,
        "format": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {"status": {"const": "ok"}},
        },
        "messages": [
            {"role": "system", "content": "Return only the requested JSON object."},
            {"role": "user", "content": 'Return {"status":"ok"}.'},
        ],
        "options": {
            "temperature": 0,
            "seed": 20260731,
            "num_predict": 64,
            "num_ctx": route.ollama_num_ctx,
        },
        "keep_alive": route.ollama_keep_alive,
    }
    request = urllib.request.Request(
        f"{route.base_url.rstrip('/')}/api/chat",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=route.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            status = int(getattr(response, "status", 200))
        raw = json.loads(body)
        content = str(raw.get("message", {}).get("content", ""))
        decoded = decode_strict_json_object(content)
        if decoded != {"status": "ok"}:
            raise ValueError("unexpected_probe_payload")
        observed = sorted({*observed_modalities, "json_schema", "strict_schema"})
        return (
            "available",
            _metadata(
                route,
                status,
                round((time.perf_counter() - started_perf) * 1000, 3),
                served_model=served_model,
                served_revision=served_revision,
                response_contract="json_schema",
            ),
            observed,
            {"status": "sufficient", "source": "local_runtime"},
        )
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace").lower()
        outcome = "model_not_found" if error.code == 404 else "contract_unsupported"
        if error.code in {400, 422, 500} and "does not support images" in body:
            outcome = "contract_unsupported"
        return (
            outcome,
            _metadata(
                route,
                int(error.code),
                round((time.perf_counter() - started_perf) * 1000, 3),
                served_model=served_model,
                served_revision=served_revision,
                error_code=f"ollama_chat_http_{error.code}",
            ),
            list(observed_modalities),
            {"status": "unknown", "source": "local_runtime"},
        )
    except (urllib.error.URLError, OSError, TimeoutError):
        return (
            "network_error",
            _metadata(
                route,
                None,
                round((time.perf_counter() - started_perf) * 1000, 3),
                served_model=served_model,
                served_revision=served_revision,
                error_code="ollama_chat_unreachable",
            ),
            list(observed_modalities),
            {"status": "unknown", "source": "local_runtime"},
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return (
            "contract_unsupported",
            _metadata(
                route,
                200,
                round((time.perf_counter() - started_perf) * 1000, 3),
                served_model=served_model,
                served_revision=served_revision,
                error_code="invalid_or_unreachable_probe_response",
            ),
            list(observed_modalities),
            {"status": "unknown", "source": "local_runtime"},
        )


def _digest_matches_route(route_revision: str, served_revision: str) -> bool:
    normalized_route = route_revision.lower()
    normalized_served = served_revision.lower()
    if normalized_route == normalized_served:
        return True
    if normalized_route.startswith("sha256:"):
        return normalized_route[7:] == normalized_served.removeprefix("sha256:")
    return normalized_route == normalized_served.removeprefix("sha256:")


def _normalize_sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate.startswith("sha256:"):
        candidate = candidate[7:]
    if len(candidate) != 64:
        return None
    try:
        int(candidate, 16)
    except ValueError:
        return None
    return candidate


def _metadata(
    route: ModelRoute,
    status: int | None,
    latency_ms: float,
    *,
    served_model: str | None = None,
    served_revision: str | None = None,
    response_contract: str | None = None,
    error_code: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "endpoint_host": urllib.parse.urlsplit(route.base_url or "").hostname or "unknown",
        "latency_ms": latency_ms,
    }
    if status is not None:
        metadata["http_status"] = status
    if served_model is not None:
        metadata["served_model"] = served_model
    if served_revision is not None:
        metadata["served_revision"] = served_revision
    if response_contract is not None:
        metadata["response_contract"] = response_contract
    if error_code is not None:
        metadata["error_code"] = error_code
    return metadata


def _receipt_root(value: str | Path, root: Path) -> Path:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    allowed = (root / "receipts" / "access").resolve()
    if not resolved.is_relative_to(allowed):
        raise RouteQualificationError(f"Receipt output {value!r} must stay within receipts/access/.")
    return resolved


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RouteQualificationError("Timestamps must include a timezone.")
    return value.astimezone(UTC)


def _source_commit(root: Path, *, required_paths: list[str]) -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise RouteQualificationError("Cannot determine probe source_commit from Git.") from error
    for label in required_paths:
        try:
            subprocess.run(
                ["git", "cat-file", "-e", f"{commit}:{label}"],
                cwd=root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as error:
            raise RouteQualificationError(
                f"Current HEAD does not contain required probe dependency {label!r}."
            ) from error
    return commit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_set")
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--output-root", default="receipts/access")
    args = parser.parse_args()
    path, payload = probe_ollama_route(args.route_set, args.route_id, output_root=args.output_root)
    print(json.dumps({"receipt_path": str(path), "outcome": payload["outcome"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
