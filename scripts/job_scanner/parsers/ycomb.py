"""YC Startup Jobs — scraping-based parser for Y Combinator startups."""

from __future__ import annotations

import httpx
import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class YCombParser(BaseParser):
    platform_name = "ycomb"
    BASE_URL = "https://www.ycombinator.com/jobs"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params = {}
        if query:
            params["query"] = query

        try:
            resp = httpx.get(self.BASE_URL, params=params, timeout=15, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)"
            })
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return []

        jobs = []
        # YC Jobs uses React — look for __NEXT_DATA__ or embedded JSON
        next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if next_data:
            import json
            try:
                data = json.loads(next_data.group(1))
                props = data.get("props", {}).get("pageProps", {})
                job_list = props.get("jobs", props.get("results", []))
                for item in job_list[:limit]:
                    jobs.append(
                        JobListing(
                            title=item.get("title", item.get("role", "")),
                            company=item.get("companyName", item.get("company", {}).get("name", "")),
                            url=f"https://www.ycombinator.com/companies/{item.get('company', {}).get('slug', '')}/jobs/{item.get('slug', item.get('id', ''))}",
                            location=item.get("location", ""),
                            remote=item.get("remote", True),
                            tags=item.get("tags", []),
                            source=self.platform_name,
                        )
                    )
            except Exception:
                pass

        # Fallback: HTML scraping
        if not jobs:
            card_pattern = re.compile(
                r'<a[^>]*href="(/companies/[^/]+/jobs/[^"]+)"[^>]*>.*?'
                r'<(?:span|div)[^>]*>([^<]+)</.*?'
                r'<(?:span|a)[^>]*href="/companies/([^"]+)"[^>]*>([^<]+)<',
                re.DOTALL,
            )
            for match in card_pattern.finditer(html):
                job_path, title, company_path, company = match.groups()
                if query and query.lower() not in f"{title} {company}".lower():
                    continue
                jobs.append(
                    JobListing(
                        title=title.strip(),
                        company=company.strip(),
                        url=f"https://www.ycombinator.com{job_path}",
                        location="Remote",
                        remote=True,
                        tags=["startup", "yc"],
                        source=self.platform_name,
                    )
                )
                if len(jobs) >= limit:
                    break

        return jobs
