from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass
class Occurrence:
    path: str
    name: str
    shape: Any
    transform: tuple[float, ...]
    bbox: tuple[float, float, float, float, float, float]
    is_valid: bool
    children: list['Occurrence'] = field(default_factory=list)


@dataclass
class StepModel:
    model_id: str
    version: str
    path: Path
    schema: str | None
    source_unit: str
    coordinate_contract: str
    roots: list[Occurrence]
    occurrences: dict[str, Occurrence]
    warnings: list[str] = field(default_factory=list)

    @property
    def leaf_occurrences(self) -> list[Occurrence]:
        return [o for o in self.occurrences.values() if not o.children]


def _label_name(label: Any) -> str | None:
    from OCP.TDataStd import TDataStd_Name

    if not label.IsAttribute(TDataStd_Name.GetID_s()):
        return None
    attr = TDataStd_Name()
    if not label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return None
    text = attr.Get().ToExtString().strip()
    return text or None


def _shape_bbox(shape: Any) -> tuple[float, float, float, float, float, float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        raise ValueError('void bounding box')
    return tuple(float(x) for x in box.Get())


def _shape_valid(shape: Any) -> bool:
    from OCP.BRepCheck import BRepCheck_Analyzer

    if shape is None or shape.IsNull():
        return False
    return bool(BRepCheck_Analyzer(shape).IsValid())


def _loc_matrix(location: Any) -> tuple[float, ...]:
    if location is None or location.IsIdentity():
        return (1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0)
    trsf = location.Transformation()
    rows: list[float] = []
    for r in range(1, 4):
        rows.extend(float(trsf.Value(r, c)) for c in range(1, 5))
    rows.extend((0.0, 0.0, 0.0, 1.0))
    return tuple(rows)


def _compose_locations(parent: Any | None, child: Any | None) -> Any | None:
    if parent is None:
        return child
    if child is None:
        return parent
    return parent.Multiplied(child)


def _detect_schema(text: str) -> str | None:
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text, re.I)
    return m.group(1) if m else None


def _detect_source_unit(text: str) -> str:
    upper = text.upper()
    if "SI_UNIT(.MILLI.,.METRE.)" in upper or "SI_UNIT(.MILLI.,.METER.)" in upper:
        return "mm"
    if "CONVERSION_BASED_UNIT('MILLIMETRE'" in upper or "CONVERSION_BASED_UNIT('MILLIMETER'" in upper:
        return "mm"
    if "SI_UNIT($,.METRE.)" in upper or "SI_UNIT($,.METER.)" in upper:
        return "m"
    return "unknown"


def load_step_model(
    step_path: str | Path,
    *,
    model_id: str,
    version: str,
    coordinate_contract: str = "X-forward/Y-left/Z-up",
) -> StepModel:
    """Load a STEP assembly through STEPCAF/XCAF and expose placed leaf shapes.

    The returned occurrence paths are deterministic for a given XCAF tree and are
    the exact identifiers used by the MVP's manual binding file. No fuzzy matching
    is performed here.
    """
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_Label, TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    path = Path(step_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(errors="ignore")
    schema = _detect_schema(text)
    source_unit = _detect_source_unit(text)

    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.SetColorMode(True)
    reader.SetLayerMode(True)
    status = reader.ReadFile(str(path))
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    if reader.Transfer(doc) is False:
        raise RuntimeError(f"STEP transfer to XCAF failed: {path}")

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    if free.Length() == 0:
        raise RuntimeError(f"XCAF has no free shapes: {path}")

    occurrence_map: dict[str, Occurrence] = {}
    warnings: list[str] = []

    def referred(label: Any) -> Any:
        if not shape_tool.IsReference_s(label):
            return label
        out = TDF_Label()
        if shape_tool.GetReferredShape_s(label, out):
            return out
        return label

    def children(label: Any, resolved: Any) -> list[Any]:
        seq = TDF_LabelSequence()
        shape_tool.GetComponents_s(label, seq)
        if seq.Length() == 0 and resolved != label:
            shape_tool.GetComponents_s(resolved, seq)
        return [seq.Value(i) for i in range(1, seq.Length() + 1)]

    def walk(label: Any, parent_path: str, index: int, parent_loc: Any | None) -> Occurrence | None:
        resolved = referred(label)
        instance_shape = shape_tool.GetShape_s(label)
        prototype_shape = shape_tool.GetShape_s(resolved)
        base_shape = instance_shape if not instance_shape.IsNull() else prototype_shape
        local_loc = None if base_shape.IsNull() else base_shape.Location()
        current_loc = _compose_locations(parent_loc, local_loc)

        raw_name = _label_name(label) or _label_name(resolved) or f"occ_{index}"
        safe_name = raw_name.replace("/", "_")
        current_path = f"{parent_path}/{safe_name}" if parent_path else f"/{safe_name}"
        child_labels = children(label, resolved)

        child_nodes: list[Occurrence] = []
        for i, child in enumerate(child_labels, start=1):
            node = walk(child, current_path, i, current_loc)
            if node is not None:
                child_nodes.append(node)

        if child_nodes:
            node_shape = base_shape
        else:
            node_shape = prototype_shape if not prototype_shape.IsNull() else base_shape
            if node_shape.IsNull():
                warnings.append(f"empty shape: {current_path}")
                return None
            if current_loc is not None:
                try:
                    from OCP.TopLoc import TopLoc_Location
                    node_shape = node_shape.Located(current_loc if current_loc is not None else TopLoc_Location())
                except Exception:
                    pass

        try:
            bbox = _shape_bbox(node_shape)
        except Exception:
            bbox = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            warnings.append(f"invalid bbox: {current_path}")
        is_valid = _shape_valid(node_shape)
        if not is_valid:
            warnings.append(f"invalid BRep: {current_path}")

        node = Occurrence(
            path=current_path,
            name=raw_name,
            shape=node_shape,
            transform=_loc_matrix(current_loc),
            bbox=bbox,
            is_valid=is_valid,
            children=child_nodes,
        )
        occurrence_map[current_path] = node
        return node

    roots: list[Occurrence] = []
    for i in range(1, free.Length() + 1):
        node = walk(free.Value(i), "", i, None)
        if node is not None:
            roots.append(node)

    return StepModel(
        model_id=model_id,
        version=version,
        path=path,
        schema=schema,
        source_unit=source_unit,
        coordinate_contract=coordinate_contract,
        roots=roots,
        occurrences=occurrence_map,
        warnings=warnings,
    )


def model_readiness(model: StepModel) -> dict[str, Any]:
    leaves = model.leaf_occurrences
    invalid = [o.path for o in leaves if not o.is_valid]
    empty = [o.path for o in leaves if o.shape is None or o.shape.IsNull()]
    duplicate_bbox: dict[tuple[float, ...], list[str]] = {}
    for o in leaves:
        sig = tuple(round(v, 3) for v in o.bbox)
        duplicate_bbox.setdefault(sig, []).append(o.path)
    duplicates = [v for v in duplicate_bbox.values() if len(v) > 1]

    checks = {
        "step_read": True,
        "source_unit_mm": model.source_unit == "mm",
        "coordinate_contract_declared": bool(model.coordinate_contract),
        "assembly_or_leaf_count_positive": len(leaves) > 0,
        "all_leaf_shapes_valid": not invalid,
        "no_empty_shapes": not empty,
    }
    status = "READY" if all(checks.values()) else "READY_WITH_WARNINGS"
    if not checks["step_read"] or not checks["assembly_or_leaf_count_positive"] or empty:
        status = "BLOCKED"
    return {
        "status": status,
        "model_id": model.model_id,
        "version": model.version,
        "step": str(model.path),
        "schema": model.schema,
        "source_unit": model.source_unit,
        "coordinate_contract": model.coordinate_contract,
        "occurrence_count": len(model.occurrences),
        "leaf_count": len(leaves),
        "invalid_shapes": invalid,
        "empty_shapes": empty,
        "duplicate_bbox_groups": duplicates,
        "checks": checks,
        "warnings": model.warnings,
    }
