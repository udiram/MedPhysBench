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
from .base import AdapterError, AgentResult, UnsupportedCapabilityError, public_endpoint_url


@dataclass
class OllamaAdapter:
    model_name: str
    base_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.0
    seed: int = 20260731
    max_tokens: int = 1024
    timeout_seconds: int = 300
    artifact_root: Path = Path.cwd()
    keep_alive: str | int | None = 0
    context_window: int = 4096
    model_revision_override: str | None = None

    provider = "ollama"
    harness_revision = "reference-json-v2"

    @property
    def name(self) -> str:
        return f"ollama/{self.model_name}"

    @property
    def model_revision(self) -> str:
        return self.model_revision_override or self.model_name

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider=self.provider,
            model_name=self.model_name,
            model_revision=self.model_revision,
            harness_name="medphysbench-ollama",
            harness_revision=self.harness_revision,
        )

    def runtime_settings(self) -> dict[str, Any]:
        return {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "ollama_chat",
            "base_url": public_endpoint_url(self.base_url),
            "timeout_seconds": self.timeout_seconds,
            "structured_output_mode": "json_schema",
            "think": False,
            "context_window": self.context_window,
            "keep_alive": self.keep_alive,
            "artifact_transport": "ollama_images",
            "required_modality_preflight": "ollama_show_then_response_v1",
            "model_identity_resolution": (
                "ollama_tags_digest_v1" if self.model_revision_override else "mutable_model_tag"
            ),
        }

    def execute(self, task: RuntimeTask) -> AgentResult:
        started = time.perf_counter()
        user_message: dict[str, Any] = {"role": "user", "content": build_user_prompt(task)}
        images = ollama_image_payloads(task.context_artifacts, self.artifact_root)
        if images:
            capabilities = self._declared_capabilities()
            if capabilities is not None and "vision" not in capabilities:
                declared = ", ".join(capabilities) or "none"
                raise UnsupportedCapabilityError(
                    f"Ollama model {self.model_name} cannot consume this task's required "
                    f"image modality; /api/show declared capabilities: {declared}."
                )
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
                "num_ctx": self.context_window,
            },
        }
        if self.keep_alive is not None:
            request_payload["keep_alive"] = self.keep_alive
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:1000]
            if images and _is_unsupported_image_response(error.code, body):
                raise UnsupportedCapabilityError(
                    f"Ollama model {self.model_name} cannot consume this task's required image modality."
                ) from error
            raise AdapterError(
                f"Ollama HTTP {error.code} for model {self.model_name}: {body}"
            ) from error
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

    def _declared_capabilities(self) -> tuple[str, ...] | None:
        """Read Ollama's model metadata without loading the model into memory."""
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/show",
            data=json.dumps({"model": self.model_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout_seconds, 30)) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        capabilities = raw.get("capabilities")
        if not isinstance(capabilities, list) or not all(
            isinstance(value, str) for value in capabilities
        ):
            return None
        return tuple(sorted(set(capabilities)))


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


def _is_unsupported_image_response(status_code: int, body: str) -> bool:
    if status_code not in {400, 422, 500}:
        return False
    normalized = body.lower()
    return any(
        marker in normalized
        for marker in (
            "does not support images",
            "doesn't support images",
            "image input is not supported",
            "image inputs are not supported",
            "vision is not supported",
        )
    )


def resolve_ollama_model_revision(
    model_name: str,
    *,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: int = 30,
) -> str:
    """Resolve a mutable Ollama tag to the immutable local artifact digest."""
    endpoint = public_endpoint_url(base_url)
    request = urllib.request.Request(f"{endpoint}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=min(timeout_seconds, 30)) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:1000]
        raise AdapterError(f"Ollama model identity lookup failed with HTTP {error.code}: {body}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise AdapterError(f"Ollama model identity lookup failed: {error}") from error

    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, list):
        raise AdapterError("Ollama /api/tags response did not contain a model list.")
    for item in models:
        if not isinstance(item, dict):
            continue
        if item.get("name") != model_name and item.get("model") != model_name:
            continue
        digest = item.get("digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise AdapterError(f"Ollama model {model_name} did not expose a valid SHA-256 digest.")
        try:
            int(digest, 16)
        except ValueError as error:
            raise AdapterError(
                f"Ollama model {model_name} exposed a non-hexadecimal artifact digest."
            ) from error
        return f"sha256:{digest.lower()}"
    raise AdapterError(f"Ollama model {model_name} was not found in /api/tags.")
