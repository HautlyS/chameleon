"""Crypto Careers — scraping-based parser for crypto/blockchain jobs."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class CryptoCareersParser(BaseParser):
    platform_name = "crypto_careers"
    BASE_URL = "https://www.crypto-careers.com"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        url = self.BASE_URL
        params = {}
        page = kwargs.get("page", 1)
        if page > 1:
            params["page"] = page

        try:
            resp = httpx.get(url, params=params, timeout=15, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)"
            })
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return []

        jobs = []
        # Parse job card patterns
        card_pattern = re.compile(
            r'<a[^>]*href="(/job/[^"]+)"[^>]*>.*?'
            r'<(?:h[234]|span|div)[^>]*>([^<]+)</.*?'
            r'<(?:span|div|p)[^>]*class="[^"]*(?:company|employer)[^"]*"[^>]*>([^<]+)<',
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
                    url=f"{self.BASE_URL}{path}",
                    location="Remote",
                    remote=True,
                    tags=["crypto", "blockchain"],
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
