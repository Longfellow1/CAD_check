from __future__ import annotations

import base64
import importlib.metadata
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .cases import CASES
from .stage2_runtime import Stage2Workspace
from .cad.binding import resolve_binding
from .cad.tessellation import tessellate_shapes

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "models/demo_manifest.yaml"
WEB_DIST = ROOT / "web/dist"
WEB = WEB_DIST if WEB_DIST.exists() else ROOT / "web"
workspace = Stage2Workspace(ROOT)
if MANIFEST.exists() and (ROOT / "data/step/vehicle_v1.step").exists():
    try: workspace.load_manifest(MANIFEST)
    except Exception as exc: print(f"[cad-check] demo load skipped: {exc}")

app = FastAPI(title="CAD Check Stage-2", version="0.2.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")

class RegisterModel(BaseModel):
    key: str; step: str; model_id: str; version: str
    coordinate_contract: str = "X-forward/Y-left/Z-up"

class RunRequest(BaseModel):
    baseline: str = "V1"; candidate: str = "V2"

class Screenshot(BaseModel):
    data_url: str

@app.get("/")
def index(): return FileResponse(WEB / "index.html")

@app.get("/api/health")
def health(): return {"ok": True, "version": "0.2.0", "stage": "real-step-occt"}

@app.get("/api/system/readiness")
def system_readiness():
    def ver(name):
        try: return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: return None
    packages = {k: ver(k) for k in ("cadquery-ocp", "ocp-tessellate", "fastapi", "pydantic")}
    return {"status": "READY" if packages["cadquery-ocp"] and packages["ocp-tessellate"] else "BLOCKED", "python_packages": packages, "models": sorted(workspace.models)}

@app.get("/api/models")
def models():
    return {k: {"model_id":m.model_id,"version":m.version,"step":str(m.path),"schema":m.schema,"source_unit":m.source_unit,"leaf_count":len(m.leaf_occurrences)} for k,m in workspace.models.items()}

@app.post("/api/models/register")
def register(req: RegisterModel):
    p = Path(req.step); p = p if p.is_absolute() else ROOT / p
    try:
        workspace.register_model(req.key, step=p, model_id=req.model_id, version=req.version, coordinate_contract=req.coordinate_contract)
        return workspace.readiness(req.key)
    except Exception as exc: raise HTTPException(400, str(exc)) from exc

@app.get("/api/models/{key}/readiness")
def readiness(key: str):
    if key not in workspace.models: raise HTTPException(404, "model not found")
    return workspace.readiness(key)

@app.get("/api/models/{key}/inventory")
def inventory(key: str):
    if key not in workspace.models: raise HTTPException(404, "model not found")
    m=workspace.models[key]
    return {"model_id":m.model_id,"version":m.version,"occurrences":[{"path":o.path,"name":o.name,"bbox":o.bbox,"valid":o.is_valid,"children":len(o.children)} for o in m.occurrences.values()]}

@app.get("/api/models/{key}/viewer")
def viewer(key: str):
    if key not in workspace.models: raise HTTPException(404, "model not found")
    return workspace.viewer_payload(key)

@app.post("/api/runs/regression")
def run(req: RunRequest):
    try: result=workspace.run_regression(req.baseline, req.candidate)
    except Exception as exc: raise HTTPException(400, str(exc)) from exc
    return {"run_id":result["run_id"],"run_dir":result["run_dir"],"cases":[c.model_dump(mode="json") for c in CASES],"baseline":[x.model_dump(mode="json") for x in result["baseline"]],"candidate":[x.model_dump(mode="json") for x in result["candidate"]],"regression":[x.model_dump(mode="json") for x in result["regression"]]}

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    p=workspace.store.root/run_id/"result.json"
    if not p.exists(): raise HTTPException(404,"run not found")
    return FileResponse(p, media_type="application/json")

@app.get("/api/runs/{run_id}/trace")
def get_trace(run_id: str):
    p=workspace.store.root/run_id/"trace.jsonl"
    if not p.exists(): raise HTTPException(404,"trace not found")
    return FileResponse(p, media_type="application/x-ndjson")

@app.get("/api/runs/{run_id}/evidence/{case_id}/viewer")
def evidence_viewer(run_id: str, case_id: str, model: str="V2"):
    p=workspace.store.root/run_id/"result.json"
    if not p.exists() or model not in workspace.models: raise HTTPException(404,"run/model not found")
    case=next((c for c in CASES if c.id==case_id),None)
    if not case: raise HTTPException(404,"case not found")
    m=workspace.models[model]; named={}
    for sid in [case.target]+([case.counterpart] if case.counterpart else []): named[sid]=resolve_binding(m,workspace.binding_data,sid).occurrence.shape
    side="candidate" if model=="V2" else "baseline"; data=json.loads(p.read_text()); exe=next((x for x in data[side] if x["case_id"]==case_id),None)
    if exe and exe["evidence"].get("line_start") and exe["evidence"].get("line_end"):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCP.gp import gp_Pnt
        named["__measurement__"]=BRepBuilderAPI_MakeEdge(gp_Pnt(*exe["evidence"]["line_start"]),gp_Pnt(*exe["evidence"]["line_end"])).Edge()
    return tessellate_shapes(named)

@app.post("/api/runs/{run_id}/evidence/{case_id}/screenshot")
def screenshot(run_id:str, case_id:str, req:Screenshot):
    prefix="data:image/png;base64,"
    if not req.data_url.startswith(prefix): raise HTTPException(400,"expected PNG data URL")
    payload=base64.b64decode(req.data_url[len(prefix):]); p=workspace.store.save_png(run_id,case_id,payload)
    return {"saved":str(p),"bytes":len(payload)}
