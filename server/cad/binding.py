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
    shape: Any
    selector: dict[str, Any] | None = None


def load_binding_file(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    if "bindings" not in data:
        raise ValueError("binding file requires top-level 'bindings'")
    return data


def _select_subshape(shape: Any, selector: dict[str, Any]) -> Any:
    from OCP.TopAbs import (
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_SHELL,
        TopAbs_VERTEX,
    )
    from OCP.TopExp import TopExp_Explorer

    kind = str(selector.get("kind", "")).lower()
    index = selector.get("index")
    kinds = {
        "shell": TopAbs_SHELL,
        "face": TopAbs_FACE,
        "edge": TopAbs_EDGE,
        "vertex": TopAbs_VERTEX,
    }
    if kind not in kinds:
        raise ValueError(f"unsupported sub-shape kind: {kind!r}")
    if not isinstance(index, int) or index < 1:
        raise ValueError("sub-shape index must be a positive 1-based integer")

    explorer = TopExp_Explorer(shape, kinds[kind])
    for current_index in range(1, index + 1):
        if not explorer.More():
            raise KeyError(f"sub-shape not found: {kind}[{index}]")
        selected = explorer.Current()
        explorer.Next()
    return selected


def resolve_binding(model: StepModel, binding_data: dict[str, Any], semantic_id: str) -> BindingResult:
    entry = binding_data.get("bindings", {}).get(semantic_id)
    if not entry:
        raise KeyError(f"missing semantic binding: {semantic_id}")
    raw_source = entry.get(model.version) or entry.get("default")
    if not raw_source:
        raise KeyError(f"binding {semantic_id} has no path for {model.version}")
    if isinstance(raw_source, dict):
        source_path = raw_source.get("path")
        selector = raw_source.get("selector")
    else:
        source_path = raw_source
        selector = None
    if not isinstance(source_path, str) or not source_path:
        raise ValueError(f"binding {semantic_id} has no source path")
    occurrence = model.occurrences.get(source_path)
    if occurrence is None:
        raise KeyError(f"binding path not found in {model.version}: {source_path}")
    selected_shape = occurrence.shape
    source_object = source_path
    if selector is not None:
        if not isinstance(selector, dict):
            raise ValueError(f"binding selector must be an object: {semantic_id}")
        selected_shape = _select_subshape(occurrence.shape, selector)
        source_object = (
            f"{source_path}#{selector['kind'].lower()}[{selector['index']}]"
        )
    return BindingResult(
        semantic_id,
        model.version,
        source_object,
        occurrence,
        selected_shape,
        selector,
    )


def validate_bindings(model: StepModel, binding_data: dict[str, Any], semantic_ids: list[str]) -> dict[str, Any]:
    ok, missing = {}, {}
    for sid in semantic_ids:
        try:
            r = resolve_binding(model, binding_data, sid)
            ok[sid] = r.source_object
        except Exception as exc:
            missing[sid] = str(exc)
    return {"ok": ok, "missing": missing, "valid": not missing}
