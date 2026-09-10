from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .desktop_contract import load_replay_record, save_replay_state
from .job_runtime import CadWorkerManager


class ModelPathRequest(BaseModel):
    path: str
    key: str | None = None
    model_id: str | None = None
    version: str = "LOCAL"
    coordinate_contract: str = "X-forward/Y-left/Z-up"


class JobRequest(BaseModel):
    kind: Literal[
        "OPEN_MODEL",
        "DETAIL",
        "CHECK",
        "CHECK_SET",
        "REGRESSION",
        "EXPLORE",
        "EVIDENCE_DETAIL",
        "PING",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_s: float | None = Field(default=None, ge=0.1, le=3600.0)


class ReplayStateRequest(BaseModel):
    state: dict[str, Any]


class ScreenshotRequest(BaseModel):
    data_url: str


def create_desktop_router(root: str | Path) -> tuple[APIRouter, CadWorkerManager]:
    root = Path(root).resolve()
    router = APIRouter(prefix="/api")
    manager = CadWorkerManager(root)
    run_root = root / ".cadcheck" / "runs"

    def timeout_for(kind: str) -> float:
        return {
            "PING": 15.0,
            "OPEN_MODEL": 900.0,
            "DETAIL": 300.0,
            "EVIDENCE_DETAIL": 300.0,
            "CHECK": 300.0,
            "CHECK_SET": 900.0,
            "REGRESSION": 1200.0,
            "EXPLORE": 300.0,
        }.get(kind, 300.0)

    @router.get("/desktop/models")
    def desktop_models():
        return manager.model_descriptors()

    @router.post("/desktop/models/register")
    def register_model(request: ModelPathRequest):
        try:
            descriptor = manager.register_model_path(
                request.path,
                key=request.key,
                model_id=request.model_id,
                version=request.version,
                coordinate_contract=request.coordinate_contract,
            )
            job = manager.submit(
                "OPEN_MODEL",
                {"model": descriptor["key"], "descriptor": descriptor},
                timeout_s=timeout_for("OPEN_MODEL"),
            )
            return {"descriptor": descriptor, "job": job}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/desktop/worker")
    def worker_status():
        try:
            manager.ensure_running()
            return manager.worker_status()
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    @router.post("/desktop/worker/restart")
    def worker_restart():
        try:
            return manager.restart()
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    @router.post("/jobs")
    def submit_job(request: JobRequest):
        try:
            return manager.submit(
                request.kind,
                request.payload,
                timeout_s=request.timeout_s or timeout_for(request.kind),
            )
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            return manager.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(404, "job not found") from exc

    @router.delete("/jobs/{job_id}")
    def cancel_job(job_id: str):
        try:
            return manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(404, "job not found") from exc

    @router.get("/runs/{run_id}")
    def run_result(run_id: str):
        path = run_root / run_id / "result.json"
        if not path.exists():
            raise HTTPException(404, "run not found")
        return FileResponse(path, media_type="application/json")

    @router.get("/runs/{run_id}/trace")
    def run_trace(run_id: str):
        path = run_root / run_id / "trace.jsonl"
        if not path.exists():
            raise HTTPException(404, "trace not found")
        return FileResponse(path, media_type="application/x-ndjson")

    @router.post("/runs/{run_id}/evidence/{case_id}/screenshot")
    def persist_screenshot(run_id: str, case_id: str, request: ScreenshotRequest):
        prefix = "data:image/png;base64,"
        if not request.data_url.startswith(prefix):
            raise HTTPException(400, "expected PNG data URL")
        try:
            payload = base64.b64decode(request.data_url[len(prefix):], validate=True)
        except Exception as exc:
            raise HTTPException(400, "invalid PNG base64") from exc
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(400, "invalid PNG signature")
        path = run_root / run_id / "evidence" / f"{case_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {"saved": str(path), "bytes": len(payload)}

    @router.post("/runs/{run_id}/evidence/{case_id}/view-state")
    def persist_view_state(run_id: str, case_id: str, request: ReplayStateRequest):
        if not (run_root / run_id / "result.json").exists():
            raise HTTPException(404, "run not found")
        try:
            path = save_replay_state(run_root, run_id, case_id, request.state)
            return {"saved": str(path)}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("/runs/{run_id}/evidence/{case_id}/replay")
    def replay_record(run_id: str, case_id: str):
        try:
            record = load_replay_record(run_root, run_id, case_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "run not found") from exc
        screenshot_path = record.get("screenshot_path")
        record["screenshot_url"] = (
            f"/api/runs/{run_id}/evidence/{case_id}/screenshot-file"
            if screenshot_path
            else None
        )
        record.pop("screenshot_path", None)
        return record

    @router.get("/runs/{run_id}/evidence/{case_id}/screenshot-file")
    def replay_screenshot(run_id: str, case_id: str):
        path = run_root / run_id / "evidence" / f"{case_id}.png"
        if not path.exists():
            raise HTTPException(404, "screenshot not found")
        return FileResponse(path, media_type="image/png")

    return router, manager
