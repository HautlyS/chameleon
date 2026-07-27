"""Remotive — free JSON API + RSS, no auth required."""

from __future__ import annotations

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class RemotiveParser(BaseParser):
    platform_name = "remotive"
    API_URL = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        params: dict = {"limit": min(limit, 100)}
        if query:
            params["search"] = query
        category = kwargs.get("category", "")
        if category:
            params["category"] = category

        resp = self._http_get(self.API_URL, params=params)
        if resp is None:
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        jobs = []
        q = query.lower() if query else ""
        for item in data.get("jobs", []):
            if q:
                searchable = f"{item.get('title', '')} {item.get('company_name', '')} {' '.join(item.get('tags', []))}".lower()
                if q not in searchable:
                    continue
            jobs.append(
                JobListing(
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    url=item.get("url", ""),
                    location=item.get("candidate_required_location", ""),
                    remote=item.get("remote", True),
                    tags=item.get("tags", []),
                    salary=item.get("salary", ""),
                    posted_at=item.get("publication_date", ""),
                    description=self._truncate(self._clean_html(item.get("description", ""))),
                    source=self.platform_name,
                    job_id=str(item.get("id", "")),
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
