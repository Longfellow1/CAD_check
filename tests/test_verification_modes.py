from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.cad.binding import resolve_binding
from server.domain import (
    CheckStatus,
    Rule,
    RuleAuthority,
    VerificationCase,
    VerificationMode,
)
from server.stage2_runtime import Stage2Workspace, run_step_case


@pytest.fixture(scope="module")
def workspace() -> Stage2Workspace:
    subprocess.run(
        [sys.executable, "tools/generate_step_fixture.py"],
        cwd=ROOT,
        check=True,
    )
    return Stage2Workspace(ROOT).load_manifest(
        ROOT / "models/demo_manifest.yaml"
    )


def test_manual_binding_can_select_a_face_subshape(
    workspace: Stage2Workspace,
):
    bindings = {
        "bindings": {
            "battery_face": {
                "default": {
                    "path": "/Vehicle/battery",
                    "selector": {"kind": "face", "index": 1},
                }
            }
        }
    }

    resolved = resolve_binding(
        workspace.models["V1"],
        bindings,
        "battery_face",
    )

    assert not resolved.shape.IsNull()
    assert resolved.source_object == "/Vehicle/battery#face[1]"


def test_explore_measure_returns_a_value_without_pass_fail(
    workspace: Stage2Workspace,
):
    bindings = {
        "bindings": {
            "explore_a": {"default": "/Vehicle/battery"},
            "explore_b": {"default": "/Vehicle/underbody_bracket"},
        }
    }

    result = workspace.run_explore(
        "V1",
        target="explore_a",
        counterpart="explore_b",
        executor="minimum_clearance",
        binding_data=bindings,
    )

    execution = result["execution"]
    assert result["mode"] == VerificationMode.EXPLORE_MEASURE
    assert execution.mode == VerificationMode.EXPLORE_MEASURE
    assert execution.status == CheckStatus.MEASURED
    assert execution.value == pytest.approx(12.0, abs=1e-6)
    assert execution.margin is None
    assert result["run_dir"]


def test_engineering_check_uses_a_versioned_card(
    workspace: Stage2Workspace,
):
    result = workspace.run_check("V1", "CLR_BAT_BRACKET")

    execution = result["execution"]
    assert result["mode"] == VerificationMode.ENGINEERING_CHECK
    assert execution.status == CheckStatus.PASS
    assert execution.rule_authority == RuleAuthority.FORMAL
    assert execution.check_card_version == "0.1"
    assert execution.value == pytest.approx(12.0, abs=1e-6)


def test_explore_angle_uses_degree_evidence_unit(
    workspace: Stage2Workspace,
):
    bindings = {
        "bindings": {
            "explore_a": {"default": "/Vehicle/motor"},
        }
    }

    result = workspace.run_explore(
        "V1",
        target="explore_a",
        counterpart=None,
        executor="angle",
        angle_axis="Z",
        binding_data=bindings,
    )

    execution = result["execution"]
    assert execution.status == CheckStatus.MEASURED
    assert execution.unit == "deg"
    assert execution.evidence.annotation.endswith(" deg")


def test_provisional_rule_cannot_claim_formal_pass(
    workspace: Stage2Workspace,
):
    case = VerificationCase(
        id="PROVISIONAL_TEST",
        title="Provisional clearance",
        source="test",
        source_ref="test",
        executor="minimum_clearance",
        target="battery",
        counterpart="underbody_bracket",
        rule=Rule(
            authority=RuleAuthority.PROVISIONAL,
            operator=">=",
            threshold=10.0,
            unit="mm",
        ),
    )

    execution = run_step_case(
        workspace.models["V1"],
        case,
        workspace.binding_data,
        mode=VerificationMode.ENGINEERING_CHECK,
    )

    assert execution.status == CheckStatus.REVIEW_REQUIRED
    assert execution.value == pytest.approx(12.0, abs=1e-6)
    rule_step = next(step for step in execution.trace if step.stage == "rule")
    assert rule_step.detail["raw_status"] == CheckStatus.PASS.value


def test_mode_api_exposes_cards_and_minimal_replay(workspace: Stage2Workspace):
    from fastapi.testclient import TestClient

    from server.app import app

    client = TestClient(app)
    cards = client.get("/api/check-cards")
    assert cards.status_code == 200, cards.text
    assert {card["id"] for card in cards.json()} == {
        "ANG_MOTOR_YAW",
        "CLR_BAT_BRACKET",
        "DIR_BAT_GROUND",
    }

    explore = client.post(
        "/api/runs/explore",
        json={
            "model": "V1",
            "target": "explore_a",
            "counterpart": "explore_b",
            "executor": "minimum_clearance",
            "bindings": {
                "bindings": {
                    "explore_a": {"default": "/Vehicle/battery"},
                    "explore_b": {
                        "default": "/Vehicle/underbody_bracket"
                    },
                }
            },
        },
    )
    assert explore.status_code == 200, explore.text
    explore_payload = explore.json()
    assert explore_payload["execution"]["status"] == "MEASURED"
    assert explore_payload["mode"] == "EXPLORE_MEASURE"

    evidence = client.get(
        f"/api/runs/{explore_payload['run_id']}/evidence/EXPLORE_MEASURE/viewer?model=V1"
    )
    assert evidence.status_code == 200, evidence.text
    assert any(
        part["name"] == "__measurement__"
        for part in evidence.json()["shapes"]["parts"]
    )

    replay = client.get(f"/api/runs/{explore_payload['run_id']}")
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    assert replay_payload["mode"] == "EXPLORE_MEASURE"
    assert replay_payload["execution"]["case_id"] == "EXPLORE_MEASURE"

    check = client.post(
        "/api/runs/check",
        json={"model": "V1", "card_id": "CLR_BAT_BRACKET"},
    )
    assert check.status_code == 200, check.text
    assert check.json()["execution"]["status"] == "PASS"


def test_inventory_exposes_manual_subshape_choices(
    workspace: Stage2Workspace,
):
    from fastapi.testclient import TestClient

    from server.app import app

    payload = TestClient(app).get("/api/models/V1/inventory").json()
    battery = next(
        item for item in payload["occurrences"]
        if item["path"] == "/Vehicle/battery"
    )
    assert battery["subshapes"]["face"][0]["selector"] == {
        "kind": "face",
        "index": 1,
    }


def test_binding_api_validates_and_saves_a_manual_source(
    workspace: Stage2Workspace,
):
    from fastapi.testclient import TestClient

    from server.app import app

    response = TestClient(app).post(
        "/api/bindings",
        json={
            "model": "V1",
            "bindings": {
                "battery": {"path": "/Vehicle/battery"},
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["validation"]["valid"]
    assert payload["bindings"]["battery"] == {"path": "/Vehicle/battery"}
