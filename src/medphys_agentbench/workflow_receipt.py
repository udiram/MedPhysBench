"""Forward-looking, non-public stateful workflow receipt validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .json_utils import decode_strict_json_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_RECEIPT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "workflow-receipt.v1.schema.json"


class WorkflowReceiptError(ValueError):
    """Raised when workflow receipt evidence is incomplete or cannot be trusted."""


@dataclass(frozen=True)
class WorkflowToolObservation:
    tool_name: str
    tool_kind: str
    call_count: int


@dataclass(frozen=True)
class WorkflowArtifact:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class WorkflowReceipt:
    source_path: Path
    payload: dict[str, Any]
    tools_observed: tuple[WorkflowToolObservation, ...]
    output_artifacts: tuple[WorkflowArtifact, ...]


def load_workflow_receipt(
    path: str | Path,
    *,
    expected_run_id: str,
    expected_task_id: str,
    expected_attempt_index: int,
    expected_initial_state_hash: str,
    expected_workflow_contract_hash: str,
    expected_declared_tools: Iterable[str],
    expected_required_artifacts: Iterable[Mapping[str, Any]],
    expected_trajectory_summary: Mapping[str, Any],
    expected_trajectory_sha256: str,
    expected_final_state_tree_sha256: str,
) -> WorkflowReceipt:
    """Load and validate a stateful workflow receipt against expected benchmark state."""
    source_path = Path(path).resolve()
    try:
        payload = decode_strict_json_object(source_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkflowReceiptError(f"Cannot read workflow receipt {source_path}: {error}") from error
    return validate_workflow_receipt_payload(
        payload,
        source_path=source_path,
        expected_run_id=expected_run_id,
        expected_task_id=expected_task_id,
        expected_attempt_index=expected_attempt_index,
        expected_initial_state_hash=expected_initial_state_hash,
        expected_workflow_contract_hash=expected_workflow_contract_hash,
        expected_declared_tools=expected_declared_tools,
        expected_required_artifacts=expected_required_artifacts,
        expected_trajectory_summary=expected_trajectory_summary,
        expected_trajectory_sha256=expected_trajectory_sha256,
        expected_final_state_tree_sha256=expected_final_state_tree_sha256,
    )


def validate_workflow_receipt_payload(
    payload: Mapping[str, Any],
    *,
    source_path: Path,
    expected_run_id: str,
    expected_task_id: str,
    expected_attempt_index: int,
    expected_initial_state_hash: str,
    expected_workflow_contract_hash: str,
    expected_declared_tools: Iterable[str],
    expected_required_artifacts: Iterable[Mapping[str, Any]],
    expected_trajectory_summary: Mapping[str, Any],
    expected_trajectory_sha256: str,
    expected_final_state_tree_sha256: str,
) -> WorkflowReceipt:
    """Validate a decoded workflow receipt without reading raw trajectory artifacts."""
    normalized = dict(payload)
    try:
        _schema_validator().validate(normalized)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise WorkflowReceiptError(f"Invalid workflow receipt contract at {location}: {error.message}") from error

    tools_observed = _validate_tools_observed(
        normalized["tools_observed"],
        expected_declared_tools=expected_declared_tools,
    )
    output_artifacts = _validate_output_artifacts(
        normalized["output_artifacts"],
        expected_required_artifacts=expected_required_artifacts,
    )
    if not bool(normalized["grader_inputs_complete"]):
        raise WorkflowReceiptError("Workflow receipt grader_inputs_complete must be true.")

    _expect_equal("run_id", normalized["run_id"], expected_run_id)
    _expect_equal("task_id", normalized["task_id"], expected_task_id)
    _expect_equal("attempt_index", normalized["attempt_index"], expected_attempt_index)
    _expect_equal("initial_state_hash", normalized["initial_state_hash"], expected_initial_state_hash)
    _expect_equal(
        "workflow_contract_hash",
        normalized["workflow_contract_hash"],
        expected_workflow_contract_hash,
    )
    _expect_equal("trajectory_summary", normalized["trajectory_summary"], dict(expected_trajectory_summary))
    _expect_equal("trajectory_sha256", normalized["trajectory_sha256"], expected_trajectory_sha256)
    _expect_equal(
        "final_state_tree_sha256",
        normalized["final_state_tree_sha256"],
        expected_final_state_tree_sha256,
    )

    return WorkflowReceipt(
        source_path=source_path,
        payload=normalized,
        tools_observed=tools_observed,
        output_artifacts=output_artifacts,
    )


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    try:
        schema = decode_strict_json_object(WORKFLOW_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkflowReceiptError(f"Cannot load workflow receipt schema: {error}") from error
    return Draft202012Validator(schema)


def _validate_tools_observed(
    raw_tools: Any,
    *,
    expected_declared_tools: Iterable[str],
) -> tuple[WorkflowToolObservation, ...]:
    if not isinstance(raw_tools, list):
        raise WorkflowReceiptError("Workflow receipt tools_observed must be a list.")
    declared = {str(tool_name) for tool_name in expected_declared_tools}
    seen: set[str] = set()
    tools: list[WorkflowToolObservation] = []
    for item in raw_tools:
        if not isinstance(item, dict):
            raise WorkflowReceiptError("Workflow receipt tool observation must be an object.")
        tool_name = str(item["tool_name"])
        if tool_name in seen:
            raise WorkflowReceiptError(f"Workflow receipt contains duplicate tool observation {tool_name!r}.")
        seen.add(tool_name)
        if tool_name not in declared:
            raise WorkflowReceiptError(f"Workflow receipt observed undeclared tool {tool_name!r}.")
        tools.append(
            WorkflowToolObservation(
                tool_name=tool_name,
                tool_kind=str(item["tool_kind"]),
                call_count=int(item["call_count"]),
            )
        )
    return tuple(tools)


def _validate_output_artifacts(
    raw_artifacts: Any,
    *,
    expected_required_artifacts: Iterable[Mapping[str, Any]],
) -> tuple[WorkflowArtifact, ...]:
    if not isinstance(raw_artifacts, list):
        raise WorkflowReceiptError("Workflow receipt output_artifacts must be a list.")

    observed_by_path: dict[str, WorkflowArtifact] = {}
    observed: list[WorkflowArtifact] = []
    for item in raw_artifacts:
        if not isinstance(item, dict):
            raise WorkflowReceiptError("Workflow receipt output artifact must be an object.")
        path = _normalize_relative_artifact_path(str(item["path"]))
        if path in observed_by_path:
            raise WorkflowReceiptError(f"Workflow receipt contains duplicate output artifact {path!r}.")
        artifact = WorkflowArtifact(
            path=path,
            sha256=str(item["sha256"]),
            bytes=int(item["bytes"]),
        )
        observed_by_path[path] = artifact
        observed.append(artifact)

    expected_by_path: dict[str, WorkflowArtifact] = {}
    for item in expected_required_artifacts:
        path = _normalize_relative_artifact_path(str(item["path"]))
        if path in expected_by_path:
            raise WorkflowReceiptError(f"Expected required artifacts contain duplicate path {path!r}.")
        expected_by_path[path] = WorkflowArtifact(
            path=path,
            sha256=str(item["sha256"]),
            bytes=int(item["bytes"]),
        )

    for path, expected in expected_by_path.items():
        observed_artifact = observed_by_path.get(path)
        if observed_artifact is None:
            raise WorkflowReceiptError(f"Workflow receipt missing required output artifact {path!r}.")
        if observed_artifact.sha256 != expected.sha256 or observed_artifact.bytes != expected.bytes:
            raise WorkflowReceiptError(f"Workflow receipt output artifact mismatch for {path!r}.")

    return tuple(observed)


def _normalize_relative_artifact_path(raw_path: str) -> str:
    if not raw_path or "\\" in raw_path:
        raise WorkflowReceiptError(f"Workflow receipt artifact path is invalid: {raw_path!r}.")
    pure_path = PurePosixPath(raw_path)
    if pure_path.is_absolute():
        raise WorkflowReceiptError(f"Workflow receipt artifact path must be relative: {raw_path!r}.")
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        raise WorkflowReceiptError(f"Workflow receipt artifact path escapes the artifact root: {raw_path!r}.")
    normalized = pure_path.as_posix()
    if normalized != raw_path:
        raise WorkflowReceiptError(f"Workflow receipt artifact path must be normalized: {raw_path!r}.")
    return normalized


def _expect_equal(field: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        raise WorkflowReceiptError(f"Workflow receipt {field} mismatch.")
