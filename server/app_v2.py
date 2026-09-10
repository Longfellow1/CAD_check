"""Electron-desktop runtime entrypoint.

The FastAPI process is an internal localhost sidecar for the Electron product.
Standalone browser use is allowed only as a developer debug harness.
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from .app import app, workspace, ROOT
from .assembly_api import create_assembly_router
from .streaming_api import create_streaming_router

app.include_router(create_assembly_router(workspace))
app.include_router(create_streaming_router(workspace, ROOT))

_DESKTOP_SESSION_TOKEN = os.environ.get("CAD_CHECK_SESSION_TOKEN")


@app.middleware("http")
async def desktop_session_guard(request: Request, call_next):
    """Fail closed for desktop API calls when Electron started the sidecar.

    Debug browser mode intentionally has no token and remains available for
    renderer/API development, but it is not a product acceptance path.
    """
    if _DESKTOP_SESSION_TOKEN and request.url.path.startswith("/api/"):
        supplied = request.headers.get("X-CAD-Check-Session")
        product_form = request.headers.get("X-CAD-Check-Product-Form")
        if supplied != _DESKTOP_SESSION_TOKEN or product_form != "electron":
            return JSONResponse(
                status_code=403,
                content={"detail": "Electron desktop session required"},
            )
    return await call_next(request)
