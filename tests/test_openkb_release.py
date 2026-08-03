from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from medphys_agentbench.adapters.reference import DevelopmentReferenceAgent
from medphys_agentbench.contracts import ContractError
from medphys_agentbench.json_utils import stable_hash
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.runner import run_trial

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "releases" / "public_real_workflows_pilot_v0_6.yaml"


def test_openkb_release_uses_case_families_and_multi_attempt_pilot_contract() -> None:
    release = load_release(RELEASE_PATH)
    tasks = release.load_tasks()

    assert release.integrity_profile == "pilot"
    assert release.public_attempt_detail == "sanitized_output"
    assert release.expected_attempts_per_task == 3
    assert len(tasks) == 10
    assert {task.family_id for task in tasks} == {"openkb.pt_289", "openkb.pt_242"}
    assert all(task.source_dependency_id for task in tasks)
    assert all(task.difficulty_tier in {"professional", "expert"} for task in tasks)


def test_every_openkb_task_has_a_feasible_reference_solution() -> None:
    for task in load_release(RELEASE_PATH).load_tasks():
        reference = task.grading.get("development_reference_output")
        assert isinstance(reference, dict), task.task_id

        result = run_trial(task, DevelopmentReferenceAgent(output=reference))

        assert result.passed is True, task.task_id
        assert result.safe is True, task.task_id
        assert result.score == 1.0, task.task_id


def test_openkb_segmentation_gold_matches_pinned_fixture_manifests() -> None:
    tasks = {task.task_id: task for task in load_release(RELEASE_PATH).load_tasks()}
    for patient_id in ("pt_289", "pt_242"):
        manifest = json.loads(
            (ROOT / "assets" / "planning" / "openkb" / patient_id / "manifest.json").read_text(encoding="utf-8")
        )
        parotid_task = tasks[f"public.rt.openkb-{patient_id.replace('_', '')}-parotid-segmentation-001"]
        dose_task = tasks[f"public.rt.openkb-{patient_id.replace('_', '')}-high-dose-segmentation-001"]
        assert parotid_task.grading["graders"][0]["expected"] == manifest["grid_gold"]["Parotids_bilateral"]
        assert dose_task.grading["graders"][0]["expected"] == manifest["grid_gold"]["dose_ge_66p5_Gy"]


def test_runtime_projection_excludes_family_and_reference_labels() -> None:
    task = load_release(RELEASE_PATH).load_tasks()[0]
    runtime = task.runtime_task().to_dict()

    assert "family_id" not in runtime
    assert "source_dependency_id" not in runtime
    assert "grading" not in runtime
    assert "provenance" not in runtime
    assert "development_reference_output" not in json.dumps(runtime)


def test_public_attempt_pointers_bind_every_projected_row_to_committed_evidence() -> None:
    leaderboard = json.loads(
        (ROOT / "web/public/data/public-real-workflows-pilot-v0.6.json").read_text(
            encoding="utf-8"
        )
    )
    task_rows = [
        task
        for model in [*leaderboard["models"], *leaderboard["unranked_models"]]
        for task in model["tasks"]
    ]
    attempt_ids: set[str] = set()

    for task_row in task_rows:
        artifact_path = task_row["artifact_path"]
        assert artifact_path.startswith(
            "results/releases/public-real-workflows-pilot-v0.6/"
        )
        artifact = (ROOT / artifact_path).resolve()
        artifact.relative_to((ROOT / "results/releases").resolve())
        raw = artifact.read_bytes()
        payload = json.loads(raw)
        artifact_sha256 = hashlib.sha256(raw).hexdigest()

        assert task_row["artifact_sha256"] == artifact_sha256
        assert task_row["attempt_id"] == stable_hash(
            {
                "artifact_path": artifact_path,
                "artifact_sha256": artifact_sha256,
                "run_id": payload["manifest"].get("run_id"),
                "task_id": payload["manifest"]["task_id"],
                "attempt_index": payload.get("attempt_index"),
            }
        )
        assert task_row["attempt_id"] not in attempt_ids
        attempt_ids.add(task_row["attempt_id"])

    assert len(task_rows) == 1020


def test_pilot_profile_rejects_single_attempt_release(tmp_path: Path) -> None:
    release_path = tmp_path / "invalid.yaml"
    release_path.write_text(
        "\n".join(
            [
                "schema_version: medeval.release.v1",
                "release_id: invalid-pilot",
                "title: Invalid",
                "description: Invalid single-attempt pilot",
                "integrity_profile: pilot",
                "expected_attempts_per_task: 1",
                "task_files:",
                f"  - {ROOT / 'tasks/public/radiation_therapy/openkb_pt289_structure_inventory_001/task.yaml'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="requires at least 3 attempts"):
        load_release(release_path)


def test_release_rejects_task_paths_outside_repository_task_tree(tmp_path: Path) -> None:
    release_path = tmp_path / "escaped.yaml"
    release_path.write_text(
        "\n".join(
            [
                "schema_version: medeval.release.v1",
                "release_id: escaped-task",
                "title: Escaped",
                "description: Must not load off-repository task material",
                "task_files:",
                "  - ../private-task.yaml",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="repository tasks directory"):
        load_release(release_path)


def test_release_rejects_public_output_projection_for_nonpublic_access(tmp_path: Path) -> None:
    release_path = tmp_path / "unsafe-publication.yaml"
    release_path.write_text(
        "\n".join(
            [
                "schema_version: medeval.release.v1",
                "release_id: unsafe-publication",
                "title: Unsafe publication",
                "description: Restricted tasks must never expose attempt outputs",
                "allow_access_classes: [restricted]",
                "public_attempt_detail: sanitized_output",
                "task_files:",
                f"  - {ROOT / 'tasks/public/core_physics/inverse_square_001/task.yaml'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="every allowed access class is public"):
        load_release(release_path)


def test_release_rejects_answer_projection_for_comparison_profile(tmp_path: Path) -> None:
    release_path = tmp_path / "unsafe-comparison-publication.yaml"
    release_path.write_text(
        "\n".join(
            [
                "schema_version: medeval.release.v1",
                "release_id: unsafe-comparison-publication",
                "title: Unsafe comparison publication",
                "description: Comparison answers must remain aggregate-only",
                "allow_access_classes: [public]",
                "integrity_profile: comparison",
                "expected_attempts_per_task: 5",
                "public_attempt_detail: sanitized_output",
                "task_files:",
                f"  - {ROOT / 'tasks/public/core_physics/inverse_square_001/task.yaml'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="comparison-profile"):
        load_release(release_path)


def test_pilot_profile_rejects_tasks_without_family_ids(tmp_path: Path) -> None:
    release_path = tmp_path / "invalid.yaml"
    release_path.write_text(
        "\n".join(
            [
                "schema_version: medeval.release.v1",
                "release_id: invalid-family",
                "title: Invalid",
                "description: Invalid family-free pilot",
                "integrity_profile: pilot",
                "expected_attempts_per_task: 3",
                "task_files:",
                f"  - {ROOT / 'tasks/public/core_physics/inverse_square_001/task.yaml'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="lack family_id"):
        load_release(release_path).load_tasks()
