#!/usr/bin/env python3
"""Validate content-addressed admissions for descriptive-only common-harness rows."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from medphys_agentbench.artifact_tree import artifact_tree_sha256, json_artifact_inventory
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "descriptive-admission.v1.schema.json"
IDENTITY_FIELDS = ("provider", "model_name", "model_revision", "harness_name", "harness_revision")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_repo_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    if not candidate.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Path escapes repository root: {relative}")
    return candidate


def _identity(value: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(value.get(field) for field in IDENTITY_FIELDS)


def _git_commit_exists(commit: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def validate_descriptive_admissions(
    admission_path: Path,
    *,
    release_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _load_json(admission_path)
    schema = _load_json(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Descriptive admission schema validation failed: {rendered}")

    release_file = _safe_repo_path(payload["release_file"])
    release = load_release(release_file)
    if release.release_id != payload["release_id"]:
        raise ValueError("Descriptive admission release_id does not match the frozen release file.")
    if not _git_commit_exists(payload["admission_commit"]):
        raise ValueError(f"Unknown admission_commit: {payload['admission_commit']}")

    summary = release_summary or summarize_release(release, ROOT / "results" / "releases")
    if summary.get("release", {}).get("release_id") != release.release_id:
        raise ValueError("Provided release summary does not match the descriptive admission release_id.")
    expected_rows = [
        row
        for row in summary.get("unranked_models", [])
        if row.get("execution_surface") == "common_harness"
    ]
    expected_by_identity = {_identity(row): row for row in expected_rows}
    if len(expected_by_identity) != len(expected_rows):
        raise ValueError("Descriptive common-harness rows contain duplicate identities.")

    entries = payload["entries"]
    entry_by_identity = {_identity(entry): entry for entry in entries}
    if len(entry_by_identity) != len(entries):
        raise ValueError("Descriptive admission entries contain duplicate identities.")
    if set(entry_by_identity) != set(expected_by_identity):
        missing = sorted(set(expected_by_identity).difference(entry_by_identity))
        extra = sorted(set(entry_by_identity).difference(expected_by_identity))
        raise ValueError(
            "Descriptive admission must exactly cover common-harness unranked rows; "
            f"missing={missing}, extra={extra}."
        )

    expected_parent = (ROOT / "results" / "releases" / release.release_id).resolve()
    seen_directories: set[Path] = set()
    for identity, entry in entry_by_identity.items():
        row = expected_by_identity[identity]
        if row.get("ranking_eligible") is not False:
            raise ValueError(f"Descriptive admission cannot bind a ranking-eligible row: {identity}.")
        accepted_errors = sorted(entry["accepted_integrity_errors"])
        current_errors = sorted(row.get("integrity", {}).get("integrity_errors", []))
        if accepted_errors != current_errors:
            raise ValueError(
                f"Descriptive admission integrity errors drifted for {identity}: "
                f"admitted={accepted_errors}, current={current_errors}."
            )

        results_directory = _safe_repo_path(entry["results_directory"])
        if results_directory.parent != expected_parent:
            raise ValueError(f"Descriptive admission directory is outside the exact release tree: {identity}.")
        if results_directory in seen_directories:
            raise ValueError(f"Descriptive admission reuses one results directory: {results_directory}.")
        seen_directories.add(results_directory)

        artifacts = json_artifact_inventory(results_directory)
        if len(artifacts) != entry["artifact_count"]:
            raise ValueError(f"Descriptive admission artifact count drifted for {identity}.")
        if artifact_tree_sha256(artifacts) != entry["artifact_tree_sha256"]:
            raise ValueError(f"Descriptive admission artifact tree drifted for {identity}.")
        result_artifacts = [artifact for artifact in artifacts if artifact["kind"] == "result"]
        expected_result_count = len(release.load_tasks()) * release.expected_attempts_per_task
        if len(result_artifacts) != expected_result_count:
            raise ValueError(
                f"Descriptive admission expected {expected_result_count} result artifacts; "
                f"found {len(result_artifacts)} for {identity}."
            )
        for artifact in result_artifacts:
            result = _load_json(results_directory / artifact["path"])
            descriptor = result.get("manifest", {}).get("model", {})
            if _identity(descriptor) != identity:
                raise ValueError(f"{artifact['path']}: descriptive admission model identity mismatch.")

    return {
        "admission_id": payload["admission_id"],
        "release_id": release.release_id,
        "entry_count": len(entries),
        "scope": payload["scope"],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("admission", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_descriptive_admissions(args.admission), indent=2, sort_keys=True))
