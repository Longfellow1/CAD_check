from __future__ import annotations

"""Isolated CAD worker for blocking OCP/OCCT work.

The worker communicates with the FastAPI Runtime Controller through an on-disk
job spool.  This intentionally keeps OCCT stdout/stderr away from an IPC
protocol and gives the controller a hard process boundary it can terminate on
cancel/timeout without taking down Electron.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import traceback
import uuid
from typing import Any

from .cases import CASES
from .desktop_contract import enrich_execution, rewrite_run_result, strict_compare
from .domain import VerificationCase, VerificationMode
from .stage2_runtime import Stage2Workspace, run_step_model
from .cad.assembly_tree import serialize_assembly_tree
from .cad.tessellation import tessellate_occurrence_paths


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path, default: Any = None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _descriptor_registry(root: Path) -> dict[str, Any]:
    return load_json(root / ".cadcheck" / "desktop_models.json", {}) or {}


def _ensure_model(workspace: Stage2Workspace, root: Path, key: str, supplied: dict[str, Any] | None = None):
    if key in workspace.models:
        return workspace.models[key]
    descriptor = supplied or _descriptor_registry(root).get(key)
    if not descriptor:
        raise KeyError(f"model not registered: {key}")
    source = Path(descriptor["step"])
    if not source.is_absolute():
        source = root / source
    return workspace.register_model(
        key,
        step=source,
        model_id=descriptor.get("model_id") or key.lower(),
        version=descriptor.get("version") or "LOCAL",
        coordinate_contract=descriptor.get("coordinate_contract") or "X-forward/Y-left/Z-up",
    )


def _case_lookup(workspace: Stage2Workspace, case_id: str) -> VerificationCase:
    return workspace.case_definition(case_id)


def _enrich_single(root: Path, workspace: Stage2Workspace, model_key: str, result: dict[str, Any]):
    case = result["case"]
    execution = result["execution"]
    enrich_execution(
        root,
        workspace.models[model_key],
        case,
        execution,
        workspace.binding_data,
        rule_version=execution.check_card_version or case.source_ref,
    )
    rewrite_run_result(result["run_dir"], execution=execution)
    return {
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "mode": result["mode"].value if hasattr(result["mode"], "value") else str(result["mode"]),
        "model": model_key,
        "case": case.model_dump(mode="json"),
        "execution": execution.model_dump(mode="json"),
    }


def _write_check_set(root: Path, workspace: Stage2Workspace, model_key: str, cases: list[VerificationCase]):
    model = workspace.models[model_key]
    executions = run_step_model(model, workspace.binding_data, cases)
    for case, execution in zip(cases, executions, strict=True):
        enrich_execution(root, model, case, execution, workspace.binding_data, rule_version=case.source_ref)

    run_id = uuid.uuid4().hex[:12]
    run_dir = workspace.store.create_run_dir(run_id)
    payload = {
        "run_id": run_id,
        "created_at": now_iso(),
        "mode": VerificationMode.ENGINEERING_CHECK.value,
        "models": {"model": model_key},
        "cases": [case.model_dump(mode="json") for case in cases],
        "executions": [item.model_dump(mode="json") for item in executions],
        "bindings": workspace.binding_data,
    }
    atomic_json(run_dir / "result.json", payload)
    workspace.store._write_trace(run_dir, run_id, "check_set", executions)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "mode": VerificationMode.ENGINEERING_CHECK.value,
        "model": model_key,
        "cases": payload["cases"],
        "executions": payload["executions"],
    }


def _enrich_regression(root: Path, workspace: Stage2Workspace, result: dict[str, Any], cases: list[VerificationCase], baseline_key: str, candidate_key: str):
    baseline_model = workspace.models[baseline_key]
    candidate_model = workspace.models[candidate_key]
    for case, execution in zip(cases, result["baseline"], strict=True):
        enrich_execution(root, baseline_model, case, execution, workspace.binding_data, rule_version=case.source_ref)
    for case, execution in zip(cases, result["candidate"], strict=True):
        enrich_execution(root, candidate_model, case, execution, workspace.binding_data, rule_version=case.source_ref)
    regression = [
        strict_compare(b, c, case)
        for case, b, c in zip(cases, result["baseline"], result["candidate"], strict=True)
    ]
    result["regression"] = regression
    rewrite_run_result(
        result["run_dir"],
        baseline=result["baseline"],
        candidate=result["candidate"],
        regression=regression,
    )
    return {
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "mode": VerificationMode.REGRESSION_COMPARE.value,
        "cases": [case.model_dump(mode="json") for case in cases],
        "baseline": [item.model_dump(mode="json") for item in result["baseline"]],
        "candidate": [item.model_dump(mode="json") for item in result["candidate"]],
        "regression": [item.model_dump(mode="json") for item in regression],
    }


def execute_job(root: Path, workspace: Stage2Workspace, kind: str, payload: dict[str, Any], progress):
    kind = kind.upper()
    if kind == "PING":
        return {"ok": True, "worker_pid": os.getpid()}

    if kind == "OPEN_MODEL":
        progress("READING", "读取 STEP / AP242")
        key = payload["model"]
        model = _ensure_model(workspace, root, key, payload.get("descriptor"))
        progress("INVENTORY", "构建 Canonical AssemblyTree")
        assembly = serialize_assembly_tree(model)
        return {
            "model": key,
            "model_id": model.model_id,
            "version": model.version,
            "source_unit": model.source_unit,
            "coordinate_contract": model.coordinate_contract,
            "schema": model.schema,
            "leaf_count": len(model.leaf_occurrences),
            "assembly": assembly,
        }

    if kind == "DETAIL":
        progress("TESSELLATING", "生成局部 Viewer Detail")
        model = _ensure_model(workspace, root, payload["model"])
        return tessellate_occurrence_paths(
            model,
            list(payload.get("paths") or []),
            deviation=float(payload.get("deviation", 0.4)),
            angular_tolerance=float(payload.get("angular_tolerance", 0.4)),
            render_edges=bool(payload.get("render_edges", False)),
        )

    if kind == "CHECK":
        progress("CHECKING", "执行工程校核")
        key = payload["model"]
        _ensure_model(workspace, root, key)
        result = workspace.run_check(key, payload["card_id"], binding_data=payload.get("bindings"))
        progress("FINALIZING", "固化 Evidence")
        return _enrich_single(root, workspace, key, result)

    if kind == "CHECK_SET":
        progress("CHECKING", "执行 Check Set")
        key = payload["model"]
        _ensure_model(workspace, root, key)
        case_ids = payload.get("case_ids")
        cases = [_case_lookup(workspace, case_id) for case_id in case_ids] if case_ids else list(CASES)
        progress("FINALIZING", "固化批量 Evidence")
        return _write_check_set(root, workspace, key, cases)

    if kind == "EXPLORE":
        progress("CHECKING", "执行探索测量")
        key = payload["model"]
        _ensure_model(workspace, root, key)
        result = workspace.run_explore(
            key,
            target=payload["target"],
            counterpart=payload.get("counterpart"),
            executor=payload["executor"],
            axis=payload.get("axis"),
            angle_axis=payload.get("angle_axis"),
            binding_data=payload.get("bindings"),
            title=payload.get("title", "快速测量"),
        )
        progress("FINALIZING", "固化测量结果")
        return _enrich_single(root, workspace, key, result)

    if kind == "REGRESSION":
        baseline_key = payload.get("baseline", "V1")
        candidate_key = payload.get("candidate", "V2")
        progress("READING", "准备 V1/V2")
        _ensure_model(workspace, root, baseline_key)
        _ensure_model(workspace, root, candidate_key)
        case_ids = payload.get("case_ids")
        cases = [_case_lookup(workspace, case_id) for case_id in case_ids] if case_ids else list(CASES)
        progress("CHECKING", "执行冻结 Check Set")
        result = workspace.run_regression(baseline_key, candidate_key, cases)
        progress("FINALIZING", "执行严格可比合同")
        return _enrich_regression(root, workspace, result, cases, baseline_key, candidate_key)

    if kind == "EVIDENCE_DETAIL":
        progress("TESSELLATING", "生成局部 Evidence 几何")
        key = payload["model"]
        model = _ensure_model(workspace, root, key)
        run_id = payload["run_id"]
        case_id = payload["case_id"]
        run_path = workspace.store.root / run_id / "result.json"
        if not run_path.exists():
            raise FileNotFoundError(f"run not found: {run_id}")
        run = json.loads(run_path.read_text(encoding="utf-8"))
        execution = None
        for field in ("execution",):
            value = run.get(field)
            if value and value.get("case_id") == case_id:
                execution = value
        for field in ("executions", "baseline", "candidate"):
            for value in run.get(field, []) or []:
                if value.get("case_id") == case_id and value.get("model_version") == model.version:
                    execution = value
        if execution is None:
            raise KeyError(f"execution not found: {case_id}/{model.version}")
        paths = list((execution.get("evidence") or {}).get("focus_paths") or [])
        if not paths:
            case = _case_lookup(workspace, case_id)
            data = run.get("bindings") or workspace.binding_data
            for semantic_id in (case.target, case.counterpart):
                if semantic_id:
                    paths.append(resolve_binding(model, data, semantic_id).occurrence.path)
        detail = tessellate_occurrence_paths(
            model,
            paths,
            deviation=float(payload.get("deviation", 0.12)),
            angular_tolerance=float(payload.get("angular_tolerance", 0.2)),
            render_edges=True,
        )
        return {"execution": execution, "detail": detail}

    raise ValueError(f"unsupported CAD worker job: {kind}")


def run_worker(root: Path, spool: Path, poll_seconds: float = 0.08) -> None:
    spool.mkdir(parents=True, exist_ok=True)
    workspace = Stage2Workspace(root)
    manifest = root / "models" / "demo_manifest.yaml"
    if manifest.exists() and (root / "data" / "step" / "vehicle_v1.step").exists():
        try:
            workspace.load_manifest(manifest)
        except Exception:
            traceback.print_exc()

    stop_heartbeat = threading.Event()

    def heartbeat_loop():
        while not stop_heartbeat.is_set():
            atomic_json(spool / "worker-heartbeat.json", {"pid": os.getpid(), "at": now_iso()})
            stop_heartbeat.wait(0.5)

    heartbeat = threading.Thread(target=heartbeat_loop, name="cad-worker-heartbeat", daemon=True)
    heartbeat.start()

    try:
        while True:
            requests = sorted(spool.glob("*.request.json"), key=lambda p: p.stat().st_mtime_ns)
            if not requests:
                time.sleep(poll_seconds)
                continue
            request_path = requests[0]
            request = load_json(request_path)
            if not request:
                request_path.unlink(missing_ok=True)
                continue
            job_id = request["job_id"]
            status_path = spool / f"{job_id}.status.json"
            result_path = spool / f"{job_id}.result.json"
            current_path = spool / "current.json"
            started_at = now_iso()
            request_path.unlink(missing_ok=True)
            atomic_json(current_path, {"job_id": job_id, "kind": request["kind"], "started_at": started_at})

            def progress(phase: str, message: str):
                existing = load_json(status_path, {}) or {}
                atomic_json(status_path, {
                    **existing,
                    "job_id": job_id,
                    "kind": request["kind"],
                    "state": "RUNNING",
                    "progress_phase": phase,
                    "message": message,
                    "worker_pid": os.getpid(),
                    "started_at": existing.get("started_at") or started_at,
                    "updated_at": now_iso(),
                })

            progress("STARTING", "CAD Worker 已接收任务")
            try:
                result = execute_job(root, workspace, request["kind"], request.get("payload") or {}, progress)
                atomic_json(result_path, {"result": result})
                existing = load_json(status_path, {}) or {}
                atomic_json(status_path, {
                    **existing,
                    "state": "SUCCEEDED",
                    "progress_phase": "DONE",
                    "message": "完成",
                    "updated_at": now_iso(),
                    "finished_at": now_iso(),
                })
            except Exception as exc:
                existing = load_json(status_path, {}) or {}
                atomic_json(status_path, {
                    **existing,
                    "state": "FAILED",
                    "progress_phase": "FAILED",
                    "message": str(exc),
                    "error_code": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                    "updated_at": now_iso(),
                    "finished_at": now_iso(),
                })
            finally:
                current_path.unlink(missing_ok=True)
    finally:
        stop_heartbeat.set()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--spool", required=True)
    args = parser.parse_args()
    run_worker(Path(args.root).resolve(), Path(args.spool).resolve())


if __name__ == "__main__":
    # resolve_binding imported lazily here to avoid circular typing noise above
    from .cad.binding import resolve_binding
    main()
