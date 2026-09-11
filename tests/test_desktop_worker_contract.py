from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.job_runtime import CadWorkerManager, TERMINAL_STATES


def ensure_fixture() -> None:
    subprocess.run(
        [sys.executable, "tools/generate_step_fixture.py"],
        cwd=ROOT,
        check=True,
    )


def wait_job(manager: CadWorkerManager, job_id: str, timeout: float = 40.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = manager.get_job(job_id)
        if last["state"] in TERMINAL_STATES:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def submit_and_wait(
    manager: CadWorkerManager,
    kind: str,
    payload=None,
    *,
    timeout_s: float = 30.0,
    wait_timeout: float = 40.0,
):
    job = manager.submit(kind, payload or {}, timeout_s=timeout_s)
    return wait_job(manager, job["job_id"], timeout=wait_timeout)


@pytest.fixture(scope="module")
def manager():
    ensure_fixture()
    spool = ROOT / ".cadcheck" / "jobs"
    if spool.exists():
        shutil.rmtree(spool)
    instance = CadWorkerManager(ROOT)
    instance.ensure_running()
    try:
        yield instance
    finally:
        instance.shutdown()


def test_worker_open_model_returns_canonical_tree_and_scoped_readiness(manager: CadWorkerManager):
    job = submit_and_wait(manager, "OPEN_MODEL", {"model": "V2"})
    assert job["state"] == "SUCCEEDED", job
    result = job["result"]
    assert result["leaf_count"] == 12
    assert result["assembly"]["import_schema_version"] == "xcaf-occurrence-v1"
    assert result["assembly"]["stats"] == {
        "occurrence_count": 13,
        "parent_count": 1,
        "leaf_count": 12,
        "max_depth": 2,
    }
    assert result["readiness"]["preview"]["status"] in {"READY", "READY_WITH_WARNINGS"}
    assert result["model_sha"]


def test_worker_three_golden_executors_match_locked_truth(manager: CadWorkerManager):
    expected = {
        "CLR_BAT_BRACKET": ("FAIL", 8.0, "mm", "minimum_clearance"),
        "DIR_BAT_GROUND": ("PASS", 156.0, "mm", "directional_distance"),
        "ANG_MOTOR_YAW": ("PASS", 0.0, "deg", "angle"),
    }
    for card_id, (status, value, unit, executor) in expected.items():
        job = submit_and_wait(
            manager,
            "CHECK",
            {"model": "V2", "card_id": card_id},
        )
        assert job["state"] == "SUCCEEDED", job
        execution = job["result"]["execution"]
        assert execution["status"] == status
        assert execution["value"] == pytest.approx(value, abs=1e-6)
        assert execution["unit"] == unit
        assert execution["executor"] == executor
        evidence = execution["evidence"]
        assert evidence["model_sha"]
        assert evidence["import_schema_version"] == "xcaf-occurrence-v1"
        assert evidence["evidence_id"]
        assert evidence["run_id"]
        assert evidence["case_version"]
        assert evidence["executor_version"]
        assert evidence["measurement_method"]
        assert evidence["binding_snapshot"]


def test_worker_coverage_set_uses_three_executors_for_18_cases(manager: CadWorkerManager):
    job = submit_and_wait(manager, "CHECK_SET", {"model": "V2"}, timeout_s=120.0, wait_timeout=130.0)
    assert job["state"] == "SUCCEEDED", job
    result = job["result"]
    assert result["check_set_id"] == "MVP-COVERAGE-18-V1"
    assert len(result["cases"]) == 18
    assert len(result["executions"]) == 18
    assert {item["executor"] for item in result["executions"]} == {
        "minimum_clearance",
        "directional_distance",
        "angle",
    }
    assert all(item["status"] != "BLOCKED" for item in result["executions"])


def test_worker_regression_enforces_strict_comparability(manager: CadWorkerManager):
    job = submit_and_wait(
        manager,
        "REGRESSION",
        {"baseline": "V1", "candidate": "V2", "case_ids": ["CLR_BAT_BRACKET"]},
        timeout_s=60.0,
    )
    assert job["state"] == "SUCCEEDED", job
    result = job["result"]
    golden = result["regression"][0]
    assert golden["regression"] == "NEW_FAIL"
    assert golden["baseline"]["value"] == pytest.approx(12.0, abs=1e-6)
    assert golden["candidate"]["value"] == pytest.approx(8.0, abs=1e-6)
    assert golden["delta"] == pytest.approx(-4.0, abs=1e-6)


def test_hard_cancel_kills_blocking_worker_and_recovers(manager: CadWorkerManager):
    job = manager.submit("PING", {"sleep_s": 5.0}, timeout_s=20.0)
    deadline = time.time() + 5.0
    running = None
    while time.time() < deadline:
        running = manager.get_job(job["job_id"], include_result=False)
        if running["state"] == "RUNNING":
            break
        time.sleep(0.03)
    assert running and running["state"] == "RUNNING", running

    cancelled = manager.cancel(job["job_id"])
    assert cancelled["state"] == "CANCELLED"
    recovered = submit_and_wait(manager, "PING", {}, timeout_s=10.0)
    assert recovered["state"] == "SUCCEEDED", recovered
    assert recovered["result"]["ok"] is True


def test_timeout_kills_worker_and_recovers(manager: CadWorkerManager):
    job = manager.submit("PING", {"sleep_s": 2.0}, timeout_s=0.25)
    timed_out = wait_job(manager, job["job_id"], timeout=8.0)
    assert timed_out["state"] == "TIMED_OUT", timed_out
    assert timed_out["error_code"] == "TIMED_OUT"

    recovered = submit_and_wait(manager, "PING", {}, timeout_s=10.0)
    assert recovered["state"] == "SUCCEEDED", recovered
    assert recovered["result"]["ok"] is True


def test_explicit_worker_restart_keeps_controller_usable(manager: CadWorkerManager):
    before = manager.worker_status()
    restarted = manager.restart()
    assert restarted["state"] == "RUNNING"
    assert restarted["pid"]
    if before.get("pid"):
        assert restarted["pid"] != before["pid"]

    ping = submit_and_wait(manager, "PING", {}, timeout_s=10.0)
    assert ping["state"] == "SUCCEEDED", ping
