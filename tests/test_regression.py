from server.cases import CASES
from server.demo_data import all_models
from server.domain import CheckStatus, RegressionStatus
from server.regression import compare_runs
from server.runtime import run_all

def test_demo_regression_has_change_signals():
    models=all_models()
    regs=compare_runs(run_all(models['V1'],CASES),run_all(models['V2'],CASES),CASES)
    assert len(regs)==18
    states={r.regression.value for r in regs}
    assert 'NEW_FAIL' in states or 'REGRESSED' in states
    assert 'IMPROVED' in states or 'FIXED' in states


def test_provisional_results_are_not_regression_comparable():
    models = all_models()
    baseline = run_all(models['V1'], CASES)
    candidate = run_all(models['V2'], CASES)
    baseline[0] = baseline[0].model_copy(update={"status": CheckStatus.REVIEW_REQUIRED})

    result = compare_runs(baseline, candidate, CASES)[0]

    assert result.regression == RegressionStatus.NON_COMPARABLE
