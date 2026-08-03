from __future__ import annotations

import io
import json
import shutil
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from medphys_agentbench.route_qualification import load_access_probe_receipt, load_route_set
from scripts.probes.openai_access_probe import probe_openai_route

ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        self.status = 200
        self.headers = headers or {}
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _probe_repository(tmp_path: Path) -> tuple[Path, str]:
    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "fleet" / "public_fleet_v1.yaml", fleet_dir / "public_fleet_v1.yaml")
    shutil.copy2(ROOT / "fleet" / "model_routes_v1.yaml", fleet_dir / "model_routes_v1.yaml")
    implementation = tmp_path / "scripts" / "probes" / "openai_access_probe.py"
    implementation.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "probes" / "openai_access_probe.py", implementation)
    route_set = load_route_set(fleet_dir / "model_routes_v1.yaml", repository_root=tmp_path)
    return fleet_dir / "model_routes_v1.yaml", route_set.routes[0].route_id


def _clock() -> Any:
    values = iter(
        [
            datetime(2026, 8, 3, 7, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 3, 7, 0, 1, tzinfo=UTC),
        ]
    )
    return lambda: next(values)


def test_probe_writes_valid_contract_evidence_without_scores_or_secrets(tmp_path: Path) -> None:
    route_set_path, route_id = _probe_repository(tmp_path)
    secret = "gsk_TEST_PROVIDER_KEY_NOT_FOR_STORAGE"

    def opener(*_args: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(
            {
                "model": "llama-3.1-8b-instant",
                "choices": [{"message": {"content": '{"status":"ok"}'}}],
            },
            {"x-request-id": secret, "x-ratelimit-remaining-requests": "99"},
        )

    path, payload = probe_openai_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": secret},
        opener=opener,
        now=_clock(),
        source_commit="a" * 40,
    )

    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    receipt = load_access_probe_receipt(path, route_set, repository_root=tmp_path)
    assert receipt.outcome == "available"
    assert payload["quota"]["status"] == "sufficient"
    assert payload["capabilities"]["observed"] == ["json_object", "text"]
    assert secret not in path.read_text(encoding="utf-8")
    assert str(payload["sanitized_metadata"]["provider_request_id"]).startswith("sha256:")
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "results").exists()


def test_probe_records_missing_credential_without_network_call(tmp_path: Path) -> None:
    route_set_path, route_id = _probe_repository(tmp_path)
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> _FakeResponse:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be called")

    _path, payload = probe_openai_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        environ={},
        opener=opener,
        now=_clock(),
        source_commit="a" * 40,
    )

    assert calls == 0
    assert payload["outcome"] == "auth_missing"
    assert payload["sanitized_metadata"]["error_code"] == "credential_environment_unset"


@pytest.mark.parametrize(
    ("status", "body", "expected_outcome"),
    [
        (401, b'{"error":"sensitive auth detail"}', "auth_missing"),
        (404, b'{"error":"sensitive model detail"}', "model_not_found"),
        (429, b'{"error":"quota exhausted sensitive detail"}', "quota_exhausted"),
        (429, b'{"error":"temporarily throttled sensitive detail"}', "rate_limited"),
    ],
)
def test_probe_maps_provider_failures_without_persisting_raw_body(
    tmp_path: Path,
    status: int,
    body: bytes,
    expected_outcome: str,
) -> None:
    route_set_path, route_id = _probe_repository(tmp_path)

    def opener(*_args: object, **_kwargs: object) -> _FakeResponse:
        raise urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            status,
            "provider failure",
            {"x-request-id": "request-failure"},
            io.BytesIO(body),
        )

    path, payload = probe_openai_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": "test-only"},
        opener=opener,
        now=_clock(),
        source_commit="a" * 40,
    )

    assert payload["outcome"] == expected_outcome
    assert "sensitive" not in path.read_text(encoding="utf-8")
    if status == 429:
        assert payload["quota"]["status"] == "insufficient"
