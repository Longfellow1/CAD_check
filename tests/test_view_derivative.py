from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_electron_runtime_does_not_expose_legacy_streaming_manifest():
    from fastapi.testclient import TestClient
    from server.app_v2 import app

    client = TestClient(app)
    response = client.get("/api/models/V2/viewer/manifest")
    assert response.status_code == 404


def test_product_renderer_does_not_use_legacy_streaming_or_old_viewers():
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")
    package = (ROOT / "web/package.json").read_text(encoding="utf-8")
    runtime = (ROOT / "server/app_v2.py").read_text(encoding="utf-8")

    assert "three-cad-viewer" not in renderer
    assert "three-cad-viewer" not in package
    assert "@babylonjs" not in package
    assert "@xeokit/xeokit-sdk" in package
    assert "/viewer/manifest" not in renderer
    assert "/viewer/chunks/" not in renderer
    assert "create_streaming_router" not in runtime


def test_viewer_contract_is_proxy_first_and_detail_on_demand():
    viewer = (ROOT / "web/src/viewer/xeokit_cad_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    assert "class XeokitCadViewer" in viewer
    assert "SceneModel" in viewer
    assert "dtxEnabled:true" in viewer
    assert "loadOverview" in viewer
    assert "maxResidentDetails" in viewer
    assert "loadDetail" in viewer
    assert "NavCubePlugin" in viewer
    assert "SectionPlanesPlugin" in viewer
    assert "OPEN_MODEL" in renderer
    assert "DETAIL" in renderer
    assert "proxy-first" in renderer
