"""Single-trial orchestration with immutable run provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any
from uuid import uuid4

from .adapters.base import AgentAdapter
from .contracts import RunManifest, TaskSpec
from .json_utils import hash_text, stable_hash
from .prompting import SYSTEM_PROMPT
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
    runtime_task = task.runtime_task()
    result = agent.execute(runtime_task)
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
        prompt_hash=prompt_hash_for_task(task),
        tool_schema_hash=tool_schema_hash_for_task(task),
        system_prompt_hash=system_prompt_hash(),
        runtime_task_hash=stable_hash(runtime_task.to_dict()),
    )
    return TrialResult(
        manifest=manifest,
        output=result.final_output,
        grades=tuple(score_attempt(task, result.final_output)),
        trace=tuple(result.trace),
        raw_response=result.raw_response,
        duration_seconds=round(monotonic() - started, 6),
    )


def prompt_hash_for_task(task: TaskSpec) -> str:
    # v1 artifacts defined prompt_hash as the authored instruction hash. The
    # system prompt and complete runtime payload now have independent hashes,
    # preserving historical comparability without weakening the new manifest.
    return hash_text(task.instructions)


def tool_schema_hash_for_task(task: TaskSpec) -> str:
    return stable_hash([asdict(tool) for tool in task.allowed_tools])


def runtime_task_hash_for_task(task: TaskSpec) -> str:
    return stable_hash(task.runtime_task().to_dict())


def system_prompt_hash() -> str:
    return hash_text(SYSTEM_PROMPT)
