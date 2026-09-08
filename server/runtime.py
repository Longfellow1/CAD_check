from __future__ import annotations

from .domain import CheckExecution, CheckStatus, Evidence, TraceStep, VehicleModel, VerificationCase
from .geometry import directional_distance, minimum_clearance, orientation_angle


def _evaluate(value: float, case: VerificationCase):
    r=case.rule
    if r.operator==">=": return (CheckStatus.PASS if value>=r.threshold else CheckStatus.FAIL, value-r.threshold)
    if r.operator=="<=": return (CheckStatus.PASS if value<=r.threshold else CheckStatus.FAIL, r.threshold-value)
    if r.operator==">": return (CheckStatus.PASS if value>r.threshold else CheckStatus.FAIL, value-r.threshold)
    if r.operator=="<": return (CheckStatus.PASS if value<r.threshold else CheckStatus.FAIL, r.threshold-value)
    if r.operator=="==": return (CheckStatus.PASS if value==r.threshold else CheckStatus.FAIL, -abs(value-r.threshold))
    if r.operator=="range":
        ok=r.lower<=value<=r.upper
        margin=min(value-r.lower,r.upper-value) if ok else -min(abs(value-r.lower),abs(value-r.upper))
        return (CheckStatus.PASS if ok else CheckStatus.FAIL, margin)
    return CheckStatus.REVIEW_REQUIRED,None


def run_case(model: VehicleModel, case: VerificationCase) -> CheckExecution:
    trace=[TraceStep(stage="resolve",detail={"target":case.target,"counterpart":case.counterpart})]
    target=model.objects.get(case.target); counterpart=model.objects.get(case.counterpart) if case.counterpart else None
    if not target or (case.counterpart and not counterpart):
        missing=[x for x,obj in [(case.target,target),(case.counterpart,counterpart)] if x and obj is None]
        return CheckExecution(model_id=model.model_id,model_version=model.version,case_id=case.id,title=case.title,executor=case.executor,status=CheckStatus.BLOCKED,unit=case.rule.unit,evidence=Evidence(focus_ids=[x for x in [case.target,case.counterpart] if x],annotation=f"Missing: {', '.join(missing)}"),trace=trace+[TraceStep(stage="blocked",detail={"missing":missing})])
    if case.executor=="minimum_clearance":
        dr=minimum_clearance(target,counterpart); value,p1,p2=dr.value,dr.p1,dr.p2
    elif case.executor=="directional_distance":
        dr=directional_distance(target,counterpart,case.axis); value,p1,p2=dr.value,dr.p1,dr.p2
    elif case.executor=="angle":
        value=orientation_angle(target,case.angle_axis); p1=p2=None
    else:
        return CheckExecution(model_id=model.model_id,model_version=model.version,case_id=case.id,title=case.title,executor=case.executor,status=CheckStatus.REVIEW_REQUIRED,unit=case.rule.unit,evidence=Evidence(focus_ids=[case.target],annotation="Unsupported executor"),trace=trace)
    status,margin=_evaluate(value,case)
    trace += [TraceStep(stage="geometry",detail={"executor":case.executor,"value":round(value,4),"unit":case.rule.unit}),TraceStep(stage="rule",detail={"operator":case.rule.operator,"threshold":case.rule.threshold,"status":status.value})]
    focus=[case.target]+([case.counterpart] if case.counterpart else [])
    return CheckExecution(model_id=model.model_id,model_version=model.version,case_id=case.id,title=case.title,executor=case.executor,status=status,value=round(value,3),unit=case.rule.unit,margin=round(margin,3) if margin is not None else None,evidence=Evidence(focus_ids=focus,line_start=p1,line_end=p2,annotation=f"{value:.2f} {case.rule.unit}"),trace=trace)


def run_all(model: VehicleModel, cases: list[VerificationCase]):
    return [run_case(model,c) for c in cases]
