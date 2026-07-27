from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class BridgeConfig:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path(__file__).resolve().parent.parent.parent / ".chameleon" / "bridge.json"
        self._path = Path(path)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        defaults = self._defaults()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(defaults, indent=2))
        return defaults

    def _defaults(self) -> dict[str, Any]:
        return {
            "telegram": {
                "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                "allowed_user_ids": os.environ.get("TELEGRAM_ALLOWED_USER_IDS", ""),
                "notifications_enabled": True,
            },
            "whatsapp": {
                "evolution_api_url": os.environ.get("EVOLUTION_API_URL", "http://localhost:8080"),
                "evolution_api_key": os.environ.get("EVOLUTION_API_KEY", ""),
                "instance_name": os.environ.get("WHATSAPP_INSTANCE_NAME", "chameleon"),
                "notifications_enabled": True,
            },
            "rss": {
                "enabled": True,
                "interval_minutes": int(os.environ.get("RSS_SCAN_INTERVAL_MINUTES", "60")),
                "queries": ["python", "rust", "ai engineer"],
                "platforms": "remoteok,remotive,hn_hiring",
                "limit_per_query": 10,
                "score_threshold": 40,
                "notify_new_jobs": True,
                "notify_high_score": True,
                "high_score_threshold": 70,
            },
            "chameleon": {
                "project_root": str(Path(__file__).resolve().parent.parent.parent),
                "master_cv": "templates/tupa_cv.yaml",
                "output_dir": "output",
                "analyses_dir": "output/job_analyses",
            },
        }

    @property
    def telegram_bot_token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN") or self._data.get("telegram", {}).get("bot_token", "")

    @property
    def telegram_allowed_user_ids(self) -> list[int]:
        raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS") or self._data.get("telegram", {}).get("allowed_user_ids", "")
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]

    @property
    def telegram_notifications_enabled(self) -> bool:
        return self._data.get("telegram", {}).get("notifications_enabled", True)

    @property
    def evolution_api_url(self) -> str:
        return os.environ.get("EVOLUTION_API_URL") or self._data.get("whatsapp", {}).get("evolution_api_url", "")

    @property
    def evolution_api_key(self) -> str:
        return os.environ.get("EVOLUTION_API_KEY") or self._data.get("whatsapp", {}).get("evolution_api_key", "")

    @property
    def whatsapp_instance_name(self) -> str:
        return os.environ.get("WHATSAPP_INSTANCE_NAME") or self._data.get("whatsapp", {}).get("instance_name", "chameleon")

    @property
    def whatsapp_notifications_enabled(self) -> bool:
        return self._data.get("whatsapp", {}).get("notifications_enabled", True)

    @property
    def whatsapp_notify_number(self) -> str:
        env = os.environ.get("WHATSAPP_NOTIFY_NUMBER", "")
        return env or self._data.get("whatsapp", {}).get("notify_number", "")

    @property
    def whatsapp_notify_numbers(self) -> list[str]:
        nums = list(self._data.get("whatsapp", {}).get("notify_numbers", []))
        single = self.whatsapp_notify_number
        if single and single not in nums:
            nums.insert(0, single)
        return nums

    @property
    def rss_enabled(self) -> bool:
        return self._data.get("rss", {}).get("enabled", True)

    @property
    def rss_interval_minutes(self) -> int:
        return self._data.get("rss", {}).get("interval_minutes", 60)

    @property
    def rss_queries(self) -> list[str]:
        return self._data.get("rss", {}).get("queries", ["python", "rust", "ai engineer"])

    @property
    def rss_platforms(self) -> str:
        return self._data.get("rss", {}).get("platforms", "remoteok,remotive,hn_hiring")

    @property
    def rss_limit_per_query(self) -> int:
        return self._data.get("rss", {}).get("limit_per_query", 10)

    @property
    def rss_score_threshold(self) -> int:
        return self._data.get("rss", {}).get("score_threshold", 40)

    @property
    def rss_notify_new_jobs(self) -> bool:
        return self._data.get("rss", {}).get("notify_new_jobs", True)

    @property
    def rss_notify_high_score(self) -> bool:
        return self._data.get("rss", {}).get("notify_high_score", True)

    @property
    def rss_high_score_threshold(self) -> int:
        return self._data.get("rss", {}).get("high_score_threshold", 70)

    @property
    def project_root(self) -> Path:
        return Path(self._data.get("chameleon", {}).get("project_root", Path(__file__).resolve().parent.parent.parent))

    @property
    def master_cv(self) -> str:
        return self._data.get("chameleon", {}).get("master_cv", "templates/tupa_cv.yaml")

    @property
    def output_dir(self) -> Path:
        return self.project_root / self._data.get("chameleon", {}).get("output_dir", "output")

    @property
    def analyses_dir(self) -> Path:
        return self.project_root / self._data.get("chameleon", {}).get("analyses_dir", "output/job_analyses")

    def reload(self):
        self._data = self._load()

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key)


config = BridgeConfig()
