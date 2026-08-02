from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = REPO_ROOT / "web" / "public" / "data"
CATALOG_PATH = PUBLIC_DATA / "model_catalog.json"
LEADERBOARD_PATHS = [
    PUBLIC_DATA / "leaderboard.json",
    PUBLIC_DATA / "imaging_leaderboard.json",
    PUBLIC_DATA / "tg263_leaderboard.json",
    PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json",
]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_model_catalog_covers_every_visible_model_row() -> None:
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    catalog_keys = {
        (str(entry["provider"]), str(entry["model_name"]))
        for entry in catalog
    }
    visible_keys: set[tuple[str, str]] = set()
    for path in LEADERBOARD_PATHS:
        payload = _load_json(path)
        assert isinstance(payload, dict)
        for collection in ("models", "unranked_models"):
            for row in payload.get(collection, []):
                visible_keys.add((str(row["provider"]), str(row["model_name"])))

    missing = sorted(visible_keys - catalog_keys)
    assert not missing, f"public model catalog missing visible rows: {missing}"


def test_public_model_catalog_declares_valid_openness_values() -> None:
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    allowed = {"open", "closed", "unknown"}
    for entry in catalog:
        assert entry["openness"] in allowed


def test_public_model_catalog_distinguishes_system_rows_from_base_models() -> None:
    catalog = _load_json(CATALOG_PATH)
    assert isinstance(catalog, list)
    base_model_ids = {entry["base_model_id"] for entry in catalog}
    assert len(catalog) >= 20
    assert len(base_model_ids) >= 15


def test_real_workflow_release_contains_expected_groq_rows() -> None:
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(payload, dict)
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    groq_models = sorted(row["model_name"] for row in rows if row["provider"] == "groq")
    assert groq_models == [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
    ]


def test_core_release_contains_expected_gpt56_native_rows() -> None:
    payload = _load_json(PUBLIC_DATA / "leaderboard.json")
    assert isinstance(payload, dict)
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    gpt56_rows = sorted(
        row["model_name"]
        for row in rows
        if row["provider"] == "codex-native" and row["model_name"].startswith("gpt-5.6-sol")
    )
    assert gpt56_rows == [
        "gpt-5.6-sol [effort=high]",
        "gpt-5.6-sol [effort=low]",
        "gpt-5.6-sol [effort=max]",
        "gpt-5.6-sol [effort=medium]",
        "gpt-5.6-sol [effort=ultra]",
        "gpt-5.6-sol [effort=xhigh]",
    ]


def test_legacy_aggregates_are_not_mistaken_for_explicit_task_outcomes() -> None:
    core = _load_json(PUBLIC_DATA / "leaderboard.json")
    real = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(core, dict)
    assert isinstance(real, dict)

    core_rows = [*core["models"], *core.get("unranked_models", [])]
    core_gpt_high = next(row for row in core_rows if row["model_name"] == "gpt-5.6-sol [effort=high]")
    assert core_gpt_high["safe_success_rate"] == 1.0
    assert core_gpt_high["tasks"]
    assert all("passed" not in task for task in core_gpt_high["tasks"])

    real_rows = [*real["models"], *real.get("unranked_models", [])]
    real_gpt_high = next(row for row in real_rows if row["model_name"] == "gpt-5.6-sol [effort=high]")
    assert len(real_gpt_high["tasks"]) == real_gpt_high["attempt_count"]
    assert all(isinstance(task.get("passed"), bool) for task in real_gpt_high["tasks"])


def test_real_workflow_drilldown_is_complete_and_redacted() -> None:
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(payload, dict)
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    assert len(rows) == 12

    forbidden = {"output", "grades", "raw_response", "trace", "error", "expected"}
    for row in rows:
        task_rows = row["tasks"]
        assert len(task_rows) == row["attempt_count"]
        recomputed_safe_success = sum(bool(task["passed"] and task["safe"]) for task in task_rows) / len(task_rows)
        assert round(recomputed_safe_success, 4) == row["safe_success_rate"]
        for task in task_rows:
            assert forbidden.isdisjoint(task)
            assert task["outcome_category"] in {"safe_success", "safe_failure", "unsafe", "inconclusive"}
            assert isinstance(task["failed_graders"], list)
            assert isinstance(task["failed_lanes"], list)
            assert task["track"]
            if task["passed"] and task["safe"]:
                assert task["failed_graders"] == []
                assert task["failed_lanes"] == []


def test_real_workflow_public_copies_are_byte_identical() -> None:
    paths = [
        REPO_ROOT / "results" / "releases" / "public-real-workflows-pilot-v0.6" / "leaderboard.json",
        REPO_ROOT / "results" / "leaderboards" / "public-real-workflows-pilot-v0.6.json",
        PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json",
    ]
    contents = [path.read_bytes() for path in paths]
    assert all(content == contents[0] for content in contents[1:])
