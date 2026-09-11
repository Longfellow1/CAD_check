#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".cadcheck" / "e2e" / "electron-smoke.json"
REQUIRED_STAGES = {
    "electron",
    "open-model",
    "fail-evidence",
    "replay",
    "regression",
    "viewer",
    "worker-restart",
}


def main() -> int:
    if not REPORT.exists():
        print(f"missing Electron E2E report: {REPORT}", file=sys.stderr)
        return 2

    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    if payload.get("product_form") != "electron":
        raise AssertionError(payload)
    if payload.get("ok") is not True:
        raise AssertionError(payload.get("error") or payload)

    stages = {item.get("name") for item in payload.get("stages", [])}
    missing = REQUIRED_STAGES - stages
    if missing:
        raise AssertionError(f"Electron E2E missing stages: {sorted(missing)}")

    viewer = payload.get("viewer") or {}
    if viewer.get("proxy_count", 0) < 12:
        raise AssertionError(f"Viewer did not retain controlled overview: {viewer}")
    if viewer.get("resident_detail_occurrences", 0) > viewer.get("max_resident_details", 24):
        raise AssertionError(f"Viewer detail residency exceeded budget: {viewer}")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
