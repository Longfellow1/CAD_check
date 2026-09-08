from __future__ import annotations

from dataclasses import dataclass
from math import degrees
from typing import Any


@dataclass(frozen=True)
class GeometryResult:
    value: float
    p1: tuple[float, float, float] | None = None
    p2: tuple[float, float, float] | None = None
    method: str = ""
    approximation: str | None = None


def _pnt_tuple(p: Any) -> tuple[float, float, float]:
    return (float(p.X()), float(p.Y()), float(p.Z()))


def minimum_clearance(shape_a: Any, shape_b: Any) -> GeometryResult:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    tool = BRepExtrema_DistShapeShape(shape_a, shape_b)
    tool.Perform()
    if not tool.IsDone():
        raise RuntimeError("OCCT minimum distance failed")
    value = float(tool.Value())
    p1 = _pnt_tuple(tool.PointOnShape1(1)) if tool.NbSolution() else None
    p2 = _pnt_tuple(tool.PointOnShape2(1)) if tool.NbSolution() else None
    return GeometryResult(value=value, p1=p1, p2=p2, method="BRepExtrema_DistShapeShape")


def _bbox(shape: Any) -> tuple[float, float, float, float, float, float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    if b.IsVoid():
        raise RuntimeError("void bbox")
    return tuple(float(v) for v in b.Get())


def directional_distance(shape_a: Any, shape_b: Any, axis: str) -> GeometryResult:
    """Axis-aligned clearance using exact BRep bounding extrema.

    This is intentionally labelled as an approximation for generic directional
    distance. It is suitable for the Stage-2 spike and must be replaced by the
    engineering method defined by the Check Card where directional projection is
    not equivalent to bounding extrema.
    """
    idx = {"X": 0, "Y": 1, "Z": 2}[axis]
    a, b = _bbox(shape_a), _bbox(shape_b)
    amin, amax = a[idx], a[idx + 3]
    bmin, bmax = b[idx], b[idx + 3]
    if amax <= bmin:
        value, av, bv = bmin - amax, amax, bmin
    elif bmax <= amin:
        value, av, bv = amin - bmax, amin, bmax
    else:
        value, av, bv = 0.0, (amin + amax) / 2.0, (bmin + bmax) / 2.0
    center = [(a[0] + a[3]) / 2, (a[1] + a[4]) / 2, (a[2] + a[5]) / 2]
    p1 = center.copy(); p2 = center.copy(); p1[idx] = av; p2[idx] = bv
    return GeometryResult(
        value=float(value), p1=tuple(p1), p2=tuple(p2),
        method=f"BRep bbox extrema axis={axis}", approximation="bbox_axis_extrema",
    )


def orientation_angle(transform: tuple[float, ...], axis: str) -> GeometryResult:
    from OCP.gp import gp_Mat, gp_Quaternion, gp_EulerSequence

    mat = gp_Mat(
        transform[0], transform[1], transform[2],
        transform[4], transform[5], transform[6],
        transform[8], transform[9], transform[10],
    )
    q = gp_Quaternion(mat)
    rx, ry, rz = q.GetEulerAngles(gp_EulerSequence.gp_Extrinsic_XYZ)
    value = abs({"X": degrees(rx), "Y": degrees(ry), "Z": degrees(rz)}[axis])
    return GeometryResult(value=float(value), method=f"gp_Quaternion Extrinsic_XYZ/{axis}")
