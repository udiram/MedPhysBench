"""Deterministic analytics for benchmark result and leaderboard artifacts.

The result v1 contract deliberately leaves provider telemetry in ``raw_response``
and ``trace``.  This module normalizes observed values without treating absent
telemetry as zero, then builds explicitly eligibility-gated Pareto frontiers.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .json_utils import stable_hash

_Z_95 = 1.959963984540054
_MODEL_FIELDS = (
    "provider",
    "model_name",
    "model_revision",
    "harness_name",
    "harness_revision",
)


def load_result_records(release_results_dir: str | Path) -> list[dict[str, Any]]:
    """Load result records from ``<release>/<model>/*.json`` in stable order."""

    root = Path(release_results_dir)
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Result artifact must contain a JSON object: {path}")
        records.append(payload)
    return records


def build_leaderboard_analytics(
    result_records: Iterable[Mapping[str, Any]],
    *,
    leaderboard: Mapping[str, Any] | None = None,
    release_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate immutable attempt records into a deterministic analytics object.

    ``leaderboard`` is optional.  When supplied, its ``ranking_eligible`` flag is
    honored by the Pareto analysis so non-comparable pilot surfaces cannot look
    efficient merely because their import step was fast.
    """

    records = [dict(record) for record in result_records]
    leaderboard_rows = _leaderboard_rows(leaderboard)
    resolved_release_id = release_id or _leaderboard_release_id(leaderboard)

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        descriptor = _model_descriptor(record)
        grouped[tuple(descriptor[field] for field in _MODEL_FIELDS)].append(record)

    model_rows: list[dict[str, Any]] = []
    for descriptor_key in sorted(grouped):
        descriptor = dict(zip(_MODEL_FIELDS, descriptor_key, strict=True))
        attempts = sorted(grouped[descriptor_key], key=_attempt_sort_key)
        leaderboard_row = leaderboard_rows.get(descriptor_key)
        model_rows.append(
            _aggregate_model(
                descriptor,
                attempts,
                leaderboard_row,
                leaderboard_attached=leaderboard is not None,
            )
        )

    frontiers = {
        "quality_wall_time": _mark_pareto_frontier(
            model_rows,
            frontier_name="quality_wall_time",
            metrics=(
                ("safe_task_success_rate", "max"),
                ("mean_score", "max"),
                ("mean_wall_time_seconds", "min"),
            ),
            eligibility=_quality_wall_time_eligible,
        ),
        "quality_latency": _mark_pareto_frontier(
            model_rows,
            frontier_name="quality_latency",
            metrics=(
                ("safe_task_success_rate", "max"),
                ("mean_score", "max"),
                ("mean_latency_seconds", "min"),
            ),
            eligibility=_quality_latency_eligible,
        ),
        "quality_throughput": _mark_pareto_frontier(
            model_rows,
            frontier_name="quality_throughput",
            metrics=(
                ("safe_task_success_rate", "max"),
                ("mean_score", "max"),
                ("output_tokens_per_second", "max"),
            ),
            eligibility=_quality_throughput_eligible,
        ),
    }

    return {
        "schema_version": "medphysbench.analytics.v1",
        "release_id": resolved_release_id,
        "source": {
            "result_record_count": len(records),
            "model_count": len(model_rows),
            "leaderboard_attached": leaderboard is not None,
        },
        "models": model_rows,
        "pareto_frontiers": frontiers,
        "methodology": {
            "missing_usage": "Missing token, latency, or throughput telemetry is null and is never imputed as zero.",
            "token_semantics": (
                "Reasoning tokens are reported separately and are not added to total tokens; provider totals are used "
                "when present, otherwise total is derived only when both input and output tokens are observed."
            ),
            "confidence_intervals": (
                "Wilson 95% intervals are used for binary rates. A bounded normal-approximation 95% interval is "
                "reported for mean score only when at least two scores are observed."
            ),
            "throughput": (
                "Output-token throughput is sum(output tokens) / sum(provider latency) over paired observations; "
                "eligibility requires complete paired telemetry."
            ),
            "pareto": (
                "A model is efficient when no eligible model is at least as good on every named axis and strictly "
                "better on at least one. Leaderboard-ineligible and explicitly non-comparable surfaces are excluded."
            ),
        },
    }


def write_analytics(analytics: Mapping[str, Any], output_file: str | Path) -> None:
    """Write analytics as stable, human-readable JSON."""

    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(dict(analytics), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _aggregate_model(
    descriptor: dict[str, str],
    attempts: Sequence[Mapping[str, Any]],
    leaderboard_row: Mapping[str, Any] | None,
    *,
    leaderboard_attached: bool,
) -> dict[str, Any]:
    total = len(attempts)
    observations = [_attempt_observation(attempt) for attempt in attempts]

    scores = [value for value in (_number(attempt.get("score")) for attempt in attempts) if value is not None]
    wall_times = [
        value
        for value in (_nonnegative_number(attempt.get("duration_seconds")) for attempt in attempts)
        if value is not None
    ]
    latencies = [
        observation["latency_seconds"] for observation in observations if observation["latency_seconds"] is not None
    ]

    token_stats = {
        field: _describe_numeric(
            [observation[field] for observation in observations if observation[field] is not None],
            total,
            integral=True,
        )
        for field in ("total_tokens", "input_tokens", "output_tokens", "reasoning_tokens")
    }
    score_stats = _describe_numeric(scores, total, mean_ci_bounds=(0.0, 1.0))
    wall_time_stats = _describe_numeric(wall_times, total)
    latency_stats = _describe_numeric(latencies, total)

    task_success = _binary_rate([attempt.get("passed") for attempt in attempts])
    safe_task_success = _safe_task_success_rate(attempts)
    throughput = _throughput(observations, total)
    completed_count = sum(attempt.get("status", "completed") == "completed" for attempt in attempts)
    error_count = sum(attempt.get("status") == "error" for attempt in attempts)
    comparable = all(observation["provider_telemetry_comparable"] for observation in observations)

    leaderboard_projection = _leaderboard_projection(
        leaderboard_row,
        leaderboard_attached=leaderboard_attached,
    )
    missing_counts = {
        **{field: stats["missing_count"] for field, stats in token_stats.items()},
        "wall_time_seconds": wall_time_stats["missing_count"],
        "latency_seconds": latency_stats["missing_count"],
        "output_tokens_per_second": throughput["missing_count"],
    }

    return {
        "model_id": stable_hash(descriptor),
        "model": descriptor,
        "leaderboard": leaderboard_projection,
        "sample_counts": {
            "result_records": total,
            "completed": completed_count,
            "errors": error_count,
            "other_status": total - completed_count - error_count,
        },
        "outcomes": {
            "score": score_stats,
            "task_success": task_success,
            "safe_task_success": safe_task_success,
        },
        "tokens": token_stats,
        "timing": {
            "wall_time_seconds": wall_time_stats,
            "latency_seconds": latency_stats,
        },
        "throughput": {
            "output_tokens_per_second": throughput,
        },
        "missing_telemetry": {
            "any": any(count > 0 for count in missing_counts.values()),
            "missing_counts": missing_counts,
            "provider_telemetry_comparable": comparable,
            "inconsistent_total_token_records": sum(
                observation["inconsistent_total_tokens"] for observation in observations
            ),
        },
        "pareto": {
            "quality_wall_time": {"eligible": False, "efficient": False},
            "quality_latency": {"eligible": False, "efficient": False},
            "quality_throughput": {"eligible": False, "efficient": False},
        },
    }


def _attempt_observation(attempt: Mapping[str, Any]) -> dict[str, Any]:
    usage_sources = _usage_sources(attempt)
    input_tokens = _first_token(
        usage_sources,
        (("input_tokens",), ("prompt_tokens",), ("prompt_eval_count",), ("prompt_token_count",)),
    )
    output_tokens = _first_token(
        usage_sources,
        (("output_tokens",), ("completion_tokens",), ("eval_count",), ("candidates_token_count",)),
    )
    total_tokens = _first_token(usage_sources, (("total_tokens",), ("total_token_count",)))
    reasoning_tokens = _first_token(
        usage_sources,
        (
            ("reasoning_tokens",),
            ("thinking_tokens",),
            ("thoughts_token_count",),
            ("output_tokens_details", "reasoning_tokens"),
            ("completion_tokens_details", "reasoning_tokens"),
        ),
    )
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    provider_total = _first_token(usage_sources, (("total_tokens",), ("total_token_count",)))
    inconsistent_total = bool(
        provider_total is not None
        and input_tokens is not None
        and output_tokens is not None
        and provider_total != input_tokens + output_tokens
    )

    return {
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "latency_seconds": _latency_seconds(attempt, usage_sources),
        "provider_telemetry_comparable": _provider_telemetry_comparable(attempt),
        "inconsistent_total_tokens": inconsistent_total,
    }


def _usage_sources(attempt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = []
    raw = attempt.get("raw_response")
    if isinstance(raw, Mapping):
        usage = raw.get("usage")
        if isinstance(usage, Mapping):
            sources.append(usage)
        sources.append(raw)
    trace = attempt.get("trace")
    if isinstance(trace, list):
        for event in trace:
            if not isinstance(event, Mapping):
                continue
            usage = event.get("usage")
            if isinstance(usage, Mapping):
                sources.append(usage)
            sources.append(event)
    top_level_usage = attempt.get("usage")
    if isinstance(top_level_usage, Mapping):
        sources.append(top_level_usage)
    return sources


def _latency_seconds(attempt: Mapping[str, Any], usage_sources: Sequence[Mapping[str, Any]]) -> float | None:
    raw = attempt.get("raw_response")
    trace = attempt.get("trace")
    telemetry_sources: list[Mapping[str, Any]] = []
    if isinstance(raw, Mapping):
        telemetry_sources.append(raw)
    if isinstance(trace, list):
        telemetry_sources.extend(event for event in trace if isinstance(event, Mapping))

    for source in telemetry_sources:
        seconds = _nonnegative_number(source.get("latency_seconds"))
        if seconds is not None:
            return seconds
        milliseconds = _nonnegative_number(source.get("latency_ms"))
        if milliseconds is not None:
            return milliseconds / 1000.0

    # Ollama reports durations in nanoseconds. Use it only when no explicit
    # latency was recorded, and keep wall time as a separate metric.
    for source in usage_sources:
        nanoseconds = _nonnegative_number(source.get("total_duration"))
        if nanoseconds is not None:
            return nanoseconds / 1_000_000_000.0
    return None


def _provider_telemetry_comparable(attempt: Mapping[str, Any]) -> bool:
    trace = attempt.get("trace")
    if not isinstance(trace, list):
        return True
    for event in trace:
        if isinstance(event, Mapping) and event.get("comparable_to_api_runs") is False:
            return False
    return True


def _first_token(sources: Sequence[Mapping[str, Any]], paths: Sequence[tuple[str, ...]]) -> int | None:
    for source in sources:
        for path in paths:
            value: Any = source
            for part in path:
                if not isinstance(value, Mapping) or part not in value:
                    value = None
                    break
                value = value[part]
            token = _token_count(value)
            if token is not None:
                return token
    return None


def _token_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and math.isfinite(value) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _nonnegative_number(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number >= 0 else None


def _describe_numeric(
    values: Sequence[int | float],
    total_count: int,
    *,
    integral: bool = False,
    mean_ci_bounds: tuple[float, float] | None = None,
) -> dict[str, Any]:
    observed = [float(value) for value in values]
    if not observed:
        return {
            "sample_count": 0,
            "missing_count": total_count,
            "sum": None,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
            "mean_ci95": None,
        }

    raw_sum = sum(observed)
    result = {
        "sample_count": len(observed),
        "missing_count": total_count - len(observed),
        "sum": int(raw_sum) if integral else _rounded(raw_sum),
        "mean": _rounded(statistics.fmean(observed)),
        "median": _rounded(statistics.median(observed)),
        "minimum": int(min(observed)) if integral else _rounded(min(observed)),
        "maximum": int(max(observed)) if integral else _rounded(max(observed)),
        "mean_ci95": None,
    }
    if mean_ci_bounds is not None and len(observed) >= 2:
        mean = statistics.fmean(observed)
        standard_error = statistics.stdev(observed) / math.sqrt(len(observed))
        low = max(mean_ci_bounds[0], mean - _Z_95 * standard_error)
        high = min(mean_ci_bounds[1], mean + _Z_95 * standard_error)
        result["mean_ci95"] = [_rounded(low), _rounded(high)]
    return result


def _binary_rate(values: Sequence[Any]) -> dict[str, Any]:
    observed = [value for value in values if isinstance(value, bool)]
    successes = sum(observed)
    trials = len(observed)
    return {
        "success_count": successes,
        "sample_count": trials,
        "missing_count": len(values) - trials,
        "rate": _rounded(successes / trials) if trials else None,
        "ci95": list(map(_rounded, _wilson_interval(successes, trials))) if trials else None,
    }


def _safe_task_success_rate(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    observed: list[bool] = []
    for attempt in attempts:
        passed = attempt.get("passed")
        safe = attempt.get("safe")
        if isinstance(passed, bool) and isinstance(safe, bool):
            observed.append(passed and safe)
    successes = sum(observed)
    trials = len(observed)
    return {
        "success_count": successes,
        "sample_count": trials,
        "missing_count": len(attempts) - trials,
        "rate": _rounded(successes / trials) if trials else None,
        "ci95": list(map(_rounded, _wilson_interval(successes, trials))) if trials else None,
    }


def _throughput(observations: Sequence[Mapping[str, Any]], total_count: int) -> dict[str, Any]:
    paired = [
        (int(observation["output_tokens"]), float(observation["latency_seconds"]))
        for observation in observations
        if observation["output_tokens"] is not None
        and observation["latency_seconds"] is not None
        and float(observation["latency_seconds"]) > 0
    ]
    if not paired:
        return {
            "value": None,
            "sample_count": 0,
            "missing_count": total_count,
            "output_token_sum": None,
            "latency_seconds_sum": None,
        }
    output_sum = sum(output for output, _ in paired)
    latency_sum = sum(latency for _, latency in paired)
    return {
        "value": _rounded(output_sum / latency_sum),
        "sample_count": len(paired),
        "missing_count": total_count - len(paired),
        "output_token_sum": output_sum,
        "latency_seconds_sum": _rounded(latency_sum),
    }


def _wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if trials <= 0:
        raise ValueError("Wilson interval requires at least one trial.")
    proportion = successes / trials
    denominator = 1 + _Z_95**2 / trials
    centre = proportion + _Z_95**2 / (2 * trials)
    margin = _Z_95 * math.sqrt(proportion * (1 - proportion) / trials + _Z_95**2 / (4 * trials**2))
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def _quality_wall_time_eligible(row: Mapping[str, Any]) -> bool:
    count = int(row["sample_counts"]["result_records"])
    return (
        _leaderboard_pareto_eligible(row)
        and row["missing_telemetry"]["provider_telemetry_comparable"] is True
        and row["outcomes"]["safe_task_success"]["sample_count"] == count
        and row["outcomes"]["score"]["sample_count"] == count
        and row["timing"]["wall_time_seconds"]["sample_count"] == count
        and count > 0
    )


def _quality_latency_eligible(row: Mapping[str, Any]) -> bool:
    count = int(row["sample_counts"]["result_records"])
    return (
        _quality_wall_time_eligible(row)
        and row["missing_telemetry"]["provider_telemetry_comparable"] is True
        and row["timing"]["latency_seconds"]["sample_count"] == count
    )


def _quality_throughput_eligible(row: Mapping[str, Any]) -> bool:
    count = int(row["sample_counts"]["result_records"])
    return (
        _quality_wall_time_eligible(row)
        and row["missing_telemetry"]["provider_telemetry_comparable"] is True
        and row["throughput"]["output_tokens_per_second"]["sample_count"] == count
    )


def _leaderboard_pareto_eligible(row: Mapping[str, Any]) -> bool:
    leaderboard = row.get("leaderboard")
    return not isinstance(leaderboard, Mapping) or leaderboard.get("ranking_eligible") is True


def _mark_pareto_frontier(
    rows: Sequence[dict[str, Any]],
    *,
    frontier_name: str,
    metrics: Sequence[tuple[str, str]],
    eligibility: Any,
) -> dict[str, Any]:
    eligible = [row for row in rows if eligibility(row)]
    efficient: list[dict[str, Any]] = []
    for candidate in eligible:
        dominated = any(other is not candidate and _dominates(other, candidate, metrics) for other in eligible)
        if not dominated:
            efficient.append(candidate)

    efficient_ids = {row["model_id"] for row in efficient}
    eligible_ids = {row["model_id"] for row in eligible}
    for row in rows:
        row["pareto"][frontier_name] = {
            "eligible": row["model_id"] in eligible_ids,
            "efficient": row["model_id"] in efficient_ids,
        }

    return {
        "metrics": [{"name": name, "direction": direction} for name, direction in metrics],
        "eligible_model_count": len(eligible),
        "efficient_model_ids": sorted(efficient_ids),
    }


def _dominates(
    candidate: Mapping[str, Any],
    other: Mapping[str, Any],
    metrics: Sequence[tuple[str, str]],
) -> bool:
    at_least_as_good = True
    strictly_better = False
    for metric, direction in metrics:
        candidate_value = _pareto_value(candidate, metric)
        other_value = _pareto_value(other, metric)
        if direction == "max":
            at_least_as_good &= candidate_value >= other_value
            strictly_better |= candidate_value > other_value
        elif direction == "min":
            at_least_as_good &= candidate_value <= other_value
            strictly_better |= candidate_value < other_value
        else:
            raise ValueError(f"Unsupported Pareto direction: {direction}")
    return at_least_as_good and strictly_better


def _pareto_value(row: Mapping[str, Any], metric: str) -> float:
    values = {
        "safe_task_success_rate": float(row["outcomes"]["safe_task_success"]["rate"]),
        "mean_score": float(row["outcomes"]["score"]["mean"]),
        "mean_wall_time_seconds": float(row["timing"]["wall_time_seconds"]["mean"]),
    }
    if metric == "mean_latency_seconds":
        return float(row["timing"]["latency_seconds"]["mean"])
    if metric == "output_tokens_per_second":
        return float(row["throughput"]["output_tokens_per_second"]["value"])
    return values[metric]


def _attempt_sort_key(attempt: Mapping[str, Any]) -> tuple[str, int, str, str]:
    manifest = attempt.get("manifest")
    if not isinstance(manifest, Mapping):
        manifest = {}
    attempt_index = attempt.get("attempt_index")
    normalized_attempt_index = (
        attempt_index if isinstance(attempt_index, int) and not isinstance(attempt_index, bool) else -1
    )
    return (
        str(manifest.get("task_id", "")),
        normalized_attempt_index,
        str(manifest.get("run_id", "")),
        stable_hash(dict(attempt)),
    )


def _model_descriptor(record: Mapping[str, Any]) -> dict[str, str]:
    manifest = record.get("manifest")
    model = manifest.get("model") if isinstance(manifest, Mapping) else None
    if not isinstance(model, Mapping):
        model = {}
    return {field: str(model.get(field, "unknown")) for field in _MODEL_FIELDS}


def _leaderboard_rows(leaderboard: Mapping[str, Any] | None) -> dict[tuple[str, ...], Mapping[str, Any]]:
    if leaderboard is None:
        return {}
    rows: dict[tuple[str, ...], Mapping[str, Any]] = {}
    for collection_name in ("models", "unranked_models"):
        collection = leaderboard.get(collection_name)
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, Mapping):
                continue
            key = tuple(str(row.get(field, "unknown")) for field in _MODEL_FIELDS)
            rows[key] = row
    return rows


def _leaderboard_projection(
    row: Mapping[str, Any] | None,
    *,
    leaderboard_attached: bool,
) -> dict[str, Any] | None:
    if not leaderboard_attached:
        return None
    if row is None:
        return {
            "matched": False,
            "rank": None,
            "ranking_eligible": False,
            "attempt_count": None,
            "reported_task_success_rate": None,
            "reported_safe_success_rate": None,
        }
    return {
        "matched": True,
        "rank": row.get("rank"),
        "ranking_eligible": row.get("ranking_eligible"),
        "attempt_count": row.get("attempt_count"),
        "reported_task_success_rate": row.get("task_success_rate"),
        "reported_safe_success_rate": row.get("safe_success_rate"),
    }


def _leaderboard_release_id(leaderboard: Mapping[str, Any] | None) -> str | None:
    if leaderboard is None:
        return None
    release = leaderboard.get("release")
    if not isinstance(release, Mapping):
        return None
    value = release.get("release_id")
    return str(value) if value is not None else None


def _rounded(value: float) -> float:
    return round(float(value), 6)
