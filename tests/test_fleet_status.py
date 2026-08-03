from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from medphys_agentbench.qualification import validate_attested_q2_qualification
from medphys_agentbench.route_qualification import load_route_set
from scripts.build_fleet_status import build_fleet_status, derive_completion_gate

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


def test_every_executable_route_resolves_to_the_frozen_fleet() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    frozen_ids = {entry["base_model_id"] for entry in fleet["models"]}
    route_paths = sorted((ROOT / "fleet").glob("*routes*.yaml"))
    routes = [route for path in route_paths for route in load_route_set(path).routes]

    assert route_paths
    assert routes
    assert all(route.base_model_id in frozen_ids for route in routes)


def test_public_fleet_projection_is_schema_valid_and_reproducible() -> None:
    schema = _load_json(ROOT / "schemas" / "fleet-status.v3.schema.json")
    status = _load_json(STATUS_PATH)
    assert isinstance(schema, dict)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(status)

    rebuilt = build_fleet_status()
    assert status == rebuilt
    assert rebuilt["summary"] == {
        "planned_base_models": 50,
        "access_qualified_base_models": 24,
        "evaluated_base_models": 21,
        "ranked_base_models": 20,
        "workflow_view_evaluated_base_models": 21,
        "workflow_view_ranked_base_models": 20,
        "published_system_configurations": 31,
        "published_release_rows": 52,
        "open_planned_models": 31,
        "closed_planned_models": 19,
        "vision_planned_models": 31,
        "steward_count": 11,
        "evaluated_open_base_models": 21,
        "evaluated_closed_base_models": 0,
        "evaluated_vision_base_models": 7,
        "evaluated_image_route_base_models": 7,
        "evaluated_steward_count": 7,
        "evaluated_size_tiers": ["large", "medium", "small"],
        "route_set_count": 8,
        "declared_route_count": 35,
    }
    gate = rebuilt["completion_gate"]
    assert gate["required_base_model_count"] == 50
    assert gate["observed_base_model_count"] == 21
    assert gate["satisfied_base_model_count"] == 21
    assert gate["remaining_base_model_count"] == 29
    assert len(gate["required_base_model_ids"]) == 50
    assert len(gate["observed_base_model_ids"]) == 21
    assert len(gate["satisfied_base_model_ids"]) == 21
    assert len(gate["remaining_base_model_ids"]) == 29
    assert gate["observed_base_model_ids"] == gate["satisfied_base_model_ids"]
    assert set(gate["satisfied_base_model_ids"]).isdisjoint(gate["remaining_base_model_ids"])
    assert set(gate["satisfied_base_model_ids"]) | set(gate["remaining_base_model_ids"]) == set(
        gate["required_base_model_ids"]
    )
    assert "gpt-5.6-terra" not in gate["observed_base_model_ids"]
    assert "gpt-5.6-terra" not in gate["satisfied_base_model_ids"]
    assert "gpt-5.6-terra" in gate["remaining_base_model_ids"]
    assert "Qwen/Qwen3.6-27B" in gate["satisfied_base_model_ids"]
    assert gate["composition"] == {
        "open_base_models": {"required": 30, "observed": 21, "satisfied": False, "remaining": 9},
        "closed_base_models": {"required": 15, "observed": 0, "satisfied": False, "remaining": 15},
        "vision_capable_base_models": {"required": 15, "observed": 7, "satisfied": False, "remaining": 8},
        "steward_count": {"required": 5, "observed": 7, "satisfied": True, "remaining": 0},
        "size_tiers": {
            "required": ["small", "medium", "large"],
            "observed": ["large", "medium", "small"],
            "satisfied": True,
            "remaining": [],
        },
    }
    assert gate["satisfied"] is False
    assert all("size_tier" in entry for entry in rebuilt["models"])
    assert all("planned_routes" in entry for entry in rebuilt["models"])
    assert all("evaluated_modalities" in entry for entry in rebuilt["models"])
    assert any("groq" in entry["planned_routes"] for entry in rebuilt["models"])
    assert any("ollama" in entry["planned_routes"] for entry in rebuilt["models"])
    assert all(entry["readiness_note"] for entry in rebuilt["models"])
    assert sum(entry["readiness_state"] == "workflow_view_evaluated" for entry in rebuilt["models"]) == 21
    assert sum(entry["readiness_state"] == "route_planned" for entry in rebuilt["models"]) == 26
    terra = next(entry for entry in rebuilt["models"] if entry["base_model_id"] == "gpt-5.6-terra")
    assert terra["readiness_state"] == "access_qualified"
    assert terra["next_gate"] == "q2_common_harness"
    assert terra["access_evidence"][0]["provider"] == "codex-native"
    assert "fresh-context" in terra["access_evidence"][0]["note"]
    assert terra["access_evidence"][0]["qualification_evidence"] is None
    phi = next(
        entry
        for entry in rebuilt["models"]
        if entry["base_model_id"] == "microsoft/Phi-4-multimodal-instruct"
    )
    assert phi["modalities"] == ["text", "image"]
    assert phi["evaluated_modalities"] == ["text"]


def test_v3_schema_remains_backward_compatible_without_completion_gate() -> None:
    schema = _load_json(ROOT / "schemas" / "fleet-status.v3.schema.json")
    status = _load_json(STATUS_PATH)
    assert isinstance(schema, dict)
    assert isinstance(status, dict)
    legacy_v3_projection = dict(status)
    legacy_v3_projection.pop("completion_gate")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(legacy_v3_projection)


def test_synthetic_post_attestation_complete_fleet_satisfies_completion_gate() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    assert isinstance(fleet, dict)
    fleet_models = fleet["models"]
    satisfied_ids = {entry["base_model_id"] for entry in fleet_models}
    model_rows = [
        {
            "base_model_id": entry["base_model_id"],
            "openness": entry["openness"],
            "modalities": entry["modalities"],
            "steward": entry["steward"],
            "size_tier": entry["size_tier"],
            "published_row_count": 1,
        }
        for entry in fleet_models
    ]

    gate = derive_completion_gate(
        fleet_models=fleet_models,
        model_rows=model_rows,
        observed_base_model_ids=satisfied_ids,
        satisfied_base_model_ids=satisfied_ids,
    )

    assert gate["required_base_model_count"] == 50
    assert gate["observed_base_model_count"] == 50
    assert gate["satisfied_base_model_count"] == 50
    assert gate["remaining_base_model_count"] == 0
    assert gate["required_base_model_ids"] == gate["observed_base_model_ids"]
    assert gate["required_base_model_ids"] == gate["satisfied_base_model_ids"]
    assert gate["remaining_base_model_ids"] == []
    assert all(item["satisfied"] for item in gate["composition"].values())
    assert gate["satisfied"] is True


def test_strict_completion_cli_rejects_current_progress_without_writing(tmp_path: Path) -> None:
    output_path = tmp_path / "fleet_status.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_fleet_status.py"),
            "--require-complete",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    error = json.loads(completed.stderr)
    assert error["error"] == "fleet_completion_gate_unsatisfied"
    assert error["required_base_model_count"] == 50
    assert error["satisfied_base_model_count"] == 21
    assert len(error["remaining_base_model_ids"]) == 29
    assert not output_path.exists()


def test_access_ledger_is_schema_valid_and_attested_promotions_resolve() -> None:
    schema = _load_json(ROOT / "schemas" / "access-status.v1.schema.json")
    access = _load_json(ACCESS_PATH)
    assert isinstance(schema, dict)
    assert isinstance(access, list)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(access)

    promoted = [entry for entry in access if entry.get("promotion_basis")]
    assert len(promoted) == 21
    for entry in promoted:
        validate_attested_q2_qualification(
            entry,
            repository_root=ROOT,
            provider=entry["provider"],
            model_name=entry["model"],
            base_model_id=entry["base_model_id"],
        )


def test_access_ledger_contract_rejects_ambiguous_promotion_and_blocked_stage() -> None:
    schema = _load_json(ROOT / "schemas" / "access-status.v1.schema.json")
    access = _load_json(ACCESS_PATH)
    assert isinstance(schema, dict)
    assert isinstance(access, list)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    missing_evidence = json.loads(json.dumps(access))
    promoted = next(entry for entry in missing_evidence if entry.get("promotion_basis"))
    promoted.pop("qualification_evidence")
    with pytest.raises(ValidationError):
        validator.validate(missing_evidence)

    blocked_stage = json.loads(json.dumps(access))
    blocked = next(entry for entry in blocked_stage if entry["status"] == "blocked")
    blocked["qualification_stage"] = "q2"
    with pytest.raises(ValidationError):
        validator.validate(blocked_stage)


def test_catalog_maps_system_configurations_to_unique_frozen_base_models() -> None:
    fleet = yaml.safe_load(FLEET_PATH.read_text(encoding="utf-8"))
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(fleet, dict)
    assert isinstance(catalog, list)
    frozen_ids = {entry["base_model_id"] for entry in fleet["models"]}
    keys = [(entry["provider"], entry["model_name"]) for entry in catalog]

    assert len(keys) == len(set(keys))
    assert all(entry["base_model_id"] in frozen_ids for entry in catalog)
    assert len({entry["base_model_id"] for entry in catalog}) == 24
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
    assert status["completion_gate"]["observed_base_model_count"] == 0
    assert status["completion_gate"]["satisfied_base_model_count"] == 0
    assert status["completion_gate"]["remaining_base_model_count"] == 50
    assert status["completion_gate"]["satisfied"] is False


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


def test_v2_workflow_view_comparison_group_is_now_officially_ranked() -> None:
    status = build_fleet_status()
    deepseek = next(
        row for row in status["models"] if row["base_model_id"] == "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    )
    assert deepseek["qualification_stage"] == "q2"
    assert deepseek["access_qualified"] is True
    assert deepseek["evaluated"] is True
    assert deepseek["ranked"] is True
    assert deepseek["workflow_view_evaluated"] is True
    assert deepseek["workflow_view_ranked"] is True


def test_qwen25vl_7b_is_exactly_bound_through_access_and_workflow_view_results() -> None:
    status = build_fleet_status()
    qwen = next(row for row in status["models"] if row["base_model_id"] == "Qwen/Qwen2.5-VL-7B-Instruct")

    assert qwen["qualification_stage"] == "q2"
    assert qwen["access_qualified"] is True
    assert qwen["evaluated"] is True
    assert qwen["ranked"] is True
    assert qwen["workflow_view_evaluated"] is True
    assert qwen["workflow_view_ranked"] is True
    assert qwen["published_row_count"] == 1


def test_pixtral_community_quantization_is_attested_and_ranked() -> None:
    status = build_fleet_status()
    pixtral = next(row for row in status["models"] if row["base_model_id"] == "mistralai/Pixtral-12B-2409")
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    catalog_row = next(row for row in catalog if row["base_model_id"] == "mistralai/Pixtral-12B-2409")
    provenance = catalog_row["artifact_provenance"]

    assert pixtral["qualification_stage"] == "q2"
    assert pixtral["access_qualified"] is True
    assert pixtral["evaluated"] is True
    assert pixtral["ranked"] is True
    assert pixtral["workflow_view_evaluated"] is True
    assert pixtral["workflow_view_ranked"] is True
    assert pixtral["published_row_count"] == 1
    assert provenance["kind"] == "community_quantization"
    assert provenance["source_url"] == (
        "https://huggingface.co/EnlistedGhost/Pixtral-12B-2409-GGUF/tree/f4b659266080c08cbceb36f8a1a387ced7a989a7"
    )
    assert provenance["source_revision"] == "f4b659266080c08cbceb36f8a1a387ced7a989a7"
    assert {(artifact["role"], artifact["sha256"], artifact["bytes"]) for artifact in provenance["artifacts"]} == {
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


def test_phi4_multimodal_community_quantization_is_attested_but_text_only() -> None:
    status = build_fleet_status()
    base_model_id = "microsoft/Phi-4-multimodal-instruct"
    phi = next(row for row in status["models"] if row["base_model_id"] == base_model_id)
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    catalog_row = next(row for row in catalog if row["base_model_id"] == base_model_id)
    provenance = catalog_row["artifact_provenance"]

    assert phi["workflow_view_ranked"] is True
    assert phi["access_evidence"][0]["surface"] == "local_ollama_text_only_community_quantization"
    assert phi["access_evidence"][0]["qualification_evidence"]["submission_id"] == (
        "phi4-multimodal-3-8b-community-q4km-openkb-v0.6-20260803"
    )
    assert provenance["kind"] == "community_quantization"
    assert provenance["source_revision"] == "cbcd2c4e48d79cad6de1ae8e05757c02f9f6400f"
    assert provenance["artifacts"] == [
        {
            "role": "model_weights",
            "sha256": "fb8897a6038bb0bf04194d111a07a79f58e54f7e5d781b712140b73a5ff056cc",
            "bytes": 2491874752,
        }
    ]
    assert "no vision projector" in catalog_row["notes"]


def test_workflow_view_counts_only_common_harness_openkbp_release() -> None:
    status = build_fleet_status()
    assert status["summary"]["workflow_view_evaluated_base_models"] == 21
    assert status["summary"]["workflow_view_ranked_base_models"] == 20

    gpt = next(row for row in status["models"] if row["base_model_id"] == "gpt-5.6-sol")
    assert gpt["evaluated"] is False
    assert gpt["workflow_view_evaluated"] is False
    assert gpt["published_row_count"] > 0

    planned_only = next(row for row in status["models"] if row["base_model_id"] == "Qwen/Qwen3-32B")
    assert planned_only["evaluated"] is False
    assert planned_only["workflow_view_evaluated"] is False
