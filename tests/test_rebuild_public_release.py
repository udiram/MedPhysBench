from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from medphys_agentbench.release_loader import load_release
from scripts.build_fleet_status import build_fleet_status

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rebuild_public_release.py"
RELEASE_PATH = ROOT / "releases" / "public_imaging_pilot_v0_4.yaml"


def _prepare_released_artifacts(tmp_path: Path) -> tuple[
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
    Path,
]:
    release = load_release(RELEASE_PATH)

    source_results = ROOT / "results" / "releases" / release.release_id
    results_root = tmp_path / "results" / "releases"
    results_release_dir = results_root / release.release_id
    shutil.copytree(source_results, results_release_dir)

    results_leaderboard = tmp_path / "results" / "leaderboards" / f"{release.release_id}.json"
    results_leaderboard.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(results_release_dir / "leaderboard.json", results_leaderboard)

    public_root = tmp_path / "web" / "public" / "data"
    public_root.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "web" / "public" / "data" / "model_catalog.json", public_root / "model_catalog.json")
    shutil.copy(ROOT / "web" / "public" / "data" / "access_status.json", public_root / "access_status.json")
    shutil.copy(ROOT / "web" / "public" / "data" / "leaderboard.json", public_root / "leaderboard.json")
    shutil.copy(ROOT / "web" / "public" / "data" / "imaging_leaderboard.json", public_root / "imaging_leaderboard.json")
    shutil.copy(ROOT / "web" / "public" / "data" / "tg263_leaderboard.json", public_root / "tg263_leaderboard.json")
    shutil.copy(
        ROOT / "web" / "public" / "data" / "public-real-workflows-pilot-v0.6.json",
        public_root / "public-real-workflows-pilot-v0.6.json",
    )

    public_leaderboard = public_root / "imaging_leaderboard.json"
    public_core_leaderboard = public_root / "leaderboard.json"
    public_imaging_leaderboard = public_root / "imaging_leaderboard.json"
    public_tg263_leaderboard = public_root / "tg263_leaderboard.json"
    public_real_leaderboard = public_root / "public-real-workflows-pilot-v0.6.json"
    fleet_manifest = tmp_path / "fleet" / "public_fleet_v1.yaml"
    fleet_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "fleet" / "public_fleet_v1.yaml", fleet_manifest)
    canonical_leaderboard = results_release_dir / "leaderboard.json"
    fleet_status = public_root / "fleet_status.json"

    return (
        RELEASE_PATH,
        results_root,
        canonical_leaderboard,
        results_leaderboard,
        public_leaderboard,
        public_core_leaderboard,
        public_imaging_leaderboard,
        public_tg263_leaderboard,
        public_real_leaderboard,
        fleet_status,
        fleet_manifest,
    )


def _run_builder(
    *,
    release: Path,
    results_root: Path,
    canonical_leaderboard: Path,
    results_leaderboard: Path,
    public_leaderboard: Path,
    public_imaging_leaderboard: Path,
    public_tg263_leaderboard: Path,
    public_real_leaderboard: Path,
    fleet_status: Path,
    fleet_manifest: Path,
    public_root: Path,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--release-file",
        str(release),
        "--results-root",
        str(results_root),
        "--canonical-leaderboard",
        str(canonical_leaderboard),
        "--results-leaderboard",
        str(results_leaderboard),
        "--public-leaderboard",
        str(public_leaderboard),
        "--fleet-status",
        str(fleet_status),
        "--fleet-manifest",
        str(fleet_manifest),
        "--fleet-catalog",
        str(public_root / "model_catalog.json"),
        "--fleet-access",
        str(public_root / "access_status.json"),
    ]
    if check:
        command.append("--check")
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def test_rebuild_public_release_writes_exact_byte_identical_copies(tmp_path: Path) -> None:
    (
        release,
        results_root,
        canonical_leaderboard,
        results_leaderboard,
        public_leaderboard,
        public_core_leaderboard,
        public_imaging_leaderboard,
        public_tg263_leaderboard,
        public_real_leaderboard,
        fleet_status,
        fleet_manifest,
    ) = _prepare_released_artifacts(tmp_path)

    public_root = tmp_path / "web" / "public" / "data"
    completed = _run_builder(
        release=release,
        results_root=results_root,
        canonical_leaderboard=canonical_leaderboard,
        results_leaderboard=results_leaderboard,
        public_leaderboard=public_leaderboard,
        public_imaging_leaderboard=public_imaging_leaderboard,
        public_tg263_leaderboard=public_tg263_leaderboard,
        public_real_leaderboard=public_real_leaderboard,
        fleet_status=fleet_status,
        fleet_manifest=fleet_manifest,
        public_root=public_root,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    assert canonical_leaderboard.read_bytes() == results_leaderboard.read_bytes() == public_leaderboard.read_bytes()
    projected = json.loads(canonical_leaderboard.read_text(encoding="utf-8"))
    assert projected["integrity"]["expected_attempt_count"] > 0
    assert len(projected["models"]) + len(projected["unranked_models"]) > 0

    expected_fleet = build_fleet_status(
        fleet_path=fleet_manifest,
        catalog_path=public_root / "model_catalog.json",
        access_path=public_root / "access_status.json",
        leaderboard_paths=(
            public_core_leaderboard,
            public_imaging_leaderboard,
            public_tg263_leaderboard,
            public_real_leaderboard,
        ),
    )
    assert json.loads(fleet_status.read_text(encoding="utf-8")) == expected_fleet

    check_run = _run_builder(
        release=release,
        results_root=results_root,
        canonical_leaderboard=canonical_leaderboard,
        results_leaderboard=results_leaderboard,
        public_leaderboard=public_leaderboard,
        public_imaging_leaderboard=public_imaging_leaderboard,
        public_tg263_leaderboard=public_tg263_leaderboard,
        public_real_leaderboard=public_real_leaderboard,
        fleet_status=fleet_status,
        fleet_manifest=fleet_manifest,
        public_root=public_root,
        check=True,
    )
    assert check_run.returncode == 0, check_run.stdout + check_run.stderr


def test_rebuild_public_release_check_mode_detects_and_does_not_mutate(tmp_path: Path) -> None:
    (
        release,
        results_root,
        canonical_leaderboard,
        results_leaderboard,
        public_leaderboard,
        public_core_leaderboard,
        public_imaging_leaderboard,
        public_tg263_leaderboard,
        public_real_leaderboard,
        fleet_status,
        fleet_manifest,
    ) = _prepare_released_artifacts(tmp_path)

    public_root = tmp_path / "web" / "public" / "data"

    completed = _run_builder(
        release=release,
        results_root=results_root,
        canonical_leaderboard=canonical_leaderboard,
        results_leaderboard=results_leaderboard,
        public_leaderboard=public_leaderboard,
        public_imaging_leaderboard=public_imaging_leaderboard,
        public_tg263_leaderboard=public_tg263_leaderboard,
        public_real_leaderboard=public_real_leaderboard,
        fleet_status=fleet_status,
        fleet_manifest=fleet_manifest,
        public_root=public_root,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    baseline_public = public_leaderboard.read_bytes()
    baseline_canonical = canonical_leaderboard.read_bytes()
    baseline_results = results_leaderboard.read_bytes()
    baseline_fleet = fleet_status.read_bytes()
    public_leaderboard.write_text((public_leaderboard.read_text(encoding="utf-8") + "\n\n"), encoding="utf-8")

    check_run = _run_builder(
        release=release,
        results_root=results_root,
        canonical_leaderboard=canonical_leaderboard,
        results_leaderboard=results_leaderboard,
        public_leaderboard=public_leaderboard,
        public_imaging_leaderboard=public_imaging_leaderboard,
        public_tg263_leaderboard=public_tg263_leaderboard,
        public_real_leaderboard=public_real_leaderboard,
        fleet_status=fleet_status,
        fleet_manifest=fleet_manifest,
        public_root=public_root,
        check=True,
    )
    assert check_run.returncode == 1
    assert "Stale release projection" in check_run.stdout + check_run.stderr

    assert public_leaderboard.read_bytes() != baseline_public
    assert public_leaderboard.read_bytes().endswith(b"\n\n")
    assert canonical_leaderboard.read_bytes() == baseline_canonical
    assert results_leaderboard.read_bytes() == baseline_results
    assert fleet_status.read_bytes() == baseline_fleet
