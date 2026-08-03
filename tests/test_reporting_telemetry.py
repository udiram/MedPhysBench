import pytest

from medphys_agentbench.reporting import (
    _common_harness_receipt_errors,
    _family_cluster_bootstrap_interval,
    _nonnegative_int,
    _pass_at_k,
    _pass_power_k,
    _reliability_summary,
    _task_usage,
    _usage_summary,
)


def test_usage_summary_preserves_missing_telemetry() -> None:
    summary = _usage_summary(
        [
            {"raw_response": {"usage": {"prompt_eval_count": 100, "eval_count": 25}}},
            {"raw_response": {}, "trace": []},
        ]
    )

    assert summary == {
        "available": True,
        "complete": False,
        "observed_attempts": 1,
        "expected_attempts": 2,
        "observed_input_attempts": 1,
        "observed_output_attempts": 1,
        "observed_total_attempts": 1,
        "input_complete": False,
        "output_complete": False,
        "total_complete": False,
        "campaign_attempts": 2,
        "capability_unavailable_attempts": 0,
        "provider_output_contract_failure_attempts": 0,
        "usage_unavailable_attempts": 0,
        "total_input_tokens": 100,
        "total_output_tokens": 25,
        "total_tokens": 125,
        "median_input_tokens": 100,
        "median_output_tokens": 25,
        "median_total_tokens": 125,
    }


def test_usage_summary_accepts_openai_style_counts_from_trace() -> None:
    summary = _usage_summary(
        [
            {
                "trace": [
                    {
                        "event": "model_response",
                        "usage": {
                            "prompt_tokens": 12,
                            "completion_tokens": 8,
                            "total_tokens": 20,
                        },
                    }
                ]
            }
        ]
    )

    assert summary["complete"] is True
    assert summary["median_total_tokens"] == 20


def test_usage_summary_accepts_total_only_telemetry_for_total_token_frontier() -> None:
    summary = _usage_summary(
        [
            {"raw_response": {"usage": {"total_tokens": 123}}},
            {"raw_response": {"usage": {"total_tokens": 177}}},
        ]
    )

    assert summary["available"] is True
    assert summary["complete"] is True
    assert summary["observed_attempts"] == 2
    assert summary["observed_total_attempts"] == 2
    assert summary["total_complete"] is True
    assert summary["input_complete"] is False
    assert summary["output_complete"] is False
    assert summary["median_total_tokens"] == 150
    assert summary["median_input_tokens"] is None
    assert summary["median_output_tokens"] is None


def test_total_only_telemetry_satisfies_receipt_without_inventing_splits() -> None:
    item = {
        "trace": [{"event": "model_response"}],
        "raw_response": {"usage": {"total_tokens": 123}},
        "duration_seconds": 1.25,
    }

    assert _common_harness_receipt_errors(item=item) == []
    assert _task_usage(item) == {
        "available": True,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": 123,
    }


def test_usage_summary_excludes_no_call_capability_failures_from_coverage() -> None:
    summary = _usage_summary(
        [
            {"raw_response": {"usage": {"prompt_eval_count": 12, "eval_count": 8}}},
            {
                "capability_failure": True,
                "model_failure_kind": "unsupported_required_modality",
                "raw_response": {},
            },
        ]
    )

    assert summary["complete"] is True
    assert summary["observed_attempts"] == 1
    assert summary["expected_attempts"] == 1
    assert summary["campaign_attempts"] == 2
    assert summary["capability_unavailable_attempts"] == 1


def test_usage_summary_never_coerces_invalid_values_to_zero() -> None:
    summary = _usage_summary([{"raw_response": {"usage": {"prompt_eval_count": None, "eval_count": -1}}}])

    assert summary["available"] is False
    assert summary["total_input_tokens"] is None
    assert summary["total_output_tokens"] is None
    assert summary["median_total_tokens"] is None
    assert _nonnegative_int(True) is None
    assert _nonnegative_int(1.5) is None


def test_pass_at_k_and_pass_power_k_are_combinatorial_not_naive() -> None:
    attempts = [True, False, False]

    assert _pass_at_k(attempts, 1) == pytest.approx(1 / 3)
    assert _pass_at_k(attempts, 2) == pytest.approx(2 / 3)
    assert _pass_at_k(attempts, 3) == 1.0
    assert _pass_power_k(attempts, 1) == pytest.approx(1 / 3)
    assert _pass_power_k(attempts, 2) == 0.0


def test_reliability_summary_reports_consistency_and_variance() -> None:
    summary = _reliability_summary(
        {
            "always": [True, True, True],
            "mixed": [True, False, False],
        }
    )

    assert summary["pass_at_k"]["1"] == pytest.approx(0.6667)
    assert summary["pass_power_k"]["3"] == pytest.approx(0.5)
    assert summary["all_attempts_agree_rate"] == 0.5
    assert summary["mean_within_task_variance"] == pytest.approx(0.1111)


def test_family_cluster_bootstrap_is_deterministic_and_family_aware() -> None:
    families = {
        "case-a": [True, True, True, True],
        "case-b": [False, False],
        "case-c": [True, False],
    }

    first = _family_cluster_bootstrap_interval(families, samples=500)
    second = _family_cluster_bootstrap_interval(families, samples=500)

    assert first == second
    assert 0.0 <= first[0] <= first[1] <= 1.0
