"""Himalayas — free JSON API + RSS, no auth required."""

from __future__ import annotations

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class HimalayasParser(BaseParser):
    platform_name = "himalayas"
    API_URL = "https://himalayas.app/jobs/api"
    SEARCH_URL = "https://himalayas.app/jobs/api/search"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params: dict = {"limit": min(limit, 50)}
        url = self.SEARCH_URL if query else self.API_URL
        if query:
            params["q"] = query

        resp = self._http_get(url, params=params)
        if resp is None:
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        jobs = []
        for item in data.get("jobs", [])[:limit]:
            jobs.append(
                JobListing(
                    title=item.get("title", ""),
                    company=item.get("companyName", ""),
                    url=item.get("applicationLink") or item.get("guid", ""),
                    location=item.get("location", ""),
                    remote=item.get("remote", True),
                    tags=[t.get("name", "") for t in item.get("tags", [])],
                    posted_at=item.get("datePosted", ""),
                    description=self._truncate(self._clean_html(item.get("description", ""))),
                    source=self.platform_name,
                )
            )
        return jobs
