from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from .chameleon_client import ChameleonClient
from .config import BridgeConfig
from .rss_scanner import RssScanner
from .telegram_dispatcher import TelegramDispatcher
from .whatsapp_dispatcher import WhatsAppDispatcher

logger = logging.getLogger("chameleon_bridge")


class BotOrchestrator:
    def __init__(self, config_path: str | Path | None = None):
        self.config = BridgeConfig(config_path)
        self.client = ChameleonClient(self.config.project_root)
        self.telegram: TelegramDispatcher | None = None
        self.whatsapp: WhatsAppDispatcher | None = None
        self.rss: RssScanner | None = None

        self._init_dispatchers()
        self._init_rss()

    def _init_dispatchers(self):
        token = self.config.telegram_bot_token
        if token:
            self.telegram = TelegramDispatcher(
                bot_token=token,
                allowed_user_ids=self.config.telegram_allowed_user_ids,
            )

        api_url = self.config.evolution_api_url
        api_key = self.config.evolution_api_key
        if api_url and api_key:
            self.whatsapp = WhatsAppDispatcher(
                evolution_api_url=api_url,
                api_key=api_key,
                instance_name=self.config.whatsapp_instance_name,
                default_to=self.config.whatsapp_notify_number or "",
            )
            if hasattr(self.whatsapp, 'broadcast_numbers') and self.config.whatsapp_notify_numbers:
                self.whatsapp.broadcast_numbers = self.config.whatsapp_notify_numbers

    def _init_rss(self):
        if not self.config.rss_enabled:
            return

        def on_new(all_jobs: list[dict[str, Any]]):
            n = len(all_jobs)
            msg = f"🔍 *RSS Scan*: {n} new job{'s' if n != 1 else ''} found"
            if self.telegram:
                self.telegram.send_message(msg)
            if self.whatsapp:
                for num in self.config.whatsapp_notify_numbers:
                    self.whatsapp.send_message(num, msg.replace("*", ""))

        def on_high(job: dict[str, Any], score: int):
            if self.telegram:
                self.telegram.send_job_alert(job, score)
            if self.whatsapp:
                for num in self.config.whatsapp_notify_numbers:
                    self.whatsapp.send_job_alert(num, job, score)

        self.rss = RssScanner(
            config=self.config,
            on_new_jobs=on_new,
            on_high_score_job=on_high,
        )

    def start_rss(self):
        if self.rss:
            self.rss.start()
            logger.info("RSS scanner started")

    def stop_rss(self):
        if self.rss:
            self.rss.stop()
            logger.info("RSS scanner stopped")

    def scan_now(self, query: str = "", platforms: str = "") -> list[dict[str, Any]]:
        jobs = self.client.scan_jobs(
            query=query or "",
            platforms=platforms or self.config.rss_platforms,
            limit=self.config.rss_limit_per_query,
        )
        if self.config.rss_notify_new_jobs:
            new = [j for j in jobs if "error" not in j]
            if new:
                msg = f"🔍 *Scan complete*: {len(new)} jobs found"
                if self.telegram:
                    self.telegram.send_message(msg)
                for num in self.config.whatsapp_notify_numbers:
                    if self.whatsapp:
                        self.whatsapp.send_message(num, msg.replace("*", ""))
                for job in new[:5]:
                    if self.telegram:
                        self.telegram.send_job_alert(job)
                    for num in self.config.whatsapp_notify_numbers:
                        if self.whatsapp:
                            self.whatsapp.send_job_alert(num, job)
        return jobs

    def tailor_for_job(
        self,
        analysis_id: str,
        cv_name: str | None = None,
        skip_render: bool = False,
    ) -> dict[str, Any]:
        analysis = self.client.get_job_analysis(analysis_id)
        if not analysis:
            return {"success": False, "error": f"Analysis not found: {analysis_id}"}

        jd_text = analysis.get("raw_jd", "") or analysis.get("description", "")
        if not jd_text:
            return {"success": False, "error": "No job description in analysis"}

        result = self.client.tailor_cv(
            jd_text=jd_text,
            company=analysis.get("company_name", ""),
            title=analysis.get("role_title", ""),
            skip_render=skip_render,
        )

        if result.get("success"):
            output = result.get("output", "")
            notify_msg = f"✅ *CV tailored* for {analysis.get('role_title', '?')} at {analysis.get('company_name', '?')}"
            if self.config.telegram_notifications_enabled and self.telegram:
                self.telegram.send_message(f"{notify_msg}\n\n{output}")
            for num in self.config.whatsapp_notify_numbers:
                if self.whatsapp:
                    self.whatsapp.send_message(num, notify_msg.replace("*", ""))

            pdf_path = Path(result["pdf_path"]) if result.get("pdf_path") else None
            if pdf_path:
                if self.telegram:
                    self.telegram.send_document(str(pdf_path), caption=f"CV for {analysis.get('role_title', '?')} at {analysis.get('company_name', '?')}")
                for num in self.config.whatsapp_notify_numbers:
                    if self.whatsapp:
                        self.whatsapp.send_media(num, str(pdf_path), caption=f"CV for {analysis.get('role_title', '?')} at {analysis.get('company_name', '?')}")
        else:
            msg = result.get("error", "Tailoring failed")
            if self.config.telegram_notifications_enabled and self.telegram:
                self.telegram.send_error(msg)
            for num in self.config.whatsapp_notify_numbers:
                if self.whatsapp:
                    self.whatsapp.send_error(num, msg)

        return result

    def send_notification(self, text: str) -> None:
        if self.telegram:
            self.telegram.send_message(text)
        for num in self.config.whatsapp_notify_numbers:
            if self.whatsapp:
                self.whatsapp.send_message(num, text.replace("*", ""))
