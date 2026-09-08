#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.stage2_runtime import Stage2Workspace


def main() -> int:
    workspace = Stage2Workspace(ROOT).load_manifest(
        ROOT / "models/demo_manifest.yaml"
    )
    blocked = False
    for key in ("V1", "V2"):
        report = workspace.readiness(key)
        print(key, json.dumps(report, ensure_ascii=False, indent=2))
        blocked = blocked or report["status"] == "BLOCKED"

    pair = workspace.pair_readiness("V1", "V2")
    print("PAIR", json.dumps(pair, ensure_ascii=False, indent=2))
    blocked = blocked or pair["status"] != "READY"
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
