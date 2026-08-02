from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scripts.build_fleet_status import build_fleet_status

ROOT = Path(__file__).resolve().parents[1]
FLEET_PATH = ROOT / "fleet" / "public_fleet_v1.yaml"
STATUS_PATH = ROOT / "web" / "public" / "data" / "fleet_status.json"
CATALOG_PATH = ROOT / "web" / "public" / "data" / "model_catalog.json"
ACCESS_PATH = ROOT / "web" / "public" / "data" / "access_status.json"
REAL_PATH = ROOT / "web" / "public" / "data" / "public-real-workflows-pilot-v0.6.json"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_fleet_meets_preregistered_composition() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    assert isinstance(fleet, dict)
    models = fleet["models"]
    ids = [entry["base_model_id"] for entry in models]

    assert fleet["target_base_model_count"] == 50
    assert len(models) == 50
    assert len(ids) == len(set(ids))
    assert sum(entry["openness"] == "open" for entry in models) >= 30
    assert sum(entry["openness"] == "closed" for entry in models) >= 15
    assert sum("image" in entry["modalities"] for entry in models) >= 15
    assert len({entry["steward"] for entry in models}) >= 5
    assert {entry["size_tier"] for entry in models} >= {"small", "medium", "large"}


def test_public_fleet_projection_is_schema_valid_and_reproducible() -> None:
    schema = _load_json(ROOT / "schemas" / "fleet-status.v1.schema.json")
    status = _load_json(STATUS_PATH)
    assert isinstance(schema, dict)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(status)

    rebuilt = build_fleet_status()
    assert status == rebuilt
    assert rebuilt["summary"] == {
        "planned_base_models": 50,
        "access_qualified_base_models": 18,
        "evaluated_base_models": 16,
        "ranked_base_models": 16,
        "workflow_qualified_base_models": 16,
        "workflow_ranked_base_models": 16,
        "published_system_configurations": 23,
        "published_release_rows": 38,
        "open_planned_models": 31,
        "closed_planned_models": 19,
        "vision_planned_models": 31,
        "steward_count": 11,
    }


def test_catalog_maps_system_configurations_to_unique_frozen_base_models() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(fleet, dict)
    assert isinstance(catalog, list)
    frozen_ids = {entry["base_model_id"] for entry in fleet["models"]}
    keys = [(entry["provider"], entry["model_name"]) for entry in catalog]

    assert len(keys) == len(set(keys))
    assert all(entry["base_model_id"] in frozen_ids for entry in catalog)
    assert len({entry["base_model_id"] for entry in catalog}) == 18
    assert sum(entry["base_model_id"] == "gpt-5.6-sol" for entry in catalog) == 6


def test_incomplete_campaign_cannot_increment_evaluated_or_ranked_counts(tmp_path: Path) -> None:
    real = _load_json(REAL_PATH)
    assert isinstance(real, dict)
    row = dict(real["models"][0])
    row["completed_count"] = row["expected_attempt_count"] - 1
    row["integrity"] = dict(row["integrity"])
    row["integrity"]["observed_attempt_keys"] = row["expected_attempt_count"] - 1
    row["integrity"]["missing_attempt_keys"] = 1
    fixture = {
        "release": real["release"],
        "models": [row],
        "unranked_models": [],
    }
    fixture_path = tmp_path / "incomplete.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    status = build_fleet_status(
        fleet_path=FLEET_PATH,
        catalog_path=CATALOG_PATH,
        access_path=ACCESS_PATH,
        leaderboard_paths=(fixture_path,),
    )

    assert status["summary"]["published_release_rows"] == 1
    assert status["summary"]["evaluated_base_models"] == 0
    assert status["summary"]["ranked_base_models"] == 0


def test_v2_workflow_comparison_group_is_now_officially_ranked() -> None:
    status = build_fleet_status()
    deepseek = next(
        row
        for row in status["models"]
        if row["base_model_id"] == "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    )
    assert deepseek["qualification_stage"] == "q2"
    assert deepseek["access_qualified"] is True
    assert deepseek["evaluated"] is True
    assert deepseek["ranked"] is True
    assert deepseek["workflow_qualified"] is True
    assert deepseek["workflow_ranked"] is True


def test_qwen25vl_7b_is_exactly_bound_through_access_and_workflow_results() -> None:
    status = build_fleet_status()
    qwen = next(
        row
        for row in status["models"]
        if row["base_model_id"] == "Qwen/Qwen2.5-VL-7B-Instruct"
    )

    assert qwen["qualification_stage"] == "q2"
    assert qwen["access_qualified"] is True
    assert qwen["evaluated"] is True
    assert qwen["ranked"] is True
    assert qwen["workflow_qualified"] is True
    assert qwen["workflow_ranked"] is True
    assert qwen["published_row_count"] == 1


def test_workflow_qualified_counts_only_common_harness_real_workflow_release() -> None:
    status = build_fleet_status()
    assert status["summary"]["workflow_qualified_base_models"] == 16
    assert status["summary"]["workflow_ranked_base_models"] == 16

    gpt = next(
        row
        for row in status["models"]
        if row["base_model_id"] == "gpt-5.6-sol"
    )
    assert gpt["evaluated"] is False
    assert gpt["workflow_qualified"] is False
    assert gpt["published_row_count"] > 0

    planned_only = next(
        row
        for row in status["models"]
        if row["base_model_id"] == "Qwen/Qwen3-32B"
    )
    assert planned_only["evaluated"] is False
    assert planned_only["workflow_qualified"] is False
