"""Ollama adapter for local and Ollama Cloud models."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import ollama_image_payloads
from ..contracts import ModelDescriptor, RuntimeTask
from ..json_utils import StrictJsonError, decode_strict_json_object
from ..prompting import SYSTEM_PROMPT, build_user_prompt
from .base import AgentResult


class AdapterError(RuntimeError):
    """A provider or response-contract failure."""


@dataclass
class OllamaAdapter:
    model_name: str
    base_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.0
    seed: int = 20260731
    max_tokens: int = 1024
    timeout_seconds: int = 300
    artifact_root: Path = Path.cwd()

    provider = "ollama"
    harness_revision = "reference-json-v1"

    @property
    def name(self) -> str:
        return f"ollama/{self.model_name}"

    @property
    def model_revision(self) -> str:
        return self.model_name

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider=self.provider,
            model_name=self.model_name,
            model_revision=self.model_revision,
            harness_name="medphysbench-ollama",
            harness_revision=self.harness_revision,
        )

    def execute(self, task: RuntimeTask) -> AgentResult:
        started = time.perf_counter()
        user_message: dict[str, Any] = {"role": "user", "content": build_user_prompt(task)}
        images = ollama_image_payloads(task.context_artifacts, self.artifact_root)
        if images:
            user_message["images"] = images
        request_payload = {
            "model": self.model_name,
            "stream": False,
            "think": False,
            "format": task.expected_output_schema,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                user_message,
            ],
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": self.max_tokens,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise AdapterError(f"Ollama request failed for {self.model_name}: {error}") from error

        content = str(raw.get("message", {}).get("content", ""))
        output, parse_trace = _parse_json_object(content)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        usage = {
            key: raw.get(key)
            for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
            if raw.get(key) is not None
        }
        return AgentResult(
            final_output=output,
            trace=[
                {
                    "event": "model_response",
                    "provider": self.provider,
                    "model": self.model_name,
                    "latency_ms": latency_ms,
                    "usage": usage,
                },
                *parse_trace,
            ],
            raw_response={
                "provider": self.provider,
                "model": self.model_name,
                "content": content,
                "done_reason": raw.get("done_reason"),
                "usage": usage,
                "latency_ms": latency_ms,
                "thinking": raw.get("message", {}).get("thinking"),
            },
        )


def _parse_json_object(content: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse one exact JSON object without repair or duplicate-key ambiguity."""
    candidate = content.strip()
    try:
        parsed = decode_strict_json_object(candidate)
    except StrictJsonError as error:
        return {}, [
            {
                "event": "structured_output_parse_failed",
                "reason": str(error),
                "raw_preview": candidate[:400],
            }
        ]
    return parsed, []
