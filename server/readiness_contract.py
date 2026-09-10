from __future__ import annotations

from typing import Any, Iterable

from .cad.binding import resolve_binding
from .domain import VerificationCase


GLOBAL_CHECK_BLOCKERS = {
    "source_unit_mm": "source_unit_not_mm",
    "coordinate_contract_declared": "coordinate_contract_missing",
    "assembly_or_leaf_count_positive": "model_has_no_renderable_occurrence",
}


def _shape_usable(shape: Any) -> bool:
    if shape is None:
        return False
    try:
        if hasattr(shape, "IsNull") and shape.IsNull():
            return False
    except Exception:
        return False
    return True


def _global_reasons(model_report: dict[str, Any]) -> list[str]:
    checks = model_report.get("checks") or {}
    return [reason for key, reason in GLOBAL_CHECK_BLOCKERS.items() if not checks.get(key, False)]


def case_readiness(model: Any, binding_data: dict[str, Any], case: VerificationCase) -> dict[str, Any]:
    reasons: list[str] = []
    bindings: dict[str, Any] = {}

    rule = case.rule
    authority = getattr(rule, "authority", None) if rule is not None else None
    if authority is None:
        reasons.append("rule_maturity_missing")

    for role, semantic_id in (("target", case.target), ("counterpart", case.counterpart)):
        if not semantic_id:
            continue
        try:
            resolved = resolve_binding(model, binding_data, semantic_id)
            occurrence = resolved.occurrence
            if not occurrence.is_valid:
                reasons.append(f"{role}_occurrence_invalid")
            if not _shape_usable(resolved.shape):
                reasons.append(f"{role}_shape_unusable")
            bindings[role] = {
                "semantic_binding_id": semantic_id,
                "path": occurrence.path,
                "source_object": resolved.source_object,
                "valid": bool(occurrence.is_valid and _shape_usable(resolved.shape)),
            }
        except Exception as exc:
            reasons.append(f"{role}_binding_unresolved")
            bindings[role] = {
                "semantic_binding_id": semantic_id,
                "valid": False,
                "error": str(exc),
            }

    return {
        "case_id": case.id,
        "title": case.title,
        "executor": case.executor,
        "rule_authority": authority.value if authority is not None else None,
        "status": "READY" if not reasons else "BLOCKED",
        "reasons": list(dict.fromkeys(reasons)),
        "bindings": bindings,
    }


def scoped_readiness(
    model: Any,
    model_report: dict[str, Any],
    binding_data: dict[str, Any],
    cases: Iterable[VerificationCase],
) -> dict[str, Any]:
    """Describe preview readiness separately from engineering-check readiness.

    A local invalid B-Rep must not turn the entire vehicle into an opaque global
    failure.  Global contract blockers are limited to unit/coordinate/empty
    model conditions.  Binding or geometry validity then blocks only the Cases
    that actually depend on those occurrences.
    """

    cases = list(cases)
    global_reasons = _global_reasons(model_report)
    case_rows = [case_readiness(model, binding_data, case) for case in cases]
    ready_count = sum(row["status"] == "READY" for row in case_rows)
    blocked_count = len(case_rows) - ready_count

    invalid_paths = sorted(
        occurrence.path
        for occurrence in model.leaf_occurrences
        if not occurrence.is_valid
    )

    if global_reasons:
        engineering = "BLOCKED"
    elif blocked_count == 0:
        engineering = "READY"
    elif ready_count > 0:
        engineering = "PARTIAL"
    else:
        engineering = "BLOCKED"

    preview = "READY" if len(model.leaf_occurrences) > 0 else "BLOCKED"

    return {
        "preview": {
            "status": preview,
            "leaf_count": len(model.leaf_occurrences),
            "invalid_leaf_count": len(invalid_paths),
            "invalid_paths": invalid_paths,
        },
        "engineering_check": {
            "status": engineering,
            "global_blockers": global_reasons,
            "ready_case_count": ready_count,
            "blocked_case_count": blocked_count,
            "total_case_count": len(case_rows),
        },
        "cases": case_rows,
        "legacy_model_report": model_report,
    }
