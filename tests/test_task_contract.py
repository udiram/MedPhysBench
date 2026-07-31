import json
import subprocess
import sys
from pathlib import Path

from medphys_agentbench.contracts import AccessClass, RiskTier
from medphys_agentbench.task_loader import load_task

TASK_FILE = Path("tasks/dev/physics_units_001/task.yaml")


def test_development_task_loads_with_a_complete_contract() -> None:
    task = load_task(TASK_FILE)

    assert task.schema_version == "medeval.task.v1"
    assert task.risk_tier is RiskTier.LOW
    assert task.access_class is AccessClass.PUBLIC
    assert task.expected_output_schema["required"] == [
        "answer_percent",
        "requires_escalation",
        "assumptions",
    ]


def test_runtime_task_cannot_see_grading_or_provenance() -> None:
    runtime = load_task(TASK_FILE).runtime_task().to_dict()

    assert "grading" not in runtime
    assert "provenance" not in runtime
    assert runtime["task_id"] == "dev.physics.units-001"


def test_validate_cli_never_prints_grading_material() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "medphys_agentbench.cli", "validate", str(TASK_FILE)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)

    assert report["valid"] is True
    assert "grading" not in completed.stdout
    assert "provenance" not in completed.stdout
