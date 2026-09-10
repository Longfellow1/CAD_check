"""Electron-desktop runtime entrypoint.

The FastAPI process is an internal localhost Runtime Controller for the Electron
product.  Standalone browser use is allowed only as a developer debug harness.
Heavy OCP/OCCT work is submitted to an isolated CAD Worker through desktop_api.
"""
from __future__ import annotations

import atexit
import os
from typing import Any

from fastapi.responses import JSONResponse

from .app import app as base_app, workspace, ROOT
from .assembly_api import create_assembly_router
from .desktop_api import create_desktop_router
from .streaming_api import create_streaming_router

base_app.include_router(create_assembly_router(workspace))
base_app.include_router(create_streaming_router(workspace, ROOT))
desktop_router, cad_worker_manager = create_desktop_router(ROOT)
base_app.include_router(desktop_router)
atexit.register(cad_worker_manager.shutdown)


class DesktopSessionGuard:
    """ASGI guard that can wrap an already-instantiated FastAPI app safely."""

    def __init__(self, inner: Any, token: str | None):
        self.inner = inner
        self.token = token

    async def __call__(self, scope, receive, send):
        if self.token and scope.get("type") == "http" and scope.get("path", "").startswith("/api/"):
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            supplied = headers.get("x-cad-check-session")
            product_form = headers.get("x-cad-check-product-form")
            if supplied != self.token or product_form != "electron":
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Electron desktop session required"},
                )
                await response(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app = DesktopSessionGuard(base_app, os.environ.get("CAD_CHECK_SESSION_TOKEN"))
