#!/usr/bin/env python3
"""Validate every public contract and artifact shipped by the repository."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from medphys_agentbench.artifacts import resolve_asset_reference
from medphys_agentbench.campaign import load_campaign
from medphys_agentbench.json_utils import decode_strict_json_object, stable_hash
from medphys_agentbench.qualification import (
    load_access_entries,
    validate_attested_q2_qualification,
)
from medphys_agentbench.recorded_capture import validate_recorded_batch
from medphys_agentbench.release_loader import load_release
from medphys_agentbench.route_qualification import load_route_set
from medphys_agentbench.runner import adapter_runtime_settings
from medphys_agentbench.scoring import score_attempt
from medphys_agentbench.task_loader import load_task
from medphys_agentbench.validation import validate_grader_mutations

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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


def _validate_review_evidence_semantics(payload: dict[str, Any], path: Path) -> None:
    release_id = str(payload["release_id"])
    for field in ("independent_domain_review", "human_baseline"):
        state = payload[field]
        completed = int(state["completed"])
        target = int(state["target"])
        if completed > target:
            raise ValueError(f"{path}:{field}: completed cannot exceed target.")
        if state["status"] != "complete":
            continue
        if completed != target:
            raise ValueError(f"{path}:{field}: complete status requires completed == target.")
        if state["matched_release_id"] != release_id:
            raise ValueError(f"{path}:{field}: matched_release_id must equal release_id.")
        for artifact in state["evidence_artifacts"]:
            artifact_path = Path(str(artifact["path"]))
            if artifact_path.is_absolute():
                raise ValueError(f"{path}:{field}: evidence artifact paths must be repository-relative.")
            resolved = (ROOT / artifact_path).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
                raise ValueError(f"{path}:{field}: evidence artifact is missing or outside the repository.")
            observed_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if observed_hash != artifact["sha256"]:
                raise ValueError(f"{path}:{field}: evidence artifact hash mismatch for {artifact_path}.")

    if payload["release_status"] == "reviewed":
        if payload["independent_domain_review"]["status"] != "complete":
            raise ValueError(f"{path}: reviewed release requires complete independent domain review.")
        if payload["data_rights_review"]["status"] != "documented":
            raise ValueError(f"{path}: reviewed release requires documented data-rights review.")
        if any(item["domain_review"] != "approved" for item in payload["task_reviews"]):
            raise ValueError(f"{path}: reviewed release requires every task review to be approved.")


def _validate_task_grading_semantics(payload: dict[str, Any], path: Path) -> None:
    version_parts = tuple(int(part) for part in str(payload["version"]).split(".")[:3])
    required_fields = set(payload["expected_output_schema"].get("required", []))
    if version_parts < (0, 7, 0) or "limitations" not in required_fields:
        return
    graders = payload["grading"].get("graders", [])
    limitations_graders = [grader for grader in graders if grader.get("field") == "limitations"]
    if not limitations_graders:
        raise ValueError(f"{path}: v0.7+ tasks requiring limitations must declare an explicit limitations grader.")
    if not any(bool(grader.get("required_for_pass", True)) for grader in limitations_graders):
        raise ValueError(f"{path}: at least one limitations grader must be required for pass.")


def _validate_defect_ledger_semantics(
    payload: dict[str, Any],
    path: Path,
    releases_by_id: dict[str, Any],
) -> None:
    defect_ids = [str(entry["defect_id"]) for entry in payload["entries"]]
    if len(defect_ids) != len(set(defect_ids)):
        raise ValueError(f"{path}: defect_id values must be unique.")

    task_ids_by_release = {
        release_id: {task.task_id for task in release.load_tasks()} for release_id, release in releases_by_id.items()
    }
    for entry in payload["entries"]:
        defect_id = str(entry["defect_id"])
        release_ids = [str(value) for value in entry["affected_release_ids"]]
        unknown_releases = sorted(set(release_ids).difference(releases_by_id))
        if unknown_releases:
            raise ValueError(f"{path}:{defect_id}: unknown affected release {unknown_releases[0]!r}.")
        eligible_task_ids = set().union(*(task_ids_by_release[value] for value in release_ids))
        unknown_tasks = sorted(set(entry["affected_task_ids"]).difference(eligible_task_ids))
        if unknown_tasks:
            raise ValueError(f"{path}:{defect_id}: unknown affected task {unknown_tasks[0]!r}.")
        for evidence in entry["evidence"]:
            evidence_path = Path(str(evidence))
            if evidence_path.is_absolute():
                raise ValueError(f"{path}:{defect_id}: evidence paths must be repository-relative.")
            resolved = (ROOT / evidence_path).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
                raise ValueError(f"{path}:{defect_id}: evidence path is missing or outside the repository.")
        if entry["status"] in {"fixed", "regraded"}:
            resolution = entry["resolution"]
            if resolution["status"] != "complete" or not resolution["replacement_artifact"]:
                raise ValueError(f"{path}:{defect_id}: fixed/regraded defects require a complete replacement artifact.")


def validate_repository() -> dict[str, int]:
    from scripts.build_fleet_status import build_fleet_status
    from scripts.common_harness_submission import validate_submission

    validators = {
        "task": _validator("task.v1.schema.json"),
        "runtime": _validator("runtime-task.v1.schema.json"),
        "run_v1": _validator("run.v1.schema.json"),
        "run_v2": _validator("run.v2.schema.json"),
        "result": _validator("result.v1.schema.json"),
        "release": _validator("release.v1.schema.json"),
        "review_evidence": _validator("review-evidence.v1.schema.json"),
        "model_fleet": _validator("model-fleet.v1.schema.json"),
        "fleet_status_v1": _validator("fleet-status.v1.schema.json"),
        "fleet_status_v2": _validator("fleet-status.v2.schema.json"),
        "common_harness_submission": _validator("common-harness-submission.v1.schema.json"),
        "recorded_batch_v2": _validator("recorded-batch.v2.schema.json"),
        "defect_ledger": _validator("defect-ledger.v1.schema.json"),
        "campaign_v1": _validator("campaign.v1.schema.json"),
        "campaign_v2": _validator("campaign.v2.schema.json"),
        "access_status": _validator("access-status.v1.schema.json"),
        "model_routes": _validator("model-route.v1.schema.json"),
        "access_probe_receipt": _validator("access-probe-receipt.v1.schema.json"),
    }

    fleet_path = ROOT / "fleet" / "public_fleet_v1.yaml"
    fleet = _load_yaml(fleet_path)
    _validate(validators["model_fleet"], fleet, fleet_path)
    fleet_models = fleet["models"]
    fleet_ids = [str(item["base_model_id"]) for item in fleet_models]
    if len(fleet_ids) != len(set(fleet_ids)):
        raise ValueError(f"{fleet_path}: base_model_id values must be unique.")
    if len(fleet_ids) != fleet["target_base_model_count"]:
        raise ValueError(f"{fleet_path}: target_base_model_count does not match the frozen list.")

    route_set_path = ROOT / "fleet" / "model_routes_v1.yaml"
    route_set_payload = _load_yaml(route_set_path)
    _validate(validators["model_routes"], route_set_payload, route_set_path)
    route_set = load_route_set(route_set_path)
    if route_set.fleet_id != fleet["fleet_id"]:
        raise ValueError(f"{route_set_path}: route set does not match the frozen fleet.")

    fleet_status_path = ROOT / "web" / "public" / "data" / "fleet_status.json"
    fleet_status = _load_json(fleet_status_path)
    _validate(validators["fleet_status_v2"], fleet_status, fleet_status_path)
    if fleet_status["fleet_id"] != fleet["fleet_id"]:
        raise ValueError(f"{fleet_status_path}: fleet_id does not match the frozen fleet manifest.")
    if fleet_status["summary"]["planned_base_models"] != len(fleet_ids):
        raise ValueError(f"{fleet_status_path}: planned model count does not match the frozen fleet.")
    projected_ids = [str(item["base_model_id"]) for item in fleet_status["models"]]
    if projected_ids != fleet_ids:
        raise ValueError(f"{fleet_status_path}: model projection order/content differs from frozen fleet.")
    if build_fleet_status() != fleet_status:
        raise ValueError(f"{fleet_status_path}: projection differs from current catalog, access, or releases.")

    access_status_path = ROOT / "web" / "public" / "data" / "access_status.json"
    access_status = load_access_entries(access_status_path)
    _validate(validators["access_status"], access_status, access_status_path)
    catalog_path = ROOT / "web" / "public" / "data" / "model_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not all(isinstance(entry, dict) for entry in catalog):
        raise ValueError(f"{catalog_path}: model catalog must contain a list of objects.")
    catalog_index = {
        (str(entry["provider"]), str(entry["model_name"])): str(entry["base_model_id"]) for entry in catalog
    }
    catalog_provider_bases = {(str(entry["provider"]), str(entry["base_model_id"])) for entry in catalog}
    access_keys: set[tuple[str, str, str]] = set()
    for entry in access_status:
        if entry["status"] != "available":
            continue
        base_model_id = str(entry["base_model_id"])
        if base_model_id not in fleet_ids:
            raise ValueError(
                f"{access_status_path}: available route references model outside the frozen fleet: {base_model_id!r}."
            )
        provider_model = (str(entry["provider"]), str(entry["model"]))
        exact_catalog_match = catalog_index.get(provider_model) == base_model_id
        base_level_catalog_match = (
            entry["model"] == base_model_id and (provider_model[0], base_model_id) in catalog_provider_bases
        )
        if not exact_catalog_match and not base_level_catalog_match:
            raise ValueError(
                f"{access_status_path}: available route {provider_model!r} is not bound to "
                f"{base_model_id!r} in the public model catalog."
            )
        key = (*provider_model, base_model_id)
        if key in access_keys:
            raise ValueError(f"{access_status_path}: duplicate available route {key!r}.")
        access_keys.add(key)
        if entry.get("promotion_basis"):
            validate_attested_q2_qualification(
                entry,
                repository_root=ROOT,
                provider=provider_model[0],
                model_name=provider_model[1],
                base_model_id=base_model_id,
            )

    release_paths = sorted((ROOT / "releases").glob("*.yaml"))
    releases_by_id = {}
    for path in release_paths:
        payload = _load_yaml(path)
        _validate(validators["release"], payload, path)
        release_id = str(payload["release_id"])
        if release_id in releases_by_id:
            raise ValueError(f"Duplicate release_id {release_id!r} in {path}.")
        releases_by_id[release_id] = load_release(path)

    campaign_paths = sorted((ROOT / "campaigns").glob("*.yaml"))
    campaign_ids: set[str] = set()
    for path in campaign_paths:
        payload = _load_yaml(path)
        campaign_validator = (
            validators["campaign_v2"]
            if payload.get("schema_version") == "medeval.campaign.v2"
            else validators["campaign_v1"]
        )
        _validate(campaign_validator, payload, path)
        campaign = load_campaign(path)
        if campaign.campaign_id in campaign_ids:
            raise ValueError(f"Duplicate campaign_id {campaign.campaign_id!r} in {path}.")
        campaign_ids.add(campaign.campaign_id)

    defect_ledger_path = ROOT / "governance" / "benchmark-defects.json"
    defect_ledger = _load_json(defect_ledger_path)
    _validate(validators["defect_ledger"], defect_ledger, defect_ledger_path)
    _validate_defect_ledger_semantics(defect_ledger, defect_ledger_path, releases_by_id)

    review_paths = sorted((ROOT / "reviews").glob("*.json"))
    for path in review_paths:
        payload = _load_json(path)
        _validate(validators["review_evidence"], payload, path)
        _validate_review_evidence_semantics(payload, path)
        release_id = str(payload["release_id"])
        release = releases_by_id.get(release_id)
        if release is None:
            raise ValueError(f"{path}: review evidence references unknown release {release_id!r}.")
        expected_task_ids = {task.task_id for task in release.load_tasks()}
        reviewed_task_ids = [str(item["task_id"]) for item in payload["task_reviews"]]
        if len(reviewed_task_ids) != len(set(reviewed_task_ids)):
            raise ValueError(f"{path}: task_reviews contains duplicate task IDs.")
        if set(reviewed_task_ids) != expected_task_ids:
            missing = sorted(expected_task_ids.difference(reviewed_task_ids))
            extra = sorted(set(reviewed_task_ids).difference(expected_task_ids))
            raise ValueError(f"{path}: review task coverage mismatch; missing={missing}, extra={extra}.")

    grader_mutation_count = 0
    task_paths = sorted((ROOT / "tasks").rglob("task.yaml"))
    for path in task_paths:
        task_payload = _load_yaml(path)
        _validate(validators["task"], task_payload, path)
        _validate_task_grading_semantics(task_payload, path)
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
        grader_mutation_count += validate_grader_mutations(task, reference_output, path)

    result_paths = sorted((ROOT / "results" / "releases").glob("*/*/*.json"))
    result_index: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    for path in result_paths:
        payload = _load_json(path)
        _validate(validators["result"], payload, path)
        manifest = payload.get("manifest")
        if not isinstance(manifest, dict):
            raise ValueError(f"{path}: result manifest must be an object.")
        manifest_version = manifest.get("schema_version")
        if manifest_version == "medeval.run.v1":
            _validate(validators["run_v1"], manifest, path)
        elif manifest_version == "medeval.run.v2":
            _validate(validators["run_v2"], manifest, path)
            settings = manifest["adapter_settings"]
            if stable_hash(settings) != manifest["adapter_settings_hash"]:
                raise ValueError(f"{path}: adapter_settings_hash does not match adapter_settings.")

            class _ManifestAdapter:
                def __init__(self, runtime_settings: dict[str, Any]) -> None:
                    self._runtime_settings = runtime_settings

                def runtime_settings(self) -> dict[str, Any]:
                    return self._runtime_settings

            adapter_runtime_settings(_ManifestAdapter(settings))  # type: ignore[arg-type]
        else:
            raise ValueError(f"{path}: unsupported run manifest version {manifest_version!r}.")
        raw_response = payload.get("raw_response")
        if isinstance(raw_response, dict) and {"content", "thinking"}.intersection(raw_response):
            raise ValueError(f"{path}: public result contains unredacted provider output.")
        trace = payload.get("trace")
        if isinstance(trace, list) and any(isinstance(item, dict) and "raw_preview" in item for item in trace):
            raise ValueError(f"{path}: public result trace contains an unredacted raw preview.")
        relative_parts = path.relative_to(ROOT / "results" / "releases").parts
        model = manifest["model"]
        result_key = (
            relative_parts[0],
            str(model["model_name"]),
            str(model["model_revision"]),
            int(payload["attempt_index"]),
            str(manifest["task_id"]),
        )
        if result_key in result_index:
            raise ValueError(f"{path}: duplicate public result identity {result_key!r}.")
        result_index[result_key] = payload

    capture_paths = sorted((ROOT / "captures" / "recorded").rglob("*.json"))
    capture_ids: set[str] = set()
    for path in capture_paths:
        capture = _load_json(path)
        _validate(validators["recorded_batch_v2"], capture, path)
        release_id = str(capture["release_id"])
        release = releases_by_id.get(release_id)
        if release is None:
            raise ValueError(f"{path}: recorded capture references unknown release {release_id!r}.")
        tasks = release.load_tasks()
        validate_recorded_batch(
            capture,
            release_id=release_id,
            tasks=tasks,
            model=str(capture["model"]),
            model_revision=str(capture["model_revision"]),
            reasoning_effort=str(capture["reasoning_effort"]),
            attempt_index=int(capture["attempt_index"]),
        )
        model_name = f"{capture['model']} [effort={capture['reasoning_effort']}]"
        capture_id = str(capture["capture"]["capture_id"])
        if capture_id in capture_ids:
            raise ValueError(f"{path}: duplicate recorded capture_id {capture_id!r}.")
        capture_ids.add(capture_id)
        for task_id, output in capture["outputs"].items():
            result_key = (
                release_id,
                model_name,
                str(capture["model_revision"]),
                int(capture["attempt_index"]) - 1,
                str(task_id),
            )
            result = result_index.get(result_key)
            if result is None:
                raise ValueError(f"{path}: no public result matches capture output {result_key!r}.")
            if result["output"] != output:
                raise ValueError(f"{path}: captured output differs from public result for {task_id!r}.")
            trace = result.get("trace")
            if not isinstance(trace, list) or not any(
                isinstance(event, dict) and event.get("capture_id") == capture_id for event in trace
            ):
                raise ValueError(f"{path}: public result trace does not bind capture_id {capture_id!r}.")
            raw_response = result.get("raw_response")
            if not isinstance(raw_response, dict) or raw_response.get("capture_id") != capture_id:
                raise ValueError(f"{path}: public result raw-response record does not bind capture_id {capture_id!r}.")

    submission_paths = sorted((ROOT / "submissions").glob("*.json"))
    for path in submission_paths:
        _validate(validators["common_harness_submission"], _load_json(path), path)
        validate_submission(path)

    return {
        "schema_count": len(validators),
        "release_count": len(release_paths),
        "review_evidence_count": len(review_paths),
        "defect_count": len(defect_ledger["entries"]),
        "task_count": len(task_paths),
        "result_count": len(result_paths),
        "submission_count": len(submission_paths),
        "recorded_capture_count": len(capture_paths),
        "campaign_count": len(campaign_paths),
        "grader_mutation_count": grader_mutation_count,
        "fleet_model_count": len(fleet_ids),
        "route_count": len(route_set.routes),
    }


def _reference_output(schema: dict[str, Any], grading: dict[str, Any], safety: dict[str, Any]) -> dict[str, Any]:
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
        return {field: _schema_placeholder(properties.get(field, {})) for field in schema.get("required", [])}
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
