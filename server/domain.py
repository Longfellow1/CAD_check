from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    MEASURED = "MEASURED"
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class RegressionStatus(str, Enum):
    NEW_FAIL = "NEW_FAIL"
    FIXED = "FIXED"
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    UNCHANGED = "UNCHANGED"
    NON_COMPARABLE = "NON_COMPARABLE"


class VerificationMode(str, Enum):
    EXPLORE_MEASURE = "EXPLORE_MEASURE"
    ENGINEERING_CHECK = "ENGINEERING_CHECK"
    REGRESSION_COMPARE = "REGRESSION_COMPARE"


class RuleAuthority(str, Enum):
    FORMAL = "FORMAL"
    PROVISIONAL = "PROVISIONAL"
    EXPLORATORY = "EXPLORATORY"


class Box(BaseModel):
    id: str
    label: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    category: str = "component"


class VehicleModel(BaseModel):
    model_id: str
    version: str
    description: str
    objects: dict[str, Box]


class Rule(BaseModel):
    operator: Literal[">=", "<=", ">", "<", "==", "range"]
    threshold: float | None = None
    lower: float | None = None
    upper: float | None = None
    unit: str = "mm"
    tolerance: float = 0.0
    authority: RuleAuthority | None = None


class VerificationCase(BaseModel):
    id: str
    version: str = "1.0"
    title: str
    source: str
    source_ref: str
    executor: Literal["minimum_clearance", "directional_distance", "angle"]
    target: str
    counterpart: str | None = None
    axis: Literal["X", "Y", "Z"] | None = None
    angle_axis: Literal["X", "Y", "Z"] | None = None
    engineering_domain: str = "unknown"
    verification_method: str = "ANALYSIS_GEOMETRY"
    workflow_id: str = "GEOMETRY_CHECK_V1"
    required_bindings: list[str] = Field(default_factory=list)
    applicable_versions: list[str] = Field(default_factory=lambda: ["*"])
    rule: Rule | None = None
    regression_epsilon: float = 0.5
    note: str = ""


class CheckCard(BaseModel):
    id: str
    version: str
    title: str
    source: str
    source_ref: str
    engineering_domain: str
    verification_method: str
    executor: Literal["minimum_clearance", "directional_distance", "angle"]
    target: str
    counterpart: str | None = None
    axis: Literal["X", "Y", "Z"] | None = None
    angle_axis: Literal["X", "Y", "Z"] | None = None
    workflow_id: str = "GEOMETRY_CHECK_V1"
    required_bindings: list[str] = Field(default_factory=list)
    applicable_versions: list[str] = Field(default_factory=lambda: ["*"])
    rule: Rule
    regression_epsilon: float = 0.5
    evidence: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    ground_truth: dict[str, Any] | None = None

    def to_case(self) -> VerificationCase:
        return VerificationCase(
            id=self.id,
            version=self.version,
            title=self.title,
            source=self.source,
            source_ref=self.source_ref,
            executor=self.executor,
            target=self.target,
            counterpart=self.counterpart,
            axis=self.axis,
            angle_axis=self.angle_axis,
            engineering_domain=self.engineering_domain,
            verification_method=self.verification_method,
            workflow_id=self.workflow_id,
            required_bindings=self.required_bindings,
            applicable_versions=self.applicable_versions,
            rule=self.rule,
            regression_epsilon=self.regression_epsilon,
            note=self.note,
        )


class Evidence(BaseModel):
    """Auditable engineering evidence plus reconstructable Viewer state.

    The engineering value is always produced by OCP/OCCT.  These fields make a
    result traceable and allow Electron Replay to restore the exact context or
    fail closed when the original model/identity contract no longer matches.
    """

    focus_ids: list[str]
    focus_occurrence_ids: list[str] = Field(default_factory=list)
    focus_paths: list[str] = Field(default_factory=list)
    line_start: tuple[float, float, float] | None = None
    line_end: tuple[float, float, float] | None = None
    camera_preset: str = "iso"
    annotation: str = ""

    evidence_id: str | None = None
    run_id: str | None = None
    check_set_id: str | None = None
    case_id: str | None = None
    case_version: str | None = None
    model_sha: str | None = None
    import_schema_version: str | None = None
    rule_version: str | None = None
    executor_version: str | None = None
    measurement_method: str | None = None
    approximation: str | None = None
    executor_params: dict[str, Any] = Field(default_factory=dict)
    binding_snapshot: dict[str, Any] = Field(default_factory=dict)
    rule_snapshot: dict[str, Any] = Field(default_factory=dict)
    coordinate_system: dict[str, Any] = Field(default_factory=dict)
    source_unit: str | None = None
    tolerance: float | None = None
    threshold: float | None = None
    runtime_info: dict[str, Any] = Field(default_factory=dict)
    view_state: dict[str, Any] = Field(default_factory=dict)
    screenshot: str | None = None


class TraceStep(BaseModel):
    stage: str
    detail: dict[str, Any]


class CheckExecution(BaseModel):
    model_id: str
    model_version: str
    case_id: str
    title: str
    executor: str
    mode: VerificationMode = VerificationMode.ENGINEERING_CHECK
    rule_authority: RuleAuthority | None = None
    check_card_version: str | None = None
    status: CheckStatus
    value: float | None = None
    unit: str = "mm"
    margin: float | None = None
    evidence: Evidence
    trace: list[TraceStep] = Field(default_factory=list)
    review_state: Literal["UNREVIEWED", "ACCEPTED", "REJECTED"] = "UNREVIEWED"


class RegressionResult(BaseModel):
    case_id: str
    title: str
    baseline: CheckExecution
    candidate: CheckExecution
    regression: RegressionStatus
    delta: float | None = None
    non_comparable_reason: str | None = None
