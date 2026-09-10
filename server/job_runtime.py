from __future__ import annotations

"""Runtime Controller for isolated CAD Worker jobs.

FastAPI owns this controller; blocking OCP/OCCT work runs in a separate Python
process.  The controller therefore keeps health/status/cancel responsive even
when a CAD call is pathological.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

import yaml


TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_key(stem: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_").upper()
    return value[:64] or f"MODEL_{uuid.uuid4().hex[:8].upper()}"


class CadWorkerManager:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.spool = self.root / ".cadcheck" / "jobs"
        self.spool.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / ".cadcheck" / "desktop_models.json"
        self.process: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._stop_monitor = threading.Event()
        self._monitor: threading.Thread | None = None

    def _status_path(self, job_id: str) -> Path:
        return self.spool / f"{job_id}.status.json"

    def _result_path(self, job_id: str) -> Path:
        return self.spool / f"{job_id}.result.json"

    def _request_path(self, job_id: str) -> Path:
        return self.spool / f"{job_id}.request.json"

    def model_descriptors(self) -> dict[str, dict[str, Any]]:
        """List models without parsing STEP geometry."""
        result: dict[str, dict[str, Any]] = {}
        manifest_path = self.root / "models" / "demo_manifest.yaml"
        if manifest_path.exists():
            try:
                manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                for key, spec in (manifest.get("models") or {}).items():
                    step = Path(spec["step"])
                    source = step if step.is_absolute() else self.root / step
                    if source.exists():
                        result[key] = {
                            "key": key,
                            "step": str(source.resolve()),
                            "model_id": spec.get("model_id") or key.lower(),
                            "version": spec.get("version") or key,
                            "coordinate_contract": spec.get("coordinate_contract") or "X-forward/Y-left/Z-up",
                            "source": "controlled",
                        }
            except Exception:
                pass

        custom = _load_json(self.registry_path, {}) or {}
        for key, spec in custom.items():
            source = Path(spec.get("step", ""))
            if source.exists():
                result[key] = {**spec, "key": key, "source": spec.get("source", "local")}

        # Developer/local engineering datasets stay outside git.  Discover them
        # by filename only; do not parse them on Runtime startup.
        step_dir = self.root / "data" / "step"
        if step_dir.exists():
            controlled_names = {Path(item["step"]).name for item in result.values() if item.get("source") == "controlled"}
            for source in sorted([*step_dir.glob("*.step"), *step_dir.glob("*.stp")]):
                if source.name in controlled_names:
                    continue
                key = "SCANIA" if "scania" in source.stem.lower() else _safe_key(source.stem)
                result.setdefault(key, {
                    "key": key,
                    "step": str(source.resolve()),
                    "model_id": source.stem,
                    "version": "LOCAL",
                    "coordinate_contract": "X-forward/Y-left/Z-up",
                    "source": "local-discovered",
                })
        return result

    def register_model_path(
        self,
        source: str | Path,
        *,
        key: str | None = None,
        model_id: str | None = None,
        version: str = "LOCAL",
        coordinate_contract: str = "X-forward/Y-left/Z-up",
    ) -> dict[str, Any]:
        path = Path(source).expanduser().resolve()
        if path.suffix.lower() not in {".step", ".stp"}:
            raise ValueError("only .step/.stp is supported")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        resolved_key = key or ("SCANIA" if "scania" in path.stem.lower() else _safe_key(path.stem))
        descriptor = {
            "key": resolved_key,
            "step": str(path),
            "model_id": model_id or path.stem,
            "version": version,
            "coordinate_contract": coordinate_contract,
            "source": "local",
        }
        registry = _load_json(self.registry_path, {}) or {}
        registry[resolved_key] = descriptor
        _atomic_json(self.registry_path, registry)
        return descriptor

    def _spawn_worker(self) -> subprocess.Popen:
        kwargs: dict[str, Any] = {
            "cwd": str(self.root),
            "stdin": subprocess.DEVNULL,
            "stdout": None,
            "stderr": None,
            "env": {**os.environ, "PYTHONUNBUFFERED": "1", "CAD_CHECK_WORKER": "1"},
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(
            [sys.executable, "-m", "server.cad_worker", "--root", str(self.root), "--spool", str(self.spool)],
            **kwargs,
        )

    def ensure_running(self) -> dict[str, Any]:
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                self._ensure_monitor()
                return self.worker_status()
            self.process = self._spawn_worker()
            self._ensure_monitor()
            return self.worker_status()

    def _ensure_monitor(self) -> None:
        if self._monitor and self._monitor.is_alive():
            return
        self._stop_monitor.clear()
        self._monitor = threading.Thread(target=self._monitor_loop, name="cad-worker-monitor", daemon=True)
        self._monitor.start()

    def _terminate_worker(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            self.process = None
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/pid", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2.5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
        finally:
            self.process = None

    def restart(self) -> dict[str, Any]:
        with self._lock:
            current = _load_json(self.spool / "current.json")
            self._terminate_worker()
            (self.spool / "current.json").unlink(missing_ok=True)
            if current:
                job_id = current.get("job_id")
                status = _load_json(self._status_path(job_id), {}) or {}
                if status.get("state") not in TERMINAL_STATES:
                    _atomic_json(self._status_path(job_id), {
                        **status,
                        "state": "FAILED",
                        "progress_phase": "WORKER_RESTARTED",
                        "message": "CAD Worker restarted while job was running",
                        "error_code": "WORKER_RESTARTED",
                        "updated_at": now_iso(),
                        "finished_at": now_iso(),
                    })
            self.process = self._spawn_worker()
            return self.worker_status()

    def shutdown(self) -> None:
        self._stop_monitor.set()
        with self._lock:
            self._terminate_worker()

    def worker_status(self) -> dict[str, Any]:
        process = self.process
        alive = bool(process is not None and process.poll() is None)
        heartbeat = _load_json(self.spool / "worker-heartbeat.json") or {}
        current = _load_json(self.spool / "current.json")
        return {
            "state": "RUNNING" if alive else "STOPPED",
            "pid": process.pid if alive else None,
            "heartbeat": heartbeat.get("at"),
            "current_job": current,
        }

    def submit(self, kind: str, payload: dict[str, Any] | None = None, *, timeout_s: float = 300.0) -> dict[str, Any]:
        self.ensure_running()
        job_id = uuid.uuid4().hex[:16]
        created = now_iso()
        status = {
            "job_id": job_id,
            "kind": kind.upper(),
            "state": "QUEUED",
            "progress_phase": "QUEUED",
            "message": "等待 CAD Worker",
            "created_at": created,
            "started_at": None,
            "updated_at": created,
            "finished_at": None,
            "timeout_s": float(timeout_s),
            "deadline_epoch": time.time() + float(timeout_s),
            "worker_pid": None,
            "error_code": None,
            "error_message": None,
        }
        _atomic_json(self._status_path(job_id), status)
        _atomic_json(self._request_path(job_id), {
            "job_id": job_id,
            "kind": kind.upper(),
            "payload": payload or {},
            "timeout_s": float(timeout_s),
            "created_at": created,
        })
        return status

    def get_job(self, job_id: str, *, include_result: bool = True) -> dict[str, Any]:
        status = _load_json(self._status_path(job_id))
        if not status:
            raise KeyError(job_id)
        if include_result and status.get("state") == "SUCCEEDED":
            result = _load_json(self._result_path(job_id), {}) or {}
            status = {**status, "result": result.get("result")}
        return status

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            status = self.get_job(job_id, include_result=False)
            if status.get("state") in TERMINAL_STATES:
                return status
            request = self._request_path(job_id)
            if request.exists():
                request.unlink(missing_ok=True)
                updated = {
                    **status,
                    "state": "CANCELLED",
                    "progress_phase": "CANCELLED",
                    "message": "用户取消",
                    "updated_at": now_iso(),
                    "finished_at": now_iso(),
                }
                _atomic_json(self._status_path(job_id), updated)
                return updated

            current = _load_json(self.spool / "current.json") or {}
            if current.get("job_id") == job_id:
                self._terminate_worker()
                (self.spool / "current.json").unlink(missing_ok=True)
                updated = {
                    **status,
                    "state": "CANCELLED",
                    "progress_phase": "WORKER_RESTARTING",
                    "message": "底层 CAD 调用已通过终止 Worker 取消",
                    "updated_at": now_iso(),
                    "finished_at": now_iso(),
                }
                _atomic_json(self._status_path(job_id), updated)
                self.process = self._spawn_worker()
                return updated
            return status

    def _monitor_loop(self) -> None:
        while not self._stop_monitor.wait(0.2):
            try:
                with self._lock:
                    process = self.process
                    current = _load_json(self.spool / "current.json") or {}
                    if process is not None and process.poll() is not None:
                        self.process = None
                        job_id = current.get("job_id")
                        if job_id:
                            status = _load_json(self._status_path(job_id), {}) or {}
                            if status.get("state") not in TERMINAL_STATES:
                                _atomic_json(self._status_path(job_id), {
                                    **status,
                                    "state": "FAILED",
                                    "progress_phase": "WORKER_CRASHED",
                                    "message": "CAD Worker unexpectedly exited",
                                    "error_code": "WORKER_CRASHED",
                                    "updated_at": now_iso(),
                                    "finished_at": now_iso(),
                                })
                            (self.spool / "current.json").unlink(missing_ok=True)
                        continue

                    job_id = current.get("job_id")
                    if not job_id:
                        continue
                    status = _load_json(self._status_path(job_id), {}) or {}
                    deadline = status.get("deadline_epoch")
                    if deadline and time.time() > float(deadline) and status.get("state") not in TERMINAL_STATES:
                        self._terminate_worker()
                        (self.spool / "current.json").unlink(missing_ok=True)
                        _atomic_json(self._status_path(job_id), {
                            **status,
                            "state": "TIMED_OUT",
                            "progress_phase": "WORKER_RESTARTING",
                            "message": f"CAD job exceeded {status.get('timeout_s')} seconds",
                            "error_code": "TIMED_OUT",
                            "updated_at": now_iso(),
                            "finished_at": now_iso(),
                        })
                        self.process = self._spawn_worker()
            except Exception:
                # Monitoring must never take down the Runtime Controller.
                continue
