from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from medphys_agentbench.adapters.ollama import AdapterError
from medphys_agentbench.adapters.openai_compatible import OpenAICompatibleAdapter
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
