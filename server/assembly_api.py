from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .cad.assembly_tree import serialize_assembly_tree


def create_assembly_router(workspace) -> APIRouter:
    router = APIRouter()

    @router.get("/api/models/{key}/assembly")
    def canonical_assembly(key: str):
        if key not in workspace.models:
            raise HTTPException(404, "model not found")
        return serialize_assembly_tree(workspace.models[key])

    return router
