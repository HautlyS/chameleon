"""Jobicy — remote job board with a clean JSON API. Tier 1."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error
from typing import Any

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class JobicyParser(BaseParser):
    platform_name = "jobicy"

    def fetch_jobs(self, query: str = "", **kwargs: Any) -> list[JobListing]:
        api_url = "https://jobicy.com/api/v2/remote-jobs"
        params = []
        if query:
            params.append(f"tag={urllib.parse.quote(query)}")
        url = api_url + ("?" + "&".join(params) if params else "")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Chameleon/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return []

        jobs: list[JobListing] = []
        raw_jobs = data.get("jobs", []) if isinstance(data, dict) else data
        for j in raw_jobs[:kwargs.get("limit", 25)]:
            title = (j.get("jobTitle") or j.get("title") or "").strip()
            company = (j.get("companyName") or j.get("company") or "").strip()
            url = j.get("url") or j.get("jobURL") or ""
            desc = (j.get("jobDescription") or j.get("description") or "")[:2000]
            location = j.get("jobGeo") or j.get("location") or "Remote"
            salary = j.get("salary") or j.get("salaryRange") or ""
            remote = "remote" in str(location).lower() or "anywhere" in str(location).lower()
            tags = j.get("jobIndustry") or j.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            job_id = j.get("id") or j.get("jobId") or f"jobicy-{hash(title + company)}"
            jobs.append(JobListing(
                job_id=str(job_id),
                title=title,
                company=company,
                url=url,
                location=location,
                description=desc,
                salary=str(salary),
                source=self.platform_name,
                remote=remote,
                tags=tags if isinstance(tags, list) else [str(tags)],
            ))
        return jobs
