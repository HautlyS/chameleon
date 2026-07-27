"""Dynamic configuration for Chameleon — 0 hardcoded values.

All settings live in a JSON file next to this module. The TUI can
read/write every key through the Settings tab. Defaults are created
on first run.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent.parent / ".chameleon"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    # ── Paths ──────────────────────────────────────────────────────────
    "profile_path": "profiles/github_repos.json",
    "master_cv_path": "templates/tupa_cv.yaml",
    "templates_dir": "templates",
    "output_dir": "output",
    "scans_dir": "output/scans",
    "analyses_dir": "output/job_analyses",
    "venv_python": ".venv/bin/python3",
    "cache_dir": ".chameleon/cache",
    "db_path": ".chameleon/jobs.db",
    "fonts_dir": ".chameleon/fonts",

    # ── Scanner defaults ───────────────────────────────────────────────
    "scan_queries": ["python", "rust", "ai engineer"],
    "scan_platforms": "remoteok,remotive,hn_hiring",
    "scan_limit_per_query": 15,
    "scan_timeout_seconds": 45,

    # ── Matching ───────────────────────────────────────────────────────
    "score_weight_languages": 25,
    "score_weight_frameworks": 25,
    "score_weight_domains": 25,
    "score_weight_cv_alignment": 25,
    "score_threshold_strong": 80,
    "score_threshold_good": 60,
    "score_threshold_moderate": 40,
    "max_matching_repos": 5,
    "max_cv_keywords_in_detail": 5,
    "cv_alignment_min_match_strong": 5,
    "cv_alignment_min_match_good": 3,
    "cv_alignment_min_match_moderate": 1,
    "domain_adjacent_min_strong": 2,
    "domain_adjacent_min_good": 1,
    "lang_overlap_3_score": 25,
    "lang_overlap_2_score": 20,
    "lang_overlap_1_score": 15,
    "lang_related_score": 10,
    "fw_overlap_3_score": 25,
    "fw_overlap_2_score": 20,
    "fw_overlap_1_score": 15,
    "fw_adjacent_score": 8,
    "dom_overlap_2_score": 25,
    "dom_overlap_1_score": 20,
    "dom_adjacent_2_score": 15,
    "dom_adjacent_1_score": 10,
    "cv_match_5_score": 25,
    "cv_match_3_score": 20,
    "cv_match_1_score": 15,

    # ── Score colors (Textual markup) ──────────────────────────────────
    "color_strong": "bold bright_green",
    "color_good": "bold yellow",
    "color_moderate": "bold dark_orange",
    "color_weak": "bold red",

    # ── Fonts for CV rendering ─────────────────────────────────────────
    "cv_font_family": "Source Sans Pro",
    "cv_font_size_body": "9.5pt",
    "cv_font_size_headline": "9.5pt",
    "cv_font_size_connections": "9.5pt",
    "cv_line_spacing": "0.8em",
    "cv_entry_spacing": "0.2cm",
    "cv_page_margin_top": "1.0cm",
    "cv_page_margin_bottom": "1.0cm",
    "cv_page_margin_left": "1.5cm",
    "cv_page_margin_right": "1.5cm",
    "cv_primary_color": "#2b3a67",
    "cv_secondary_color": "#3a5a8c",

    # ── Tailoring ──────────────────────────────────────────────────────
    "summary_max_chars": 300,
    "safe_company_max_chars": 20,
    "safe_title_max_chars": 20,
    "opencode_bin_path": "~/.opencode/bin/opencode",

    # ── AI Reviewer / Model ────────────────────────────────────────────
    "model_provider": "opencode",
    "model_id": "big-pickle",
    "opencode_api_url": "http://localhost:4096",
    "opencode_server_username": "",
    "opencode_server_password": "",

    # ── Telegram Bot ───────────────────────────────────────────────────
    "telegram_bot_token": "",
    "telegram_allowed_user_ids": "",

    # ── WhatsApp / Evolution API ───────────────────────────────────────
    "evolution_api_url": "http://localhost:8080",
    "evolution_api_key": "",
    "whatsapp_instance_name": "chameleon",

    # ── Bridge ─────────────────────────────────────────────────────────
    "webhook_secret": "change-me-to-a-random-string",
    "rss_scan_interval_minutes": 60,
    "rss_notify_new_jobs": True,
    "rss_notify_high_score": True,
    "rss_high_score_threshold": 70,

    # ── Setup Wizard ───────────────────────────────────────────────────
    "setup_wizard_completed": False,
    "setup_wizard_version": 1,

    # ── Cache ──────────────────────────────────────────────────────────
    "cache_ttl_seconds": 3600,
    "max_cached_scans": 50,

    # ── Rate limiting ──────────────────────────────────────────────────
    "rate_limit_per_platform_per_minute": 10,
    "rate_limit_global_per_minute": 60,

    # ── Retry ──────────────────────────────────────────────────────────
    "max_retries": 3,
    "retry_backoff_seconds": 2,

    # ── ATS Ghost Text ────────────────────────────────────────────────
    "ats_ghost_enabled": False,
    "ats_ghost_extra_terms": "",
    "ats_ghost_font_size": "1",
    "ats_ghost_color": "#ffffff",
}

# Domain adjacency (used by matcher)
DOMAIN_ADJACENCY: dict[str, list[str]] = {
    "healthcare": ["ai/ml", "web-apps", "data-science"],
    "cryptography": ["security", "desktop-apps", "file-management", "blockchain"],
    "ai/ml": ["embeddings", "rag", "web-automation", "data-science"],
    "rag": ["ai/ml", "embeddings", "nlp"],
    "embeddings": ["ai/ml", "rag", "vector-database"],
    "devops": ["infrastructure", "web-automation", "cloud"],
    "fintech": ["web-apps", "api", "ecommerce"],
    "ecommerce": ["web-apps", "marketplace", "fintech"],
    "geospatial": ["mapping", "gis", "data-visualization"],
    "web-automation": ["testing", "devops", "browser"],
    "desktop-apps": ["cross-platform", "gui", "file-management"],
    "file-management": ["storage", "cloud", "desktop-apps"],
    "education": ["web-apps", "content-management"],
    "conservation": ["geospatial", "data-science", "environmental"],
}

# Language adjacency (used by matcher)
LANG_ADJACENCY: dict[str, list[str]] = {
    "typescript": ["javascript"],
    "javascript": ["typescript"],
    "vue": ["javascript", "typescript"],
}


def _resolve(path: str) -> Path:
    base = Path(__file__).resolve().parent.parent
    return (base / path).resolve()


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


class Config:
    """Thread-safe config store. Reload by calling config.reload()."""

    _data: dict[str, Any] = {}
    _loaded = False
    _lock = threading.Lock()

    def __init__(self) -> None:
        if not Config._loaded:
            Config.reload()

    @classmethod
    def reload(cls) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text())
                cls._data = {**DEFAULTS, **raw}
            except (json.JSONDecodeError, OSError):
                cls._data = dict(DEFAULTS)
        else:
            cls._data = dict(DEFAULTS)
            cls._persist()
        cls._loaded = True

    @classmethod
    def _persist(cls) -> None:
        _ensure_dir(CONFIG_PATH)
        try:
            CONFIG_PATH.write_text(json.dumps(cls._data, indent=2))
        except OSError:
            pass

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        with cls._lock:
            cls._data[key] = value
            cls._persist()

    @classmethod
    def set_nopersist(cls, key: str, value: Any) -> None:
        """Update in memory only — call persist() to write to disk."""
        with cls._lock:
            cls._data[key] = value

    @classmethod
    def persist(cls) -> None:
        """Write current config to disk."""
        with cls._lock:
            cls._persist()

    @classmethod
    def set_many(cls, updates: dict[str, Any]) -> None:
        with cls._lock:
            cls._data.update(updates)
            cls._persist()

    @classmethod
    def all(cls) -> dict[str, Any]:
        return dict(cls._data)

    @classmethod
    def resolve(cls, key: str) -> Path:
        raw = cls.get(key, "")
        if not raw:
            return Path()
        return _resolve(raw)

    # ── Convenience helpers ────────────────────────────────────────────
    @classmethod
    def profile_path(cls) -> Path:
        return cls.resolve("profile_path")

    @classmethod
    def master_cv_path(cls) -> Path:
        return cls.resolve("master_cv_path")

    @classmethod
    def templates_dir(cls) -> Path:
        return cls.resolve("templates_dir")

    @classmethod
    def output_dir(cls) -> Path:
        return cls.resolve("output_dir")

    @classmethod
    def scans_dir(cls) -> Path:
        return _resolve(cls.get("scans_dir", "output/scans"))

    @classmethod
    def analyses_dir(cls) -> Path:
        return _resolve(cls.get("analyses_dir", "output/job_analyses"))

    @classmethod
    def venv_python(cls) -> Path:
        raw = cls.get("venv_python", ".venv/bin/python3")
        base = Path(__file__).resolve().parent.parent
        # Don't .resolve() through symlinks — venv python is often a symlink
        # to system python, and resolving loses venv site-packages.
        return (base / raw)

    @classmethod
    def cache_dir(cls) -> Path:
        return _resolve(cls.get("cache_dir", ".chameleon/cache"))

    @classmethod
    def fonts_dir(cls) -> Path:
        return _resolve(cls.get("fonts_dir", ".chameleon/fonts"))

    @classmethod
    def score_color(cls, score: int) -> str:
        if score >= cls.get("score_threshold_strong", 80):
            return cls.get("color_strong", "bold bright_green")
        elif score >= cls.get("score_threshold_good", 60):
            return cls.get("color_good", "bold yellow")
        elif score >= cls.get("score_threshold_moderate", 40):
            return cls.get("color_moderate", "bold dark_orange")
        return cls.get("color_weak", "bold red")

    @classmethod
    def scan_queries(cls) -> list[str]:
        return list(cls.get("scan_queries", ["python", "rust", "ai engineer"]))

    @classmethod
    def scan_platforms(cls) -> str:
        return cls.get("scan_platforms", "remoteok,remotive,hn_hiring")

    @classmethod
    def scan_limit(cls) -> int:
        return cls.get("scan_limit_per_query", 15)

    @classmethod
    def scan_timeout(cls) -> int:
        return cls.get("scan_timeout_seconds", 45)

    @classmethod
    def env(cls) -> dict[str, str]:
        """Return env dict with PATH extended for subprocess calls."""
        env = os.environ.copy()
        opencode_bin = cls.opencode_bin()
        if opencode_bin:
            parent = str(opencode_bin.parent)
            path = env.get("PATH", "")
            sep = ";" if os.name == "nt" else ":"
            if parent not in path:
                env["PATH"] = f"{parent}{sep}{path}"
        return env

    @classmethod
    def opencode_bin(cls) -> Path:
        raw = cls.get("opencode_bin_path", "~/.opencode/bin/opencode")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = _resolve(raw)
        return path

    @classmethod
    def domain_adjacency(cls) -> dict[str, list[str]]:
        return dict(DOMAIN_ADJACENCY)

    @classmethod
    def lang_adjacency(cls) -> dict[str, list[str]]:
        return dict(LANG_ADJACENCY)

    # ── Bridge config sync ─────────────────────────────────────────────
    @classmethod
    def bridge_config_path(cls) -> Path:
        return cls.resolve("db_path").parent / "bridge.json"

    @classmethod
    def sync_to_bridge(cls) -> None:
        """Push relevant settings to .chameleon/bridge.json so the bridge
        process picks them up without manual .env editing."""
        bridge_path = cls.bridge_config_path()
        try:
            if bridge_path.exists():
                import json
                bridge = json.loads(bridge_path.read_text())
            else:
                bridge = {}
            bridge.setdefault("telegram", {})
            bridge["telegram"]["bot_token"] = cls.get("telegram_bot_token", "")
            bridge["telegram"]["allowed_user_ids"] = cls.get("telegram_allowed_user_ids", "")
            bridge.setdefault("whatsapp", {})
            bridge["whatsapp"]["evolution_api_url"] = cls.get("evolution_api_url", "http://localhost:8080")
            bridge["whatsapp"]["evolution_api_key"] = cls.get("evolution_api_key", "")
            bridge["whatsapp"]["instance_name"] = cls.get("whatsapp_instance_name", "chameleon")
            bridge.setdefault("chameleon", {})
            bridge["chameleon"]["project_root"] = str(cls.resolve("master_cv_path").parent.parent)
            bridge["chameleon"]["master_cv"] = str(cls.master_cv_path().relative_to(cls.resolve("master_cv_path").parent.parent))
            bridge_path.parent.mkdir(parents=True, exist_ok=True)
            bridge_path.write_text(json.dumps(bridge, indent=2))
        except Exception:
            pass


config = Config()
