"""Remote Rocketship — scraping-based parser for remote jobs."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class RemoteRocketshipParser(BaseParser):
    platform_name = "remote_rocketship"
    BASE_URL = "https://remoterocketship.com"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {}
        if query:
            params["q"] = query

        try:
            resp = httpx.get(
                self.BASE_URL,
                params=params,
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)",
                },
            )
            if resp.status_code in (403, 429):
                return []
            resp.raise_for_status()
        except Exception:
            return []

        jobs = []
        card_pattern = re.compile(
            r'<a[^>]*href="(/job/[^"]+)"[^>]*>.*?'
            r'<(?:h[234]|span)[^>]*>([^<]+)</.*?'
            r'<(?:span|div)[^>]*class="[^"]*(?:company|employer)[^"]*"[^>]*>([^<]+)<',
            re.DOTALL,
        )

        for match in card_pattern.finditer(resp.text):
            path, title, company = match.groups()
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title.strip(),
                    company=company.strip(),
                    url=f"{self.BASE_URL}{path}",
                    location="Remote",
                    remote=True,
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
