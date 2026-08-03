#!/usr/bin/env python3
"""Probe one OpenAI-compatible route without exposing benchmark tasks or provider bodies."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
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
IMPLEMENTATION_LABEL = "scripts/probes/openai_access_probe.py"
PROBE_VERSION = "openai-access-probe-v1"
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
_SECRET_PREFIX = re.compile(r"^(?:sk-|gsk_|ghp_|hf_|xox[pbar]-)", re.IGNORECASE)


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
    """Write one content-addressed access receipt; never load a benchmark task."""
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
            "source_commit": source_commit or _source_commit(
                root,
                required_paths=[IMPLEMENTATION_LABEL, route_set.source_label, route_set.fleet_file],
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
    destination = destination_root / route.route_id / (
        f"{completed.strftime('%Y%m%dT%H%M%SZ')}-{payload['content_sha256'][:12]}.json"
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
    request = urllib.request.Request(
        f"{route.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(
            {
                "model": route.model,
                "messages": [
                    {"role": "system", "content": "Return only the requested JSON object."},
                    {"role": "user", "content": "Return {\"status\":\"ok\"}."},
                ],
                "temperature": 0,
                "seed": 20260731,
                "max_completion_tokens": 64,
                "response_format": _response_format(route),
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "api-client/1.0 MedPhysBench-access-probe/1.0",
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
        observed = ["text", route.response_format]
        if route.strict_schema:
            observed.append("strict_schema")
        return "available", metadata, observed, _quota(headers)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        outcome, error_code = _http_failure(int(error.code), body)
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


def _response_format(route: ModelRoute) -> dict[str, object]:
    if route.response_format == "json_object":
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "medphysbench_access_probe",
            "strict": route.strict_schema,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status"],
                "properties": {"status": {"const": "ok"}},
            },
        },
    }


def _metadata(
    route: ModelRoute,
    status: int,
    headers: Mapping[str, Any],
    elapsed_seconds: float,
    raw: Mapping[str, Any],
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "endpoint_host": _endpoint_host(route.base_url or ""),
        "http_status": status,
        "latency_ms": round(elapsed_seconds * 1000, 3),
        "response_contract": route.response_format,
    }
    request_id = _header(headers, "x-request-id")
    if request_id:
        metadata["provider_request_id"] = _safe_identifier(request_id)
    if isinstance(raw.get("model"), str):
        metadata["served_model"] = _safe_identifier(str(raw["model"]))
    if isinstance(raw.get("model_revision"), str):
        metadata["served_revision"] = _safe_identifier(str(raw["model_revision"]))
    return metadata


def _quota(headers: Mapping[str, Any]) -> dict[str, str]:
    remaining = _header(headers, "x-ratelimit-remaining-requests")
    if remaining is not None:
        try:
            status = "sufficient" if float(remaining) > 0 else "insufficient"
            return {"status": status, "source": "provider_headers"}
        except ValueError:
            pass
    return {"status": "unknown", "source": "not_exposed"}


def _http_failure(status: int, body: str) -> tuple[str, str]:
    if status in {401, 403}:
        return "auth_missing", "provider_auth_rejected"
    if status == 404:
        return "model_not_found", "provider_model_not_found"
    if status == 429:
        lowered = body.lower()
        if "quota" in lowered or "usage limit" in lowered:
            return "quota_exhausted", "provider_quota_exhausted"
        return "rate_limited", "provider_rate_limited"
    return "network_error", f"provider_http_{status}"


def _header(headers: Mapping[str, Any], key: str) -> str | None:
    value = headers.get(key) or headers.get(key.title())
    return str(value) if value is not None else None


def _safe_identifier(value: str) -> str:
    candidate = value.strip()
    if _SAFE_IDENTIFIER.fullmatch(candidate) and not _SECRET_PREFIX.match(candidate):
        return candidate
    return f"sha256:{sha256(candidate.encode('utf-8')).hexdigest()}"


def _endpoint_host(base_url: str) -> str:
    return urllib.parse.urlsplit(base_url).hostname or "unknown"


def _receipt_root(value: str | Path, root: Path) -> Path:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    allowed = (root / "receipts" / "access").resolve()
    if not resolved.is_relative_to(allowed):
        raise RouteQualificationError("Probe output_root must stay under receipts/access/.")
    return resolved


def _source_commit(root: Path, *, required_paths: list[str]) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip().lower()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RouteQualificationError("Cannot resolve a full source commit for the access probe.")
    for label in required_paths:
        committed = subprocess.run(
            ["git", "show", f"{commit}:{label}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        if committed != (root / label).read_bytes():
            raise RouteQualificationError(
                f"Access probe requires committed, byte-identical source artifact {label!r}."
            )
    return commit


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RouteQualificationError("Probe clocks must include a timezone.")
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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
