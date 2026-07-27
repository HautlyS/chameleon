#!/usr/bin/env python3
"""
Chameleon Job Scanner — search jobs across 20 platforms.

Usage:
    python -m scripts.job_scanner --query "python engineer" --platforms himalayas,remoteok,remotive
    python -m scripts.job_scanner --query "rust" --all --limit 10
    python -m scripts.job_scanner --list-platforms
    echo "python" | python -m scripts.job_scanner --stdin
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure the project root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.job_scanner.registry import get_all_parsers, list_platforms, get_parser
from scripts.job_scanner.base import JobListing

# All supported platforms
ALL_PLATFORMS = [
    # Tier 1 — Direct API/RSS (most reliable)
    "himalayas", "remoteok", "remotive", "weworkremotely", "hn_hiring",
    "jobicy", "adzuna", "jooble",
    # Tier 2 — Scraping (moderate)
    "arc", "crypto_careers", "dailyremote", "relocate", "web3_career",
    "ycomb",
    # Tier 3 — Hard (anti-bot, limited)
    "linkedin", "indeed", "wellfound", "flexjobs", "remote_rocketship",
    # Tier 4 — API key required
    "opentoworkremote",
]

TIER_1 = ["himalayas", "remoteok", "remotive", "weworkremotely", "hn_hiring", "jobicy", "adzuna", "jooble"]
TIER_2 = ["arc", "crypto_careers", "dailyremote", "relocate", "web3_career", "ycomb"]


def scan_jobs(
    query: str = "",
    platforms: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 25,
    use_tier1_only: bool = False,
    **kwargs,
) -> list[JobListing]:
    """Scan jobs across specified platforms and return unified listings."""
    if platforms is None:
        platforms = TIER_1 if use_tier1_only else ALL_PLATFORMS

    all_jobs: list[JobListing] = []
    seen_ids: set[str] = set()
    errors: list[str] = []

    for platform_name in platforms:
        parser_cls = get_parser(platform_name)
        if parser_cls is None:
            print(f"[warn] Unknown platform: {platform_name}", file=sys.stderr)
            continue

        parser = parser_cls()
        try:
            jobs = parser.fetch_jobs(query=query, tags=tags, limit=limit, **kwargs)
            for job in jobs:
                if job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    all_jobs.append(job)
        except Exception as e:
            errors.append(f"{platform_name}: {e}")
            print(f"[error] {platform_name}: {e}", file=sys.stderr)

    if errors:
        print(f"\n[info] {len(errors)} platform(s) had errors", file=sys.stderr)

    return all_jobs


def main():
    ap = argparse.ArgumentParser(description="Chameleon Job Scanner")
    ap.add_argument("--query", "-q", default="", help="Search query (keywords, role)")
    ap.add_argument("--platforms", "-p", default="", help="Comma-separated platform names")
    ap.add_argument("--all", "-a", action="store_true", help="Scan all platforms")
    ap.add_argument("--tier1", action="store_true", help="Scan only Tier 1 (API/RSS) platforms")
    ap.add_argument("--limit", "-n", type=int, default=25, help="Max jobs per platform")
    ap.add_argument("--tags", "-t", default="", help="Comma-separated tags to filter")
    ap.add_argument("--output", "-o", default="", help="Output JSON file path")
    ap.add_argument("--list-platforms", "-l", action="store_true", help="List all available platforms")
    ap.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = ap.parse_args()

    if args.list_platforms:
        for p in list_platforms():
            tier = "T1" if p in TIER_1 else "T2" if p in TIER_2 else "T3/T4"
            print(f"  [{tier:4s}] {p}")
        print(f"\n  Total: {len(list_platforms())} platforms")
        return

    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
    elif args.all:
        platforms = ALL_PLATFORMS
    elif args.tier1:
        platforms = TIER_1

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    start = time.time()
    jobs = scan_jobs(
        query=args.query,
        platforms=platforms,
        tags=tags,
        limit=args.limit,
    )
    elapsed = time.time() - start

    if args.json or args.output:
        data = [j.to_dict() for j in jobs]
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(data, indent=2))
            print(f"Saved {len(data)} jobs to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(data, indent=2))
    else:
        # Pretty table output
        if not jobs:
            print("No jobs found.")
            return

        print(f"\n{'='*80}")
        print(f" CHAMELEON JOB SCANNER — {len(jobs)} results ({elapsed:.1f}s)")
        print(f"{'='*80}\n")

        for i, job in enumerate(jobs, 1):
            tags_str = ", ".join(job.tags[:5]) if job.tags else ""
            remote_tag = " [R]" if job.remote else ""
            salary_tag = f" ${job.salary}" if job.salary else ""
            print(f"  {i:2}. [{job.source}]{remote_tag}{salary_tag} {job.title}")
            print(f"      Company: {job.company}")
            if job.location:
                print(f"      Location: {job.location}")
            if tags_str:
                print(f"      Tags: {tags_str}")
            print(f"      URL: {job.url}")
            print()

        print(f"{'='*80}")
        src_count = len(set(j.source for j in jobs))
        print(f" Total: {len(jobs)} jobs from {src_count} platforms ({elapsed:.1f}s)")
        print(f"{'='*80}")


if __name__ == "__main__":
    main()
