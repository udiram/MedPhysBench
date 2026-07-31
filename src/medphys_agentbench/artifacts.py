"""Integrity-checked runtime resolution for repository benchmark artifacts."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from .contracts import ContextArtifact


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact reference escapes its root or fails its digest."""


def resolve_asset_reference(reference: str, root: Path) -> Path:
    """Resolve ``asset://relative/path#sha256=<digest>`` below a declared root."""
    if not reference.startswith("asset://"):
        raise ArtifactIntegrityError("Only asset:// references may be resolved as files.")
    body = reference.removeprefix("asset://")
    relative, separator, fragment = body.partition("#")
    if not separator or not fragment.startswith("sha256="):
        raise ArtifactIntegrityError("Asset references must include a sha256 fragment.")
    expected = fragment.removeprefix("sha256=")
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ArtifactIntegrityError("Asset sha256 must be 64 lowercase hexadecimal characters.")

    root = root.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ArtifactIntegrityError("Asset reference escapes the configured artifact root.")
    if not candidate.is_file():
        raise ArtifactIntegrityError(f"Referenced artifact does not exist: {relative}")
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != expected:
        raise ArtifactIntegrityError(
            f"Artifact digest mismatch for {relative}: expected {expected}, observed {actual}."
        )
    return candidate


def ollama_image_payloads(artifacts: tuple[ContextArtifact, ...], root: Path) -> list[str]:
    images: list[str] = []
    for artifact in artifacts:
        if artifact.media_type.startswith("image/"):
            path = resolve_asset_reference(artifact.content, root)
            images.append(base64.b64encode(path.read_bytes()).decode("ascii"))
    return images
