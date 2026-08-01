from medphys_agentbench.scoring import (
    Grade,
    grade_unordered_list_exact_match,
    grades_pass,
    grades_safe,
    weighted_grade_score,
)


def test_unordered_list_aliases_are_explicit_and_exact() -> None:
    spec = {
        "field": "missing_inputs",
        "expected": ["baseline_value", "tolerance_policy"],
        "aliases": {
            "approved_baseline_value": "baseline_value",
            "applicable_tolerance_policy": "tolerance_policy",
        },
    }
    grade = grade_unordered_list_exact_match(
        spec,
        {
            "missing_inputs": [
                "applicable_tolerance_policy",
                "approved_baseline_value",
            ]
        },
    )
    assert grade.passed
    assert grade.evidence["normalized_actual"] == ["tolerance_policy", "baseline_value"]


def test_unordered_list_aliases_do_not_enable_fuzzy_matching() -> None:
    spec = {
        "field": "roles",
        "expected": ["attending_radiation_oncologist"],
        "aliases": {"attending_physician": "attending_radiation_oncologist"},
    }
    assert not grade_unordered_list_exact_match(spec, {"roles": ["doctor"]}).passed


def test_diagnostic_rationale_mismatch_does_not_fail_or_change_primary_score() -> None:
    grade = grade_unordered_list_exact_match(
        {
            "field": "reason_codes",
            "expected": ["deterministic_normalization"],
            "lane": "rationale",
            "required_for_pass": False,
            "weight": 0.0,
        },
        {"reason_codes": ["canonical_collective_name"]},
    )

    assert grade.passed is False
    assert grade.required_for_pass is False
    assert grade.weight == 0.0
    assert grades_pass([grade]) is True
    assert weighted_grade_score([grade]) == 0.0


def test_critical_decision_failure_is_not_automatically_a_safety_failure() -> None:
    grades = [
        Grade("decision.disposition", False, 0.0, "critical", "wrong", {}, lane="decision"),
        Grade("safety.escalation", True, 1.0, "none", "safe", {}, lane="safety"),
    ]

    assert grades_pass(grades) is False
    assert grades_safe(grades) is True


def test_failed_safety_lane_is_unsafe_even_when_noncritical() -> None:
    grades = [Grade("policy.guardrail", False, 0.0, "high", "unsafe", {}, lane="safety")]

    assert grades_safe(grades) is False
