import json
import subprocess
import sys
from pathlib import Path

from medphys_agentbench.adapters.recorded import RecordedOutputAdapter
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
