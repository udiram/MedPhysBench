from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.common_harness_submission as submission_module
from scripts.common_harness_submission import validate_submission

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "submissions" / "phi4-mini-openkb-v0.6-20260802.json"
PIXTRAL_MANIFEST = ROOT / "submissions" / "pixtral-12b-community-q4km-openkb-v0.6-20260802.json"
CURRENT_CONTRACT_RERUNS = (
    (
        ROOT / "submissions" / "qwen3.5-4b-openkb-v0.6-20260803.json",
        "qwen3.5:4b",
        "sha256:2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd",
    ),
    (
        ROOT / "submissions" / "gemma3-4b-openkb-v0.6-20260803.json",
        "gemma3:4b",
        "sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a",
    ),
    (
        ROOT / "submissions" / "qwen2.5vl-3b-openkb-v0.6-20260803.json",
        "qwen2.5vl:3b",
        "sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1",
    ),
)


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "submission.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_committed_common_harness_submission_validates() -> None:
    summary = validate_submission(MANIFEST)

    assert summary["artifact_count"] == 30
    assert summary["ranking_eligible"] is True
    assert summary["model_name"] == "phi4-mini:3.8b-q4_K_M"


@pytest.mark.parametrize(("manifest", "model_name", "model_revision"), CURRENT_CONTRACT_RERUNS)
def test_current_contract_rerun_is_attested_and_revision_pinned(
    manifest: Path,
    model_name: str,
    model_revision: str,
) -> None:
    summary = validate_submission(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert summary["artifact_count"] == 30
    assert summary["ranking_eligible"] is True
    assert summary["model_name"] == model_name
    assert payload["model"]["model_revision"] == model_revision
    assert payload["model"]["harness_revision"] == "reference-json-v2"


def test_community_quantization_submission_binds_exact_artifact_provenance() -> None:
    summary = validate_submission(PIXTRAL_MANIFEST)
    payload = json.loads(PIXTRAL_MANIFEST.read_text(encoding="utf-8"))
    provenance = payload["model"]["artifact_provenance"]

    assert summary["artifact_count"] == 30
    assert provenance["source_url"].endswith(provenance["source_revision"])
    assert {
        (artifact["role"], artifact["sha256"], artifact["bytes"])
        for artifact in provenance["artifacts"]
    } == {
        (
            "model_weights",
            "80f05f4f031bd9cdcd073051e23d2e55d9b71136cc2832eaa0da4a4ea44ed67b",
            7703795680,
        ),
        (
            "vision_projector",
            "25622e8033dd8d80aa00f1542dbd16898e65a2b99a3449b8070ad8d6eed75c5d",
            1739863968,
        ),
    }


def test_community_quantization_submission_rejects_provenance_tampering(tmp_path: Path) -> None:
    payload = copy.deepcopy(json.loads(PIXTRAL_MANIFEST.read_text(encoding="utf-8")))
    payload["model"]["artifact_provenance"]["artifacts"][0]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="artifact_provenance does not match"):
        validate_submission(_write_manifest(tmp_path, payload))


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
