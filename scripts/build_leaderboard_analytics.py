#!/usr/bin/env python3
"""Build deterministic run analytics from one release result directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from medphys_agentbench.analytics import build_leaderboard_analytics, load_result_records, write_analytics


def _load_leaderboard(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Leaderboard must contain a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate scores, safe success, provider usage, timing, throughput, missing telemetry, and Pareto fronts."
        )
    )
    parser.add_argument(
        "release_results_dir",
        type=Path,
        help="Release directory containing one subdirectory per model.",
    )
    parser.add_argument(
        "--leaderboard",
        type=Path,
        help="Optional leaderboard JSON. Defaults to <release_results_dir>/leaderboard.json when present.",
    )
    parser.add_argument("--release-id", help="Explicit release identifier when no leaderboard is supplied.")
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout.")
    args = parser.parse_args()

    leaderboard_path = args.leaderboard
    default_leaderboard = args.release_results_dir / "leaderboard.json"
    if leaderboard_path is None and default_leaderboard.is_file():
        leaderboard_path = default_leaderboard

    leaderboard = _load_leaderboard(leaderboard_path)
    records = load_result_records(args.release_results_dir)
    analytics = build_leaderboard_analytics(
        records,
        leaderboard=leaderboard,
        release_id=args.release_id,
    )
    if args.output is not None:
        write_analytics(analytics, args.output)
    else:
        print(json.dumps(analytics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
