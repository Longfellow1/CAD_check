from __future__ import annotations

import hashlib
from typing import Any

IMPORT_SCHEMA_VERSION = "xcaf-occurrence-v1"


def _occurrence_id(parent_id: str | None, ordinal: int, name: str) -> str:
    """Return a deterministic version-local occurrence id.

    The id deliberately includes the canonical import schema and sibling ordinal.
    It is stable for the same XCAF tree, but it is not a cross-version semantic id.
    """
    parent = parent_id or "ROOT"
    raw = f"{IMPORT_SCHEMA_VERSION}|{parent}|{ordinal}|{name}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"occ_{digest}"


def serialize_assembly_tree(model: Any) -> dict[str, Any]:
    """Serialize XCAF occurrences independently from viewer mesh payloads."""
    stats = {
        "occurrence_count": 0,
        "parent_count": 0,
        "leaf_count": 0,
        "max_depth": 0,
    }

    def walk(node: Any, parent_id: str | None, ordinal: int, depth: int) -> dict[str, Any]:
        occurrence_id = _occurrence_id(parent_id, ordinal, node.name)
        children = [
            walk(child, occurrence_id, child_ordinal, depth + 1)
            for child_ordinal, child in enumerate(node.children, start=1)
        ]

        stats["occurrence_count"] += 1
        stats["max_depth"] = max(stats["max_depth"], depth)
        if children:
            stats["parent_count"] += 1
        else:
            stats["leaf_count"] += 1

        return {
            "occurrence_id": occurrence_id,
            "parent_id": parent_id,
            "name": node.name,
            "original_path": node.path,
            "geometry_ref": {
                "kind": "occurrence_path",
                "value": node.path,
            },
            "transform": list(node.transform),
            "bbox": list(node.bbox),
            "valid": bool(node.is_valid),
            "children": children,
        }

    roots = [
        walk(root, None, ordinal, 1)
        for ordinal, root in enumerate(model.roots, start=1)
    ]

    return {
        "import_schema_version": IMPORT_SCHEMA_VERSION,
        "model_id": model.model_id,
        "version": model.version,
        "source_unit": model.source_unit,
        "coordinate_contract": model.coordinate_contract,
        "stats": stats,
        "roots": roots,
    }
