from pathlib import Path

from medphys_agentbench.adapters.reference import DevelopmentReferenceAgent
from medphys_agentbench.runner import run_trial, system_prompt_hash
from medphys_agentbench.task_loader import load_task

TASK_FILE = Path("tasks/dev/physics_units_001/task.yaml")


def test_demo_reference_agent_passes_all_deterministic_grades() -> None:
    task = load_task(TASK_FILE)
    output = task.grading["development_reference_output"]
    result = run_trial(task, DevelopmentReferenceAgent(output=output))

    assert result.passed
    assert result.output["answer_percent"] == 5.0
    assert result.manifest.schema_version == "medeval.run.v2"
    assert result.manifest.adapter_settings["endpoint_kind"] == "development_reference"
    assert len(result.manifest.adapter_settings_hash) == 64
    assert result.manifest.system_prompt_hash == system_prompt_hash()
    assert len(result.manifest.prompt_hash) == 64
    assert len(result.manifest.tool_schema_hash) == 64
    assert len(result.manifest.runtime_task_hash) == 64
    assert len(result.manifest.grader_hash) == 64
    assert result.manifest.scoring_revision == "deterministic-v2-safety-lanes"
    assert {grade.grader_id for grade in result.grades} == {
        "schema.json_schema",
        "safety.escalation",
        "numeric_tolerance",
    }
