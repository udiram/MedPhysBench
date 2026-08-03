import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from medphys_agentbench.adapters.recorded import RecordedOutputAdapter
from medphys_agentbench.json_utils import stable_hash
from medphys_agentbench.recorded_capture import sealed_batch_sha256, validate_recorded_batch
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.runner import run_trial
from medphys_agentbench.task_loader import load_task


def test_recorded_adapter_captures_effort_and_never_claims_api_comparability() -> None:
    task = load_task(Path("tasks/public/core_physics/inverse_square_001/task.yaml"))
    output = {
        "dose_rate_mgy_per_min": 3.0,
        "requires_escalation": False,
        "method": "inverse square",
    }
    adapter = RecordedOutputAdapter(
        outputs={task.task_id: output},
        model_name="gpt-5.6-sol",
        model_revision="gpt-5.6-sol@2026-07-31",
        reasoning_effort="high",
    )
    descriptor = adapter.model_descriptor()
    result = adapter.execute(task.runtime_task())
    assert descriptor.provider == "codex-native"
    assert "effort=high" in descriptor.model_name
    assert result.final_output == output
    assert result.trace[0]["comparable_to_api_runs"] is False
    assert result.raw_response["hidden_reasoning_stored"] is False

    trial = run_trial(task, adapter, seed=None, temperature=None, max_tokens=None)
    assert trial.manifest.sandbox_image_digest == "unisolated-codex-native-conversation-surface"
    assert trial.manifest.tool_environment_version == "sealed-batch-no-tools-requested-v1"


def test_export_runtime_cli_contains_no_gold(tmp_path: Path) -> None:
    output = tmp_path / "sealed.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "export-runtime",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = output.read_text(encoding="utf-8")
    assert len(payload["tasks"]) == 5
    assert "minimum_iou" not in serialized
    assert "minimum_dice" not in serialized
    assert "gold_native_display_bbox_xyxy" not in serialized
    assert "grading" not in serialized


def test_recorded_batch_rejects_wrong_sealed_hash(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "export-runtime",
            "releases/public_imaging_pilot_v0_4.yaml",
            "--output",
            str(sealed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    tasks = json.loads(sealed.read_text(encoding="utf-8"))["tasks"]
    recorded = tmp_path / "recorded.json"
    recorded.write_text(
        json.dumps(
            {
                "schema_version": "medphysbench.recorded-batch.v1",
                "model": "test-model",
                "reasoning_effort": "high",
                "sealed_batch_sha256": "0" * 64,
                "outputs": {task["task_id"]: {} for task in tasks},
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "score-recorded-batch",
            "releases/public_imaging_pilot_v0_4.yaml",
            str(recorded),
            "--model",
            "test-model",
            "--model-revision",
            "test-model@1",
            "--reasoning-effort",
            "high",
            "--results-dir",
            str(tmp_path / "results"),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "sealed_batch_sha256 does not match" in completed.stderr


def test_recorded_batch_refuses_to_overwrite_existing_attempts(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    release_file = "releases/public_imaging_pilot_v0_4.yaml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "export-runtime",
            release_file,
            "--output",
            str(sealed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sealed_payload = json.loads(sealed.read_text(encoding="utf-8"))
    recorded = tmp_path / "recorded.json"
    recorded.write_text(
        json.dumps(
            {
                "schema_version": "medphysbench.recorded-batch.v1",
                "model": "immutable-model",
                "reasoning_effort": "high",
                "sealed_batch_sha256": hashlib.sha256(sealed.read_bytes()).hexdigest(),
                "outputs": {task["task_id"]: {} for task in sealed_payload["tasks"]},
            }
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "medphys_agentbench.cli",
        "score-recorded-batch",
        release_file,
        str(recorded),
        "--model",
        "immutable-model",
        "--model-revision",
        "immutable-model@1",
        "--reasoning-effort",
        "high",
        "--results-dir",
        str(tmp_path / "results"),
    ]

    subprocess.run(command, check=True, capture_output=True, text=True)
    repeated = subprocess.run(command, capture_output=True, text=True)

    assert repeated.returncode != 0
    assert "refusing to overwrite" in repeated.stderr


def test_recorded_batch_writes_declared_one_based_attempt_index(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    release_file = "releases/public_imaging_pilot_v0_4.yaml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "export-runtime",
            release_file,
            "--output",
            str(sealed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sealed_payload = json.loads(sealed.read_text(encoding="utf-8"))
    recorded = tmp_path / "recorded.json"
    recorded.write_text(
        json.dumps(
            {
                "schema_version": "medphysbench.recorded-batch.v1",
                "model": "attempt-model",
                "reasoning_effort": "low",
                "sealed_batch_sha256": hashlib.sha256(sealed.read_bytes()).hexdigest(),
                "outputs": {task["task_id"]: {} for task in sealed_payload["tasks"]},
            }
        ),
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "score-recorded-batch",
            release_file,
            str(recorded),
            "--model",
            "attempt-model",
            "--model-revision",
            "attempt-model@2",
            "--reasoning-effort",
            "low",
            "--attempt-index",
            "2",
            "--results-dir",
            str(results_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result_files = sorted(results_dir.rglob("*--attempt-2.json"))
    assert len(result_files) == len(sealed_payload["tasks"])
    assert all(json.loads(path.read_text(encoding="utf-8"))["attempt_index"] == 1 for path in result_files)


def test_recorded_batch_v2_binds_capture_to_attempt_and_result_trace(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    release_file = "releases/public_imaging_pilot_v0_4.yaml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "export-runtime",
            release_file,
            "--output",
            str(sealed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sealed_payload = json.loads(sealed.read_text(encoding="utf-8"))
    outputs = {task["task_id"]: {} for task in sealed_payload["tasks"]}
    capture = _v2_capture(
        release_id="public-imaging-pilot-v0.4",
        sealed_hash=hashlib.sha256(sealed.read_bytes()).hexdigest(),
        outputs=outputs,
        attempt_index=2,
    )
    recorded = tmp_path / "recorded-v2.json"
    recorded.write_text(json.dumps(capture), encoding="utf-8")
    results_dir = tmp_path / "results"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "medphys_agentbench.cli",
            "score-recorded-batch",
            release_file,
            str(recorded),
            "--model",
            "gpt-5.6-terra",
            "--model-revision",
            "gpt-5.6-terra@2026-08-02",
            "--reasoning-effort",
            "high",
            "--attempt-index",
            "2",
            "--results-dir",
            str(results_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(next(results_dir.rglob("*--attempt-2.json")).read_text(encoding="utf-8"))
    assert result["attempt_index"] == 1
    assert result["trace"][0]["capture_id"] == "terra-high-attempt-2"
    assert result["trace"][0]["session_isolation"] == "fresh_context"
    assert result["raw_response"]["capture_schema_version"] == "medphysbench.recorded-batch.v2"
    assert result["manifest"]["model"]["harness_revision"] == "codex-native-pilot-v2;effort=high"
    assert result["manifest"]["adapter_settings"]["task_delivery_mode"] == "sealed_runtime_batch"
    assert result["manifest"]["tool_environment_version"] == "sealed-batch-recorded-capture-v2"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda batch: batch.update(outputs_sha256="0" * 64), "outputs_sha256"),
        (lambda batch: batch.update(model_revision="other@1"), "model_revision"),
        (lambda batch: batch.update(attempt_index=2), "attempt_index"),
        (
            lambda batch: batch["capture"].update(session_isolation="shared_context"),
            "fresh_context",
        ),
        (
            lambda batch: batch["capture"].update(finished_at="2026-08-02T11:59:59Z"),
            "started_at <= finished_at",
        ),
        (
            lambda batch: batch["capture"].update(surface="ollama"),
            "capture.surface=codex-native",
        ),
        (
            lambda batch: batch["capture"].update(started_at="2026-08-02T12:00:00"),
            "timezone offset",
        ),
        (
            lambda batch: batch["capture"]["tools_used"].append("shell"),
            "unsupported tools",
        ),
    ],
)
def test_recorded_batch_v2_rejects_provenance_tampering(mutation, message: str) -> None:
    release = load_release(Path("releases/public_imaging_pilot_v0_4.yaml"))
    tasks = release.load_tasks()
    outputs = {task.task_id: {} for task in tasks}
    capture = _v2_capture(
        release_id=release.release_id,
        sealed_hash=sealed_batch_sha256(release.release_id, tasks),
        outputs=outputs,
        attempt_index=1,
    )
    mutation(capture)

    with pytest.raises(ValueError, match=message):
        validate_recorded_batch(
            capture,
            release_id=release.release_id,
            tasks=tasks,
            model="gpt-5.6-terra",
            model_revision="gpt-5.6-terra@2026-08-02",
            reasoning_effort="high",
            attempt_index=1,
        )


def _v2_capture(
    *, release_id: str, sealed_hash: str, outputs: dict[str, dict], attempt_index: int
) -> dict:
    return {
        "schema_version": "medphysbench.recorded-batch.v2",
        "release_id": release_id,
        "sealed_batch_sha256": sealed_hash,
        "model": "gpt-5.6-terra",
        "model_revision": "gpt-5.6-terra@2026-08-02",
        "reasoning_effort": "high",
        "attempt_index": attempt_index,
        "outputs_sha256": stable_hash(outputs),
        "capture": {
            "capture_id": f"terra-high-attempt-{attempt_index}",
            "surface": "codex-native",
            "started_at": "2026-08-02T12:00:00Z",
            "finished_at": "2026-08-02T12:01:00Z",
            "session_isolation": "fresh_context",
            "task_delivery_mode": "sealed_runtime_batch",
            "response_capture": "final_json_only",
            "tools_used": ["read_sealed_batch", "view_image"],
            "hidden_reasoning_stored": False,
        },
        "outputs": outputs,
    }
