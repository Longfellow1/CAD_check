from __future__ import annotations

"""Isolated CAD worker for blocking OCP/OCCT work.

FastAPI is the responsive Runtime Controller.  STEP/XCAF import, tessellation
and verification execute only in this process.  The Controller can terminate
this process to implement hard cancel/timeout without taking Electron down.
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
from typing import Any, Callable

from .cases import CASES
from .desktop_contract import (
    enrich_execution,
    finalize_evidence_identity,
    strict_compare,
)
from .domain import RegressionResult, RegressionStatus, VerificationCase, VerificationMode
from .readiness_contract import scoped_readiness
from .stage2_runtime import Stage2Workspace, run_step_case
from .cad.assembly_tree import serialize_assembly_tree
from .cad.binding import resolve_binding
from .cad.source_identity import source_sha256
from .cad.step_reader import model_readiness
from .cad.tessellation import tessellate_occurrence_paths


Progress = Callable[..., None]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically and tolerate transient Windows sharing locks.

    Electron polls status files while the CAD Worker updates them. On Windows a
    reader can briefly prevent replacement of the destination file. Use a unique
    temp file per write, then retry only transient sharing/access failures.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        for attempt in range(40):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if os.name != "nt" or attempt == 39:
                    raise
            except OSError as exc:
                if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32} or attempt == 39:
                    raise
            time.sleep(min(0.01 * (attempt + 1), 0.1))
    finally:
        tmp.unlink(missing_ok=True)


def load_json(path: Path, default: Any = None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _descriptor_registry(root: Path) -> dict[str, Any]:
    return load_json(root / ".cadcheck" / "desktop_models.json", {}) or {}


def _ensure_model(
    workspace: Stage2Workspace,
    root: Path,
    key: str,
    supplied: dict[str, Any] | None = None,
):
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


def _selected_cases(workspace: Stage2Workspace, case_ids: list[str] | None) -> list[VerificationCase]:
    return [_case_lookup(workspace, case_id) for case_id in case_ids] if case_ids else list(CASES)


def _check_set_id(cases: list[VerificationCase]) -> str:
    ids = [case.id for case in cases]
    if ids == [case.id for case in CASES]:
        return "MVP-COVERAGE-18-V1"
    if len(ids) == 1:
        return f"SINGLE:{ids[0]}"
    return "SET:" + ",".join(ids)


def _persist_check_set(
    root: Path,
    workspace: Stage2Workspace,
    model_key: str,
    cases: list[VerificationCase],
    progress: Progress,
) -> dict[str, Any]:
    model = workspace.models[model_key]
    run_id = uuid.uuid4().hex[:12]
    check_set_id = _check_set_id(cases)
    executions = []
    total = len(cases)

    for index, case in enumerate(cases, start=1):
        progress("CHECKING", f"校核 {index}/{total}: {case.id}", completed=index - 1, total=total, current_case_id=case.id)
        execution = run_step_case(model, case, workspace.binding_data)
        enrich_execution(root, model, case, execution, workspace.binding_data, rule_version=case.source_ref)
        finalize_evidence_identity(execution, run_id=run_id, check_set_id=check_set_id)
        executions.append(execution)

    progress("FINALIZING", "固化 Check Set Evidence", completed=total, total=total)
    run_dir = workspace.store.create_run_dir(run_id)
    payload = {
        "run_id": run_id,
        "created_at": now_iso(),
        "mode": VerificationMode.ENGINEERING_CHECK.value,
        "check_set_id": check_set_id,
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
        "check_set_id": check_set_id,
        "model": model_key,
        "cases": payload["cases"],
        "executions": payload["executions"],
    }


def _persist_single(
    root: Path,
    workspace: Stage2Workspace,
    model_key: str,
    result: dict[str, Any],
    *,
    check_set_id: str,
) -> dict[str, Any]:
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
    finalize_evidence_identity(execution, run_id=result["run_id"], check_set_id=check_set_id)

    run_path = Path(result["run_dir"]) / "result.json"
    payload = load_json(run_path, {}) or {}
    payload["check_set_id"] = check_set_id
    payload["execution"] = execution.model_dump(mode="json")
    atomic_json(run_path, payload)
    return {
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "mode": result["mode"].value if hasattr(result["mode"], "value") else str(result["mode"]),
        "check_set_id": check_set_id,
        "model": model_key,
        "case": case.model_dump(mode="json"),
        "execution": execution.model_dump(mode="json"),
    }


def _persist_regression(
    root: Path,
    workspace: Stage2Workspace,
    baseline_key: str,
    candidate_key: str,
    cases: list[VerificationCase],
    progress: Progress,
) -> dict[str, Any]:
    baseline_model = workspace.models[baseline_key]
    candidate_model = workspace.models[candidate_key]
    run_id = uuid.uuid4().hex[:12]
    check_set_id = f"REGRESSION:{_check_set_id(cases)}"
    baseline = []
    candidate = []
    total = len(cases) * 2
    completed = 0

    for side, model in (("V1", baseline_model), ("V2", candidate_model)):
        output = baseline if side == "V1" else candidate
        for case in cases:
            progress(
                "CHECKING",
                f"{side} · {case.id} ({completed + 1}/{total})",
                completed=completed,
                total=total,
                current_case_id=case.id,
            )
            execution = run_step_case(model, case, workspace.binding_data, mode=VerificationMode.REGRESSION_COMPARE)
            enrich_execution(root, model, case, execution, workspace.binding_data, rule_version=case.source_ref)
            finalize_evidence_identity(execution, run_id=run_id, check_set_id=check_set_id)
            output.append(execution)
            completed += 1

    progress("FINALIZING", "执行严格可比合同并固化 Regression", completed=total, total=total)
    regression: list[RegressionResult] = [
        strict_compare(b, c, case)
        for case, b, c in zip(cases, baseline, candidate, strict=True)
    ]

    run_dir = workspace.store.write_run(
        run_id,
        baseline,
        candidate,
        regression,
        mode=VerificationMode.REGRESSION_COMPARE,
        models={"baseline": baseline_key, "candidate": candidate_key},
        cases=cases,
        bindings=workspace.binding_data,
    )
    run_path = run_dir / "result.json"
    saved = load_json(run_path, {}) or {}
    saved["check_set_id"] = check_set_id
    atomic_json(run_path, saved)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "mode": VerificationMode.REGRESSION_COMPARE.value,
        "check_set_id": check_set_id,
        "cases": [case.model_dump(mode="json") for case in cases],
        "baseline": [item.model_dump(mode="json") for item in baseline],
        "candidate": [item.model_dump(mode="json") for item in candidate],
        "regression": [item.model_dump(mode="json") for item in regression],
    }


def _find_execution(run: dict[str, Any], case_id: str, model_version: str) -> dict[str, Any] | None:
    single = run.get("execution")
    if single and single.get("case_id") == case_id and single.get("model_version") == model_version:
        return single
    for field in ("executions", "baseline", "candidate"):
        for value in run.get(field, []) or []:
            if value.get("case_id") == case_id and value.get("model_version") == model_version:
                return value
    return None


def execute_job(
    root: Path,
    workspace: Stage2Workspace,
    kind: str,
    payload: dict[str, Any],
    progress: Progress,
):
    kind = kind.upper()
    if kind == "PING":
        delay = min(max(float(payload.get("sleep_s", 0.0)), 0.0), 30.0)
        if delay:
            progress("CHECKING", f"Worker probe sleep {delay:.2f}s")
            time.sleep(delay)
        return {"ok": True, "worker_pid": os.getpid()}

    if kind == "OPEN_MODEL":
        key = payload["model"]
        warm_session = key in workspace.models
        progress("READING", "读取 STEP / AP242")
        model = _ensure_model(workspace, root, key, payload.get("descriptor"))
        progress("INVENTORY", "构建 Canonical AssemblyTree")
        assembly = serialize_assembly_tree(model)
        legacy = model_readiness(model)
        readiness = scoped_readiness(model, legacy, workspace.binding_data, CASES)
        model_sha = source_sha256(model.path, root / ".cadcheck" / "cache" / "source")
        return {
            "model": key,
            "model_id": model.model_id,
            "version": model.version,
            "model_sha": model_sha,
            "source_unit": model.source_unit,
            "coordinate_contract": model.coordinate_contract,
            "schema": model.schema,
            "leaf_count": len(model.leaf_occurrences),
            "warm_session": warm_session,
            "readiness": readiness,
            "assembly": assembly,
        }

    if kind == "DETAIL":
        progress("TESSELLATING", "生成局部 Viewer Detail")
        model = _ensure_model(workspace, root, payload["model"])
        paths = list(payload.get("paths") or [])
        return tessellate_occurrence_paths(
            model,
            paths,
            deviation=float(payload.get("deviation", 0.4)),
            angular_tolerance=float(payload.get("angular_tolerance", 0.4)),
            render_edges=bool(payload.get("render_edges", False)),
        )

    if kind == "CHECK":
        key = payload["model"]
        _ensure_model(workspace, root, key)
        card_id = payload["card_id"]
        progress("CHECKING", f"执行工程校核 {card_id}", completed=0, total=1, current_case_id=card_id)
        result = workspace.run_check(key, card_id, binding_data=payload.get("bindings"))
        progress("FINALIZING", "固化 Evidence", completed=1, total=1, current_case_id=card_id)
        return _persist_single(root, workspace, key, result, check_set_id=f"SINGLE:{card_id}")

    if kind == "CHECK_SET":
        key = payload["model"]
        _ensure_model(workspace, root, key)
        cases = _selected_cases(workspace, payload.get("case_ids"))
        return _persist_check_set(root, workspace, key, cases, progress)

    if kind == "EXPLORE":
        key = payload["model"]
        _ensure_model(workspace, root, key)
        progress("CHECKING", "执行探索测量", completed=0, total=1)
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
        progress("FINALIZING", "固化探索测量", completed=1, total=1)
        return _persist_single(root, workspace, key, result, check_set_id="EXPLORATORY")

    if kind == "REGRESSION":
        baseline_key = payload.get("baseline", "V1")
        candidate_key = payload.get("candidate", "V2")
        progress("READING", "准备 V1 / V2")
        _ensure_model(workspace, root, baseline_key)
        _ensure_model(workspace, root, candidate_key)
        cases = _selected_cases(workspace, payload.get("case_ids"))
        return _persist_regression(root, workspace, baseline_key, candidate_key, cases, progress)

    if kind == "EVIDENCE_DETAIL":
        key = payload["model"]
        model = _ensure_model(workspace, root, key)
        run_id = payload["run_id"]
        case_id = payload["case_id"]
        progress("TESSELLATING", "生成局部 Evidence 几何")
        run_path = workspace.store.root / run_id / "result.json"
        if not run_path.exists():
            raise FileNotFoundError(f"run not found: {run_id}")
        run = json.loads(run_path.read_text(encoding="utf-8"))
        execution = _find_execution(run, case_id, model.version)
        if execution is None:
            raise KeyError(f"execution not found: {case_id}/{model.version}")

        paths = list((execution.get("evidence") or {}).get("focus_paths") or [])
        if not paths:
            case = _case_lookup(workspace, case_id)
            data = run.get("bindings") or workspace.binding_data
            for semantic_id in (case.target, case.counterpart):
                if semantic_id:
                    paths.append(resolve_binding(model, data, semantic_id).occurrence.path)
        if not paths:
            raise ValueError("Evidence has no reconstructable occurrence paths")

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
            atomic_json(
                spool / "worker-heartbeat.json",
                {"pid": os.getpid(), "at": now_iso(), "epoch": time.time()},
            )
            stop_heartbeat.wait(0.5)

    heartbeat = threading.Thread(target=heartbeat_loop, name="cad-worker-heartbeat", daemon=True)
    heartbeat.start()

    try:
        while True:
            requests = sorted(spool.glob("*.request.json"), key=lambda path: path.stat().st_mtime_ns)
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
            atomic_json(
                current_path,
                {"job_id": job_id, "kind": request["kind"], "started_at": started_at, "worker_pid": os.getpid()},
            )

            def progress(
                phase: str,
                message: str,
                *,
                completed: int | None = None,
                total: int | None = None,
                current_case_id: str | None = None,
            ):
                existing = load_json(status_path, {}) or {}
                row = {
                    **existing,
                    "job_id": job_id,
                    "kind": request["kind"],
                    "state": "RUNNING",
                    "progress_phase": phase,
                    "message": message,
                    "worker_pid": os.getpid(),
                    "started_at": existing.get("started_at") or started_at,
                    "updated_at": now_iso(),
                }
                if completed is not None:
                    row["completed"] = completed
                if total is not None:
                    row["total"] = total
                if current_case_id is not None:
                    row["current_case_id"] = current_case_id
                atomic_json(status_path, row)

            progress("STARTING", "CAD Worker 已接收任务")
            try:
                result = execute_job(root, workspace, request["kind"], request.get("payload") or {}, progress)
                atomic_json(result_path, {"result": result})
                existing = load_json(status_path, {}) or {}
                atomic_json(
                    status_path,
                    {
                        **existing,
                        "state": "SUCCEEDED",
                        "progress_phase": "DONE",
                        "message": "完成",
                        "updated_at": now_iso(),
                        "finished_at": now_iso(),
                    },
                )
            except Exception as exc:
                existing = load_json(status_path, {}) or {}
                atomic_json(
                    status_path,
                    {
                        **existing,
                        "state": "FAILED",
                        "progress_phase": "FAILED",
                        "message": str(exc),
                        "error_code": type(exc).__name__,
                        "error_message": str(exc),
                        "traceback": traceback.format_exc(),
                        "updated_at": now_iso(),
                        "finished_at": now_iso(),
                    },
                )
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
    main()
