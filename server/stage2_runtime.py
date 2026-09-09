from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import uuid
import yaml

from .artifacts import ArtifactStore
from .cases import CASES
from .check_registry import CheckCardRegistry
from .domain import (
    CheckExecution,
    CheckStatus,
    Evidence,
    RuleAuthority,
    RegressionStatus,
    TraceStep,
    VerificationCase,
    VerificationMode,
)
from .regression import compare_runs
from .cad.binding import load_binding_file, resolve_binding, validate_bindings
from .cad.geometry_occt import directional_distance, minimum_clearance, orientation_angle
from .cad.step_reader import StepModel, load_step_model, model_readiness
from .cad.tessellation import tessellate_shapes


CRITICAL_READINESS_CHECKS = (
    "source_unit_mm",
    "coordinate_contract_declared",
    "assembly_or_leaf_count_positive",
    "all_leaf_shapes_valid",
    "no_empty_shapes",
)


def _evaluate(value: float, case: VerificationCase):
    r = case.rule
    if r is None or r.authority == RuleAuthority.EXPLORATORY:
        return CheckStatus.MEASURED, None, None
    if r.operator == ">=":
        raw_status, margin = (
            (CheckStatus.PASS, value - r.threshold)
            if value >= r.threshold
            else (CheckStatus.FAIL, value - r.threshold)
        )
    elif r.operator == "<=":
        raw_status, margin = (
            (CheckStatus.PASS, r.threshold - value)
            if value <= r.threshold
            else (CheckStatus.FAIL, r.threshold - value)
        )
    elif r.operator == ">":
        raw_status, margin = (
            (CheckStatus.PASS, value - r.threshold)
            if value > r.threshold
            else (CheckStatus.FAIL, value - r.threshold)
        )
    elif r.operator == "<":
        raw_status, margin = (
            (CheckStatus.PASS, r.threshold - value)
            if value < r.threshold
            else (CheckStatus.FAIL, r.threshold - value)
        )
    elif r.operator == "==":
        raw_status = CheckStatus.PASS if value == r.threshold else CheckStatus.FAIL
        margin = -abs(value - r.threshold)
    elif r.operator == "range":
        ok = r.lower <= value <= r.upper
        margin = (
            min(value - r.lower, r.upper - value)
            if ok
            else -min(abs(value - r.lower), abs(value - r.upper))
        )
        raw_status = CheckStatus.PASS if ok else CheckStatus.FAIL
    else:
        return CheckStatus.REVIEW_REQUIRED, None, None

    status = (
        CheckStatus.REVIEW_REQUIRED
        if r.authority == RuleAuthority.PROVISIONAL
        else raw_status
    )
    return status, margin, raw_status


def _measurement_unit(case: VerificationCase) -> str:
    if case.rule is not None:
        return case.rule.unit
    return "deg" if case.executor == "angle" else "mm"


def _blocked(
    model: StepModel,
    case: VerificationCase,
    reason: str,
    trace: list[TraceStep],
    *,
    mode: VerificationMode = VerificationMode.ENGINEERING_CHECK,
    check_card_version: str | None = None,
) -> CheckExecution:
    return CheckExecution(
        model_id=model.model_id,
        model_version=model.version,
        case_id=case.id,
        title=case.title,
        executor=case.executor,
        mode=mode,
        rule_authority=case.rule.authority if case.rule else None,
        check_card_version=check_card_version,
        status=CheckStatus.BLOCKED,
        unit=_measurement_unit(case),
        evidence=Evidence(
            focus_ids=[value for value in (case.target, case.counterpart) if value],
            annotation=reason,
        ),
        trace=trace + [TraceStep(stage="blocked", detail={"reason": reason})],
    )


def _required_semantic_ids(
    cases: list[VerificationCase] = CASES,
) -> list[str]:
    return sorted(
        {case.target for case in cases}
        | {case.counterpart for case in cases if case.counterpart}
    )


def run_step_case(
    model: StepModel,
    case: VerificationCase,
    binding_data: dict[str, Any],
    *,
    mode: VerificationMode = VerificationMode.ENGINEERING_CHECK,
    check_card_version: str | None = None,
) -> CheckExecution:
    trace: list[TraceStep] = []
    try:
        target = resolve_binding(model, binding_data, case.target)
        counterpart = (
            resolve_binding(model, binding_data, case.counterpart)
            if case.counterpart
            else None
        )
    except Exception as exc:
        return _blocked(
            model,
            case,
            f"binding failed: {exc}",
            trace,
            mode=mode,
            check_card_version=check_card_version,
        )

    trace.append(
        TraceStep(
            stage="binding",
            detail={
                "target": case.target,
                "target_source_object": target.source_object,
                "counterpart": case.counterpart,
                "counterpart_source_object": (
                    counterpart.source_object if counterpart else None
                ),
                "binding_mode": "manual_exact_path",
            },
        )
    )

    try:
        if case.executor == "minimum_clearance":
            result = minimum_clearance(
                target.shape,
                counterpart.shape,
            )
        elif case.executor == "directional_distance":
            result = directional_distance(
                target.shape,
                counterpart.shape,
                case.axis,
            )
        elif case.executor == "angle":
            result = orientation_angle(
                target.occurrence.transform,
                case.angle_axis,
            )
        else:
            return _blocked(
                model,
                case,
                f"unsupported executor: {case.executor}",
                trace,
                mode=mode,
                check_card_version=check_card_version,
            )
    except Exception as exc:
        return _blocked(
            model,
            case,
            f"geometry failed: {exc}",
            trace,
            mode=mode,
            check_card_version=check_card_version,
        )

    status, margin, raw_status = _evaluate(result.value, case)
    trace.append(
        TraceStep(
            stage="geometry",
            detail={
                "executor": case.executor,
                "method": result.method,
                "approximation": result.approximation,
                "value": round(result.value, 6),
                "unit": _measurement_unit(case),
                "p1": result.p1,
                "p2": result.p2,
            },
        )
    )
    if case.rule is not None:
        trace.append(
            TraceStep(
                stage="rule",
                detail={
                    "authority": (
                        case.rule.authority.value
                        if case.rule.authority
                        else None
                    ),
                    "operator": case.rule.operator,
                    "threshold": case.rule.threshold,
                    "lower": case.rule.lower,
                    "upper": case.rule.upper,
                    "value": round(result.value, 6),
                    "margin": round(margin, 6) if margin is not None else None,
                    "raw_status": raw_status.value if raw_status else None,
                    "status": status.value,
                    "source_ref": case.source_ref,
                },
            )
        )

    focus = [case.target] + ([case.counterpart] if case.counterpart else [])
    return CheckExecution(
        model_id=model.model_id,
        model_version=model.version,
        case_id=case.id,
        title=case.title,
        executor=case.executor,
        mode=mode,
        rule_authority=case.rule.authority if case.rule else None,
        check_card_version=check_card_version,
        status=status,
        value=round(result.value, 3),
        unit=_measurement_unit(case),
        margin=round(margin, 3) if margin is not None else None,
        evidence=Evidence(
            focus_ids=focus,
            line_start=result.p1,
            line_end=result.p2,
            annotation=f"{result.value:.2f} {_measurement_unit(case)}",
        ),
        trace=trace,
    )


def run_step_model(
    model: StepModel,
    binding_data: dict[str, Any],
    cases: list[VerificationCase] = CASES,
) -> list[CheckExecution]:
    return [run_step_case(model, case, binding_data) for case in cases]


class Stage2Workspace:
    """Fail-closed P0 workspace for real STEP/XCAF experiments.

    P0 intentionally has no fuzzy binding and no partial-success batch mode.
    Missing objects, unit/geometry readiness failures and executor errors block
    the batch instead of returning a superficially successful comparison.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.models: dict[str, StepModel] = {}
        self.manifest: dict[str, Any] = {}
        self.binding_data: dict[str, Any] = {"bindings": {}}
        self.store = ArtifactStore(self.root / ".cadcheck" / "runs")
        self.registry = CheckCardRegistry(self.root / "checks")

    def load_manifest(self, manifest_path: str | Path):
        manifest_path = Path(manifest_path)
        if not manifest_path.is_absolute():
            manifest_path = self.root / manifest_path
        self.manifest = yaml.safe_load(manifest_path.read_text()) or {}
        binding_path = self.manifest.get("binding_file")
        if binding_path:
            self.binding_data = load_binding_file(self.root / binding_path)
        session_binding_path = self.root / ".cadcheck/session-bindings.json"
        if session_binding_path.exists():
            session_data = json.loads(session_binding_path.read_text())
            for semantic_id, entry in session_data.get("bindings", {}).items():
                self.binding_data.setdefault("bindings", {}).setdefault(
                    semantic_id,
                    {},
                ).update(entry)

        self.models.clear()
        for key, spec in self.manifest.get("models", {}).items():
            self.models[key] = load_step_model(
                self.root / spec["step"],
                model_id=spec["model_id"],
                version=spec["version"],
                coordinate_contract=spec.get(
                    "coordinate_contract",
                    "X-forward/Y-left/Z-up",
                ),
            )
        return self

    def register_model(
        self,
        key: str,
        *,
        step: str | Path,
        model_id: str,
        version: str,
        coordinate_contract: str = "X-forward/Y-left/Z-up",
    ):
        self.models[key] = load_step_model(
            step,
            model_id=model_id,
            version=version,
            coordinate_contract=coordinate_contract,
        )
        return self.models[key]

    def get_bindings(self, model_key: str) -> dict[str, Any]:
        model = self.models[model_key]
        return {
            semantic_id: entry.get(model.version) or entry.get("default")
            for semantic_id, entry in self.binding_data.get("bindings", {}).items()
            if entry.get(model.version) or entry.get("default")
        }

    def save_bindings(
        self,
        model_key: str,
        bindings: dict[str, Any],
    ) -> dict[str, Any]:
        model = self.models[model_key]
        all_bindings = self.binding_data.setdefault("bindings", {})
        for semantic_id, source in bindings.items():
            all_bindings.setdefault(semantic_id, {})[model.version] = source
        session_binding_path = self.root / ".cadcheck/session-bindings.json"
        session_binding_path.parent.mkdir(parents=True, exist_ok=True)
        session_binding_path.write_text(
            json.dumps(
                {"bindings": all_bindings},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self.get_bindings(model_key)

    def _write_single_execution(
        self,
        model_key: str,
        case: VerificationCase,
        execution: CheckExecution,
        *,
        mode: VerificationMode,
        binding_data: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:12]
        run_dir = self.store.write_single_run(
            run_id,
            execution,
            mode=mode,
            model_key=model_key,
            case=case,
            bindings=binding_data,
        )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "mode": mode,
            "model": model_key,
            "case": case,
            "execution": execution,
        }

    def run_explore(
        self,
        model_key: str,
        *,
        target: str,
        counterpart: str | None,
        executor: str,
        axis: str | None = None,
        angle_axis: str | None = None,
        binding_data: dict[str, Any] | None = None,
        title: str = "探索性几何测量",
        verification_method: str = "ANALYSIS_GEOMETRY",
    ) -> dict[str, Any]:
        model = self.models[model_key]
        case = VerificationCase(
            id="EXPLORE_MEASURE",
            title=title,
            source="Manual exploration",
            source_ref="explore://manual",
            executor=executor,
            target=target,
            counterpart=counterpart,
            axis=axis,
            angle_axis=angle_axis,
            engineering_domain="exploratory",
            verification_method=verification_method,
            workflow_id="GEOMETRY_MEASURE_V1",
            required_bindings=[
                semantic_id
                for semantic_id in (target, counterpart)
                if semantic_id
            ],
            rule=None,
        )
        data = binding_data or self.binding_data
        execution = run_step_case(
            model,
            case,
            data,
            mode=VerificationMode.EXPLORE_MEASURE,
        )
        return self._write_single_execution(
            model_key,
            case,
            execution,
            mode=VerificationMode.EXPLORE_MEASURE,
            binding_data=data,
        )

    def run_check(
        self,
        model_key: str,
        card_id: str,
        *,
        binding_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = self.models[model_key]
        card = self.registry.get(card_id)
        case = card.to_case()
        data = binding_data or self.binding_data
        execution = run_step_case(
            model,
            case,
            data,
            mode=VerificationMode.ENGINEERING_CHECK,
            check_card_version=card.version,
        )
        return self._write_single_execution(
            model_key,
            case,
            execution,
            mode=VerificationMode.ENGINEERING_CHECK,
            binding_data=data,
        )

    def check_cards(self):
        return self.registry.list()

    def case_definition(self, case_id: str) -> VerificationCase:
        try:
            return self.registry.case(case_id)
        except KeyError:
            for case in CASES:
                if case.id == case_id:
                    return case
        raise KeyError(f"unknown case: {case_id}")

    def readiness(
        self,
        key: str,
        cases: list[VerificationCase] = CASES,
    ) -> dict[str, Any]:
        model = self.models[key]
        report = model_readiness(model)
        report["bindings"] = validate_bindings(
            model,
            self.binding_data,
            _required_semantic_ids(cases),
        )

        failed_model_checks = [
            name
            for name in CRITICAL_READINESS_CHECKS
            if not report.get("checks", {}).get(name, False)
        ]
        blocked_reasons: list[str] = []
        if failed_model_checks:
            blocked_reasons.extend(
                f"model:{name}" for name in failed_model_checks
            )
        if not report["bindings"]["valid"]:
            blocked_reasons.append("binding")

        if blocked_reasons:
            report["status"] = "BLOCKED"
        report["blocked_reasons"] = blocked_reasons
        return report

    def pair_readiness(
        self,
        baseline_key: str,
        candidate_key: str,
        cases: list[VerificationCase] = CASES,
    ) -> dict[str, Any]:
        baseline_model = self.models[baseline_key]
        candidate_model = self.models[candidate_key]
        baseline = self.readiness(baseline_key, cases)
        candidate = self.readiness(candidate_key, cases)
        checks = {
            "baseline_not_blocked": baseline["status"] != "BLOCKED",
            "candidate_not_blocked": candidate["status"] != "BLOCKED",
            "baseline_bindings_valid": baseline["bindings"]["valid"],
            "candidate_bindings_valid": candidate["bindings"]["valid"],
            "same_model_id": baseline_model.model_id == candidate_model.model_id,
            "same_coordinate_contract": (
                baseline_model.coordinate_contract
                == candidate_model.coordinate_contract
            ),
            "same_source_unit": (
                baseline_model.source_unit == candidate_model.source_unit
            ),
        }
        return {
            "status": "READY" if all(checks.values()) else "NON_COMPARABLE",
            "checks": checks,
            "baseline": baseline["status"],
            "candidate": candidate["status"],
        }

    def run_regression(
        self,
        baseline_key: str,
        candidate_key: str,
        cases: list[VerificationCase] = CASES,
    ):
        pair = self.pair_readiness(
            baseline_key,
            candidate_key,
            cases,
        )
        if pair["status"] != "READY":
            raise RuntimeError(
                f"batch blocked by readiness/comparability: {pair}"
            )

        baseline = run_step_model(
            self.models[baseline_key],
            self.binding_data,
            cases,
        )
        candidate = run_step_model(
            self.models[candidate_key],
            self.binding_data,
            cases,
        )

        blocked = [
            {
                "case_id": execution.case_id,
                "version": execution.model_version,
                "reason": execution.evidence.annotation,
            }
            for execution in [*baseline, *candidate]
            if execution.status == CheckStatus.BLOCKED
        ]
        if blocked:
            raise RuntimeError(
                f"batch blocked by case execution failure: {blocked}"
            )

        regression = compare_runs(baseline, candidate, cases)
        if regression and all(
            item.regression == RegressionStatus.NON_COMPARABLE
            for item in regression
        ):
            raise RuntimeError(
                "batch blocked: all regression results are NON_COMPARABLE"
            )

        run_id = uuid.uuid4().hex[:12]
        run_dir = self.store.write_run(
            run_id,
            baseline,
            candidate,
            regression,
            mode=VerificationMode.REGRESSION_COMPARE,
            models={"baseline": baseline_key, "candidate": candidate_key},
            cases=cases,
            bindings=self.binding_data,
        )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "mode": VerificationMode.REGRESSION_COMPARE,
            "baseline": baseline,
            "candidate": candidate,
            "regression": regression,
        }

    def viewer_payload(
        self,
        key: str,
        semantic_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        model = self.models[key]
        if semantic_ids:
            named: dict[str, Any] = {}
            for semantic_id in semantic_ids:
                binding = resolve_binding(
                    model,
                    self.binding_data,
                    semantic_id,
                )
                named[semantic_id] = binding.shape
        else:
            named = {
                occurrence.path: occurrence.shape
                for occurrence in model.leaf_occurrences
            }
        return tessellate_shapes(named)
