"""We Work Remotely — RSS feed, no auth required."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class WeWorkRemotelyParser(BaseParser):
    platform_name = "weworkremotely"
    RSS_URL = "https://weworkremotely.com/remote-jobs.rss"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        resp = self._http_get(self.RSS_URL)
        if resp is None:
            return []

        try:
            root = ET.fromstring(resp.text)
        except Exception:
            return []

        jobs = []
        for item in root.findall(".//item")[:limit * 2]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            desc = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")

            if query and query.lower() not in f"{title} {desc}".lower():
                continue

            company = ""
            if ":" in title:
                parts = title.split(":", 1)
                company = parts[0].strip()
                title = parts[1].strip()

            jobs.append(
                JobListing(
                    title=title,
                    company=company,
                    url=link,
                    location="Remote",
                    remote=True,
                    tags=[],
                    posted_at=pub_date,
                    description=self._truncate(self._clean_html(desc)),
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
