from __future__ import annotations

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import BridgeConfig
from .chameleon_client import ChameleonClient


class RssScanner:
    MAX_SEEN_IDS = 10_000
    def __init__(
        self,
        config: BridgeConfig,
        on_new_jobs: Callable[[list[dict[str, Any]]], None] | None = None,
        on_high_score_job: Callable[[dict[str, Any], int], None] | None = None,
    ):
        self.config = config
        self.client = ChameleonClient(config.project_root)
        self.on_new_jobs = on_new_jobs
        self.on_high_score_job = on_high_score_job
        self._running = False
        self._thread: threading.Thread | None = None
        self._seen_file = config.project_root / ".chameleon" / "rss_seen.json"
        self._seen_ids: set[str] = set()
        self._stop_event = threading.Event()
        self._load_seen()

    def _load_seen(self):
        if self._seen_file.exists():
            try:
                data = json.loads(self._seen_file.read_text())
                self._seen_ids = set(data.get("seen_ids", []))
            except (json.JSONDecodeError, FileNotFoundError):
                self._seen_ids = set()

    def _save_seen(self):
        self._seen_file.parent.mkdir(parents=True, exist_ok=True)
        # Retaining every historical ID makes this state grow forever. The
        # scanner only needs a bounded recent window for de-duplication.
        seen_ids = sorted(self._seen_ids)[-self.MAX_SEEN_IDS:]
        self._seen_ids = set(seen_ids)
        self._seen_file.write_text(json.dumps({
            "seen_ids": seen_ids,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }))

    def scan_and_notify(self) -> list[dict[str, Any]]:
        all_new: list[dict[str, Any]] = []
        high_score_jobs: list[tuple[dict[str, Any], int]] = []

        for query in self.config.rss_queries:
            jobs = self.client.scan_jobs(
                query=query,
                platforms=self.config.rss_platforms,
                limit=self.config.rss_limit_per_query,
            )
            if isinstance(jobs, list):
                for job in jobs:
                    if "error" in job:
                        continue
                    jid = job.get("job_id", "")
                    if jid and jid not in self._seen_ids:
                        self._seen_ids.add(jid)
                        all_new.append(job)

        if not all_new:
            self._save_seen()
            return []

        if self.config.rss_notify_high_score and self.config.rss_high_score_threshold > 0:
            for job in all_new:
                desc = job.get("description", "")
                if len(desc) > 50:
                    result = self.client.score_job(
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        description=desc,
                    )
                    score = result.get("score", 0) if isinstance(result, dict) else 0
                    job["_score"] = score
                    if score >= self.config.rss_high_score_threshold:
                        high_score_jobs.append((job, score))

        if self.on_new_jobs and all_new:
            self.on_new_jobs(all_new)

        for job, score in high_score_jobs:
            if self.on_high_score_job:
                self.on_high_score_job(job, score)

        self._save_seen()
        return all_new

    def _loop(self):
        while self._running:
            try:
                self.scan_and_notify()
            except Exception:
                import traceback
                pass
            self._stop_event.wait(self.config.rss_interval_minutes * 60)

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running
