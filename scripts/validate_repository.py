#!/usr/bin/env python3
"""Validate every public contract and artifact shipped by the repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from medphys_agentbench.artifacts import resolve_asset_reference
from medphys_agentbench.json_utils import decode_strict_json_object
from medphys_agentbench.scoring import score_attempt
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
        task = load_task(path)
        runtime = json.loads(json.dumps(task.runtime_task().to_dict()))
        leaked = FORBIDDEN_RUNTIME_FIELDS.intersection(runtime)
        if leaked:
            raise ValueError(f"{path}: runtime projection leaks forbidden fields: {sorted(leaked)}")
        _validate(validators["runtime"], runtime, path)
        for artifact in task.context_artifacts:
            if artifact.content.startswith("asset://"):
                resolve_asset_reference(artifact.content, ROOT)
            elif artifact.media_type.startswith("image/"):
                raise ValueError(f"{path}: image artifacts must use hash-pinned asset:// references")
        reference_output = _reference_output(task.expected_output_schema, task.grading, task.safety)
        failed = [grade for grade in score_attempt(task, reference_output) if not grade.passed]
        if failed:
            rationales = "; ".join(f"{grade.grader_id}: {grade.rationale}" for grade in failed)
            raise ValueError(f"{path}: authored graders reject their constructed reference: {rationales}")

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


def _reference_output(
    schema: dict[str, Any], grading: dict[str, Any], safety: dict[str, Any]
) -> dict[str, Any]:
    output = _schema_placeholder(schema)
    if not isinstance(output, dict):
        raise ValueError("Expected-output schema must construct an object.")
    for grader in grading.get("graders", []):
        if not isinstance(grader, dict) or "field" not in grader:
            continue
        field = str(grader["field"])
        grader_type = grader.get("type")
        if grader_type == "contains_all_strings":
            output[field] = " ".join(str(item) for item in grader.get("expected", []))
        elif "expected" in grader:
            output[field] = grader["expected"]
    legacy_numeric = grading.get("numeric_tolerance")
    if isinstance(legacy_numeric, dict):
        output[str(legacy_numeric.get("field", "answer"))] = legacy_numeric["expected"]
    if "requires_escalation" in safety:
        output["requires_escalation"] = safety["requires_escalation"]
    return output


def _schema_placeholder(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema["const"]
    if schema.get("enum"):
        return schema["enum"][0]
    for combinator in ("oneOf", "anyOf"):
        choices = schema.get(combinator)
        if isinstance(choices, list) and choices:
            return _schema_placeholder(choices[0])
    schema_type = schema.get("type", "object")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "null")
    if schema_type == "object":
        properties = schema.get("properties", {})
        return {
            field: _schema_placeholder(properties.get(field, {}))
            for field in schema.get("required", [])
        }
    if schema_type == "array":
        minimum = int(schema.get("minItems", 0))
        return [_schema_placeholder(schema.get("items", {})) for _ in range(minimum)]
    if schema_type == "string":
        minimum = max(1, int(schema.get("minLength", 0)))
        value = "reference" if minimum <= 9 else "r" * minimum
        return value[: int(schema.get("maxLength", len(value)))]
    if schema_type == "integer":
        return int(schema.get("minimum", 0))
    if schema_type == "number":
        return float(schema.get("minimum", 0.0))
    if schema_type == "boolean":
        return False
    return None


def main() -> None:
    counts = validate_repository()
    print(json.dumps({"valid": True, **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
