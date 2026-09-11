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


def test_product_renderer_uses_three_cad_without_restoring_legacy_backend_streaming():
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")
    package = (ROOT / "web/package.json").read_text(encoding="utf-8")
    runtime = (ROOT / "server/app_v2.py").read_text(encoding="utf-8")
    adapter = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")

    assert '"three-cad-viewer": "5.0.5"' in package
    assert "@xeokit/xeokit-sdk" not in package
    assert "@babylonjs" not in package
    assert "ThreeCadProductViewer" in adapter
    assert "/viewer/manifest" not in renderer
    assert "create_streaming_router" not in runtime


def test_viewer_contract_keeps_proxy_first_and_detail_on_demand():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    assert "class ThreeCadProductViewer" in viewer
    assert "loadOverview" in viewer
    assert "loadPreview" in viewer
    assert "maxResidentDetails" in viewer
    assert "loadDetail" in viewer
    assert "_enforceDetailBudget" in viewer
    assert "control: 'trackball'" in viewer
    assert "up: 'Z'" in viewer
    assert "OPEN_MODEL" in renderer
    assert "DETAIL" in renderer
    assert "proxy-first" in renderer


def test_three_cad_navigation_is_native_and_model_load_resets_sectioning():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    # dev-3 deliberately delegates basic CAD interaction to the mature
    # three-cad control layer instead of recreating mouse/camera math.
    assert "new Display" in viewer
    assert "new Viewer" in viewer
    assert "control: 'trackball'" in viewer
    assert "reset_camera: 'iso'" in viewer
    assert "setView?.('iso')" in viewer

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
    assert "and model.occurrences[path].is_valid" in derivative
    assert '"invalid_proxy_paths"' in derivative


def test_viewer_axis_convention_is_delegated_to_three_cad_z_up_contract():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")

    assert "up: 'Z'" in viewer
    assert "setView?.(view)" in viewer
    # Do not encode Scania-specific front/right vectors in the new adapter.
    assert "Scania's longitudinal axis" not in viewer


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
