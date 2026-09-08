from __future__ import annotations

from .domain import CheckExecution, CheckStatus, RegressionResult, RegressionStatus, VerificationCase


def compare_case(b: CheckExecution, c: CheckExecution, case: VerificationCase) -> RegressionResult:
    if b.status==CheckStatus.BLOCKED or c.status==CheckStatus.BLOCKED or b.value is None or c.value is None:
        reg=RegressionStatus.NON_COMPARABLE; delta=None
    elif b.status==CheckStatus.PASS and c.status==CheckStatus.FAIL:
        reg=RegressionStatus.NEW_FAIL; delta=c.value-b.value
    elif b.status==CheckStatus.FAIL and c.status==CheckStatus.PASS:
        reg=RegressionStatus.FIXED; delta=c.value-b.value
    else:
        delta=c.value-b.value; dm=(c.margin or 0.0)-(b.margin or 0.0)
        if dm>case.regression_epsilon: reg=RegressionStatus.IMPROVED
        elif dm<-case.regression_epsilon: reg=RegressionStatus.REGRESSED
        else: reg=RegressionStatus.UNCHANGED
    return RegressionResult(case_id=case.id,title=case.title,baseline=b,candidate=c,regression=reg,delta=round(delta,3) if delta is not None else None)


def compare_runs(baseline, candidate, cases):
    bm={x.case_id:x for x in baseline}; cm={x.case_id:x for x in candidate}
    return [compare_case(bm[c.id],cm[c.id],c) for c in cases]
