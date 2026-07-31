from medphys_agentbench.reporting import _nonnegative_int, _usage_summary


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


def test_usage_summary_never_coerces_invalid_values_to_zero() -> None:
    summary = _usage_summary([{"raw_response": {"usage": {"prompt_eval_count": None, "eval_count": -1}}}])

    assert summary["available"] is False
    assert summary["total_input_tokens"] is None
    assert summary["total_output_tokens"] is None
    assert summary["median_total_tokens"] is None
    assert _nonnegative_int(True) is None
    assert _nonnegative_int(1.5) is None
