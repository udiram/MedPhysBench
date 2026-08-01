from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_public_sanitizer_redacts_trace_raw_preview(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    model_dir = release_root / "model"
    model_dir.mkdir(parents=True)
    artifact_path = model_dir / "attempt.json"
    artifact_path.write_text(
        json.dumps(
            {
                "raw_response": {"content": "private response"},
                "trace": [{"event": "parse_error", "raw_preview": "private preview"}],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/sanitize_public_results.py", str(release_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert "content" not in artifact["raw_response"]
    assert artifact["raw_response"]["content_redacted"] is True
    assert "raw_preview" not in artifact["trace"][0]
    assert artifact["trace"][0]["raw_preview_redacted"] is True

    check = subprocess.run(
        [sys.executable, "scripts/sanitize_public_results.py", str(release_root), "--check"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0


def test_api_release_path_cannot_escape_results_root(tmp_path: Path) -> None:
    fastapi = pytest.importorskip("fastapi")
    from medphys_agentbench.api import _release_leaderboard_path

    results_root = (tmp_path / "results").resolve()
    results_root.mkdir()

    with pytest.raises(fastapi.HTTPException) as exc_info:
        _release_leaderboard_path(results_root, "../../private")

    assert exc_info.value.status_code == 404
