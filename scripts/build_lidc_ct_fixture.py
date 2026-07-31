#!/usr/bin/env python3
"""Build a deterministic, reduced CT fixture from one public LIDC-IDRI series."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image, ImageDraw
from scipy import ndimage

SERIES_UID = "1.3.6.1.4.1.14519.5.2.1.6279.6001.314917368146772872954571551463"
ARCHIVE_SHA256 = "b80ef2947df822d82039a06ad0777639d6a395a46b676f9ed8e5fa8bab9a6b5d"
SOURCE_URL = (
    "https://services.cancerimagingarchive.net/nbia-api/services/v1/getImage"
    f"?SeriesInstanceUID={SERIES_UID}"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_middle_slice(archive: Path) -> pydicom.dataset.FileDataset:
    if sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("LIDC archive digest does not match the pinned upstream artifact.")
    with tempfile.TemporaryDirectory(prefix="medphysbench-lidc-") as directory:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(directory)
        datasets = []
        for path in Path(directory).glob("*.dcm"):
            dataset = pydicom.dcmread(path)
            z_position = float(dataset.ImagePositionPatient[2])
            datasets.append((z_position, dataset))
        datasets.sort(key=lambda item: item[0])
        return datasets[len(datasets) // 2][1]


def hu_pixels(dataset: pydicom.dataset.FileDataset) -> np.ndarray:
    pixels = dataset.pixel_array.astype(np.float32)
    slope = float(getattr(dataset, "RescaleSlope", 1.0))
    intercept = float(getattr(dataset, "RescaleIntercept", 0.0))
    return pixels * slope + intercept


def lung_mask(hu: np.ndarray) -> np.ndarray:
    mask = hu < -400
    mask = ndimage.binary_opening(mask, iterations=2)
    labels, count = ndimage.label(mask)
    if count:
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        border_labels = set(labels[0]) | set(labels[-1]) | set(labels[:, 0]) | set(labels[:, -1])
        candidates = [index for index in range(1, count + 1) if index not in border_labels]
        keep = sorted(candidates, key=lambda index: float(sizes[index - 1]))[-2:]
        mask = np.isin(labels, keep)
    return mask


def grid_cells(mask: np.ndarray, rows: int = 16, columns: int = 16) -> list[list[int]]:
    height, width = mask.shape
    cells: list[list[int]] = []
    for row in range(rows):
        y0, y1 = row * height // rows, (row + 1) * height // rows
        for column in range(columns):
            x0, x1 = column * width // columns, (column + 1) * width // columns
            if float(mask[y0:y1, x0:x1].mean()) >= 0.3:
                cells.append([row, column])
    return cells


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    dataset = read_middle_slice(args.archive)
    hu = hu_pixels(dataset)
    mask = lung_mask(hu)
    cells = grid_cells(mask)

    low, high = -1000.0, 400.0
    display = np.clip((hu - low) / (high - low), 0.0, 1.0)
    image = Image.fromarray(np.uint8(display * 255), mode="L").convert("RGB")
    draw = ImageDraw.Draw(image)
    for index in range(17):
        coordinate = index * image.width // 16
        draw.line((coordinate, 0, coordinate, image.height - 1), fill=(0, 220, 230), width=1)
        draw.line((0, coordinate, image.width - 1, coordinate), fill=(0, 220, 230), width=1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.output_dir / "lidc_0957_mid_chest_lung_window_grid16.png"
    image.save(image_path, optimize=True)
    manifest = {
        "schema_version": "medphysbench.imaging-fixture.v1",
        "collection": "LIDC-IDRI",
        "license": "CC-BY-3.0",
        "source_url": SOURCE_URL,
        "series_instance_uid": SERIES_UID,
        "upstream_archive_sha256": ARCHIVE_SHA256,
        "selected_slice_z_mm": float(dataset.ImagePositionPatient[2]),
        "pixel_spacing_mm": [float(value) for value in dataset.PixelSpacing],
        "slice_thickness_mm": float(dataset.SliceThickness),
        "display_window_hu": [int(low), int(high)],
        "derived_png": image_path.name,
        "derived_png_sha256": sha256(image_path),
        "reference_mask_method": (
            "HU < -400; morphology; two largest connected air components "
            "not touching the image border"
        ),
        "reference_grid_cells_30_percent": cells,
        "intended_use": "public research benchmark fixture; not a clinical contour",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"cell_count": len(cells), "png_sha256": sha256(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
