#!/usr/bin/env python3
"""Probe an Ollama Cloud route while preserving hosted access and quota semantics.

The local Ollama daemon proxies these requests, but HTTP 401/403/429 responses
describe hosted access rather than a broken local model contract. This versioned
probe keeps the original local-runtime probe immutable and stores no provider
response body.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
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
from scripts.probes.ollama_access_probe import (
    _as_utc,
    _format_timestamp,
    _metadata,
    _observed_modalities,
    _ProbeFailure,
    _receipt_root,
    _resolve_route_identity,
    _source_commit,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_LABEL = "scripts/probes/ollama_cloud_access_probe_v2.py"
PROBE_VERSION = "ollama-cloud-access-probe-v2"
DEPENDENCY_LABELS = (
    "scripts/probes/ollama_access_probe.py",
    "src/medphys_agentbench/adapters/ollama.py",
    "src/medphys_agentbench/json_utils.py",
    "src/medphys_agentbench/route_qualification.py",
)


def probe_ollama_cloud_route(
    route_set_path: str | Path,
    route_id: str,
    *,
    output_root: str | Path = "receipts/access",
    repository_root: Path = REPOSITORY_ROOT,
    opener: Callable[..., Any] = urllib.request.urlopen,
    now: Callable[[], datetime] | None = None,
    source_commit: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write one content-addressed hosted-route receipt without benchmark tasks."""
    root = repository_root.resolve()
    route_set = load_route_set(route_set_path, repository_root=root)
    route = route_set.route(route_id)
    if route.adapter != "ollama" or route.revision_basis != "provider_snapshot":
        raise RouteQualificationError(
            f"Route {route_id!r} is not a snapshot-pinned Ollama Cloud route."
        )
    if not route.base_url:
        raise RouteQualificationError(f"Route {route_id!r} has no frozen Ollama proxy endpoint.")

    clock = now or (lambda: datetime.now(UTC))
    started = _as_utc(clock())
    started_perf = time.perf_counter()
    try:
        served_model, served_revision = _resolve_route_identity(route, opener)
        observed_modalities = _observed_modalities(route, opener)
        outcome, metadata, observed, quota = _run_cloud_json_canary(
            route,
            opener,
            started_perf,
            served_model=served_model,
            served_revision=served_revision,
            observed_modalities=observed_modalities,
        )
    except _ProbeFailure as error:
        outcome = error.outcome
        metadata = error.metadata
        observed = error.observed
        quota = error.quota

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
        / f"{completed.strftime('%Y%m%dT%H%M%SZ')}-{payload['content_sha256'][:12]}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    load_access_probe_receipt(destination, route_set, repository_root=root)
    return destination, payload


def _run_cloud_json_canary(
    route: ModelRoute,
    opener: Callable[..., Any],
    started_perf: float,
    *,
    served_model: str,
    served_revision: str,
    observed_modalities: tuple[str, ...],
) -> tuple[str, dict[str, object], list[str], dict[str, str]]:
    payload = {
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
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=route.timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
            status = int(getattr(response, "status", 200))
        decoded = decode_strict_json_object(str(raw.get("message", {}).get("content", "")))
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
            {"status": "unknown", "source": "not_exposed"},
        )
    except urllib.error.HTTPError as error:
        # Consume and discard the response so secrets or generated text never reach the receipt.
        error.read()
        outcome, error_code, quota = _classify_cloud_http_failure(int(error.code))
        return (
            outcome,
            _metadata(
                route,
                int(error.code),
                round((time.perf_counter() - started_perf) * 1000, 3),
                served_model=served_model,
                served_revision=served_revision,
                error_code=error_code,
            ),
            list(observed_modalities),
            quota,
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
                error_code="ollama_cloud_unreachable",
            ),
            list(observed_modalities),
            {"status": "unknown", "source": "not_exposed"},
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
            {"status": "unknown", "source": "not_exposed"},
        )


def _classify_cloud_http_failure(status: int) -> tuple[str, str, dict[str, str]]:
    if status == 429:
        return "rate_limited", "ollama_cloud_rate_limited", {
            "status": "insufficient",
            "source": "not_exposed",
        }
    if status in {401, 403}:
        return "auth_missing", "ollama_cloud_auth_required", {
            "status": "unknown",
            "source": "not_exposed",
        }
    if status == 404:
        return "model_not_found", "ollama_cloud_model_not_found", {
            "status": "unknown",
            "source": "not_exposed",
        }
    if status in {408, 502, 503, 504}:
        return "network_error", f"ollama_cloud_http_{status}", {
            "status": "unknown",
            "source": "not_exposed",
        }
    return "contract_unsupported", f"ollama_cloud_http_{status}", {
        "status": "unknown",
        "source": "not_exposed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_set")
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--output-root", default="receipts/access")
    args = parser.parse_args()
    try:
        path, payload = probe_ollama_cloud_route(
            args.route_set,
            args.route_id,
            output_root=args.output_root,
        )
    except (RouteQualificationError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps({"receipt_path": str(path), "outcome": payload["outcome"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
