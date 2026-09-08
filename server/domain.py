from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
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


class VerificationCase(BaseModel):
    id: str
    title: str
    source: str
    source_ref: str
    executor: Literal["minimum_clearance", "directional_distance", "angle"]
    target: str
    counterpart: str | None = None
    axis: Literal["X", "Y", "Z"] | None = None
    angle_axis: Literal["X", "Y", "Z"] | None = None
    rule: Rule
    regression_epsilon: float = 0.5
    note: str = ""


class Evidence(BaseModel):
    focus_ids: list[str]
    line_start: tuple[float, float, float] | None = None
    line_end: tuple[float, float, float] | None = None
    camera_preset: str = "iso"
    annotation: str = ""


class TraceStep(BaseModel):
    stage: str
    detail: dict[str, Any]


class CheckExecution(BaseModel):
    model_id: str
    model_version: str
    case_id: str
    title: str
    executor: str
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
