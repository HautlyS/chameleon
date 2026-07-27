"""Crypto Careers — parser with HTTP + Playwright browser fallback for Cloudflare."""
from __future__ import annotations

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
        jobs = []

        # Attempt 1: HTTP (usually Cloudflare-blocked)
        resp = self._http_get(self.BASE_URL)
        if resp and "cloudflare" not in resp.text[:500].lower() and len(resp.text) > 2000:
            self._parse_html(resp.text, jobs, query, limit)

        # Attempt 2: Browser fallback (bypasses Cloudflare)
        if not jobs and self._browser_available():
            browser_resp = self._browser_get(
                self.BASE_URL, timeout=25,
                wait_selector="[class*='job'], article, .card, tr",
                scroll=True,
            )
            if browser_resp:
                self._parse_html(browser_resp.text, jobs, query, limit)

        return jobs

    def _parse_html(self, html: str, jobs: list, query: str, limit: int) -> None:
        # Try JSON-LD
        ld = self._extract_json_ld(html)
        seen = set()
        for entry in ld:
            if entry.get("@type") != "JobPosting":
                continue
            title = (entry.get("title", "") or "").strip()
            org = entry.get("hiringOrganization", {})
            company_name = (org.get("name", "") if isinstance(org, dict) else str(org)).strip()
            url = entry.get("url", "")
            if not title or not company_name:
                continue
            key = f"{title}|{company_name}"
            if key in seen:
                continue
            seen.add(key)
            if query and query.lower() not in f"{title} {company_name}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title, company=company_name, url=url,
                    location="Remote", remote=True,
                    tags=["crypto", "blockchain"],
                    description=self._truncate(self._clean_html(entry.get("description", "")), 500),
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                return

        # HTML card pattern
        card = re.compile(
            r'<a[^>]*href="(/job/[^"]+)"[^>]*>.*?'
            r'<(?:h[234]|span|div)[^>]*>([^<]+)</.*?'
            r'<(?:span|div|p)[^>]*class="[^"]*(?:company|employer)[^"]*"[^>]*>([^<]+)<',
            re.DOTALL,
        )
        for match in card.finditer(html):
            path, title, company = match.groups()
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title.strip(), company=company.strip(),
                    url=f"{self.BASE_URL}{path}",
                    location="Remote", remote=True,
                    tags=["crypto", "blockchain"], source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                return
