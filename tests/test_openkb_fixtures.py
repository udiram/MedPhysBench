from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_openkb_real_fixtures",
    ROOT / "scripts" / "build_openkb_real_fixtures.py",
)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_nested_arrow_tensor_decodes_without_python_object_expansion(tmp_path: Path) -> None:
    parquet_path = tmp_path / "tensor.parquet"
    pq.write_table(pa.table({"tensor": pa.array([[[1.0, 2.0], [3.0, 4.0]]])}), parquet_path)
    parquet = pq.ParquetFile(parquet_path, memory_map=True, pre_buffer=False)

    tensor = builder._read_row_tensor(parquet, "tensor", 0, (2, 2))

    assert tensor.dtype == np.float32
    assert tensor.tolist() == [[1.0, 2.0], [3.0, 4.0]]
    assert ".as_py(" not in inspect.getsource(builder._read_row_tensor)


def test_openkb_rss_guard_aborts_above_declared_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builder, "_peak_rss_mb", lambda: 901.0)

    with pytest.raises(MemoryError, match="exceeded 900 MB"):
        builder._guard_rss(900, "unit test")


@pytest.mark.parametrize("patient_id", builder.SELECTED_PATIENTS)
def test_openkb_fixture_manifest_is_pinned_and_self_verifying(patient_id: str) -> None:
    fixture_dir = ROOT / "assets" / "planning" / "openkb" / patient_id
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "medphysbench.fixture.v1"
    assert manifest["patient_id"] == patient_id
    assert manifest["source"]["dataset_revision"] == builder.DATASET_REVISION
    assert manifest["source"]["parquet_sha256"] == builder.PARQUET_SHA256
    assert manifest["source"]["planning_criteria_source_doi"] == "10.1088/1361-6560/ac8044"
    assert manifest["data_character"]["ct"].startswith("real de-identified")
    assert manifest["data_character"]["dose"].startswith("standardized synthetic")
    assert manifest["structure_names"] == list(builder.STRUCTURES)

    for filename, expected_sha256 in manifest["artifacts"].items():
        observed = hashlib.sha256((fixture_dir / filename).read_bytes()).hexdigest()
        assert observed == expected_sha256

    for cells in manifest["grid_gold"].values():
        assert len(cells) == len({tuple(cell) for cell in cells})
        assert all(len(cell) == 2 and all(0 <= coordinate < 16 for coordinate in cell) for cell in cells)

    for metric in manifest["plan_metrics"].values():
        if metric["evaluable"]:
            assert isinstance(metric["value_Gy"], float)
            assert isinstance(metric["passed"], bool)
        else:
            assert metric["value_Gy"] is None
            assert metric["passed"] is None
