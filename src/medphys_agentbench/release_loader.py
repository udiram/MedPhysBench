"""Benchmark release loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .contracts import AccessClass, ContractError, TaskSpec
from .task_loader import load_task


@dataclass(frozen=True)
class BenchmarkRelease:
    schema_version: str
    release_id: str
    title: str
    description: str
    task_files: tuple[Path, ...]
    allow_access_classes: tuple[AccessClass, ...]
    expected_attempts_per_task: int = 1

    def load_tasks(self) -> tuple[TaskSpec, ...]:
        tasks = tuple(load_task(path) for path in self.task_files)
        task_ids = [task.task_id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            duplicates = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
            raise ContractError(f"Release {self.release_id!r} contains duplicate task IDs: {duplicates}.")
        for task in tasks:
            if task.access_class not in self.allow_access_classes:
                raise ContractError(
                    f"Task {task.task_id} has access_class {task.access_class.value!r}, "
                    f"which is not permitted in release {self.release_id!r}."
                )
        return tasks


def load_release(release_file: str | Path) -> BenchmarkRelease:
    path = Path(release_file)
    with path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ContractError("Release file must contain a YAML mapping at the document root.")
    required = ("schema_version", "release_id", "title", "description", "task_files")
    for key in required:
        if key not in raw:
            raise ContractError(f"release is missing required field {key!r}.")
    if raw["schema_version"] != "medeval.release.v1":
        raise ContractError(
            f"Unsupported release schema_version {raw['schema_version']!r}; expected 'medeval.release.v1'."
        )

    task_files_raw = raw["task_files"]
    if not isinstance(task_files_raw, list) or not task_files_raw:
        raise ContractError("release.task_files must be a non-empty list.")
    task_files = tuple((path.parent / item).resolve() for item in task_files_raw)
    if len(task_files) != len(set(task_files)):
        raise ContractError(f"Release {raw['release_id']!r} contains duplicate task_files entries.")
    allow_raw = raw.get("allow_access_classes", ["public"])
    if not isinstance(allow_raw, list) or not allow_raw:
        raise ContractError("release.allow_access_classes must be a non-empty list when present.")
    allow_access_classes = tuple(AccessClass(item) for item in allow_raw)
    expected_attempts_per_task = int(raw.get("expected_attempts_per_task", 1))
    if expected_attempts_per_task < 1:
        raise ContractError("release.expected_attempts_per_task must be a positive integer.")

    return BenchmarkRelease(
        schema_version=str(raw["schema_version"]),
        release_id=str(raw["release_id"]),
        title=str(raw["title"]),
        description=str(raw["description"]),
        task_files=task_files,
        allow_access_classes=allow_access_classes,
        expected_attempts_per_task=expected_attempts_per_task,
    )
