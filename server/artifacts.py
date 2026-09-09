from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .domain import CheckExecution, RegressionResult, VerificationCase, VerificationMode


class ArtifactStore:
    def __init__(self, root: str | Path = ".cadcheck/runs"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_run_dir(self, run_id: str) -> Path:
        path = self.root / run_id
        (path / "evidence").mkdir(parents=True, exist_ok=True)
        return path

    def _write_trace(
        self,
        path: Path,
        run_id: str,
        run_kind: str,
        executions: list[CheckExecution],
    ) -> None:
        with (path / "trace.jsonl").open("w", encoding="utf-8") as f:
            for execution in executions:
                for seq, step in enumerate(execution.trace, start=1):
                    row = {
                        "run_id": run_id,
                        "run_kind": run_kind,
                        "model_id": execution.model_id,
                        "model_version": execution.model_version,
                        "case_id": execution.case_id,
                        "executor": execution.executor,
                        "seq": seq,
                        "stage": step.stage,
                        "detail": step.detail,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def write_run(
        self,
        run_id: str,
        baseline: list[CheckExecution],
        candidate: list[CheckExecution],
        regression: list[RegressionResult],
        *,
        mode: VerificationMode = VerificationMode.REGRESSION_COMPARE,
        models: dict[str, str] | None = None,
        cases: list[VerificationCase] | None = None,
        bindings: dict | None = None,
    ) -> Path:
        path = self.create_run_dir(run_id)
        payload = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode.value,
            "models": models or {},
            "baseline": [x.model_dump(mode="json") for x in baseline],
            "candidate": [x.model_dump(mode="json") for x in candidate],
            "regression": [x.model_dump(mode="json") for x in regression],
        }
        if cases is not None:
            payload["cases"] = [x.model_dump(mode="json") for x in cases]
        if bindings is not None:
            payload["bindings"] = bindings
        (path / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_trace(path, run_id, "baseline", baseline)
        with (path / "trace.jsonl").open("a", encoding="utf-8") as f:
            for execution in candidate:
                for seq, step in enumerate(execution.trace, start=1):
                    row = {
                        "run_id": run_id,
                        "run_kind": "candidate",
                        "model_id": execution.model_id,
                        "model_version": execution.model_version,
                        "case_id": execution.case_id,
                        "executor": execution.executor,
                        "seq": seq,
                        "stage": step.stage,
                        "detail": step.detail,
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path

    def write_single_run(
        self,
        run_id: str,
        execution: CheckExecution,
        *,
        mode: VerificationMode,
        model_key: str,
        case: VerificationCase,
        bindings: dict,
    ) -> Path:
        path = self.create_run_dir(run_id)
        payload = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode.value,
            "models": {"model": model_key},
            "case": case.model_dump(mode="json"),
            "execution": execution.model_dump(mode="json"),
            "bindings": bindings,
        }
        (path / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_trace(path, run_id, "single", [execution])
        return path

    def save_png(self, run_id: str, case_id: str, png_bytes: bytes) -> Path:
        path = self.create_run_dir(run_id) / "evidence" / f"{case_id}.png"
        path.write_bytes(png_bytes)
        return path
