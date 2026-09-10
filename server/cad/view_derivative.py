from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import gzip
import json
import math
import os
import time

from .step_reader import Occurrence, StepModel
from .tessellation import _expand_shape_refs, _json_safe, _normalize_viewer_tree

DERIVATIVE_SCHEMA_VERSION = "1"


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
        deviation=0.25,
        angular_tolerance=0.3,
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


def _model_sha(model: StepModel, cache_root: Path) -> str:
    """Content identity with a tiny stat-index so repeated opens do not re-hash huge STEP files."""
    path = model.path.resolve()
    stat = path.stat()
    cache_root.mkdir(parents=True, exist_ok=True)
    index_path = cache_root / "source-index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        index = {}
    key = str(path)
    cached = index.get(key)
    if cached and cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
        return str(cached["sha256"])

    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    value = digest.hexdigest()
    index[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": value}
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, index_path)
    return value


def _chunk_groups(model: StepModel, *, max_parts: int = 4) -> list[list[Occurrence]]:
    """Assembly-first chunking with a strict leaf-count ceiling.

    Parent groups stay together when small. Oversized parents are split into stable batches.
    The first-pass budget is intentionally conservative because a single automotive leaf can
    still be geometrically heavy even when leaf_count is small.
    """
    grouped: dict[str, list[Occurrence]] = {}
    for occurrence in model.leaf_occurrences:
        grouped.setdefault(_parent_path(occurrence.path), []).append(occurrence)

    chunks: list[list[Occurrence]] = []
    for parent in sorted(grouped):
        items = sorted(grouped[parent], key=lambda item: item.path)
        for offset in range(0, len(items), max_parts):
            chunks.append(items[offset : offset + max_parts])

    # Put visually representative / large-bbox chunks first so time-to-first-geometry is useful.
    chunks.sort(key=lambda group: _bbox_diagonal(_bbox_union(group)), reverse=True)
    return chunks


def _profile(name: str) -> TessellationProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown tessellation profile: {name}") from exc


class ViewDerivativeStore:
    """Web-view derivative layer; deliberately separate from engineering BRep truth."""

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
        source_sha = _model_sha(model, self.cache_root)
        derivative_id = f"{source_sha[:20]}-{DERIVATIVE_SCHEMA_VERSION}-{profile_cfg.name}"
        derivative_dir = self.cache_root / derivative_id
        derivative_dir.mkdir(parents=True, exist_ok=True)

        groups = _chunk_groups(model)
        chunks: list[dict[str, Any]] = []
        for index, group in enumerate(groups):
            chunk_id = f"chunk-{index:04d}"
            cache_file = derivative_dir / f"{chunk_id}.json.gz"
            bbox = _bbox_union(group)
            chunks.append(
                {
                    "id": chunk_id,
                    "part_count": len(group),
                    "paths": [item.path for item in group],
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
        _normalize_viewer_tree(shapes)
        payload = _json_safe(
            {
                "shapes": shapes,
                "meta": {
                    "chunk_id": chunk_id,
                    "profile": cfg.name,
                    "part_count": meta["part_count"],
                    "paths": meta["paths"],
                    "cache": "MISS",
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
