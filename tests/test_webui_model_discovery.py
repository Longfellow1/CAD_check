"""Browser contract for discovering runtime-registered CAD preview models."""

from __future__ import annotations

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def test_home_exposes_registered_model_before_loading_heavy_viewer():
    """The home workspace exposes Scania and loads it only after an explicit click."""
    base_url = os.environ.get("CAD_CHECK_UI_URL")
    if not base_url:
        pytest.skip("set CAD_CHECK_UI_URL to run the browser contract")

    with playwright.sync_playwright() as manager:
        browser = manager.chromium.launch(
            headless=True,
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            args=["--use-angle=swiftshader"],
        )
        page = browser.new_page()
        try:
            # The real Scania payload is ~1.56 GB. Keep the browser contract
            # deterministic while still exercising the actual request path.
            scania_requests = []

            def serve_small_payload(route):
                scania_requests.append(route.request.url)
                response = page.request.get(f"{base_url}/api/models/V2/viewer")
                route.fulfill(
                    status=response.status,
                    content_type="application/json",
                    body=response.body(),
                )

            page.route("**/api/models/SCANIA/viewer", serve_small_payload)
            page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
            page.reload(wait_until="domcontentloaded", timeout=30_000)
            page.locator("#preview-model").wait_for(state="visible", timeout=30_000)

            options = page.locator("#preview-model option").all_text_contents()
            assert any("SCANIA" in option for option in options)
            assert page.locator("#preview-load").is_visible()
            assert page.locator("#preview-load").inner_text() == "加载 SCANIA"
            assert page.locator("#preview-status").is_visible()
            assert page.locator("#step-upload").get_attribute("accept") == ".stp,.step"
            assert page.get_by_role("button", name="上传并加载").is_visible()

            # Hard refresh must keep the page responsive and must not pull the
            # heavy payload until the user explicitly asks for the preview.
            assert scania_requests == []
            assert "等待加载" in page.locator("#vt").inner_text()

            page.locator("#preview-load").click()
            page.wait_for_function(
                "() => document.querySelector('#sys')?.textContent.includes('SCANIA 三维已加载')",
                timeout=30_000,
            )
            assert len(scania_requests) == 1
            assert page.locator("#vt").inner_text().startswith("SCANIA ·")

            # Returning to regression must restore the controlled V2 preview.
            page.get_by_role("button", name="版本回归", exact=True).click()
            page.locator("#regression-scope").wait_for(state="visible", timeout=30_000)
            page.wait_for_function(
                "() => document.querySelector('#vt')?.textContent.startsWith('V2 ·')",
                timeout=30_000,
            )
        finally:
            browser.close()
