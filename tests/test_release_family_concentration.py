from __future__ import annotations

from pathlib import Path

import pytest

from medphys_agentbench.contracts import ContractError
from medphys_agentbench.release_loader import DEFAULT_MAX_FAMILY_SHARE, load_release

ROOT = Path(__file__).resolve().parents[1]
OPENKB_TASKS = {
    family_id: tuple(
        sorted((ROOT / "tasks" / "public" / "radiation_therapy").glob(f"{prefix}_*/task.yaml"))
    )
    for family_id, prefix in (
        ("openkb.pt_242", "openkb_pt242"),
        ("openkb.pt_289", "openkb_pt289"),
    )
}


def _write_release(
    tmp_path: Path,
    task_files: tuple[Path, ...],
    *,
    max_family_share: str | None = None,
) -> Path:
    lines = [
        "schema_version: medeval.release.v1",
        "release_id: family-concentration-test",
        "title: Family concentration test",
        "description: Synthetic release-validation fixture",
        "integrity_profile: pilot",
        "expected_attempts_per_task: 3",
    ]
    if max_family_share is not None:
        lines.append(f"max_family_share: {max_family_share}")
    lines.append("task_files:")
    lines.extend(f"  - {path}" for path in task_files)
    release_path = tmp_path / "release.yaml"
    release_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return release_path


def test_default_boundary_accepts_two_equal_explicit_families() -> None:
    release = load_release(ROOT / "releases" / "public_real_workflows_pilot_v0_6.yaml")
    tasks = release.load_tasks()

    assert release.max_family_share == DEFAULT_MAX_FAMILY_SHARE == 0.5
    assert len(tasks) == 10
    assert [task.family_id for task in tasks].count("openkb.pt_242") == 5
    assert [task.family_id for task in tasks].count("openkb.pt_289") == 5


def test_default_rejects_a_family_with_a_strict_majority(tmp_path: Path) -> None:
    task_files = (*OPENKB_TASKS["openkb.pt_289"], *OPENKB_TASKS["openkb.pt_242"][:4])
    release = load_release(_write_release(tmp_path, task_files))

    with pytest.raises(ContractError) as raised:
        release.load_tasks()

    assert str(raised.value) == (
        "Release 'family-concentration-test' exceeds max_family_share 50.00%: "
        "family_id 'openkb.pt_289' has 5 of 9 tasks (55.56%). Rebalance "
        "release.task_files or set an explicit reviewed release.max_family_share threshold."
    )


def test_explicit_reviewed_threshold_accepts_a_specialized_release(tmp_path: Path) -> None:
    task_files = (*OPENKB_TASKS["openkb.pt_289"], *OPENKB_TASKS["openkb.pt_242"][:4])
    release = load_release(_write_release(tmp_path, task_files, max_family_share="0.6"))

    assert release.max_family_share == 0.6
    assert len(release.load_tasks()) == 9


def test_tied_violations_are_reported_deterministically_by_family_id(tmp_path: Path) -> None:
    task_files = (*OPENKB_TASKS["openkb.pt_289"], *OPENKB_TASKS["openkb.pt_242"])
    release = load_release(_write_release(tmp_path, task_files, max_family_share="0.4"))

    with pytest.raises(ContractError) as raised:
        release.load_tasks()

    message = str(raised.value)
    assert message.index("family_id 'openkb.pt_242'") < message.index("family_id 'openkb.pt_289'")
    assert "family_id 'openkb.pt_242' has 5 of 10 tasks (50.00%)" in message
    assert "family_id 'openkb.pt_289' has 5 of 10 tasks (50.00%)" in message


@pytest.mark.parametrize("value", ["0", "1.01", "true", ".nan", "not-a-number"])
def test_max_family_share_rejects_invalid_values(tmp_path: Path, value: str) -> None:
    release_path = _write_release(
        tmp_path,
        (*OPENKB_TASKS["openkb.pt_289"], *OPENKB_TASKS["openkb.pt_242"]),
        max_family_share=value,
    )

    with pytest.raises(
        ContractError,
        match=r"release\.max_family_share must be a finite number greater than 0 and at most 1",
    ):
        load_release(release_path)
