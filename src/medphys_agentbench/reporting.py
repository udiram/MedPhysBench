"""Aggregate benchmark results into leaderboard-ready JSON."""

from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import TaskSpec
from .json_utils import stable_hash
from .release_loader import BenchmarkRelease
from .runner import (
    SCORING_REVISION,
    grader_hash_for_task,
    prompt_hash_for_task,
    runtime_task_hash_for_task,
    system_prompt_hash,
    tool_schema_hash_for_task,
)
from .scoring import grades_pass, grades_safe, score_attempt, weighted_grade_score


def summarize_release(
    release: BenchmarkRelease,
    results_root: str | Path,
    *,
    expected_attempts_per_task: int | None = None,
) -> dict[str, Any]:
    tasks = release.load_tasks()
    expected_attempts = expected_attempts_per_task or release.expected_attempts_per_task
    if expected_attempts <= 0:
        raise ValueError("expected_attempts_per_task must be positive.")

    root = Path(results_root) / release.release_id
    model_dirs = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    task_catalog = {task.task_id: task for task in tasks}
    task_hash_catalog = {
        task.task_id: {
            "prompt_hash": prompt_hash_for_task(task),
            "tool_schema_hash": tool_schema_hash_for_task(task),
            "runtime_task_hash": runtime_task_hash_for_task(task),
            "system_prompt_hash": system_prompt_hash(),
            "grader_hash": grader_hash_for_task(task),
        }
        for task in tasks
    }
    expected_attempt_keys = {
        (task.task_id, attempt_index) for task in tasks for attempt_index in range(expected_attempts)
    }

    ranked_rows: list[dict[str, Any]] = []
    unranked_rows: list[dict[str, Any]] = []
    for model_dir in model_dirs:
        results = _load_model_results(model_dir)
        if not results:
            continue
        row = _summarize_model_dir(
            results=results,
            task_catalog=task_catalog,
            task_hash_catalog=task_hash_catalog,
            expected_attempt_keys=expected_attempt_keys,
        )
        if row["ranking_eligible"]:
            ranked_rows.append(row)
        else:
            unranked_rows.append(row)

    task_rows = [
        {
            "task_id": task.task_id,
            "title": task.title,
            "domain": task.domain,
            "risk_tier": task.risk_tier.value,
            "track": task.track,
            "access_class": task.access_class.value,
            "expected_escalation": task.safety.get("requires_escalation"),
            "context_artifact_count": len(task.context_artifacts),
            "prompt_hash": task_hash_catalog[task.task_id]["prompt_hash"],
            "tool_schema_hash": task_hash_catalog[task.task_id]["tool_schema_hash"],
        }
        for task in tasks
    ]

    ranked_models = _rank_models(ranked_rows)
    unranked_models = sorted(unranked_rows, key=lambda row: str(row["model_name"]))
    _assign_outcome_ranks([*ranked_models, *unranked_models])

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "release": {
            "schema_version": release.schema_version,
            "release_id": release.release_id,
            "title": release.title,
            "description": release.description,
            "task_files": [_portable_task_path(path) for path in release.task_files],
            "allow_access_classes": [value.value for value in release.allow_access_classes],
            "expected_attempts_per_task": expected_attempts,
            "integrity_profile": release.integrity_profile,
            "family_count": len({task.family_id or task.task_id for task in tasks}),
        },
        "integrity": {
            "expected_attempts_per_task": expected_attempts,
            "expected_attempt_count": len(expected_attempt_keys),
            "ranked_model_count": len(ranked_rows),
            "unranked_model_count": len(unranked_rows),
            "release_contract_hash": _release_contract_hash_v1(
                release_id=release.release_id,
                expected_attempts=expected_attempts,
                tasks=tasks,
                task_hash_catalog=task_hash_catalog,
            ),
            "release_contract_hash_v2": _release_contract_hash(
                release_id=release.release_id,
                expected_attempts=expected_attempts,
                tasks=tasks,
                task_hash_catalog=task_hash_catalog,
            ),
        },
        "models": ranked_models,
        "unranked_models": unranked_models,
        "tasks": task_rows,
        "coverage": _build_coverage(task_rows),
        "methodology": {
            "primary_metric": "safe task success rate",
            "confidence_interval": (
                "Wilson 95% interval over attempts plus deterministic family-cluster bootstrap "
                "when family IDs are available"
            ),
            "pass_at_k": "unbiased probability that at least one of k sampled attempts safely passes",
            "pass_power_k": "unbiased probability that all k sampled attempts safely pass",
            "ranking_rule": (
                "Only complete and internally consistent model runs receive an official rank, and ranks are "
                "computed within an identical provider, harness, and harness-revision group."
            ),
            "outcome_order_rule": (
                "Complete, internally consistent rows also receive a descriptive cross-surface outcome order. "
                "It orders point estimates only and is not a claim of harness-equivalent performance."
            ),
            "family_dependence": (
                "Tasks sharing family_id are correlated. The reported family-cluster interval resamples "
                "whole families; task-level Wilson intervals remain descriptive."
            ),
            "status": "public research pilot; provisional and not clinical validation",
        },
    }


def _release_contract_hash(
    *,
    release_id: str,
    expected_attempts: int,
    tasks: tuple[TaskSpec, ...],
    task_hash_catalog: dict[str, dict[str, str]],
) -> str:
    return stable_hash(
        {
            "schema_version": "medphysbench.release-contract-hash.v2",
            "release_id": release_id,
            "expected_attempts_per_task": expected_attempts,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "version": task.version,
                    "prompt_hash": task_hash_catalog[task.task_id]["prompt_hash"],
                    "tool_schema_hash": task_hash_catalog[task.task_id]["tool_schema_hash"],
                    "runtime_task_hash": task_hash_catalog[task.task_id]["runtime_task_hash"],
                    "system_prompt_hash": task_hash_catalog[task.task_id]["system_prompt_hash"],
                    "grader_hash": task_hash_catalog[task.task_id]["grader_hash"],
                    "scoring_revision": SCORING_REVISION,
                    "family_id": task.family_id,
                    "difficulty_tier": task.difficulty_tier,
                    "source_dependency_id": task.source_dependency_id,
                    "contamination_tags": sorted(task.contamination_tags),
                }
                for task in tasks
            ],
        }
    )


def _release_contract_hash_v1(
    *,
    release_id: str,
    expected_attempts: int,
    tasks: tuple[TaskSpec, ...],
    task_hash_catalog: dict[str, dict[str, str]],
) -> str:
    """Preserve the published v1 hash while v2 pins authoring metadata."""
    return stable_hash(
        {
            "release_id": release_id,
            "expected_attempts_per_task": expected_attempts,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "version": task.version,
                    "prompt_hash": task_hash_catalog[task.task_id]["prompt_hash"],
                    "tool_schema_hash": task_hash_catalog[task.task_id]["tool_schema_hash"],
                    "runtime_task_hash": task_hash_catalog[task.task_id]["runtime_task_hash"],
                    "system_prompt_hash": task_hash_catalog[task.task_id]["system_prompt_hash"],
                    "grader_hash": task_hash_catalog[task.task_id]["grader_hash"],
                    "scoring_revision": SCORING_REVISION,
                }
                for task in tasks
            ],
        }
    )


def write_summary(summary: dict[str, Any], output_file: str | Path) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _load_model_results(model_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for result_file in sorted(model_dir.glob("*.json")):
        with result_file.open("r", encoding="utf-8") as handle:
            results.append(json.load(handle))
    return results


def _summarize_model_dir(
    *,
    results: list[dict[str, Any]],
    task_catalog: dict[str, Any],
    task_hash_catalog: dict[str, dict[str, str]],
    expected_attempt_keys: set[tuple[str, int]],
) -> dict[str, Any]:
    integrity = _audit_model_results(
        results=results,
        task_catalog=task_catalog,
        task_hash_catalog=task_hash_catalog,
        expected_attempt_keys=expected_attempt_keys,
    )
    verified_results, regrade_errors = _regrade_results(results, task_catalog)
    if regrade_errors:
        integrity["errors"] = sorted(set([*integrity["errors"], *regrade_errors]))
        integrity["ranking_eligible"] = False
    completed = [item for item in verified_results if item.get("status", "completed") == "completed"]
    attempt_count = len(verified_results)

    task_successes = sum(1 for item in verified_results if item.get("passed"))
    safe_successes = sum(1 for item in verified_results if item.get("passed") and item.get("safe"))
    safety_gate_successes = sum(1 for item in verified_results if item.get("safe"))
    valid_outputs = sum(1 for item in verified_results if _grade_passed(item, "schema.json_schema"))
    escalation_tasks = [
        item for item in verified_results if _expected_escalation(item.get("manifest", {}).get("task_id"), task_catalog)
    ]
    correct_escalations = sum(1 for item in escalation_tasks if _grade_passed(item, "safety.escalation"))
    critical_failures = sum(
        1
        for item in verified_results
        if any(
            (not grade.get("passed"))
            and grade.get("severity") == "critical"
            and (grade.get("lane") == "safety" or str(grade.get("grader_id", "")).startswith("safety."))
            for grade in item.get("grades", [])
        )
    )

    by_domain: dict[str, list[bool]] = defaultdict(list)
    lane_scores: dict[str, list[float]] = defaultdict(list)
    by_task: dict[str, list[bool]] = defaultdict(list)
    by_task_safe: dict[str, list[bool]] = defaultdict(list)
    for item in verified_results:
        task_id = item.get("manifest", {}).get("task_id")
        if task_id not in task_catalog:
            continue
        task = task_catalog[task_id]
        by_domain[task.domain].append(bool(item.get("passed") and item.get("safe")))
        by_task[task_id].append(bool(item.get("passed")))
        by_task_safe[task_id].append(bool(item.get("passed") and item.get("safe")))
        for grade in item.get("grades", []):
            lane_scores[str(grade.get("lane", "outcome"))].append(float(grade.get("score", 0.0)))

    any_pass = sum(any(attempts) for attempts in by_task.values())
    all_pass = sum(all(attempts) for attempts in by_task.values())
    ci_low, ci_high = _wilson_interval(task_successes, attempt_count)
    safe_ci_low, safe_ci_high = _wilson_interval(safe_successes, attempt_count)
    family_outcomes: dict[str, list[bool]] = defaultdict(list)
    for task_id, attempts in by_task_safe.items():
        family_id = task_catalog[task_id].family_id or task_id
        family_outcomes[family_id].extend(attempts)
    cluster_low, cluster_high = _family_cluster_bootstrap_interval(family_outcomes)
    reliability = _reliability_summary(by_task_safe)
    usage = _usage_summary(verified_results)
    is_common_harness = integrity["is_common_harness"]
    comparison_group = (
        f"{integrity['provider']}::{integrity['harness_name']}::{integrity['harness_revision']}"
        if is_common_harness
        else None
    )
    durations = [
        float(item["duration_seconds"])
        for item in verified_results
        if item.get("duration_seconds") is not None
        and not item.get("model_failure_kind")
        and not item.get("capability_failure")
    ]

    return {
        "model_name": integrity["model_name"],
        "provider": integrity["provider"],
        "model_revision": integrity["model_revision"],
        "execution_surface": "recorded_output_import" if integrity["is_recorded_import"] else "common_harness",
        "execution_surface_label": (
            "Recorded output import"
            if integrity["is_recorded_import"]
            else "Common harness execution"
        ),
        "run_profile": {
            "provider": integrity["provider"],
            "harness_name": integrity["harness_name"],
            "harness_revision": integrity["harness_revision"],
            "is_common_harness": is_common_harness,
            "is_recorded_import_surface": not is_common_harness,
        },
        "harness_name": str(results[0].get("manifest", {}).get("model", {}).get("harness_name", "")),
        "harness_revision": str(results[0].get("manifest", {}).get("model", {}).get("harness_revision", "")),
        "comparison_group": comparison_group,
        "attempt_count": attempt_count,
        "completed_count": len(completed),
        "error_count": attempt_count - len(completed),
        "expected_attempt_count": len(expected_attempt_keys),
        "task_success_rate": round(task_successes / attempt_count, 4) if attempt_count else 0.0,
        "task_success_ci95": [round(ci_low, 4), round(ci_high, 4)],
        "safe_success_ci95": [round(safe_ci_low, 4), round(safe_ci_high, 4)],
        "family_cluster_safe_success_ci95": [round(cluster_low, 4), round(cluster_high, 4)],
        "family_count": len(family_outcomes),
        "safe_success_rate": round(safe_successes / attempt_count, 4) if attempt_count else 0.0,
        "safety_gate_rate": round(safety_gate_successes / attempt_count, 4) if attempt_count else 0.0,
        "valid_output_rate": round(valid_outputs / attempt_count, 4) if attempt_count else 0.0,
        "any_pass_rate": round(any_pass / len(by_task), 4) if by_task else 0.0,
        "all_pass_rate": round(all_pass / len(by_task), 4) if by_task else 0.0,
        "reliability": reliability,
        "appropriate_escalation_rate": round(correct_escalations / len(escalation_tasks), 4)
        if escalation_tasks
        else None,
        "critical_unsafe_action_rate": round(critical_failures / attempt_count, 4) if attempt_count else 0.0,
        # Recorded native batches measure import/scoring time, not model latency.
        # Publishing that value as inference time would be materially misleading.
        "average_duration_seconds": (
            None if not is_common_harness or not durations else round(statistics.fmean(durations), 4)
        ),
        "median_duration_seconds": (
            None if not is_common_harness or not durations else round(statistics.median(durations), 4)
        ),
        "duration_telemetry": {
            "available": bool(durations) and is_common_harness,
            "complete": is_common_harness and len(durations) == attempt_count,
            "kind": (
                "unavailable_recorded_surface"
                if not is_common_harness
                else "common_harness_wall_clock"
                if len(durations) == attempt_count
                else "partial_common_harness_wall_clock"
                if durations
                else "unavailable_common_harness_wall_clock"
            ),
            "observed_attempts": len(durations) if is_common_harness else 0,
            "expected_attempts": attempt_count,
        },
        "token_usage": usage,
        "lane_scores": {lane: round(statistics.fmean(values), 4) for lane, values in sorted(lane_scores.items())},
        "domain_safe_success": {
            domain: round(sum(values) / len(values), 4) for domain, values in sorted(by_domain.items())
        },
        "ranking_eligible": integrity["ranking_eligible"],
        "outcome_order_eligible": integrity["outcome_order_eligible"],
        "integrity": {
            "observed_attempt_keys": integrity["observed_attempt_count"],
            "missing_attempt_keys": integrity["missing_attempt_count"],
            "unexpected_attempt_keys": integrity["unexpected_attempt_count"],
            "integrity_errors": integrity["errors"],
        },
        "tasks": [
            _task_result_row(item, task_catalog)
            for item in verified_results
            if item.get("manifest", {}).get("task_id") in task_catalog
        ],
    }


def _usage_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate provider-reported token counts without treating missing values as zero."""
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    total_tokens: list[int] = []
    for item in results:
        usage = _provider_usage(item)
        prompt = _nonnegative_int(usage.get("prompt_eval_count", usage.get("prompt_tokens")))
        completion = _nonnegative_int(usage.get("eval_count", usage.get("completion_tokens")))
        total = _nonnegative_int(usage.get("total_tokens"))
        if prompt is not None:
            input_tokens.append(prompt)
        if completion is not None:
            output_tokens.append(completion)
        if total is None and prompt is not None and completion is not None:
            total = prompt + completion
        if total is not None:
            total_tokens.append(total)

    observed = min(len(input_tokens), len(output_tokens))
    expected = len(results)
    return {
        "available": observed > 0,
        "complete": observed == expected and expected > 0,
        "observed_attempts": observed,
        "expected_attempts": expected,
        "total_input_tokens": sum(input_tokens) if input_tokens else None,
        "total_output_tokens": sum(output_tokens) if output_tokens else None,
        "total_tokens": sum(total_tokens) if total_tokens else None,
        "median_input_tokens": round(statistics.median(input_tokens), 2) if input_tokens else None,
        "median_output_tokens": round(statistics.median(output_tokens), 2) if output_tokens else None,
        "median_total_tokens": round(statistics.median(total_tokens), 2) if total_tokens else None,
    }


def _provider_usage(item: dict[str, Any]) -> dict[str, Any]:
    raw_usage = item.get("raw_response", {}).get("usage")
    if isinstance(raw_usage, dict):
        return raw_usage
    for event in item.get("trace", []):
        if isinstance(event, dict) and isinstance(event.get("usage"), dict):
            return event["usage"]
    return {}


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = int(value)
    return number if number >= 0 and number == value else None


def _task_result_row(item: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    task_id = item["manifest"]["task_id"]
    task = task_catalog[task_id]
    return {
        "task_id": task_id,
        "family_id": task.family_id,
        "title": task.title,
        "domain": task.domain,
        "track": task.track,
        "run_id": item["manifest"].get("run_id"),
        "seed": item["manifest"].get("seed"),
        "attempt_index": item.get("attempt_index"),
        "prompt_hash": item["manifest"].get("prompt_hash"),
        "tool_schema_hash": item["manifest"].get("tool_schema_hash"),
        "runtime_task_hash": item["manifest"].get("runtime_task_hash"),
        "grader_hash": item["manifest"].get("grader_hash"),
        "scoring_revision": item["manifest"].get("scoring_revision"),
        "passed": bool(item.get("passed", False)),
        "safe": item.get("safe", item["passed"]),
        "outcome_category": _task_outcome_category(item),
        "failed_graders": _failed_graders(item),
        "failed_lanes": _failed_lanes(item),
    }


def _task_outcome_category(item: dict[str, Any]) -> str:
    if not bool(item.get("passed", False)):
        if not bool(item.get("safe", False)):
            return "unsafe"
        return "safe_failure"
    if bool(item.get("passed", False)) and bool(item.get("safe", False)):
        return "safe_success"
    return "inconclusive"


def _failed_graders(item: dict[str, Any]) -> list[str]:
    return sorted(
        {
            grade.get("grader_id")
            for grade in item.get("grades", [])
            if isinstance(grade, dict) and not bool(grade.get("passed"))
        }
    )


def _failed_lanes(item: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(grade.get("lane", "outcome"))
            for grade in item.get("grades", [])
            if isinstance(grade, dict) and not bool(grade.get("passed"))
        }
    )


def _audit_model_results(
    *,
    results: list[dict[str, Any]],
    task_catalog: dict[str, Any],
    task_hash_catalog: dict[str, dict[str, str]],
    expected_attempt_keys: set[tuple[str, int]],
) -> dict[str, Any]:
    errors: list[str] = []
    observed_attempt_keys: set[tuple[str, int]] = set()
    observed_run_ids: set[str] = set()
    run_configurations: set[tuple[Any, ...]] = set()

    first_manifest = results[0].get("manifest", {})
    first_model = first_manifest.get("model", {})
    model_name = str(first_model.get("model_name", "unknown"))
    provider = str(first_model.get("provider", "unknown"))
    model_revision = str(first_model.get("model_revision", model_name))

    for item in results:
        manifest = item.get("manifest", {})
        model = manifest.get("model", {})
        if str(model.get("model_name", model_name)) != model_name:
            errors.append("mixed_model_name_manifest")
        if str(model.get("provider", provider)) != provider:
            errors.append("mixed_provider_manifest")
        if str(model.get("model_revision", model_revision)) != model_revision:
            errors.append("mixed_model_revision_manifest")
        if str(model.get("harness_name", first_model.get("harness_name", ""))) != str(
            first_model.get("harness_name", "")
        ):
            errors.append("mixed_harness_name_manifest")
        if str(model.get("harness_revision", first_model.get("harness_revision", ""))) != str(
            first_model.get("harness_revision", "")
        ):
            errors.append("mixed_harness_revision_manifest")

        run_configurations.add(
            (
                manifest.get("temperature"),
                manifest.get("max_tokens"),
                manifest.get("sandbox_image_digest"),
                manifest.get("tool_environment_version"),
            )
        )

        task_id = str(manifest.get("task_id", ""))
        if task_id not in task_catalog:
            errors.append(f"unknown_task_id:{task_id or 'missing'}")
            continue
        if str(manifest.get("task_version", "")) != task_catalog[task_id].version:
            errors.append(f"task_version_mismatch:{task_id}")

        run_id = str(manifest.get("run_id", ""))
        if not run_id:
            errors.append(f"missing_run_id:{task_id}")
        elif run_id in observed_run_ids:
            errors.append(f"duplicate_run_id:{run_id}")
        observed_run_ids.add(run_id)

        attempt_index = item.get("attempt_index")
        if not isinstance(attempt_index, int) or isinstance(attempt_index, bool) or attempt_index < 0:
            errors.append(f"invalid_attempt_index:{task_id}")
            continue

        attempt_key = (task_id, attempt_index)
        if attempt_key in observed_attempt_keys:
            errors.append(f"duplicate_attempt:{task_id}:{attempt_index}")
        observed_attempt_keys.add(attempt_key)

        expected_hashes = task_hash_catalog[task_id]
        prompt_hash = manifest.get("prompt_hash")
        if not prompt_hash:
            errors.append(f"missing_prompt_hash:{task_id}:{attempt_index}")
        elif prompt_hash != expected_hashes["prompt_hash"]:
            errors.append(f"prompt_hash_mismatch:{task_id}:{attempt_index}")
        tool_schema_hash = manifest.get("tool_schema_hash")
        if not tool_schema_hash:
            errors.append(f"missing_tool_schema_hash:{task_id}:{attempt_index}")
        elif tool_schema_hash != expected_hashes["tool_schema_hash"]:
            errors.append(f"tool_schema_hash_mismatch:{task_id}:{attempt_index}")
        runtime_task_hash = manifest.get("runtime_task_hash")
        if not runtime_task_hash:
            errors.append(f"missing_runtime_task_hash:{task_id}:{attempt_index}")
        elif runtime_task_hash != expected_hashes["runtime_task_hash"]:
            errors.append(f"runtime_task_hash_mismatch:{task_id}:{attempt_index}")
        manifest_system_prompt_hash = manifest.get("system_prompt_hash")
        if not manifest_system_prompt_hash:
            errors.append(f"missing_system_prompt_hash:{task_id}:{attempt_index}")
        elif manifest_system_prompt_hash != expected_hashes["system_prompt_hash"]:
            errors.append(f"system_prompt_hash_mismatch:{task_id}:{attempt_index}")
        grader_hash = manifest.get("grader_hash")
        scoring_revision = manifest.get("scoring_revision")
        # Every scored attempt must pin the grader contract. Older public-core
        # artifacts predate this invariant and remain historical snapshots;
        # they must not become eligible when regenerated under newer graders.
        requires_scoring_contract = True
        if requires_scoring_contract and not grader_hash:
            errors.append(f"missing_grader_hash:{task_id}:{attempt_index}")
        elif grader_hash and grader_hash != expected_hashes["grader_hash"]:
            errors.append(f"grader_hash_mismatch:{task_id}:{attempt_index}")
        if requires_scoring_contract and not scoring_revision:
            errors.append(f"missing_scoring_revision:{task_id}:{attempt_index}")
        elif scoring_revision and scoring_revision != SCORING_REVISION:
            errors.append(f"scoring_revision_mismatch:{task_id}:{attempt_index}")

    missing_attempt_keys = expected_attempt_keys - observed_attempt_keys
    unexpected_attempt_keys = observed_attempt_keys - expected_attempt_keys
    if missing_attempt_keys:
        errors.append(f"missing_attempts:{len(missing_attempt_keys)}")
    if unexpected_attempt_keys:
        errors.append(f"unexpected_attempts:{len(unexpected_attempt_keys)}")
    if len(run_configurations) > 1:
        errors.append("mixed_run_configuration_manifest")
    noncompleted_attempts = sum(1 for item in results if item.get("status", "completed") != "completed")
    if noncompleted_attempts:
        errors.append(f"noncompleted_attempts:{noncompleted_attempts}")
    is_recorded_import = _run_is_recorded_import(results)
    if is_recorded_import:
        errors.append("unranked_noncommon_surface")

    return {
        "model_name": model_name,
        "provider": provider,
        "model_revision": model_revision,
        "harness_name": str(first_model.get("harness_name", "")),
        "harness_revision": str(first_model.get("harness_revision", model_name)),
        "is_recorded_import": is_recorded_import,
        "is_common_harness": not is_recorded_import,
        "ranking_eligible": not errors,
        "outcome_order_eligible": not [error for error in errors if error != "unranked_noncommon_surface"],
        "errors": sorted(set(errors)),
        "observed_attempt_count": len(observed_attempt_keys),
        "missing_attempt_count": len(missing_attempt_keys),
        "unexpected_attempt_count": len(unexpected_attempt_keys),
    }


def _run_is_recorded_import(results: list[dict[str, Any]]) -> bool:
    return any(
        str(item.get("manifest", {}).get("model", {}).get("harness_name", "")) == "medphysbench-recorded-output"
        or any(
            str(event.get("event", "")) == "recorded_output_import"
            for event in item.get("trace", [])
            if isinstance(event, dict)
        )
        for item in results
    )


def _regrade_results(
    results: list[dict[str, Any]], task_catalog: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Recompute public scores from outputs so stored grades cannot inflate ranks."""
    verified_results: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in results:
        verified = dict(item)
        manifest = item.get("manifest", {})
        task_id = str(manifest.get("task_id", ""))
        if item.get("status", "completed") != "completed" or task_id not in task_catalog:
            verified.update({"passed": False, "safe": False, "score": 0.0, "grades": []})
            verified_results.append(verified)
            continue
        output = item.get("output")
        if not isinstance(output, dict):
            errors.append(f"invalid_output_object:{task_id}:{item.get('attempt_index')}")
            verified.update({"passed": False, "safe": False, "score": 0.0, "grades": []})
            verified_results.append(verified)
            continue

        grades = score_attempt(task_catalog[task_id], output)
        passed = grades_pass(grades)
        safe = grades_safe(grades)
        score = weighted_grade_score(grades)
        stored_signature = _grade_signature(item.get("grades", []))
        verified_signature = _grade_signature([grade.to_dict() for grade in grades])
        if (
            bool(item.get("passed")) != passed
            or bool(item.get("safe")) != safe
            or stored_signature != verified_signature
        ):
            errors.append(f"stored_grades_disagree_with_regrade:{task_id}:{item.get('attempt_index')}")
        verified.update(
            {
                "grades": [grade.to_dict() for grade in grades],
                "passed": passed,
                "safe": safe,
                "score": score,
            }
        )
        verified_results.append(verified)
    return verified_results, errors


def _grade_signature(grades: Any) -> tuple[tuple[Any, ...], ...]:
    if not isinstance(grades, list):
        return ()
    return tuple(
        (
            grade.get("grader_id"),
            bool(grade.get("passed")),
            _finite_grade_number(grade.get("score", 0.0)),
            grade.get("severity"),
            grade.get("lane", "outcome"),
            bool(grade.get("required_for_pass", True)),
            _finite_grade_number(grade.get("weight", 1.0)),
        )
        for grade in grades
        if isinstance(grade, dict)
    )


def _finite_grade_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _build_coverage(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    for task in tasks:
        bucket = by_domain.setdefault(
            task["domain"],
            {"domain": task["domain"], "task_count": 0, "expected_escalation_count": 0},
        )
        bucket["task_count"] += 1
        bucket["expected_escalation_count"] += int(bool(task["expected_escalation"]))
    return sorted(by_domain.values(), key=lambda item: str(item["domain"]))


def _portable_task_path(path: Path) -> str:
    """Return a host-independent task path suitable for public metadata."""
    if "tasks" in path.parts:
        task_root_index = path.parts.index("tasks")
        return Path(*path.parts[task_root_index:]).as_posix()
    return path.name


def _grade_passed(result: dict[str, Any], grader_id: str) -> bool:
    for grade in result.get("grades", []):
        if grade.get("grader_id") == grader_id:
            return bool(grade.get("passed"))
    return False


def _expected_escalation(task_id: str | None, task_catalog: dict[str, Any]) -> bool:
    if not task_id:
        return False
    task = task_catalog[task_id]
    return bool(task.safety.get("requires_escalation"))


def _reliability_summary(by_task: dict[str, list[bool]]) -> dict[str, Any]:
    if not by_task:
        return {
            "pass_at_k": {},
            "pass_power_k": {},
            "all_attempts_agree_rate": None,
            "mean_within_task_variance": None,
        }
    maximum_k = max(len(attempts) for attempts in by_task.values())
    pass_at_k: dict[str, float] = {}
    pass_power_k: dict[str, float] = {}
    for k in range(1, maximum_k + 1):
        eligible = [attempts for attempts in by_task.values() if len(attempts) >= k]
        if not eligible:
            continue
        pass_at_k[str(k)] = round(statistics.fmean(_pass_at_k(attempts, k) for attempts in eligible), 4)
        pass_power_k[str(k)] = round(statistics.fmean(_pass_power_k(attempts, k) for attempts in eligible), 4)
    agreement = statistics.fmean(1.0 if len(set(attempts)) == 1 else 0.0 for attempts in by_task.values())
    variances = []
    for attempts in by_task.values():
        proportion = sum(attempts) / len(attempts)
        variances.append(proportion * (1.0 - proportion))
    return {
        "pass_at_k": pass_at_k,
        "pass_power_k": pass_power_k,
        "all_attempts_agree_rate": round(agreement, 4),
        "mean_within_task_variance": round(statistics.fmean(variances), 4),
    }


def _pass_at_k(attempts: list[bool], k: int) -> float:
    """Unbiased probability of at least one success in k draws without replacement."""

    n = len(attempts)
    if k < 1 or k > n:
        raise ValueError("k must be between 1 and the number of attempts")
    successes = sum(attempts)
    failures = n - successes
    if failures < k:
        return 1.0
    return 1.0 - (math.comb(failures, k) / math.comb(n, k))


def _pass_power_k(attempts: list[bool], k: int) -> float:
    """Unbiased probability that every one of k draws succeeds without replacement."""

    n = len(attempts)
    if k < 1 or k > n:
        raise ValueError("k must be between 1 and the number of attempts")
    successes = sum(attempts)
    if successes < k:
        return 0.0
    return math.comb(successes, k) / math.comb(n, k)


def _family_cluster_bootstrap_interval(by_family: dict[str, list[bool]], *, samples: int = 2000) -> tuple[float, float]:
    """Return a deterministic percentile interval that resamples whole task families."""

    families = sorted((family, outcomes) for family, outcomes in by_family.items() if outcomes)
    if not families:
        return (0.0, 0.0)
    if len(families) == 1:
        rate = sum(families[0][1]) / len(families[0][1])
        return (rate, rate)
    generator = random.Random(20260731)
    rates: list[float] = []
    for _ in range(samples):
        sampled = [families[generator.randrange(len(families))][1] for _ in families]
        successes = sum(sum(outcomes) for outcomes in sampled)
        trials = sum(len(outcomes) for outcomes in sampled)
        rates.append(successes / trials)
    rates.sort()
    lower_index = int(0.025 * (samples - 1))
    upper_index = int(0.975 * (samples - 1))
    return (rates[lower_index], rates[upper_index])


def _wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1 + z**2 / trials
    centre = proportion + z**2 / (2 * trials)
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z**2 / (4 * trials**2))
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def _rank_models(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["ranking_eligible"]:
            grouped[str(row.get("comparison_group") or "undeclared")].append(row)
    eligible: list[dict[str, Any]] = []
    for group_name, group_rows in sorted(grouped.items()):
        ordered = sorted(
            group_rows,
            key=lambda item: (
                -float(item["safe_success_rate"]),
                -float(item["task_success_rate"]),
                -float(item["safety_gate_rate"]),
                str(item["model_name"]),
            ),
        )
        for index, row in enumerate(ordered, start=1):
            row["rank"] = index
            row["rank_group"] = group_name
        eligible.extend(ordered)
    ineligible = sorted(
        [row for row in rows if not row["ranking_eligible"]],
        key=lambda item: str(item["model_name"]),
    )
    for row in ineligible:
        row["rank"] = None
    return eligible + ineligible


def _assign_outcome_ranks(rows: list[dict[str, Any]]) -> None:
    """Add a descriptive point-estimate order without weakening official rank eligibility."""

    eligible = sorted(
        [row for row in rows if row.get("outcome_order_eligible")],
        key=lambda item: (
            -float(item["safe_success_rate"]),
            -float(item["task_success_rate"]),
            -float(item["safety_gate_rate"]),
            str(item["model_name"]),
        ),
    )
    for index, row in enumerate(eligible, start=1):
        row["outcome_rank"] = index
        row["outcome_rank_status"] = "descriptive_cross_surface"
    for row in rows:
        if row not in eligible:
            row["outcome_rank"] = None
            row["outcome_rank_status"] = "ineligible_incomplete_or_invalid"
