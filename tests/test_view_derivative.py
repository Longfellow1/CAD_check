from __future__ import annotations

from pathlib import Path
import math
import sys

import pytest

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


def test_viewer_navigation_contract_is_explicit_and_model_load_resets_sectioning():
    viewer = (ROOT / "web/src/viewer/xeokit_cad_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    # Do not rely on xeokit's default map: it is built before panRightClick is
    # assigned and can silently leave middle-button pan unavailable.
    assert "cameraControl.panRightClick = true" in viewer
    assert "[cameraControl.MOUSE_PAN]" in viewer
    assert "input.MOUSE_RIGHT_BUTTON" in viewer
    assert "中键拖拽缩放" in viewer
    assert "event.buttons & 4" in viewer
    assert "cameraControl.panRightClick = false" not in viewer

    # A new model starts with a neutral section state; replay may restore it
    # explicitly after the model is ready.
    assert "function resetSectionState()" in renderer
    assert "state.sectionEnabled = false" in renderer
    assert "state.viewer?.setSectionPlane(null)" in renderer


def test_invalid_large_parts_use_compatibility_fallback_and_tiny_parts_stay_proxy():
    from types import SimpleNamespace

    from server.cad.view_derivative import _legacy_fallback_paths

    valid = SimpleNamespace(
        path="/valid",
        bbox=(0.0, 0.0, 0.0, 1000.0, 1000.0, 1000.0),
        is_valid=True,
    )
    large_invalid = SimpleNamespace(
        path="/large-invalid",
        bbox=(0.0, 0.0, 0.0, 100.0, 100.0, 100.0),
        is_valid=False,
    )
    tiny_invalid = SimpleNamespace(
        path="/tiny-invalid",
        bbox=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
        is_valid=False,
    )
    model = SimpleNamespace(
        occurrences={item.path: item for item in (valid, large_invalid, tiny_invalid)},
        leaf_occurrences=[valid, large_invalid, tiny_invalid],
    )

    assert _legacy_fallback_paths(model, ["/valid", "/large-invalid", "/tiny-invalid"]) == [
        "/large-invalid"
    ]

    derivative = (ROOT / "server/cad/view_derivative.py").read_text(encoding="utf-8")
    # Invalid BReps that are not selected for the compatibility serializer
    # must remain proxy-only; sending imported springs to native BRepMesh can
    # hang the CAD worker.
    assert "and model.occurrences[path].is_valid" in derivative
    assert '"invalid_proxy_paths"' in derivative


def test_viewer_axis_presets_match_vehicle_cad_convention():
    viewer = (ROOT / "web/src/viewer/xeokit_cad_viewer.js").read_text(encoding="utf-8")

    assert "front: {dir:[0,-1,0]" in viewer
    assert "rear:  {dir:[0,1,0]" in viewer
    assert "left:  {dir:[-1,0,0]" in viewer
    assert "right: {dir:[1,0,0]" in viewer


def test_legacy_fallback_bakes_occurrence_location_into_mesh():
    from server.cad.view_derivative import _bake_part_location

    half_turn = math.sqrt(0.5)
    part = {
        "source_path": "/cab",
        "loc": [[10.0, 20.0, 30.0], [half_turn, 0.0, 0.0, half_turn]],
        "shape": {
            "vertices": [1.0, 2.0, 3.0, 0.0, 1.0, 0.0],
            "normals": [0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            "triangles": [0, 1, 1],
        },
    }

    assert _bake_part_location(part) is True
    assert part["loc"] == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    assert part["shape"]["vertices"] == pytest.approx(
        [11.0, 17.0, 32.0, 10.0, 20.0, 31.0]
    )
    assert part["shape"]["normals"] == pytest.approx(
        [0.0, 0.0, 1.0, 0.0, -1.0, 0.0]
    )
