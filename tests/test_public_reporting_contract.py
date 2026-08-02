from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PAYLOADS = (
    ROOT / "web/public/data/leaderboard.json",
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

    official_ranks: dict[str, list[int]] = defaultdict(list)
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
            official_ranks[group].append(row["rank"])
        else:
            assert row.get("rank") is None

        usage = row.get("token_usage")
        if usage and not usage["available"]:
            assert usage["median_total_tokens"] is None
            assert usage["total_tokens"] is None

    for ranks in official_ranks.values():
        assert sorted(ranks) == list(range(1, len(ranks) + 1))


def test_real_workflow_reporting_preserves_family_and_repeat_contract() -> None:
    payload = json.loads(PUBLIC_PAYLOADS[-1].read_text())

    assert payload["release"]["integrity_profile"] == "pilot"
    assert payload["release"]["family_count"] == 2
    assert payload["release"]["expected_attempts_per_task"] == 3
    assert payload["methodology"]["status"].startswith("public research pilot")
    assert "correlated" in payload["methodology"]["family_dependence"].lower()
