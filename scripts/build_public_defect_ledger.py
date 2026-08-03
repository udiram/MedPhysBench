#!/usr/bin/env python3
"""Project the canonical benchmark defect ledger into the public website."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SOURCE = ROOT / "governance" / "benchmark-defects.json"
DESTINATION = ROOT / "web" / "public" / "data" / "benchmark-defects.json"
RELEASES_DIR = ROOT / "releases"


def load_public_release_task_ids(releases_dir: Path = RELEASES_DIR) -> dict[str, frozenset[str]]:
    """Return the task IDs declared by each known public release manifest."""

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from medphys_agentbench.release_loader import load_release

    release_task_ids: dict[str, frozenset[str]] = {}
    for path in sorted(releases_dir.glob("*.yaml")):
        release = load_release(path)
        if any(access_class.value != "public" for access_class in release.allow_access_classes):
            continue
        if release.release_id in release_task_ids:
            raise ValueError(f"Duplicate release_id {release.release_id!r} in {path}.")
        release_task_ids[release.release_id] = frozenset(task.task_id for task in release.load_tasks())
    return release_task_ids


def build_public_projection(
    payload: Mapping[str, Any],
    *,
    release_task_ids: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, Any]:
    """Add a deterministic task-to-defect index without inferring task scope."""

    known_releases = (
        load_public_release_task_ids() if release_task_ids is None else release_task_ids
    )
    task_index: defaultdict[str, list[str]] = defaultdict(list)
    seen_defect_ids: set[str] = set()

    for entry in payload["entries"]:
        defect_id = str(entry["defect_id"])
        if defect_id in seen_defect_ids:
            raise ValueError(f"Duplicate defect_id {defect_id!r}.")
        seen_defect_ids.add(defect_id)

        affected_release_ids = [str(value) for value in entry["affected_release_ids"]]
        unknown_releases = sorted(set(affected_release_ids).difference(known_releases))
        if unknown_releases:
            raise ValueError(
                f"{defect_id}: unknown affected release {unknown_releases[0]!r}."
            )

        eligible_task_ids = set().union(
            *(known_releases[release_id] for release_id in affected_release_ids)
        )
        affected_task_ids = [str(value) for value in entry.get("affected_task_ids", [])]
        unknown_task_ids = sorted(set(affected_task_ids).difference(eligible_task_ids))
        if unknown_task_ids:
            raise ValueError(f"{defect_id}: unknown affected task {unknown_task_ids[0]!r}.")

        # Empty task scope is intentional for release-level defects. Do not expand it
        # to every task in a release because that would fabricate task-level impact.
        for task_id in set(affected_task_ids):
            task_index[task_id].append(defect_id)

    projection = dict(payload)
    projection["task_index"] = {
        task_id: sorted(defect_ids)
        for task_id, defect_ids in sorted(task_index.items())
    }
    return projection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    rendered = json.dumps(build_public_projection(payload), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Stale public defect-ledger projection: web/public/data/benchmark-defects.json")
        return

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
