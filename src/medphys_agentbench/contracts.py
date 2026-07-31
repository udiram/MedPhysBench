"""Versioned, dependency-light contracts for task packs and evaluation attempts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ContractError(ValueError):
    """Raised when a task pack violates the public benchmark contract."""


class RiskTier(StrEnum):
    LOW = "tier_1_low"
    MEDIUM = "tier_2_shadow"
    HIGH = "tier_3_escalation_only"


class AccessClass(StrEnum):
    PUBLIC = "public"
    GATED = "gated"
    RESTRICTED = "restricted"
    PRIVATE = "private"


@dataclass(frozen=True)
class RuntimeTask:
    """The only task representation a candidate agent is allowed to receive.

    Gold answers, grader configuration, author identity, and sensitive provenance
    are deliberately absent. The production service should serialize this object
    into the sandbox rather than mounting the authored task pack.
    """

    schema_version: str
    task_id: str
    version: str
    title: str
    domain: str
    track: str
    risk_tier: RiskTier
    instructions: str
    input_payload: dict[str, Any]
    context_artifacts: tuple[ContextArtifact, ...]
    allowed_tools: tuple[ToolSpec, ...]
    expected_output_schema: dict[str, Any]
    safety: dict[str, Any]
    stop_conditions: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["risk_tier"] = self.risk_tier.value
        return payload


@dataclass(frozen=True)
class ContextArtifact:
    artifact_id: str
    media_type: str
    content: str
    description: str = ""
    title: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextArtifact:
        _require(data, "artifact_id", "context_artifact")
        _require(data, "media_type", "context_artifact")
        _require(data, "content", "context_artifact")
        return cls(
            artifact_id=str(data["artifact_id"]),
            media_type=str(data["media_type"]),
            content=str(data["content"]),
            description=str(data.get("description", "")),
            title=_optional_str(data.get("title")),
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    mode: str
    description: str
    fixture_ref: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolSpec:
        _require(data, "name", "allowed_tools item")
        _require(data, "mode", "allowed_tools item")
        return cls(
            name=str(data["name"]),
            mode=str(data["mode"]),
            description=str(data.get("description", "")),
            fixture_ref=_optional_str(data.get("fixture_ref")),
        )


@dataclass(frozen=True)
class TaskSpec:
    schema_version: str
    task_id: str
    version: str
    title: str
    domain: str
    track: str
    risk_tier: RiskTier
    access_class: AccessClass
    instructions: str
    input_payload: dict[str, Any]
    context_artifacts: tuple[ContextArtifact, ...]
    allowed_tools: tuple[ToolSpec, ...]
    expected_output_schema: dict[str, Any]
    grading: dict[str, Any]
    safety: dict[str, Any]
    provenance: dict[str, Any]
    stop_conditions: dict[str, Any] = field(default_factory=dict)
    contamination_tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskSpec:
        required = (
            "schema_version",
            "task_id",
            "version",
            "title",
            "domain",
            "track",
            "risk_tier",
            "access_class",
            "instructions",
            "input_payload",
            "expected_output_schema",
            "grading",
            "safety",
            "provenance",
        )
        for key in required:
            _require(data, key, "task")

        if data["schema_version"] != "medeval.task.v1":
            raise ContractError(
                f"Unsupported schema_version {data['schema_version']!r}; expected 'medeval.task.v1'."
            )
        if not str(data["task_id"]).strip():
            raise ContractError("task.task_id must be non-empty.")
        if not isinstance(data["input_payload"], dict):
            raise ContractError("task.input_payload must be an object.")
        if not isinstance(data["expected_output_schema"], dict):
            raise ContractError("task.expected_output_schema must be an object.")
        if not isinstance(data["grading"], dict):
            raise ContractError("task.grading must be an object.")
        if not isinstance(data["safety"], dict):
            raise ContractError("task.safety must be an object.")
        if not isinstance(data["provenance"], dict):
            raise ContractError("task.provenance must be an object.")

        raw_tools = data.get("allowed_tools", [])
        if not isinstance(raw_tools, list):
            raise ContractError("task.allowed_tools must be a list.")
        raw_artifacts = data.get("context_artifacts", [])
        if not isinstance(raw_artifacts, list):
            raise ContractError("task.context_artifacts must be a list.")
        raw_tags = data.get("contamination_tags", [])
        if not isinstance(raw_tags, list):
            raise ContractError("task.contamination_tags must be a list.")

        try:
            risk_tier = RiskTier(data["risk_tier"])
            access_class = AccessClass(data["access_class"])
        except ValueError as error:
            raise ContractError(str(error)) from error

        return cls(
            schema_version=str(data["schema_version"]),
            task_id=str(data["task_id"]),
            version=str(data["version"]),
            title=str(data["title"]),
            domain=str(data["domain"]),
            track=str(data["track"]),
            risk_tier=risk_tier,
            access_class=access_class,
            instructions=str(data["instructions"]),
            input_payload=data["input_payload"],
            context_artifacts=tuple(ContextArtifact.from_dict(item) for item in raw_artifacts),
            allowed_tools=tuple(ToolSpec.from_dict(item) for item in raw_tools),
            expected_output_schema=data["expected_output_schema"],
            grading=data["grading"],
            safety=data["safety"],
            provenance=data["provenance"],
            stop_conditions=data.get("stop_conditions", {}),
            contamination_tags=tuple(str(tag) for tag in raw_tags),
        )

    def authoring_manifest(self) -> dict[str, Any]:
        """Return the complete authoring view for validation and review only."""
        payload = asdict(self)
        payload["risk_tier"] = self.risk_tier.value
        payload["access_class"] = self.access_class.value
        return payload

    def runtime_task(self) -> RuntimeTask:
        """Build the sealed, runtime-visible view of an authored task.

        This separation is an integrity control, not merely a convenience API.
        In particular, `grading` must never cross the agent/sandbox boundary.
        """
        return RuntimeTask(
            schema_version=self.schema_version,
            task_id=self.task_id,
            version=self.version,
            title=self.title,
            domain=self.domain,
            track=self.track,
            risk_tier=self.risk_tier,
            instructions=self.instructions,
            input_payload=self.input_payload,
            context_artifacts=self.context_artifacts,
            allowed_tools=self.allowed_tools,
            expected_output_schema=self.expected_output_schema,
            safety=self.safety,
            stop_conditions=self.stop_conditions,
        )


@dataclass(frozen=True)
class ModelDescriptor:
    provider: str
    model_name: str
    model_revision: str
    harness_name: str
    harness_revision: str


@dataclass(frozen=True)
class RunManifest:
    schema_version: str
    run_id: str
    task_id: str
    task_version: str
    model: ModelDescriptor
    seed: int | None
    temperature: float | None
    max_tokens: int | None
    sandbox_image_digest: str
    tool_environment_version: str
    created_at: str
    prompt_hash: str
    tool_schema_hash: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        task: TaskSpec,
        model: ModelDescriptor,
        seed: int | None,
        temperature: float | None,
        max_tokens: int | None,
        sandbox_image_digest: str,
        tool_environment_version: str,
        prompt_hash: str,
        tool_schema_hash: str,
    ) -> RunManifest:
        return cls(
            schema_version="medeval.run.v1",
            run_id=run_id,
            task_id=task.task_id,
            task_version=task.version,
            model=model,
            seed=seed,
            temperature=temperature,
            max_tokens=max_tokens,
            sandbox_image_digest=sandbox_image_digest,
            tool_environment_version=tool_environment_version,
            created_at=datetime.now(UTC).isoformat(),
            prompt_hash=prompt_hash,
            tool_schema_hash=tool_schema_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require(data: dict[str, Any], key: str, context: str) -> None:
    if key not in data:
        raise ContractError(f"{context} is missing required field {key!r}.")


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
