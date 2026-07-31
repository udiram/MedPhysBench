"""Single-trial orchestration with immutable run provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from time import monotonic
from typing import Any
from uuid import uuid4

from .adapters.base import AgentAdapter
from .contracts import RunManifest, TaskSpec
from .scoring import Grade, score_attempt


@dataclass(frozen=True)
class TrialResult:
    manifest: RunManifest
    output: dict[str, Any]
    grades: tuple[Grade, ...]
    trace: tuple[dict[str, Any], ...]
    raw_response: dict[str, Any]
    duration_seconds: float

    @property
    def passed(self) -> bool:
        return all(grade.passed for grade in self.grades)

    @property
    def safe(self) -> bool:
        return not any(
            (not grade.passed) and grade.severity == "critical" for grade in self.grades
        )

    @property
    def score(self) -> float:
        scored = [grade.score for grade in self.grades if not grade.grader_id.startswith("schema.")]
        return sum(scored) / len(scored) if scored else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "output": self.output,
            "grades": [grade.to_dict() for grade in self.grades],
            "trace": list(self.trace),
            "raw_response": self.raw_response,
            "duration_seconds": self.duration_seconds,
            "passed": self.passed,
            "safe": self.safe,
            "score": self.score,
        }


def run_trial(
    task: TaskSpec,
    agent: AgentAdapter,
    *,
    seed: int | None = 0,
    temperature: float | None = 0.0,
    max_tokens: int | None = 0,
    run_id: str | None = None,
) -> TrialResult:
    """Run exactly one trial against the sealed runtime task view."""
    started = monotonic()
    result = agent.execute(task.runtime_task())
    model = agent.model_descriptor()
    manifest = RunManifest.create(
        run_id=run_id or str(uuid4()),
        task=task,
        model=model,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        sandbox_image_digest="process-isolation-public-v0.2.0",
        tool_environment_version="public-fixtures-v0.2.0",
        prompt_hash=_hash_text(task.instructions),
        tool_schema_hash=_hash_text(str([asdict(tool) for tool in task.allowed_tools])),
    )
    return TrialResult(
        manifest=manifest,
        output=result.final_output,
        grades=tuple(score_attempt(task, result.final_output)),
        trace=tuple(result.trace),
        raw_response=result.raw_response,
        duration_seconds=round(monotonic() - started, 6),
    )


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
