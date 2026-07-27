"""Relocate.me — scraping-based parser for relocation-friendly jobs."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class RelocateParser(BaseParser):
    platform_name = "relocate"
    SEARCH_URL = "https://relocate.me/search"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {}
        if query:
            params["query"] = query

        resp = self._http_get(self.SEARCH_URL, params=params, timeout=15)
        if resp is None:
            return []

        html = resp.text
        jobs = []

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
            location = entry.get("jobLocation", "")
            if isinstance(location, dict):
                location = location.get("address", {}).get("addressLocality", location.get("name", "Remote"))
            if isinstance(location, dict):
                location = "Relocation required"
            jobs.append(
                JobListing(
                    title=title,
                    company=company_name,
                    url=url or f"https://relocate.me/job/{title.lower().replace(' ', '-')}",
                    location=str(location),
                    remote=False,
                    tags=["relocation"],
                    description=self._truncate(self._clean_html(entry.get("description", "")), 500),
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        # Fallback: HTML card parsing
        if not jobs:
            card_pattern = re.compile(
                r'<a[^>]*href="(/job[^"]+)"[^>]*>.*?'
                r'<(?:h[234]|span)[^>]*>([^<]+)</.*?'
                r'(?:<(?:span|div)[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)<|([^<]{3,50})</)',
                re.DOTALL,
            )
            for match in card_pattern.finditer(html):
                path, title, company = match.group(1), match.group(2), match.group(3) or match.group(4) or ""
                if query and query.lower() not in f"{title} {company}".lower():
                    continue
                jobs.append(
                    JobListing(
                        title=title.strip(),
                        company=company.strip() if company else "Unknown",
                        url=f"https://relocate.me{path}",
                        location="Relocation required",
                        remote=False,
                        tags=["relocation"],
                        source=self.platform_name,
                    )
                )
                if len(jobs) >= limit:
                    break

        return jobs
