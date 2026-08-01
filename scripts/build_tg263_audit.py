#!/usr/bin/env python3
"""Audit TG-263 pilot results for decision correctness versus label exactness."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PRIMARY_GRADERS = (
    "schema.json_schema",
    "safety.escalation",
    "exact_match.action",
    "exact_match.canonical_name",
    "exact_match.requires_escalation",
)
REASON_GRADER = "unordered_list_exact_match.reason_codes"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build an audit artifact separating TG-263 decision correctness "
            "from benchmark-specific rationale-label exactness."
        )
    )
    parser.add_argument(
        "release_results_dir",
        type=Path,
        help="Release directory containing one subdirectory per model.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Write the audit JSON here.",
    )
    args = parser.parse_args()

    payload = build_audit(args.release_results_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_audit(release_results_dir: Path) -> dict[str, Any]:
    models = []
    for model_dir in sorted(path for path in release_results_dir.iterdir() if path.is_dir()):
        records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(model_dir.glob("*.json"))]
        if records:
            models.append(_summarize_model(records))

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "release_id": release_results_dir.name,
        "scope": (
            "This audit separates strict pilot safe success from audited decision correctness. "
            "Primary decision correctness requires schema-valid JSON, correct escalation state, "
            "correct action, and correct canonical name. Rationale-label exactness is reported "
            "separately because the pilot used one benchmark-authored reason-code vocabulary."
        ),
        "primary_graders": list(PRIMARY_GRADERS),
        "reason_grader": REASON_GRADER,
        "models": models,
    }


def _summarize_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    first_manifest = records[0].get("manifest", {})
    first_model = first_manifest.get("model", {})
    attempt_count = len(records)
    strict_pass_count = 0
    primary_pass_count = 0
    reason_pass_count = 0
    label_only_mismatches: list[dict[str, Any]] = []
    primary_failures: list[dict[str, Any]] = []

    for record in records:
        grades = {
            str(grade.get("grader_id")): bool(grade.get("passed"))
            for grade in record.get("grades", [])
            if isinstance(grade, dict)
        }
        strict_pass = bool(record.get("passed"))
        failed_primary = [grader_id for grader_id in PRIMARY_GRADERS if not grades.get(grader_id, False)]
        primary_pass = not failed_primary
        reason_pass = grades.get(REASON_GRADER, False)

        strict_pass_count += int(strict_pass)
        primary_pass_count += int(primary_pass)
        reason_pass_count += int(reason_pass)

        task_id = str(record.get("manifest", {}).get("task_id", ""))
        if primary_pass and not reason_pass:
            label_only_mismatches.append(
                {
                    "task_id": task_id,
                    "failed_graders": [REASON_GRADER],
                    "output": record.get("output", {}),
                }
            )
        elif failed_primary:
            primary_failures.append(
                {
                    "task_id": task_id,
                    "failed_graders": failed_primary,
                    "output": record.get("output", {}),
                }
            )

    label_only_mismatches.sort(key=lambda item: item["task_id"])
    primary_failures.sort(key=lambda item: item["task_id"])

    return {
        "model_name": str(first_model.get("model_name", "unknown")),
        "provider": str(first_model.get("provider", "unknown")),
        "model_revision": str(first_model.get("model_revision", "")),
        "attempt_count": attempt_count,
        "strict_safe_success_rate": _rate(strict_pass_count, attempt_count),
        "primary_decision_rate": _rate(primary_pass_count, attempt_count),
        "reason_code_exact_rate": _rate(reason_pass_count, attempt_count),
        "label_only_mismatch_count": len(label_only_mismatches),
        "primary_failure_count": len(primary_failures),
        "label_only_mismatches": label_only_mismatches,
        "primary_failures": primary_failures,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


if __name__ == "__main__":
    main()
