"""Adzuna — structured job API with salary data. Tier 1 (free tier).

Requires ADZUNA_APP_ID and ADZUNA_API_KEY env vars. Falls back gracefully.
"""
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
class AdzunaParser(BaseParser):
    platform_name = "adzuna"

    def fetch_jobs(self, query: str = "", **kwargs: Any) -> list[JobListing]:
        app_id = os.environ.get("ADZUNA_APP_ID")
        api_key = os.environ.get("ADZUNA_API_KEY")
        if not app_id or not api_key:
            return []

        country = kwargs.get("country", "gb")
        params = {
            "app_id": app_id,
            "app_key": api_key,
            "results_per_page": str(min(kwargs.get("limit", 25), 50)),
            "content_type": "application/json",
        }
        if query:
            params["what"] = query
        params["where"] = kwargs.get("location", "")

        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Chameleon/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return []

        jobs: list[JobListing] = []
        for j in data.get("results", [])[:kwargs.get("limit", 25)]:
            title = (j.get("title") or "").strip()
            company = (j.get("company", {}) or {}).get("display_name") or "Unknown"
            url = j.get("redirect_url") or j.get("url") or ""
            desc = (j.get("description") or "")[:2000]
            location = j.get("location", {}).get("display_name") or j.get("location") or ""
            salary_min = j.get("salary_min") or j.get("salary_minimum")
            salary_max = j.get("salary_max") or j.get("salary_maximum")
            salary = ""
            if salary_min and salary_max:
                salary = f"${int(salary_min):,} - ${int(salary_max):,}"
            elif salary_min:
                salary = f"${int(salary_min):,}+"
            remote = False
            if desc and ("remote" in desc.lower() or "anywhere" in desc.lower()):
                remote = True
            if location and ("remote" in location.lower()):
                remote = True

            job_id = j.get("id") or f"adzuna-{hash(title + company)}"
            jobs.append(JobListing(
                job_id=f"adz-{job_id}",
                title=title,
                company=company,
                url=url,
                location=location,
                description=desc,
                salary=salary,
                source=self.platform_name,
                remote=remote,
                tags=[],
            ))
        return jobs
