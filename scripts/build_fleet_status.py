#!/usr/bin/env python3
"""Build the public 50-base-model qualification funnel from repository evidence."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from medphys_agentbench.qualification import (
    find_access_entry,
    validate_attested_q2_qualification,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLEET = REPO_ROOT / "fleet" / "public_fleet_v1.yaml"
DEFAULT_CATALOG = REPO_ROOT / "web" / "public" / "data" / "model_catalog.json"
DEFAULT_ACCESS = REPO_ROOT / "web" / "public" / "data" / "access_status.json"
DEFAULT_LEADERBOARDS = (
    REPO_ROOT / "web" / "public" / "data" / "leaderboard.json",
    REPO_ROOT / "web" / "public" / "data" / "imaging_leaderboard.json",
    REPO_ROOT / "web" / "public" / "data" / "tg263_leaderboard.json",
    REPO_ROOT / "web" / "public" / "data" / "public-real-workflows-pilot-v0.6.json",
)
DEFAULT_OUTPUT = REPO_ROOT / "web" / "public" / "data" / "fleet_status.json"
WORKFLOW_QUALIFYING_RELEASE_IDS = {"public-real-workflows-pilot-v0.6"}

COMPARABILITY_ONLY_ISSUES = {
    "unranked_singleton_comparison_group",
}
STAGE_ORDER = {"q0": 0, "q1": 1, "q2": 2, "q3": 3}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fleet(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Fleet manifest must contain an object: {path}")
    return payload


def _complete_row(row: dict[str, Any]) -> bool:
    expected = row.get("expected_attempt_count")
    if not isinstance(expected, int) or expected <= 0:
        return False
    if row.get("attempt_count") != expected or row.get("completed_count") != expected:
        return False
    if row.get("error_count") != 0:
        return False
    integrity = row.get("integrity")
    if not isinstance(integrity, dict):
        return False
    if integrity.get("observed_attempt_keys") != expected:
        return False
    if integrity.get("missing_attempt_keys") != 0 or integrity.get("unexpected_attempt_keys") != 0:
        return False
    issues = integrity.get("integrity_errors", [])
    if not isinstance(issues, list):
        return False
    if set(issues) - COMPARABILITY_ONLY_ISSUES:
        return False
    for key in ("missing_attempts", "duplicate_attempts", "invalid_task_ids"):
        if row.get(key):
            return False
    return True


def build_fleet_status(
    *,
    fleet_path: Path = DEFAULT_FLEET,
    catalog_path: Path = DEFAULT_CATALOG,
    access_path: Path = DEFAULT_ACCESS,
    leaderboard_paths: tuple[Path, ...] = DEFAULT_LEADERBOARDS,
) -> dict[str, Any]:
    fleet = _load_fleet(fleet_path)
    fleet_models = fleet.get("models")
    if not isinstance(fleet_models, list):
        raise ValueError("Fleet manifest models must be a list.")
    target = fleet.get("target_base_model_count")
    if target != len(fleet_models):
        raise ValueError(f"Fleet target declares {target}, but manifest contains {len(fleet_models)} models.")

    fleet_ids = [str(row["base_model_id"]) for row in fleet_models]
    duplicate_ids = sorted({model_id for model_id in fleet_ids if fleet_ids.count(model_id) > 1})
    if duplicate_ids:
        raise ValueError(f"Fleet manifest has duplicate base model IDs: {duplicate_ids}")
    fleet_index = {str(row["base_model_id"]): row for row in fleet_models}

    catalog = _load_json(catalog_path)
    if not isinstance(catalog, list):
        raise ValueError("Public model catalog must be a list.")
    catalog_index: dict[tuple[str, str], dict[str, Any]] = {}
    configurations_by_base: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for entry in catalog:
        if not isinstance(entry, dict):
            raise ValueError("Public model catalog entries must be objects.")
        key = (str(entry["provider"]), str(entry["model_name"]))
        if key in catalog_index:
            raise ValueError(f"Duplicate public model catalog key: {key}")
        base_model_id = str(entry["base_model_id"])
        if base_model_id not in fleet_index:
            raise ValueError(f"Catalog row {key} maps to model outside frozen fleet: {base_model_id}")
        catalog_index[key] = entry
        configurations_by_base[base_model_id].add(key)

    access = _load_json(access_path)
    if not isinstance(access, list):
        raise ValueError("Access status must be a list.")
    stages_by_base: dict[str, set[str]] = defaultdict(set)
    access_evidence_by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in access:
        if not isinstance(entry, dict):
            continue
        base_model_id = entry.get("base_model_id")
        stage = entry.get("qualification_stage")
        if base_model_id not in fleet_index:
            continue
        base_model_id = str(base_model_id)
        access_evidence_by_base[base_model_id].append(
            {
                "provider": entry.get("provider"),
                "model": str(entry["model"]),
                "status": str(entry["status"]),
                "qualification_stage": stage if stage in STAGE_ORDER else None,
                "surface": str(entry["surface"]),
                "date": str(entry["date"]),
                "promotion_basis": entry.get("promotion_basis"),
                "qualification_evidence": entry.get("qualification_evidence"),
                "note": str(entry["note"]),
            }
        )
        if entry.get("status") == "available" and stage in STAGE_ORDER:
            stages_by_base[base_model_id].add(str(stage))

    evaluated_by_base: dict[str, bool] = defaultdict(bool)
    ranked_by_base: dict[str, bool] = defaultdict(bool)
    workflow_evaluated_by_base: dict[str, bool] = defaultdict(bool)
    workflow_ranked_by_base: dict[str, bool] = defaultdict(bool)
    releases_by_base: dict[str, set[str]] = defaultdict(set)
    row_count_by_base: dict[str, int] = defaultdict(int)
    visible_configurations: set[tuple[str, str]] = set()

    for path in leaderboard_paths:
        payload = _load_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"Leaderboard must contain an object: {path}")
        release = payload.get("release")
        if not isinstance(release, dict) or not isinstance(release.get("release_id"), str):
            raise ValueError(f"Leaderboard has no release ID: {path}")
        release_id = str(release["release_id"])
        rows = [*payload.get("models", []), *payload.get("unranked_models", [])]
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Leaderboard model row must be an object: {path}")
            key = (str(row["provider"]), str(row["model_name"]))
            if key not in catalog_index:
                raise ValueError(f"Visible leaderboard row is missing from model catalog: {key}")
            base_model_id = str(catalog_index[key]["base_model_id"])
            if row.get("harness_revision") == "reference-json-v2" and _complete_row(row):
                qualification = find_access_entry(
                    access,
                    provider=key[0],
                    model_name=key[1],
                    base_model_id=base_model_id,
                )
                validate_attested_q2_qualification(
                    qualification,
                    repository_root=REPO_ROOT,
                    provider=key[0],
                    model_name=key[1],
                    base_model_id=base_model_id,
                )
            visible_configurations.add(key)
            row_count_by_base[base_model_id] += 1
            releases_by_base[base_model_id].add(release_id)
            if _complete_row(row):
                evaluated_by_base[base_model_id] = True
                if row.get("ranking_eligible") is True:
                    ranked_by_base[base_model_id] = True
                if release_id in WORKFLOW_QUALIFYING_RELEASE_IDS:
                    workflow_evaluated_by_base[base_model_id] = True
                    if row.get("ranking_eligible") is True:
                        workflow_ranked_by_base[base_model_id] = True

    model_rows: list[dict[str, Any]] = []
    for planned in fleet_models:
        base_model_id = str(planned["base_model_id"])
        stages = stages_by_base.get(base_model_id, set())
        highest_stage = max(stages, key=STAGE_ORDER.get) if stages else None
        readiness_state, next_gate, readiness_note = _readiness(
            access_qualified=bool(stages),
            evaluated=evaluated_by_base[base_model_id],
            workflow_qualified=workflow_evaluated_by_base[base_model_id],
        )
        model_rows.append(
            {
                "base_model_id": base_model_id,
                "display_name": str(planned["display_name"]),
                "steward": str(planned["steward"]),
                "family": str(planned["family"]),
                "openness": str(planned["openness"]),
                "modalities": list(planned["modalities"]),
                "size_tier": str(planned["size_tier"]),
                "planned_routes": list(planned["planned_routes"]),
                "access_qualified": bool(stages),
                "qualification_stage": highest_stage,
                "evaluated": evaluated_by_base[base_model_id],
                "ranked": ranked_by_base[base_model_id],
                "workflow_qualified": workflow_evaluated_by_base[base_model_id],
                "workflow_ranked": workflow_ranked_by_base[base_model_id],
                "system_configuration_count": len(configurations_by_base.get(base_model_id, set())),
                "published_release_count": len(releases_by_base.get(base_model_id, set())),
                "published_row_count": row_count_by_base[base_model_id],
                "readiness_state": readiness_state,
                "next_gate": next_gate,
                "readiness_note": readiness_note,
                "access_evidence": sorted(
                    access_evidence_by_base.get(base_model_id, []),
                    key=lambda item: (str(item["date"]), str(item["provider"]), str(item["model"])),
                    reverse=True,
                ),
            }
        )

    return {
        "schema_version": "medphysbench.fleet-status.v2",
        "generated_at": str(fleet["frozen_at"]),
        "fleet_id": str(fleet["fleet_id"]),
        "summary": {
            "planned_base_models": len(fleet_models),
            "access_qualified_base_models": sum(row["access_qualified"] for row in model_rows),
            "evaluated_base_models": sum(row["evaluated"] for row in model_rows),
            "ranked_base_models": sum(row["ranked"] for row in model_rows),
            "workflow_qualified_base_models": sum(row["workflow_qualified"] for row in model_rows),
            "workflow_ranked_base_models": sum(row["workflow_ranked"] for row in model_rows),
            "published_system_configurations": len(visible_configurations),
            "published_release_rows": sum(row_count_by_base.values()),
            "open_planned_models": sum(row["openness"] == "open" for row in model_rows),
            "closed_planned_models": sum(row["openness"] == "closed" for row in model_rows),
            "vision_planned_models": sum("image" in row["modalities"] for row in model_rows),
            "steward_count": len({row["steward"] for row in model_rows}),
        },
        "models": model_rows,
    }


def _readiness(
    *,
    access_qualified: bool,
    evaluated: bool,
    workflow_qualified: bool,
) -> tuple[str, str, str]:
    if workflow_qualified:
        return (
            "workflow_qualified",
            "q3_comparison",
            "A complete current-contract OpenKBP common-harness matrix is published. The next gate is a larger "
            "family-diverse comparison release with external physics review and a matched human baseline.",
        )
    if evaluated:
        return (
            "evaluated",
            "q2_workflow",
            "Complete common-harness evidence exists on another public release. The next gate is the repeated-attempt "
            "OpenKBP real-workflow matrix under one frozen configuration.",
        )
    if access_qualified:
        return (
            "access_qualified",
            "q2_common_harness",
            "Provider or local access has passed Q0 or later. The next gate is a complete, attested common-harness "
            "matrix; partial attempts and native-only rows do not satisfy it.",
        )
    return (
        "route_planned",
        "q0_access",
        "No base-model-bound Q0 access evidence is committed. Planned routes are hypotheses until an exact provider "
        "handle or local artifact revision passes the access probe.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fleet", type=Path, default=DEFAULT_FLEET)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--access", type=Path, default=DEFAULT_ACCESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_fleet_status(
        fleet_path=args.fleet,
        catalog_path=args.catalog,
        access_path=args.access,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
