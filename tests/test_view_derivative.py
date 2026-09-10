from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_streaming_manifest_splits_controlled_model_into_bounded_chunks():
    from server.stage2_runtime import Stage2Workspace
    from server.cad.view_derivative import ViewDerivativeStore

    workspace = Stage2Workspace(ROOT).load_manifest(ROOT / "models/demo_manifest.yaml")
    store = ViewDerivativeStore(ROOT)
    manifest = store.manifest("V2", workspace.models["V2"], profile="preview")

    assert manifest["streaming"] is True
    assert manifest["part_count"] == len(workspace.models["V2"].leaf_occurrences)
    assert manifest["chunk_count"] >= 1
    assert all(chunk["part_count"] <= 4 for chunk in manifest["chunks"])
    assert all("/viewer/chunks/" in chunk["url"] for chunk in manifest["chunks"])


def test_preview_chunk_is_tessellated_and_disk_cached():
    from server.stage2_runtime import Stage2Workspace
    from server.cad.view_derivative import ViewDerivativeStore

    workspace = Stage2Workspace(ROOT).load_manifest(ROOT / "models/demo_manifest.yaml")
    store = ViewDerivativeStore(ROOT)
    manifest = store.manifest("V2", workspace.models["V2"], profile="preview")
    chunk_id = manifest["chunks"][0]["id"]

    first = store.build_chunk("V2", workspace.models["V2"], chunk_id, profile="preview")
    second = store.build_chunk("V2", workspace.models["V2"], chunk_id, profile="preview")

    assert first["shapes"]["parts"]
    assert second["meta"]["cache"] == "HIT"
    assert store.chunk_path("V2", workspace.models["V2"], chunk_id, profile="preview").exists()


def test_streaming_api_exposes_manifest_and_chunk():
    from fastapi.testclient import TestClient
    from server.app_v2 import app

    client = TestClient(app)
    manifest = client.get("/api/models/V2/viewer/manifest")
    assert manifest.status_code == 200
    payload = manifest.json()
    assert payload["profile"]["render_edges"] is False

    chunk = client.get(payload["chunks"][0]["url"])
    assert chunk.status_code == 200
    assert chunk.json()["shapes"]["parts"]
