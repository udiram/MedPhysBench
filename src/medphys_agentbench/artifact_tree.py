"""Canonical inventories and tree hashes for JSON benchmark artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def json_artifact_inventory(directory: Path) -> list[dict[str, Any]]:
    """Inventory every JSON artifact below ``directory`` in stable path order."""
    if not directory.is_dir():
        raise ValueError(f"Artifact directory does not exist: {directory}")
    if directory.is_symlink():
        raise ValueError("Artifact directory must not be a symbolic link.")

    files = sorted(path for path in directory.rglob("*") if path.is_file())
    if not files:
        raise ValueError("Artifact directory is empty.")

    inventory: list[dict[str, Any]] = []
    for path in files:
        if path.is_symlink():
            raise ValueError(f"Artifacts must not be symbolic links: {path}")
        if path.suffix != ".json":
            raise ValueError(f"Only JSON artifacts are allowed: {path}")
        relative = path.relative_to(directory).as_posix()
        inventory.append(
            {
                "path": relative,
                "kind": "transport_error" if "_transport_errors" in path.parts else "result",
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return inventory


def artifact_tree_sha256(artifacts: list[dict[str, Any]]) -> str:
    """Hash a canonical artifact inventory using the public submission contract."""
    canonical = json.dumps(artifacts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
