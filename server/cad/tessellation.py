from __future__ import annotations

from typing import Any


def tessellate_shapes(named_shapes: dict[str, Any]) -> dict[str, Any]:
    """Convert OCP TopoDS shapes into three-cad-viewer compatible Shapes.

    Keep this adapter isolated so domain evidence never depends on the viewer's
    payload schema.
    """
    from ocp_tessellate.convert import to_ocpgroup, tessellate_group

    group, instances = to_ocpgroup(named_shapes)
    _meshed, shapes, mapping = tessellate_group(group, instances)
    return {"shapes": shapes, "mapping": mapping}
