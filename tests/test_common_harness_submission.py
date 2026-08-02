from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.common_harness_submission as submission_module
from scripts.common_harness_submission import validate_submission

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "submissions" / "phi4-mini-openkb-v0.6-20260802.json"


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_committed_common_harness_submission_validates() -> None:
    summary = validate_submission(MANIFEST)

    assert summary["artifact_count"] == 30
    assert summary["ranking_eligible"] is True
    assert summary["model_name"] == "phi4-mini:3.8b-q4_K_M"


def test_submission_requires_matching_public_qualification_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = json.loads(submission_module.ACCESS_PATH.read_text(encoding="utf-8"))
    phi = next(entry for entry in access if entry.get("model") == "phi4-mini:3.8b-q4_K_M")
    phi.pop("qualification_evidence")
    access_path = tmp_path / "access-status.json"
    access_path.write_text(json.dumps(access), encoding="utf-8")
    monkeypatch.setattr(submission_module, "ACCESS_PATH", access_path)

    with pytest.raises(ValueError, match="qualification_evidence"):
        submission_module.validate_submission(MANIFEST)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["artifacts"][0].update(sha256="0" * 64), "Artifact inventory differs"),
        (lambda payload: payload["artifacts"].pop(), "Artifact inventory differs"),
        (lambda payload: payload.update(artifact_tree_sha256="0" * 64), "artifact_tree_sha256"),
        (
            lambda payload: payload["attestations"].update(no_manual_output_edits=False),
            "Submission schema validation failed",
        ),
        (
            lambda payload: payload.update(results_directory="results/releases/../secrets"),
            "results_directory",
        ),
        (lambda payload: payload.update(repo_commit="0" * 40), "Unknown git commit"),
        (
            lambda payload: payload["model"].update(base_model_id="not/the/frozen-model"),
            "base_model_id does not match",
        ),
        (lambda payload: payload.update(release_contract_hash_v2="0" * 64), "release_contract_hash_v2"),
    ],
)
def test_common_harness_submission_rejects_tampering(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    payload = copy.deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        validate_submission(_write_manifest(tmp_path, payload))
