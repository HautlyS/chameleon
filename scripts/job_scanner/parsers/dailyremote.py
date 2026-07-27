"""DailyRemote — scraping-based parser for remote jobs."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class DailyRemoteParser(BaseParser):
    platform_name = "dailyremote"
    SEARCH_URL = "https://dailyremote.com/remote-jobs"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {}
        if query:
            params["q"] = query
        params["page"] = kwargs.get("page", 1)

        try:
            resp = httpx.get(self.SEARCH_URL, params=params, timeout=15, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)"
            })
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return []

        jobs = []
        card_pattern = re.compile(
            r'<a[^>]*href="(/remote-jobs/[^"]+)"[^>]*>.*?'
            r'<(?:h[234]|span)[^>]*>([^<]+)</.*?'
            r'<(?:span|div)[^>]*class="[^"]*(?:company|employer)[^"]*"[^>]*>([^<]+)<',
            re.DOTALL,
        )

        for match in card_pattern.finditer(html):
            path, title, company = match.groups()
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title.strip(),
                    company=company.strip(),
                    url=f"https://dailyremote.com{path}",
                    location="Remote",
                    remote=True,
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
