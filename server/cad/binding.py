from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

from .step_reader import StepModel, Occurrence


@dataclass(frozen=True)
class BindingResult:
    semantic_id: str
    model_version: str
    source_object: str
    occurrence: Occurrence


def load_binding_file(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if "bindings" not in data:
        raise ValueError("binding file requires top-level 'bindings'")
    return data


def resolve_binding(model: StepModel, binding_data: dict[str, Any], semantic_id: str) -> BindingResult:
    entry = binding_data.get("bindings", {}).get(semantic_id)
    if not entry:
        raise KeyError(f"missing semantic binding: {semantic_id}")
    source_object = entry.get(model.version) or entry.get("default")
    if not source_object:
        raise KeyError(f"binding {semantic_id} has no path for {model.version}")
    occurrence = model.occurrences.get(source_object)
    if occurrence is None:
        raise KeyError(f"binding path not found in {model.version}: {source_object}")
    return BindingResult(semantic_id, model.version, source_object, occurrence)


def validate_bindings(model: StepModel, binding_data: dict[str, Any], semantic_ids: list[str]) -> dict[str, Any]:
    ok, missing = {}, {}
    for sid in semantic_ids:
        try:
            r = resolve_binding(model, binding_data, sid)
            ok[sid] = r.source_object
        except Exception as exc:
            missing[sid] = str(exc)
    return {"ok": ok, "missing": missing, "valid": not missing}
