from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from medphys_agentbench import release_loader
from medphys_agentbench.contracts import ContractError

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TASK = ROOT / "tasks" / "public" / "radiation_therapy" / "openkb_pt242_structure_inventory_001" / "task.yaml"


def _write_comparison_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    families: tuple[str, ...] = ("family.1", "family.2", "family.3", "family.4"),
    sources: tuple[str, ...] = ("source.1", "source.2", "source.3", "source.3"),
    receipt_overrides: dict[str, Any] | None = None,
    custodian_count: int = 2,
) -> tuple[Path, Path]:
    tasks_root = tmp_path / "tasks"
    receipts_root = tmp_path / "governance" / "holdout-receipts"
    artifacts_root = tmp_path / "governance" / "holdout-artifacts"
    releases_root = tmp_path / "releases"
    receipts_root.mkdir(parents=True)
    artifacts_root.mkdir(parents=True)
    releases_root.mkdir(parents=True)
    monkeypatch.setattr(release_loader, "REPOSITORY_TASKS_ROOT", tasks_root.resolve())
    monkeypatch.setattr(release_loader, "HOLDOUT_RECEIPTS_ROOT", receipts_root.resolve())
    monkeypatch.setattr(release_loader, "HOLDOUT_ARTIFACTS_ROOT", artifacts_root.resolve())

    source_payload = yaml.safe_load(SOURCE_TASK.read_text(encoding="utf-8"))
    task_files: list[str] = []
    task_paths: list[Path] = []
    for index, (family_id, source_id) in enumerate(zip(families, sources, strict=True), start=1):
        task_payload = dict(source_payload)
        task_payload["task_id"] = f"restricted.comparison.task-{index}"
        task_payload["title"] = f"Protected comparison task {index}"
        task_payload["access_class"] = "restricted"
        task_payload["family_id"] = family_id
        task_payload["source_dependency_id"] = source_id
        task_path = tasks_root / f"task-{index}" / "task.yaml"
        task_path.parent.mkdir(parents=True)
        task_path.write_text(yaml.safe_dump(task_payload, sort_keys=False), encoding="utf-8")
        task_files.append(str(Path("../tasks") / f"task-{index}" / "task.yaml"))
        task_paths.append(task_path)

    loaded_tasks = tuple(release_loader.load_task(path) for path in task_paths)
    try:
        task_bundle_sha256 = release_loader.comparison_task_bundle_sha256(
            loaded_tasks,
            tuple(task_paths),
        )
        family_registry_sha256 = release_loader.comparison_family_registry_sha256(loaded_tasks)
    except ContractError:
        # Invalid-identifier fixtures must reach the release loader's fail-closed check.
        task_bundle_sha256 = "0" * 64
        family_registry_sha256 = "0" * 64

    environment_path = artifacts_root / "environment.json"
    environment_path.write_text('{"sandbox":"sealed-v1"}\n', encoding="utf-8")
    access_log_path = artifacts_root / "access-log.jsonl"
    access_log_path.write_text('{"event":"sealed"}\n', encoding="utf-8")

    custodian_attestations = []
    for custodian_id in ("custodian-alpha", "custodian-beta")[:custodian_count]:
        attestation_path = artifacts_root / f"{custodian_id}.json"
        attestation_path.write_text(
            json.dumps(
                {
                    "schema_version": "medphysbench.holdout-custodian-attestation.v1",
                    "custodian_id": custodian_id,
                    "release_id": "protected-comparison-fixture",
                    "task_bundle_sha256": task_bundle_sha256,
                    "attested_at": "2026-08-01T13:00:00Z",
                    "statement": "Protected holdout sealed and operating",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        custodian_attestations.append(
            {
                "custodian_id": custodian_id,
                "attestation_file": f"governance/holdout-artifacts/{attestation_path.name}",
                "attestation_sha256": hashlib.sha256(attestation_path.read_bytes()).hexdigest(),
            }
        )

    receipt: dict[str, Any] = {
        "schema_version": "medphysbench.holdout-receipt.v1",
        "receipt_id": "holdout-fixture-v1",
        "release_id": "protected-comparison-fixture",
        "sealed_at": "2026-08-01T12:00:00Z",
        "holdout_status": "operating",
        "access_classes": ["restricted"],
        "task_count": 4,
        "family_count": 4,
        "source_dependency_count": 3,
        "task_bundle_sha256": task_bundle_sha256,
        "family_registry_sha256": family_registry_sha256,
        "environment_bundle_file": "governance/holdout-artifacts/environment.json",
        "environment_bundle_sha256": hashlib.sha256(environment_path.read_bytes()).hexdigest(),
        "access_log_file": "governance/holdout-artifacts/access-log.jsonl",
        "access_log_sha256": hashlib.sha256(access_log_path.read_bytes()).hexdigest(),
        "custodian_attestations": custodian_attestations,
        "public_task_text_included": False,
    }
    receipt.update(receipt_overrides or {})
    receipt_path = receipts_root / "protected-comparison-fixture.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()

    release_payload = {
        "schema_version": "medeval.release.v1",
        "release_id": "protected-comparison-fixture",
        "title": "Protected comparison fixture",
        "description": "Synthetic protected comparison contract fixture",
        "allow_access_classes": ["restricted"],
        "expected_attempts_per_task": 5,
        "integrity_profile": "comparison",
        "public_attempt_detail": "aggregate_only",
        "max_family_share": 0.5,
        "comparison_requirements": {
            "minimum_family_count": 4,
            "minimum_source_dependency_count": 3,
            "holdout_receipt_file": "../governance/holdout-receipts/protected-comparison-fixture.json",
            "holdout_receipt_sha256": receipt_hash,
        },
        "task_files": task_files,
    }
    release_path = releases_root / "protected-comparison-fixture.yaml"
    release_path.write_text(yaml.safe_dump(release_payload, sort_keys=False), encoding="utf-8")
    return release_path, receipt_path


def _mutate_release(path: Path, update: Any) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    update(payload)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_protected_comparison_accepts_bound_diverse_nonpublic_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, receipt_path = _write_comparison_fixture(tmp_path, monkeypatch)

    release = release_loader.load_release(release_path)
    tasks = release.load_tasks()
    schema = json.loads(
        (ROOT / "schemas" / "holdout-receipt.v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )

    assert len(tasks) == 4
    assert release.comparison_requirements is not None
    assert len(release.comparison_requirements.holdout_receipt.custodian_ids) == 2


def test_comparison_profile_rejects_public_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(tmp_path, monkeypatch)
    _mutate_release(release_path, lambda payload: payload.update(allow_access_classes=["public"]))

    with pytest.raises(ContractError, match="only gated, restricted, or private"):
        release_loader.load_release(release_path)


def test_comparison_profile_binds_exact_holdout_receipt_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(tmp_path, monkeypatch)

    def corrupt_hash(payload: dict[str, Any]) -> None:
        payload["comparison_requirements"]["holdout_receipt_sha256"] = "0" * 64

    _mutate_release(release_path, corrupt_hash)
    with pytest.raises(ContractError, match="receipt hash mismatch"):
        release_loader.load_release(release_path)


def test_comparison_profile_binds_exact_task_bytes_not_only_aggregate_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(tmp_path, monkeypatch)
    task_path = tmp_path / "tasks" / "task-1" / "task.yaml"
    task_payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    task_payload["title"] = "Counts-preserving task substitution"
    task_path.write_text(yaml.safe_dump(task_payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ContractError, match="protected task bundle does not match"):
        release_loader.load_release(release_path).load_tasks()


def test_comparison_profile_binds_family_registry_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        receipt_overrides={"family_registry_sha256": "f" * 64},
    )

    with pytest.raises(ContractError, match="family registry does not match"):
        release_loader.load_release(release_path).load_tasks()


def test_comparison_profile_enforces_observed_family_diversity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        families=("family.1", "family.1", "family.2", "family.3"),
    )

    with pytest.raises(ContractError, match="at least 4 independent families; observed 3"):
        release_loader.load_release(release_path).load_tasks()


def test_comparison_profile_rejects_cosmetic_identifier_inflation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        families=("family.1", "family.1 ", "family.2", "family.3"),
    )

    with pytest.raises(ContractError, match="non-canonical family_id"):
        release_loader.load_release(release_path).load_tasks()


def test_comparison_profile_casefolds_identifiers_before_counting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        families=("family.A", "family.a", "family.B", "family.C"),
    )

    with pytest.raises(ContractError, match="at least 4 independent families; observed 3"):
        release_loader.load_release(release_path).load_tasks()


def test_comparison_profile_enforces_observed_source_diversity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        sources=("source.1", "source.1", "source.2", "source.2"),
    )

    with pytest.raises(ContractError, match="at least 3 source dependencies; observed 2"):
        release_loader.load_release(release_path).load_tasks()


def test_holdout_receipt_rejects_public_task_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        receipt_overrides={"public_task_text_included": True},
    )

    with pytest.raises(ContractError, match="must not include public task text"):
        release_loader.load_release(release_path)


def test_holdout_receipt_requires_two_distinct_custodian_attestations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        custodian_count=1,
    )

    with pytest.raises(ContractError, match="at least two custodian attestations"):
        release_loader.load_release(release_path)


def test_holdout_receipt_rejects_future_seal_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(
        tmp_path,
        monkeypatch,
        receipt_overrides={"sealed_at": "2099-01-01T00:00:00Z"},
    )

    with pytest.raises(ContractError, match="sealed_at cannot be in the future"):
        release_loader.load_release(release_path)


def test_holdout_receipt_binds_environment_and_access_log_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(tmp_path, monkeypatch)
    environment_path = tmp_path / "governance" / "holdout-artifacts" / "environment.json"
    environment_path.write_text('{"sandbox":"substituted"}\n', encoding="utf-8")

    with pytest.raises(ContractError, match="environment_bundle hash mismatch"):
        release_loader.load_release(release_path)


def test_noncomparison_release_rejects_comparison_requirements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_path, _ = _write_comparison_fixture(tmp_path, monkeypatch)

    def downgrade(payload: dict[str, Any]) -> None:
        payload["integrity_profile"] = "pilot"
        payload["expected_attempts_per_task"] = 3

    _mutate_release(release_path, downgrade)
    with pytest.raises(ContractError, match="reserved for integrity_profile 'comparison'"):
        release_loader.load_release(release_path)
