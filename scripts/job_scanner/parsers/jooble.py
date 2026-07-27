"""Jooble — job aggregator with structured API. Tier 1 (free tier key).

Requires JOOBLE_API_KEY env var. Falls back gracefully.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class JoobleParser(BaseParser):
    platform_name = "jooble"

    def fetch_jobs(self, query: str = "", **kwargs: Any) -> list[JobListing]:
        api_key = os.environ.get("JOOBLE_API_KEY")
        if not api_key:
            return []

        url = f"https://jooble.org/api/{api_key}"
        payload = {"keywords": query or "software engineer", "page": 1}
        if kwargs.get("location"):
            payload["location"] = kwargs["location"]

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Chameleon/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return []

        jobs: list[JobListing] = []
        for j in data.get("jobs", [])[:kwargs.get("limit", 25)]:
            title = (j.get("title") or "").strip()
            company = (j.get("company") or "Unknown").strip()
            url = j.get("link") or j.get("url") or ""
            desc = (j.get("snippet") or j.get("description") or "")[:2000]
            location = j.get("location") or ""
            salary = j.get("salary") or ""
            remote = "remote" in str(location).lower() or "anywhere" in str(desc).lower()

            job_id = j.get("id") or f"jooble-{hash(title + company)}"
            jobs.append(JobListing(
                job_id=f"job-{job_id}",
                title=title,
                company=company,
                url=url,
                location=location,
                description=desc,
                salary=str(salary),
                source=self.platform_name,
                remote=remote,
                tags=[],
            ))
        return jobs
