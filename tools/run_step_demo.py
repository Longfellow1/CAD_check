#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.domain import CheckStatus, RegressionStatus
from server.stage2_runtime import Stage2Workspace

GOLDEN_CASE = "CLR_BAT_BRACKET"
GOLDEN_V1_MM = 12.0
GOLDEN_V2_MM = 8.0


def main() -> int:
    workspace = Stage2Workspace(ROOT).load_manifest(
        ROOT / "models/demo_manifest.yaml"
    )
    result = workspace.run_regression("V1", "V2")

    print("run_id=", result["run_id"])
    print("run_dir=", result["run_dir"])
    for item in result["regression"]:
        print(
            f"{item.case_id:24} {item.regression.value:16} "
            f"{item.baseline.value!s:>8} -> {item.candidate.value!s:>8}"
        )

    golden = next(
        item for item in result["regression"] if item.case_id == GOLDEN_CASE
    )
    errors: list[str] = []
    if (
        golden.baseline.value is None
        or abs(golden.baseline.value - GOLDEN_V1_MM) > 1e-6
    ):
        errors.append(
            f"V1 expected {GOLDEN_V1_MM} mm, got {golden.baseline.value}"
        )
    if (
        golden.candidate.value is None
        or abs(golden.candidate.value - GOLDEN_V2_MM) > 1e-6
    ):
        errors.append(
            f"V2 expected {GOLDEN_V2_MM} mm, got {golden.candidate.value}"
        )
    if golden.baseline.status != CheckStatus.PASS:
        errors.append(
            f"V1 expected PASS, got {golden.baseline.status.value}"
        )
    if golden.candidate.status != CheckStatus.FAIL:
        errors.append(
            f"V2 expected FAIL, got {golden.candidate.status.value}"
        )
    if golden.regression != RegressionStatus.NEW_FAIL:
        errors.append(
            f"expected NEW_FAIL, got {golden.regression.value}"
        )

    non_comparable = [
        item.case_id
        for item in result["regression"]
        if item.regression == RegressionStatus.NON_COMPARABLE
    ]
    if non_comparable:
        errors.append(
            f"unexpected NON_COMPARABLE cases: {non_comparable}"
        )

    if errors:
        print("CONTROLLED CONTRACT FAILED:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 3

    print(
        f"CONTROLLED CONTRACT OK: {GOLDEN_CASE} "
        f"{GOLDEN_V1_MM:.1f} mm PASS -> "
        f"{GOLDEN_V2_MM:.1f} mm FAIL -> NEW_FAIL"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
