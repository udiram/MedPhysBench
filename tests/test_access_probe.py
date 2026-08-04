from __future__ import annotations

import io
import json
import shutil
import urllib.error
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
import yaml

from medphys_agentbench.route_qualification import (
    load_access_probe_receipt,
    load_route_set,
    receipt_payload_with_hash,
)
from scripts.probes.ollama_access_probe import probe_ollama_route
from scripts.probes.openai_access_probe import probe_openai_route
from scripts.probes.openai_access_probe_v2 import probe_openai_route as probe_openai_route_v2
from scripts.probes.openai_access_probe_v3 import DEPENDENCY_LABELS as V3_DEPENDENCY_LABELS
from scripts.probes.openai_access_probe_v3 import PROBE_MAX_TOKENS
from scripts.probes.openai_access_probe_v3 import probe_openai_route as probe_openai_route_v3

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


def _ollama_clock() -> Any:
    values = iter(
        [
            datetime(2026, 8, 3, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 3, 13, 0, 1, tzinfo=UTC),
        ]
    )
    return lambda: next(values)


def _v3_clock() -> Any:
    values = iter(
        [
            datetime(2026, 8, 4, 5, 20, 0, tzinfo=UTC),
            datetime(2026, 8, 4, 5, 20, 1, tzinfo=UTC),
        ]
    )
    return lambda: next(values)


def _copy_v2_probe_contract(tmp_path: Path) -> None:
    labels = (
        "scripts/probes/openai_access_probe_v2.py",
        "src/medphys_agentbench/adapters/openai_compatible.py",
        "src/medphys_agentbench/json_utils.py",
        "src/medphys_agentbench/route_qualification.py",
    )
    for label in labels:
        destination = tmp_path / label
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / label, destination)


def _copy_v3_probe_contract(tmp_path: Path) -> None:
    labels = (
        "scripts/probes/openai_access_probe_v3.py",
        *V3_DEPENDENCY_LABELS,
    )
    for label in labels:
        destination = tmp_path / label
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / label, destination)


def _ollama_probe_repository(tmp_path: Path) -> tuple[Path, str]:
    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "fleet" / "public_fleet_v1.yaml", fleet_dir / "public_fleet_v1.yaml")
    shutil.copy2(ROOT / "fleet" / "local_ollama_routes_v1.yaml", fleet_dir / "local_ollama_routes_v1.yaml")
    labels = (
        "scripts/probes/ollama_access_probe.py",
        "src/medphys_agentbench/adapters/ollama.py",
        "src/medphys_agentbench/json_utils.py",
        "src/medphys_agentbench/route_qualification.py",
    )
    for label in labels:
        destination = tmp_path / label
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / label, destination)
    route_set_path = fleet_dir / "local_ollama_routes_v1.yaml"
    load_route_set(route_set_path, repository_root=tmp_path)
    return route_set_path, "ollama-qwen2-5vl-3b"


def test_v1_probe_bytes_remain_frozen() -> None:
    assert sha256((ROOT / "scripts" / "probes" / "openai_access_probe.py").read_bytes()).hexdigest() == (
        "7213f4dc7971bbef238d1a77145ec9c62a6c29392f30df271237547cf4c188df"
    )


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


def test_probe_uses_the_route_request_dialect(tmp_path: Path) -> None:
    route_set_path, route_id = _probe_repository(tmp_path)
    route_set_payload = yaml.safe_load(route_set_path.read_text(encoding="utf-8"))
    route = next(item for item in route_set_payload["routes"] if item["route_id"] == route_id)
    route.update(send_temperature=False, send_seed=False, completion_limit_field="max_tokens")
    route.update(response_format="json_schema", response_format_dialect="cohere")
    route.update(reasoning_effort="none", reasoning_format="hidden")
    route_set_path.write_text(yaml.safe_dump(route_set_payload, sort_keys=False), encoding="utf-8")
    _copy_v2_probe_contract(tmp_path)
    adapter_dependency = tmp_path / "src" / "medphys_agentbench" / "adapters" / "openai_compatible.py"
    captured: dict[str, object] = {}

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": '{"status":"ok"}'}}]})

    _path, receipt = probe_openai_route_v2(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": "test-only"},
        opener=opener,
        now=_clock(),
        source_commit="a" * 40,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "temperature" not in payload
    assert "seed" not in payload
    assert "max_completion_tokens" not in payload
    assert payload["max_tokens"] == 64
    assert payload["response_format"]["type"] == "json_object"
    assert payload["response_format"]["schema"]["required"] == ["status"]
    assert payload["reasoning_effort"] == "none"
    assert payload["reasoning_format"] == "hidden"
    assert receipt["probe_version"] == "openai-access-probe-v2"
    assert {item["path"] for item in receipt["probe_dependencies"]} == {
        "scripts/probes/openai_access_probe.py",
        "src/medphys_agentbench/adapters/openai_compatible.py",
        "src/medphys_agentbench/json_utils.py",
        "src/medphys_agentbench/route_qualification.py",
    }

    forged = {key: value for key, value in receipt.items() if key not in {"content_sha256", "probe_dependencies"}}
    _path.write_text(json.dumps(receipt_payload_with_hash(forged)), encoding="utf-8")
    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    with pytest.raises(ValueError, match="probe_dependencies"):
        load_access_probe_receipt(_path, route_set, repository_root=tmp_path)
    _path.write_text(json.dumps(receipt), encoding="utf-8")

    wrong_implementation = {key: value for key, value in receipt.items() if key != "content_sha256"}
    wrong_implementation["probe_implementation_path"] = "scripts/probes/openai_access_probe.py"
    wrong_implementation["probe_implementation_sha256"] = sha256(
        (tmp_path / "scripts" / "probes" / "openai_access_probe.py").read_bytes()
    ).hexdigest()
    _path.write_text(json.dumps(receipt_payload_with_hash(wrong_implementation)), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected implementation path"):
        load_access_probe_receipt(_path, route_set, repository_root=tmp_path)
    _path.write_text(json.dumps(receipt), encoding="utf-8")

    adapter_dependency.write_text("# tampered after probe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dependency hash mismatch"):
        load_access_probe_receipt(_path, route_set, repository_root=tmp_path)

    shutil.copy2(ROOT / "src" / "medphys_agentbench" / "adapters" / "openai_compatible.py", adapter_dependency)
    json_dependency = tmp_path / "src" / "medphys_agentbench" / "json_utils.py"
    json_dependency.write_text("# tampered strict decoder after probe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dependency hash mismatch"):
        load_access_probe_receipt(_path, route_set, repository_root=tmp_path)

    shutil.copy2(ROOT / "src" / "medphys_agentbench" / "json_utils.py", json_dependency)
    route_dependency = tmp_path / "src" / "medphys_agentbench" / "route_qualification.py"
    route_dependency.write_text("# tampered receipt validator after probe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dependency hash mismatch"):
        load_access_probe_receipt(_path, route_set, repository_root=tmp_path)


def test_v2_probe_does_not_promote_local_json_parsing_as_provider_contract(tmp_path: Path) -> None:
    route_set_path, route_id = _probe_repository(tmp_path)
    route_set_payload = yaml.safe_load(route_set_path.read_text(encoding="utf-8"))
    route = next(item for item in route_set_payload["routes"] if item["route_id"] == route_id)
    route.update(response_format="json_schema", response_format_dialect="omit", strict_schema=False)
    route_set_path.write_text(yaml.safe_dump(route_set_payload, sort_keys=False), encoding="utf-8")
    _copy_v2_probe_contract(tmp_path)
    captured: dict[str, object] = {}

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return _FakeResponse({"choices": [{"message": {"content": '{"status":"ok"}'}}]})

    path, receipt = probe_openai_route_v2(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": "test-only"},
        opener=opener,
        now=_clock(),
        source_commit="a" * 40,
    )

    assert "response_format" not in captured["payload"]
    assert receipt["outcome"] == "contract_unsupported"
    assert receipt["capabilities"]["observed"] == ["json_parseable", "text"]
    assert receipt["sanitized_metadata"]["response_contract"] == "adapter_local_json_parse"
    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    assert load_access_probe_receipt(path, route_set, repository_root=tmp_path).outcome == "contract_unsupported"

    forged = {key: value for key, value in receipt.items() if key != "content_sha256"}
    forged["outcome"] = "available"
    forged["capabilities"] = {"observed": ["json_schema", "text"], "inferred": ["text"]}
    forged["sanitized_metadata"] = dict(forged["sanitized_metadata"])
    forged["sanitized_metadata"]["response_contract"] = "json_schema"
    path.write_text(json.dumps(receipt_payload_with_hash(forged)), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot prove a provider response contract"):
        load_access_probe_receipt(path, route_set, repository_root=tmp_path)


def test_v3_probe_uses_budgeted_strict_schema_reasoning_contract(tmp_path: Path) -> None:
    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "fleet" / "public_fleet_v1.yaml", fleet_dir / "public_fleet_v1.yaml")
    shutil.copy2(ROOT / "fleet" / "groq_gpt_oss_routes_v3.yaml", fleet_dir / "groq_gpt_oss_routes_v3.yaml")
    _copy_v3_probe_contract(tmp_path)
    captured: dict[str, object] = {}

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return _FakeResponse(
            {"model": "openai/gpt-oss-120b", "choices": [{"message": {"content": '{"status":"ok"}'}}]},
            {"x-ratelimit-remaining-requests": "10"},
        )

    route_set_path = fleet_dir / "groq_gpt_oss_routes_v3.yaml"
    path, receipt = probe_openai_route_v3(
        route_set_path,
        "groq-gpt-oss-120b-schema-v3",
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": "test-only"},
        opener=opener,
        now=_v3_clock(),
        source_commit="a" * 40,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["max_completion_tokens"] == PROBE_MAX_TOKENS == 512
    assert payload["reasoning_effort"] == "low"
    assert "reasoning_format" not in payload
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "medphysbench_access_probe",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status"],
                "properties": {"status": {"type": "string", "enum": ["ok"]}},
            },
        },
    }
    assert receipt["outcome"] == "available"
    assert receipt["capabilities"]["observed"] == ["json_schema", "strict_schema", "text"]
    assert {item["path"] for item in receipt["probe_dependencies"]} == set(V3_DEPENDENCY_LABELS)
    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    assert load_access_probe_receipt(path, route_set, repository_root=tmp_path).outcome == "available"


def test_v3_probe_classifies_sanitized_http_400_without_persisting_body(tmp_path: Path) -> None:
    fleet_dir = tmp_path / "fleet"
    fleet_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "fleet" / "public_fleet_v1.yaml", fleet_dir / "public_fleet_v1.yaml")
    shutil.copy2(ROOT / "fleet" / "groq_gpt_oss_routes_v3.yaml", fleet_dir / "groq_gpt_oss_routes_v3.yaml")
    _copy_v3_probe_contract(tmp_path)
    sensitive_message = "request details that must not be stored"

    def opener(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            400,
            "Bad Request",
            {"x-ratelimit-remaining-requests": "10"},
            io.BytesIO(
                json.dumps(
                    {
                        "error": {
                            "code": "json_validate_failed",
                            "type": "invalid_request_error",
                            "message": sensitive_message,
                        }
                    }
                ).encode("utf-8")
            ),
        )

    route_set_path = fleet_dir / "groq_gpt_oss_routes_v3.yaml"
    path, receipt = probe_openai_route_v3(
        route_set_path,
        "groq-gpt-oss-120b-schema-v3",
        repository_root=tmp_path,
        environ={"GROQ_API_KEY": "test-only"},
        opener=opener,
        now=_v3_clock(),
        source_commit="a" * 40,
    )

    assert receipt["outcome"] == "contract_unsupported"
    assert receipt["sanitized_metadata"]["http_status"] == 400
    assert receipt["sanitized_metadata"]["error_code"] == "provider_http_400_json_validate_failed"
    assert sensitive_message not in path.read_text(encoding="utf-8")


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


def test_ollama_probe_writes_valid_local_runtime_receipt_without_scores(tmp_path: Path) -> None:
    route_set_path, route_id = _ollama_probe_repository(tmp_path)
    calls: list[str] = []

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        url = request.full_url
        calls.append(url)
        if url.endswith("/api/tags"):
            return _FakeResponse(
                {
                    "models": [
                        {
                            "name": "qwen2.5vl:3b",
                            "model": "qwen2.5vl:3b",
                            "digest": "sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1",
                        }
                    ]
                }
            )
        if url.endswith("/api/show"):
            return _FakeResponse({"capabilities": ["vision"]})
        if url.endswith("/api/chat"):
            payload = json.loads(bytes(request.data or b"").decode("utf-8"))
            assert payload["options"]["num_predict"] == 64
            assert payload["options"]["num_ctx"] == 4096
            assert payload["keep_alive"] == 0
            return _FakeResponse({"message": {"content": '{"status":"ok"}'}})
        raise AssertionError(f"unexpected URL {url}")

    path, payload = probe_ollama_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        opener=opener,
        now=_ollama_clock(),
        source_commit="a" * 40,
    )

    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    receipt = load_access_probe_receipt(path, route_set, repository_root=tmp_path)
    assert receipt.outcome == "available"
    assert payload["quota"] == {"status": "sufficient", "source": "local_runtime"}
    assert payload["sanitized_metadata"]["served_revision"] == (
        "sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1"
    )
    assert payload["capabilities"]["observed"] == ["image", "json_schema", "strict_schema", "text"]
    assert calls == [
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.1:11434/api/show",
        "http://127.0.0.1:11434/api/chat",
    ]
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "results").exists()


def test_ollama_probe_rejects_digest_mismatch_before_canary(tmp_path: Path) -> None:
    route_set_path, route_id = _ollama_probe_repository(tmp_path)
    calls: list[str] = []

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        url = request.full_url
        calls.append(url)
        if url.endswith("/api/tags"):
            return _FakeResponse(
                {
                    "models": [
                        {
                            "name": "qwen2.5vl:3b",
                            "model": "qwen2.5vl:3b",
                            "digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        }
                    ]
                }
            )
        raise AssertionError("canary should not run after a digest mismatch")

    path, payload = probe_ollama_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        opener=opener,
        now=_ollama_clock(),
        source_commit="a" * 40,
    )

    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    assert load_access_probe_receipt(path, route_set, repository_root=tmp_path).outcome == "contract_unsupported"
    assert payload["outcome"] == "contract_unsupported"
    assert payload["sanitized_metadata"]["error_code"] == "ollama_digest_mismatch"
    assert calls == ["http://127.0.0.1:11434/api/tags"]


@pytest.mark.parametrize(
    ("failure_mode", "expected_outcome", "expected_error"),
    [
        ("daemon_unreachable", "network_error", "ollama_tags_unreachable"),
        ("model_missing", "model_not_found", "ollama_model_not_found"),
        ("invalid_canary", "contract_unsupported", "invalid_or_unreachable_probe_response"),
    ],
)
def test_ollama_probe_records_typed_failures_without_score_artifacts(
    tmp_path: Path,
    failure_mode: str,
    expected_outcome: str,
    expected_error: str,
) -> None:
    route_set_path, route_id = _ollama_probe_repository(tmp_path)

    def opener(request: Any, **_kwargs: object) -> _FakeResponse:
        url = request.full_url
        if url.endswith("/api/tags"):
            if failure_mode == "daemon_unreachable":
                raise urllib.error.URLError("local daemon unavailable")
            models = [] if failure_mode == "model_missing" else [
                {
                    "name": "qwen2.5vl:3b",
                    "model": "qwen2.5vl:3b",
                    "digest": "sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1",
                }
            ]
            return _FakeResponse({"models": models})
        if url.endswith("/api/show"):
            return _FakeResponse({"capabilities": ["vision"]})
        if url.endswith("/api/chat"):
            return _FakeResponse({"message": {"content": "not-json"}})
        raise AssertionError(f"unexpected URL {url}")

    path, payload = probe_ollama_route(
        route_set_path,
        route_id,
        repository_root=tmp_path,
        opener=opener,
        now=_ollama_clock(),
        source_commit="a" * 40,
    )

    route_set = load_route_set(route_set_path, repository_root=tmp_path)
    receipt = load_access_probe_receipt(path, route_set, repository_root=tmp_path)
    assert receipt.outcome == expected_outcome
    assert payload["sanitized_metadata"]["error_code"] == expected_error
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "results").exists()
