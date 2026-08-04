from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from medphys_agentbench.public_task_inputs import (
    RUNTIME_KEYS,
    SCHEMA_VERSION,
    build_public_task_input_catalog,
)
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.runner import runtime_task_hash_for_task

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATHS = (
    ROOT / "releases/public_core_v0_4.yaml",
    ROOT / "releases/public_imaging_pilot_v0_4.yaml",
    ROOT / "releases/public_tg263_pilot_v0_5.yaml",
    ROOT / "releases/public_real_workflows_pilot_v0_6.yaml",
)
PUBLIC_PATH = ROOT / "web/public/data/public_task_inputs.json"
LEADERBOARDS = {
    "public-core-v0.4": ROOT / "web/public/data/leaderboard.json",
    "public-imaging-pilot-v0.4": ROOT / "web/public/data/imaging_leaderboard.json",
    "public-tg263-pilot-v0.5": ROOT / "web/public/data/tg263_leaderboard.json",
    "public-real-workflows-pilot-v0.6": ROOT / "web/public/data/public-real-workflows-pilot-v0.6.json",
}


def test_checked_in_catalog_is_deterministic_and_contains_only_runtime_views() -> None:
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    assert payload == build_public_task_input_catalog(RELEASE_PATHS)
    assert payload["schema_version"] == SCHEMA_VERSION

    runtime_schema = json.loads((ROOT / "schemas/runtime-task.v1.schema.json").read_text())
    validator = Draft202012Validator(runtime_schema)
    forbidden_keys = {"grading", "provenance", "development_reference_output", "contamination_tags"}

    for release_entry in payload["releases"]:
        release_path = next(
            path for path in RELEASE_PATHS if load_release(path).release_id == release_entry["release_id"]
        )
        tasks = {task.task_id: task for task in load_release(release_path).load_tasks()}
        assert set(tasks) == {entry["task_id"] for entry in release_entry["tasks"]}
        for entry in release_entry["tasks"]:
            task = tasks[entry["task_id"]]
            runtime_task = entry["runtime_task"]
            assert set(runtime_task) == RUNTIME_KEYS
            assert forbidden_keys.isdisjoint(runtime_task)
            assert runtime_task == json.loads(json.dumps(task.runtime_task().to_dict()))
            assert entry["runtime_task_hash"] == runtime_task_hash_for_task(task)
            assert not list(validator.iter_errors(runtime_task))


def test_every_published_attempt_hash_resolves_to_one_public_input() -> None:
    payload = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    catalog = {
        release["release_id"]: {
            (entry["task_id"], entry["runtime_task_hash"])
            for entry in release["tasks"]
        }
        for release in payload["releases"]
    }
    for release_id, leaderboard_path in LEADERBOARDS.items():
        leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
        rows = [*leaderboard["models"], *leaderboard.get("unranked_models", [])]
        for row in rows:
            for attempt in row.get("tasks", []):
                assert (attempt["task_id"], attempt["runtime_task_hash"]) in catalog[release_id]
