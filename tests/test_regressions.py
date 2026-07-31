from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from medphys_agentbench.adapters.ollama import _parse_json_object
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release
from medphys_agentbench.scoring import grade_safety_gate, score_attempt, validate_expected_output_shape
from medphys_agentbench.task_loader import load_task


def test_ollama_parser_extracts_fenced_json_and_succeeds() -> None:
    content = """```json
{"answer_percent": 5, "requires_escalation": false}
```"""

    output, parse_trace = _parse_json_object(content)

    assert output == {"answer_percent": 5, "requires_escalation": False}
    assert parse_trace == []


def test_ollama_parser_repair_finds_first_json_object_in_noisy_content() -> None:
    content = "Here is my result:\n```text\nignore this line\n{\"answer_percent\": 4.99}\n```\n"

    output, parse_trace = _parse_json_object(content)

    assert output == {"answer_percent": 4.99}
    assert parse_trace == []


def test_ollama_parser_rejects_non_dict_content() -> None:
    output, parse_trace = _parse_json_object("[1, 2, 3]")

    assert output == {}
    assert parse_trace == [
        {
            "event": "structured_output_parse_failed",
            "reason": "decoded_type:list",
            "raw_preview": "[1, 2, 3]",
        }
    ]


def test_json_schema_grade_fails_on_invalid_output_shape() -> None:
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml")

    output = {"dose_rate_mgy_per_min": 3.0}
    grade = validate_expected_output_shape(task, output)

    assert grade.grader_id == "schema.json_schema"
    assert grade.passed is False
    assert grade.score == 0.0
    assert grade.severity == "high"


def test_safety_escalation_gate_enforces_required_bool() -> None:
    task = load_task("tasks/public/core_physics/inverse_square_001/task.yaml")

    pass_grade = grade_safety_gate(task, {"requires_escalation": False})
    fail_grade = grade_safety_gate(task, {"requires_escalation": True})

    assert pass_grade.passed is True
    assert pass_grade.score == 1.0
    assert pass_grade.severity == "none"

    assert fail_grade.passed is False
    assert fail_grade.score == 0.0
    assert fail_grade.severity == "critical"


def test_safety_gate_is_noop_without_declared_contract() -> None:
    task = SimpleNamespace(safety={})

    grade = grade_safety_gate(task, {})

    assert grade.passed is True
    assert grade.severity == "none"


def _write_result(path: Path, task_id: str, model_name: str, *, passed: bool, safe: bool) -> None:
    model = {
        "provider": "ollama",
        "model_name": model_name,
        "model_revision": "local",
        "harness_name": "medphysbench-ollama",
        "harness_revision": "reference-json-v1",
    }

    payload = {
        "status": "completed",
        "passed": passed,
        "safe": safe,
        "attempt_index": 0,
        "duration_seconds": 1.0,
        "manifest": {
            "schema_version": "medeval.run.v1",
            "task_id": task_id,
            "task_version": "0.2.0",
            "model": model,
            "seed": 20260731,
            "temperature": 0.0,
            "max_tokens": 1024,
        },
        "grades": [
            {
                "grader_id": "schema.json_schema",
                "passed": True,
                "score": 1.0,
                "severity": "none",
                "rationale": "schema",
                "evidence": {},
                "lane": "artifact",
            },
            {
                "grader_id": "safety.escalation",
                "passed": safe,
                "score": 1.0 if safe else 0.0,
                "severity": "none" if safe else "critical",
                "rationale": "safety",
                "evidence": {},
                "lane": "safety",
            },
        ],
        "output": {},
        "trace": [],
        "raw_response": {},
    }

    if not passed:
        payload["grades"][0]["passed"] = False
        payload["grades"][0]["score"] = 0.0
        payload["grades"][0]["severity"] = "high"

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_release_summary_reports_wilson_ci_and_ranking(tmp_path: Path) -> None:
    release = load_release("releases/public_dev_2026_07_31.yaml")
    tasks = release.load_tasks()

    top_model = "bench-top"
    baseline_model = "bench-baseline"
    top_dir = tmp_path / release.release_id / top_model
    baseline_dir = tmp_path / release.release_id / baseline_model
    top_dir.mkdir(parents=True)
    baseline_dir.mkdir(parents=True)

    _write_result(top_dir / f"{tasks[0].task_id}--attempt-1.json", tasks[0].task_id, top_model, passed=True, safe=True)
    _write_result(top_dir / f"{tasks[1].task_id}--attempt-2.json", tasks[1].task_id, top_model, passed=True, safe=True)

    _write_result(
        baseline_dir / f"{tasks[0].task_id}--attempt-1.json", tasks[0].task_id, baseline_model, passed=False, safe=False
    )
    _write_result(
        baseline_dir / f"{tasks[1].task_id}--attempt-2.json", tasks[1].task_id, baseline_model, passed=True, safe=True
    )

    summary = summarize_release(release, tmp_path)

    assert len(summary["tasks"]) == 16
    models = summary["models"]
    assert [row["model_name"] for row in models] == [top_model, baseline_model]

    top = models[0]
    baseline = models[1]

    assert top["safe_success_rate"] == 1.0
    assert baseline["safe_success_rate"] == 0.5

    ci_low, ci_high = baseline["task_success_ci95"]
    assert 0 <= ci_low <= 0.5 <= ci_high <= 1


def test_validate_release_command_reports_sixteen_public_tasks() -> None:
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
    assert report["task_count"] == 16
    assert len(report["task_ids"]) == 16


def test_score_attempt_picks_deterministic_gates_for_dev_task() -> None:
    task = load_task("tasks/dev/physics_units_001/task.yaml")
    output = task.grading["development_reference_output"]

    grades = score_attempt(task, output)
    ids = {grade.grader_id for grade in grades}

    assert ids == {"schema.json_schema", "safety.escalation", "numeric_tolerance"}
