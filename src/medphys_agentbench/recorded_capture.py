"""Validation helpers for sealed, non-API recorded-output captures."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from typing import Any

from .contracts import TaskSpec
from .json_utils import stable_hash
from .prompting import SYSTEM_PROMPT

RECORDED_BATCH_V1 = "medphysbench.recorded-batch.v1"
RECORDED_BATCH_V2 = "medphysbench.recorded-batch.v2"
RECORDED_CAPTURE_TOOLS = frozenset({"read_sealed_batch", "view_image"})


def sealed_batch_payload(release_id: str, tasks: list[TaskSpec]) -> dict[str, object]:
    return {
        "schema_version": "medphysbench.sealed-batch.v1",
        "release_id": release_id,
        "system_prompt": SYSTEM_PROMPT,
        "tasks": [task.runtime_task().to_dict() for task in tasks],
    }


def sealed_batch_sha256(release_id: str, tasks: list[TaskSpec]) -> str:
    payload = sealed_batch_payload(release_id, tasks)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return sha256(serialized.encode("utf-8")).hexdigest()


def validate_recorded_batch(
    batch: dict[str, Any],
    *,
    release_id: str,
    tasks: list[TaskSpec],
    model: str,
    model_revision: str,
    reasoning_effort: str,
    attempt_index: int,
) -> dict[str, Any] | None:
    """Validate a capture and return its public capture metadata when present."""

    outputs = batch.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Recorded batch must contain an object named 'outputs'.")

    expected_ids = {task.task_id for task in tasks}
    actual_ids = set(outputs)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ValueError(f"Recorded batch task IDs mismatch; missing={missing}, extra={extra}.")
    if not all(isinstance(output, dict) for output in outputs.values()):
        raise ValueError("Every recorded task output must be a JSON object.")

    expected_hash = sealed_batch_sha256(release_id, tasks)
    if batch.get("sealed_batch_sha256") != expected_hash:
        raise ValueError("Recorded batch sealed_batch_sha256 does not match this release runtime.")
    if batch.get("model") != model or batch.get("reasoning_effort") != reasoning_effort:
        raise ValueError("Recorded batch model or reasoning_effort does not match CLI declarations.")

    schema_version = batch.get("schema_version")
    if schema_version == RECORDED_BATCH_V1:
        return None
    if schema_version != RECORDED_BATCH_V2:
        raise ValueError(f"Unsupported recorded batch schema_version {schema_version!r}.")

    if batch.get("release_id") != release_id:
        raise ValueError("Recorded batch release_id does not match the selected release.")
    if batch.get("model_revision") != model_revision:
        raise ValueError("Recorded batch model_revision does not match the CLI declaration.")
    if batch.get("attempt_index") != attempt_index:
        raise ValueError("Recorded batch attempt_index does not match --attempt-index.")
    if batch.get("outputs_sha256") != stable_hash(outputs):
        raise ValueError("Recorded batch outputs_sha256 does not match outputs.")

    capture = batch.get("capture")
    if not isinstance(capture, dict):
        raise ValueError("Recorded batch v2 requires capture metadata.")
    capture_id = capture.get("capture_id")
    if not isinstance(capture_id, str) or not capture_id.strip():
        raise ValueError("Recorded batch v2 requires a non-empty capture.capture_id.")
    if capture.get("surface") != "codex-native":
        raise ValueError("Recorded batch v2 requires capture.surface=codex-native.")
    started = _parse_timestamp(capture.get("started_at"), "capture.started_at")
    finished = _parse_timestamp(capture.get("finished_at"), "capture.finished_at")
    if finished < started:
        raise ValueError("Recorded capture timestamps must satisfy started_at <= finished_at.")
    if capture.get("session_isolation") != "fresh_context":
        raise ValueError("Recorded batch v2 requires fresh_context session isolation.")
    if capture.get("task_delivery_mode") != "sealed_runtime_batch":
        raise ValueError("Recorded batch v2 requires sealed_runtime_batch task delivery.")
    if capture.get("response_capture") != "final_json_only":
        raise ValueError("Recorded batch v2 requires final_json_only response capture.")
    if capture.get("hidden_reasoning_stored") is not False:
        raise ValueError("Recorded batch v2 must declare hidden_reasoning_stored=false.")
    tools_used = capture.get("tools_used")
    if not isinstance(tools_used, list) or not all(isinstance(tool, str) for tool in tools_used):
        raise ValueError("Recorded batch v2 capture.tools_used must be a string array.")
    if len(tools_used) != len(set(tools_used)):
        raise ValueError("Recorded batch v2 capture.tools_used must not contain duplicates.")
    unsupported_tools = sorted(set(tools_used) - RECORDED_CAPTURE_TOOLS)
    if unsupported_tools:
        raise ValueError(f"Recorded batch v2 capture.tools_used contains unsupported tools: {unsupported_tools}.")
    return dict(capture)


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset.")
    return parsed
