from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .cases import CASES
from .demo_data import all_models
from .regression import compare_runs
from .runtime import run_all

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/"web"
app=FastAPI(title="CAD Check MVP",version="0.1.0")
app.mount("/static",StaticFiles(directory=WEB),name="static")

@app.get("/")
def index():
    return FileResponse(WEB/"index.html")

@app.get("/api/health")
def health():
    return {"ok":True,"version":"0.1.0"}

@app.get("/api/demo")
def demo():
    models=all_models(); baseline=run_all(models["V1"],CASES); candidate=run_all(models["V2"],CASES); regression=compare_runs(baseline,candidate,CASES)
    return {"models":{k:v.model_dump() for k,v in models.items()},"cases":[c.model_dump() for c in CASES],"baseline":[r.model_dump() for r in baseline],"candidate":[r.model_dump() for r in candidate],"regression":[r.model_dump() for r in regression]}
