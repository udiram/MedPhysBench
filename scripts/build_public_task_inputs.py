#!/usr/bin/env python3
"""Generate or verify the website's sealed public task-input catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from medphys_agentbench.public_task_inputs import build_public_task_input_catalog  # noqa: E402

DEFAULT_RELEASES = (
    ROOT / "releases" / "public_core_v0_4.yaml",
    ROOT / "releases" / "public_imaging_pilot_v0_4.yaml",
    ROOT / "releases" / "public_tg263_pilot_v0_5.yaml",
    ROOT / "releases" / "public_real_workflows_pilot_v0_6.yaml",
)
DEFAULT_OUTPUT = ROOT / "web" / "public" / "data" / "public_task_inputs.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = build_public_task_input_catalog(DEFAULT_RELEASES)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(f"Public task input catalog is stale: {args.output}")
        print(f"Verified {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
