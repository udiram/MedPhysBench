"""Frozen reference-harness prompt construction."""

from __future__ import annotations

import json

from .contracts import RuntimeTask

SYSTEM_PROMPT = """You are being evaluated by MedPhysBench.
Complete only the supplied synthetic or public medical-physics task.
Return one JSON object matching the requested schema and no other text.
Do not claim clinical authority. If the task is underspecified, unsafe, patient-specific,
or requires a local policy that is not supplied, set requires_escalation to true and state why.
Use only the visible task payload. You cannot see the graders or reference answer."""


def build_user_prompt(task: RuntimeTask) -> str:
    payload = {
        "task_id": task.task_id,
        "title": task.title,
        "domain": task.domain,
        "track": task.track,
        "risk_tier": task.risk_tier.value,
        "instructions": task.instructions,
        "input_payload": task.input_payload,
        "context_artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "media_type": artifact.media_type,
                "title": artifact.title,
                "description": artifact.description,
                "content": artifact.content,
            }
            for artifact in task.context_artifacts
        ],
        "expected_output_schema": task.expected_output_schema,
        "safety": task.safety,
        "stop_conditions": task.stop_conditions,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
