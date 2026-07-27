---
name: scan-jobs
description: >
  Scan job listings across 20 platforms (Adzuna, Arc, Crypto Careers,
  DailyRemote, FlexJobs, Himalayas, HN Hiring, Indeed, Jobicy, Jooble,
  LinkedIn, OpenToWorkRemote, Relocate.me, Remote OK, Remote Rocketship,
  Remotive, Web3 Career, Wellfound, We Work Remotely, Y Combinator Startup Jobs).
  Returns a unified list of matching job postings from a single or multiple
  platforms. Use when the user wants to find or search for jobs, or wants to
  discover openings before tailoring a CV.
disable-model-invocation: true
---

# /scan-jobs

Scan job listings across 20 platforms and return a unified, deduplicated list.

## Usage

```
/scan-jobs <query> [--platforms <p1,p2,...>] [--limit <n>] [--all] [--tier1] [--json]
```

Examples:
- `/scan-jobs "rust engineer"`
- `/scan-jobs "python" --platforms himalayas,remotive,remoteok --limit 10`
- `/scan-jobs "frontend react" --tier1 --limit 5`
- `/scan-jobs "web3" --all --json`

## Supported Platforms

| Tier | Platform | Method | Notes |
|------|----------|--------|-------|
| T1 | himalayas | API + RSS | Best coverage, no auth |
| T1 | remoteok | JSON API | All remote jobs, tag filter |
| T1 | remotive | JSON API | Category + search filter |
| T1 | weworkremotely | RSS | Category feeds available |
| T1 | hn_hiring | Algolia API | Who is Hiring threads |
| T1 | jobicy | JSON API | Remote jobs, salary data |
| T1 | adzuna | JSON API | Requires API key, salary data |
| T1 | jooble | JSON API | Requires API key, aggregator |
| T2 | arc | Scraping | Remote dev jobs |
| T2 | crypto_careers | Scraping | Crypto/blockchain |
| T2 | dailyremote | Scraping | Remote jobs aggregator |
| T2 | relocate | Scraping | Relocation-friendly |
| T2 | web3_career | Scraping | Web3/blockchain |
| T2 | ycomb | Scraping | YC startup jobs |
| T3 | linkedin | Guest API | Risk of rate-limit |
| T3 | indeed | Scraping | Heavy anti-bot |
| T3 | wellfound | Scraping | Heavy JS rendering |
| T3 | flexjobs | Scraping | Membership required |
| T3 | remote_rocketship | Scraping | Remote aggregator |
| T4 | opentoworkremote | RapidAPI | Requires API key |

## Workflow

### Step 1 — Parse arguments

Extract:
- `query`: the search keywords (role, skills, technologies)
- `platforms`: comma-separated list of platform names (optional)
- `limit`: max results per platform (default 25)
- `--all`: scan all 20 platforms
- `--tier1`: scan only Tier 1 (API/RSS, most reliable)
- `--json`: output as JSON

If no platforms are specified and `--all` is not set, default to Tier 1 platforms (himalayas, remoteok, remotive, weworkremotely, hn_hiring, jobicy, adzuna, jooble).

### Step 2 — Run the scanner

Execute the scanner CLI:

```bash
./chameleon scan --query "<query>" --limit <n> [--platforms <p1,p2>] [--all] [--tier1]
```

Or directly:
```bash
python3 -m scripts.job_scanner.scanner --query "<query>" --limit <n> [--platforms <p1,p2>] [--all] [--tier1]
```

Run from the project root.

### Step 3 — Present results

Format and present the results as a numbered list:

```
Scanned <N> platforms — <M> unique jobs found

 1. [platform] Job Title
    Company: Company Name
    Location: Remote / City, Country
    Tags: tag1, tag2
    URL: https://...

 2. ...
```

Group by platform if multiple were scanned. Highlight remote-friendly listings.

### Step 4 — Optional: Auto-tailor

If the user says "apply" or "tailor all" or "generate CVs for these", offer to run `/chameleon` for each listed job. Ask for confirmation before batch-tailoring.

For batch mode, use `/chameleon --batch <job-url-1> <job-url-2> ...` to process multiple jobs.

## Error Handling

- If a platform times out or returns an error, skip it and report which platforms failed.
- If no results are found, suggest broadening the query or trying different platforms.
- If `--all` is specified, report how many platforms succeeded vs failed.

## Output Location

When `--json` is used, results can be saved to `output/job_scans/` for later reuse:

```
output/job_scans/<timestamp>__<query>.json
```
