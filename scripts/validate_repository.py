#!/usr/bin/env python3
"""Validate every public contract and artifact shipped by the repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from medphys_agentbench.json_utils import decode_strict_json_object
from medphys_agentbench.task_loader import load_task

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
FORBIDDEN_RUNTIME_FIELDS = {"grading", "provenance", "access_class", "contamination_tags"}


def _load_json(path: Path) -> dict[str, Any]:
    return decode_strict_json_object(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a mapping at the document root")
    return payload


def _validator(name: str) -> Draft202012Validator:
    schema = _load_json(SCHEMA_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(validator: Draft202012Validator, payload: Any, path: Path) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    details = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        details.append(f"{path}:{location}: {error.message}")
    raise ValueError("\n".join(details))


def validate_repository() -> dict[str, int]:
    validators = {
        "task": _validator("task.v1.schema.json"),
        "runtime": _validator("runtime-task.v1.schema.json"),
        "run": _validator("run.v1.schema.json"),
        "result": _validator("result.v1.schema.json"),
        "release": _validator("release.v1.schema.json"),
    }

    release_paths = sorted((ROOT / "releases").glob("*.yaml"))
    for path in release_paths:
        _validate(validators["release"], _load_yaml(path), path)

    task_paths = sorted((ROOT / "tasks").rglob("task.yaml"))
    for path in task_paths:
        _validate(validators["task"], _load_yaml(path), path)
        runtime = json.loads(json.dumps(load_task(path).runtime_task().to_dict()))
        leaked = FORBIDDEN_RUNTIME_FIELDS.intersection(runtime)
        if leaked:
            raise ValueError(f"{path}: runtime projection leaks forbidden fields: {sorted(leaked)}")
        _validate(validators["runtime"], runtime, path)

    result_paths = sorted((ROOT / "results" / "releases").glob("*/*/*.json"))
    for path in result_paths:
        payload = _load_json(path)
        _validate(validators["result"], payload, path)
        _validate(validators["run"], payload.get("manifest"), path)

    return {
        "schema_count": len(validators),
        "release_count": len(release_paths),
        "task_count": len(task_paths),
        "result_count": len(result_paths),
    }


def main() -> None:
    counts = validate_repository()
    print(json.dumps({"valid": True, **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
