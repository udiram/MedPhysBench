#!/usr/bin/env python3
"""Build the public 50-base-model qualification funnel from repository evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from medphys_agentbench.qualification import (
    find_access_entry,
    validate_attested_q2_qualification,
)
from medphys_agentbench.route_qualification import load_route_set

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
def _route_sets_for_fleet(fleet_id: str) -> tuple[Path, ...]:
    selected: list[Path] = []
    for path in sorted((REPO_ROOT / "fleet").glob("*routes*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("fleet_id") == fleet_id:
            selected.append(path)
    return tuple(selected)


DEFAULT_ROUTE_SETS = _route_sets_for_fleet("public-fleet-v1")
WORKFLOW_VIEW_RELEASE_IDS = {"public-real-workflows-pilot-v0.6"}

COMPARABILITY_ONLY_ISSUES = {
    "unranked_singleton_comparison_group",
}
STAGE_ORDER = {"q0": 0, "q1": 1, "q2": 2, "q3": 3}
COMPLETION_REQUIRED_BASE_MODEL_COUNT = 50
COMPLETION_COMPOSITION_MINIMA = {
    "open_base_models": 30,
    "closed_base_models": 15,
    "vision_capable_base_models": 15,
    "steward_count": 5,
}
COMPLETION_REQUIRED_SIZE_TIERS = ("small", "medium", "large")


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


def derive_completion_gate(
    *,
    fleet_models: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    observed_base_model_ids: set[str],
    satisfied_base_model_ids: set[str],
) -> dict[str, Any]:
    """Derive the strict 50-model claim gate from post-attestation evidence."""

    required_ids = [str(row["base_model_id"]) for row in fleet_models]
    if len(required_ids) != COMPLETION_REQUIRED_BASE_MODEL_COUNT or len(required_ids) != len(set(required_ids)):
        raise ValueError(
            "Completion gate derivation requires exactly "
            f"{COMPLETION_REQUIRED_BASE_MODEL_COUNT} unique frozen base-model IDs."
        )
    required_id_set = set(required_ids)
    model_index = {str(row["base_model_id"]): row for row in model_rows}
    if set(model_index) != required_id_set:
        missing = sorted(required_id_set.difference(model_index))
        unexpected = sorted(set(model_index).difference(required_id_set))
        raise ValueError(
            "Completion gate model projection must match the frozen fleet exactly: "
            f"missing={missing}, unexpected={unexpected}"
        )

    unexpected_observed = sorted(observed_base_model_ids.difference(required_id_set))
    if unexpected_observed:
        raise ValueError(
            "Current-contract completion evidence references base models outside the frozen fleet: "
            f"{unexpected_observed}"
        )
    unpublished_observed = sorted(
        base_model_id
        for base_model_id in observed_base_model_ids
        if not isinstance(model_index[base_model_id].get("published_row_count"), int)
        or model_index[base_model_id]["published_row_count"] <= 0
    )
    if unpublished_observed:
        raise ValueError(
            "Current-contract completion evidence requires a published row for every observed base model: "
            f"{unpublished_observed}"
        )
    unexpected_satisfied = sorted(satisfied_base_model_ids.difference(required_id_set))
    if unexpected_satisfied:
        raise ValueError(
            "Completion evidence references base models outside the frozen fleet: "
            f"{unexpected_satisfied}"
        )
    unobserved_satisfied = sorted(satisfied_base_model_ids.difference(observed_base_model_ids))
    if unobserved_satisfied:
        raise ValueError(
            "Completion evidence cannot satisfy base models that were not observed under the current contract: "
            f"{unobserved_satisfied}"
        )

    observed_ids = [base_model_id for base_model_id in required_ids if base_model_id in observed_base_model_ids]
    satisfied_ids = [base_model_id for base_model_id in required_ids if base_model_id in satisfied_base_model_ids]
    remaining_ids = [base_model_id for base_model_id in required_ids if base_model_id not in satisfied_base_model_ids]
    satisfied_models = [model_index[base_model_id] for base_model_id in satisfied_ids]

    observed_composition = {
        "open_base_models": sum(row["openness"] == "open" for row in satisfied_models),
        "closed_base_models": sum(row["openness"] == "closed" for row in satisfied_models),
        "vision_capable_base_models": sum("image" in row["modalities"] for row in satisfied_models),
        "steward_count": len({row["steward"] for row in satisfied_models}),
    }
    composition: dict[str, dict[str, Any]] = {}
    for name, minimum in COMPLETION_COMPOSITION_MINIMA.items():
        observed = observed_composition[name]
        composition[name] = {
            "required": minimum,
            "observed": observed,
            "satisfied": observed >= minimum,
            "remaining": max(minimum - observed, 0),
        }

    observed_size_tier_set = {str(row["size_tier"]) for row in satisfied_models}
    observed_size_tiers = sorted(observed_size_tier_set)
    missing_size_tiers = [
        size_tier for size_tier in COMPLETION_REQUIRED_SIZE_TIERS if size_tier not in observed_size_tier_set
    ]
    composition["size_tiers"] = {
        "required": list(COMPLETION_REQUIRED_SIZE_TIERS),
        "observed": observed_size_tiers,
        "satisfied": not missing_size_tiers,
        "remaining": missing_size_tiers,
    }

    all_composition_minima_satisfied = all(item["satisfied"] for item in composition.values())
    gate_satisfied = not remaining_ids and all_composition_minima_satisfied
    return {
        "required_base_model_count": len(required_ids),
        "observed_base_model_count": len(observed_ids),
        "satisfied_base_model_count": len(satisfied_ids),
        "remaining_base_model_count": len(remaining_ids),
        "required_base_model_ids": required_ids,
        "observed_base_model_ids": observed_ids,
        "satisfied_base_model_ids": satisfied_ids,
        "remaining_base_model_ids": remaining_ids,
        "composition": composition,
        "satisfied": gate_satisfied,
    }


def build_fleet_status(
    *,
    fleet_path: Path = DEFAULT_FLEET,
    catalog_path: Path = DEFAULT_CATALOG,
    access_path: Path = DEFAULT_ACCESS,
    leaderboard_paths: tuple[Path, ...] = DEFAULT_LEADERBOARDS,
    route_set_paths: tuple[Path, ...] = DEFAULT_ROUTE_SETS,
) -> dict[str, Any]:
    fleet = _load_fleet(fleet_path)
    fleet_models = fleet.get("models")
    if not isinstance(fleet_models, list):
        raise ValueError("Fleet manifest models must be a list.")
    target = fleet.get("target_base_model_count")
    if target != len(fleet_models):
        raise ValueError(f"Fleet target declares {target}, but manifest contains {len(fleet_models)} models.")
    if target != COMPLETION_REQUIRED_BASE_MODEL_COUNT:
        raise ValueError(
            "The public completion claim gate requires exactly "
            f"{COMPLETION_REQUIRED_BASE_MODEL_COUNT} frozen base models, not {target}."
        )

    fleet_ids = [str(row["base_model_id"]) for row in fleet_models]
    duplicate_ids = sorted({model_id for model_id in fleet_ids if fleet_ids.count(model_id) > 1})
    if duplicate_ids:
        raise ValueError(f"Fleet manifest has duplicate base model IDs: {duplicate_ids}")
    fleet_index = {str(row["base_model_id"]): row for row in fleet_models}
    route_sets = [load_route_set(path) for path in route_set_paths]
    if not route_sets:
        raise ValueError("At least one frozen executable route set is required.")
    if any(route_set.fleet_id != fleet["fleet_id"] for route_set in route_sets):
        raise ValueError("Every executable route set must bind to the selected frozen fleet.")
    routes = [route for route_set in route_sets for route in route_set.routes]
    unknown_route_models = sorted({route.base_model_id for route in routes}.difference(fleet_index))
    if unknown_route_models:
        raise ValueError(
            "Executable routes reference base models outside the frozen fleet: "
            f"{unknown_route_models}"
        )
    route_ids = [route.route_id for route in routes]
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("Executable route IDs must be unique across frozen route sets.")
    route_modalities_by_configuration: dict[tuple[str, str], set[str]] = defaultdict(set)
    for route in routes:
        route_modalities_by_configuration[(route.provider, route.model)].update(route.modalities)

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
                **(
                    {"access_probe_receipt": entry["access_probe_receipt"]}
                    if "access_probe_receipt" in entry
                    else {}
                ),
                "note": str(entry["note"]),
            }
        )
        if entry.get("status") == "available" and stage in STAGE_ORDER:
            stages_by_base[base_model_id].add(str(stage))

    evaluated_by_base: dict[str, bool] = defaultdict(bool)
    ranked_by_base: dict[str, bool] = defaultdict(bool)
    workflow_view_evaluated_by_base: dict[str, bool] = defaultdict(bool)
    workflow_view_ranked_by_base: dict[str, bool] = defaultdict(bool)
    releases_by_base: dict[str, set[str]] = defaultdict(set)
    row_count_by_base: dict[str, int] = defaultdict(int)
    visible_configurations: set[tuple[str, str]] = set()
    evaluated_modalities_by_base: dict[str, set[str]] = defaultdict(set)
    completion_observed_base_model_ids: set[str] = set()
    completion_satisfied_base_model_ids: set[str] = set()

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
            if row.get("execution_surface") == "common_harness" and _complete_row(row):
                completion_observed_base_model_ids.add(base_model_id)
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
                completion_satisfied_base_model_ids.add(base_model_id)
            visible_configurations.add(key)
            row_count_by_base[base_model_id] += 1
            releases_by_base[base_model_id].add(release_id)
            if _complete_row(row):
                evaluated_by_base[base_model_id] = True
                evaluated_modalities_by_base[base_model_id].update(
                    route_modalities_by_configuration.get(key, set())
                )
                if row.get("ranking_eligible") is True:
                    ranked_by_base[base_model_id] = True
                if release_id in WORKFLOW_VIEW_RELEASE_IDS:
                    workflow_view_evaluated_by_base[base_model_id] = True
                    if row.get("ranking_eligible") is True:
                        workflow_view_ranked_by_base[base_model_id] = True

    model_rows: list[dict[str, Any]] = []
    for planned in fleet_models:
        base_model_id = str(planned["base_model_id"])
        stages = stages_by_base.get(base_model_id, set())
        highest_stage = max(stages, key=STAGE_ORDER.get) if stages else None
        readiness_state, next_gate, readiness_note = _readiness(
            access_qualified=bool(stages),
            evaluated=evaluated_by_base[base_model_id],
            workflow_view_evaluated=workflow_view_evaluated_by_base[base_model_id],
        )
        model_rows.append(
            {
                "base_model_id": base_model_id,
                "display_name": str(planned["display_name"]),
                "steward": str(planned["steward"]),
                "family": str(planned["family"]),
                "openness": str(planned["openness"]),
                "modalities": list(planned["modalities"]),
                "evaluated_modalities": sorted(evaluated_modalities_by_base[base_model_id]),
                "size_tier": str(planned["size_tier"]),
                "planned_routes": list(planned["planned_routes"]),
                "access_qualified": bool(stages),
                "qualification_stage": highest_stage,
                "evaluated": evaluated_by_base[base_model_id],
                "ranked": ranked_by_base[base_model_id],
                "workflow_view_evaluated": workflow_view_evaluated_by_base[base_model_id],
                "workflow_view_ranked": workflow_view_ranked_by_base[base_model_id],
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

    completion_gate = derive_completion_gate(
        fleet_models=fleet_models,
        model_rows=model_rows,
        observed_base_model_ids=completion_observed_base_model_ids,
        satisfied_base_model_ids=completion_satisfied_base_model_ids,
    )
    return {
        "schema_version": "medphysbench.fleet-status.v3",
        "generated_at": str(fleet["frozen_at"]),
        "fleet_id": str(fleet["fleet_id"]),
        "summary": {
            "planned_base_models": len(fleet_models),
            "access_qualified_base_models": sum(row["access_qualified"] for row in model_rows),
            "evaluated_base_models": sum(row["evaluated"] for row in model_rows),
            "ranked_base_models": sum(row["ranked"] for row in model_rows),
            "workflow_view_evaluated_base_models": sum(row["workflow_view_evaluated"] for row in model_rows),
            "workflow_view_ranked_base_models": sum(row["workflow_view_ranked"] for row in model_rows),
            "published_system_configurations": len(visible_configurations),
            "published_release_rows": sum(row_count_by_base.values()),
            "open_planned_models": sum(row["openness"] == "open" for row in model_rows),
            "closed_planned_models": sum(row["openness"] == "closed" for row in model_rows),
            "vision_planned_models": sum("image" in row["modalities"] for row in model_rows),
            "steward_count": len({row["steward"] for row in model_rows}),
            "evaluated_open_base_models": sum(row["evaluated"] and row["openness"] == "open" for row in model_rows),
            "evaluated_closed_base_models": sum(row["evaluated"] and row["openness"] == "closed" for row in model_rows),
            "evaluated_vision_base_models": sum(
                row["evaluated"] and "image" in row["modalities"] for row in model_rows
            ),
            "evaluated_image_route_base_models": sum(
                "image" in row["evaluated_modalities"] for row in model_rows
            ),
            "evaluated_steward_count": len({row["steward"] for row in model_rows if row["evaluated"]}),
            "evaluated_size_tiers": sorted({row["size_tier"] for row in model_rows if row["evaluated"]}),
            "route_set_count": len(route_sets),
            "declared_route_count": len(route_ids),
        },
        "completion_gate": completion_gate,
        "models": model_rows,
    }


def _readiness(
    *,
    access_qualified: bool,
    evaluated: bool,
    workflow_view_evaluated: bool,
) -> tuple[str, str, str]:
    if workflow_view_evaluated:
        return (
            "workflow_view_evaluated",
            "q3_comparison",
            "A complete current-contract OpenKBP one-response workflow-view matrix is published. This is not a "
            "stateful workflow claim; the next gate is a larger family-diverse comparison release with external "
            "physics review and a matched human baseline.",
        )
    if evaluated:
        return (
            "evaluated",
            "q2_workflow_view",
            "Complete common-harness evidence exists on another public release. The next gate is the repeated-attempt "
            "OpenKBP one-response workflow-view matrix under one frozen configuration.",
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fleet", type=Path, default=DEFAULT_FLEET)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--access", type=Path, default=DEFAULT_ACCESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit nonzero and do not write output unless all 50 attested model IDs and composition minima pass.",
    )
    args = parser.parse_args(argv)

    payload = build_fleet_status(
        fleet_path=args.fleet,
        catalog_path=args.catalog,
        access_path=args.access,
    )
    completion_gate = payload["completion_gate"]
    if args.require_complete and not completion_gate["satisfied"]:
        print(
            json.dumps(
                {
                    "error": "fleet_completion_gate_unsatisfied",
                    "required_base_model_count": completion_gate["required_base_model_count"],
                    "satisfied_base_model_count": completion_gate["satisfied_base_model_count"],
                    "remaining_base_model_ids": completion_gate["remaining_base_model_ids"],
                    "composition": completion_gate["composition"],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
