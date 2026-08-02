"""A test-only oracle. It must never be used to score a real hidden task set."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ModelDescriptor, RuntimeTask
from .base import AgentResult


@dataclass(frozen=True)
class DevelopmentReferenceAgent:
    """Test-only oracle that receives its output out-of-band from the task runtime view."""

    name = "development-reference-agent"
    provider = "development"
    model_name = "development-reference-agent"
    model_revision = "fixture"
    harness_revision = "0.2.0"
    output: dict[str, object]

    def model_descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(
            provider="development",
            model_name=self.name,
            model_revision="scaffold",
            harness_name="reference-harness",
            harness_revision="0.2.0",
        )

    def runtime_settings(self) -> dict[str, object]:
        return {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "development_reference",
            "development_only": True,
        }

    def execute(self, task: RuntimeTask) -> AgentResult:
        return AgentResult(
            final_output=self.output,
            trace=[
                {
                    "event": "reference_output_loaded",
                    "warning": (
                        "Development-only oracle; output was injected by the test harness "
                        "and never read from the runtime task."
                    ),
                }
            ],
            raw_response={"development_reference": True},
        )
