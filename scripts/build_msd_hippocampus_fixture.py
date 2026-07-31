#!/usr/bin/env python3
"""Build the tiny, attributed MSD hippocampus fixture used by public vision tasks.

This script intentionally requires an operator-supplied copy of the upstream
NIfTI image and label. It never downloads data and never emits the gold mask as
an agent-visible artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(slice_data: np.ndarray) -> np.ndarray:
    finite = slice_data[np.isfinite(slice_data)]
    low, high = np.percentile(finite, [1.0, 99.0])
    clipped = np.clip(slice_data, low, high)
    scaled = (clipped - low) / max(high - low, np.finfo(float).eps)
    return np.round(scaled * 255.0).astype(np.uint8)


def _bbox(mask: np.ndarray) -> list[int]:
    rows, cols = np.where(mask)
    return [int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1]


def build_fixture(image_path: Path, label_path: Path, output_dir: Path) -> None:
    image = nib.load(image_path)
    label = nib.load(label_path)
    volume = np.asanyarray(image.dataobj)
    labels = np.asanyarray(label.dataobj)
    if volume.shape != labels.shape or volume.ndim != 3:
        raise ValueError("Image and label must be matching 3D volumes.")
    foreground_by_slice = np.sum(labels > 0, axis=(0, 1))
    slice_index = int(np.argmax(foreground_by_slice))
    pixels = _normalize(volume[:, :, slice_index])
    mask = labels[:, :, slice_index] > 0

    # Transpose to conventional row/column display, then enlarge without
    # inventing intensities. Gold coordinates remain on the native grid.
    displayed = np.flipud(pixels.T)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_out = output_dir / "hippocampus_367_axial_z16.png"
    rendered = Image.fromarray(displayed, mode="L").resize((576, 368), Image.Resampling.NEAREST)
    rendered.save(image_out)
    grid_out = output_dir / "hippocampus_367_axial_z16_grid16.png"
    gridded = rendered.convert("RGB")
    draw = ImageDraw.Draw(gridded)
    for index in range(17):
        x = round(index * gridded.width / 16)
        y = round(index * gridded.height / 16)
        draw.line((x, 0, x, gridded.height), fill=(0, 220, 255), width=1)
        draw.line((0, y, gridded.width, y), fill=(0, 220, 255), width=1)
    gridded.save(grid_out)

    # Convert the native mask to the same displayed orientation for a sealed
    # deterministic bbox. This value belongs in authoring/grader data only.
    displayed_mask = np.flipud(mask.T)
    bbox = _bbox(displayed_mask)
    manifest = {
        "schema_version": "medphysbench.fixture.v1",
        "fixture_id": "msd-hippocampus-367-axial-z16",
        "source_dataset": "Medical Segmentation Decathlon Task04 Hippocampus",
        "source_url": "https://msd-for-monai.s3.amazonaws.com/Task04_Hippocampus.tar",
        "dataset_page": "https://medicaldecathlon.com/",
        "dataset_license": "CC-BY-SA-4.0",
        "source_archive_sha256": "282d808a3e84e5a52f090d9dd4c0b0057b94a6bd51ad41569aef5ff303287771",
        "source_image_member": "Task04_Hippocampus/imagesTr/hippocampus_367.nii.gz",
        "source_label_member": "Task04_Hippocampus/labelsTr/hippocampus_367.nii.gz",
        "source_image_sha256": _sha256(image_path),
        "source_label_sha256": _sha256(label_path),
        "derived_image": image_out.name,
        "derived_image_sha256": _sha256(image_out),
        "derived_grid_image": grid_out.name,
        "derived_grid_image_sha256": _sha256(grid_out),
        "native_shape": list(volume.shape),
        "voxel_spacing_mm": [float(value) for value in image.header.get_zooms()[:3]],
        "selected_axis": 2,
        "selected_slice_index": slice_index,
        "display_transform": "transpose XY, vertical flip, nearest-neighbor resize 57x36 to 576x368",
        "gold_native_display_bbox_xyxy": bbox,
        "gold_foreground_voxels_on_slice": int(mask.sum()),
        "intended_use": "research benchmark fixture; not for diagnosis or clinical use",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("label", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    build_fixture(args.image, args.label, args.output_dir)


if __name__ == "__main__":
    main()
