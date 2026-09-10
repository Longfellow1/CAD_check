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
    """Replace ocp-tessellate's local mesh references with geometry payloads."""
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
    """Keep legacy IDs deterministic while the canonical tree owns identity."""
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


def _leaf_parts(node: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in node.get("parts", []) or []:
        if isinstance(part, dict) and part.get("parts"):
            result.extend(_leaf_parts(part))
        elif isinstance(part, dict):
            result.append(part)
    return result


def _tessellate(named_shapes: dict[str, Any], *, kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    from ocp_tessellate.convert import to_ocpgroup, tessellate_group

    group, instances = to_ocpgroup(named_shapes)
    meshes, shapes, _mapping = tessellate_group(group, instances, kwargs=kwargs or {})
    _expand_shape_refs(shapes, meshes)
    _normalize_viewer_tree(shapes)
    return shapes


def tessellate_shapes(named_shapes: dict[str, Any]) -> dict[str, Any]:
    """Legacy-compatible geometry payload used by controlled fixtures."""
    return _json_safe({"shapes": _tessellate(named_shapes)})


def tessellate_occurrence_paths(
    model: Any,
    paths: list[str],
    *,
    deviation: float = 0.25,
    angular_tolerance: float = 0.3,
    render_edges: bool = False,
) -> dict[str, Any]:
    """Tessellate selected XCAF occurrences for the replaceable Electron viewer.

    The output adds canonical occurrence identity to each geometry leaf.  It is
    intentionally small/on-demand; whole-vehicle hierarchy comes from the
    Canonical AssemblyTree rather than this payload.
    """
    from .assembly_tree import occurrence_index

    unique_paths = list(dict.fromkeys(paths))
    missing = [path for path in unique_paths if path not in model.occurrences]
    if missing:
        raise KeyError(f"unknown occurrence path(s): {missing[:5]}")

    named = {path: model.occurrences[path].shape for path in unique_paths}
    shapes = _tessellate(
        named,
        kwargs={
            "deviation": deviation,
            "angular_tolerance": angular_tolerance,
            "render_edges": render_edges,
            "render_normals": False,
        },
    )
    leaves = _leaf_parts(shapes)
    if len(leaves) != len(unique_paths):
        raise ValueError(
            f"occurrence tessellation mismatch: geometry={len(leaves)} paths={len(unique_paths)}"
        )

    identities = occurrence_index(model)
    for leaf, source_path in zip(leaves, unique_paths, strict=True):
        identity = identities[source_path]
        leaf["source_path"] = source_path
        leaf["occurrence_id"] = identity["occurrence_id"]
        leaf["prototype_ref"] = source_path

    return _json_safe(
        {
            "schema": "cadcheck-viewer-v2",
            "shapes": shapes,
            "paths": unique_paths,
            "occurrence_ids": [identities[path]["occurrence_id"] for path in unique_paths],
        }
    )
