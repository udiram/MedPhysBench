from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


def test_public_sanitizer_redacts_trace_raw_preview(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    model_dir = release_root / "model"
    model_dir.mkdir(parents=True)
    artifact_path = model_dir / "attempt.json"
    artifact_path.write_text(
        json.dumps(
            {
                "raw_response": {"content": "private response"},
                "trace": [{"event": "parse_error", "raw_preview": "private preview"}],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/sanitize_public_results.py", str(release_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert "content" not in artifact["raw_response"]
    assert artifact["raw_response"]["content_redacted"] is True
    assert "raw_preview" not in artifact["trace"][0]
    assert artifact["trace"][0]["raw_preview_redacted"] is True

    check = subprocess.run(
        [sys.executable, "scripts/sanitize_public_results.py", str(release_root), "--check"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0


def test_public_sanitizer_ignores_release_summary_json(tmp_path: Path) -> None:
    releases_root = tmp_path / "releases"
    release_dir = releases_root / "release"
    release_dir.mkdir(parents=True)
    leaderboard_path = release_dir / "leaderboard.json"
    leaderboard_path.write_text(json.dumps([{"model_name": "fixture"}]), encoding="utf-8")

    check = subprocess.run(
        [sys.executable, "scripts/sanitize_public_results.py", str(releases_root), "--check"],
        capture_output=True,
        text=True,
    )

    assert check.returncode == 0
    assert json.loads(leaderboard_path.read_text(encoding="utf-8")) == [
        {"model_name": "fixture"}
    ]


def test_completed_human_review_state_requires_hashed_evidence_package() -> None:
    schema = json.loads(
        Path("schemas/review-evidence.v1.schema.json").read_text(encoding="utf-8")
    )
    payload = json.loads(
        Path("reviews/public-real-workflows-pilot-v0.6.json").read_text(encoding="utf-8")
    )
    payload["human_baseline"] = {
        **payload["human_baseline"],
        "status": "complete",
        "completed": payload["human_baseline"]["target"],
    }

    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)
    )

    assert errors
    required_evidence_fields = {
        "completed_at",
        "matched_release_id",
        "evidence_artifacts",
    }
    reported_missing_fields = {
        field
        for error in errors
        for field in required_evidence_fields
        if field in error.message
    }
    assert reported_missing_fields == {
        "completed_at",
        "matched_release_id",
        "evidence_artifacts",
    }


def test_completed_review_evidence_must_match_release_count_and_artifact_hash() -> None:
    from scripts.validate_repository import _validate_review_evidence_semantics

    review_path = Path("reviews/public-real-workflows-pilot-v0.6.json")
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    readme_path = Path("README.md")
    payload["human_baseline"] = {
        **payload["human_baseline"],
        "status": "complete",
        "completed": payload["human_baseline"]["target"],
        "completed_at": "2026-08-02T12:00:00Z",
        "matched_release_id": payload["release_id"],
        "evidence_artifacts": [
            {
                "path": str(readme_path),
                "sha256": hashlib.sha256(readme_path.read_bytes()).hexdigest(),
            }
        ],
    }
    _validate_review_evidence_semantics(payload, review_path)

    payload["human_baseline"]["completed"] -= 1
    with pytest.raises(ValueError, match="completed == target"):
        _validate_review_evidence_semantics(payload, review_path)

    payload["human_baseline"]["completed"] += 1
    payload["human_baseline"]["evidence_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        _validate_review_evidence_semantics(payload, review_path)


def test_public_review_evidence_projection_matches_canonical_ledger() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_public_review_evidence.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_release_evidence_projection_matches_canonical_ledger() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_public_release_evidence.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout

    schema = json.loads(Path("schemas/release-evidence-index.v1.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(
        Path("governance/release-evidence-index.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_release_evidence_rejects_manifest_count_and_review_hash_drift() -> None:
    from scripts.build_public_release_evidence import validate_release_evidence_index

    payload = json.loads(Path("governance/release-evidence-index.json").read_text(encoding="utf-8"))

    tampered = deepcopy(payload)
    tampered["releases"][0]["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="manifest_sha256 mismatch"):
        validate_release_evidence_index(tampered)

    tampered = deepcopy(payload)
    tampered["releases"][0]["family_count"] += 1
    with pytest.raises(ValueError, match="family_count does not match"):
        validate_release_evidence_index(tampered)

    tampered = deepcopy(payload)
    real = next(item for item in tampered["releases"] if item["release_id"] == "public-real-workflows-pilot-v0.6")
    real["review_ledger"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="review ledger path or hash mismatch"):
        validate_release_evidence_index(tampered)


def test_release_evidence_fails_closed_on_overclaim_and_stateful_shortcuts() -> None:
    from scripts.build_public_release_evidence import validate_release_evidence_index

    payload = json.loads(Path("governance/release-evidence-index.json").read_text(encoding="utf-8"))

    tampered = deepcopy(payload)
    entry = tampered["releases"][0]
    entry["claim_boundary"]["prohibited"] = ["Clinical use is prohibited."]
    with pytest.raises(ValueError, match="incomplete human baseline"):
        validate_release_evidence_index(tampered)

    tampered = deepcopy(payload)
    entry = tampered["releases"][0]
    entry["interaction"] = {
        **entry["interaction"],
        "depth": "stateful_workflow",
        "trajectory_capture": "none",
        "final_state_grading": False,
    }
    with pytest.raises(ValueError, match="stateful_workflow requires complete trajectory"):
        validate_release_evidence_index(tampered)


def test_release_evidence_requires_exact_release_coverage() -> None:
    from scripts.build_public_release_evidence import validate_release_evidence_index

    payload = json.loads(Path("governance/release-evidence-index.json").read_text(encoding="utf-8"))
    payload["releases"].pop()

    with pytest.raises(ValueError, match="release evidence coverage mismatch"):
        validate_release_evidence_index(payload)


def test_public_defect_ledger_is_valid_and_matches_canonical_projection() -> None:
    schema = json.loads(Path("schemas/defect-ledger.v1.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path("governance/benchmark-defects.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)

    completed = subprocess.run(
        [sys.executable, "scripts/build_public_defect_ledger.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_defect_ledger_rejects_unknown_affected_task() -> None:
    from medphys_agentbench.release_loader import load_release
    from scripts.validate_repository import _validate_defect_ledger_semantics

    payload = json.loads(Path("governance/benchmark-defects.json").read_text(encoding="utf-8"))
    payload["entries"][0]["affected_task_ids"].append("private.nonexistent-task")
    releases = {
        "public-real-workflows-pilot-v0.6": load_release(
            "releases/public_real_workflows_pilot_v0_6.yaml"
        )
    }

    with pytest.raises(ValueError, match="unknown affected task"):
        _validate_defect_ledger_semantics(payload, Path("fixture.json"), releases)


def test_v07_required_limitations_field_cannot_be_presence_only() -> None:
    import yaml

    from scripts.validate_repository import _validate_task_grading_semantics

    task_path = Path(
        "tasks/public/radiation_therapy/openkb_pt242_plan_criteria_audit_001/task.yaml"
    )
    payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    payload["version"] = "0.7.0"

    with pytest.raises(ValueError, match="explicit limitations grader"):
        _validate_task_grading_semantics(payload, task_path)

    payload["grading"]["graders"].append(
        {
            "type": "contains_all_strings",
            "field": "limitations",
            "expected": ["research", "clinical"],
            "required_for_pass": True,
        }
    )
    _validate_task_grading_semantics(payload, task_path)


def test_api_release_path_cannot_escape_results_root(tmp_path: Path) -> None:
    fastapi = pytest.importorskip("fastapi")
    from medphys_agentbench.api import _release_leaderboard_path

    results_root = (tmp_path / "results").resolve()
    results_root.mkdir()

    with pytest.raises(fastapi.HTTPException) as exc_info:
        _release_leaderboard_path(results_root, "../../private")

    assert exc_info.value.status_code == 404
