from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from medphys_agentbench.item_diagnostics import build_item_diagnostics_artifact

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATH = (
    ROOT / "web" / "public" / "data" / "public-real-workflows-pilot-v0.6-diagnostics.json"
)
LEADERBOARD_PATH = ROOT / "web" / "public" / "data" / "public-real-workflows-pilot-v0.6.json"
RESULTS_PATH = ROOT / "results" / "releases" / "public-real-workflows-pilot-v0.6"


def test_public_item_diagnostics_are_schema_valid_hash_bound_and_reproducible() -> None:
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas" / "item-diagnostics.v1.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(schema).validate(payload)
    assert payload == build_item_diagnostics_artifact(
        RESULTS_PATH,
        LEADERBOARD_PATH,
        repository_root=ROOT,
    )
    assert payload["source"]["result_record_count"] == 1020
    assert len(payload["source"]["leaderboard_sha256"]) == 64
    assert len(payload["source"]["result_manifest_sha256"]) == 64


def test_public_item_diagnostics_preserve_exact_comparison_groups_and_small_panel_missingness() -> None:
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    groups = payload["item_diagnostics"]["groups"]
    by_provider = {
        group["comparison_group"].split("::", 1)[0]: group
        for group in groups
    }

    assert set(by_provider) == {"groq", "ollama"}
    assert by_provider["groq"]["model_count"] == 2
    assert by_provider["groq"]["attempt_count"] == 60
    assert by_provider["groq"]["summary"]["median_task_discrimination"] is None
    assert by_provider["groq"]["summary"]["discrimination_task_count"] == 0
    assert by_provider["ollama"]["model_count"] == 18
    assert by_provider["ollama"]["attempt_count"] == 540
    assert by_provider["ollama"]["summary"]["discrimination_task_count"] == 5
    assert sum(group["model_count"] for group in groups) == 20
    assert all(group["summary"]["governance_status"] == "public_development_diagnostic_only" for group in groups)


def test_public_item_diagnostics_never_embed_model_outputs_or_grader_payloads() -> None:
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        return set()

    assert keys(payload).isdisjoint({"output", "raw_response", "trace", "grader_results", "grading"})
