from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from medphys_agentbench.adapters.ollama import _parse_json_object
from medphys_agentbench.cli import _build_adapter
from medphys_agentbench.json_utils import decode_strict_json_object
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import _assign_outcome_ranks, summarize_release
from medphys_agentbench.runner import (
    SCORING_REVISION,
    grader_hash_for_task,
    prompt_hash_for_task,
    runtime_task_hash_for_task,
    system_prompt_hash,
    tool_schema_hash_for_task,
)
from medphys_agentbench.scoring import (
    grade_numeric_tolerance,
    grade_safety_gate,
    grades_pass,
    grades_safe,
    score_attempt,
    validate_expected_output_shape,
)
from medphys_agentbench.task_loader import load_task


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-1000, max_value=1000),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.text(max_size=16),
        ),
        max_size=6,
    )
)
def test_strict_json_decoder_round_trips_plain_objects(payload: dict[str, object]) -> None:
    encoded = json.dumps(payload)
    assert decode_strict_json_object(encoded) == payload


@pytest.mark.parametrize(
    ("content", "reason_prefix"),
    [
        ('```json\n{"answer_percent": 5}\n```', "invalid_json"),
        ('{"answer_percent": 5} trailing', "trailing_content"),
        ('{"answer_percent": 5, "answer_percent": 6}', "duplicate_key"),
        ('{"answer_percent": NaN}', "non_finite_number"),
        ("[1, 2, 3]", "decoded_type:list"),
    ],
)
def test_ollama_parser_rejects_non_canonical_json(content: str, reason_prefix: str) -> None:
    output, trace = _parse_json_object(content)

    assert output == {}
    assert trace
    assert str(trace[0]["reason"]).startswith(reason_prefix)


def test_ollama_parser_accepts_exact_json_object() -> None:
    output, trace = _parse_json_object('{"answer_percent": 5, "requires_escalation": false}')

    assert output == {"answer_percent": 5, "requires_escalation": False}
    assert trace == []


def test_json_schema_grade_rejects_non_finite_output() -> None:
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml")

    grade = validate_expected_output_shape(
        task,
        {"distance_cm": 100.0, "answer_ratio": float("nan"), "requires_escalation": False, "assumptions": []},
    )

    assert grade.grader_id == "schema.json_schema"
    assert grade.passed is False
    assert grade.severity == "high"


def test_numeric_tolerance_rejects_boolean_actual_value() -> None:
    task = load_task("tasks/dev/physics_units_001/task.yaml")

    grade = grade_numeric_tolerance(task, {"answer_percent": True})

    assert grade.passed is False
    assert grade.severity == "high"


def test_numeric_tolerance_rejects_invalid_authored_tolerance() -> None:
    task = SimpleNamespace(
        grading={"numeric_tolerance": {"field": "answer", "expected": 5.0, "absolute_tolerance": -1.0}},
    )

    grade = grade_numeric_tolerance(task, {"answer": 5.0})

    assert grade.passed is False
    assert grade.severity == "critical"


def test_safety_gate_is_noop_without_declared_contract() -> None:
    grade = grade_safety_gate(SimpleNamespace(safety={}), {})

    assert grade.passed is True
    assert grade.severity == "none"


def _write_result(
    path: Path,
    task,
    model_name: str,
    *,
    attempt_index: int = 0,
    passed: bool = True,
    safe: bool = True,
    include_hashes: bool = True,
) -> None:
    output = _passing_output(task)
    if not safe:
        output["requires_escalation"] = not bool(task.safety.get("requires_escalation", False))
    elif not passed:
        first_grader = task.grading.get("graders", [])[0]
        output[first_grader["field"]] = "deliberately incorrect"
    grades = score_attempt(task, output)
    verified_passed = grades_pass(grades)
    verified_safe = grades_safe(grades)
    payload = {
        "status": "completed",
        "attempt_index": attempt_index,
        "passed": verified_passed,
        "safe": verified_safe,
        "score": 1.0 if verified_passed else 0.0,
        "duration_seconds": 1.0,
        "manifest": {
            "schema_version": "medeval.run.v1",
            "run_id": f"{model_name}-{task.task_id}-{attempt_index}",
            "task_id": task.task_id,
            "task_version": task.version,
            "model": {
                "provider": "ollama",
                "model_name": model_name,
                "model_revision": model_name,
                "harness_name": "medphysbench-ollama",
                "harness_revision": "reference-json-v1",
            },
            "seed": 20260731 + attempt_index,
            "temperature": 0.0,
            "max_tokens": 1024,
            "sandbox_image_digest": "process-isolation-public-v0.2.0",
            "tool_environment_version": "public-fixtures-v0.2.0",
            "prompt_hash": prompt_hash_for_task(task) if include_hashes else "wrong",
            "tool_schema_hash": tool_schema_hash_for_task(task) if include_hashes else "wrong",
            "system_prompt_hash": system_prompt_hash() if include_hashes else "wrong",
            "runtime_task_hash": runtime_task_hash_for_task(task) if include_hashes else "wrong",
            "grader_hash": grader_hash_for_task(task) if include_hashes else "wrong",
            "scoring_revision": SCORING_REVISION,
        },
        "grades": [grade.to_dict() for grade in grades],
        "output": output,
        "trace": [],
        "raw_response": {},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _passing_output(task) -> dict[str, object]:
    schema = task.expected_output_schema
    output: dict[str, object] = {}
    for field in schema.get("required", []):
        field_schema = schema.get("properties", {}).get(field, {})
        raw_types = field_schema.get("type")
        field_types = {raw_types} if isinstance(raw_types, str) else set(raw_types or [])
        if "const" in field_schema:
            output[field] = field_schema["const"]
        elif field_schema.get("enum"):
            output[field] = field_schema["enum"][0]
        elif "boolean" in field_types:
            output[field] = False
        elif field_types & {"number", "integer"}:
            output[field] = 0
        elif "array" in field_types:
            output[field] = []
        else:
            output[field] = "clinical limitation"
    for grader in task.grading.get("graders", []):
        field = grader["field"]
        if grader["type"] in {"exact_match", "numeric_tolerance", "unordered_list_exact_match"}:
            output[field] = grader["expected"]
        elif grader["type"] == "contains_all_strings":
            output[field] = " ".join(grader["expected"])
    if "requires_escalation" in output:
        output["requires_escalation"] = bool(task.safety.get("requires_escalation", False))
    return output


def test_release_summary_regrades_and_rejects_stored_score_tampering(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "tampered-score"
    model_dir.mkdir(parents=True)
    for task in tasks:
        result_file = model_dir / f"{task.task_id}--attempt-1.json"
        _write_result(result_file, task, "tampered-score")
        if task == tasks[0]:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
            payload["output"]["requires_escalation"] = not task.safety.get("requires_escalation", False)
            payload["passed"] = True
            payload["safe"] = True
            result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = summarize_release(release, tmp_path)
    assert summary["models"] == []
    row = summary["unranked_models"][0]
    assert any("stored_grades_disagree_with_regrade" in issue for issue in row["integrity"]["integrity_errors"])
    assert row["safe_success_rate"] == 0.9375


def test_release_summary_demotes_malformed_stored_grade_numbers(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    task = release.load_tasks()[0]
    model_dir = tmp_path / release.release_id / "malformed-grades"
    model_dir.mkdir(parents=True)
    result_file = model_dir / "attempt.json"
    _write_result(result_file, task, "malformed-grades")
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    payload["grades"][0]["score"] = "not-a-number"
    payload["grades"][0]["weight"] = {"invalid": True}
    result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = summarize_release(release, tmp_path)

    assert summary["models"] == []
    row = summary["unranked_models"][0]
    assert row["ranking_eligible"] is False
    assert any("stored_grades_disagree_with_regrade" in issue for issue in row["integrity"]["integrity_errors"])


def test_release_summary_keeps_attempt_outputs_out_of_leaderboard(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    task = release.load_tasks()[0]
    model_dir = tmp_path / release.release_id / "projection-test"
    model_dir.mkdir(parents=True)
    _write_result(model_dir / "attempt.json", task, model_name="projection-test")

    summary = summarize_release(release, tmp_path)
    task_row = summary["unranked_models"][0]["tasks"][0]

    assert "output" not in task_row
    assert "grades" not in task_row
    assert "score" not in task_row
    assert task_row["task_id"] == task.task_id
    assert task_row["runtime_task_hash"]


def test_release_summary_marks_incomplete_run_ineligible(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "partial-model"
    model_dir.mkdir(parents=True)

    for task in tasks[:-1]:
        _write_result(model_dir / f"{task.task_id}--attempt-1.json", task, "partial-model")

    summary = summarize_release(release, tmp_path)
    assert summary["models"] == []
    row = next(item for item in summary["unranked_models"] if item["model_name"] == "partial-model")

    assert row["ranking_eligible"] is False
    assert any("missing_attempts" in issue for issue in row["integrity"]["integrity_errors"])


def test_release_summary_marks_hash_drift_ineligible(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "tampered-model"
    model_dir.mkdir(parents=True)

    for task in tasks:
        _write_result(
            model_dir / f"{task.task_id}--attempt-1.json",
            task,
            "tampered-model",
            include_hashes=(task.task_id != tasks[0].task_id),
        )

    summary = summarize_release(release, tmp_path)
    assert summary["models"] == []
    row = next(item for item in summary["unranked_models"] if item["model_name"] == "tampered-model")

    assert row["ranking_eligible"] is False
    assert any("prompt_hash_mismatch" in issue for issue in row["integrity"]["integrity_errors"])


def test_release_summary_requires_runtime_and_system_hashes(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "missing-runtime-hashes"
    model_dir.mkdir(parents=True)

    for task in tasks:
        result_file = model_dir / f"{task.task_id}--attempt-1.json"
        _write_result(result_file, task, "missing-runtime-hashes")
        payload = json.loads(result_file.read_text(encoding="utf-8"))
        payload["manifest"].pop("runtime_task_hash", None)
        payload["manifest"].pop("system_prompt_hash", None)
        result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = summarize_release(release, tmp_path)
    assert summary["models"] == []
    row = next(item for item in summary["unranked_models"] if item["model_name"] == "missing-runtime-hashes")

    assert row["ranking_eligible"] is False
    assert any("missing_runtime_task_hash" in issue for issue in row["integrity"]["integrity_errors"])
    assert any("missing_system_prompt_hash" in issue for issue in row["integrity"]["integrity_errors"])


def test_release_summary_rejects_mixed_run_configuration(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "mixed-config"
    model_dir.mkdir(parents=True)

    for task in tasks:
        result_file = model_dir / f"{task.task_id}--attempt-1.json"
        _write_result(result_file, task, "mixed-config")
        if task == tasks[0]:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
            payload["manifest"]["temperature"] = 0.25
            result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = summarize_release(release, tmp_path)

    assert summary["models"] == []
    row = summary["unranked_models"][0]
    assert "mixed_run_configuration_manifest" in row["integrity"]["integrity_errors"]


def test_release_summary_never_ranks_provider_error_attempts(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    model_dir = tmp_path / release.release_id / "provider-error"
    model_dir.mkdir(parents=True)

    for task in tasks:
        result_file = model_dir / f"{task.task_id}--attempt-1.json"
        _write_result(result_file, task, "provider-error")
        payload = json.loads(result_file.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "error",
                "error_type": "AdapterError",
                "error": "provider unavailable",
                "passed": False,
                "safe": False,
                "score": 0.0,
                "grades": [],
                "output": {},
            }
        )
        result_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = summarize_release(release, tmp_path)

    assert summary["models"] == []
    row = summary["unranked_models"][0]
    assert row["completed_count"] == 0
    assert "noncompleted_attempts:16" in row["integrity"]["integrity_errors"]


def test_descriptive_outcome_rank_includes_complete_native_rows_without_promoting_official_rank() -> None:
    rows = [
        {
            "model_name": "common",
            "safe_success_rate": 0.6,
            "task_success_rate": 0.6,
            "safety_gate_rate": 1.0,
            "ranking_eligible": True,
            "outcome_order_eligible": True,
        },
        {
            "model_name": "native",
            "safe_success_rate": 0.8,
            "task_success_rate": 0.8,
            "safety_gate_rate": 1.0,
            "ranking_eligible": False,
            "outcome_order_eligible": True,
        },
        {
            "model_name": "incomplete",
            "safe_success_rate": 1.0,
            "task_success_rate": 1.0,
            "safety_gate_rate": 1.0,
            "ranking_eligible": False,
            "outcome_order_eligible": False,
        },
    ]

    _assign_outcome_ranks(rows)

    assert rows[1]["outcome_rank"] == 1
    assert rows[0]["outcome_rank"] == 2
    assert rows[2]["outcome_rank"] is None
    assert rows[1]["ranking_eligible"] is False


def test_validate_release_command_reports_expected_attempt_count() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "validate-release",
            "releases/public_dev_2026_07_31.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["valid"] is True
    assert report["release_id"] == "public-dev-2026-07-31"
    assert report["expected_attempts_per_task"] == 1
    assert report["task_count"] == 16


def test_repository_contracts_and_public_artifacts_validate() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_repository.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    counts = json.loads(completed.stdout)

    assert counts["schema_count"] == 6
    assert counts["release_count"] >= 1
    assert counts["review_evidence_count"] >= 1
    assert counts["task_count"] >= 98
    assert counts["result_count"] >= 120


def test_release_summary_ranks_complete_models(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()
    top_dir = tmp_path / release.release_id / "complete-top"
    base_dir = tmp_path / release.release_id / "complete-base"
    top_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)

    for task in tasks:
        _write_result(top_dir / f"{task.task_id}--attempt-1.json", task, "complete-top")
        _write_result(
            base_dir / f"{task.task_id}--attempt-1.json",
            task,
            "complete-base",
            passed=task.task_id != tasks[0].task_id,
            safe=task.task_id != tasks[0].task_id,
        )

    summary = summarize_release(release, tmp_path)

    assert summary["integrity"]["ranked_model_count"] == 2
    assert summary["release"]["expected_attempts_per_task"] == 1
    assert [row["model_name"] for row in summary["models"]] == ["complete-top", "complete-base"]
    assert summary["models"][0]["rank"] == 1
    assert summary["models"][0]["ranking_eligible"] is True
    assert summary["models"][0]["safe_success_rate"] == 1.0
    assert summary["models"][1]["safe_success_rate"] == 0.9375
    assert all(path.startswith("tasks/") for path in summary["release"]["task_files"])
    assert not any(Path(path).is_absolute() for path in summary["release"]["task_files"])


def test_cli_sampling_contract_reaches_ollama_adapter() -> None:
    adapter = _build_adapter(
        "ollama",
        "fixture-model",
        "http://127.0.0.1:11434",
        99,
        seed=42,
        temperature=0.25,
        max_tokens=777,
    )

    assert adapter.seed == 42
    assert adapter.temperature == 0.25
    assert adapter.max_tokens == 777
    assert adapter.timeout_seconds == 99
    assert adapter.keep_alive == 0
    assert adapter.context_window == 4096
