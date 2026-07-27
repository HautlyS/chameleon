"""Arc.dev — parser for remote dev jobs via __NEXT_DATA__."""
from __future__ import annotations

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class ArcParser(BaseParser):
    platform_name = "arc"
    BASE_URL = "https://arc.dev/remote-jobs"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        url = self.BASE_URL
        if query:
            slug = query.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/{slug}"

        resp = self._http_get(url)
        if resp is None:
            return []

        data = self._extract_next_data(resp.text)
        if data is None:
            return []

        page_props = data.get("props", {}).get("pageProps", {})
        jobs = []

        for source_key in ("arcJobs", "externalJobs"):
            items = page_props.get(source_key, [])
            for item in items[:limit]:
                company = item.get("company", {})
                if isinstance(company, dict):
                    company_name = company.get("name", "")
                else:
                    company_name = str(company) if company else ""

                job_title = item.get("title", "") or ""
                url_str = item.get("urlString", "")
                job_url = f"https://arc.dev/remote-jobs/{url_str}" if url_str else ""

                categories = item.get("categories", [])
                tags_list = [c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in categories]

                jobs.append(
                    JobListing(
                        title=job_title,
                        company=company_name,
                        url=job_url,
                        location="Remote",
                        remote=True,
                        tags=tags_list,
                        posted_at=item.get("postedAt", ""),
                        source=self.platform_name,
                    )
                )
                if len(jobs) >= limit:
                    break
            if len(jobs) >= limit:
                break

        return jobs
