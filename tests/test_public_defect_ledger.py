from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.build_public_defect_ledger import build_public_projection

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance" / "benchmark-defects.json"
PUBLIC_PROJECTION = ROOT / "web" / "public" / "data" / "benchmark-defects.json"


def _fixture_entry(
    defect_id: str,
    *,
    task_ids: list[str],
    release_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "defect_id": defect_id,
        "affected_release_ids": release_ids or ["public-release-v1"],
        "affected_task_ids": task_ids,
    }


def test_public_projection_preserves_ledger_and_builds_deterministic_task_index() -> None:
    payload = {
        "schema_version": "medphysbench.defect-ledger.v1",
        "updated_at": "2026-08-02T00:00:00Z",
        "entries": [
            _fixture_entry("MPB-2026-003", task_ids=["public.task-b", "public.task-a"]),
            _fixture_entry("MPB-2026-001", task_ids=["public.task-a"]),
            _fixture_entry("MPB-2026-002", task_ids=[]),
        ],
    }
    original = deepcopy(payload)
    release_task_ids = {
        "public-release-v1": frozenset({"public.task-a", "public.task-b"})
    }

    projection = build_public_projection(payload, release_task_ids=release_task_ids)

    assert payload == original
    assert projection["schema_version"] == payload["schema_version"]
    assert projection["updated_at"] == payload["updated_at"]
    assert projection["entries"] == payload["entries"]
    assert projection["task_index"] == {
        "public.task-a": ["MPB-2026-001", "MPB-2026-003"],
        "public.task-b": ["MPB-2026-003"],
    }
    assert list(projection["task_index"]) == ["public.task-a", "public.task-b"]


def test_release_level_defect_remains_visible_without_fabricated_task_scope() -> None:
    release_level = _fixture_entry("MPB-2026-001", task_ids=[])
    payload = {"entries": [release_level]}

    projection = build_public_projection(
        payload,
        release_task_ids={"public-release-v1": frozenset({"public.task-a"})},
    )

    assert projection["entries"] == [release_level]
    assert projection["task_index"] == {}


@pytest.mark.parametrize(
    ("entry", "expected_error"),
    [
        (
            _fixture_entry("MPB-2026-001", task_ids=[], release_ids=["unknown-release"]),
            "unknown affected release 'unknown-release'",
        ),
        (
            _fixture_entry("MPB-2026-001", task_ids=["public.unknown-task"]),
            "unknown affected task 'public.unknown-task'",
        ),
    ],
)
def test_projection_rejects_unknown_release_or_task_scope(
    entry: dict[str, object], expected_error: str
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        build_public_projection(
            {"entries": [entry]},
            release_task_ids={"public-release-v1": frozenset({"public.task-a"})},
        )


def test_canonical_public_projection_is_valid_current_and_task_addressable() -> None:
    schema = json.loads((ROOT / "schemas" / "defect-ledger.v1.schema.json").read_text())
    canonical = json.loads(SOURCE.read_text(encoding="utf-8"))
    public = json.loads(PUBLIC_PROJECTION.read_text(encoding="utf-8"))

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(canonical)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(public)
    assert public["entries"] == canonical["entries"]
    assert public["schema_version"] == canonical["schema_version"]
    assert public["updated_at"] == canonical["updated_at"]

    entries_by_id = {entry["defect_id"]: entry for entry in public["entries"]}
    explicit_task_ids = {
        task_id
        for entry in public["entries"]
        for task_id in entry["affected_task_ids"]
    }
    assert set(public["task_index"]) == explicit_task_ids
    for task_id, defect_ids in public["task_index"].items():
        assert defect_ids == sorted(defect_ids)
        assert all(task_id in entries_by_id[defect_id]["affected_task_ids"] for defect_id in defect_ids)

    completed = subprocess.run(
        [sys.executable, "scripts/build_public_defect_ledger.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
