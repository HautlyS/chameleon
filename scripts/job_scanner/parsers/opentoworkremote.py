"""OpenToWorkRemote — RapidAPI aggregator (requires API key)."""

from __future__ import annotations

import httpx

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class OpenToWorkRemoteParser(BaseParser):
    platform_name = "opentoworkremote"
    API_URL = "https://remote-jobs1.p.rapidapi.com/search"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        import os
        api_key = kwargs.get("rapidapi_key") or os.environ.get("RAPIDAPI_KEY", "")
        if not api_key:
            return []

        params = {"title": query, "limit": limit}
        try:
            resp = httpx.get(
                self.API_URL,
                params=params,
                timeout=15,
                headers={
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": "remote-jobs1.p.rapidapi.com",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        jobs = []
        for item in data.get("jobs", data if isinstance(data, list) else [])[:limit]:
            jobs.append(
                JobListing(
                    title=item.get("title", ""),
                    company=item.get("company_name", item.get("company", "")),
                    url=item.get("url", item.get("job_url", "")),
                    location=item.get("location", "Remote"),
                    remote=True,
                    tags=item.get("tags", []),
                    source=self.platform_name,
                )
            )
        return jobs
