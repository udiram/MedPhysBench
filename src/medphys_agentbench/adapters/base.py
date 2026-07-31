"""Protocols shared by benchmark adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..contracts import ModelDescriptor, RuntimeTask


@dataclass(frozen=True)
class AgentResult:
    final_output: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


class AgentAdapter(Protocol):
    """A model or agent shell evaluated under a declared harness configuration."""

    name: str
    provider: str
    model_name: str
    model_revision: str
    harness_revision: str

    def model_descriptor(self) -> ModelDescriptor:
        """Return the normalized identity captured in run manifests."""

    def execute(self, task: RuntimeTask) -> AgentResult:
        """Execute exactly one isolated trial against a runtime-visible task contract."""
