"""Electron Desktop Runtime Controller.

This process is deliberately a *control plane*, not a CAD process.  It serves
only the Electron Renderer, Check Card metadata and job/replay APIs.  STEP/XCAF,
OCP/OCCT geometry, tessellation and verification are imported/executed only by
``server.cad_worker`` in a separate process.

Standalone browser access is a developer harness only.  When Electron supplies
``CAD_CHECK_SESSION_TOKEN`` every API call is session/product-form guarded.
"""
from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .check_registry import CheckCardRegistry
from .desktop_api import create_desktop_router


ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"
WEB = WEB_DIST if WEB_DIST.exists() else ROOT / "web"

base_app = FastAPI(title="CAD Check Electron Runtime Controller", version="0.3.0")
base_app.mount("/static", StaticFiles(directory=WEB), name="static")

cards = CheckCardRegistry(ROOT / "checks")
desktop_router, cad_worker_manager = create_desktop_router(ROOT)
base_app.include_router(desktop_router)
# Uvicorn normally gives the sidecar a graceful shutdown window, but relying
# on ``atexit`` alone leaves the independently-grouped CAD Worker behind when
# Electron is interrupted from a terminal. Bind cleanup to ASGI shutdown as
# well so Scania jobs cannot survive the Desktop process.
base_app.add_event_handler("shutdown", cad_worker_manager.shutdown)
atexit.register(cad_worker_manager.shutdown)


@base_app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@base_app.get("/api/health")
def health():
    # Do not import OCP here.  CAD Worker health has a separate endpoint.
    return {
        "ok": True,
        "version": "0.3.0",
        "product_form": "electron",
        "role": "runtime-controller",
    }


@base_app.get("/api/check-cards")
def check_cards():
    cards.reload()
    return [card.model_dump(mode="json") for card in cards.list()]


class DesktopSessionGuard:
    """ASGI guard for the Electron-only product contract."""

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
        await self.inner(scope, receive, send)


app = DesktopSessionGuard(base_app, os.environ.get("CAD_CHECK_SESSION_TOKEN"))
