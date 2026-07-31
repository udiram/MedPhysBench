"""Task-pack loading and first-line contract validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .contracts import ContractError, TaskSpec


def load_task(task_file: str | Path) -> TaskSpec:
    path = Path(task_file)
    if not path.is_file():
        raise FileNotFoundError(f"Task file does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        raw: Any = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ContractError("Task file must contain a YAML mapping at the document root.")
    return TaskSpec.from_dict(raw)


def discover_tasks(root: str | Path) -> list[Path]:
    path = Path(root)
    if path.is_file():
        return [path]
    return sorted(path.glob("**/task.yaml"))
