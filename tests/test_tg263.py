from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from medphys_agentbench.scoring import score_attempt
from medphys_agentbench.task_loader import load_task
from medphys_agentbench.tg263 import (
    StructureAction,
    normalize_structure,
    normalize_structure_set,
    validate_tg263_name,
)


@pytest.mark.parametrize(
    "name",
    [
        "Brainstem",
        "Parotid_L",
        "OpticNrv_PRV03_L",
        "OpticChiasm_PRV3",
        "Lung~_R",
        "Bowel_Bag",
    ],
)
def test_valid_non_target_examples(name: str) -> None:
    assert validate_tg263_name(name).valid


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("Left Parotid", "whitespace_not_allowed"),
        ("OpticNrv_L_PRV03", "prv_must_precede_laterality"),
        ("SpinalCord_PRV5", "single_digit_prv_margin_without_length_constraint"),
        ("BrachialPlex_PRV03", "non_target_name_over_16_characters"),
        ("PTVp1_CT1_7000", "target_name_misclassified"),
    ],
)
def test_invalid_non_target_examples(name: str, reason: str) -> None:
    result = validate_tg263_name(name)
    assert not result.valid
    assert reason in result.errors


@pytest.mark.parametrize("name", ["PTVp1_CT1_7000", "GTVn2_MR1", "PTV_Liver_20Gyx3"])
def test_valid_target_grammar(name: str) -> None:
    assert validate_tg263_name(name, structure_class="target").valid


def test_target_grammar_rejects_spaces_and_bad_prefix() -> None:
    assert not validate_tg263_name("PTV Liver", structure_class="target").valid
    assert not validate_tg263_name("TARGET_Liver", structure_class="target").valid


def test_deterministic_alias_normalization_and_keep() -> None:
    renamed = normalize_structure({"source_name": "left parotid"})
    kept = normalize_structure({"source_name": "Parotid_L"})

    assert renamed.action is StructureAction.RENAME
    assert renamed.canonical_name == "Parotid_L"
    assert kept.action is StructureAction.KEEP
    assert kept.canonical_name == "Parotid_L"


def test_prv_partial_and_custom_tokens_have_fixed_order() -> None:
    prv = normalize_structure({"source_name": "left optic nerve", "is_prv": True, "prv_margin_mm": 3})
    partial = normalize_structure({"source_name": "right lung", "partial": True})
    custom = normalize_structure({"source_name": "lungs", "custom_qualifier": "Ex"})

    assert prv.canonical_name == "OpticNrv_PRV03_L"
    assert partial.canonical_name == "Lung~_R"
    assert custom.canonical_name == "Lungs^Ex"


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        ({"source_name": "parotid"}, "missing_laterality"),
        ({"source_name": "left parotid", "laterality": "R"}, "contradictory_laterality"),
        ({"source_name": "mystery organ"}, "unknown_structure"),
        ({"source_name": "brain stem", "laterality": "L"}, "unexpected_laterality"),
        ({"source_name": "cord", "prv_margin_mm": 5}, "prv_margin_without_prv"),
        ({"source_name": "cord", "is_prv": True, "prv_margin_mm": 100}, "invalid_prv_margin"),
    ],
)
def test_ambiguous_or_invalid_context_escalates(record: dict[str, object], reason: str) -> None:
    decision = normalize_structure(record)
    assert decision.action is StructureAction.ESCALATE
    assert decision.canonical_name is None
    assert reason in decision.reason_codes


def test_ptv_bang_requires_explicit_semantic_confirmation() -> None:
    ambiguous = normalize_structure({"source_name": "PTV!_eval", "structure_class": "target"})
    confirmed = normalize_structure({"source_name": "PTV!_eval", "structure_class": "target", "segmented_volume": True})

    assert ambiguous.action is StructureAction.ESCALATE
    assert "ptv_bang_semantics_unconfirmed" in ambiguous.reason_codes
    assert confirmed.action is StructureAction.KEEP


def test_case_insensitive_collisions_escalate_without_inventing_suffixes() -> None:
    decisions = normalize_structure_set(
        [
            {"roi_number": 1, "source_name": "Brainstem"},
            {"roi_number": 2, "source_name": "brain stem"},
        ]
    )

    assert [decision.canonical_name for decision in decisions] == ["Brainstem", "Brainstem"]
    assert all(decision.action is StructureAction.ESCALATE for decision in decisions)
    assert all("case_insensitive_collision" in decision.reason_codes for decision in decisions)


def test_batch_result_is_order_invariant_when_keyed_by_roi_number() -> None:
    records = [
        {"roi_number": 8, "source_name": "left kidney"},
        {"roi_number": 3, "source_name": "right cochlea"},
    ]
    forward = {item.roi_number: item.canonical_name for item in normalize_structure_set(records)}
    reverse = {item.roi_number: item.canonical_name for item in normalize_structure_set(reversed(records))}
    assert forward == reverse == {8: "Kidney_L", 3: "Cochlea_R"}


def test_laterality_flip_is_a_metamorphic_suffix_flip() -> None:
    left = normalize_structure({"source_name": "parotid", "laterality": "left"})
    right = normalize_structure({"source_name": "parotid", "laterality": "right"})
    assert left.canonical_name == "Parotid_L"
    assert right.canonical_name == "Parotid_R"


def test_normalization_does_not_mutate_source_record() -> None:
    record = {"source_name": "left optic nerve", "is_prv": True, "prv_margin_mm": 3}
    before = deepcopy(record)
    normalize_structure(record)
    assert record == before


def test_all_public_tg263_tasks_load_and_have_reference_graders() -> None:
    task_paths = sorted(Path("tasks/public/structure_naming").glob("*/task.yaml"))
    assert len(task_paths) >= 16
    for path in task_paths:
        task = load_task(path)
        assert task.domain == "radiation_therapy_physics"
        assert task.track == "structure_naming"
        assert task.access_class.value == "public"
        assert task.grading.get("graders")
        assert task.provenance["source_class"] == "synthetic"


def test_each_task_has_an_executable_reference_solution() -> None:
    for path in sorted(Path("tasks/public/structure_naming").glob("*/task.yaml")):
        task = load_task(path)
        records = task.input_payload["structures"]
        decisions = normalize_structure_set(records)
        decision = decisions[0]
        reference_output = {
            "action": decision.action.value,
            "canonical_name": decision.canonical_name,
            "reason_codes": list(decision.reason_codes),
            "requires_escalation": decision.requires_escalation,
        }
        grades = score_attempt(task, reference_output)
        assert grades, path
        assert all(grade.passed for grade in grades), (path, grades)
