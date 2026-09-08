from server.cases import CASES
from server.demo_data import all_models
from server.runtime import run_all
from server.regression import compare_runs


def test_demo_has_18_cases():
    assert len(CASES) == 18


def test_all_cases_execute_for_both_versions():
    models = all_models()
    for version in ("V1", "V2"):
        results = run_all(models[version], CASES)
        assert len(results) == 18
        assert all(r.status.value in {"PASS", "FAIL", "REVIEW_REQUIRED", "BLOCKED"} for r in results)


def test_regression_produces_meaningful_changes():
    models = all_models()
    baseline = run_all(models["V1"], CASES)
    candidate = run_all(models["V2"], CASES)
    regression = compare_runs(baseline, candidate, CASES)
    states = {r.regression.value for r in regression}
    assert "NEW_FAIL" in states
    assert "FIXED" in states
    assert len(regression) == 18
