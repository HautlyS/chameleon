"""DailyRemote — parser with HTTP + Playwright browser fallback."""
from __future__ import annotations

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

        jobs = []

        # Attempt 1: HTTP
        resp = self._http_get(self.SEARCH_URL, params=params)
        if resp and len(resp.text) > 1000:
            self._parse_html(resp.text, jobs, query, limit)

        # Attempt 2: Browser fallback
        if not jobs and self._browser_available():
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            browser_resp = self._browser_get(
                f"{self.SEARCH_URL}?{qs}", timeout=20,
                wait_selector="[class*='card'], [class*='job'], article, tr",
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
                    location="Remote", remote=True, source=self.platform_name,
                    description=self._truncate(self._clean_html(entry.get("description", "")), 500),
                )
            )
            if len(jobs) >= limit:
                return

        # HTML card pattern
        card = re.compile(
            r'<a[^>]*href="(/remote-jobs/[^"]+)"[^>]*>.*?'
            r'<(?:h[234]|span)[^>]*>([^<]+)</.*?'
            r'<(?:span|div)[^>]*class="[^"]*(?:company|employer)[^"]*"[^>]*>([^<]+)<',
            re.DOTALL,
        )
        for match in card.finditer(html):
            path, title, company = match.groups()
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title.strip(), company=company.strip(),
                    url=f"https://dailyremote.com{path}",
                    location="Remote", remote=True, source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                return
