from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAYLOADS = (
    ROOT / "web/public/data/leaderboard.json",
    ROOT / "web/public/data/imaging_leaderboard.json",
    ROOT / "web/public/data/tg263_leaderboard.json",
    ROOT / "web/public/data/public-real-workflows-pilot-v0.6.json",
)


@pytest.mark.parametrize("payload_path", PUBLIC_PAYLOADS)
def test_public_reporting_payload_is_internally_consistent(payload_path: Path) -> None:
    payload = json.loads(payload_path.read_text())
    task_ids = {task["task_id"] for task in payload["tasks"]}
    rows = [*payload["models"], *payload.get("unranked_models", [])]

    assert task_ids
    assert rows

    official_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        attempts = row["tasks"]
        assert row["completed_count"] == len(attempts)
        assert row["attempt_count"] == len(attempts)
        assert {attempt["task_id"] for attempt in attempts} <= task_ids

        labelled_attempts = [attempt for attempt in attempts if isinstance(attempt.get("passed"), bool)]
        if len(labelled_attempts) == len(attempts):
            safe_success = sum(attempt["passed"] is True and attempt["safe"] for attempt in attempts)
            unsafe = sum(not attempt["safe"] for attempt in attempts)
            safe_failure = len(attempts) - safe_success - unsafe
            assert safe_success + safe_failure + unsafe == len(attempts)
            assert row["safe_success_rate"] == pytest.approx(
                safe_success / len(attempts), abs=5e-5
            )

        lower, upper = row.get("safe_success_ci95", row["task_success_ci95"])
        assert 0 <= lower <= row["safe_success_rate"] <= upper <= 1

        if row["ranking_eligible"]:
            assert row["rank"] is not None
            group = (
                row.get("comparison_group")
                or row.get("rank_group")
                or "::".join(
                    [
                        row["provider"],
                        row.get("harness_name", "legacy"),
                        row.get("harness_revision", "legacy"),
                    ]
                )
            )
            assert group
            official_rows[group].append(row)
        else:
            assert row.get("rank") is None

        usage = row.get("token_usage")
        if usage and not usage["available"]:
            assert usage["median_total_tokens"] is None
            assert usage["total_tokens"] is None

    for group_rows in official_rows.values():
        ordered = sorted(
            group_rows,
            key=lambda item: (
                -float(item["safe_success_rate"]),
                -float(item["task_success_rate"]),
                -float(item["safety_gate_rate"]),
                str(item["model_name"]),
            ),
        )
        previous_key = None
        expected_rank = 0
        for position, row in enumerate(ordered, start=1):
            ranking_key = (
                row["safe_success_rate"],
                row["task_success_rate"],
                row["safety_gate_rate"],
            )
            if ranking_key != previous_key:
                expected_rank = position
                previous_key = ranking_key
            assert row["rank"] == expected_rank

    ordered_outcomes = sorted(
        [row for row in rows if row.get("outcome_order_eligible")],
        key=lambda item: (
            -float(item["safe_success_rate"]),
            -float(item["task_success_rate"]),
            -float(item["safety_gate_rate"]),
            str(item["model_name"]),
        ),
    )
    previous_key = None
    expected_rank = 0
    for position, row in enumerate(ordered_outcomes, start=1):
        ranking_key = (
            row["safe_success_rate"],
            row["task_success_rate"],
            row["safety_gate_rate"],
        )
        if ranking_key != previous_key:
            expected_rank = position
            previous_key = ranking_key
        assert row["outcome_rank"] == expected_rank


def test_real_workflow_reporting_preserves_family_and_repeat_contract() -> None:
    payload = json.loads(PUBLIC_PAYLOADS[-1].read_text())

    assert payload["release"]["integrity_profile"] == "pilot"
    assert payload["release"]["family_count"] == 2
    assert payload["release"]["max_family_share"] == 0.5
    assert payload["release"]["expected_attempts_per_task"] == 3
    assert payload["methodology"]["status"].startswith("public research pilot")
    assert "correlated" in payload["methodology"]["family_dependence"].lower()
    assert "competition rank" in payload["methodology"]["ranking_rule"]
    assert "names affect display order only" in payload["methodology"]["ranking_rule"]
    rows = [*payload["models"], *payload.get("unranked_models", [])]
    assert rows
    for row in rows:
        assert all(task.get("family_id") for task in row["tasks"])
