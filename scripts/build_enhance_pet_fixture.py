#!/usr/bin/env python3
"""Build a deterministic whole-body PET MIP fixture from ENHANCE.PET 1.6k."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw

SOURCE_URL = "https://enhance-pet-1-6k.s3.us-west-2.amazonaws.com/imaging-data/images/PT/0001.nii.gz"
SOURCE_SHA256 = "3e86576c9214b12c6e065a5590d84d5dc30ae2a101a967d28a2694bd6b7a5805"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_nifti", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if sha256(args.source_nifti) != SOURCE_SHA256:
        raise ValueError("ENHANCE.PET source digest does not match the pinned artifact.")

    volume = nib.load(args.source_nifti).get_fdata(dtype=np.float32)
    mip = np.flipud(volume.max(axis=1).T)
    positive = mip[mip > 0]
    upper = float(np.percentile(positive, 99.5))
    display = np.log1p(np.clip(mip, 0, upper))
    display /= float(display.max())
    image = Image.fromarray(np.uint8(display * 255), mode="L")
    image = image.resize((512, 768), Image.Resampling.BILINEAR).convert("RGB")
    draw = ImageDraw.Draw(image)
    for column in range(17):
        x = column * image.width // 16
        draw.line((x, 0, x, image.height - 1), fill=(0, 220, 230), width=1)
    for row in range(25):
        y = row * image.height // 24
        draw.line((0, y, image.width - 1, y), fill=(0, 220, 230), width=1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.output_dir / "enhance_pet_0001_coronal_mip_grid16x24.png"
    image.save(image_path, optimize=True)
    manifest = {
        "schema_version": "medphysbench.imaging-fixture.v1",
        "collection": "ENHANCE.PET 1.6k",
        "source_cohort": "AutoPET Challenge",
        "source_subject": "0001",
        "source_cohort_label": "NEGATIVE",
        "license": "CC-BY-NC-4.0",
        "source_url": SOURCE_URL,
        "source_nifti_sha256": SOURCE_SHA256,
        "transform": "coronal maximum-intensity projection; log1p; 99.5 percentile clipping; 16x24 cyan grid",
        "derived_png": image_path.name,
        "derived_png_sha256": sha256(image_path),
        "bladder_reference_bbox_xyxy": [220, 610, 302, 666],
        "intended_use": "non-commercial public research benchmark fixture; not diagnosis",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"png_sha256": sha256(image_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
