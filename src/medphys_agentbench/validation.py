"""Machine-enforced adversarial checks for authored deterministic graders."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .contracts import TaskSpec
from .scoring import (
    grade_safety_gate,
    grades_pass,
    grades_safe,
    run_declared_graders,
    score_attempt,
    validate_expected_output_shape,
)


def validate_grader_mutations(task: TaskSpec, reference_output: dict[str, Any], path: Path) -> int:
    """Require every deterministic gate to reject a targeted authored near-miss."""
    checked = 0
    required_fields = task.expected_output_schema.get("required", [])
    if isinstance(required_fields, list):
        for field in required_fields:
            mutated = deepcopy(reference_output)
            mutated.pop(str(field), None)
            if validate_expected_output_shape(task, mutated).passed:
                raise ValueError(f"{path}: JSON Schema accepted missing required field {field!r}.")
            checked += 1

    declared = task.grading.get("graders", [])
    if isinstance(declared, list):
        for index, spec in enumerate(declared):
            if not isinstance(spec, dict) or "field" not in spec:
                continue
            mutated = deepcopy(reference_output)
            _apply_targeted_grader_mutation(mutated, spec)
            grades = run_declared_graders(task, mutated)
            grader_id = spec.get("grader_id", f"{spec.get('type', 'unknown')}.{spec['field']}")
            if index >= len(grades) or grades[index].passed:
                raise ValueError(f"{path}: grader {grader_id!r} accepted its targeted mutation.")
            if bool(spec.get("required_for_pass", True)) and grades_pass(score_attempt(task, mutated)):
                raise ValueError(f"{path}: required grader {grader_id!r} did not block the mutated attempt.")
            checked += 1

    legacy_numeric = task.grading.get("numeric_tolerance")
    if isinstance(legacy_numeric, dict) and not declared:
        mutated = deepcopy(reference_output)
        _apply_targeted_grader_mutation(mutated, {"type": "numeric_tolerance", **legacy_numeric})
        if grades_pass(score_attempt(task, mutated)):
            raise ValueError(f"{path}: legacy numeric grader accepted its targeted mutation.")
        checked += 1

    required_escalation = task.safety.get("requires_escalation")
    if isinstance(required_escalation, bool):
        mutated = deepcopy(reference_output)
        mutated["requires_escalation"] = not required_escalation
        safety_grade = grade_safety_gate(task, mutated)
        if safety_grade.passed or grades_safe(score_attempt(task, mutated)):
            raise ValueError(f"{path}: safety escalation gate accepted the opposite decision.")
        checked += 1
    return checked


def _apply_targeted_grader_mutation(output: dict[str, Any], spec: dict[str, Any]) -> None:
    field = str(spec["field"])
    grader_type = str(spec.get("type", ""))
    expected = spec.get("expected")
    if grader_type == "numeric_tolerance":
        expected_number = float(expected)
        tolerance = abs(float(spec.get("absolute_tolerance", 0.0)))
        output[field] = expected_number + tolerance + max(tolerance, 1.0)
    elif grader_type == "unordered_list_exact_match":
        expected_items = list(expected) if isinstance(expected, list) else []
        output[field] = expected_items[:-1] if expected_items else ["__mutation__"]
    elif grader_type == "contains_all_strings":
        expected_items = [str(item) for item in expected] if isinstance(expected, list) else []
        output[field] = " ".join(expected_items[1:]) if expected_items else "__mutation__"
    elif grader_type == "bounding_box_iou":
        output[field] = []
    elif grader_type == "grid_mask_dice":
        expected_cells = expected if isinstance(expected, list) else []
        output[field] = [] if expected_cells else [[-1, -1]]
    else:
        output[field] = _different_value(expected)


def _different_value(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return f"{value}__mutation__"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value + 1
    if isinstance(value, list):
        return value[:-1] if value else ["__mutation__"]
    if isinstance(value, dict):
        return {**value, "__mutation__": True}
    return "__mutation__"
