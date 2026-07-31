from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from medphys_agentbench.analytics import build_leaderboard_analytics


def _result(
    model_name: str,
    *,
    run_id: str,
    score: float,
    passed: bool,
    safe: bool,
    duration_seconds: float | None = 1.0,
    usage: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    comparable: bool = True,
) -> dict[str, Any]:
    raw_response: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    if usage is not None:
        raw_response["usage"] = usage
    if latency_ms is not None:
        raw_response["latency_ms"] = latency_ms
    if not comparable:
        trace.append({"event": "recorded_output_import", "comparable_to_api_runs": False})
    payload: dict[str, Any] = {
        "status": "completed",
        "attempt_index": int(run_id.rsplit("-", 1)[-1]),
        "manifest": {
            "run_id": run_id,
            "task_id": f"task-{run_id}",
            "model": {
                "provider": "test-provider",
                "model_name": model_name,
                "model_revision": f"{model_name}@1",
                "harness_name": "test-harness",
                "harness_revision": "1",
            },
        },
        "passed": passed,
        "safe": safe,
        "score": score,
        "trace": trace,
        "raw_response": raw_response,
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    return payload


def _leaderboard_row(model_name: str, *, ranking_eligible: bool = True) -> dict[str, Any]:
    return {
        "provider": "test-provider",
        "model_name": model_name,
        "model_revision": f"{model_name}@1",
        "harness_name": "test-harness",
        "harness_revision": "1",
        "rank": 1 if ranking_eligible else None,
        "ranking_eligible": ranking_eligible,
        "attempt_count": 1,
        "task_success_rate": 1.0,
        "safe_success_rate": 1.0,
    }


def test_analytics_preserves_missing_usage_and_aggregates_observed_values() -> None:
    records = [
        _result(
            "model-a",
            run_id="run-0",
            score=1.0,
            passed=True,
            safe=True,
            duration_seconds=2.0,
            latency_ms=500.0,
            usage={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "output_tokens_details": {"reasoning_tokens": 2},
            },
        ),
        _result(
            "model-a",
            run_id="run-1",
            score=0.0,
            passed=False,
            safe=True,
            duration_seconds=4.0,
        ),
    ]

    analytics = build_leaderboard_analytics(records, release_id="test-release")
    row = analytics["models"][0]

    assert analytics["release_id"] == "test-release"
    assert row["tokens"]["total_tokens"] == {
        "sample_count": 1,
        "missing_count": 1,
        "sum": 15,
        "mean": 15.0,
        "median": 15.0,
        "minimum": 15,
        "maximum": 15,
        "mean_ci95": None,
    }
    assert row["tokens"]["reasoning_tokens"]["sum"] == 2
    assert row["timing"]["wall_time_seconds"]["mean"] == 3.0
    assert row["timing"]["latency_seconds"]["sample_count"] == 1
    assert row["throughput"]["output_tokens_per_second"]["value"] == 10.0
    assert row["outcomes"]["score"]["mean"] == 0.5
    assert row["outcomes"]["score"]["mean_ci95"] == [0.0, 1.0]
    assert row["outcomes"]["safe_task_success"]["success_count"] == 1
    assert row["outcomes"]["safe_task_success"]["rate"] == 0.5
    assert row["outcomes"]["safe_task_success"]["ci95"] is not None
    assert row["missing_telemetry"]["any"] is True
    assert row["missing_telemetry"]["missing_counts"]["total_tokens"] == 1


def test_ollama_aliases_derive_total_tokens_and_latency_without_zero_imputation() -> None:
    record = _result(
        "ollama-shape",
        run_id="run-0",
        score=1.0,
        passed=True,
        safe=True,
        duration_seconds=2.1,
        usage={"prompt_eval_count": 100, "eval_count": 20, "total_duration": 2_000_000_000},
    )

    row = build_leaderboard_analytics([record])["models"][0]

    assert row["tokens"]["input_tokens"]["sum"] == 100
    assert row["tokens"]["output_tokens"]["sum"] == 20
    assert row["tokens"]["total_tokens"]["sum"] == 120
    assert row["tokens"]["reasoning_tokens"]["sum"] is None
    assert row["tokens"]["reasoning_tokens"]["missing_count"] == 1
    assert row["timing"]["latency_seconds"]["mean"] == 2.0
    assert row["throughput"]["output_tokens_per_second"]["value"] == 10.0


def test_pareto_frontiers_exclude_ineligible_models_and_keep_tradeoffs() -> None:
    records = [
        _result(
            "accurate",
            run_id="run-0",
            score=1.0,
            passed=True,
            safe=True,
            duration_seconds=2.0,
            latency_ms=2_000,
            usage={"input_tokens": 10, "output_tokens": 20},
        ),
        _result(
            "dominated",
            run_id="run-0",
            score=0.5,
            passed=False,
            safe=True,
            duration_seconds=3.0,
            latency_ms=3_000,
            usage={"input_tokens": 10, "output_tokens": 15},
        ),
        _result(
            "fast-tradeoff",
            run_id="run-0",
            score=0.8,
            passed=True,
            safe=True,
            duration_seconds=1.0,
            latency_ms=1_000,
            usage={"input_tokens": 10, "output_tokens": 30},
        ),
        _result(
            "native-import",
            run_id="run-0",
            score=1.0,
            passed=True,
            safe=True,
            duration_seconds=0.001,
            latency_ms=1,
            usage={"input_tokens": 1, "output_tokens": 100},
            comparable=False,
        ),
        _result(
            "unlisted",
            run_id="run-0",
            score=1.0,
            passed=True,
            safe=True,
            duration_seconds=0.5,
            latency_ms=500,
            usage={"input_tokens": 1, "output_tokens": 100},
        ),
    ]
    leaderboard = {
        "release": {"release_id": "pareto-release"},
        "models": [
            _leaderboard_row("accurate"),
            _leaderboard_row("dominated"),
            _leaderboard_row("fast-tradeoff"),
        ],
        "unranked_models": [_leaderboard_row("native-import", ranking_eligible=False)],
    }

    analytics = build_leaderboard_analytics(records, leaderboard=leaderboard)
    rows = {row["model"]["model_name"]: row for row in analytics["models"]}

    assert rows["accurate"]["pareto"]["quality_wall_time"] == {"eligible": True, "efficient": True}
    assert rows["fast-tradeoff"]["pareto"]["quality_wall_time"] == {"eligible": True, "efficient": True}
    assert rows["dominated"]["pareto"]["quality_wall_time"] == {"eligible": True, "efficient": False}
    assert rows["native-import"]["pareto"]["quality_wall_time"] == {"eligible": False, "efficient": False}
    assert rows["native-import"]["pareto"]["quality_latency"] == {"eligible": False, "efficient": False}
    assert rows["unlisted"]["leaderboard"]["matched"] is False
    assert rows["unlisted"]["pareto"]["quality_wall_time"] == {"eligible": False, "efficient": False}
    assert analytics["pareto_frontiers"]["quality_throughput"]["eligible_model_count"] == 3


def test_aggregation_is_independent_of_input_order() -> None:
    records = [
        _result(
            "stable",
            run_id=f"run-{index}",
            score=value,
            passed=value > 0,
            safe=True,
            duration_seconds=1.0 + index,
            latency_ms=1_000 + index,
            usage={"input_tokens": index + 1, "output_tokens": index + 2},
        )
        for index, value in enumerate((0.0, 0.5, 1.0))
    ]

    assert build_leaderboard_analytics(records) == build_leaderboard_analytics(reversed(records))


def test_build_script_emits_valid_analytics_json(tmp_path: Path) -> None:
    model_dir = tmp_path / "model-a"
    model_dir.mkdir()
    record = _result(
        "script-model",
        run_id="run-0",
        score=1.0,
        passed=True,
        safe=True,
        usage={"input_tokens": 2, "output_tokens": 3},
        latency_ms=500,
    )
    (model_dir / "attempt.json").write_text(json.dumps(record), encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": "src"}

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_leaderboard_analytics.py",
            str(tmp_path),
            "--release-id",
            "script-release",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema_version"] == "medphysbench.analytics.v1"
    assert payload["release_id"] == "script-release"
    assert payload["source"]["result_record_count"] == 1
