#!/usr/bin/env python3
"""Project canonical review ledgers into the public website data bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWS_DIR = ROOT / "reviews"
PUBLIC_DATA_DIR = ROOT / "web" / "public" / "data"


def build_projections() -> dict[Path, dict[str, object]]:
    projections: dict[Path, dict[str, object]] = {}
    for source in sorted(REVIEWS_DIR.glob("*.json")):
        payload = json.loads(source.read_text(encoding="utf-8"))
        release_id = str(payload["release_id"])
        projections[PUBLIC_DATA_DIR / f"{release_id}-review.json"] = payload
    return projections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    mismatches: list[str] = []
    for destination, payload in build_projections().items():
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not destination.is_file() or destination.read_text(encoding="utf-8") != rendered:
                mismatches.append(str(destination.relative_to(ROOT)))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8")

    if mismatches:
        raise SystemExit(f"Stale public review evidence projections: {', '.join(mismatches)}")


if __name__ == "__main__":
    main()
