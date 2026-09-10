from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.metadata
import json
import platform
import sys

from .cad.assembly_tree import IMPORT_SCHEMA_VERSION, occurrence_id_for_path
from .cad.binding import resolve_binding
from .cad.source_identity import source_sha256
from .domain import CheckExecution, RegressionResult, RegressionStatus, VerificationCase

EXECUTOR_VERSION = "occt-executor-v1"


def _geometry_step(execution: CheckExecution) -> dict[str, Any]:
    for step in execution.trace:
        if step.stage == "geometry":
            return step.detail
    return {}


def _binding_entry(model, binding_data: dict[str, Any], semantic_id: str | None):
    if not semantic_id:
        return None
    resolved = resolve_binding(model, binding_data, semantic_id)
    path = resolved.occurrence.path
    return {
        "semantic_binding_id": semantic_id,
        "path": path,
        "source_object": resolved.source_object,
        "selector": resolved.selector,
        "occurrence_id": occurrence_id_for_path(model, path),
    }


def runtime_snapshot() -> dict[str, Any]:
    def version(name: str) -> str | None:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cadquery_ocp": version("cadquery-ocp"),
        "ocp_tessellate": version("ocp-tessellate"),
        "executor_version": EXECUTOR_VERSION,
    }


def enrich_execution(
    root: str | Path,
    model,
    case: VerificationCase,
    execution: CheckExecution,
    binding_data: dict[str, Any],
    *,
    rule_version: str | None = None,
) -> CheckExecution:
    """Attach reproducibility metadata before a Run receives its final ID."""
    evidence = execution.evidence
    try:
        target = _binding_entry(model, binding_data, case.target)
        counterpart = _binding_entry(model, binding_data, case.counterpart)
        entries = [item for item in (target, counterpart) if item]
    except Exception:
        # BLOCKED results can intentionally have incomplete bindings.  Never
        # invent a path/occurrence by fuzzy name matching just to make Evidence.
        target = None
        counterpart = None
        entries = []

    geometry = _geometry_step(execution)
    evidence.focus_paths = [item["path"] for item in entries]
    evidence.focus_occurrence_ids = [
        item["occurrence_id"] for item in entries if item.get("occurrence_id")
    ]
    evidence.model_sha = source_sha256(
        model.path,
        Path(root) / ".cadcheck" / "cache" / "source",
    )
    evidence.import_schema_version = IMPORT_SCHEMA_VERSION
    evidence.case_id = case.id
    evidence.case_version = case.version
    evidence.rule_version = rule_version or case.source_ref
    evidence.executor_version = EXECUTOR_VERSION
    evidence.measurement_method = str(geometry.get("method") or case.verification_method)
    evidence.approximation = geometry.get("approximation")
    evidence.executor_params = {
        key: value
        for key, value in {
            "executor": case.executor,
            "axis": case.axis,
            "angle_axis": case.angle_axis,
            "workflow_id": case.workflow_id,
        }.items()
        if value is not None
    }
    evidence.binding_snapshot = {
        "target": target,
        "counterpart": counterpart,
    }
    evidence.coordinate_system = {
        "id": model.coordinate_contract,
        "transform_to_model": [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ],
    }
    evidence.source_unit = model.source_unit
    evidence.runtime_info = runtime_snapshot()
    if case.rule is not None:
        evidence.tolerance = case.rule.tolerance
        evidence.threshold = case.rule.threshold
        evidence.rule_snapshot = {
            "authority": case.rule.authority.value if case.rule.authority else None,
            "operator": case.rule.operator,
            "threshold": case.rule.threshold,
            "lower": case.rule.lower,
            "upper": case.rule.upper,
            "unit": case.rule.unit,
            "tolerance": case.rule.tolerance,
            "source_ref": case.source_ref,
        }
    evidence.view_state = {
        "camera_preset": evidence.camera_preset,
        "focus_occurrence_ids": evidence.focus_occurrence_ids,
        "context_strategy": "translucent",
        "annotation": {
            "line_start": evidence.line_start,
            "line_end": evidence.line_end,
            "text": evidence.annotation,
            "axis": case.axis or case.angle_axis,
        },
    }
    return execution


def finalize_evidence_identity(
    execution: CheckExecution,
    *,
    run_id: str,
    check_set_id: str,
) -> CheckExecution:
    evidence = execution.evidence
    evidence.run_id = run_id
    evidence.check_set_id = check_set_id
    evidence.evidence_id = f"{run_id}:{execution.case_id}:{execution.model_version}"
    return execution


def strict_compare(
    baseline: CheckExecution,
    candidate: CheckExecution,
    case: VerificationCase,
) -> RegressionResult:
    """Compare only when engineering, method and semantic identity contracts match."""
    reasons: list[str] = []
    b = baseline.evidence
    c = candidate.evidence

    if baseline.rule_authority is None or candidate.rule_authority is None:
        reasons.append("rule_maturity_missing")
    elif baseline.rule_authority.value != "FORMAL" or candidate.rule_authority.value != "FORMAL":
        reasons.append("rule_not_formal")
    if baseline.executor != candidate.executor:
        reasons.append("executor_changed")
    if b.executor_version != c.executor_version:
        reasons.append("executor_version_changed")
    if b.measurement_method != c.measurement_method:
        reasons.append("measurement_method_changed")
    if baseline.unit != candidate.unit:
        reasons.append("unit_changed")
    if b.source_unit != c.source_unit:
        reasons.append("source_unit_changed")
    if b.coordinate_system.get("id") != c.coordinate_system.get("id"):
        reasons.append("coordinate_system_changed")
    if b.rule_version != c.rule_version:
        reasons.append("rule_version_changed")
    if b.case_version != c.case_version:
        reasons.append("case_version_changed")
    if not b.import_schema_version or not c.import_schema_version:
        reasons.append("import_schema_missing")
    elif b.import_schema_version != c.import_schema_version:
        reasons.append("import_schema_changed")

    def semantic_keys(snapshot: dict[str, Any]) -> tuple[str, ...]:
        values = []
        for key in ("target", "counterpart"):
            item = snapshot.get(key)
            if item and item.get("semantic_binding_id"):
                values.append(str(item["semantic_binding_id"]))
        return tuple(values)

    b_semantic = semantic_keys(b.binding_snapshot)
    c_semantic = semantic_keys(c.binding_snapshot)
    if not b_semantic or b_semantic != c_semantic:
        reasons.append("semantic_binding_incompatible")

    comparable_statuses = {"PASS", "FAIL"}
    if baseline.status.value not in comparable_statuses or candidate.status.value not in comparable_statuses:
        reasons.append("status_not_comparable")
    if baseline.value is None or candidate.value is None:
        reasons.append("value_missing")

    if reasons:
        return RegressionResult(
            case_id=case.id,
            title=case.title,
            baseline=baseline,
            candidate=candidate,
            regression=RegressionStatus.NON_COMPARABLE,
            delta=None,
            non_comparable_reason=",".join(dict.fromkeys(reasons)),
        )

    delta = candidate.value - baseline.value
    if baseline.status.value == "PASS" and candidate.status.value == "FAIL":
        status = RegressionStatus.NEW_FAIL
    elif baseline.status.value == "FAIL" and candidate.status.value == "PASS":
        status = RegressionStatus.FIXED
    else:
        delta_margin = (candidate.margin or 0.0) - (baseline.margin or 0.0)
        if delta_margin > case.regression_epsilon:
            status = RegressionStatus.IMPROVED
        elif delta_margin < -case.regression_epsilon:
            status = RegressionStatus.REGRESSED
        else:
            status = RegressionStatus.UNCHANGED
    return RegressionResult(
        case_id=case.id,
        title=case.title,
        baseline=baseline,
        candidate=candidate,
        regression=status,
        delta=round(delta, 3),
    )


def rewrite_run_result(
    run_dir: str | Path,
    *,
    execution: CheckExecution | None = None,
    executions: list[CheckExecution] | None = None,
    baseline: list[CheckExecution] | None = None,
    candidate: list[CheckExecution] | None = None,
    regression: list[RegressionResult] | None = None,
) -> None:
    path = Path(run_dir) / "result.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if execution is not None:
        payload["execution"] = execution.model_dump(mode="json")
    if executions is not None:
        payload["executions"] = [item.model_dump(mode="json") for item in executions]
    if baseline is not None:
        payload["baseline"] = [item.model_dump(mode="json") for item in baseline]
    if candidate is not None:
        payload["candidate"] = [item.model_dump(mode="json") for item in candidate]
    if regression is not None:
        payload["regression"] = [item.model_dump(mode="json") for item in regression]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_replay_state(run_root: str | Path, run_id: str, case_id: str, state: dict[str, Any]) -> Path:
    path = Path(run_root) / run_id / "evidence" / f"{case_id}.view.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_replay_record(run_root: str | Path, run_id: str, case_id: str) -> dict[str, Any]:
    run_dir = Path(run_root) / run_id
    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise FileNotFoundError(run_id)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    view_path = run_dir / "evidence" / f"{case_id}.view.json"
    png_path = run_dir / "evidence" / f"{case_id}.png"
    return {
        "run_id": run_id,
        "case_id": case_id,
        "result": result,
        "view_state": json.loads(view_path.read_text(encoding="utf-8")) if view_path.exists() else None,
        "screenshot_path": str(png_path) if png_path.exists() else None,
    }
