"""Indeed — parser with HTTP + Playwright browser fallback."""
from __future__ import annotations

import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class IndeedParser(BaseParser):
    platform_name = "indeed"
    SEARCH_URL = "https://www.indeed.com/jobs"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {"q": query}
        location = kwargs.get("location", "")
        if location:
            params["l"] = location
        remote = kwargs.get("remote", False)
        if remote:
            params["remotejob"] = "032b3046-06a3-4876-8dfd-474eb5e7ed11"

        jobs = []

        # Attempt 1: HTTP
        resp = self._http_get(self.SEARCH_URL, params=params, retries=1)
        if resp and len(resp.text) > 1000:
            self._parse_html(resp.text, jobs, query, limit, location, remote)

        # Attempt 2: Browser fallback
        if not jobs and self._browser_available():
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            browser_resp = self._browser_get(
                f"{self.SEARCH_URL}?{qs}",
                timeout=20,
                wait_selector=".jobsearch-ResultsList",
                scroll=True,
            )
            if browser_resp:
                self._parse_html(browser_resp.text, jobs, query, limit, location, remote)

        return jobs

    def _parse_html(self, html: str, jobs: list, query: str, limit: int,
                    location: str, remote: bool) -> None:
        # Try JSON-LD first
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
                    location=location or "", remote=remote,
                    description=self._truncate(self._clean_html(entry.get("description", "")), 500),
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                return

        # Fallback: HTML card pattern
        card = re.compile(
            r'<a[^>]*href="(/rc/clk[^"]*|/viewjob[^"]*)"[^>]*>.*?'
            r'<(?:h2|span)[^>]*class="[^"]*jobTitle[^"]*"[^>]*>([^<]+)</.*?'
            r'<(?:span|div)[^>]*data-testid="[^"]*company[^"]*"[^>]*>([^<]+)<',
            re.DOTALL,
        )
        for match in card.finditer(html):
            path, title, company = match.groups()
            url = f"https://www.indeed.com{path.split('?')[0]}"
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=title.strip(), company=company.strip(),
                    url=url, location=location or "",
                    remote=remote, source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                return
