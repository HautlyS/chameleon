"""LinkedIn Jobs — guest API + browser fallback for anti-bot."""
from __future__ import annotations

import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class LinkedInParser(BaseParser):
    platform_name = "linkedin"
    GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    BROWSE_URL = "https://www.linkedin.com/jobs/search"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {
            "keywords": query,
            "start": kwargs.get("start", 0),
            "f_TPR": "r604800",
        }
        location = kwargs.get("location", "")
        if location:
            params["location"] = location

        jobs = []

        # Attempt 1: Guest API (HTTP)
        resp = self._http_get(
            self.GUEST_API,
            params=params,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        if resp and len(resp.text) > 500:
            self._parse_guest_api(resp.text, jobs, query, limit)

        # Attempt 2: Browser automation fallback
        if not jobs and self._browser_available():
            browse_params = {
                "keywords": query or "software engineer",
                "f_TPR": "r604800",
            }
            qs = "&".join(f"{k}={v}" for k, v in browse_params.items())
            browser_resp = self._browser_get(
                f"{self.BROWSE_URL}?{qs}",
                timeout=20,
                wait_selector=".job-card-container",
                scroll=True,
            )
            if browser_resp:
                self._parse_browser_html(browser_resp.text, jobs, query, limit)

        return jobs

    def _parse_guest_api(self, html: str, jobs: list, query: str, limit: int) -> None:
        card_pattern = re.compile(
            r'<a[^>]*href="(https://www\.linkedin\.com/jobs/view/[^"]+)"[^>]*>.*?'
            r'<h3[^>]*>([^<]+)</h3>.*?'
            r'<h4[^>]*>([^<]+)</h4>',
            re.DOTALL,
        )
        for match in card_pattern.finditer(html):
            url, title, company = match.groups()
            if query and query.lower() not in f"{title} {company}".lower():
                continue
            jobs.append(
                JobListing(
                    title=self._clean_html(title).strip(),
                    company=self._clean_html(company).strip(),
                    url=url.split("?")[0],
                    location="",
                    remote=True,
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

    def _parse_browser_html(self, html: str, jobs: list, query: str, limit: int) -> None:
        # Try JSON-LD first
        ld = self._extract_json_ld(html)
        seen = set()
        for entry in ld:
            if entry.get("@type") != "JobPosting":
                continue
            title = (entry.get("title", "") or "").strip()
            org = entry.get("hiringOrganization", {})
            company_name = (org.get("name", "") if isinstance(org, dict) else str(org)).strip()
            url = entry.get("url", "") or entry.get("directApply", "")
            if isinstance(url, dict):
                url = url.get("url", "")
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
                    title=title,
                    company=company_name,
                    url=url,
                    location="Remote",
                    remote=True,
                    description=self._truncate(self._clean_html(entry.get("description", "")), 500),
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        # Fallback: HTML card pattern
        if not jobs:
            card = re.compile(
                r'class="[^"]*job-card-container[^"]*"[^>]*>.*?'
                r'<a[^>]*href="(/jobs/view/[^"]+)"[^>]*>.*?'
                r'<span[^>]*>([^<]+)</span>.*?'
                r'<span[^>]*>([^<]+)</span>',
                re.DOTALL,
            )
            for match in card.finditer(html):
                path, title, company = match.groups()
                if query and query.lower() not in f"{title} {company}".lower():
                    continue
                jobs.append(
                    JobListing(
                        title=self._clean_html(title).strip(),
                        company=self._clean_html(company).strip(),
                        url=f"https://www.linkedin.com{path}",
                        location="",
                        remote=True,
                        source=self.platform_name,
                    )
                )
                if len(jobs) >= limit:
                    break
