"""Machine-verifiable model qualification evidence for public promotion."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

PROMOTION_BASIS = "attested_complete_q2"
QUALIFICATION_CHRONOLOGIES = {
    "preflight_before_full_q2",
    "backfilled_after_full_q2",
}


def load_access_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(entry, dict) for entry in payload):
        raise ValueError(f"Access status must contain a list of objects: {path}")
    return payload


def find_access_entry(
    entries: list[dict[str, Any]],
    *,
    provider: str,
    model_name: str,
    base_model_id: str,
) -> dict[str, Any]:
    matches = [
        entry
        for entry in entries
        if entry.get("provider") == provider
        and entry.get("model") == model_name
        and entry.get("base_model_id") == base_model_id
    ]
    if len(matches) != 1:
        raise ValueError(
            "Expected one access-status entry for "
            f"{provider}::{model_name}::{base_model_id}; found {len(matches)}."
        )
    return matches[0]


def validate_attested_q2_qualification(
    entry: dict[str, Any],
    *,
    repository_root: Path,
    provider: str,
    model_name: str,
    base_model_id: str,
    expected_submission_id: str | None = None,
    expected_manifest_path: str | None = None,
) -> dict[str, Any]:
    identity = f"{provider}::{model_name}::{base_model_id}"
    if entry.get("status") != "available" or entry.get("qualification_stage") != "q2":
        raise ValueError(f"{identity}: public promotion requires available Q2 access status.")
    if entry.get("provider") != provider or entry.get("model") != model_name:
        raise ValueError(f"{identity}: qualification entry does not match the system configuration.")
    if entry.get("base_model_id") != base_model_id:
        raise ValueError(f"{identity}: qualification entry does not match the frozen base model.")
    if entry.get("promotion_basis") != PROMOTION_BASIS:
        raise ValueError(
            f"{identity}: promotion_basis must be {PROMOTION_BASIS!r} for the current Q2 contract."
        )
    chronology = entry.get("qualification_chronology")
    if chronology not in QUALIFICATION_CHRONOLOGIES:
        raise ValueError(
            f"{identity}: qualification_chronology must declare whether preflight preceded full Q2."
        )

    evidence = entry.get("qualification_evidence")
    if not isinstance(evidence, dict) or evidence.get("kind") != "common_harness_submission":
        raise ValueError(f"{identity}: qualification_evidence must reference a common-harness submission.")
    submission_id = evidence.get("submission_id")
    manifest_path = evidence.get("manifest_path")
    if not isinstance(submission_id, str) or not submission_id:
        raise ValueError(f"{identity}: qualification evidence has no submission_id.")
    if not isinstance(manifest_path, str) or not manifest_path:
        raise ValueError(f"{identity}: qualification evidence has no manifest_path.")
    relative = PurePosixPath(manifest_path)
    if relative.is_absolute() or ".." in relative.parts or relative.parent != PurePosixPath("submissions"):
        raise ValueError(f"{identity}: qualification manifest must be one JSON file under submissions/.")
    if relative.suffix != ".json":
        raise ValueError(f"{identity}: qualification manifest must be JSON.")
    if expected_submission_id is not None and submission_id != expected_submission_id:
        raise ValueError(f"{identity}: access evidence references a different submission_id.")
    if expected_manifest_path is not None and manifest_path != expected_manifest_path:
        raise ValueError(f"{identity}: access evidence references a different submission path.")

    resolved_root = repository_root.resolve()
    resolved_manifest = (resolved_root / Path(*relative.parts)).resolve()
    if not resolved_manifest.is_relative_to(resolved_root) or not resolved_manifest.is_file():
        raise ValueError(f"{identity}: qualification submission does not exist: {manifest_path}")
    submission = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    if not isinstance(submission, dict):
        raise ValueError(f"{identity}: qualification submission must contain an object.")
    if submission.get("submission_id") != submission_id:
        raise ValueError(f"{identity}: qualification submission ID differs from access evidence.")
    submitted_model = submission.get("model")
    if not isinstance(submitted_model, dict):
        raise ValueError(f"{identity}: qualification submission has no model descriptor.")
    for field, expected in (
        ("provider", provider),
        ("model_name", model_name),
        ("base_model_id", base_model_id),
    ):
        if submitted_model.get(field) != expected:
            raise ValueError(f"{identity}: qualification submission model mismatch for {field}.")
    return evidence
