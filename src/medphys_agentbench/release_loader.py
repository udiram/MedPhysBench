"""Benchmark release loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .contracts import AccessClass, ContractError, TaskSpec
from .task_loader import load_task

REPOSITORY_TASKS_ROOT = (Path(__file__).resolve().parents[2] / "tasks").resolve()


@dataclass(frozen=True)
class BenchmarkRelease:
    schema_version: str
    release_id: str
    title: str
    description: str
    task_files: tuple[Path, ...]
    allow_access_classes: tuple[AccessClass, ...]
    expected_attempts_per_task: int = 1
    integrity_profile: str = "development"
    public_attempt_detail: str = "aggregate_only"

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
        if self.integrity_profile in {"pilot", "comparison"}:
            missing_family_ids = sorted(task.task_id for task in tasks if not task.family_id)
            if missing_family_ids:
                raise ContractError(
                    f"Release {self.release_id!r} uses integrity_profile {self.integrity_profile!r} "
                    f"but tasks lack family_id: {missing_family_ids}."
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
    escaped_task_files = [task_file for task_file in task_files if not task_file.is_relative_to(REPOSITORY_TASKS_ROOT)]
    if escaped_task_files:
        raise ContractError(
            "release.task_files entries must resolve inside the repository tasks directory; "
            f"rejected {escaped_task_files[0]}."
        )
    if len(task_files) != len(set(task_files)):
        raise ContractError(f"Release {raw['release_id']!r} contains duplicate task_files entries.")
    allow_raw = raw.get("allow_access_classes", ["public"])
    if not isinstance(allow_raw, list) or not allow_raw:
        raise ContractError("release.allow_access_classes must be a non-empty list when present.")
    allow_access_classes = tuple(AccessClass(item) for item in allow_raw)
    expected_attempts_per_task = int(raw.get("expected_attempts_per_task", 1))
    if expected_attempts_per_task < 1:
        raise ContractError("release.expected_attempts_per_task must be a positive integer.")
    integrity_profile = str(raw.get("integrity_profile", "development"))
    minimum_attempts = {"development": 1, "pilot": 3, "comparison": 5}
    if integrity_profile not in minimum_attempts:
        raise ContractError("release.integrity_profile must be development, pilot, or comparison.")
    if expected_attempts_per_task < minimum_attempts[integrity_profile]:
        raise ContractError(
            f"release.integrity_profile {integrity_profile!r} requires at least "
            f"{minimum_attempts[integrity_profile]} attempts per task."
        )
    public_attempt_detail = str(raw.get("public_attempt_detail", "aggregate_only"))
    if public_attempt_detail not in {"aggregate_only", "sanitized_output"}:
        raise ContractError(
            "release.public_attempt_detail must be aggregate_only or sanitized_output."
        )
    if public_attempt_detail == "sanitized_output" and any(
        access_class is not AccessClass.PUBLIC for access_class in allow_access_classes
    ):
        raise ContractError(
            "release.public_attempt_detail may expose sanitized outputs only when every "
            "allowed access class is public."
        )
    if public_attempt_detail == "sanitized_output" and integrity_profile == "comparison":
        raise ContractError(
            "release.public_attempt_detail cannot expose answers for a comparison-profile release."
        )

    return BenchmarkRelease(
        schema_version=str(raw["schema_version"]),
        release_id=str(raw["release_id"]),
        title=str(raw["title"]),
        description=str(raw["description"]),
        task_files=task_files,
        allow_access_classes=allow_access_classes,
        expected_attempts_per_task=expected_attempts_per_task,
        integrity_profile=integrity_profile,
        public_attempt_detail=public_attempt_detail,
    )
