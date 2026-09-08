from server.cases import CASES
from server.demo_data import all_models
from server.regression import compare_runs
from server.runtime import run_all

def test_demo_regression_has_change_signals():
    models=all_models()
    regs=compare_runs(run_all(models['V1'],CASES),run_all(models['V2'],CASES),CASES)
    assert len(regs)==18
    states={r.regression.value for r in regs}
    assert 'NEW_FAIL' in states or 'REGRESSED' in states
    assert 'IMPROVED' in states or 'FIXED' in states
