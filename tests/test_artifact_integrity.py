import base64
import hashlib
from pathlib import Path

import pytest

from medphys_agentbench.artifacts import (
    ArtifactIntegrityError,
    ollama_image_payloads,
    resolve_asset_reference,
)
from medphys_agentbench.contracts import ContextArtifact
from medphys_agentbench.task_loader import load_task


def _reference(path: Path, root: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"asset://{path.relative_to(root)}#sha256={digest}"


def test_asset_reference_is_root_bounded_and_digest_checked(tmp_path: Path) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"not-a-real-png-but-integrity-is-byte-level")
    reference = _reference(image, tmp_path)
    assert resolve_asset_reference(reference, tmp_path) == image

    with pytest.raises(ArtifactIntegrityError, match="digest mismatch"):
        resolve_asset_reference(reference[:-1] + "0", tmp_path)
    with pytest.raises(ArtifactIntegrityError, match="escapes"):
        resolve_asset_reference(
            "asset://../outside.png#sha256=" + "0" * 64,
            tmp_path,
        )


def test_ollama_images_are_binary_payloads_not_prompt_base64(tmp_path: Path) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fixture-bytes")
    artifact = ContextArtifact(
        artifact_id="image",
        media_type="image/png",
        content=_reference(image, tmp_path),
    )
    assert ollama_image_payloads((artifact,), tmp_path) == [
        base64.b64encode(b"fixture-bytes").decode("ascii")
    ]


def test_real_image_runtime_projection_hides_gold_geometry() -> None:
    task = load_task(
        Path("tasks/public/imaging/real_mri_hippocampus_localization_001/task.yaml")
    )
    runtime = task.runtime_task().to_dict()
    serialized = str(runtime)
    assert "minimum_iou" not in serialized
    assert "77.47" not in serialized
    assert "grading" not in runtime
