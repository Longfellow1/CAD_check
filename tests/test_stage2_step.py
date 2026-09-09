from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.cases import CASES
from server.domain import CheckStatus, RegressionStatus
from server.stage2_runtime import Stage2Workspace

GOLDEN_CASE = "CLR_BAT_BRACKET"


def ensure_fixture() -> None:
    subprocess.run(
        [sys.executable, "tools/generate_step_fixture.py"],
        cwd=ROOT,
        check=True,
    )


@pytest.fixture(scope="module")
def workspace() -> Stage2Workspace:
    ensure_fixture()
    return Stage2Workspace(ROOT).load_manifest(
        ROOT / "models/demo_manifest.yaml"
    )


def test_step_import_preserves_ap242_assembly_and_exact_paths(
    workspace: Stage2Workspace,
):
    for key in ("V1", "V2"):
        model = workspace.models[key]
        assert model.schema and "AP242" in model.schema.upper()
        assert model.source_unit == "mm"
        assert len(model.leaf_occurrences) == 12
        assert "/Vehicle/battery" in model.occurrences
        assert "/Vehicle/underbody_bracket" in model.occurrences

        report = workspace.readiness(key)
        assert report["status"] != "BLOCKED", report
        assert report["bindings"]["valid"], report
        assert report["checks"]["all_leaf_shapes_valid"], report
        assert report["checks"]["no_empty_shapes"], report


def test_controlled_golden_is_12_8_pass_fail_new_fail(
    workspace: Stage2Workspace,
):
    result = workspace.run_regression("V1", "V2")
    assert len(result["regression"]) == len(CASES)
    golden = next(
        item
        for item in result["regression"]
        if item.case_id == GOLDEN_CASE
    )

    assert golden.baseline.value == pytest.approx(12.0, abs=1e-6)
    assert golden.candidate.value == pytest.approx(8.0, abs=1e-6)
    assert golden.baseline.status == CheckStatus.PASS
    assert golden.candidate.status == CheckStatus.FAIL
    assert golden.regression == RegressionStatus.NEW_FAIL

    run_dir = Path(result["run_dir"])
    trace_path = run_dir / "trace.jsonl"
    assert trace_path.exists()
    trace = trace_path.read_text()
    assert GOLDEN_CASE in trace
    assert "BRepExtrema_DistShapeShape" in trace


def test_batch_fails_closed_when_binding_drifts(
    workspace: Stage2Workspace,
):
    original = copy.deepcopy(workspace.binding_data)
    try:
        workspace.binding_data["bindings"]["battery"]["V2"] = (
            "/Vehicle/does_not_exist"
        )
        report = workspace.readiness("V2")
        assert report["status"] == "BLOCKED"
        assert not report["bindings"]["valid"]
        with pytest.raises(RuntimeError, match="batch blocked"):
            workspace.run_regression("V1", "V2")
    finally:
        workspace.binding_data = original


def test_ocp_tessellate_bridge_is_json_serializable(
    workspace: Stage2Workspace,
):
    payload = workspace.viewer_payload(
        "V1",
        ["battery", "underbody_bracket"],
    )
    assert "shapes" in payload
    encoded = json.dumps(payload)
    assert '"parts"' in encoded


def test_viewer_http_endpoint_returns_serialized_shapes(
    workspace: Stage2Workspace,
):
    from fastapi.testclient import TestClient

    from server.app import app

    response = TestClient(app).get("/api/models/V1/viewer")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["shapes"]["parts"]
    for leaf in payload["shapes"]["parts"]:
        assert leaf["shape"].get("vertices"), leaf
        assert leaf["shape"].get("triangles"), leaf
        assert "ref" not in leaf["shape"], leaf
        assert "/" not in leaf["name"], leaf
        assert leaf["id"].startswith(payload["shapes"]["id"] + "/"), leaf


def test_evidence_viewer_http_endpoint_includes_measurement_shape(
    workspace: Stage2Workspace,
):
    from fastapi.testclient import TestClient

    from server.app import app

    client = TestClient(app)
    run_response = client.post(
        "/api/runs/regression",
        json={"baseline": "V1", "candidate": "V2"},
    )
    assert run_response.status_code == 200, run_response.text
    run_id = run_response.json()["run_id"]

    response = client.get(
        f"/api/runs/{run_id}/evidence/{GOLDEN_CASE}/viewer?model=V2"
    )
    assert response.status_code == 200, response.text
    parts = response.json()["shapes"]["parts"]
    measurement = next(
        part for part in parts if part["name"] == "__measurement__"
    )
    assert measurement["shape"].get("edges"), measurement
    assert "ref" not in measurement["shape"], measurement


def test_cli_contract_returns_zero_only_for_real_golden():
    ensure_fixture()
    completed = subprocess.run(
        [sys.executable, "tools/run_step_demo.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        "12.0 mm PASS -> 8.0 mm FAIL -> NEW_FAIL"
        in completed.stdout
    )
