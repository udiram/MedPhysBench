"""Build the public, runtime-visible task-input catalog used by the website.

The catalog deliberately reuses ``TaskSpec.runtime_task()`` so the web surface
cannot drift into publishing authoring-only grading, gold, or provenance data.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .contracts import AccessClass
from .release_loader import load_release
from .runner import runtime_task_hash_for_task

SCHEMA_VERSION = "medphysbench.public-task-inputs.v1"
RUNTIME_KEYS = {
    "schema_version",
    "task_id",
    "version",
    "title",
    "domain",
    "track",
    "risk_tier",
    "instructions",
    "input_payload",
    "context_artifacts",
    "allowed_tools",
    "expected_output_schema",
    "safety",
    "stop_conditions",
}


def build_public_task_input_catalog(release_paths: Iterable[str | Path]) -> dict[str, Any]:
    """Return a deterministic catalog containing only sealed runtime task views."""

    releases: list[dict[str, Any]] = []
    seen_release_ids: set[str] = set()
    for release_path in release_paths:
        release = load_release(release_path)
        if release.release_id in seen_release_ids:
            raise ValueError(f"Duplicate release_id in public task input catalog: {release.release_id}")
        seen_release_ids.add(release.release_id)

        task_entries: list[dict[str, Any]] = []
        for task in release.load_tasks():
            if task.access_class is not AccessClass.PUBLIC:
                raise ValueError(
                    f"Public task input catalog cannot expose {task.task_id!r} with "
                    f"access_class {task.access_class.value!r}."
                )
            runtime_task = json.loads(json.dumps(task.runtime_task().to_dict()))
            if set(runtime_task) != RUNTIME_KEYS:
                missing = sorted(RUNTIME_KEYS.difference(runtime_task))
                extra = sorted(set(runtime_task).difference(RUNTIME_KEYS))
                raise ValueError(
                    f"Runtime projection keys drifted for {task.task_id}; missing={missing}, extra={extra}."
                )
            task_entries.append(
                {
                    "task_id": task.task_id,
                    "runtime_task_hash": runtime_task_hash_for_task(task),
                    "runtime_task": runtime_task,
                }
            )

        releases.append(
            {
                "release_id": release.release_id,
                "tasks": sorted(task_entries, key=lambda entry: entry["task_id"]),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "releases": sorted(releases, key=lambda entry: entry["release_id"]),
    }
