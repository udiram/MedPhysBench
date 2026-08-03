from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_llama31_routes_share_one_base_identity_without_merging_scores() -> None:
    catalog = _load_json(CATALOG_PATH)
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(catalog, list)
    assert isinstance(payload, dict)

    base_model_id = "meta-llama/Llama-3.1-8B-Instruct"
    catalog_routes = {
        (entry["provider"], entry["model_name"])
        for entry in catalog
        if entry["base_model_id"] == base_model_id
    }
    assert catalog_routes == {
        ("groq", "llama-3.1-8b-instant"),
        ("ollama", "llama3.1:8b"),
    }

    rows = [*payload["models"], *payload.get("unranked_models", [])]
    route_metrics = {
        (row["provider"], row["model_name"]): (
            row["safe_success_rate"],
            row["safety_gate_rate"],
        )
        for row in rows
        if (row["provider"], row["model_name"]) in catalog_routes
    }
    assert route_metrics == {
        ("groq", "llama-3.1-8b-instant"): (0.0, 0.2778),
        ("ollama", "llama3.1:8b"): (0.0, 0.3333),
    }


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


def test_legacy_outputs_are_regraded_but_never_promoted_past_integrity_gates() -> None:
    core = _load_json(PUBLIC_DATA / "leaderboard.json")
    real = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(core, dict)
    assert isinstance(real, dict)

    core_rows = [*core["models"], *core.get("unranked_models", [])]
    core_gpt_high = next(row for row in core_rows if row["model_name"] == "gpt-5.6-sol [effort=high]")
    assert core_gpt_high["safe_success_rate"] == 1.0
    assert core_gpt_high["tasks"]
    assert all(isinstance(task.get("passed"), bool) for task in core_gpt_high["tasks"])
    assert core_gpt_high["ranking_eligible"] is False
    assert any(
        issue.startswith("missing_grader_hash:")
        for issue in core_gpt_high["integrity"]["integrity_errors"]
    )

    real_rows = [*real["models"], *real.get("unranked_models", [])]
    real_gpt_high = next(row for row in real_rows if row["model_name"] == "gpt-5.6-sol [effort=high]")
    assert len(real_gpt_high["tasks"]) == real_gpt_high["attempt_count"]
    assert all(isinstance(task.get("passed"), bool) for task in real_gpt_high["tasks"])


def test_real_workflow_drilldown_is_complete_and_redacted() -> None:
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    assert isinstance(payload, dict)
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    assert len(rows) == 31
    v2_rows = [
        row
        for row in rows
        if row.get("harness_revision") == "reference-json-v2"
    ]
    assert {row["model_name"] for row in v2_rows} == {
        "deepseek-r1:1.5b",
        "gemma3:12b-it-q4_K_M",
        "gemma3:4b",
        "llama3.1:8b",
        "llama3.2:3b",
        "mistral-nemo:12b-instruct-2407-q4_K_M",
        "hf.co/EnlistedGhost/Pixtral-12B-2409-GGUF:Q4_K_M",
        "phi4:14b",
        "phi4-mini:3.8b-q4_K_M",
        "qwen2.5:7b-instruct",
        "qwen2.5vl:3b",
        "qwen2.5vl:7b-q4_K_M",
        "qwen3:1.7b",
        "qwen3:8b",
        "qwen3:14b",
        "qwen3-vl:8b-instruct",
        "qwen3.5:4b",
        "hf.co/ShayanCyan/phi4-multimodal-quantisized-gguf:Q4_K_M",
    }
    assert all(row["ranking_eligible"] is True for row in v2_rows)
    assert sorted(row["rank"] for row in v2_rows) == [1, 2, 2, 2, 2, 6, 6, 8, 9, 9, 9, 12, 13, 14, 15, 16, 17, 17]

    for model_name in ("qwen3.5:4b", "gemma3:4b", "qwen2.5vl:3b"):
        immutable_rows = [row for row in rows if row["provider"] == "ollama" and row["model_name"] == model_name]
        assert len(immutable_rows) == 2
        assert {row["harness_revision"] for row in immutable_rows} == {
            "reference-json-v1",
            "reference-json-v2",
        }
        assert len({
            (
                row["provider"],
                row["model_name"],
                row["model_revision"],
                row["harness_revision"],
            )
            for row in immutable_rows
        }) == 2
    deepseek = next(row for row in rows if row["model_name"] == "deepseek-r1:1.5b")
    capability_failures = [task for task in deepseek["tasks"] if task.get("capability_failure")]
    assert len(capability_failures) == 12
    assert {task["model_failure_kind"] for task in capability_failures} == {
        "unsupported_required_modality"
    }
    assert {task["outcome_category"] for task in capability_failures} == {"unavailable"}
    assert deepseek["capability_unavailable_count"] == 12
    assert deepseek["safety_evaluable_attempt_count"] == deepseek["attempt_count"] - 12

    forbidden = {"grades", "raw_response", "trace", "error", "expected", "evidence"}
    for row in rows:
        task_rows = row["tasks"]
        assert len(task_rows) == row["attempt_count"]
        recomputed_safe_success = sum(bool(task["passed"] and task["safe"]) for task in task_rows) / len(task_rows)
        assert round(recomputed_safe_success, 4) == row["safe_success_rate"]
        for task in task_rows:
            assert forbidden.isdisjoint(task)
            assert isinstance(task["output"], dict)
            assert isinstance(task["grader_results"], list)
            assert all("evidence" not in grade for grade in task["grader_results"])
            assert "content" not in task["response_receipt"]
            assert task["outcome_category"] in {
                "safe_success",
                "safe_failure",
                "unsafe",
                "unavailable",
                "inconclusive",
            }
            assert isinstance(task["failed_graders"], list)
            assert isinstance(task["failed_lanes"], list)
            assert task["track"]
            if task["passed"] and task["safe"]:
                assert task["failed_graders"] == []
                assert task["failed_lanes"] == []

    recorded = next(row for row in rows if row["model_name"] == "gpt-5.6-sol [effort=high]")
    assert recorded["execution_surface"] == "recorded_output_import"
    for task in recorded["tasks"]:
        assert task["duration_seconds"] is None
        assert task["token_usage"] == {
            "available": False,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
        assert task["response_receipt"] == {}

    terra = next(row for row in rows if row["model_name"] == "gpt-5.6-terra [effort=high]")
    assert terra["provider"] == "codex-native"
    assert terra["execution_surface"] == "recorded_output_import"
    assert terra["ranking_eligible"] is False
    assert terra["outcome_order_eligible"] is True
    assert terra["safe_success_rate"] == 0.6333
    assert terra["family_cluster_safe_success_ci95"] == [0.6, 0.6667]
    assert terra["safety_gate_rate"] == 1.0
    assert terra["valid_output_rate"] == 1.0
    assert terra["attempt_count"] == terra["expected_attempt_count"] == 30
    assert all(task["response_receipt"] == {} for task in terra["tasks"])


def test_v2_ollama_group_freezes_the_published_sampling_and_adapter_contract() -> None:
    result_root = REPO_ROOT / "results" / "releases" / "public-real-workflows-pilot-v0.6"
    manifests: list[dict[str, object]] = []
    for path in result_root.glob("*/*.json"):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        manifest = payload.get("manifest")
        if not isinstance(manifest, dict):
            continue
        model = manifest.get("model")
        if isinstance(model, dict) and model.get("harness_revision") == "reference-json-v2":
            manifests.append(manifest)

    assert len(manifests) == 18 * 30
    assert {manifest["max_tokens"] for manifest in manifests} == {2048}
    assert {manifest["temperature"] for manifest in manifests} == {0.0}
    assert {manifest["seed"] for manifest in manifests} == {20260731, 20260732, 20260733}
    assert {manifest["adapter_settings_hash"] for manifest in manifests} == {
        "b424732b3b1b2f4672d08e259526d7090484a1df832180809ca3494ea2a5ff75"
    }
    adapter_settings = [manifest["adapter_settings"] for manifest in manifests]
    assert all(isinstance(settings, dict) for settings in adapter_settings)
    assert {settings["context_window"] for settings in adapter_settings} == {4096}
    assert {settings["keep_alive"] for settings in adapter_settings} == {"0"}
    assert {settings["structured_output_mode"] for settings in adapter_settings} == {"json_schema"}


@pytest.mark.parametrize(
    ("release_id", "public_filename"),
    [
        ("public-core-v0.4", "leaderboard.json"),
        ("public-imaging-pilot-v0.4", "imaging_leaderboard.json"),
        ("public-tg263-pilot-v0.5", "tg263_leaderboard.json"),
        ("public-real-workflows-pilot-v0.6", "public-real-workflows-pilot-v0.6.json"),
    ],
)
def test_public_release_copies_are_byte_identical(release_id: str, public_filename: str) -> None:
    paths = [
        REPO_ROOT / "results" / "releases" / release_id / "leaderboard.json",
        REPO_ROOT / "results" / "leaderboards" / f"{release_id}.json",
        PUBLIC_DATA / public_filename,
    ]
    contents = [path.read_bytes() for path in paths]
    assert all(content == contents[0] for content in contents[1:])


def test_receipt_free_groq_batch_remains_visible_but_unranked() -> None:
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    row = next(item for item in rows if item["model_name"] == "qwen/qwen3.6-27b")

    assert row["attempt_count"] == row["expected_attempt_count"] == 30
    assert row["ranking_eligible"] is False
    assert row["outcome_order_eligible"] is False
    assert row.get("outcome_rank") is None
    assert set(row["integrity"]["integrity_errors"]) == {
        "missing_adapter_settings_hash",
        "missing_duration_telemetry",
        "missing_model_response_trace",
        "missing_provider_receipt",
        "missing_usage_telemetry",
    }


def test_admitted_legacy_groq_scores_are_descriptive_but_never_official() -> None:
    payload = _load_json(PUBLIC_DATA / "public-real-workflows-pilot-v0.6.json")
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    admitted = [
        row
        for row in rows
        if row["provider"] == "groq" and row["model_name"] != "qwen/qwen3.6-27b"
    ]

    assert len(admitted) == 4
    assert all(row["ranking_eligible"] is False for row in admitted)
    assert all(row.get("rank") is None for row in admitted)
    assert all(row["outcome_order_eligible"] is True for row in admitted)
    assert all(isinstance(row["outcome_rank"], int) for row in admitted)
    assert {tuple(row["integrity"]["integrity_errors"]) for row in admitted} == {
        ("missing_adapter_settings_hash",)
    }
