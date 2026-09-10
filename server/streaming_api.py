from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
import gzip
import json

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

from .cad.step_reader import subshape_inventory
from .cad.view_derivative import PROFILES, ViewDerivativeStore


def create_streaming_router(workspace: Any, root: str | Path) -> APIRouter:
    router = APIRouter(prefix="/api")
    derivatives = ViewDerivativeStore(root)

    def require_model(key: str):
        model = workspace.models.get(key)
        if model is None:
            raise HTTPException(404, "model not found")
        return model

    @router.get("/models/{key}/viewer/manifest")
    def viewer_manifest(
        key: str,
        profile: Literal["preview", "normal", "evidence"] = "preview",
    ):
        model = require_model(key)
        return derivatives.manifest(key, model, profile=profile)

    @router.get("/models/{key}/viewer/cache")
    def viewer_cache(
        key: str,
        profile: Literal["preview", "normal", "evidence"] = "preview",
    ):
        model = require_model(key)
        return derivatives.cache_status(key, model, profile=profile)

    @router.get("/models/{key}/viewer/chunks/{chunk_id}")
    def viewer_chunk(
        key: str,
        chunk_id: str,
        profile: Literal["preview", "normal", "evidence"] = "preview",
    ):
        model = require_model(key)
        try:
            cache_path = derivatives.chunk_path(key, model, chunk_id, profile=profile)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

        if not cache_path.exists():
            try:
                derivatives.build_chunk(key, model, chunk_id, profile=profile)
            except Exception as exc:
                raise HTTPException(500, f"viewer chunk build failed: {exc}") from exc

        # Let the browser decode gzip directly. This avoids server-side inflate + re-encode copies.
        return FileResponse(
            cache_path,
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-CAD-Viewer-Cache": "HIT",
            },
        )

    @router.get("/models/{key}/inventory/summary")
    def inventory_summary(key: str):
        model = require_model(key)
        return {
            "model": key,
            "model_id": model.model_id,
            "version": model.version,
            "part_count": len(model.leaf_occurrences),
            "parts": [
                {
                    "path": item.path,
                    "name": item.name,
                    "bbox": item.bbox,
                    "valid": item.is_valid,
                }
                for item in model.leaf_occurrences
            ],
        }

    @router.get("/models/{key}/inventory/subshapes")
    def inventory_subshapes(
        key: str,
        path: str = Query(..., min_length=1),
        limit: int = Query(128, ge=1, le=1024),
    ):
        model = require_model(key)
        occurrence = model.occurrences.get(path)
        if occurrence is None:
            raise HTTPException(404, "occurrence not found")
        return {
            "model": key,
            "path": path,
            "subshapes": subshape_inventory(occurrence.shape, limit=limit),
        }

    @router.get("/models/{key}/viewer/legacy")
    def legacy_viewer_guard(key: str):
        """Explicit escape hatch for tiny fixtures only; large-model monolithic JSON is forbidden."""
        model = require_model(key)
        if len(model.leaf_occurrences) > 32:
            raise HTTPException(
                409,
                "large model must use /viewer/manifest + /viewer/chunks; monolithic viewer JSON is disabled",
            )
        return workspace.viewer_payload(key)

    return router
