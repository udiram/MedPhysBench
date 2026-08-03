from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import urllib.request

import pytest

from medphys_agentbench.adapters.ollama import AdapterError
from medphys_agentbench.adapters.openai_compatible import (
    OpenAICompatibleAdapter,
    ProviderOutputContractError,
    UnsupportedCapabilityError,
)
from medphys_agentbench.cli import _build_adapter
from medphys_agentbench.task_loader import load_task


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_compatible_propagates_common_harness_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["user_agent"] = request.get_header("User-agent")
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return _FakeResponse(
            {
                "id": "req-test",
                "system_fingerprint": "fp-test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"distance_cm":100,"answer_ratio":0.25,'
                                '"requires_escalation":false,"assumptions":[]}'
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60},
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="openai/gpt-oss-120b",
        api_key="secret-not-recorded",
        base_url="https://api.example.test/v1",
        provider="groq",
        temperature=0.0,
        seed=17,
        max_tokens=512,
        timeout_seconds=30,
        reasoning_effort="high",
    )

    result = adapter.execute(task)
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["timeout"] == 30
    assert captured["authorization"] == "Bearer secret-not-recorded"
    assert captured["user_agent"] == "api-client/1.0 MedPhysBench/0.6.0"
    assert payload["seed"] == 17
    assert payload["temperature"] == 0.0
    assert payload["max_completion_tokens"] == 512
    assert payload["reasoning_effort"] == "high"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"] == task.expected_output_schema
    assert result.final_output["answer_ratio"] == 0.25
    assert result.raw_response["usage"]["total_tokens"] == 60
    assert "secret-not-recorded" not in json.dumps(result.raw_response)


def test_openai_compatible_does_not_repair_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            {"choices": [{"finish_reason": "stop", "message": {"content": "```json\n{}\n```"}}]}
        ),
    )
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="test-model",
        api_key="secret",
        base_url="https://api.example.test/v1",
        provider="test-provider",
    )

    result = adapter.execute(task)

    assert result.final_output == {}
    assert any(event["event"] == "structured_output_parse_failed" for event in result.trace)


def test_openai_compatible_surfaces_provider_error_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://api.example.test/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"invalid key"}}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="test-model",
        api_key="secret",
        base_url="https://api.example.test/v1",
        provider="test-provider",
    )

    with pytest.raises(AdapterError, match="HTTP 401"):
        adapter.execute(task)


def test_cli_provider_presets_require_named_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        _build_adapter(
            "groq",
            "openai/gpt-oss-120b",
            "",
            30,
            seed=1,
            temperature=0.0,
            max_tokens=128,
        )


def test_openai_compatible_retries_rate_limits_with_auditable_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def fake_urlopen(*_args: object, **_kwargs: object) -> _FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                "https://api.example.test/v1/chat/completions",
                429,
                "rate limited",
                {"Retry-After": "0.25"},
                io.BytesIO(b'{"error":{"message":"rate limited"}}'),
            )
        return _FakeResponse(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {},
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("medphys_agentbench.adapters.openai_compatible.time.sleep", sleeps.append)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="test-model",
        api_key="secret",
        base_url="https://api.example.test/v1",
        provider="test-provider",
    )

    result = adapter.execute(task)

    assert calls == 2
    assert sleeps == [0.25]
    assert result.trace[0] == {
        "event": "provider_rate_limit_retry",
        "provider": "test-provider",
        "retry_index": 1,
        "delay_seconds": 0.25,
    }


def test_openai_compatible_classifies_unsupported_required_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "medphys_agentbench.adapters.openai_compatible.openai_message_content",
        lambda *_args: [{"type": "text", "text": "task"}, {"type": "image_url", "image_url": {}}],
    )

    def reject_artifact(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://api.example.test/v1/chat/completions",
            400,
            "bad request",
            {},
            io.BytesIO(
                b'{"error":{"message":"messages[1].content must be a string",'
                b'"param":"messages[1].content"}}'
            ),
        )

    monkeypatch.setattr(urllib.request, "urlopen", reject_artifact)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="text-only-model",
        api_key="secret",
        base_url="https://api.example.test/v1",
        provider="test-provider",
    )

    with pytest.raises(UnsupportedCapabilityError, match="required artifact modality"):
        adapter.execute(task)


def test_openai_compatible_classifies_provider_json_generation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"x-request-id": "req-json-failed"}
    body = b'{"error":{"code":"json_validate_failed","failed_generation":"secret-output"}}'

    def reject_json(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://api.example.test/v1/chat/completions",
            400,
            "bad request",
            headers,
            io.BytesIO(body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", reject_json)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OpenAICompatibleAdapter(
        model_name="json-failing-model",
        api_key="secret",
        base_url="https://api.example.test/v1",
        provider="test-provider",
    )

    with pytest.raises(ProviderOutputContractError, match="JSON output contract") as captured:
        adapter.execute(task)

    error = captured.value
    assert error.duration_seconds is not None and error.duration_seconds > 0
    assert error.raw_response == {
        "provider": "test-provider",
        "model": "json-failing-model",
        "http_status": 400,
        "error_code": "json_validate_failed",
        "error_body_sha256": hashlib.sha256(body).hexdigest(),
        "latency_ms": pytest.approx(error.duration_seconds * 1000),
        "provider_request_id": "req-json-failed",
        "content_redacted": True,
    }
    assert "secret-output" not in json.dumps(error.raw_response)
    assert any(event["event"] == "provider_output_contract_response" for event in error.trace)
