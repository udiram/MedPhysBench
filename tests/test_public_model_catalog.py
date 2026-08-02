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
