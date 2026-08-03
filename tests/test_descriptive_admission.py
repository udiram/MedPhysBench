from __future__ import annotations

import json
from pathlib import Path

import pytest

from medphys_agentbench.release_loader import load_release
from scripts.descriptive_admission import validate_descriptive_admissions
from scripts.rebuild_public_release import _build_projection
from tests.test_regressions import _write_result

ROOT = Path(__file__).resolve().parents[1]
ADMISSION = ROOT / "governance" / "descriptive-admissions-public-real-workflows-pilot-v0.6.json"


def test_committed_descriptive_admission_exactly_covers_unranked_common_rows() -> None:
    summary = validate_descriptive_admissions(ADMISSION)

    assert summary == {
        "admission_id": "openkb-v0.6-descriptive-20260803",
        "release_id": "public-real-workflows-pilot-v0.6",
        "entry_count": 10,
        "scope": "descriptive_publication_only",
    }


def test_unsubmitted_singleton_cannot_enter_descriptive_public_projection(tmp_path: Path) -> None:
    release_path = ROOT / "releases" / "public_dev_2026_07_31.yaml"
    release = load_release(release_path)
    model_dir = tmp_path / release.release_id / "fabricated-singleton"
    model_dir.mkdir(parents=True)
    for task in release.load_tasks():
        _write_result(model_dir / f"{task.task_id}--attempt-1.json", task, "fabricated-singleton")

    with pytest.raises(ValueError, match="content-addressed admission ledger"):
        _build_projection(
            release_file=release_path,
            results_root=tmp_path,
            expected_attempts_per_task=None,
            submissions_dir=tmp_path / "submissions",
            descriptive_admissions=tmp_path / "missing-admission.json",
        )


@pytest.mark.parametrize("mutation", ["artifact_tree", "integrity_errors", "missing_entry"])
def test_descriptive_admission_fails_closed_on_ledger_drift(tmp_path: Path, mutation: str) -> None:
    payload = json.loads(ADMISSION.read_text(encoding="utf-8"))
    if mutation == "artifact_tree":
        payload["entries"][0]["artifact_tree_sha256"] = "0" * 64
        expected = "artifact tree drifted"
    elif mutation == "integrity_errors":
        payload["entries"][0]["accepted_integrity_errors"].append("invented_exception")
        expected = "integrity errors drifted"
    else:
        payload["entries"].pop()
        expected = "must exactly cover"
    path = tmp_path / "admission.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=expected):
        validate_descriptive_admissions(path)
