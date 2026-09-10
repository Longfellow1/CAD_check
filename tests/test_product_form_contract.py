from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    ROOT / "docs/MVP_PRODUCT_REQUIREMENTS_V1.md",
    ROOT / "docs/MVP_TECH_ARCHITECTURE_V1.md",
    ROOT / "docs/MVP_UX_UI_V1.md",
    ROOT / "docs/MVP_PROJECT_PLAN_V1.md",
]


def test_all_core_docs_lock_electron_as_only_product_entry():
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        assert "Electron" in text, path
        assert "唯一产品入口" in text, path
        assert "Standalone Browser" in text or "Standalone browser" in text, path
        assert "NOT DONE" in text, path


def test_primary_launcher_is_electron_not_uvicorn():
    launcher = (ROOT / "start.sh").read_text(encoding="utf-8")
    assert "desktop" in launcher
    assert "npm" in launcher
    assert "uvicorn" not in launcher


def test_web_launcher_is_explicitly_debug_only():
    debug = (ROOT / "scripts/start-web-dev.sh").read_text(encoding="utf-8")
    assert "DEBUG" in debug
    assert "NOT PRODUCT" in debug
    assert "uvicorn" in debug


def test_readme_does_not_instruct_browser_as_product_entry():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "唯一用户入口：Electron App" in readme
    assert "浏览器调试模式不是产品形态" in readme


def test_electron_shell_and_windows_launcher_exist():
    assert (ROOT / "desktop/main.cjs").exists()
    assert (ROOT / "desktop/runtime.cjs").exists()
    assert (ROOT / "desktop/preload.cjs").exists()
    assert (ROOT / "start.cmd").exists()
    assert (ROOT / "scripts/bootstrap.ps1").exists()
