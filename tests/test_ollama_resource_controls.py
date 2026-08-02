from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from medphys_agentbench.adapters.ollama import AdapterError, OllamaAdapter
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


def test_ollama_defaults_unload_model_and_bound_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> _FakeResponse:
        captured["timeout"] = timeout
        captured["payload"] = json.loads(bytes(request.data or b"").decode("utf-8"))
        return _FakeResponse(
            {
                "message": {
                    "content": (
                        '{"distance_cm":100,"answer_ratio":0.25,'
                        '"requires_escalation":false,"assumptions":[]}'
                    )
                },
                "done_reason": "stop",
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()
    adapter = OllamaAdapter(model_name="fixture-model", timeout_seconds=29)

    result = adapter.execute(task)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert captured["timeout"] == 29
    assert payload["keep_alive"] == 0
    assert payload["options"]["num_ctx"] == 4096
    assert payload["options"]["num_predict"] == 1024
    assert result.final_output["answer_ratio"] == 0.25


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@example.test/v1",
        "https://example.test/v1?api_key=secret",
        "https://example.test/v1#credential",
    ],
)
def test_ollama_runtime_manifest_rejects_credential_bearing_base_urls(base_url: str) -> None:
    adapter = OllamaAdapter(model_name="fixture-model", base_url=base_url)
    with pytest.raises(ValueError, match="must not contain"):
        adapter.runtime_settings()


def test_ollama_surfaces_overload_without_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fail(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            "http://127.0.0.1:11434/api/chat",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":"server busy"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml").runtime_task()

    with pytest.raises(AdapterError, match="HTTP Error 429"):
        OllamaAdapter(model_name="fixture-model").execute(task)
    assert calls == 1
