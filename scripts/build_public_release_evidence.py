#!/usr/bin/env python3
"""Validate the canonical release-evidence index and project it to the public site."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from math import isclose
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

CANONICAL_PATH = ROOT / "governance" / "release-evidence-index.json"
PUBLIC_PATH = ROOT / "web" / "public" / "data" / "release_evidence.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected an object at the document root.")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_path(value: str, *, root: Path, expected_root: Path) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"Absolute evidence path is forbidden: {value!r}.")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(expected_root.resolve()) or not resolved.is_file():
        raise ValueError(f"Evidence path is missing or outside {expected_root}: {value!r}.")
    return resolved


def _release_contract_hash_v2(release: Any, tasks: tuple[Any, ...]) -> str:
    from medphys_agentbench.reporting import _release_contract_hash
    from medphys_agentbench.runner import (
        grader_hash_for_task,
        prompt_hash_for_task,
        runtime_task_hash_for_task,
        system_prompt_hash,
        tool_schema_hash_for_task,
    )

    task_hash_catalog = {
        task.task_id: {
            "prompt_hash": prompt_hash_for_task(task),
            "tool_schema_hash": tool_schema_hash_for_task(task),
            "runtime_task_hash": runtime_task_hash_for_task(task),
            "system_prompt_hash": system_prompt_hash(),
            "grader_hash": grader_hash_for_task(task),
        }
        for task in tasks
    }
    return _release_contract_hash(
        release_id=release.release_id,
        expected_attempts=release.expected_attempts_per_task,
        tasks=tasks,
        task_hash_catalog=task_hash_catalog,
    )


def _validate_count_state(state: dict[str, Any], *, release_id: str, field: str) -> None:
    completed = int(state["completed"])
    target = state["target"]
    if target is not None and completed > int(target):
        raise ValueError(f"{release_id}:{field}: completed cannot exceed target.")
    if state["status"] == "complete":
        if target is None or completed != int(target):
            raise ValueError(f"{release_id}:{field}: complete requires a non-null target and completed == target.")
    if state["status"] == "not_applicable" and (completed != 0 or target is not None):
        raise ValueError(f"{release_id}:{field}: not_applicable requires completed=0 and target=null.")


def _claim_text(entry: dict[str, Any], side: str) -> str:
    return " ".join(str(item).lower() for item in entry["claim_boundary"][side])


def _validate_claim_guards(entry: dict[str, Any]) -> None:
    release_id = str(entry["release_id"])
    prohibited = _claim_text(entry, "prohibited")
    evidence = entry["evidence"]
    if evidence["human_baseline"]["status"] != "complete" and "human" not in prohibited:
        raise ValueError(f"{release_id}: incomplete human baseline must be explicit in prohibited claims.")
    if evidence["independent_domain_review"]["status"] != "complete" and "independent" not in prohibited:
        raise ValueError(f"{release_id}: incomplete independent review must be explicit in prohibited claims.")
    if evidence["independent_replication"]["status"] != "complete" and "replication" not in prohibited:
        raise ValueError(f"{release_id}: missing independent replication must be explicit in prohibited claims.")
    if entry["exposure"]["protected_holdout"]["status"] != "operating" and not any(
        token in prohibited for token in ("contamination", "protected", "frontier")
    ):
        raise ValueError(f"{release_id}: absent protected holdout must be explicit in prohibited claims.")
    if entry["interaction"]["depth"] == "single_response" and not any(
        token in prohibited for token in ("stateful", "workflow", "end-to-end")
    ):
        raise ValueError(f"{release_id}: single-response depth must be explicit in prohibited claims.")


def _validate_interaction(entry: dict[str, Any]) -> None:
    release_id = str(entry["release_id"])
    interaction = entry["interaction"]
    if interaction["depth"] == "single_response":
        if interaction["trajectory_capture"] != "none" or interaction["final_state_grading"] is not False:
            raise ValueError(f"{release_id}: single_response requires no trajectory and no final-state grading.")
    elif interaction["depth"] == "stateful_workflow":
        if interaction["trajectory_capture"] != "complete" or interaction["final_state_grading"] is not True:
            raise ValueError(f"{release_id}: stateful_workflow requires complete trajectory and final-state grading.")


def validate_release_evidence_index(
    payload: dict[str, Any],
    *,
    root: Path = ROOT,
) -> None:
    from medphys_agentbench.release_loader import load_release

    release_paths = sorted((root / "releases").glob("*.yaml"))
    releases_by_id = {load_release(path).release_id: (path, load_release(path)) for path in release_paths}
    entries = payload["releases"]
    release_ids = [str(entry["release_id"]) for entry in entries]
    if release_ids != sorted(release_ids):
        raise ValueError("release evidence entries must be ordered by release_id.")
    if len(release_ids) != len(set(release_ids)):
        raise ValueError("release evidence contains duplicate release_id values.")
    if set(release_ids) != set(releases_by_id):
        missing = sorted(set(releases_by_id).difference(release_ids))
        extra = sorted(set(release_ids).difference(releases_by_id))
        raise ValueError(f"release evidence coverage mismatch; missing={missing}, extra={extra}.")

    defects = _load_json(root / "governance" / "benchmark-defects.json")
    defect_ids_by_release: dict[str, set[str]] = {}
    for defect in defects["entries"]:
        for release_id in defect["affected_release_ids"]:
            defect_ids_by_release.setdefault(str(release_id), set()).add(str(defect["defect_id"]))

    linked_review_paths: set[Path] = set()
    for entry in entries:
        release_id = str(entry["release_id"])
        release_path, release = releases_by_id[release_id]
        manifest = _repository_path(
            str(entry["manifest_path"]),
            root=root,
            expected_root=root / "releases",
        )
        if manifest != release_path.resolve():
            raise ValueError(f"{release_id}: manifest_path points at the wrong release.")
        if entry["manifest_sha256"] != _sha256(manifest):
            raise ValueError(f"{release_id}: manifest_sha256 mismatch.")

        tasks = release.load_tasks()
        families = Counter(task.family_id or task.task_id for task in tasks)
        observed_share = max(families.values()) / len(tasks)
        expected = {
            "task_count": len(tasks),
            "family_count": len(families),
            "expected_attempts_per_task": release.expected_attempts_per_task,
            "integrity_profile": release.integrity_profile,
            "public_attempt_detail": release.public_attempt_detail,
        }
        for field, value in expected.items():
            if entry[field] != value:
                raise ValueError(f"{release_id}: {field} does not match the release manifest.")
        access_classes = sorted(item.value for item in release.allow_access_classes)
        if entry["allow_access_classes"] != access_classes:
            raise ValueError(f"{release_id}: allow_access_classes does not match the release manifest.")
        if not isclose(float(entry["max_family_share_observed"]), observed_share, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"{release_id}: max_family_share_observed does not match the task families.")
        if entry["release_contract_hash_v2"] != _release_contract_hash_v2(release, tasks):
            raise ValueError(f"{release_id}: release_contract_hash_v2 mismatch.")

        expected_task_access = "private" if "private" in access_classes else (
            "restricted" if {"restricted", "gated"}.intersection(access_classes) else "public"
        )
        if entry["exposure"]["task_access"] != expected_task_access:
            raise ValueError(f"{release_id}: exposure.task_access contradicts allow_access_classes.")
        if entry["maturity"] == "protected_comparison":
            holdout_operating = entry["exposure"]["protected_holdout"]["status"] == "operating"
            if release.integrity_profile != "comparison" or not holdout_operating:
                raise ValueError(
                    f"{release_id}: protected_comparison requires comparison profile and an operating holdout."
                )

        expected_defects = sorted(defect_ids_by_release.get(release_id, set()))
        if entry["defect_ids"] != expected_defects or entry["defect_count"] != len(expected_defects):
            raise ValueError(f"{release_id}: defect summary differs from the canonical defect ledger.")

        evidence = entry["evidence"]
        _validate_count_state(
            evidence["independent_domain_review"],
            release_id=release_id,
            field="independent_domain_review",
        )
        _validate_count_state(evidence["human_baseline"], release_id=release_id, field="human_baseline")
        _validate_interaction(entry)
        _validate_claim_guards(entry)

        review_binding = entry["review_ledger"]
        expected_review_path = root / "reviews" / f"{release_id}.json"
        if review_binding is None:
            if expected_review_path.is_file():
                raise ValueError(f"{release_id}: canonical review ledger exists but is not bound.")
            continue
        review_path = _repository_path(
            str(review_binding["path"]),
            root=root,
            expected_root=root / "reviews",
        )
        if review_path != expected_review_path.resolve() or review_binding["sha256"] != _sha256(review_path):
            raise ValueError(f"{release_id}: review ledger path or hash mismatch.")
        linked_review_paths.add(review_path)
        review = _load_json(review_path)
        if review["release_id"] != release_id:
            raise ValueError(f"{release_id}: review ledger release_id mismatch.")
        review_pairs = (
            ("reference_feasibility", "status", "reference_feasibility", "status"),
            ("independent_domain_review", "status", "independent_domain_review", "status"),
            ("independent_domain_review", "completed", "independent_domain_review", "completed"),
            ("independent_domain_review", "target", "independent_domain_review", "target"),
            ("human_baseline", "status", "human_baseline", "status"),
            ("human_baseline", "completed", "human_baseline", "completed"),
            ("human_baseline", "target", "human_baseline", "target"),
            ("data_rights_review", "status", "data_rights_review", "status"),
        )
        for evidence_group, evidence_field, review_group, review_field in review_pairs:
            if evidence[evidence_group][evidence_field] != review[review_group][review_field]:
                raise ValueError(
                    f"{release_id}: evidence.{evidence_group}.{evidence_field} differs from review ledger."
                )
        if entry["claim_boundary"] != review["claim_boundary"]:
            raise ValueError(f"{release_id}: claim boundary differs from the review ledger.")

    unlinked_reviews = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "reviews").glob("*.json")
        if path.resolve() not in linked_review_paths
    )
    if unlinked_reviews:
        raise ValueError(f"Unlinked release review ledgers: {unlinked_reviews}.")


def build_public_projection(*, canonical_path: Path = CANONICAL_PATH) -> dict[str, Any]:
    payload = _load_json(canonical_path)
    validate_release_evidence_index(payload, root=ROOT)
    return payload


def _serialize(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--public", type=Path, default=PUBLIC_PATH)
    args = parser.parse_args()

    rendered = _serialize(build_public_projection())
    if args.check:
        if not args.public.is_file() or args.public.read_bytes() != rendered:
            raise SystemExit("Stale public release evidence projection: web/public/data/release_evidence.json")
        print("release evidence index projection up to date")
        return
    args.public.parent.mkdir(parents=True, exist_ok=True)
    args.public.write_bytes(rendered)


if __name__ == "__main__":
    main()
