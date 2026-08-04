#!/usr/bin/env python3
"""Build a hash-bound public item-diagnostics projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from medphys_agentbench.item_diagnostics import (
    build_item_diagnostics_artifact,
    write_item_diagnostics_artifact,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_results_dir", type=Path)
    parser.add_argument("--leaderboard", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_item_diagnostics_artifact(
        args.release_results_dir,
        args.leaderboard,
        repository_root=ROOT,
    )
    if args.output:
        write_item_diagnostics_artifact(payload, args.output)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
