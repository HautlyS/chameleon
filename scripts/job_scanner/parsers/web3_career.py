"""Web3 Career — parser for web3/blockchain jobs via JSON-LD."""
from __future__ import annotations

from ..base import BaseParser, JobListing
from ..registry import register_parser


@register_parser
class Web3CareerParser(BaseParser):
    platform_name = "web3_career"
    BASE_URL = "https://web3.career"

    def fetch_jobs(
        self, query: str = "", tags: list[str] | None = None, limit: int = 25, **kwargs
    ) -> list[JobListing]:
        url = f"{self.BASE_URL}/web3-jobs"
        if query:
            slug = query.lower().replace(" ", "+")
            url = f"{self.BASE_URL}/{slug}+crypto-jobs"

        resp = self._http_get(url)
        if resp is None:
            return []

        ld = self._extract_json_ld(resp.text)
        jobs = []
        seen = set()

        for entry in ld:
            if entry.get("@type") != "JobPosting":
                continue
            title = (entry.get("title", "") or "").strip()
            company = entry.get("hiringOrganization", {})
            if isinstance(company, dict):
                company_name = (company.get("name", "") or "").strip()
            else:
                company_name = str(company).strip() if company else ""
            # Skip artist/portfolio entries mislabeled as JobPosting
            if company_name.lower() in ("nftphotographers.xyz",) or not company_name:
                continue
            if not title or len(title) < 5:
                continue

            direct_apply = entry.get("directApply", entry.get("url", ""))
            if isinstance(direct_apply, dict):
                direct_apply = direct_apply.get("url", "")
            if not direct_apply:
                direct_apply = entry.get("url", "")

            desc = self._clean_html(entry.get("description", ""))
            location = entry.get("jobLocation", "")
            if isinstance(location, dict):
                location = location.get("address", {}).get("addressLocality", location.get("name", "Remote"))
            if isinstance(location, dict):
                location = "Remote"

            salary = entry.get("baseSalary", {})
            salary_str = ""
            if isinstance(salary, dict):
                min_v = salary.get("value", {}).get("minValue", salary.get("value", ""))
                max_v = salary.get("value", {}).get("maxValue", "")
                if min_v and max_v:
                    salary_str = f"${min_v} - ${max_v}"
                elif min_v:
                    salary_str = f"${min_v}+"

            dedup_key = f"{title}|{company_name}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            if query and query.lower() not in f"{title} {company_name}".lower():
                continue

            job_url = direct_apply or f"{self.BASE_URL}/job/{title.lower().replace(' ', '-')}"
            jobs.append(
                JobListing(
                    title=title.strip(),
                    company=company_name.strip(),
                    url=job_url,
                    location=location if isinstance(location, str) else "Remote",
                    remote="remote" in str(location).lower() or "anywhere" in str(location).lower(),
                    tags=["web3", "crypto"],
                    description=self._truncate(desc, 500),
                    salary=salary_str,
                    source=self.platform_name,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs
