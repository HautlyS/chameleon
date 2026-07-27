"""Remote OK — free JSON API + RSS, no auth required."""

from __future__ import annotations

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class RemoteOKParser(BaseParser):
    platform_name = "remoteok"
    API_URL = "https://remoteok.com/api"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        url = self.API_URL
        if tags:
            url += "?tag=" + tags[0]

        resp = self._http_get(url)
        if resp is None:
            return []

        try:
            items = resp.json()
        except Exception:
            return []

        # First item is metadata
        if items and isinstance(items[0], dict) and "legal" in str(items[0]):
            items = items[1:]

        q = query.lower() if query else ""
        jobs = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("position", "")
            company = item.get("company", "")
            job_tags = item.get("tags", [])
            desc = item.get("description", "")
            searchable = f"{title} {company} {' '.join(job_tags)} {desc}".lower()
            if q and q not in searchable:
                continue
            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    url=item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id', '')}"),
                    location=item.get("location", "Remote"),
                    remote=True,
                    tags=item.get("tags", []),
                    salary=item.get("salary", ""),
                    posted_at=item.get("date", ""),
                    description=self._truncate(item.get("description", "")),
                    source=self.platform_name,
                    job_id=str(item.get("id", "")),
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
