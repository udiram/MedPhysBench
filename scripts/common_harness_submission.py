#!/usr/bin/env python3
"""Build and validate auditable common-harness result submission manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "common-harness-submission.v1.schema.json"
CATALOG_PATH = ROOT / "web" / "public" / "data" / "model_catalog.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_inventory(results_directory: Path) -> list[dict[str, Any]]:
    if not results_directory.is_dir():
        raise ValueError(f"Results directory does not exist: {results_directory}")
    if results_directory.is_symlink():
        raise ValueError("Results directory must not be a symbolic link.")
    files = sorted(path for path in results_directory.rglob("*") if path.is_file())
    if not files:
        raise ValueError("Results directory is empty.")
    inventory: list[dict[str, Any]] = []
    for path in files:
        if path.is_symlink():
            raise ValueError(f"Submission artifacts must not be symbolic links: {path}")
        if path.suffix != ".json":
            raise ValueError(f"Only JSON result and transport-ledger artifacts are allowed: {path}")
        relative = path.relative_to(results_directory).as_posix()
        kind = "transport_error" if "_transport_errors" in path.parts else "result"
        inventory.append(
            {
                "path": relative,
                "kind": kind,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return inventory


def _artifact_tree_hash(artifacts: list[dict[str, Any]]) -> str:
    canonical = json.dumps(artifacts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_repo_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    if not candidate.is_relative_to(ROOT):
        raise ValueError(f"Path escapes repository root: {relative}")
    return candidate


def _git_commit_exists(commit: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _catalog_entry(provider: str, model_name: str) -> dict[str, Any]:
    catalog = _load_json(CATALOG_PATH)
    matches = [
        entry
        for entry in catalog
        if entry.get("provider") == provider and entry.get("model_name") == model_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one model-catalog row for {provider}::{model_name}; found {len(matches)}.")
    return matches[0]


def validate_submission(manifest_path: Path) -> dict[str, Any]:
    payload = _load_json(manifest_path)
    schema = _load_json(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Submission schema validation failed: {rendered}")

    release_path = _safe_repo_path(payload["release_file"])
    results_directory = _safe_repo_path(payload["results_directory"])
    release = load_release(release_path)
    if release.release_id != payload["release_id"]:
        raise ValueError("Submission release_id does not match the frozen release file.")
    expected_release_parent = ROOT / "results" / "releases" / release.release_id
    if results_directory.parent.resolve() != expected_release_parent.resolve():
        raise ValueError("results_directory must be one model directory under the declared release.")

    for field in ("repo_commit", "adapter_source_commit", "harness_source_commit"):
        if not _git_commit_exists(payload[field]):
            raise ValueError(f"Unknown git commit in {field}: {payload[field]}")

    actual_artifacts = _artifact_inventory(results_directory)
    if payload["artifacts"] != actual_artifacts:
        raise ValueError("Artifact inventory differs from disk (missing, extra, reordered, resized, or rehashed file).")
    if payload["artifact_tree_sha256"] != _artifact_tree_hash(actual_artifacts):
        raise ValueError("artifact_tree_sha256 does not match the canonical artifact inventory.")

    result_artifacts = [item for item in actual_artifacts if item["kind"] == "result"]
    expected_result_count = len(release.load_tasks()) * release.expected_attempts_per_task
    if len(result_artifacts) != expected_result_count:
        raise ValueError(
            f"Expected {expected_result_count} canonical result artifacts; found {len(result_artifacts)}."
        )

    model = payload["model"]
    for artifact in result_artifacts:
        result = _load_json(results_directory / artifact["path"])
        descriptor = result.get("manifest", {}).get("model", {})
        for field in ("provider", "model_name", "model_revision", "harness_name", "harness_revision"):
            if descriptor.get(field) != model[field]:
                raise ValueError(f"{artifact['path']}: model descriptor mismatch for {field}.")

    catalog = _catalog_entry(model["provider"], model["model_name"])
    if catalog.get("base_model_id") != model["base_model_id"]:
        raise ValueError("Submission base_model_id does not match the public model catalog.")

    summary = summarize_release(release, ROOT / "results" / "releases")
    if summary["integrity"]["release_contract_hash_v2"] != payload["release_contract_hash_v2"]:
        raise ValueError("release_contract_hash_v2 does not match the current frozen release contract.")
    rows = [*summary.get("models", []), *summary.get("unranked_models", [])]
    matches = [
        row
        for row in rows
        if row.get("provider") == model["provider"]
        and row.get("model_name") == model["model_name"]
        and row.get("model_revision") == model["model_revision"]
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one summarized row for submitted model; found {len(matches)}.")
    row = matches[0]
    if row.get("ranking_eligible") is not True:
        raise ValueError(
            "Submitted row is not ranking-eligible after completeness, receipt, telemetry, "
            "and deterministic regrade checks: "
            + ", ".join(row.get("integrity", {}).get("integrity_errors", []))
        )

    started = datetime.fromisoformat(payload["execution_started_at"].replace("Z", "+00:00"))
    finished = datetime.fromisoformat(payload["execution_finished_at"].replace("Z", "+00:00"))
    submitted = datetime.fromisoformat(payload["submitted_at"].replace("Z", "+00:00"))
    if not started <= finished <= submitted:
        raise ValueError("Execution/submission timestamps must satisfy started <= finished <= submitted.")
    return {
        "submission_id": payload["submission_id"],
        "release_id": release.release_id,
        "model_name": model["model_name"],
        "artifact_count": len(actual_artifacts),
        "artifact_tree_sha256": payload["artifact_tree_sha256"],
        "ranking_eligible": True,
    }


def _artifact_execution_window(results_directory: Path) -> tuple[str, str]:
    created: list[datetime] = []
    finished: list[datetime] = []
    for path in sorted(results_directory.glob("*.json")):
        result = _load_json(path)
        raw_created = result.get("manifest", {}).get("created_at")
        if not isinstance(raw_created, str):
            continue
        timestamp = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
        created.append(timestamp)
        duration = result.get("duration_seconds")
        finished.append(timestamp + timedelta(seconds=float(duration or 0)))
    if not created:
        raise ValueError("Cannot derive an execution window from result manifests.")
    return min(created).isoformat(), max(finished).isoformat()


def build_submission(args: argparse.Namespace) -> dict[str, Any]:
    release_path = _safe_repo_path(args.release_file)
    results_directory = _safe_repo_path(args.results_directory)
    release = load_release(release_path)
    artifacts = _artifact_inventory(results_directory)
    first_result = next(item for item in artifacts if item["kind"] == "result")
    descriptor = _load_json(results_directory / first_result["path"])["manifest"]["model"]
    catalog = _catalog_entry(descriptor["provider"], descriptor["model_name"])
    summary = summarize_release(release, ROOT / "results" / "releases")
    started, finished = _artifact_execution_window(results_directory)
    commit = args.repo_commit or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    runtime_versions = {
        "python": platform.python_version(),
        **dict(item.split("=", 1) for item in args.runtime_version),
    }
    return {
        "schema_version": "medphysbench.common-harness-submission.v1",
        "submission_id": args.submission_id,
        "submission_kind": args.submission_kind,
        "release_file": args.release_file,
        "release_id": release.release_id,
        "release_contract_hash_v2": summary["integrity"]["release_contract_hash_v2"],
        "repo_commit": commit,
        "adapter_source_commit": args.adapter_source_commit or commit,
        "harness_source_commit": args.harness_source_commit or commit,
        "execution_started_at": started,
        "execution_finished_at": finished,
        "submitted_at": datetime.now(UTC).isoformat(),
        "submitter": {"name": args.submitter_name, "affiliation": args.affiliation},
        "model": {
            **{key: descriptor[key] for key in (
                "provider", "model_name", "model_revision", "harness_name", "harness_revision"
            )},
            "base_model_id": catalog["base_model_id"],
        },
        "results_directory": args.results_directory,
        "artifact_tree_sha256": _artifact_tree_hash(artifacts),
        "artifacts": artifacts,
        "environment": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "hardware_summary": args.hardware_summary,
            "accelerator": args.accelerator,
            "runtime_versions": runtime_versions,
        },
        "budget": {
            "funding": args.funding,
            "estimated_cost_usd": args.estimated_cost_usd,
        },
        "attestations": {
            "complete_unfiltered_artifact_set": True,
            "no_manual_output_edits": True,
            "no_runtime_gold_or_grader_access": True,
            "no_credentials_or_phi": True,
            "redistribution_permitted": True,
            "common_harness_unmodified": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="Validate one submission manifest and its artifacts.")
    validate_parser.add_argument("manifest", type=Path)
    validate_all_parser = subparsers.add_parser(
        "validate-all", help="Validate every committed submission manifest."
    )
    validate_all_parser.add_argument("directory", type=Path, nargs="?", default=ROOT / "submissions")

    build_parser = subparsers.add_parser("build", help="Build an attested submission manifest from frozen results.")
    build_parser.add_argument("--release-file", required=True)
    build_parser.add_argument("--results-directory", required=True)
    build_parser.add_argument("--submission-id", required=True)
    build_parser.add_argument("--submission-kind", choices=("managed_local", "external_reproduction"), required=True)
    build_parser.add_argument("--submitter-name", required=True)
    build_parser.add_argument("--affiliation", required=True)
    build_parser.add_argument("--hardware-summary", required=True)
    build_parser.add_argument("--accelerator")
    build_parser.add_argument(
        "--funding",
        choices=("local_compute", "provider_free_tier", "paid_api", "sponsored"),
        required=True,
    )
    build_parser.add_argument("--estimated-cost-usd", type=float)
    build_parser.add_argument("--runtime-version", action="append", default=[], metavar="NAME=VERSION")
    build_parser.add_argument("--repo-commit")
    build_parser.add_argument("--adapter-source-commit")
    build_parser.add_argument("--harness-source-commit")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument(
        "--attest",
        action="store_true",
        help="Required acknowledgement that every emitted attestation is accurate.",
    )
    args = parser.parse_args()

    if args.command == "validate":
        print(json.dumps(validate_submission(args.manifest), indent=2, sort_keys=True))
        return
    if args.command == "validate-all":
        manifests = sorted(args.directory.glob("*.json"))
        if not manifests:
            raise ValueError(f"No submission manifests found in {args.directory}.")
        summaries = [validate_submission(path) for path in manifests]
        print(json.dumps({"validated_submissions": summaries}, indent=2, sort_keys=True))
        return
    if not args.attest:
        raise SystemExit("Refusing to create an attested manifest without --attest.")
    payload = build_submission(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validate_submission(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
