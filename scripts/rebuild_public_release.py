#!/usr/bin/env python3
"""Regenerate one public release projection from a committed result directory."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from medphys_agentbench.release_loader import load_release
from medphys_agentbench.reporting import summarize_release

try:
    from scripts.common_harness_submission import validate_submission
    from scripts.descriptive_admission import validate_descriptive_admissions
except ModuleNotFoundError:  # Direct script execution places scripts/ rather than the repository on sys.path.
    from common_harness_submission import validate_submission
    from descriptive_admission import validate_descriptive_admissions


ROOT = Path(__file__).resolve().parents[1]


def _load_build_fleet_status() -> Any:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_fleet_status import build_fleet_status

    return build_fleet_status


def _serialize_sorted(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _serialize_default(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def _overlay_fleet_inputs(
    *,
    base_inputs: list[Path],
    replaced_paths: dict[Path, Path],
) -> list[Path]:
    return [replaced_paths.get(path, path) for path in base_inputs]


def _build_projection(
    *,
    release_file: Path,
    results_root: Path,
    expected_attempts_per_task: int | None,
    submissions_dir: Path,
    descriptive_admissions: Path | None = None,
) -> tuple[dict[str, Any], bytes]:
    release = load_release(release_file)
    leaderboard = summarize_release(
        release,
        results_root,
        expected_attempts_per_task=expected_attempts_per_task,
    )
    _require_ranked_submission_manifests(
        leaderboard=leaderboard,
        release_id=release.release_id,
        results_root=results_root,
        submissions_dir=submissions_dir,
    )
    _require_descriptive_common_harness_admissions(
        leaderboard=leaderboard,
        release_id=release.release_id,
        admission_path=descriptive_admissions
        or ROOT / "governance" / f"descriptive-admissions-{release.release_id}.json",
    )
    evidence_timestamps = [
        str(task["created_at"])
        for row in [*leaderboard.get("models", []), *leaderboard.get("unranked_models", [])]
        for task in row.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("created_at"), str)
    ]
    if evidence_timestamps:
        leaderboard["generated_at"] = max(evidence_timestamps)
    return leaderboard, _serialize_sorted(leaderboard)


def _require_ranked_submission_manifests(
    *,
    leaderboard: dict[str, Any],
    release_id: str,
    results_root: Path,
    submissions_dir: Path,
) -> None:
    ranked_rows = leaderboard.get("models", [])
    if not ranked_rows:
        return

    manifest_paths = sorted(submissions_dir.glob("*.json"))
    manifests: list[tuple[Path, dict[str, Any]]] = []
    for path in manifest_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read submission manifest {path}: {exc}") from exc
        if payload.get("release_id") == release_id:
            manifests.append((path, payload))

    expected_results_root = (results_root / release_id).resolve()
    validated_paths: set[Path] = set()
    for row in ranked_rows:
        identity = (
            row.get("provider"),
            row.get("model_name"),
            row.get("model_revision"),
            row.get("harness_name"),
            row.get("harness_revision"),
        )
        matches = [
            (path, payload)
            for path, payload in manifests
            if (
                payload.get("model", {}).get("provider"),
                payload.get("model", {}).get("model_name"),
                payload.get("model", {}).get("model_revision"),
                payload.get("model", {}).get("harness_name"),
                payload.get("model", {}).get("harness_revision"),
            ) == identity
        ]
        if len(matches) != 1:
            raise ValueError(
                "Every officially ranked row must have exactly one validated common-harness submission manifest; "
                f"found {len(matches)} for {identity}."
            )
        manifest_path, payload = matches[0]
        submitted_results = (ROOT / str(payload["results_directory"])).resolve()
        if submitted_results.parent != expected_results_root:
            raise ValueError(
                f"Submission {manifest_path} does not bind a model directory under {expected_results_root}."
            )
        if manifest_path not in validated_paths:
            validate_submission(manifest_path, release_summary=leaderboard)
            validated_paths.add(manifest_path)


def _require_descriptive_common_harness_admissions(
    *,
    leaderboard: dict[str, Any],
    release_id: str,
    admission_path: Path,
) -> None:
    descriptive_rows = [
        row
        for row in leaderboard.get("unranked_models", [])
        if row.get("execution_surface") == "common_harness"
    ]
    if not descriptive_rows:
        return
    if not admission_path.is_file():
        raise ValueError(
            "Every descriptive common-harness row requires one content-addressed admission ledger; "
            f"missing {admission_path} for {release_id}."
        )
    validate_descriptive_admissions(admission_path, release_summary=leaderboard)


def _coerce_paths(*paths: Path) -> list[Path]:
    seen: set[Path] = set()
    output: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        output.append(path)
    return output


def _check_or_write(
    *,
    check: bool,
    payloads: dict[Path, bytes],
    fleet_status_path: Path,
    fleet_status_payload: bytes,
) -> None:
    stale: list[str] = []
    for path, projected in payloads.items():
        if not path.is_file() or path.read_bytes() != projected:
            stale.append(f"drift@{path}")

    if not fleet_status_path.is_file() or fleet_status_path.read_bytes() != fleet_status_payload:
        stale.append(f"drift@{fleet_status_path}")

    if stale:
        if check:
            raise SystemExit(
                "Stale release projection for: " + ", ".join(sorted(stale))
            )
        for path, projected in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(projected)
        fleet_status_path.parent.mkdir(parents=True, exist_ok=True)
        fleet_status_path.write_bytes(fleet_status_payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-file", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--canonical-leaderboard", type=Path, required=True)
    parser.add_argument("--results-leaderboard", type=Path, required=True)
    parser.add_argument("--public-leaderboard", type=Path, required=True)
    parser.add_argument("--fleet-status", type=Path, required=True)
    parser.add_argument("--fleet-manifest", type=Path, required=True)
    parser.add_argument("--fleet-catalog", type=Path, required=True)
    parser.add_argument("--fleet-access", type=Path, required=True)
    parser.add_argument(
        "--fleet-leaderboard",
        action="append",
        dest="fleet_leaderboards",
        type=Path,
    )
    parser.add_argument("--expected-attempts", type=int)
    parser.add_argument(
        "--submissions-dir",
        type=Path,
        default=ROOT / "submissions",
        help="Directory containing strict common-harness submission manifests required for every ranked row.",
    )
    parser.add_argument(
        "--descriptive-admissions",
        type=Path,
        help="Content-addressed admission ledger required for descriptive-only common-harness rows.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    release = load_release(args.release_file)
    release_id = release.release_id
    public_data_root = args.public_leaderboard.parent

    _, leaderboard_text = _build_projection(
        release_file=args.release_file,
        results_root=args.results_root,
        expected_attempts_per_task=args.expected_attempts,
        submissions_dir=args.submissions_dir,
        descriptive_admissions=args.descriptive_admissions,
    )

    payloads = {
        args.canonical_leaderboard: leaderboard_text,
        args.results_leaderboard: leaderboard_text,
        args.public_leaderboard: leaderboard_text,
    }

    discovered_fleet_inputs = [
        public_data_root / name
        for name in (
            "leaderboard.json",
            "imaging_leaderboard.json",
            "tg263_leaderboard.json",
            "public-real-workflows-pilot-v0.6.json",
        )
        if (public_data_root / name).is_file()
    ]
    with tempfile.TemporaryDirectory(prefix="medphysbench-leaderboard-") as temp_dir:
        temp_root = Path(temp_dir)
        replaced_paths = {
            args.results_leaderboard: temp_root / f"results-{args.results_leaderboard.name}",
            args.public_leaderboard: temp_root / f"public-{args.public_leaderboard.name}",
        }
        for path in set(replaced_paths.values()):
            path.write_bytes(leaderboard_text)

        if args.fleet_leaderboards:
            fleet_inputs = _coerce_paths(*args.fleet_leaderboards)
        else:
            if discovered_fleet_inputs:
                fleet_inputs = _coerce_paths(*discovered_fleet_inputs)
            else:
                fleet_inputs = _coerce_paths(args.results_leaderboard)
        projected_paths = _coerce_paths(
            *_overlay_fleet_inputs(
                base_inputs=fleet_inputs,
                replaced_paths=replaced_paths,
            )
        )
        build_fleet_status = _load_build_fleet_status()
        fleet_payload = build_fleet_status(
            fleet_path=args.fleet_manifest,
            catalog_path=args.fleet_catalog,
            access_path=args.fleet_access,
            leaderboard_paths=tuple(projected_paths),
        )
    fleet_text = _serialize_default(fleet_payload)

    _check_or_write(
        check=args.check,
        payloads=payloads,
        fleet_status_path=args.fleet_status,
        fleet_status_payload=fleet_text,
    )

    if args.check:
        print(
            f"release projection up to date: release_id={release_id}, "
            f"path={args.canonical_leaderboard.name}"
        )


if __name__ == "__main__":
    main()
