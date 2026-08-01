"""Read-only public API for release metadata and leaderboard artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def create_app(results_root: Path = Path("results/releases")) -> FastAPI:
    resolved_results_root = results_root.resolve()
    app = FastAPI(
        title="MedPhysBench API",
        version="0.2.0",
        description="Read-only benchmark artifacts. Research use only; not clinical authority.",
    )

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/releases")
    def releases() -> dict[str, Any]:
        items = []
        for path in sorted(results_root.glob("*/leaderboard.json"), reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "release": payload.get("release", {}).get("release_id", path.parent.name),
                    "generated_at": payload.get("generated_at"),
                    "models": len(payload.get("models", [])),
                    "tasks": len(payload.get("tasks", [])),
                }
            )
        return {"releases": items}

    @app.get("/v1/releases/{release}/leaderboard")
    def leaderboard(release: str) -> dict[str, Any]:
        path = _release_leaderboard_path(resolved_results_root, release)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Release not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/v1/releases/{release}/download")
    def download(release: str) -> FileResponse:
        path = _release_leaderboard_path(resolved_results_root, release)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Release not found.")
        return FileResponse(
            path,
            media_type="application/json",
            filename=f"{release}-leaderboard.json",
        )

    return app


def _release_leaderboard_path(results_root: Path, release: str) -> Path:
    path = (results_root / release / "leaderboard.json").resolve()
    if not path.is_relative_to(results_root):
        raise HTTPException(status_code=404, detail="Release not found.")
    return path


app = create_app()
