from __future__ import annotations

import json
from pathlib import Path

import pytest
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
    schema = _load_json(ROOT / "schemas" / "fleet-status.v2.schema.json")
    status = _load_json(STATUS_PATH)
    assert isinstance(schema, dict)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(status)

    rebuilt = build_fleet_status()
    assert status == rebuilt
    assert rebuilt["summary"] == {
        "planned_base_models": 50,
        "access_qualified_base_models": 23,
        "evaluated_base_models": 20,
        "ranked_base_models": 20,
        "workflow_qualified_base_models": 20,
        "workflow_ranked_base_models": 20,
        "published_system_configurations": 29,
        "published_release_rows": 44,
        "open_planned_models": 31,
        "closed_planned_models": 19,
        "vision_planned_models": 31,
        "steward_count": 11,
    }
    assert all("size_tier" in entry for entry in rebuilt["models"])
    assert all("planned_routes" in entry for entry in rebuilt["models"])
    assert any("groq" in entry["planned_routes"] for entry in rebuilt["models"])
    assert any("ollama" in entry["planned_routes"] for entry in rebuilt["models"])
    assert all(entry["readiness_note"] for entry in rebuilt["models"])
    assert sum(entry["readiness_state"] == "workflow_qualified" for entry in rebuilt["models"]) == 20
    assert sum(entry["readiness_state"] == "route_planned" for entry in rebuilt["models"]) == 27
    terra = next(entry for entry in rebuilt["models"] if entry["base_model_id"] == "gpt-5.6-terra")
    assert terra["readiness_state"] == "access_qualified"
    assert terra["next_gate"] == "q2_common_harness"
    assert terra["access_evidence"][0]["provider"] == "codex-native"
    assert "fresh-context" in terra["access_evidence"][0]["note"]


def test_catalog_maps_system_configurations_to_unique_frozen_base_models() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(fleet, dict)
    assert isinstance(catalog, list)
    frozen_ids = {entry["base_model_id"] for entry in fleet["models"]}
    keys = [(entry["provider"], entry["model_name"]) for entry in catalog]

    assert len(keys) == len(set(keys))
    assert all(entry["base_model_id"] in frozen_ids for entry in catalog)
    assert len({entry["base_model_id"] for entry in catalog}) == 23
    assert sum(entry["base_model_id"] == "gpt-5.6-sol" for entry in catalog) == 6
    assert sum(entry["base_model_id"] == "gpt-5.6-terra" for entry in catalog) == 1


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


@pytest.mark.parametrize("field", ["promotion_basis", "qualification_evidence"])
def test_complete_v2_row_requires_attested_qualification_evidence(
    tmp_path: Path,
    field: str,
) -> None:
    access = _load_json(ACCESS_PATH)
    assert isinstance(access, list)
    qwen = next(entry for entry in access if entry.get("model") == "qwen3:14b")
    qwen.pop(field)
    access_path = tmp_path / "access-status.json"
    access_path.write_text(json.dumps(access), encoding="utf-8")

    with pytest.raises(ValueError, match="promotion_basis|qualification_evidence"):
        build_fleet_status(access_path=access_path)


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


def test_pixtral_community_quantization_is_attested_and_ranked() -> None:
    status = build_fleet_status()
    pixtral = next(
        row
        for row in status["models"]
        if row["base_model_id"] == "mistralai/Pixtral-12B-2409"
    )
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    catalog_row = next(
        row
        for row in catalog
        if row["base_model_id"] == "mistralai/Pixtral-12B-2409"
    )
    provenance = catalog_row["artifact_provenance"]

    assert pixtral["qualification_stage"] == "q2"
    assert pixtral["access_qualified"] is True
    assert pixtral["evaluated"] is True
    assert pixtral["ranked"] is True
    assert pixtral["workflow_qualified"] is True
    assert pixtral["workflow_ranked"] is True
    assert pixtral["published_row_count"] == 1
    assert provenance["kind"] == "community_quantization"
    assert provenance["source_url"] == (
        "https://huggingface.co/EnlistedGhost/Pixtral-12B-2409-GGUF/tree/"
        "f4b659266080c08cbceb36f8a1a387ced7a989a7"
    )
    assert provenance["source_revision"] == "f4b659266080c08cbceb36f8a1a387ced7a989a7"
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


def test_workflow_qualified_counts_only_common_harness_real_workflow_release() -> None:
    status = build_fleet_status()
    assert status["summary"]["workflow_qualified_base_models"] == 20
    assert status["summary"]["workflow_ranked_base_models"] == 20

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
