#!/usr/bin/env python3
"""Probe a reasoning route with a budgeted, schema-enforced JSON canary.

This version exists instead of modifying v2 because published receipts bind the
exact v2 implementation and dependency bytes. It keeps the benchmark task set
sealed, uses a fixed non-benchmark schema, and stores no provider response body.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from medphys_agentbench.adapters.openai_compatible import apply_openai_request_dialect
from medphys_agentbench.json_utils import decode_strict_json_object
from medphys_agentbench.route_qualification import (
    ModelRoute,
    RouteQualificationError,
    load_access_probe_receipt,
    load_route_set,
    receipt_payload_with_hash,
)
from scripts.probes.openai_access_probe import (
    _as_utc,
    _endpoint_host,
    _format_timestamp,
    _http_failure,
    _metadata,
    _quota,
    _receipt_root,
    _safe_identifier,
    _source_commit,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_LABEL = "scripts/probes/openai_access_probe_v3.py"
PROBE_VERSION = "openai-access-probe-v3"
PROBE_MAX_TOKENS = 512
DEPENDENCY_LABELS = (
    "scripts/probes/openai_access_probe.py",
    "src/medphys_agentbench/adapters/openai_compatible.py",
    "src/medphys_agentbench/json_utils.py",
    "src/medphys_agentbench/route_qualification.py",
)


def probe_openai_route(
    route_set_path: str | Path,
    route_id: str,
    *,
    output_root: str | Path = "receipts/access",
    environ: Mapping[str, str] | None = None,
    repository_root: Path = REPOSITORY_ROOT,
    opener: Callable[..., Any] = urllib.request.urlopen,
    now: Callable[[], datetime] | None = None,
    source_commit: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write one content-addressed receipt without loading a benchmark task."""
    root = repository_root.resolve()
    route_set = load_route_set(route_set_path, repository_root=root)
    route = route_set.route(route_id)
    if route.adapter not in {"groq", "openai", "openai-compatible"}:
        raise RouteQualificationError(f"Route {route_id!r} is not OpenAI-compatible.")
    if not route.base_url or not route.api_key_env:
        raise RouteQualificationError(f"Route {route_id!r} has no frozen endpoint/credential environment.")
    environment = os.environ if environ is None else environ
    clock = now or (lambda: datetime.now(UTC))
    started = _as_utc(clock())
    started_perf = time.perf_counter()
    api_key = environment.get(route.api_key_env)

    if not api_key:
        outcome = "auth_missing"
        metadata: dict[str, object] = {
            "endpoint_host": _endpoint_host(route.base_url),
            "error_code": "credential_environment_unset",
        }
        observed: list[str] = []
        quota = {"status": "unknown", "source": "not_exposed"}
    else:
        outcome, metadata, observed, quota = _make_probe_request(route, api_key, opener, started_perf)

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


def _make_probe_request(
    route: ModelRoute,
    api_key: str,
    opener: Callable[..., Any],
    started_perf: float,
) -> tuple[str, dict[str, object], list[str], dict[str, str]]:
    request_payload = apply_openai_request_dialect(
        {
            "model": route.model,
            "messages": [
                {"role": "system", "content": "Return only the requested JSON object."},
                {"role": "user", "content": 'Return {"status":"ok"}.'},
            ],
            **_response_format_payload(route),
        },
        temperature=0,
        seed=20260731,
        max_tokens=PROBE_MAX_TOKENS,
        send_temperature=route.send_temperature,
        send_seed=route.send_seed,
        completion_limit_field=route.completion_limit_field,
    )
    if route.send_reasoning_effort and route.reasoning_effort is not None:
        request_payload["reasoning_effort"] = route.reasoning_effort
    if route.reasoning_format is not None:
        request_payload["reasoning_format"] = route.reasoning_format
    request = urllib.request.Request(
        f"{route.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "api-client/1.0 MedPhysBench-access-probe/3.0",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=route.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            headers = response.headers
            status = int(getattr(response, "status", 200))
        raw = json.loads(body)
        content = raw["choices"][0]["message"]["content"]
        decoded = decode_strict_json_object(content)
        if decoded != {"status": "ok"}:
            raise ValueError("unexpected_probe_payload")
        metadata = _metadata(route, status, headers, time.perf_counter() - started_perf, raw)
        if route.response_format_dialect == "omit":
            metadata["response_contract"] = "adapter_local_json_parse"
            metadata["error_code"] = "provider_response_contract_unproven"
            return "contract_unsupported", metadata, ["json_parseable", "text"], _quota(headers)
        observed = ["text", route.response_format]
        if route.strict_schema:
            observed.append("strict_schema")
        return "available", metadata, observed, _quota(headers)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        outcome, error_code = _classified_http_failure(int(error.code), body)
        metadata = _metadata(route, int(error.code), error.headers, time.perf_counter() - started_perf, {})
        metadata["error_code"] = error_code
        quota = _quota(error.headers)
        if error.code == 429:
            quota = {"status": "insufficient", "source": quota["source"]}
        return outcome, metadata, [], quota
    except (urllib.error.URLError, OSError):
        return (
            "network_error",
            {
                "endpoint_host": _endpoint_host(route.base_url),
                "latency_ms": round((time.perf_counter() - started_perf) * 1000, 3),
                "error_code": "provider_network_error",
            },
            [],
            {"status": "unknown", "source": "not_exposed"},
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return (
            "contract_unsupported",
            {
                "endpoint_host": _endpoint_host(route.base_url),
                "latency_ms": round((time.perf_counter() - started_perf) * 1000, 3),
                "error_code": "invalid_or_unreachable_probe_response",
            },
            [],
            {"status": "unknown", "source": "not_exposed"},
        )


def _classified_http_failure(status: int, body: str) -> tuple[str, str]:
    if status != 400:
        return _http_failure(status, body)
    provider_code = _provider_error_identifier(body)
    return "contract_unsupported", f"provider_http_400_{provider_code}"


def _response_format_payload(route: ModelRoute) -> dict[str, object]:
    if route.response_format_dialect == "omit":
        return {}
    if route.response_format == "json_object":
        return {"response_format": {"type": "json_object"}}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["ok"]}},
    }
    if route.response_format_dialect == "cohere":
        return {"response_format": {"type": "json_object", "schema": schema}}
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "medphysbench_access_probe",
                "strict": route.strict_schema,
                "schema": schema,
            },
        }
    }


def _provider_error_identifier(body: str) -> str:
    try:
        raw = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return "invalid_request"
    error = raw.get("error") if isinstance(raw, dict) else None
    candidates = []
    if isinstance(error, dict):
        candidates.extend((error.get("code"), error.get("type")))
    if isinstance(raw, dict):
        candidates.extend((raw.get("code"), raw.get("type")))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            safe = _safe_identifier(candidate.strip())
            if not safe.startswith("sha256:"):
                return safe.replace("/", "_").replace(":", "_")
    return "invalid_request"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_set_file", type=Path)
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--output-root", default="receipts/access")
    args = parser.parse_args()
    try:
        path, payload = probe_openai_route(
            args.route_set_file,
            args.route_id,
            output_root=args.output_root,
        )
    except (RouteQualificationError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps({"receipt": str(path), "outcome": payload["outcome"]}, sort_keys=True))
    if payload["outcome"] != "available":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
