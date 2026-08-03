"""Adapter for grading outputs produced on an explicitly non-API pilot surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import ModelDescriptor, RuntimeTask
from .base import AgentResult


@dataclass
class RecordedOutputAdapter:
    outputs: dict[str, dict[str, Any]]
    model_name: str
    model_revision: str
    reasoning_effort: str
    capture_metadata: dict[str, Any] | None = None
    capture_schema_version: str = "medphysbench.recorded-batch.v1"

    provider = "codex-native"
    sandbox_image_digest = "unisolated-codex-native-conversation-surface"

    @property
    def harness_revision(self) -> str:
        if self.capture_schema_version == "medphysbench.recorded-batch.v2":
            return "codex-native-pilot-v2"
        return "codex-native-pilot-v1"

    @property
    def tool_environment_version(self) -> str:
        if self.capture_metadata is None:
            return "sealed-batch-no-tools-requested-v1"
        return "sealed-batch-recorded-capture-v2"

    @property
    def name(self) -> str:
        return f"{self.provider}/{self.model_name}/{self.reasoning_effort}"

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider=self.provider,
            model_name=f"{self.model_name} [effort={self.reasoning_effort}]",
            model_revision=self.model_revision,
            harness_name="medphysbench-recorded-output",
            harness_revision=f"{self.harness_revision};effort={self.reasoning_effort}",
        )

    def runtime_settings(self) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "recorded_output_import",
            "reasoning_effort": self.reasoning_effort,
            "live_provider_request": False,
            "tool_access": False,
        }
        if self.capture_metadata is not None:
            settings.update(
                {
                    "capture_schema_version": self.capture_schema_version,
                    "session_isolation": self.capture_metadata["session_isolation"],
                    "task_delivery_mode": self.capture_metadata["task_delivery_mode"],
                    "response_capture": self.capture_metadata["response_capture"],
                    "transport_tools": list(self.capture_metadata["tools_used"]),
                }
            )
        return settings

    def execute(self, task: RuntimeTask) -> AgentResult:
        output = self.outputs.get(task.task_id)
        if not isinstance(output, dict):
            raise KeyError(f"Recorded batch is missing an object output for {task.task_id}.")
        trace_event: dict[str, Any] = {
            "event": "recorded_output_import",
            "surface": "codex-native",
            "reasoning_effort": self.reasoning_effort,
            "comparable_to_api_runs": False,
        }
        raw_response: dict[str, Any] = {
            "surface": "codex-native",
            "reasoning_effort": self.reasoning_effort,
            "hidden_reasoning_stored": False,
        }
        if self.capture_metadata is not None:
            trace_event.update(
                {
                    "capture_id": self.capture_metadata["capture_id"],
                    "capture_started_at": self.capture_metadata["started_at"],
                    "capture_finished_at": self.capture_metadata["finished_at"],
                    "session_isolation": self.capture_metadata["session_isolation"],
                    "task_delivery_mode": self.capture_metadata["task_delivery_mode"],
                    "transport_tools": list(self.capture_metadata["tools_used"]),
                }
            )
            raw_response.update(
                {
                    "capture_schema_version": self.capture_schema_version,
                    "capture_id": self.capture_metadata["capture_id"],
                }
            )
        return AgentResult(
            final_output=output,
            trace=[trace_event],
            raw_response=raw_response,
        )
