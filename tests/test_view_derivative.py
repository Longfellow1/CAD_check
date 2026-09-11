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


def test_viewer_contract_keeps_proxy_first_preview_and_bounded_detail():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    assert "class ThreeCadProductViewer" in viewer
    assert "loadOverview" in viewer
    assert "loadPreview" in viewer
    assert "previewCache" in viewer
    assert "maxResidentDetails" in viewer
    assert "loadDetail" in viewer
    assert "_enforceDetailBudget" in viewer
    assert "OPEN_MODEL" in renderer
    assert "DETAIL" in renderer
    assert "VIEWER_MANIFEST" in renderer
    assert "VIEWER_CHUNK" in renderer
    assert "proxy-first" in renderer


def test_three_cad_uses_native_cad_navigation_instead_of_custom_camera_math():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    assert "new Display" in viewer
    assert "new Viewer" in viewer
    assert "control: 'trackball'" in viewer
    assert "ortho: true" in viewer
    assert "up: 'Z'" in viewer
    assert "presetCamera?.('iso')" in viewer
    assert "setRotateSpeed" in viewer
    assert "setPanSpeed" in viewer
    assert "setZoomSpeed" in viewer

    assert "function resetSectionState()" in renderer
    assert "state.sectionEnabled = false" in renderer
    assert "state.viewer?.setSectionPlane(null)" in renderer


def test_three_cad_preview_updates_are_batched_not_old_all_resident_streaming():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")

    # The old route paid a bounds/tree rebuild per part. dev-3 must use the
    # official dynamic-part batching path and flush bounds once per derivative chunk.
    assert "updatePart(path, part, { skipBounds })" in viewer
    assert "removePart(path, { skipBounds: true })" in viewer
    assert "addPart(ROOT_ID, part, { skipBounds })" in viewer
    assert "this.viewer.updateBounds?.()" in viewer
    assert "previewCache" in viewer


def test_three_cad_product_operations_are_real_not_placeholder_state_only():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")

    # Hide/isolate/show-all must drive actual tree/object visibility.
    assert "this.viewer.setStates?.(states)" in viewer
    # Replay must restore the actual camera, not merely remember a JS object.
    assert "getCameraLocationSettings" in viewer
    assert "setCameraLocationSettings" in viewer
    assert "switchCamera" in viewer
    # Product Z section must control three-cad clipping.
    assert "setClipNormal" in viewer
    assert "setLocalClipping" in viewer
    # Evidence must be visible geometry in the 3D scene, not annotation text only.
    assert "LineSegments" in viewer
    assert "CADCheckEvidence" in viewer


def test_three_cad_capture_is_synchronous_for_existing_evidence_contract():
    viewer = (ROOT / "web/src/viewer/three_cad_product_viewer.js").read_text(encoding="utf-8")
    renderer = (ROOT / "web/src/main_v4.js").read_text(encoding="utf-8")

    # main_v4 persists captureView() synchronously; the adapter therefore takes
    # the current canvas directly instead of forwarding three-cad's async getImage().
    capture = viewer.split("captureView()", 1)[1].split("getViewState()", 1)[0]
    assert "async captureView" not in viewer
    assert "toDataURL('image/png')" in capture
    assert "const data_url = state.viewer.captureView();" in renderer


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
    assert "presetCamera?.(view" in viewer
    # Do not encode Scania-specific front/right vectors in the product adapter.
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
