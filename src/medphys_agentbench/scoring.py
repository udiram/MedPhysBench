"""Deterministic grading primitives. LLM and human grading stay separate by design."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from jsonschema import Draft202012Validator

from .contracts import TaskSpec


@dataclass(frozen=True)
class Grade:
    grader_id: str
    passed: bool
    score: float
    severity: str
    rationale: str
    evidence: dict[str, Any]
    lane: str = "outcome"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_expected_output_shape(task: TaskSpec, output: dict[str, Any]) -> Grade:
    try:
        Draft202012Validator.check_schema(task.expected_output_schema)
    except Exception as error:
        return Grade(
            grader_id="schema.json_schema",
            passed=False,
            score=0.0,
            severity="critical",
            rationale="The authored output schema is invalid; the task cannot be scored.",
            evidence={"schema_error": str(error)},
            lane="artifact",
        )
    non_finite_paths = _non_finite_number_paths(output)
    if non_finite_paths:
        return Grade(
            grader_id="schema.json_schema",
            passed=False,
            score=0.0,
            severity="high",
            rationale="Candidate output contains non-finite numeric values, which are not valid JSON.",
            evidence={"non_finite_paths": non_finite_paths[:10]},
            lane="artifact",
        )
    errors = sorted(
        Draft202012Validator(task.expected_output_schema).iter_errors(output),
        key=lambda error: list(error.path),
    )
    if errors:
        return Grade(
            grader_id="schema.json_schema",
            passed=False,
            score=0.0,
            severity="high",
            rationale="Candidate output does not match the declared JSON Schema.",
            evidence={"errors": [error.message for error in errors[:10]]},
            lane="artifact",
        )
    return Grade(
        grader_id="schema.json_schema",
        passed=True,
        score=1.0,
        severity="none",
        rationale="Candidate output matches the declared JSON Schema.",
        evidence={},
        lane="artifact",
    )


def grade_numeric_tolerance(task: TaskSpec, output: dict[str, Any]) -> Grade:
    spec = task.grading.get("numeric_tolerance")
    if not isinstance(spec, dict):
        return Grade(
            grader_id="numeric_tolerance",
            passed=True,
            score=1.0,
            severity="none",
            rationale="No numeric tolerance grader was declared for this task.",
            evidence={},
            lane="outcome",
        )

    field = str(spec.get("field", "answer"))
    raw_actual = output.get(field)
    try:
        if isinstance(raw_actual, bool):
            raise TypeError("booleans are not numeric answers")
        actual = float(raw_actual)
        if not math.isfinite(actual):
            raise ValueError("numeric answer must be finite")
    except (TypeError, ValueError):
        return Grade(
            grader_id="numeric_tolerance",
            passed=False,
            score=0.0,
            severity=str(spec.get("severity", "high")),
            rationale=f"Candidate output field {field!r} is missing or not numeric.",
            evidence={"field": field},
            lane=str(spec.get("lane", "outcome")),
        )

    expected = float(spec["expected"])
    tolerance = float(spec["absolute_tolerance"])
    if not math.isfinite(expected) or not math.isfinite(tolerance) or tolerance < 0:
        return Grade(
            grader_id="numeric_tolerance",
            passed=False,
            score=0.0,
            severity="critical",
            rationale="The authored numeric grader is invalid; the task cannot be scored.",
            evidence={"expected": expected, "absolute_tolerance": tolerance},
            lane=str(spec.get("lane", "outcome")),
        )
    error = abs(actual - expected)
    passed = error <= tolerance
    return Grade(
        grader_id="numeric_tolerance",
        passed=passed,
        score=1.0 if passed else 0.0,
        severity=str(spec.get("severity", "high")),
        rationale=(
            f"Absolute error {error:g} is within tolerance {tolerance:g}."
            if passed
            else f"Absolute error {error:g} exceeds tolerance {tolerance:g}."
        ),
        evidence={"field": field, "actual": actual, "expected": expected, "absolute_error": error},
        lane=str(spec.get("lane", "outcome")),
    )


def grade_exact_match(spec: dict[str, Any], output: dict[str, Any]) -> Grade:
    field = str(spec["field"])
    expected = spec["expected"]
    actual = output.get(field)
    passed = actual == expected
    return Grade(
        grader_id=str(spec.get("grader_id", f"exact_match.{field}")),
        passed=passed,
        score=1.0 if passed else 0.0,
        severity=str(spec.get("severity", "high" if not passed else "none")),
        rationale=(
            f"Candidate field {field!r} matched the expected value."
            if passed
            else f"Candidate field {field!r} did not match the expected value."
        ),
        evidence={"field": field, "actual": actual, "expected": expected},
        lane=str(spec.get("lane", "outcome")),
    )


def grade_unordered_list_exact_match(spec: dict[str, Any], output: dict[str, Any]) -> Grade:
    field = str(spec["field"])
    actual_raw = output.get(field, [])
    if not isinstance(actual_raw, list):
        return Grade(
            grader_id=str(spec.get("grader_id", f"unordered_list_exact_match.{field}")),
            passed=False,
            score=0.0,
            severity=str(spec.get("severity", "high")),
            rationale=f"Candidate field {field!r} is not a list.",
            evidence={"field": field, "actual": actual_raw},
            lane=str(spec.get("lane", "outcome")),
        )
    expected = [str(item) for item in spec["expected"]]
    actual = [str(item) for item in actual_raw]
    passed = sorted(actual) == sorted(expected)
    return Grade(
        grader_id=str(spec.get("grader_id", f"unordered_list_exact_match.{field}")),
        passed=passed,
        score=1.0 if passed else 0.0,
        severity=str(spec.get("severity", "high" if not passed else "none")),
        rationale=(
            f"Candidate field {field!r} matched the expected set."
            if passed
            else f"Candidate field {field!r} did not match the expected set."
        ),
        evidence={"field": field, "actual": actual, "expected": expected},
        lane=str(spec.get("lane", "outcome")),
    )


def grade_contains_all_strings(spec: dict[str, Any], output: dict[str, Any]) -> Grade:
    field = str(spec["field"])
    actual = str(output.get(field, ""))
    expected = [str(item) for item in spec["expected"]]
    missing = [item for item in expected if item not in actual]
    passed = not missing
    return Grade(
        grader_id=str(spec.get("grader_id", f"contains_all_strings.{field}")),
        passed=passed,
        score=1.0 if passed else 0.0,
        severity=str(spec.get("severity", "medium" if not passed else "none")),
        rationale=(
            f"Candidate field {field!r} contains every required string."
            if passed
            else f"Candidate field {field!r} omitted required strings."
        ),
        evidence={"field": field, "missing": missing, "expected": expected},
        lane=str(spec.get("lane", "outcome")),
    )


def grade_safety_gate(task: TaskSpec, output: dict[str, Any]) -> Grade:
    safety = task.safety
    required_escalation = safety.get("requires_escalation")
    if required_escalation is None:
        return Grade(
            grader_id="safety.escalation",
            passed=True,
            score=1.0,
            severity="none",
            rationale="No explicit escalation gate was declared for this task.",
            evidence={},
            lane="safety",
        )

    actual = output.get("requires_escalation")
    passed = actual is required_escalation
    return Grade(
        grader_id="safety.escalation",
        passed=passed,
        score=1.0 if passed else 0.0,
        severity="critical" if not passed else "none",
        rationale=(
            "Candidate correctly satisfied the escalation contract."
            if passed
            else "Candidate violated the escalation contract."
        ),
        evidence={"expected": required_escalation, "actual": actual},
        lane="safety",
    )


def run_declared_graders(task: TaskSpec, output: dict[str, Any]) -> list[Grade]:
    declared = task.grading.get("graders", [])
    if not isinstance(declared, list):
        return []

    grades: list[Grade] = []
    for spec in declared:
        if not isinstance(spec, dict):
            continue
        grader_type = str(spec.get("type", ""))
        if grader_type == "numeric_tolerance":
            nested_task = TaskSpec(
                **{
                    **task.__dict__,
                    "grading": {"numeric_tolerance": spec},
                }
            )
            grades.append(grade_numeric_tolerance(nested_task, output))
        elif grader_type == "exact_match":
            grades.append(grade_exact_match(spec, output))
        elif grader_type == "unordered_list_exact_match":
            grades.append(grade_unordered_list_exact_match(spec, output))
        elif grader_type == "contains_all_strings":
            grades.append(grade_contains_all_strings(spec, output))
        else:
            grades.append(
                Grade(
                    grader_id=str(spec.get("grader_id", f"unsupported.{grader_type or 'unknown'}")),
                    passed=False,
                    score=0.0,
                    severity="high",
                    rationale=f"Unsupported grader type {grader_type!r}.",
                    evidence={"grader_spec": spec},
                    lane=str(spec.get("lane", "outcome")),
                )
            )
    return grades


def score_attempt(task: TaskSpec, output: dict[str, Any]) -> list[Grade]:
    """Run deterministic gates first. Future graders append rather than replace these."""
    grades = [validate_expected_output_shape(task, output), grade_safety_gate(task, output)]
    declared = run_declared_graders(task, output)
    if declared:
        return grades + declared
    return grades + [grade_numeric_tolerance(task, output)]


def _non_finite_number_paths(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        paths.append(path)
    elif isinstance(value, dict):
        for key, child in value.items():
            paths.extend(_non_finite_number_paths(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            paths.extend(_non_finite_number_paths(child, f"{path}[{index}]"))
    return paths
