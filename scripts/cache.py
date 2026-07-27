"""Simple TTL cache for scan results — improves trustability."""
from __future__ import annotations

import json
import time
from pathlib import Path

from scripts.config import config


def _cache_path(key: str) -> Path:
    d = config.cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return d / f"{safe}.json"


def cache_get(key: str) -> list[dict] | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
        age = time.time() - raw.get("ts", 0)
        if age > config.get("cache_ttl_seconds", 3600):
            p.unlink(missing_ok=True)
            return None
        return raw.get("data")
    except (json.JSONDecodeError, OSError):
        p.unlink(missing_ok=True)
        return None


def cache_set(key: str, data: list[dict]) -> None:
    p = _cache_path(key)
    try:
        p.write_text(json.dumps({"ts": time.time(), "data": data}))
    except OSError:
        pass


def cache_clear() -> int:
    d = config.cache_dir()
    if not d.exists():
        return 0
    count = 0
    for f in d.glob("*.json"):
        f.unlink(missing_ok=True)
        count += 1
    return count


def cache_prune() -> int:
    d = config.cache_dir()
    if not d.exists():
        return 0
    max_items = config.get("max_cached_scans", 50)
    files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    removed = 0
    for f in files[max_items:]:
        f.unlink(missing_ok=True)
        removed += 1
    return removed
