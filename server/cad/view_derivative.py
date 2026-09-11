from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import gzip
import json
import math
import os
import time

from .assembly_tree import occurrence_index
from .source_identity import source_sha256
from .step_reader import Occurrence, StepModel
from .tessellation import _expand_shape_refs, _json_safe, _normalize_viewer_tree

# v6 keeps native OCCT BRepMesh for the fast whole-vehicle surface preview,
# but uses the existing ocp-tessellate path for visibly large invalid BReps.
# Some imported STEP parts (notably the Scania cab) triangulate natively while
# still rendering as an incomplete surface.  The old serializer produces a
# usable display derivative for those parts; small malformed springs remain on
# the proxy path so one pathological detail cannot stall a whole vehicle.
# Compatibility meshes are normalized to canonical world coordinates before
# they leave the CAD Worker.  This keeps placement independent of the chosen
# WebGL renderer's instance-transform implementation.
# Bump whenever display selection/fallback policy changes.  Older schema-5
# chunks may still contain local fallback coordinates and must not be reused.
DERIVATIVE_SCHEMA_VERSION = "6"

# A malformed leaf smaller than roughly one percent of the assembly is kept on
# the native path. This bounds the legacy fallback to visually material parts
# and avoids the known slow path for tiny imported helix/spring geometry.
LEGACY_FALLBACK_ASSEMBLY_RATIO = 0.01


@dataclass(frozen=True)
class TessellationProfile:
    name: str
    deviation: float
    angular_tolerance: float
    render_edges: bool


PROFILES: dict[str, TessellationProfile] = {
    "preview": TessellationProfile(
        name="preview",
        deviation=1.0,
        angular_tolerance=0.5,
        render_edges=False,
    ),
    "normal": TessellationProfile(
        name="normal",
        # This is the default medium surface preview, not engineering evidence.
        # A 0.5 mm native OCCT mesh keeps vehicle silhouettes useful while
        # avoiding an unnecessarily dense first-pass mesh.
        deviation=0.5,
        angular_tolerance=0.4,
        render_edges=False,
    ),
    "evidence": TessellationProfile(
        name="evidence",
        deviation=0.1,
        angular_tolerance=0.2,
        render_edges=True,
    ),
}


def _bbox_union(items: Iterable[Occurrence]) -> tuple[float, float, float, float, float, float]:
    boxes = [item.bbox for item in items]
    if not boxes:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        min(b[2] for b in boxes),
        max(b[3] for b in boxes),
        max(b[4] for b in boxes),
        max(b[5] for b in boxes),
    )


def _bbox_diagonal(bbox: tuple[float, ...]) -> float:
    return math.sqrt(
        (bbox[3] - bbox[0]) ** 2
        + (bbox[4] - bbox[1]) ** 2
        + (bbox[5] - bbox[2]) ** 2
    )


def _parent_path(path: str) -> str:
    parent = path.rsplit("/", 1)[0]
    return parent or "/"


def _chunk_groups(model: StepModel, *, max_parts: int = 4) -> list[list[Occurrence]]:
    """Assembly-first chunking with a strict leaf-count ceiling.

    This remains a cache/build unit only.  The Electron viewer no longer loads
    every chunk; it uses Canonical AssemblyTree bbox proxies for whole-vehicle
    overview and requests detail on demand.
    """
    grouped: dict[str, list[Occurrence]] = {}
    for occurrence in model.leaf_occurrences:
        grouped.setdefault(_parent_path(occurrence.path), []).append(occurrence)

    chunks: list[list[Occurrence]] = []
    for parent in sorted(grouped):
        items = sorted(grouped[parent], key=lambda item: item.path)
        for offset in range(0, len(items), max_parts):
            chunks.append(items[offset : offset + max_parts])

    chunks.sort(key=lambda group: _bbox_diagonal(_bbox_union(group)), reverse=True)
    return chunks


def _profile(name: str) -> TessellationProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown tessellation profile: {name}") from exc


def _leaf_parts(node: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in node.get("parts", []) or []:
        if isinstance(part, dict) and part.get("parts"):
            result.extend(_leaf_parts(part))
        elif isinstance(part, dict):
            result.append(part)
    return result


def _rotate_vector(vector: list[float], quaternion: list[float]) -> list[float]:
    """Rotate a vector by an ``[x, y, z, w]`` unit quaternion."""
    qx, qy, qz, qw = (float(value) for value in quaternion)
    length = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if length <= 1e-12:
        raise ValueError("viewer fallback location has a zero quaternion")
    qx, qy, qz, qw = (value / length for value in (qx, qy, qz, qw))

    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    xw, yw, zw = qx * qw, qy * qw, qz * qw
    x, y, z = (float(value) for value in vector)
    return [
        (1.0 - 2.0 * (yy + zz)) * x + 2.0 * (xy - zw) * y + 2.0 * (xz + yw) * z,
        2.0 * (xy + zw) * x + (1.0 - 2.0 * (xx + zz)) * y + 2.0 * (yz - xw) * z,
        2.0 * (xz - yw) * x + 2.0 * (yz + xw) * y + (1.0 - 2.0 * (xx + yy)) * z,
    ]


def _bake_part_location(part: dict[str, Any]) -> bool:
    """Bake a legacy tessellator occurrence transform into its mesh.

    ``ocp-tessellate`` serializes a shared local mesh plus an occurrence
    ``loc``.  Native OCCT preview meshes are already in world coordinates, so
    leaving only the legacy path in local coordinates makes the two paths
    renderer-dependent.  Baking here gives both paths the same contract:
    vertices and normals are in the canonical model frame and ``loc`` is
    identity.
    """
    loc = part.get("loc")
    if not isinstance(loc, (list, tuple)) or len(loc) < 2:
        return False
    translation, quaternion = loc[0], loc[1]
    if not (
        isinstance(translation, (list, tuple))
        and len(translation) == 3
        and isinstance(quaternion, (list, tuple))
        and len(quaternion) == 4
    ):
        raise ValueError("viewer fallback location must contain translation and quaternion")

    translation = [float(value) for value in translation]
    quaternion = [float(value) for value in quaternion]
    identity_quaternion = [0.0, 0.0, 0.0, 1.0]
    is_identity = all(abs(value) <= 1e-12 for value in translation) and all(
        abs(value - expected) <= 1e-12
        for value, expected in zip(quaternion, identity_quaternion, strict=True)
    )
    if is_identity:
        part["loc"] = [[0.0, 0.0, 0.0], identity_quaternion]
        return False

    shape = part.get("shape")
    vertices = shape.get("vertices") if isinstance(shape, dict) else None
    if not isinstance(vertices, list) or len(vertices) % 3:
        raise ValueError("viewer fallback location cannot be baked without mesh vertices")

    for index in range(0, len(vertices), 3):
        rotated = _rotate_vector(vertices[index : index + 3], quaternion)
        vertices[index : index + 3] = [
            rotated[axis] + translation[axis] for axis in range(3)
        ]

    normals = shape.get("normals") if isinstance(shape, dict) else None
    if isinstance(normals, list) and len(normals) == len(vertices):
        for index in range(0, len(normals), 3):
            rotated = _rotate_vector(normals[index : index + 3], quaternion)
            length = math.sqrt(sum(component * component for component in rotated))
            if length > 1e-12:
                rotated = [component / length for component in rotated]
            normals[index : index + 3] = rotated

    part["loc"] = [[0.0, 0.0, 0.0], identity_quaternion]
    return True


def _bake_part_locations(parts: list[dict[str, Any]]) -> list[str]:
    """Normalize placed fallback parts and return the paths that were baked."""
    baked: list[str] = []
    for part in parts:
        if _bake_part_location(part):
            source_path = part.get("source_path")
            if isinstance(source_path, str):
                baked.append(source_path)
    return baked


def _native_mesh_part(shape: Any, *, deviation: float, angular_tolerance: float) -> dict[str, Any]:
    """Mesh one placed BRep with OCCT's native triangulator.

    The viewer derivative is a display artifact, so it should not inherit a
    pathological tessellation path from the higher-level ocp-tessellate
    serializer.  Native BRepMesh is both faster for imported STEP faces and
    keeps the operation inside the CAD Worker.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location

    BRepMesh_IncrementalMesh(
        shape,
        float(deviation),
        False,
        float(angular_tolerance),
        True,
    )

    vertices: list[float] = []
    triangles: list[int] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None and triangulation.NbNodes() and triangulation.NbTriangles():
            offset = len(vertices) // 3
            transform = location.Transformation()
            for index in range(1, triangulation.NbNodes() + 1):
                point = triangulation.Node(index).Transformed(transform)
                vertices.extend((float(point.X()), float(point.Y()), float(point.Z())))
            reversed_face = face.Orientation() == TopAbs_REVERSED
            for index in range(1, triangulation.NbTriangles() + 1):
                first, second, third = triangulation.Triangle(index).Get()
                if reversed_face:
                    second, third = third, second
                triangles.extend(
                    (
                        offset + int(first) - 1,
                        offset + int(second) - 1,
                        offset + int(third) - 1,
                    )
                )
        explorer.Next()

    if not triangles:
        raise ValueError("native OCCT triangulation produced no triangles")

    normals = [0.0] * len(vertices)
    for index in range(0, len(triangles), 3):
        ia, ib, ic = (triangles[index + item] * 3 for item in range(3))
        ax, ay, az = vertices[ia : ia + 3]
        bx, by, bz = vertices[ib : ib + 3]
        cx, cy, cz = vertices[ic : ic + 3]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for vertex in (ia, ib, ic):
            normals[vertex] += nx
            normals[vertex + 1] += ny
            normals[vertex + 2] += nz
    for index in range(0, len(normals), 3):
        length = math.sqrt(sum(component * component for component in normals[index : index + 3]))
        if length <= 1e-12:
            normals[index : index + 3] = [0.0, 0.0, 1.0]
        else:
            normals[index : index + 3] = [component / length for component in normals[index : index + 3]]

    return {
        "vertices": vertices,
        "triangles": triangles,
        "normals": normals,
        "edges": [],
        "face_types": [],
    }


def _native_tessellate(
    named_shapes: dict[str, Any],
    *,
    deviation: float,
    angular_tolerance: float,
) -> tuple[dict[str, Any], list[str]]:
    parts: list[dict[str, Any]] = []
    skipped_paths: list[str] = []
    for path, shape in named_shapes.items():
        try:
            mesh = _native_mesh_part(
                shape,
                deviation=deviation,
                angular_tolerance=angular_tolerance,
            )
        except ValueError as exc:
            if str(exc) != "native OCCT triangulation produced no triangles":
                raise
            # Keep the canonical occurrence and its bbox proxy visible. A
            # malformed display mesh must never block the complete vehicle.
            skipped_paths.append(path)
            continue
        parts.append(
            {
                "name": str(path).strip("/").replace("/", "__"),
                "shape": mesh,
                # Coordinates are already transformed into the canonical world
                # frame by the placed XCAF occurrence shape.
                "loc": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            }
        )
    return (
        {
            "version": 3,
            "id": "/Dict",
            "name": "Dict",
            "parts": parts,
        },
        skipped_paths,
    )


def _legacy_fallback_paths(model: StepModel, paths: list[str]) -> list[str]:
    """Choose large malformed leaves that need the compatibility tessellator."""
    assembly_diagonal = _bbox_diagonal(_bbox_union(model.leaf_occurrences))
    threshold = max(assembly_diagonal * LEGACY_FALLBACK_ASSEMBLY_RATIO, 1e-9)
    return [
        path
        for path in paths
        if not model.occurrences[path].is_valid
        and _bbox_diagonal(model.occurrences[path].bbox) >= threshold
    ]


def _legacy_tessellate(
    model: StepModel,
    paths: list[str],
    *,
    deviation: float,
    angular_tolerance: float,
    render_edges: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Tessellate malformed display leaves without blocking the whole chunk.

    Try one batch first for the common case. If an individual imported shape
    makes the compatibility serializer fail, retry each requested leaf so
    healthy fallbacks still render and the remaining leaf can use native
    BRepMesh as a last resort.
    """
    if not paths:
        return [], [], []

    from .tessellation import tessellate_occurrence_paths

    try:
        payload = tessellate_occurrence_paths(
            model,
            paths,
            deviation=deviation,
            angular_tolerance=angular_tolerance,
            render_edges=render_edges,
        )
        parts = _leaf_parts(payload["shapes"])
        _bake_part_locations(parts)
        return parts, list(paths), []
    except Exception:
        parts: list[dict[str, Any]] = []
        rendered: list[str] = []
        failed: list[str] = []
        for path in paths:
            try:
                payload = tessellate_occurrence_paths(
                    model,
                    [path],
                    deviation=deviation,
                    angular_tolerance=angular_tolerance,
                    render_edges=render_edges,
                )
                path_parts = _leaf_parts(payload["shapes"])
                _bake_part_locations(path_parts)
                parts.extend(path_parts)
                rendered.append(path)
            except Exception:
                failed.append(path)
        return parts, rendered, failed


def _attach_occurrence_identity(
    shapes: dict[str, Any],
    model: StepModel,
    paths: list[str],
) -> None:
    """Attach authoritative occurrence identity to renderable leaves.

    ocp-tessellate owns only geometry serialization.  The authoritative object
    identity comes from the XCAF canonical tree and is copied onto the derived
    render payload so picking can return occurrence_id directly.
    """
    leaves = _leaf_parts(shapes)
    if len(leaves) != len(paths):
        raise ValueError(
            f"viewer derivative leaf mismatch: geometry={len(leaves)} paths={len(paths)}"
        )
    identities = occurrence_index(model)
    for leaf, source_path in zip(leaves, paths, strict=True):
        identity = identities.get(source_path)
        if identity is None:
            raise ValueError(f"missing canonical identity for {source_path}")
        leaf["source_path"] = source_path
        leaf["occurrence_id"] = identity["occurrence_id"]
        leaf["prototype_ref"] = source_path


class ViewDerivativeStore:
    """Viewer derivative cache, deliberately separate from engineering BRep truth."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.cache_root = self.root / ".cadcheck" / "cache" / "viewer"
        self._manifest_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def manifest(self, model_key: str, model: StepModel, *, profile: str = "preview") -> dict[str, Any]:
        profile_cfg = _profile(profile)
        cache_key = (model_key, profile)
        cached = self._manifest_cache.get(cache_key)
        stat = model.path.stat()
        if cached and cached.get("source", {}).get("mtime_ns") == stat.st_mtime_ns:
            return cached

        started = time.perf_counter()
        skipped_paths: list[str] = []
        source_sha = source_sha256(model.path, self.cache_root)
        derivative_id = f"{source_sha[:20]}-{DERIVATIVE_SCHEMA_VERSION}-{profile_cfg.name}"
        derivative_dir = self.cache_root / derivative_id
        derivative_dir.mkdir(parents=True, exist_ok=True)

        identities = occurrence_index(model)
        groups = _chunk_groups(model)
        chunks: list[dict[str, Any]] = []
        for index, group in enumerate(groups):
            chunk_id = f"chunk-{index:04d}"
            cache_file = derivative_dir / f"{chunk_id}.json.gz"
            bbox = _bbox_union(group)
            paths = [item.path for item in group]
            chunks.append(
                {
                    "id": chunk_id,
                    "part_count": len(group),
                    "paths": paths,
                    "occurrence_ids": [identities[path]["occurrence_id"] for path in paths],
                    "bbox": bbox,
                    "bbox_diagonal": round(_bbox_diagonal(bbox), 3),
                    "cached": cache_file.exists(),
                    "url": f"/api/models/{model_key}/viewer/chunks/{chunk_id}?profile={profile_cfg.name}",
                }
            )

        manifest = {
            "schema": DERIVATIVE_SCHEMA_VERSION,
            "model": model_key,
            "model_id": model.model_id,
            "version": model.version,
            "streaming": True,
            "strategy": "proxy-overview+on-demand-detail",
            "profile": {
                "name": profile_cfg.name,
                "deviation": profile_cfg.deviation,
                "angular_tolerance": profile_cfg.angular_tolerance,
                "render_edges": profile_cfg.render_edges,
            },
            "source": {
                "sha256": source_sha,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            },
            "derivative_id": derivative_id,
            "part_count": len(model.leaf_occurrences),
            "chunk_count": len(chunks),
            "chunks": chunks,
            "build_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        (derivative_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._manifest_cache[cache_key] = manifest
        return manifest

    def chunk_path(self, model_key: str, model: StepModel, chunk_id: str, *, profile: str = "preview") -> Path:
        manifest = self.manifest(model_key, model, profile=profile)
        if chunk_id not in {item["id"] for item in manifest["chunks"]}:
            raise KeyError(f"unknown viewer chunk: {chunk_id}")
        return self.cache_root / manifest["derivative_id"] / f"{chunk_id}.json.gz"

    def build_chunk(self, model_key: str, model: StepModel, chunk_id: str, *, profile: str = "preview") -> dict[str, Any]:
        manifest = self.manifest(model_key, model, profile=profile)
        meta = next((item for item in manifest["chunks"] if item["id"] == chunk_id), None)
        if meta is None:
            raise KeyError(f"unknown viewer chunk: {chunk_id}")
        path = self.chunk_path(model_key, model, chunk_id, profile=profile)
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            payload.setdefault("meta", {})["cache"] = "HIT"
            return payload

        cfg = _profile(profile)
        named = {occurrence_path: model.occurrences[occurrence_path].shape for occurrence_path in meta["paths"]}
        started = time.perf_counter()
        fallback_paths: list[str] = []
        fallback_rendered: list[str] = []
        fallback_failed: list[str] = []
        rendered_paths: list[str] = []
        skipped_paths: list[str] = []
        invalid_proxy_paths: list[str] = []

        # Evidence keeps the existing serializer because it carries the
        # higher-fidelity edge payload.  Preview/normal are display-only and
        # use native OCCT BRepMesh, which is materially more predictable for
        # imported STEP parts with small helical faces.
        if cfg.name == "evidence":
            from ocp_tessellate.convert import tessellate_group, to_ocpgroup

            group, instances = to_ocpgroup(named)
            meshes, shapes, _mapping = tessellate_group(
                group,
                instances,
                kwargs={
                    "deviation": cfg.deviation,
                    "angular_tolerance": cfg.angular_tolerance,
                    "render_edges": cfg.render_edges,
                    "render_normals": False,
                },
            )
            _expand_shape_refs(shapes, meshes)
            tessellator = "ocp-tessellate"
            rendered_paths = list(meta["paths"])
        else:
            fallback_candidates = _legacy_fallback_paths(model, meta["paths"])
            fallback_paths = fallback_candidates
            legacy_parts, fallback_rendered, fallback_failed = _legacy_tessellate(
                model,
                fallback_candidates,
                deviation=cfg.deviation,
                angular_tolerance=cfg.angular_tolerance,
                render_edges=cfg.render_edges,
            )
            native_paths = [
                path
                for path in meta["paths"]
                if path not in fallback_rendered
                and model.occurrences[path].is_valid
            ]
            native_named = {path: model.occurrences[path].shape for path in native_paths}
            native_shapes, native_skipped_paths = _native_tessellate(
                native_named,
                deviation=cfg.deviation,
                angular_tolerance=cfg.angular_tolerance,
            )
            shapes = {
                "version": 3,
                "id": "/Dict",
                "name": "Dict",
                "parts": [*native_shapes.get("parts", []), *legacy_parts],
            }
            rendered_paths = [
                path for path in native_paths if path not in native_skipped_paths
            ] + fallback_rendered
            # Valid imported paths use native BRepMesh. Invalid imported BReps
            # are never sent to native BRepMesh: a tiny malformed spring can
            # make that OCCT path run indefinitely. If the compatibility path
            # also fails, keep the canonical bbox proxy instead of blocking
            # the complete Scania preview.
            invalid_proxy_paths = [
                path
                for path in meta["paths"]
                if not model.occurrences[path].is_valid
                and path not in fallback_rendered
            ]
            skipped_paths = [*native_skipped_paths, *invalid_proxy_paths]
            tessellator = (
                "occt-brepmesh+ocp-tessellate-invalid"
                if fallback_rendered
                else "occt-brepmesh"
            )
        _normalize_viewer_tree(shapes)
        _attach_occurrence_identity(shapes, model, rendered_paths)
        payload = _json_safe(
            {
                "shapes": shapes,
                "meta": {
                    "chunk_id": chunk_id,
                    "profile": cfg.name,
                    "part_count": meta["part_count"],
                    "paths": meta["paths"],
                    "occurrence_ids": meta["occurrence_ids"],
                    "skipped_paths": skipped_paths,
                    "rendered_part_count": len(rendered_paths),
                    "fallback_paths": fallback_paths,
                    "fallback_rendered_paths": fallback_rendered,
                    "fallback_failed_paths": fallback_failed,
                    "invalid_proxy_paths": invalid_proxy_paths,
                    "cache": "MISS",
                    "tessellator": tessellator,
                    "tessellation_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            }
        )
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(tmp, "wb", compresslevel=4) as handle:
            handle.write(raw)
        os.replace(tmp, path)
        payload["meta"]["raw_bytes"] = len(raw)
        payload["meta"]["gzip_bytes"] = path.stat().st_size
        return payload

    def cache_status(self, model_key: str, model: StepModel, *, profile: str = "preview") -> dict[str, Any]:
        manifest = self.manifest(model_key, model, profile=profile)
        cached = 0
        bytes_total = 0
        for chunk in manifest["chunks"]:
            path = self.cache_root / manifest["derivative_id"] / f"{chunk['id']}.json.gz"
            if path.exists():
                cached += 1
                bytes_total += path.stat().st_size
        return {
            "model": model_key,
            "profile": profile,
            "cached_chunks": cached,
            "total_chunks": manifest["chunk_count"],
            "cached_bytes": bytes_total,
        }
