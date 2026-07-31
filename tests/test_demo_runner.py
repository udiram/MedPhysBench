from pathlib import Path

from medphys_agentbench.adapters.reference import DevelopmentReferenceAgent
from medphys_agentbench.runner import run_trial
from medphys_agentbench.task_loader import load_task

TASK_FILE = Path("tasks/dev/physics_units_001/task.yaml")


def test_demo_reference_agent_passes_all_deterministic_grades() -> None:
    task = load_task(TASK_FILE)
    output = task.grading["development_reference_output"]
    result = run_trial(task, DevelopmentReferenceAgent(output=output))

    assert result.passed
    assert result.output["answer_percent"] == 5.0
    assert result.manifest.schema_version == "medeval.run.v1"
    assert {grade.grader_id for grade in result.grades} == {
        "schema.json_schema",
        "safety.escalation",
        "numeric_tolerance",
    }
