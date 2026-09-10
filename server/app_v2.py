"""Electron-desktop Runtime Controller entrypoint.

The FastAPI process is an internal localhost control plane for the Electron
product.  Standalone browser use is only a developer harness.  Blocking STEP,
XCAF, tessellation and verification calls must go through ``/api/jobs`` so they
execute in the isolated CAD Worker process.
"""
from __future__ import annotations

import atexit
import os
from typing import Any

from fastapi.responses import JSONResponse

from .app import app as base_app, ROOT
from .desktop_api import create_desktop_router


desktop_router, cad_worker_manager = create_desktop_router(ROOT)
base_app.include_router(desktop_router)
atexit.register(cad_worker_manager.shutdown)


# Legacy routes remain on ``server.app`` for developer/backward compatibility,
# but Electron is forbidden from reaching them because they can execute OCCT in
# the Runtime Controller process.  This makes an accidental regression to the
# old synchronous Web architecture fail closed instead of silently blocking UI
# health/status/cancel calls.
def _legacy_heavy_path(path: str) -> bool:
    if path in {
        "/api/models/upload",
        "/api/models/register",
        "/api/runs/check",
        "/api/runs/regression",
        "/api/runs/explore",
    }:
        return True
    if path.startswith("/api/models/"):
        return True
    if path.startswith("/api/runs/") and path.endswith("/viewer"):
        return True
    return False


class DesktopSessionGuard:
    """ASGI guard for product form, session isolation and worker-only CAD I/O."""

    def __init__(self, inner: Any, token: str | None):
        self.inner = inner
        self.token = token

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if self.token and scope.get("type") == "http" and path.startswith("/api/"):
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
            if _legacy_heavy_path(path):
                response = JSONResponse(
                    status_code=410,
                    content={
                        "detail": "Legacy synchronous CAD endpoint disabled in Electron; submit an isolated /api/jobs task instead"
                    },
                )
                await response(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app = DesktopSessionGuard(base_app, os.environ.get("CAD_CHECK_SESSION_TOKEN"))
