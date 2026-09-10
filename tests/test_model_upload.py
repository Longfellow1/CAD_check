from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_upload_step_registers_a_runtime_model_and_reports_readiness():
    from server import app as app_module

    source = ROOT / "data/step/vehicle_v1.step"
    client = TestClient(app_module.app)
    response = client.post(
        "/api/models/upload",
        files={
            "file": (
                "headspace-demo.stp",
                source.read_bytes(),
                "application/step",
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    key = payload["key"]
    stored = Path(payload["step"])
    try:
        assert key.startswith("UPLOAD_")
        assert payload["filename"] == "headspace-demo.stp"
        assert payload["bytes"] == source.stat().st_size
        assert payload["readiness"]["checks"]["step_read"]
        assert payload["readiness"]["checks"]["all_leaf_shapes_valid"]
        assert key in app_module.workspace.models
        assert stored.exists()
        assert client.get("/api/models").json()[key]["model_id"]
    finally:
        app_module.workspace.models.pop(key, None)
        stored.unlink(missing_ok=True)


def test_upload_rejects_non_step_files_without_registering_a_model():
    from server import app as app_module

    response = TestClient(app_module.app).post(
        "/api/models/upload",
        files={"file": ("not-a-cad.txt", b"not CAD", "text/plain")},
    )

    assert response.status_code == 400
    assert ".stp" in response.json()["detail"]
