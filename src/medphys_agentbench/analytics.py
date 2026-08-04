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
        payload["_analytics_source_group"] = path.parent.name
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
        grouped[_analytics_group_key(record, descriptor)].append(record)

    model_rows: list[dict[str, Any]] = []
    resolved_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for group_key in sorted(grouped):
        descriptor_key = group_key[: len(_MODEL_FIELDS)]
        attempts = sorted(grouped[group_key], key=_attempt_sort_key)
        run_configuration_hash = _run_configuration_hash(attempts)
        resolved_key = (*descriptor_key, run_configuration_hash)
        if resolved_key in resolved_groups:
            raise ValueError(
                "Analytics source groups resolve to the same immutable model configuration: "
                f"{resolved_key!r}."
            )
        resolved_groups[resolved_key] = attempts
        descriptor = dict(zip(_MODEL_FIELDS, descriptor_key, strict=True))
        descriptor["run_configuration_hash"] = run_configuration_hash
        leaderboard_row = _leaderboard_row_for(resolved_key, leaderboard_rows)
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
    item_diagnostics = _build_item_diagnostics(resolved_groups, leaderboard_rows)

    return {
        "schema_version": "medphysbench.analytics.v1",
        "release_id": resolved_release_id,
        "source": {
            "result_record_count": len(records),
            "model_count": len(model_rows),
            "leaderboard_attached": leaderboard is not None,
        },
        "models": model_rows,
        "item_diagnostics": item_diagnostics,
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
            "item_diagnostics": (
                "Task and family diagnostics are computed separately within each exact comparison group from "
                "ranking-eligible rows only. Public-development watch signals are diagnostic and never imply a "
                "protected-holdout saturation decision."
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


def _build_item_diagnostics(
    grouped: Mapping[tuple[str, ...], Sequence[Mapping[str, Any]]],
    leaderboard_rows: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> dict[str, Any]:
    if not leaderboard_rows:
        return {
            "status": "not_available",
            "reason": "A signed leaderboard is required to identify exact comparison groups and eligible rows.",
            "groups": [],
        }

    task_families: dict[str, str] = {}
    comparison_models: dict[str, list[tuple[tuple[str, ...], Sequence[Mapping[str, Any]]]]] = defaultdict(list)
    for descriptor_key, attempts in grouped.items():
        leaderboard_row = _leaderboard_row_for(descriptor_key, leaderboard_rows)
        if not isinstance(leaderboard_row, Mapping) or leaderboard_row.get("ranking_eligible") is not True:
            continue
        comparison_group = leaderboard_row.get("comparison_group")
        if not isinstance(comparison_group, str) or not comparison_group:
            continue
        comparison_models[comparison_group].append((descriptor_key, attempts))
        tasks = leaderboard_row.get("tasks")
        if isinstance(tasks, list):
            for task in tasks:
                if not isinstance(task, Mapping):
                    continue
                task_id = task.get("task_id")
                family_id = task.get("family_id")
                if not isinstance(task_id, str) or not task_id:
                    continue
                normalized_family = family_id if isinstance(family_id, str) and family_id else task_id
                existing = task_families.get(task_id)
                if existing is not None and existing != normalized_family:
                    raise ValueError(
                        f"Leaderboard task {task_id!r} maps to conflicting families "
                        f"{existing!r} and {normalized_family!r}."
                    )
                task_families[task_id] = normalized_family

    groups = [
        _comparison_group_item_diagnostics(group, models, task_families)
        for group, models in sorted(comparison_models.items())
    ]
    return {
        "status": "available" if groups else "not_available",
        "reason": None if groups else "No ranking-eligible rows declared an exact comparison group.",
        "groups": groups,
        "methodology": {
            "response": "Safe success requires passed=true and safe=true; missing booleans are excluded, not imputed.",
            "task_difficulty": "Observed safe-success proportion over all eligible attempts in the comparison group.",
            "discrimination": (
                "Pearson correlation across systems between each system's task safe-success rate and its "
                "safe-success rate on all other tasks; at least three systems and non-zero variance are required."
            ),
            "family_solution": (
                "A system solves a family when at least 80% of its observed family attempts are safe successes. "
                "A family is panel-solved when at least 80% of eligible systems solve it."
            ),
            "near_zero_entropy": (
                "Binary Shannon entropy at or below 0.10 bits for the system-level family-solved indicator."
            ),
            "watch_thresholds": (
                "The predeclared MedPhysBench thresholds are applied as public-development diagnostics only: "
                "best system >=80%; >=60% of families panel-solved; median task discrimination <0.10; or "
                ">50% of families with near-zero response entropy."
            ),
        },
    }


def _comparison_group_item_diagnostics(
    comparison_group: str,
    models: Sequence[tuple[tuple[str, ...], Sequence[Mapping[str, Any]]]],
    task_families: Mapping[str, str],
) -> dict[str, Any]:
    system_task_observations: list[dict[str, list[bool]]] = []
    attempt_count = 0
    for _, attempts in sorted(models, key=lambda item: item[0]):
        task_observations: dict[str, list[bool]] = defaultdict(list)
        for attempt in attempts:
            task_id = _attempt_task_id(attempt)
            passed = attempt.get("passed")
            safe = attempt.get("safe")
            if task_id and isinstance(passed, bool) and isinstance(safe, bool):
                task_observations[task_id].append(passed and safe)
                attempt_count += 1
        system_task_observations.append(dict(task_observations))

    task_ids = sorted({task_id for observations in system_task_observations for task_id in observations})
    task_rows = [
        _task_item_diagnostic(task_id, system_task_observations, task_families.get(task_id, task_id))
        for task_id in task_ids
    ]
    family_ids = sorted({row["family_id"] for row in task_rows})
    family_rows = [
        _family_item_diagnostic(family_id, task_rows, system_task_observations)
        for family_id in family_ids
    ]

    system_rates = [_system_rate(observations) for observations in system_task_observations]
    observed_system_rates = [rate for rate in system_rates if rate is not None]
    discriminations = [
        float(row["discrimination"])
        for row in task_rows
        if isinstance(row["discrimination"], (int, float))
    ]
    panel_solved_count = sum(bool(row["panel_solved"]) for row in family_rows)
    near_zero_count = sum(bool(row["near_zero_response_entropy"]) for row in family_rows)
    family_count = len(family_rows)
    median_discrimination = statistics.median(discriminations) if discriminations else None
    panel_solved_fraction = panel_solved_count / family_count if family_count else None
    near_zero_fraction = near_zero_count / family_count if family_count else None
    best_system_rate = max(observed_system_rates) if observed_system_rates else None

    watch_signals: list[dict[str, Any]] = []
    if best_system_rate is not None and best_system_rate >= 0.8:
        watch_signals.append({"code": "best_system_at_or_above_80_percent", "observed": _rounded(best_system_rate)})
    if panel_solved_fraction is not None and panel_solved_fraction >= 0.6:
        watch_signals.append(
            {
                "code": "families_panel_solved_at_or_above_60_percent",
                "observed": _rounded(panel_solved_fraction),
            }
        )
    if median_discrimination is not None and median_discrimination < 0.1:
        watch_signals.append(
            {
                "code": "median_task_discrimination_below_0_10",
                "observed": _rounded(median_discrimination),
            }
        )
    if near_zero_fraction is not None and near_zero_fraction > 0.5:
        watch_signals.append({"code": "near_zero_family_entropy_above_half", "observed": _rounded(near_zero_fraction)})

    return {
        "comparison_group": comparison_group,
        "model_count": len(system_task_observations),
        "task_count": len(task_rows),
        "family_count": family_count,
        "attempt_count": attempt_count,
        "tasks": task_rows,
        "families": family_rows,
        "summary": {
            "best_system_safe_success_rate": _rounded(best_system_rate) if best_system_rate is not None else None,
            "median_task_safe_success_rate": (
                _rounded(statistics.median([row["safe_success_rate"] for row in task_rows]))
                if task_rows
                else None
            ),
            "median_task_discrimination": (
                _rounded(median_discrimination) if median_discrimination is not None else None
            ),
            "discrimination_task_count": len(discriminations),
            "panel_solved_family_count": panel_solved_count,
            "panel_solved_family_fraction": (
                _rounded(panel_solved_fraction) if panel_solved_fraction is not None else None
            ),
            "near_zero_entropy_family_count": near_zero_count,
            "near_zero_entropy_family_fraction": (
                _rounded(near_zero_fraction) if near_zero_fraction is not None else None
            ),
            "watch": bool(watch_signals),
            "watch_signals": watch_signals,
            "governance_status": "public_development_diagnostic_only",
        },
    }


def _task_item_diagnostic(
    task_id: str,
    system_task_observations: Sequence[Mapping[str, Sequence[bool]]],
    family_id: str,
) -> dict[str, Any]:
    pooled = [value for observations in system_task_observations for value in observations.get(task_id, ())]
    system_task_rates: list[float] = []
    system_rest_rates: list[float] = []
    for observations in system_task_observations:
        task_values = list(observations.get(task_id, ()))
        rest_values = [
            value
            for other_task_id, values in observations.items()
            if other_task_id != task_id
            for value in values
        ]
        if task_values and rest_values:
            system_task_rates.append(sum(task_values) / len(task_values))
            system_rest_rates.append(sum(rest_values) / len(rest_values))
    rate = sum(pooled) / len(pooled) if pooled else 0.0
    return {
        "task_id": task_id,
        "family_id": family_id,
        "model_count": sum(bool(observations.get(task_id)) for observations in system_task_observations),
        "attempt_count": len(pooled),
        "safe_success_count": sum(pooled),
        "safe_success_rate": _rounded(rate),
        "response_entropy_bits": _rounded(_binary_entropy(rate)),
        "discrimination": _pearson_correlation(system_task_rates, system_rest_rates),
        "discrimination_model_count": len(system_task_rates),
    }


def _family_item_diagnostic(
    family_id: str,
    task_rows: Sequence[Mapping[str, Any]],
    system_task_observations: Sequence[Mapping[str, Sequence[bool]]],
) -> dict[str, Any]:
    task_ids = {str(row["task_id"]) for row in task_rows if row["family_id"] == family_id}
    system_rates: list[float] = []
    for observations in system_task_observations:
        values = [value for task_id in task_ids for value in observations.get(task_id, ())]
        if values:
            system_rates.append(sum(values) / len(values))
    solved = [rate >= 0.8 for rate in system_rates]
    solved_rate = sum(solved) / len(solved) if solved else 0.0
    pooled_values = [
        value
        for observations in system_task_observations
        for task_id in task_ids
        for value in observations.get(task_id, ())
    ]
    safe_success_rate = sum(pooled_values) / len(pooled_values) if pooled_values else 0.0
    entropy = _binary_entropy(solved_rate)
    return {
        "family_id": family_id,
        "task_count": len(task_ids),
        "model_count": len(system_rates),
        "attempt_count": len(pooled_values),
        "safe_success_rate": _rounded(safe_success_rate),
        "system_solved_count": sum(solved),
        "system_solved_fraction": _rounded(solved_rate),
        "panel_solved": solved_rate >= 0.8,
        "response_entropy_bits": _rounded(entropy),
        "near_zero_response_entropy": entropy <= 0.1,
    }


def _attempt_task_id(attempt: Mapping[str, Any]) -> str:
    manifest = attempt.get("manifest")
    task_id = manifest.get("task_id") if isinstance(manifest, Mapping) else None
    return str(task_id) if isinstance(task_id, str) and task_id else ""


def _system_rate(observations: Mapping[str, Sequence[bool]]) -> float | None:
    values = [value for task_values in observations.values() for value in task_values]
    return sum(values) / len(values) if values else None


def _binary_entropy(rate: float) -> float:
    if rate <= 0 or rate >= 1:
        return 0.0
    return -(rate * math.log2(rate) + (1 - rate) * math.log2(1 - rate))


def _pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    denominator = math.sqrt(sum(value * value for value in left_delta) * sum(value * value for value in right_delta))
    if denominator == 0:
        return None
    return _rounded(sum(a * b for a, b in zip(left_delta, right_delta, strict=True)) / denominator)


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


def _analytics_group_key(record: Mapping[str, Any], descriptor: Mapping[str, str]) -> tuple[str, ...]:
    source_group = record.get("_analytics_source_group")
    if isinstance(source_group, str) and source_group:
        partition = f"source:{source_group}"
    else:
        manifest = record.get("manifest")
        normalized_manifest = manifest if isinstance(manifest, Mapping) else {}
        partition = "config:" + stable_hash(
            {
                "adapter_settings_hash": normalized_manifest.get("adapter_settings_hash"),
                "temperature": normalized_manifest.get("temperature"),
                "max_tokens": normalized_manifest.get("max_tokens"),
                "sandbox_image_digest": normalized_manifest.get("sandbox_image_digest"),
                "tool_environment_version": normalized_manifest.get("tool_environment_version"),
            }
        )
    return (*tuple(descriptor[field] for field in _MODEL_FIELDS), partition)


def _run_configuration_hash(attempts: Sequence[Mapping[str, Any]]) -> str:
    run_configurations: set[tuple[Any, ...]] = set()
    seeds_by_attempt_index: dict[int, set[Any]] = defaultdict(set)
    for attempt in attempts:
        manifest = attempt.get("manifest")
        normalized_manifest = manifest if isinstance(manifest, Mapping) else {}
        run_configurations.add(
            (
                normalized_manifest.get("adapter_settings_hash"),
                normalized_manifest.get("temperature"),
                normalized_manifest.get("max_tokens"),
                normalized_manifest.get("sandbox_image_digest"),
                normalized_manifest.get("tool_environment_version"),
            )
        )
        attempt_index = attempt.get("attempt_index")
        if isinstance(attempt_index, int) and not isinstance(attempt_index, bool) and attempt_index >= 0:
            seeds_by_attempt_index[attempt_index].add(normalized_manifest.get("seed"))
    return stable_hash(
        {
            "run_configurations": [list(values) for values in sorted(run_configurations, key=repr)],
            "seeds_by_attempt_index": {
                str(index): sorted(seeds, key=repr)
                for index, seeds in sorted(seeds_by_attempt_index.items())
            },
        }
    )


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
            base_key = tuple(str(row.get(field, "unknown")) for field in _MODEL_FIELDS)
            run_profile = row.get("run_profile")
            run_configuration_hash = (
                run_profile.get("run_configuration_hash") if isinstance(run_profile, Mapping) else None
            )
            key = (
                (*base_key, str(run_configuration_hash))
                if isinstance(run_configuration_hash, str) and run_configuration_hash
                else base_key
            )
            if key in rows:
                raise ValueError(f"Leaderboard contains duplicate analytics identity {key!r}.")
            rows[key] = row
    return rows


def _leaderboard_row_for(
    resolved_key: tuple[str, ...],
    leaderboard_rows: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    exact = leaderboard_rows.get(resolved_key)
    if exact is not None:
        return exact
    return leaderboard_rows.get(resolved_key[: len(_MODEL_FIELDS)])


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
