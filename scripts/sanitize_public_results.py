#!/usr/bin/env python3
"""Remove provider reasoning from public result artifacts while retaining provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitize_raw_response(raw: dict[str, Any]) -> dict[str, Any]:
    sanitized = {
        key: value
        for key, value in raw.items()
        if key not in {"content", "thinking"}
    }
    content = raw.get("content")
    thinking = raw.get("thinking")
    if isinstance(content, str):
        sanitized["content_sha256"] = digest(content)
        sanitized["content_redacted"] = True
    if isinstance(thinking, str):
        sanitized["thinking_sha256"] = digest(thinking)
        sanitized["thinking_redacted"] = True
    return sanitized


def sanitize_tree(root: Path) -> int:
    changed = 0
    for path in sorted(root.glob("*/*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        raw = artifact.get("raw_response")
        if not isinstance(raw, dict) or (
            "content" not in raw and "thinking" not in raw
        ):
            continue
        artifact["raw_response"] = sanitize_raw_response(raw)
        path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        changed += 1
    return changed


def find_unsanitized(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.glob("*/*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        raw = artifact.get("raw_response")
        if isinstance(raw, dict) and (
            "content" in raw or "thinking" in raw
        ):
            paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        type=Path,
        help="Published release directory containing one directory per model.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail without editing if public artifacts contain provider reasoning.",
    )
    args = parser.parse_args()
    if args.check:
        unsanitized = find_unsanitized(args.root)
        if unsanitized:
            for path in unsanitized:
                print(path)
            raise SystemExit(
                f"{len(unsanitized)} public artifacts contain unredacted provider fields."
            )
        print("Public result artifacts contain no provider reasoning fields.")
        return
    changed = sanitize_tree(args.root)
    print(f"Sanitized {changed} public result artifacts.")


if __name__ == "__main__":
    main()
