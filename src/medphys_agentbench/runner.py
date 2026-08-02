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
from .scoring import Grade, grades_pass, grades_safe, score_attempt, weighted_grade_score

SCORING_REVISION = "deterministic-v2-safety-lanes"


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
        return grades_pass(self.grades)

    @property
    def safe(self) -> bool:
        return grades_safe(self.grades)

    @property
    def score(self) -> float:
        return weighted_grade_score(self.grades)

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
    manifest = create_run_manifest(
        task,
        agent,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        run_id=run_id,
    )
    result = agent.execute(runtime_task)
    return TrialResult(
        manifest=manifest,
        output=result.final_output,
        grades=tuple(score_attempt(task, result.final_output)),
        trace=tuple(result.trace),
        raw_response=result.raw_response,
        duration_seconds=round(monotonic() - started, 6),
    )


def adapter_runtime_settings(agent: AgentAdapter) -> dict[str, Any]:
    """Return the public, secret-free settings that define an adapter execution."""
    settings_method = getattr(agent, "runtime_settings", None)
    if callable(settings_method):
        settings = settings_method()
    else:
        settings = {
            "schema_version": "medphysbench.adapter-settings.v1",
            "endpoint_kind": "undeclared_test_adapter",
            "adapter_class": type(agent).__name__,
        }
    if not isinstance(settings, dict):
        raise TypeError("Agent runtime_settings() must return a JSON object.")
    stable_hash(settings)
    forbidden = _credential_like_setting_paths(settings)
    if forbidden:
        raise ValueError(f"Adapter runtime settings contain forbidden credential-like keys: {forbidden}")
    return settings


def _credential_like_setting_paths(value: Any, path: str = "adapter_settings") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            lowered = str(key).lower()
            if any(token in lowered for token in ("secret", "api_key", "apikey", "access_token", "auth_token")):
                found.append(child_path)
            found.extend(_credential_like_setting_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_credential_like_setting_paths(child, f"{path}[{index}]"))
    return sorted(set(found))


def create_run_manifest(
    task: TaskSpec,
    agent: AgentAdapter,
    *,
    seed: int | None,
    temperature: float | None,
    max_tokens: int | None,
    run_id: str | None = None,
) -> RunManifest:
    """Create the immutable v2 manifest before provider execution begins."""
    runtime_task = task.runtime_task()
    settings = adapter_runtime_settings(agent)
    return RunManifest.create(
        run_id=run_id or str(uuid4()),
        task=task,
        model=agent.model_descriptor(),
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        adapter_settings=settings,
        adapter_settings_hash=stable_hash(settings),
        sandbox_image_digest=getattr(
            agent, "sandbox_image_digest", "process-isolation-public-v0.2.0"
        ),
        tool_environment_version=getattr(
            agent, "tool_environment_version", "public-fixtures-v0.2.0"
        ),
        prompt_hash=prompt_hash_for_task(task),
        tool_schema_hash=tool_schema_hash_for_task(task),
        system_prompt_hash=system_prompt_hash(),
        runtime_task_hash=stable_hash(runtime_task.to_dict()),
        grader_hash=grader_hash_for_task(task),
        scoring_revision=SCORING_REVISION,
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


def grader_hash_for_task(task: TaskSpec) -> str:
    return stable_hash(task.grading)
