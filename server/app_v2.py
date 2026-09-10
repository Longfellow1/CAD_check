"""Electron-desktop runtime entrypoint.

The FastAPI process is an internal localhost sidecar for the Electron product.
Standalone browser use is allowed only as a developer debug harness.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi.responses import JSONResponse

from .app import app as base_app, workspace, ROOT
from .assembly_api import create_assembly_router
from .streaming_api import create_streaming_router

base_app.include_router(create_assembly_router(workspace))
base_app.include_router(create_streaming_router(workspace, ROOT))


class DesktopSessionGuard:
    """ASGI guard that can wrap an already-instantiated FastAPI app safely.

    Tests may import/start the base app before importing this module, so adding
    Starlette middleware at import time is unsafe. A thin ASGI wrapper keeps the
    Electron session contract without mutating middleware after startup.
    """

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
