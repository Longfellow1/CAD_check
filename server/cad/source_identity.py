from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os


def source_sha256(path: str | Path, cache_root: str | Path) -> str:
    """Return a content SHA-256 with a stat keyed local cache.

    The digest is used by Evidence/Replay contracts and viewer derivatives.  A
    large STEP file is only re-hashed when size or mtime changes.
    """
    source = Path(path).resolve()
    root = Path(cache_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / "source-index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        index = {}

    stat = source.stat()
    key = str(source)
    cached = index.get(key)
    if (
        cached
        and cached.get("size") == stat.st_size
        and cached.get("mtime_ns") == stat.st_mtime_ns
        and cached.get("sha256")
    ):
        return str(cached["sha256"])

    digest = sha256()
    with source.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    value = digest.hexdigest()

    index[key] = {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": value,
    }
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, index_path)
    return value
