"""Strict OpenAI-compatible Chat Completions adapter.

The adapter is intentionally provider-neutral so Groq, OpenAI, vLLM, and other
declared compatible endpoints can share one metered harness without sharing
credentials or silently changing output contracts.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import openai_message_content
from ..contracts import ModelDescriptor, RuntimeTask
from ..json_utils import StrictJsonError, decode_strict_json_object
from ..prompting import SYSTEM_PROMPT, build_user_prompt
from .base import AgentResult
from .ollama import AdapterError


class UnsupportedCapabilityError(AdapterError):
    """A declared model cannot consume a task's required input modality."""


class ProviderOutputContractError(AdapterError):
    """The model/provider failed to produce the declared structured output."""


@dataclass
class OpenAICompatibleAdapter:
    model_name: str
    api_key: str
    base_url: str
    provider: str
    temperature: float = 0.0
    seed: int | None = 20260731
    max_tokens: int = 1024
    timeout_seconds: int = 300
    response_format: str = "json_schema"
    strict_schema: bool = True
    reasoning_effort: str | None = None
    artifact_root: Path = Path.cwd()
    model_revision_override: str | None = None
    max_rate_limit_retries: int = 8

    harness_revision = "openai-chat-json-v1"

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("A non-empty API key is required.")
        if self.response_format not in {"json_schema", "json_object"}:
            raise ValueError("response_format must be 'json_schema' or 'json_object'.")
        if not self.provider.strip():
            raise ValueError("provider must be non-empty.")

    @property
    def name(self) -> str:
        return f"{self.provider}/{self.model_name}"

    @property
    def model_revision(self) -> str:
        return self.model_revision_override or self.model_name

    def model_descriptor(self) -> ModelDescriptor:
        mode = "strict" if self.strict_schema and self.response_format == "json_schema" else "best-effort"
        effort = self.reasoning_effort or "provider-default"
        return ModelDescriptor(
            provider=self.provider,
            model_name=self.model_name,
            model_revision=self.model_revision,
            harness_name="medphysbench-openai-compatible",
            harness_revision=f"{self.harness_revision};format={self.response_format};mode={mode};effort={effort}",
        )

    def execute(self, task: RuntimeTask) -> AgentResult:
        started = time.perf_counter()
        user_content = openai_message_content(
            task.context_artifacts,
            self.artifact_root,
            build_user_prompt(task),
        )
        request_payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
            "response_format": self._response_format(task),
        }
        if self.seed is not None:
            request_payload["seed"] = self.seed
        if self.reasoning_effort is not None:
            request_payload["reasoning_effort"] = self.reasoning_effort

        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Keep a conventional product/version prefix for provider edge
                # compatibility while retaining an auditable benchmark label.
                "User-Agent": "api-client/1.0 MedPhysBench/0.6.0",
            },
            method="POST",
        )
        retry_trace: list[dict[str, Any]] = []
        for retry_index in range(self.max_rate_limit_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")[:1000]
                if _is_unsupported_input_modality(error.code, body, user_content):
                    raise UnsupportedCapabilityError(
                        f"{self.provider} model {self.model_name} cannot consume "
                        "this task's required artifact modality."
                    ) from error
                if error.code == 400 and "json_validate_failed" in body.lower():
                    raise ProviderOutputContractError(
                        f"{self.provider} model {self.model_name} failed the declared JSON output contract."
                    ) from error
                if error.code == 429 and retry_index < self.max_rate_limit_retries:
                    delay_seconds = _rate_limit_delay(error, body, retry_index)
                    retry_trace.append(
                        {
                            "event": "provider_rate_limit_retry",
                            "provider": self.provider,
                            "retry_index": retry_index + 1,
                            "delay_seconds": delay_seconds,
                        }
                    )
                    time.sleep(delay_seconds)
                    continue
                raise AdapterError(
                    f"{self.provider} HTTP {error.code} for model {self.model_name}: {body}"
                ) from error
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                raise AdapterError(f"{self.provider} request failed for {self.model_name}: {error}") from error

        choice = _first_choice(raw)
        content = choice.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise AdapterError(f"{self.provider} returned non-text message content for {self.model_name}.")
        try:
            output = decode_strict_json_object(content.strip())
            parse_trace: list[dict[str, Any]] = []
        except StrictJsonError as error:
            output = {}
            parse_trace = [
                {
                    "event": "structured_output_parse_failed",
                    "reason": str(error),
                    "raw_preview": content[:400],
                }
            ]

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        provider_request_id = raw.get("id")
        system_fingerprint = raw.get("system_fingerprint")
        trace = [
            *retry_trace,
            {
                "event": "model_response",
                "provider": self.provider,
                "model": self.model_name,
                "latency_ms": latency_ms,
                "usage": usage,
                "finish_reason": choice.get("finish_reason"),
                "provider_request_id": provider_request_id,
                "system_fingerprint": system_fingerprint,
            },
            *parse_trace,
        ]
        return AgentResult(
            final_output=output,
            trace=trace,
            raw_response={
                "provider": self.provider,
                "model": self.model_name,
                "content": content,
                "finish_reason": choice.get("finish_reason"),
                "usage": usage,
                "latency_ms": latency_ms,
                "provider_request_id": provider_request_id,
                "system_fingerprint": system_fingerprint,
            },
        )

    def _response_format(self, task: RuntimeTask) -> dict[str, Any]:
        if self.response_format == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "medphysbench_output",
                "strict": self.strict_schema,
                "schema": task.expected_output_schema,
            },
        }


def _first_choice(raw: dict[str, Any]) -> dict[str, Any]:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AdapterError("OpenAI-compatible response did not contain a first choice.")
    return choices[0]


def _is_unsupported_input_modality(status_code: int, body: str, user_content: object) -> bool:
    normalized = body.lower()
    return (
        status_code == 400
        and isinstance(user_content, list)
        and "messages[1].content" in normalized
        and "must be a string" in normalized
    )


def _rate_limit_delay(error: urllib.error.HTTPError, body: str, retry_index: int) -> float:
    header_value = error.headers.get("Retry-After") if error.headers else None
    if header_value:
        try:
            return min(max(float(header_value), 0.25), 30.0)
        except ValueError:
            pass
    match = re.search(r"try again in\s+([0-9.]+)s", body, flags=re.IGNORECASE)
    if match:
        return min(max(float(match.group(1)) + 0.25, 0.25), 30.0)
    return min(2.0 ** retry_index, 30.0)
