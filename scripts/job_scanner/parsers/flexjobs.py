"""FlexJobs — scraping-based parser (membership required for full details)."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class FlexJobsParser(BaseParser):
    platform_name = "flexjobs"
    SEARCH_URL = "https://www.flexjobs.com/search"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {"search": query}
        location = kwargs.get("location", "")
        if location:
            params["location"] = location

        try:
            resp = httpx.get(
                self.SEARCH_URL,
                params=params,
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
                    url=f"https://www.flexjobs.com{path}",
                    location=location or "",
                    remote=True,
                    tags=["flexible"],
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
