from __future__ import annotations

import json
from collections import Counter

from server.cases import CASES
from server.demo_data import all_models
from server.regression import compare_runs
from server.runtime import run_all


def main():
    models = all_models()
    baseline = run_all(models["V1"], CASES)
    candidate = run_all(models["V2"], CASES)
    regression = compare_runs(baseline, candidate, CASES)
    summary = Counter(r.regression.value for r in regression)
    print("CAD Check MVP")
    print(f"cases={len(CASES)}")
    print("regression=" + json.dumps(summary, ensure_ascii=False))
    for r in regression:
        if r.regression.value in {"NEW_FAIL", "REGRESSED", "FIXED", "IMPROVED"}:
            print(f"- {r.regression.value:10s} {r.case_id:22s} {r.title}")


if __name__ == "__main__":
    main()
