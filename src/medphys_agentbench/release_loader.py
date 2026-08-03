"""Benchmark release loading and validation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any

import yaml

from .contracts import AccessClass, ContractError, TaskSpec
from .json_utils import stable_hash
from .task_loader import load_task

REPOSITORY_TASKS_ROOT = (Path(__file__).resolve().parents[2] / "tasks").resolve()
HOLDOUT_RECEIPTS_ROOT = (Path(__file__).resolve().parents[2] / "governance" / "holdout-receipts").resolve()
HOLDOUT_ARTIFACTS_ROOT = (Path(__file__).resolve().parents[2] / "governance" / "holdout-artifacts").resolve()
DEFAULT_MAX_FAMILY_SHARE = 0.5
COMPARISON_MIN_FAMILY_COUNT = 4
COMPARISON_MIN_SOURCE_DEPENDENCY_COUNT = 3
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
COMPARISON_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


@dataclass(frozen=True)
class HoldoutReceipt:
    receipt_id: str
    release_id: str
    sealed_at: str
    access_classes: tuple[AccessClass, ...]
    task_count: int
    family_count: int
    source_dependency_count: int
    task_bundle_sha256: str
    family_registry_sha256: str
    environment_bundle_sha256: str
    access_log_sha256: str
    custodian_ids: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonRequirements:
    minimum_family_count: int
    minimum_source_dependency_count: int
    holdout_receipt_file: Path
    holdout_receipt_sha256: str
    holdout_receipt: HoldoutReceipt


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
    max_family_share: float = DEFAULT_MAX_FAMILY_SHARE
    comparison_requirements: ComparisonRequirements | None = None

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
        if self.integrity_profile == "comparison":
            requirements = self.comparison_requirements
            if requirements is None:
                raise ContractError(
                    f"Release {self.release_id!r} uses the comparison profile without protected-holdout requirements."
                )
            missing_source_ids = sorted(task.task_id for task in tasks if not task.source_dependency_id)
            if missing_source_ids:
                raise ContractError(
                    f"Release {self.release_id!r} uses the comparison profile but tasks lack "
                    f"source_dependency_id: {missing_source_ids}."
                )
            normalized_families = tuple(
                _comparison_identifier(task.family_id, field="family_id", task_id=task.task_id)
                for task in tasks
            )
            normalized_sources = tuple(
                _comparison_identifier(
                    task.source_dependency_id,
                    field="source_dependency_id",
                    task_id=task.task_id,
                )
                for task in tasks
            )
            family_count = len(set(normalized_families))
            source_dependency_count = len(set(normalized_sources))
            if family_count < requirements.minimum_family_count:
                raise ContractError(
                    f"Release {self.release_id!r} comparison profile requires at least "
                    f"{requirements.minimum_family_count} independent families; observed {family_count}."
                )
            if source_dependency_count < requirements.minimum_source_dependency_count:
                raise ContractError(
                    f"Release {self.release_id!r} comparison profile requires at least "
                    f"{requirements.minimum_source_dependency_count} source dependencies; "
                    f"observed {source_dependency_count}."
                )
            receipt = requirements.holdout_receipt
            observed_access_classes = {task.access_class for task in tasks}
            if observed_access_classes != set(receipt.access_classes):
                raise ContractError(
                    f"Release {self.release_id!r} task access classes do not match holdout receipt "
                    f"{receipt.receipt_id!r}."
                )
            observed_counts = (len(tasks), family_count, source_dependency_count)
            receipt_counts = (receipt.task_count, receipt.family_count, receipt.source_dependency_count)
            if observed_counts != receipt_counts:
                raise ContractError(
                    f"Release {self.release_id!r} task/family/source counts {observed_counts} do not match "
                    f"holdout receipt {receipt.receipt_id!r} counts {receipt_counts}."
                )
            observed_task_bundle_sha256 = comparison_task_bundle_sha256(tasks, self.task_files)
            if observed_task_bundle_sha256 != receipt.task_bundle_sha256:
                raise ContractError(
                    f"Release {self.release_id!r} protected task bundle does not match holdout receipt "
                    f"{receipt.receipt_id!r}."
                )
            observed_family_registry_sha256 = comparison_family_registry_sha256(tasks)
            if observed_family_registry_sha256 != receipt.family_registry_sha256:
                raise ContractError(
                    f"Release {self.release_id!r} family registry does not match holdout receipt "
                    f"{receipt.receipt_id!r}."
                )
        family_counts = Counter(
            _comparison_identifier(task.family_id, field="family_id", task_id=task.task_id)
            if self.integrity_profile == "comparison"
            else task.family_id or task.task_id
            for task in tasks
        )
        violating_families = sorted(
            (
                (family_id, task_count)
                for family_id, task_count in family_counts.items()
                if task_count / len(tasks) > self.max_family_share
            ),
            key=lambda item: (-item[1], item[0]),
        )
        if violating_families:
            details = "; ".join(
                f"family_id {family_id!r} has {task_count} of {len(tasks)} tasks "
                f"({task_count / len(tasks):.2%})"
                for family_id, task_count in violating_families
            )
            raise ContractError(
                f"Release {self.release_id!r} exceeds max_family_share "
                f"{self.max_family_share:.2%}: {details}. Rebalance release.task_files or set "
                "an explicit reviewed release.max_family_share threshold."
            )
        return tasks


def comparison_task_bundle_sha256(
    tasks: tuple[TaskSpec, ...],
    task_files: tuple[Path, ...],
) -> str:
    """Bind a protected comparison receipt to exact authored task bytes and identity."""
    if len(tasks) != len(task_files):
        raise ContractError("Protected comparison task bundle has mismatched task and file counts.")
    entries = []
    for task, task_file in zip(tasks, task_files, strict=True):
        entries.append(
            {
                "task_id": task.task_id,
                "task_file_sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
                "family_id": _comparison_identifier(
                    task.family_id,
                    field="family_id",
                    task_id=task.task_id,
                ),
                "source_dependency_id": _comparison_identifier(
                    task.source_dependency_id,
                    field="source_dependency_id",
                    task_id=task.task_id,
                ),
                "access_class": task.access_class.value,
            }
        )
    return stable_hash(
        {
            "schema_version": "medphysbench.comparison-task-bundle.v1",
            "tasks": sorted(entries, key=lambda entry: entry["task_id"]),
        }
    )


def comparison_family_registry_sha256(tasks: tuple[TaskSpec, ...]) -> str:
    """Bind family/source membership independently of task ordering."""
    entries = [
        {
            "task_id": task.task_id,
            "family_id": _comparison_identifier(
                task.family_id,
                field="family_id",
                task_id=task.task_id,
            ),
            "source_dependency_id": _comparison_identifier(
                task.source_dependency_id,
                field="source_dependency_id",
                task_id=task.task_id,
            ),
        }
        for task in tasks
    ]
    return stable_hash(
        {
            "schema_version": "medphysbench.comparison-family-registry.v1",
            "tasks": sorted(entries, key=lambda entry: entry["task_id"]),
        }
    )


def _comparison_identifier(value: str | None, *, field: str, task_id: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"Comparison task {task_id!r} requires {field}.")
    if value != value.strip() or not COMPARISON_IDENTIFIER_PATTERN.fullmatch(value):
        raise ContractError(
            f"Comparison task {task_id!r} has non-canonical {field} {value!r}; "
            "use an ASCII identifier without whitespace."
        )
    return value.casefold()


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
    if integrity_profile == "comparison" and any(
        access_class is AccessClass.PUBLIC for access_class in allow_access_classes
    ):
        raise ContractError(
            "release.integrity_profile 'comparison' requires only gated, restricted, or private access classes."
        )
    max_family_share_raw = raw.get("max_family_share", DEFAULT_MAX_FAMILY_SHARE)
    if isinstance(max_family_share_raw, bool) or not isinstance(max_family_share_raw, (int, float)):
        raise ContractError(
            "release.max_family_share must be a finite number greater than 0 and at most 1."
        )
    max_family_share = float(max_family_share_raw)
    if not isfinite(max_family_share) or not 0 < max_family_share <= 1:
        raise ContractError(
            "release.max_family_share must be a finite number greater than 0 and at most 1."
        )

    comparison_raw = raw.get("comparison_requirements")
    if integrity_profile == "comparison":
        comparison_requirements = _load_comparison_requirements(
            comparison_raw,
            release_path=path,
            release_id=str(raw["release_id"]),
            allow_access_classes=allow_access_classes,
        )
    else:
        if comparison_raw is not None:
            raise ContractError(
                "release.comparison_requirements is reserved for integrity_profile 'comparison'."
            )
        comparison_requirements = None

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
        max_family_share=max_family_share,
        comparison_requirements=comparison_requirements,
    )


def _load_comparison_requirements(
    raw: Any,
    *,
    release_path: Path,
    release_id: str,
    allow_access_classes: tuple[AccessClass, ...],
) -> ComparisonRequirements:
    if not isinstance(raw, dict):
        raise ContractError(
            "release.integrity_profile 'comparison' requires release.comparison_requirements."
        )
    required = {
        "minimum_family_count",
        "minimum_source_dependency_count",
        "holdout_receipt_file",
        "holdout_receipt_sha256",
    }
    if set(raw) != required:
        missing = sorted(required.difference(raw))
        extra = sorted(set(raw).difference(required))
        raise ContractError(
            f"release.comparison_requirements fields mismatch; missing={missing}, extra={extra}."
        )
    minimum_family_count = _bounded_integer(
        raw["minimum_family_count"],
        field="release.comparison_requirements.minimum_family_count",
        minimum=COMPARISON_MIN_FAMILY_COUNT,
    )
    minimum_source_dependency_count = _bounded_integer(
        raw["minimum_source_dependency_count"],
        field="release.comparison_requirements.minimum_source_dependency_count",
        minimum=COMPARISON_MIN_SOURCE_DEPENDENCY_COUNT,
    )
    receipt_hash = str(raw["holdout_receipt_sha256"])
    if not SHA256_PATTERN.fullmatch(receipt_hash):
        raise ContractError(
            "release.comparison_requirements.holdout_receipt_sha256 must be a lowercase SHA-256 digest."
        )
    receipt_path = (release_path.parent / str(raw["holdout_receipt_file"])).resolve()
    if not receipt_path.is_relative_to(HOLDOUT_RECEIPTS_ROOT):
        raise ContractError(
            "release.comparison_requirements.holdout_receipt_file must resolve inside "
            "governance/holdout-receipts."
        )
    if not receipt_path.is_file():
        raise ContractError(f"Protected holdout receipt is missing: {receipt_path}.")
    observed_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    if observed_hash != receipt_hash:
        raise ContractError(
            f"Protected holdout receipt hash mismatch for release {release_id!r}."
        )
    receipt = _load_holdout_receipt(receipt_path)
    if receipt.release_id != release_id:
        raise ContractError(
            f"Protected holdout receipt {receipt.receipt_id!r} targets release "
            f"{receipt.release_id!r}, not {release_id!r}."
        )
    if not set(receipt.access_classes).issubset(set(allow_access_classes)):
        raise ContractError(
            f"Protected holdout receipt {receipt.receipt_id!r} declares access outside the release allowlist."
        )
    if receipt.family_count < minimum_family_count:
        raise ContractError(
            f"Protected holdout receipt {receipt.receipt_id!r} declares {receipt.family_count} families, "
            f"below the required {minimum_family_count}."
        )
    if receipt.source_dependency_count < minimum_source_dependency_count:
        raise ContractError(
            f"Protected holdout receipt {receipt.receipt_id!r} declares "
            f"{receipt.source_dependency_count} source dependencies, below the required "
            f"{minimum_source_dependency_count}."
        )
    return ComparisonRequirements(
        minimum_family_count=minimum_family_count,
        minimum_source_dependency_count=minimum_source_dependency_count,
        holdout_receipt_file=receipt_path,
        holdout_receipt_sha256=receipt_hash,
        holdout_receipt=receipt,
    )


def _load_holdout_receipt(path: Path) -> HoldoutReceipt:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"Invalid protected holdout receipt {path}: {error}.") from error
    required = {
        "schema_version",
        "receipt_id",
        "release_id",
        "sealed_at",
        "holdout_status",
        "access_classes",
        "task_count",
        "family_count",
        "source_dependency_count",
        "task_bundle_sha256",
        "family_registry_sha256",
        "environment_bundle_file",
        "environment_bundle_sha256",
        "access_log_file",
        "access_log_sha256",
        "custodian_attestations",
        "public_task_text_included",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        keys = set(raw) if isinstance(raw, dict) else set()
        raise ContractError(
            f"Protected holdout receipt fields mismatch; missing={sorted(required.difference(keys))}, "
            f"extra={sorted(keys.difference(required))}."
        )
    if raw["schema_version"] != "medphysbench.holdout-receipt.v1":
        raise ContractError("Unsupported protected holdout receipt schema_version.")
    if raw["holdout_status"] != "operating":
        raise ContractError("Protected holdout receipt must have holdout_status 'operating'.")
    if raw["public_task_text_included"] is not False:
        raise ContractError("Protected holdout receipt must not include public task text.")
    sealed_at = _past_timestamp(raw["sealed_at"], field="Protected holdout receipt sealed_at")
    access_raw = raw["access_classes"]
    if not isinstance(access_raw, list) or not access_raw:
        raise ContractError("Protected holdout receipt access_classes must be a non-empty list.")
    try:
        access_classes = tuple(AccessClass(value) for value in access_raw)
    except ValueError as error:
        raise ContractError(str(error)) from error
    if len(access_classes) != len(set(access_classes)) or AccessClass.PUBLIC in access_classes:
        raise ContractError("Protected holdout receipt access_classes must be unique and non-public.")
    for field in ("task_bundle_sha256", "family_registry_sha256"):
        if not SHA256_PATTERN.fullmatch(str(raw[field])):
            raise ContractError(f"Protected holdout receipt {field} must be a lowercase SHA-256 digest.")
    environment_hash = _verify_holdout_artifact(
        artifact_file=raw["environment_bundle_file"],
        expected_sha256=raw["environment_bundle_sha256"],
        field="environment_bundle",
    )
    access_log_hash = _verify_holdout_artifact(
        artifact_file=raw["access_log_file"],
        expected_sha256=raw["access_log_sha256"],
        field="access_log",
    )
    task_count = _bounded_integer(raw["task_count"], field="holdout receipt task_count", minimum=1)
    family_count = _bounded_integer(
        raw["family_count"], field="holdout receipt family_count", minimum=COMPARISON_MIN_FAMILY_COUNT
    )
    source_count = _bounded_integer(
        raw["source_dependency_count"],
        field="holdout receipt source_dependency_count",
        minimum=COMPARISON_MIN_SOURCE_DEPENDENCY_COUNT,
    )
    custodian_raw = raw["custodian_attestations"]
    if not isinstance(custodian_raw, list) or len(custodian_raw) < 2:
        raise ContractError("Protected holdout receipt requires at least two custodian attestations.")
    custodian_ids: list[str] = []
    attestation_paths: set[Path] = set()
    for reference in custodian_raw:
        if not isinstance(reference, dict) or set(reference) != {
            "custodian_id",
            "attestation_file",
            "attestation_sha256",
        }:
            raise ContractError("Protected holdout custodian attestation reference is malformed.")
        custodian_id = str(reference["custodian_id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", custodian_id):
            raise ContractError("Protected holdout custodian_id must be a canonical opaque identifier.")
        attestation_path, _ = _verify_holdout_artifact(
            artifact_file=reference["attestation_file"],
            expected_sha256=reference["attestation_sha256"],
            field=f"custodian attestation {custodian_id!r}",
            return_path=True,
        )
        if attestation_path in attestation_paths:
            raise ContractError("Protected holdout custodian attestations must use distinct artifacts.")
        attestation_paths.add(attestation_path)
        _validate_custodian_attestation(
            attestation_path,
            custodian_id=custodian_id,
            release_id=str(raw["release_id"]),
            task_bundle_sha256=str(raw["task_bundle_sha256"]),
            sealed_at=sealed_at,
        )
        custodian_ids.append(custodian_id)
    if len(custodian_ids) != len(set(custodian_ids)):
        raise ContractError("Protected holdout custodian attestations require unique custodian IDs.")
    if family_count > task_count or source_count > task_count:
        raise ContractError("Protected holdout receipt family/source counts cannot exceed task_count.")
    return HoldoutReceipt(
        receipt_id=str(raw["receipt_id"]),
        release_id=str(raw["release_id"]),
        sealed_at=str(raw["sealed_at"]),
        access_classes=access_classes,
        task_count=task_count,
        family_count=family_count,
        source_dependency_count=source_count,
        task_bundle_sha256=str(raw["task_bundle_sha256"]),
        family_registry_sha256=str(raw["family_registry_sha256"]),
        environment_bundle_sha256=environment_hash,
        access_log_sha256=access_log_hash,
        custodian_ids=tuple(custodian_ids),
    )


def _verify_holdout_artifact(
    *,
    artifact_file: Any,
    expected_sha256: Any,
    field: str,
    return_path: bool = False,
) -> str | tuple[Path, str]:
    expected = str(expected_sha256)
    if not SHA256_PATTERN.fullmatch(expected):
        raise ContractError(f"Protected holdout {field} must declare a lowercase SHA-256 digest.")
    relative_path = Path(str(artifact_file))
    if relative_path.is_absolute():
        raise ContractError(f"Protected holdout {field} path must be repository-relative.")
    repository_root = HOLDOUT_ARTIFACTS_ROOT.parents[1]
    resolved = (repository_root / relative_path).resolve()
    if not resolved.is_relative_to(HOLDOUT_ARTIFACTS_ROOT) or not resolved.is_file():
        raise ContractError(
            f"Protected holdout {field} must resolve to a file inside governance/holdout-artifacts."
        )
    observed = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if observed != expected:
        raise ContractError(f"Protected holdout {field} hash mismatch.")
    return (resolved, observed) if return_path else observed


def _validate_custodian_attestation(
    path: Path,
    *,
    custodian_id: str,
    release_id: str,
    task_bundle_sha256: str,
    sealed_at: datetime,
) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"Invalid protected holdout custodian attestation {path}: {error}.") from error
    required = {
        "schema_version",
        "custodian_id",
        "release_id",
        "task_bundle_sha256",
        "attested_at",
        "statement",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ContractError("Protected holdout custodian attestation fields mismatch.")
    if raw["schema_version"] != "medphysbench.holdout-custodian-attestation.v1":
        raise ContractError("Unsupported protected holdout custodian attestation schema_version.")
    if raw["custodian_id"] != custodian_id or raw["release_id"] != release_id:
        raise ContractError("Protected holdout custodian attestation identity mismatch.")
    if raw["task_bundle_sha256"] != task_bundle_sha256:
        raise ContractError("Protected holdout custodian attestation task bundle mismatch.")
    if raw["statement"] != "Protected holdout sealed and operating":
        raise ContractError("Protected holdout custodian attestation statement is invalid.")
    attested_at = _past_timestamp(
        raw["attested_at"],
        field="Protected holdout custodian attestation attested_at",
    )
    if attested_at < sealed_at:
        raise ContractError("Protected holdout custodian attestation cannot predate sealed_at.")


def _past_timestamp(value: Any, *, field: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"{field} must be an ISO-8601 date-time.") from error
    if timestamp.tzinfo is None:
        raise ContractError(f"{field} must include a timezone.")
    timestamp_utc = timestamp.astimezone(UTC)
    if timestamp_utc > datetime.now(UTC):
        raise ContractError(f"{field} cannot be in the future.")
    return timestamp_utc


def _bounded_integer(value: Any, *, field: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{field} must be an integer greater than or equal to {minimum}.")
    return value
