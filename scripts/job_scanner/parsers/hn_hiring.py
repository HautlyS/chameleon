"""HN Hiring (Who Is Hiring) — Algolia API, no auth required."""

from __future__ import annotations

import re

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class HNHiringParser(BaseParser):
    platform_name = "hn_hiring"
    ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
    ITEMS_URL = "https://hn.algolia.com/api/v1/items"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        # Find the latest "Ask HN: Who is hiring?" thread
        resp = self._http_get(
            self.ALGOLIA_URL,
            params={"tags": "story", "query": "Ask HN Who is hiring"},
        )
        if resp is None:
            return []

        try:
            hits = resp.json().get("hits", [])
        except Exception:
            return []

        # Find the actual "Ask HN: Who is hiring?" thread
        thread_id = None
        for hit in hits:
            title = hit.get("title", "")
            lower = title.lower()
            if "ask hn" in lower and "who is hiring?" in lower and "(" in title:
                thread_id = hit.get("objectID")
                break

        if not thread_id:
            return []

        # Fetch thread comments
        resp = self._http_get(f"{self.ITEMS_URL}/{thread_id}")
        if resp is None:
            return []

        try:
            thread = resp.json()
        except Exception:
            return []

        comments = thread.get("children", [])

        jobs = []
        for comment in comments:
            text = comment.get("text", "")
            if not text or comment.get("dead") or comment.get("deleted"):
                continue

            clean = self._clean_html(text)
            lines = clean.split("\n")
            header = lines[0] if lines else ""

            parts = [p.strip() for p in header.split("|")]
            company = parts[0] if parts else ""
            title = parts[1] if len(parts) > 1 else ""
            location = parts[2] if len(parts) > 2 else ""

            if query and query.lower() not in clean.lower():
                continue

            url = f"https://news.ycombinator.com/item?id={comment.get('id', '')}"

            jobs.append(
                JobListing(
                    title=title or "See posting",
                    company=company,
                    url=url,
                    location=location,
                    remote="remote" in clean.lower(),
                    tags=[],
                    posted_at=thread.get("time", ""),
                    description=self._truncate(clean),
                    source=self.platform_name,
                    job_id=str(comment.get("id", "")),
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
