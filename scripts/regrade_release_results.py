#!/usr/bin/env python3
"""Recompute derived grades in stored public results after a declared grader update."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from medphys_agentbench.release_loader import load_release
from medphys_agentbench.scoring import (
    grades_pass,
    grades_safe,
    score_attempt,
    weighted_grade_score,
)


def derived_fields(task: Any, output: dict[str, Any]) -> dict[str, Any]:
    grades = score_attempt(task, output)
    return {
        "grades": [grade.to_dict() for grade in grades],
        "passed": grades_pass(grades),
        "safe": grades_safe(grades),
        "score": weighted_grade_score(grades),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_file", type=Path)
    parser.add_argument("--results-dir", type=Path, default=Path("results/releases"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    release = load_release(args.release_file)
    tasks = {task.task_id: task for task in release.load_tasks()}
    changed: list[Path] = []
    for path in sorted((args.results_dir / release.release_id).glob("*/*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "completed":
            continue
        task_id = payload.get("manifest", {}).get("task_id")
        task = tasks.get(task_id)
        output = payload.get("output")
        if task is None or not isinstance(output, dict):
            continue
        expected = derived_fields(task, output)
        if any(payload.get(key) != value for key, value in expected.items()):
            changed.append(path)
            if not args.check:
                payload.update(expected)
                path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"changed_count": len(changed), "release_id": release.release_id}, sort_keys=True))
    if args.check and changed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
