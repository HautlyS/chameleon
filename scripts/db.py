"""
Persistent SQLite store for scanned jobs, tailored CVs, and scan history.
Every job, score, and tailored CV lives on disk — survives restarts.
0 hardcoded paths. DB path from config.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.config import config

_local = threading.local()


def compute_job_id(title: str, company: str) -> str:
    """Deterministic 12-char job ID from title+company. FIPS-safe."""
    raw = f"{title}|{company}".encode()
    try:
        return hashlib.md5(raw, usedforsecurity=False).hexdigest()[:12]
    except TypeError:
        return hashlib.md5(raw).hexdigest()[:12]


def _get_conn() -> sqlite3.Connection:
    """Thread-local connection — safe for TUI background workers."""
    if not hasattr(_local, "conn") or _local.conn is None:
        db_path = config.resolve("db_path") or (
            Path(__file__).resolve().parent.parent / ".chameleon" / "jobs.db"
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(db_path))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def migrate():
    """Ensure all tables exist. Idempotent — safe to call on every startup."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id            TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            company       TEXT NOT NULL,
            url           TEXT DEFAULT '',
            location      TEXT DEFAULT 'Remote',
            description   TEXT DEFAULT '',
            salary        TEXT DEFAULT '',
            source        TEXT DEFAULT '',
            remote        INTEGER DEFAULT 0,
            tags          TEXT DEFAULT '[]',
            score         INTEGER DEFAULT 0,
            score_detail  TEXT DEFAULT '{}',
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tailored_cvs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id        TEXT REFERENCES jobs(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            company       TEXT NOT NULL,
            score         INTEGER DEFAULT 0,
            yaml_path     TEXT DEFAULT '',
            pdf_path      TEXT DEFAULT '',
            description   TEXT DEFAULT '',
            url           TEXT DEFAULT '',
            location      TEXT DEFAULT 'Remote',
            remote        INTEGER DEFAULT 0,
            salary        TEXT DEFAULT '',
            tags          TEXT DEFAULT '[]',
            source        TEXT DEFAULT 'tailored',
            aliases       TEXT DEFAULT '',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            query         TEXT NOT NULL,
            platform      TEXT NOT NULL,
            job_count     INTEGER DEFAULT 0,
            duration_ms   INTEGER DEFAULT 0,
            scanned_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);
        CREATE INDEX IF NOT EXISTS idx_tailored_job_id ON tailored_cvs(job_id);
    """)
    conn.commit()


# ── Jobs ─────────────────────────────────────────────────────────────────


def save_job(
    title: str,
    company: str,
    url: str = "",
    location: str = "Remote",
    description: str = "",
    salary: str = "",
    source: str = "",
    remote: bool = False,
    tags: list[str] | None = None,
    score: int = 0,
    score_detail: dict | None = None,
    job_id: str | None = None,
) -> str:
    """Insert or update a job. Returns the job ID."""
    job_id = job_id or compute_job_id(title, company)
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO jobs (id, title, company, url, location, description, salary, source, remote, tags, score, score_detail, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            url         = excluded.url,
            location    = excluded.location,
            description = excluded.description,
            salary      = excluded.salary,
            source      = excluded.source,
            remote      = excluded.remote,
            tags        = excluded.tags,
            score       = excluded.score,
            score_detail = excluded.score_detail,
            updated_at  = datetime('now')
        """,
        (
            job_id, title, company, url, location, description,
            salary, source, int(remote),
            json.dumps(tags or []), score, json.dumps(score_detail or {}),
        ),
    )
    conn.commit()
    return job_id


def save_jobs(jobs: list[dict]) -> int:
    """Save multiple jobs. Returns count saved."""
    count = 0
    for j in jobs:
        save_job(
            title=j.get("title", ""),
            company=j.get("company", ""),
            url=j.get("url", ""),
            location=j.get("location", "Remote"),
            description=j.get("description", ""),
            salary=j.get("salary", ""),
            source=j.get("source", ""),
            remote=bool(j.get("remote", False)),
            tags=j.get("tags") or [],
            score=j.get("score", 0),
            score_detail=j.get("score_detail") or {},
            job_id=j.get("job_id") or j.get("id"),
        )
        count += 1
    return count


def get_all_jobs(limit: int = 500, offset: int = 0) -> list[dict]:
    """Return all jobs ordered by score DESC."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY score DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id: str) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(r) if r else None


def find_jobs(
    keyword: str = "",
    source: str = "",
    min_score: int = 0,
    limit: int = 100,
) -> list[dict]:
    """Search jobs by keyword in title/company/description."""
    conn = _get_conn()
    parts: list[str] = ["SELECT * FROM jobs WHERE 1=1"]
    params: list[Any] = []
    if keyword:
        parts.append("AND (title LIKE ? OR company LIKE ? OR description LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])
    if source:
        parts.append("AND source = ?")
        params.append(source)
    if min_score:
        parts.append("AND score >= ?")
        params.append(min_score)
    parts.append("ORDER BY score DESC LIMIT ?")
    params.append(limit)
    rows = conn.execute(" ".join(parts), params).fetchall()
    return [_row_to_job(r) for r in rows]


def delete_job(job_id: str) -> bool:
    conn = _get_conn()
    c = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    return c.rowcount > 0


def update_job_score(job_id: str, score: int, score_detail: dict) -> bool:
    conn = _get_conn()
    c = conn.execute(
        "UPDATE jobs SET score = ?, score_detail = ?, updated_at = datetime('now') WHERE id = ?",
        (score, json.dumps(score_detail), job_id),
    )
    conn.commit()
    return c.rowcount > 0


def job_count() -> int:
    conn = _get_conn()
    return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


# ── Tailored CVs ──────────────────────────────────────────────────────────


def save_tailored_cv(
    job_id: str,
    title: str,
    company: str,
    score: int = 0,
    yaml_path: str = "",
    pdf_path: str = "",
    description: str = "",
    url: str = "",
    location: str = "Remote",
    remote: bool = False,
    salary: str = "",
    tags: list[str] | None = None,
    source: str = "tailored",
    aliases: str = "",
) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """
        INSERT INTO tailored_cvs
            (job_id, title, company, score, yaml_path, pdf_path,
             description, url, location, remote, salary, tags, source, aliases)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id, title, company, score, yaml_path, pdf_path,
            description, url, location, int(remote), salary,
            json.dumps(tags or []), source, aliases,
        ),
    )
    conn.commit()
    return cur.lastrowid or 0


def get_tailored_cvs(limit: int = 50) -> list[dict]:
    rows = _get_conn().execute(
        "SELECT * FROM tailored_cvs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_tailored(r) for r in rows]


def delete_tailored_cv(tailored_id: int) -> bool:
    conn = _get_conn()
    c = conn.execute("DELETE FROM tailored_cvs WHERE id = ?", (tailored_id,))
    conn.commit()
    return c.rowcount > 0


# ── Scan history ──────────────────────────────────────────────────────────


def record_scan(query: str, platform: str, job_count: int, duration_ms: int) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO scans (query, platform, job_count, duration_ms) VALUES (?, ?, ?, ?)",
        (query, platform, job_count, duration_ms),
    )
    conn.commit()
    return cur.lastrowid or 0


def get_recent_scans(limit: int = 20) -> list[dict]:
    rows = _get_conn().execute(
        "SELECT * FROM scans ORDER BY scanned_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────


def _row_to_job(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["remote"] = bool(d["remote"])
    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else (d["tags"] or [])
    d["score_detail"] = json.loads(d["score_detail"]) if isinstance(d["score_detail"], str) else (d["score_detail"] or {})
    return d


def _row_to_tailored(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["remote"] = bool(d["remote"])
    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else (d["tags"] or [])
    return d


def close():
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None


# Auto-migrate on first import (idempotent)
migrate()
