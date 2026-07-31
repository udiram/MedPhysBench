from medphys_agentbench.scoring import grade_unordered_list_exact_match


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
