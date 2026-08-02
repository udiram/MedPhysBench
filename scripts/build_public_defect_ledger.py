#!/usr/bin/env python3
"""Project the canonical benchmark defect ledger into the public website."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance" / "benchmark-defects.json"
DESTINATION = ROOT / "web" / "public" / "data" / "benchmark-defects.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = SOURCE.read_text(encoding="utf-8")
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Stale public defect-ledger projection: web/public/data/benchmark-defects.json")
        return

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
