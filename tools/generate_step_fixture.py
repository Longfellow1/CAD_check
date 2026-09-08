#!/usr/bin/env python3
from __future__ import annotations

import re
from math import radians
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Controlled fixture contract:
# CLR_BAT_BRACKET must measure 12.0 mm in V1 and 8.0 mm in V2.
BASE = {
    "battery": ((1500, 1100, 120), (0, 0, 220), (0, 0, 0)),
    "underbody_bracket": ((500, 800, 20), (0, 0, 138), (0, 0, 0)),
    "left_rail": ((1700, 90, 160), (0, 650, 300), (0, 0, 0)),
    "right_rail": ((1700, 90, 160), (0, -650, 300), (0, 0, 0)),
    "motor": ((520, 480, 420), (650, 0, 520), (0, 0, 0.8)),
    "motor_bracket": ((260, 70, 240), (650, 295, 520), (0, 0, 0)),
    "controller": ((360, 260, 150), (300, -360, 610), (0, 1.0, 0)),
    "controller_bracket": ((300, 40, 180), (300, -515, 610), (0, 0, 0)),
    "exhaust": ((600, 180, 180), (720, 480, 450), (0, 0, 0)),
    "front_crossmember": ((130, 1150, 120), (1020, 0, 330), (0, 0, 0)),
    "ground_ref": ((2800, 1700, 10), (0, 0, 0), (0, 0, 0)),
    "rear_module": ((460, 420, 300), (-800, 0, 420), (0, 0.6, 0)),
}


def variant(version: str):
    data = {
        name: [list(size), list(center), list(rotation)]
        for name, (size, center, rotation) in BASE.items()
    }
    if version == "V2":
        # Battery moves 4 mm toward the bracket: 12 mm -> 8 mm.
        data["battery"][1] = [0, 0, 216]
        data["controller"][1] = [300, -375, 610]
        data["motor"][1] = [680, 0, 520]
        data["motor"][2] = [0, 0, 2.2]
        data["rear_module"][2] = [0, 0.1, 0]
    return data


def _location(center, rotation_deg):
    from OCP.TopLoc import TopLoc_Location
    from OCP.gp import gp_EulerSequence, gp_Quaternion, gp_Trsf, gp_Vec

    quat = gp_Quaternion()
    quat.SetEulerAngles(
        gp_EulerSequence.gp_Extrinsic_XYZ,
        *[radians(value) for value in rotation_deg],
    )
    trsf = gp_Trsf()
    trsf.SetRotation(quat)
    trsf.SetTranslationPart(gp_Vec(*center))
    return TopLoc_Location(trsf)


def _file_schema(raw: str) -> str | None:
    match = re.search(
        r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'",
        raw,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1) if match else None


def write_fixture(version: str, path: Path) -> Path:
    """Write a named XCAF assembly as STEP AP242 and fail on silent flattening.

    The fixture exists to verify our STEP boundary, not only the downstream
    primitive math. Names, occurrence paths and placements must survive a real
    STEP write/read round trip.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Controller
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.gp import gp_Pnt

    # STEP parameters do not exist until the controller is initialized. Setting
    # AP242 before Init can be a no-op and makes the first generated file AP214.
    STEPControl_Controller.Init_s()
    if not Interface_Static.SetCVal_s("write.step.schema", "AP242DIS"):
        raise RuntimeError("OCCT rejected write.step.schema=AP242DIS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    Interface_Static.SetCVal_s("xstep.cascade.unit", "MM")

    app = XCAFApp_Application.GetApplication_s()
    fmt = TCollection_ExtendedString("XmlXCAF")
    doc = TDocStd_Document(fmt)
    app.NewDocument(fmt, doc)
    app.InitDocument(doc)
    XCAFDoc_DocumentTool.SetLengthUnit_s(doc, 0.001)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    shape_tool.SetAutoNaming_s(False)

    root = shape_tool.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("Vehicle"))

    for name, (size, center, rotation_deg) in variant(version).items():
        sx, sy, sz = size
        shape = BRepPrimAPI_MakeBox(
            gp_Pnt(-sx / 2.0, -sy / 2.0, -sz / 2.0),
            sx,
            sy,
            sz,
        ).Shape()
        definition = shape_tool.AddShape(shape, False)
        TDataStd_Name.Set_s(
            definition,
            TCollection_ExtendedString(f"{name}_part"),
        )
        occurrence = shape_tool.AddComponent(
            root,
            definition,
            _location(center, rotation_deg),
        )
        TDataStd_Name.Set_s(
            occurrence,
            TCollection_ExtendedString(name),
        )

    # XCAF must regenerate the assembly compound before the STEP transfer.
    shape_tool.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    writer.SetLayerMode(True)
    if writer.Transfer(doc, STEPControl_AsIs) is False:
        raise RuntimeError(f"STEP transfer failed for {version}")

    path.parent.mkdir(parents=True, exist_ok=True)
    status = writer.Write(str(path))
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed for {version}: {status}")

    raw = path.read_text(errors="ignore")
    schema = _file_schema(raw)
    if not schema or "AP242" not in schema.upper():
        raise RuntimeError(
            f"{version} fixture is not AP242: {schema or 'FILE_SCHEMA missing'}"
        )
    return path


if __name__ == "__main__":
    for version, filename in (("V1", "vehicle_v1.step"), ("V2", "vehicle_v2.step")):
        print(write_fixture(version, ROOT / "data" / "step" / filename))
