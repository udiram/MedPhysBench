from __future__ import annotations

import json
from pathlib import Path

import pytest

from medphys_agentbench.workflow_receipt import WorkflowReceiptError, load_workflow_receipt


def _expected_artifacts() -> list[dict[str, object]]:
    return [
        {
            "path": "outputs/plan_summary.json",
            "sha256": "a" * 64,
            "bytes": 512,
        },
        {
            "path": "outputs/contours.csv",
            "sha256": "b" * 64,
            "bytes": 2048,
        },
    ]


def _trajectory_summary() -> dict[str, object]:
    return {
        "step_count": 7,
        "assistant_turns": 3,
        "tool_call_count": 4,
        "terminal_state": "completed",
    }


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "medphysbench.workflow-receipt.v1",
        "run_id": "run_20260803_0001",
        "task_id": "tg263-rename-case-01",
        "attempt_index": 0,
        "initial_state_hash": "1" * 64,
        "workflow_contract_hash": "2" * 64,
        "tools_observed": [
            {
                "tool_name": "dicom_lookup",
                "tool_kind": "structured_io",
                "call_count": 2,
            },
            {
                "tool_name": "tg263_mapper",
                "tool_kind": "transform",
                "call_count": 1,
            },
        ],
        "trajectory_summary": _trajectory_summary(),
        "trajectory_sha256": "3" * 64,
        "final_state_tree_sha256": "4" * 64,
        "output_artifacts": _expected_artifacts(),
        "grader_inputs_complete": True,
    }
    payload.update(overrides)
    return payload


def _write_receipt(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "workflow_receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_payload(**overrides), sort_keys=True), encoding="utf-8")
    return path


def _load(path: Path):
    return load_workflow_receipt(
        path,
        expected_run_id="run_20260803_0001",
        expected_task_id="tg263-rename-case-01",
        expected_attempt_index=0,
        expected_initial_state_hash="1" * 64,
        expected_workflow_contract_hash="2" * 64,
        expected_declared_tools={"dicom_lookup", "tg263_mapper", "planner_terminal"},
        expected_required_artifacts=_expected_artifacts(),
        expected_trajectory_summary=_trajectory_summary(),
        expected_trajectory_sha256="3" * 64,
        expected_final_state_tree_sha256="4" * 64,
    )


def test_workflow_receipt_loads_when_identity_and_inventory_match(tmp_path: Path) -> None:
    receipt = _load(_write_receipt(tmp_path))

    assert receipt.payload["run_id"] == "run_20260803_0001"
    assert [tool.tool_name for tool in receipt.tools_observed] == ["dicom_lookup", "tg263_mapper"]
    assert [artifact.path for artifact in receipt.output_artifacts] == [
        "outputs/plan_summary.json",
        "outputs/contours.csv",
    ]


@pytest.mark.parametrize(
    ("artifact_path", "pattern"),
    [
        ("/absolute/output.json", "must be relative"),
        ("../outside.json", "escapes the artifact root"),
        ("outputs/./plan.json", "must be normalized"),
    ],
)
def test_workflow_receipt_rejects_unsafe_artifact_paths(
    tmp_path: Path,
    artifact_path: str,
    pattern: str,
) -> None:
    path = _write_receipt(
        tmp_path,
        output_artifacts=[
            {
                "path": artifact_path,
                "sha256": "a" * 64,
                "bytes": 128,
            }
        ],
    )

    with pytest.raises(WorkflowReceiptError, match=pattern):
        _load(path)


def test_workflow_receipt_rejects_duplicate_tools_and_duplicate_artifacts(tmp_path: Path) -> None:
    duplicate_tools = _write_receipt(
        tmp_path / "tools",
        tools_observed=[
            {"tool_name": "dicom_lookup", "tool_kind": "structured_io", "call_count": 1},
            {"tool_name": "dicom_lookup", "tool_kind": "structured_io", "call_count": 2},
        ],
    )
    with pytest.raises(WorkflowReceiptError, match="duplicate tool observation"):
        _load(duplicate_tools)

    duplicate_artifacts = _write_receipt(
        tmp_path / "artifacts",
        output_artifacts=[
            {"path": "outputs/plan_summary.json", "sha256": "a" * 64, "bytes": 512},
            {"path": "outputs/plan_summary.json", "sha256": "b" * 64, "bytes": 1024},
        ],
    )
    with pytest.raises(WorkflowReceiptError, match="duplicate output artifact"):
        _load(duplicate_artifacts)


def test_workflow_receipt_rejects_undeclared_tool_use(tmp_path: Path) -> None:
    path = _write_receipt(
        tmp_path,
        tools_observed=[
            {"tool_name": "dicom_lookup", "tool_kind": "structured_io", "call_count": 1},
            {"tool_name": "shadow_tool", "tool_kind": "external_api", "call_count": 1},
        ],
    )

    with pytest.raises(WorkflowReceiptError, match="undeclared tool"):
        _load(path)


def test_workflow_receipt_rejects_missing_or_mismatched_required_artifacts(tmp_path: Path) -> None:
    missing = _write_receipt(
        tmp_path / "missing",
        output_artifacts=[_expected_artifacts()[0]],
    )
    with pytest.raises(WorkflowReceiptError, match="missing required output artifact"):
        _load(missing)

    mismatched = _write_receipt(
        tmp_path / "mismatch",
        output_artifacts=[
            {
                "path": "outputs/plan_summary.json",
                "sha256": "0" * 64,
                "bytes": 512,
            },
            _expected_artifacts()[1],
        ],
    )
    with pytest.raises(WorkflowReceiptError, match="output artifact mismatch"):
        _load(mismatched)


def test_workflow_receipt_rejects_identity_and_hash_drift(tmp_path: Path) -> None:
    with pytest.raises(WorkflowReceiptError, match="run_id mismatch"):
        _load(_write_receipt(tmp_path / "run", run_id="other-run"))

    with pytest.raises(WorkflowReceiptError, match="initial_state_hash mismatch"):
        _load(_write_receipt(tmp_path / "state", initial_state_hash="9" * 64))

    with pytest.raises(WorkflowReceiptError, match="workflow_contract_hash mismatch"):
        _load(_write_receipt(tmp_path / "contract", workflow_contract_hash="8" * 64))

    with pytest.raises(WorkflowReceiptError, match="trajectory_sha256 mismatch"):
        _load(_write_receipt(tmp_path / "trajectory", trajectory_sha256="7" * 64))

    with pytest.raises(WorkflowReceiptError, match="final_state_tree_sha256 mismatch"):
        _load(_write_receipt(tmp_path / "final", final_state_tree_sha256="6" * 64))


def test_workflow_receipt_rejects_trajectory_summary_drift_and_incomplete_grader_inputs(tmp_path: Path) -> None:
    summary_drift = _write_receipt(
        tmp_path / "summary",
        trajectory_summary={
            "step_count": 8,
            "assistant_turns": 3,
            "tool_call_count": 4,
            "terminal_state": "completed",
        },
    )
    with pytest.raises(WorkflowReceiptError, match="trajectory_summary mismatch"):
        _load(summary_drift)

    incomplete = _write_receipt(tmp_path / "grader", grader_inputs_complete=False)
    with pytest.raises(WorkflowReceiptError, match="grader_inputs_complete must be true"):
        _load(incomplete)
