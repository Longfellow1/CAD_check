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


def tessellate_shapes(named_shapes: dict[str, Any]) -> dict[str, Any]:
    """Convert OCP TopoDS shapes into three-cad-viewer compatible Shapes.

    Keep this adapter isolated so domain evidence never depends on the viewer's
    payload schema.
    """
    from ocp_tessellate.convert import to_ocpgroup, tessellate_group

    group, instances = to_ocpgroup(named_shapes)
    _meshed, shapes, _mapping = tessellate_group(group, instances)
    # ``mapping`` is an internal tessellation index and contains raw OCP
    # TopoDS objects.  It must not cross the JSON API boundary; the viewer
    # consumes the serialized ``shapes`` payload and its ref IDs instead.
    return _json_safe({"shapes": shapes})
