"""Aggregate benchmark results into leaderboard-ready JSON."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .json_utils import stable_hash
from .release_loader import BenchmarkRelease
from .runner import prompt_hash_for_task, runtime_task_hash_for_task, system_prompt_hash, tool_schema_hash_for_task
from .scoring import score_attempt


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
        }
        for task in tasks
    }
    expected_attempt_keys = {
        (task.task_id, attempt_index)
        for task in tasks
        for attempt_index in range(expected_attempts)
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
        },
        "integrity": {
            "expected_attempts_per_task": expected_attempts,
            "expected_attempt_count": len(expected_attempt_keys),
            "ranked_model_count": len(ranked_rows),
            "unranked_model_count": len(unranked_rows),
            "release_contract_hash": stable_hash(
                {
                    "release_id": release.release_id,
                    "expected_attempts_per_task": expected_attempts,
                    "tasks": [
                        {
                            "task_id": task.task_id,
                            "version": task.version,
                            "prompt_hash": task_hash_catalog[task.task_id]["prompt_hash"],
                            "tool_schema_hash": task_hash_catalog[task.task_id]["tool_schema_hash"],
                        }
                        for task in tasks
                    ],
                }
            ),
        },
        "models": _rank_models(ranked_rows),
        "unranked_models": sorted(unranked_rows, key=lambda row: str(row["model_name"])),
        "tasks": task_rows,
        "coverage": _build_coverage(task_rows),
        "methodology": {
            "primary_metric": "safe task success rate",
            "confidence_interval": "Wilson 95% interval over attempts",
            "any_pass": "fraction of tasks with at least one successful attempt",
            "all_pass": "fraction of tasks where every attempt succeeded",
            "ranking_rule": "Only complete and internally consistent model runs are ranked.",
            "status": "public development set; not clinical validation",
        },
    }


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
        item
        for item in verified_results
        if _expected_escalation(item.get("manifest", {}).get("task_id"), task_catalog)
    ]
    correct_escalations = sum(1 for item in escalation_tasks if _grade_passed(item, "safety.escalation"))
    critical_failures = sum(
        1
        for item in verified_results
        if any((not grade.get("passed")) and grade.get("severity") == "critical" for grade in item.get("grades", []))
    )

    by_domain: dict[str, list[bool]] = defaultdict(list)
    lane_scores: dict[str, list[float]] = defaultdict(list)
    by_task: dict[str, list[bool]] = defaultdict(list)
    for item in verified_results:
        task_id = item.get("manifest", {}).get("task_id")
        if task_id not in task_catalog:
            continue
        task = task_catalog[task_id]
        by_domain[task.domain].append(bool(item.get("passed") and item.get("safe")))
        by_task[task_id].append(bool(item.get("passed")))
        for grade in item.get("grades", []):
            lane_scores[str(grade.get("lane", "outcome"))].append(float(grade.get("score", 0.0)))

    any_pass = sum(any(attempts) for attempts in by_task.values())
    all_pass = sum(all(attempts) for attempts in by_task.values())
    ci_low, ci_high = _wilson_interval(task_successes, attempt_count)

    return {
        "model_name": integrity["model_name"],
        "provider": integrity["provider"],
        "model_revision": integrity["model_revision"],
        "harness_name": str(results[0].get("manifest", {}).get("model", {}).get("harness_name", "")),
        "harness_revision": str(results[0].get("manifest", {}).get("model", {}).get("harness_revision", "")),
        "attempt_count": attempt_count,
        "completed_count": len(completed),
        "error_count": attempt_count - len(completed),
        "expected_attempt_count": len(expected_attempt_keys),
        "task_success_rate": round(task_successes / attempt_count, 4) if attempt_count else 0.0,
        "task_success_ci95": [round(ci_low, 4), round(ci_high, 4)],
        "safe_success_rate": round(safe_successes / attempt_count, 4) if attempt_count else 0.0,
        "safety_gate_rate": round(safety_gate_successes / attempt_count, 4) if attempt_count else 0.0,
        "valid_output_rate": round(valid_outputs / attempt_count, 4) if attempt_count else 0.0,
        "any_pass_rate": round(any_pass / len(by_task), 4) if by_task else 0.0,
        "all_pass_rate": round(all_pass / len(by_task), 4) if by_task else 0.0,
        "appropriate_escalation_rate": round(correct_escalations / len(escalation_tasks), 4)
        if escalation_tasks
        else None,
        "critical_unsafe_action_rate": round(critical_failures / attempt_count, 4) if attempt_count else 0.0,
        "average_duration_seconds": round(
            sum(float(item.get("duration_seconds", 0.0)) for item in verified_results) / attempt_count,
            4,
        )
        if attempt_count
        else 0.0,
        "median_duration_seconds": round(
            statistics.median(float(item.get("duration_seconds", 0.0)) for item in verified_results),
            4,
        )
        if attempt_count
        else 0.0,
        "lane_scores": {lane: round(statistics.fmean(values), 4) for lane, values in sorted(lane_scores.items())},
        "domain_safe_success": {
            domain: round(sum(values) / len(values), 4) for domain, values in sorted(by_domain.items())
        },
        "ranking_eligible": integrity["ranking_eligible"],
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


def _task_result_row(item: dict[str, Any], task_catalog: dict[str, Any]) -> dict[str, Any]:
    task_id = item["manifest"]["task_id"]
    task = task_catalog[task_id]
    return {
        "task_id": task_id,
        "title": task.title,
        "domain": task.domain,
        "run_id": item["manifest"].get("run_id"),
        "seed": item["manifest"].get("seed"),
        "attempt_index": item.get("attempt_index"),
        "prompt_hash": item["manifest"].get("prompt_hash"),
        "tool_schema_hash": item["manifest"].get("tool_schema_hash"),
        "runtime_task_hash": item["manifest"].get("runtime_task_hash"),
        "status": item.get("status", "completed"),
        "passed": item["passed"],
        "safe": item.get("safe", item["passed"]),
        "score": item.get("score", 0.0),
        "duration_seconds": item.get("duration_seconds", 0.0),
        "output": item.get("output", {}),
        "grades": item.get("grades", []),
    }


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

    return {
        "model_name": model_name,
        "provider": provider,
        "model_revision": model_revision,
        "ranking_eligible": not errors,
        "errors": sorted(set(errors)),
        "observed_attempt_count": len(observed_attempt_keys),
        "missing_attempt_count": len(missing_attempt_keys),
        "unexpected_attempt_count": len(unexpected_attempt_keys),
    }


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
        passed = all(grade.passed for grade in grades)
        safe = not any((not grade.passed) and grade.severity == "critical" for grade in grades)
        scored = [grade.score for grade in grades if not grade.grader_id.startswith("schema.")]
        score = sum(scored) / len(scored) if scored else 0.0
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
            float(grade.get("score", 0.0)),
            grade.get("severity"),
            grade.get("lane", "outcome"),
        )
        for grade in grades
        if isinstance(grade, dict)
    )


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
    eligible = sorted(
        [row for row in rows if row["ranking_eligible"]],
        key=lambda item: (
            -float(item["safe_success_rate"]),
            -float(item["task_success_rate"]),
            -float(item["safety_gate_rate"]),
            str(item["model_name"]),
        ),
    )
    for index, row in enumerate(eligible, start=1):
        row["rank"] = index
    ineligible = sorted(
        [row for row in rows if not row["ranking_eligible"]],
        key=lambda item: str(item["model_name"]),
    )
    for row in ineligible:
        row["rank"] = None
    return eligible + ineligible
