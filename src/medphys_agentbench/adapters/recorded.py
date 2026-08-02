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

    provider = "codex-native"
    harness_revision = "codex-native-pilot-v1"
    sandbox_image_digest = "unisolated-codex-native-conversation-surface"
    tool_environment_version = "sealed-batch-no-tools-requested-v1"

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
        return {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "recorded_output_import",
            "reasoning_effort": self.reasoning_effort,
            "live_provider_request": False,
            "tool_access": False,
        }

    def execute(self, task: RuntimeTask) -> AgentResult:
        output = self.outputs.get(task.task_id)
        if not isinstance(output, dict):
            raise KeyError(f"Recorded batch is missing an object output for {task.task_id}.")
        return AgentResult(
            final_output=output,
            trace=[
                {
                    "event": "recorded_output_import",
                    "surface": "codex-native",
                    "reasoning_effort": self.reasoning_effort,
                    "comparable_to_api_runs": False,
                }
            ],
            raw_response={
                "surface": "codex-native",
                "reasoning_effort": self.reasoning_effort,
                "hidden_reasoning_stored": False,
            },
        )
