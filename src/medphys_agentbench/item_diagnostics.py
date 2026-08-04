"""Deterministic public projection of comparison-group item diagnostics."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from .analytics import build_leaderboard_analytics, load_result_records
from .json_utils import stable_hash


def build_item_diagnostics_artifact(
    release_results_dir: str | Path,
    leaderboard_file: str | Path,
    *,
    repository_root: str | Path,
) -> dict[str, Any]:
    """Build one hash-bound, output-free diagnostics artifact."""
    root = Path(repository_root).resolve()
    results_dir = Path(release_results_dir).resolve()
    leaderboard_path = Path(leaderboard_file).resolve()
    if not results_dir.is_relative_to(root) or not leaderboard_path.is_relative_to(root):
        raise ValueError("Diagnostics sources must resolve inside the repository.")
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    if not isinstance(leaderboard, dict):
        raise ValueError(f"Leaderboard must contain a JSON object: {leaderboard_path}")
    records = load_result_records(results_dir)
    analytics = build_leaderboard_analytics(records, leaderboard=leaderboard)
    result_manifest = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(results_dir.glob("*/*.json"))
    ]
    release = leaderboard.get("release")
    release_id = release.get("release_id") if isinstance(release, dict) else None
    if not isinstance(release_id, str) or not release_id:
        raise ValueError("Leaderboard release.release_id is required.")
    return {
        "schema_version": "medphysbench.item-diagnostics.v1",
        "release_id": release_id,
        "source": {
            "leaderboard_file": leaderboard_path.relative_to(root).as_posix(),
            "leaderboard_sha256": sha256(leaderboard_path.read_bytes()).hexdigest(),
            "results_directory": results_dir.relative_to(root).as_posix(),
            "result_record_count": len(result_manifest),
            "result_manifest_sha256": stable_hash(result_manifest),
        },
        "item_diagnostics": analytics["item_diagnostics"],
    }


def write_item_diagnostics_artifact(payload: dict[str, Any], output_file: str | Path) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
