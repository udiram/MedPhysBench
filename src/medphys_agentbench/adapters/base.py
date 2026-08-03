"""Protocols shared by benchmark adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from ..contracts import ModelDescriptor, RuntimeTask


class AdapterError(RuntimeError):
    """A provider transport or response failure."""


class UnsupportedCapabilityError(AdapterError):
    """A declared model cannot consume a task's required input modality."""


class ProviderOutputContractError(AdapterError):
    """The model/provider failed to produce the declared structured output."""

    def __init__(
        self,
        message: str,
        *,
        trace: list[dict[str, Any]] | None = None,
        raw_response: dict[str, Any] | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.trace = list(trace or [])
        self.raw_response = dict(raw_response or {})
        self.duration_seconds = duration_seconds


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

    def runtime_settings(self) -> dict[str, Any]:
        """Return the non-secret execution settings that define this system row."""

    def execute(self, task: RuntimeTask) -> AgentResult:
        """Execute exactly one isolated trial against a runtime-visible task contract."""


def public_endpoint_url(value: str) -> str:
    """Normalize a credential-free HTTP endpoint for a public run manifest."""
    parsed = urlsplit(value.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Adapter base URL must be an absolute HTTP(S) URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Adapter base URL must not contain user-info credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("Adapter base URL must not contain query parameters or a fragment.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
