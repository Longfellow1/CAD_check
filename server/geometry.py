from __future__ import annotations

import math
from dataclasses import dataclass
from .domain import Box


@dataclass
class DistanceResult:
    value: float
    p1: tuple[float, float, float]
    p2: tuple[float, float, float]


def _bounds(box: Box):
    cx, cy, cz = box.center
    sx, sy, sz = box.size
    return ((cx-sx/2,cx+sx/2),(cy-sy/2,cy+sy/2),(cz-sz/2,cz+sz/2))


def minimum_clearance(a: Box, b: Box) -> DistanceResult:
    ab, bb = _bounds(a), _bounds(b)
    p1, p2, diffs = [], [], []
    for (amin,amax),(bmin,bmax) in zip(ab,bb):
        if amax < bmin:
            p1.append(amax); p2.append(bmin); diffs.append(bmin-amax)
        elif bmax < amin:
            p1.append(amin); p2.append(bmax); diffs.append(amin-bmax)
        else:
            overlap=(max(amin,bmin)+min(amax,bmax))/2
            p1.append(overlap); p2.append(overlap); diffs.append(0.0)
    return DistanceResult(math.sqrt(sum(d*d for d in diffs)), tuple(p1), tuple(p2))


def directional_distance(a: Box, b: Box, axis: str) -> DistanceResult:
    idx={"X":0,"Y":1,"Z":2}[axis]
    ab,bb=_bounds(a),_bounds(b)
    amin,amax=ab[idx]; bmin,bmax=bb[idx]
    if amax <= bmin: value,av,bv=bmin-amax,amax,bmin
    elif bmax <= amin: value,av,bv=amin-bmax,amin,bmax
    else: value,av,bv=0.0,(amin+amax)/2,(bmin+bmax)/2
    p1=list(a.center); p2=list(a.center); p1[idx]=av; p2[idx]=bv
    return DistanceResult(value,tuple(p1),tuple(p2))


def orientation_angle(box: Box, axis: str) -> float:
    return abs(float(box.rotation_deg[{"X":0,"Y":1,"Z":2}[axis]]))
