"""Build small, checksum-pinned OpenKBP fixtures for public benchmark tasks.

The upstream cases contain real de-identified CT and expert structure masks.
OpenKBP augments them with standardized synthetic reference dose distributions;
the generated manifest preserves that distinction. Only compact PNG/JSON
derivatives are written to the repository.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import sys
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq
from PIL import Image, ImageDraw

DATASET = "oxkitsune/open-kbp"
DATASET_REVISION = "399a3f6d1c9aa9fd3f66677901666c670cead524"
UPSTREAM_REPOSITORY = "https://github.com/ababier/open-kbp"
UPSTREAM_REPOSITORY_REVISION = "ce625e62f3b04203f22bd9d1634f3e8fb0245e46"
PARQUET_URL = (
    "https://huggingface.co/datasets/oxkitsune/open-kbp/resolve/"
    "refs%2Fconvert%2Fparquet/default/test/0000.parquet"
)
PARQUET_SHA256 = "fab82af2d334cb4eb44d385c561353cc62d64002e6d2eef9b3821dca64fdf698"
SELECTED_PATIENTS = ("pt_289", "pt_242")
STRUCTURES = (
    "Brainstem",
    "SpinalCord",
    "RightParotid",
    "LeftParotid",
    "Esophagus",
    "Larynx",
    "Mandible",
    "PTV56",
    "PTV63",
    "PTV70",
)
CRITERIA = {
    "Brainstem": ("D0.1cc_Gy", "max", 50.0),
    "SpinalCord": ("D0.1cc_Gy", "max", 45.0),
    "RightParotid": ("Dmean_Gy", "max", 26.0),
    "LeftParotid": ("Dmean_Gy", "max", 26.0),
    "Esophagus": ("Dmean_Gy", "max", 45.0),
    "Larynx": ("Dmean_Gy", "max", 45.0),
    "Mandible": ("D0.1cc_Gy", "max", 73.5),
    "PTV56": ("D99_Gy", "min", 53.2),
    "PTV63": ("D99_Gy", "min", 59.9),
    "PTV70": ("D99_Gy", "min", 66.5),
}


def main() -> None:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = args.cache_dir or root / ".cache" / "openkb"
    cache.mkdir(parents=True, exist_ok=True)
    parquet_path = cache / "test-0000.parquet"
    _download_verified(parquet_path)
    parquet = pq.ParquetFile(parquet_path, memory_map=True, pre_buffer=False)
    patient_rows = _patient_rows(parquet)
    selected_patients = tuple(args.patient or SELECTED_PATIENTS)
    unknown = sorted(set(selected_patients) - patient_rows.keys())
    if unknown:
        raise SystemExit(f"Patients are not present in the pinned shard: {', '.join(unknown)}")

    for patient_id in selected_patients:
        row_index = patient_rows[patient_id]
        output_dir = root / "assets" / "planning" / "openkb" / patient_id
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = _patient_metadata(parquet, row_index)
        names = metadata["names"]
        voxel_dimensions = metadata["voxel_dimensions"]

        ct = _read_row_tensor(parquet, "ct", row_index, (128, 128, 128))
        _guard_rss(args.max_rss_mb, f"loading CT for {patient_id}")
        parotid_path = output_dir / "parotid_ct_grid16.png"

        masks = _read_row_tensor(
            parquet,
            "structure_masks",
            row_index,
            (128, 128, 128, 10),
            as_boolean=True,
        )
        _guard_rss(args.max_rss_mb, f"loading masks for {patient_id}")
        if names != STRUCTURES or masks.shape != (128, 128, 128, 10):
            raise RuntimeError(f"Unexpected OpenKBP row contract for {patient_id}: {names}, {masks.shape}")

        parotid_slice = int(np.argmax((masks[..., 2] | masks[..., 3]).sum(axis=(0, 1))))
        _save_ct_grid(ct[:, :, parotid_slice], parotid_path)
        _guard_rss(args.max_rss_mb, f"rendering CT for {patient_id}")

        dose = _read_row_tensor(parquet, "dose", row_index, (128, 128, 128))
        _guard_rss(args.max_rss_mb, f"loading dose for {patient_id}")
        high_dose_slice = int(np.argmax((dose >= 66.5).sum(axis=(0, 1))))
        dose_path = output_dir / "reference_dose_grid16.png"
        _save_dose_grid(ct[:, :, high_dose_slice], dose[:, :, high_dose_slice], dose_path)
        del ct
        gc.collect()

        metrics = _plan_metrics(dose, masks, voxel_dimensions)
        voxel_cc = float(np.prod(voxel_dimensions) / 1000.0)
        structure_inventory = {
            structure: {
                "has_contour": bool(masks[..., index].any()),
                "voxel_count": int(masks[..., index].sum()),
                "volume_cc": round(float(masks[..., index].sum()) * voxel_cc, 3),
            }
            for index, structure in enumerate(STRUCTURES)
        }
        parotid_union = masks[:, :, parotid_slice, 2] | masks[:, :, parotid_slice, 3]
        grid_gold = {
            "Parotid_R": _grid_cells(masks[:, :, parotid_slice, 2], occupancy=0.05),
            "Parotid_L": _grid_cells(masks[:, :, parotid_slice, 3], occupancy=0.05),
            "Parotids_bilateral": _grid_cells(parotid_union, occupancy=0.05),
            "dose_ge_66p5_Gy": _grid_cells(dose[:, :, high_dose_slice] >= 66.5, occupancy=0.25),
        }
        manifest = {
            "schema_version": "medphysbench.fixture.v1",
            "patient_id": patient_id,
            "source": {
                "dataset": DATASET,
                "dataset_revision": DATASET_REVISION,
                "parquet_url": PARQUET_URL,
                "parquet_sha256": PARQUET_SHA256,
                "official_repository": UPSTREAM_REPOSITORY,
                "official_repository_revision": UPSTREAM_REPOSITORY_REVISION,
                "upstream_challenge": "https://www.aapm.org/GrandChallenge/OpenKBP/",
                "upstream_paper_doi": "10.1002/mp.14845",
                "planning_criteria_source_doi": "10.1088/1361-6560/ac8044",
            },
            "data_character": {
                "ct": "real de-identified patient image sourced from TCIA",
                "structure_masks": "expert clinical contours from multiple institutions",
                "dose": "standardized synthetic clinical-quality OpenKBP reference plan",
            },
            "source_license": {
                "official_repository": "MIT",
                "dataset_mirror_card": "MIT",
                "note": "OpenKBP CTs originated in TCIA; upstream challenge and repository attribution retained",
            },
            "voxel_dimensions_mm": voxel_dimensions.tolist(),
            "structure_names": list(names),
            "structure_inventory": structure_inventory,
            "selected_slices": {
                "parotid_axial_index": parotid_slice,
                "high_dose_axial_index": high_dose_slice,
            },
            "plan_metrics": metrics,
            "grid_occupancy_thresholds": {
                "Parotid_R": 0.05,
                "Parotid_L": 0.05,
                "Parotids_bilateral": 0.05,
                "dose_ge_66p5_Gy": 0.25,
            },
            "grid_gold": grid_gold,
            "artifacts": {
                parotid_path.name: _sha256(parotid_path),
                dose_path.name: _sha256(dose_path),
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        del dose, masks
        gc.collect()
        _guard_rss(args.max_rss_mb, f"finishing {patient_id}")
        print(f"built {patient_id} (peak RSS {_peak_rss_mb():.0f} MB)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--patient",
        action="append",
        choices=SELECTED_PATIENTS,
        help="Build one selected patient. Repeat to build both; the default builds both sequentially.",
    )
    parser.add_argument(
        "--max-rss-mb",
        type=int,
        default=900,
        help="Abort if this process crosses the peak RSS ceiling (default: 900 MB).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Override the checksum-pinned download cache directory.",
    )
    args = parser.parse_args()
    if args.max_rss_mb < 512:
        parser.error("--max-rss-mb must be at least 512 for one decoded mask row")
    return args


def _patient_rows(parquet: pq.ParquetFile) -> dict[str, int]:
    rows: dict[str, int] = {}
    for index, batch in enumerate(
        parquet.iter_batches(batch_size=1, columns=["patient"], use_threads=False)
    ):
        rows[str(batch.column(0)[0].as_py())] = index
    return rows


def _patient_metadata(parquet: pq.ParquetFile, row_index: int) -> dict[str, Any]:
    for index, batch in enumerate(
        parquet.iter_batches(
            batch_size=1,
            columns=["structure_mask_names", "voxel_dimensions"],
            use_threads=False,
        )
    ):
        if index != row_index:
            continue
        return {
            "names": tuple(batch.column(0)[0].as_py()),
            "voxel_dimensions": np.asarray(batch.column(1)[0].as_py(), dtype=float),
        }
    raise IndexError(row_index)


def _read_row_tensor(
    parquet: pq.ParquetFile,
    column: str,
    row_index: int,
    shape: tuple[int, ...],
    *,
    as_boolean: bool = False,
) -> np.ndarray:
    """Decode one nested Arrow tensor without materializing Python lists."""

    for index, batch in enumerate(
        parquet.iter_batches(batch_size=1, columns=[column], use_threads=False)
    ):
        if index != row_index:
            del batch
            continue
        flat = batch.column(0)
        for _ in shape:
            flat = pc.list_flatten(flat)
        values = np.array(flat.to_numpy(zero_copy_only=False), dtype=np.float32, copy=True)
        expected = int(np.prod(shape))
        if values.size != expected:
            raise RuntimeError(f"Unexpected {column} size: {values.size}; expected {expected}")
        tensor = values.reshape(shape)
        if as_boolean:
            tensor = tensor > 0.5
        del flat, batch, values
        gc.collect()
        return tensor
    raise IndexError(row_index)


def _peak_rss_mb() -> float:
    peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux reports KiB.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def _guard_rss(max_rss_mb: int, stage: str) -> None:
    peak = _peak_rss_mb()
    if peak > max_rss_mb:
        raise MemoryError(
            f"OpenKBP fixture builder exceeded {max_rss_mb} MB after {stage} "
            f"(peak RSS {peak:.0f} MB; pid {os.getpid()})"
        )


def _download_verified(path: Path) -> None:
    if not path.exists() or _sha256(path) != PARQUET_SHA256:
        urllib.request.urlretrieve(PARQUET_URL, path)
    observed = _sha256(path)
    if observed != PARQUET_SHA256:
        raise RuntimeError(f"OpenKBP parquet checksum mismatch: {observed}")


def _plan_metrics(dose: np.ndarray, masks: np.ndarray, voxel_dimensions: np.ndarray) -> dict[str, Any]:
    voxel_cc = float(np.prod(voxel_dimensions) / 1000.0)
    result: dict[str, Any] = {}
    for index, structure in enumerate(STRUCTURES):
        values = np.asarray(dose[masks[..., index]], dtype=float)
        if values.size == 0:
            result[structure] = {
                "evaluable": False,
                "reason": "structure mask is empty in the source case",
                "value_Gy": None,
                "passed": None,
            }
            continue
        metric_name, direction, threshold = CRITERIA[structure]
        if metric_name == "Dmean_Gy":
            value = float(values.mean())
        elif metric_name == "D0.1cc_Gy":
            hottest_voxels = max(1, int(np.ceil(0.1 / voxel_cc)))
            values.partition(values.size - hottest_voxels)
            value = float(values[-hottest_voxels])
        elif metric_name == "D99_Gy":
            value = float(np.quantile(values, 0.01, method="linear"))
        else:
            raise RuntimeError(metric_name)
        passed = value <= threshold if direction == "max" else value >= threshold
        margin = threshold - value if direction == "max" else value - threshold
        result[structure] = {
            "evaluable": True,
            "metric": metric_name,
            "value_Gy": round(value, 2),
            "criterion": f"{metric_name} {'<=' if direction == 'max' else '>='} {threshold:g} Gy",
            "threshold_Gy": threshold,
            "passed": bool(passed),
            "margin_Gy": round(margin, 2),
        }
    return result


def _grid_cells(mask: np.ndarray, *, occupancy: float) -> list[list[int]]:
    if mask.shape != (128, 128):
        raise ValueError(mask.shape)
    cells: list[list[int]] = []
    for row in range(16):
        for column in range(16):
            tile = mask[row * 8 : (row + 1) * 8, column * 8 : (column + 1) * 8]
            if float(tile.mean()) >= occupancy:
                cells.append([row, column])
    return cells


def _save_ct_grid(ct_slice: np.ndarray, path: Path) -> None:
    normalized = np.clip((ct_slice + 200.0) / 500.0, 0.0, 1.0)
    image = Image.fromarray(np.uint8(normalized * 255), mode="L").resize((512, 512), Image.Resampling.BILINEAR)
    _draw_grid(image.convert("RGB"), path)


def _save_dose_grid(ct_slice: np.ndarray, dose_slice: np.ndarray, path: Path) -> None:
    normalized = np.clip((ct_slice + 200.0) / 500.0, 0.0, 1.0)
    base = np.stack([normalized, normalized, normalized], axis=-1)
    alpha = np.clip((dose_slice - 20.0) / 50.0, 0.0, 0.78)[..., None]
    heat = np.zeros_like(base)
    heat[..., 0] = np.clip((dose_slice - 35.0) / 35.0, 0.0, 1.0)
    heat[..., 1] = np.clip(1.0 - np.abs(dose_slice - 50.0) / 30.0, 0.0, 0.85)
    heat[..., 2] = np.clip((45.0 - dose_slice) / 35.0, 0.0, 0.7)
    blended = np.clip(base * (1.0 - alpha) + heat * alpha, 0.0, 1.0)
    image = Image.fromarray(np.uint8(blended * 255), mode="RGB").resize(
        (512, 512), Image.Resampling.BILINEAR
    )
    high_dose = dose_slice >= 66.5
    interior = high_dose.copy()
    interior[1:, :] &= high_dose[:-1, :]
    interior[:-1, :] &= high_dose[1:, :]
    interior[:, 1:] &= high_dose[:, :-1]
    interior[:, :-1] &= high_dose[:, 1:]
    boundary = high_dose & ~interior
    boundary_image = Image.fromarray(np.uint8(boundary) * 255, mode="L").resize(
        (512, 512), Image.Resampling.NEAREST
    )
    pixels = np.asarray(image).copy()
    pixels[np.asarray(boundary_image) > 0] = (255, 244, 210)
    image = Image.fromarray(pixels, mode="RGB")
    legend = ImageDraw.Draw(image)
    legend.rectangle((8, 8, 223, 28), fill=(18, 18, 16), outline=(255, 244, 210), width=1)
    legend.text((14, 12), "WHITE: reference dose >= 66.5 Gy", fill=(255, 244, 210))
    _draw_grid(image, path)


def _draw_grid(image: Image.Image, path: Path) -> None:
    draw = ImageDraw.Draw(image)
    color = (238, 183, 76)
    for index in range(17):
        coordinate = min(index * 32, 511)
        draw.line((coordinate, 0, coordinate, 511), fill=color, width=1)
        draw.line((0, coordinate, 511, coordinate), fill=color, width=1)
    image.save(path, optimize=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
