from __future__ import annotations

from typing import Any


def _json_safe(value: Any) -> Any:
    """Convert tessellation metadata to values accepted by a JSON API."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(
        f"unsupported viewer payload value: {type(value).__name__}"
    )


def _expand_shape_refs(node: dict[str, Any], meshes: list[dict[str, Any]]) -> None:
    """Replace ocp-tessellate's local mesh references with geometry payloads.

    ``tessellate_group`` returns a shape tree whose leaves contain
    ``{"ref": N}`` and keeps the corresponding mesh dictionaries in a
    separate list.  That reference form is an internal Python result, not a
    complete JSON payload for the browser viewer.
    """
    for part in node.get("parts", []):
        shape = part.get("shape")
        if isinstance(shape, dict) and set(shape) == {"ref"}:
            ref = shape["ref"]
            if not isinstance(ref, int) or not 0 <= ref < len(meshes):
                raise ValueError(f"invalid tessellation mesh reference: {ref!r}")
            part["shape"] = meshes[ref]
        if isinstance(part, dict) and part.get("parts"):
            _expand_shape_refs(part, meshes)


def _normalize_viewer_tree(node: dict[str, Any]) -> None:
    """Make part names and IDs safe for the viewer's slash-delimited tree."""
    parent_id = str(node.get("id") or f"/{node.get('name', 'Group')}")
    used_names: set[str] = set()
    for part in node.get("parts", []) or []:
        raw_name = str(part.get("name") or "part").strip("/")
        name = raw_name.replace("/", "__") or "part"
        base_name = name
        suffix = 2
        while name in used_names:
            name = f"{base_name}__{suffix}"
            suffix += 1
        used_names.add(name)
        part["name"] = name
        part["id"] = f"{parent_id.rstrip('/')}/{name}"
        if part.get("parts"):
            _normalize_viewer_tree(part)


def tessellate_shapes(named_shapes: dict[str, Any]) -> dict[str, Any]:
    """Convert OCP TopoDS shapes into three-cad-viewer compatible Shapes.

    Keep this adapter isolated so domain evidence never depends on the viewer's
    payload schema.
    """
    from ocp_tessellate.convert import to_ocpgroup, tessellate_group

    group, instances = to_ocpgroup(named_shapes)
    meshes, shapes, _mapping = tessellate_group(group, instances)
    _expand_shape_refs(shapes, meshes)
    _normalize_viewer_tree(shapes)
    return _json_safe({"shapes": shapes})
