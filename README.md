# Chameleon — Resume Tailor

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![OpenCode](https://img.shields.io/badge/OpenCode-ready-blueviolet)](https://opencode.ai)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-ready-darkviolet)](https://claude.ai)
[![Codex](https://img.shields.io/badge/Codex-ready-black)](https://openai.com/codex)

Tailor your master resume to any job posting with AI. Produces ATS-optimized PDFs without inventing experience. Works as a **TUI**, **CLI**, or via **AI assistant** (OpenCode / Claude Code / Codex).

---

## Why Chameleon?

| Problem | Chameleon |
|---------|-----------|
| Generic resume rejected by ATS | Tailored keywords + **invisible ATS injection** |
| Fabricated skills get caught | **Strict no-fabrication** rules enforced by AI and code |
| Lost track of applications | **Persistent analysis** — JSON artifacts saved for reuse |
| Manual tailoring takes hours | **4-pass pipeline** runs in under 2 minutes |
| No feedback loop | **Score every CV** against the JD with category breakdowns |
| Scattered job platforms | **20-platform scanner** with API, RSS, and scraping |

---

## Quick Start

### Prerequisites

- Python 3.10+
- An AI assistant binary: [OpenCode](https://opencode.ai), [Claude Code](https://claude.ai/claude-code), or [Codex CLI](https://openai.com/codex)

### Install

```bash
git clone https://github.com/davidalecrim1/chameleon.git
cd chameleon
make install-tools          # creates .venv + installs rendercv
```

### Makefile Targets

| Target | Usage | Description |
|--------|-------|-------------|
| `install-tools` | `make install-tools` | Create `.venv`, install `rendercv[full]` |
| `render` | `make render FILE=<yaml>` | Render a CV YAML to PDF |
| `tailor` | `make tailor JD=<text> COMPANY=<name>` | Tailor CV for a job posting |
| `score` | `make score JD=<text>` | Score job match against profile |
| `scan` | `make scan QUERY=<query>` | Scan job platforms |
| `scan-all` | `make scan-all` | Scan all 20 platforms |
| `scan-tier1` | `make scan-tier1` | Scan Tier 1 platforms only |
| `list-platforms` | `make list-platforms` | List available scanner platforms |

---

## Three Ways to Use

### 1. TUI — Full Terminal UI

```bash
./tui.sh
```

Browse scored jobs from 20 platforms, tailor with `Ctrl+T`, view diffs between master and tailored YAML, and edit config live — all in the terminal.

**6 Tabs:**

| Tab | Shortcut | Shows |
|-----|----------|-------|
| **Jobs** | `Ctrl+1` | Scanned/pasted jobs with scores, gap analysis, experience fit |
| **Editor** | `Ctrl+2` | Inline nano-style editor for job descriptions |
| **Profile** | `Ctrl+3` | GitHub profile (languages, tech stack, matching repos) |
| **Scanner** | `Ctrl+4` | Live pipeline logs — scan progress, tailor phases, render status |
| **Tailored** | `Ctrl+5` | Tailored CVs with diff view, scores, PDF links |
| **Settings** | `Ctrl+6` | Live config editor — paths, scan queries, score weights, fonts, colors |

**Keybindings:**

| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit (with confirmation) |
| `Ctrl+S` | Scan job platforms |
| `Ctrl+Shift+S` / `F2` | Custom scan with platform/query options |
| `Ctrl+N` | Paste a job description |
| `Ctrl+E` | Edit selected job description |
| `Ctrl+T` | Tailor CV for selected job |
| `Ctrl+R` | Re-score all jobs |
| `Ctrl+D` | Delete selected job |
| `Ctrl+O` | Open job URL in browser |
| `Enter` | Show job detail or tailored CV diff |
| `/` | Focus search bar |
| `F1` | Help screen |
| `F5` | Refresh / re-score |
| `↑/↓` | Navigate rows |

Full reference: [docs/TUI.md](docs/TUI.md)

---

### 2. AI Assistant — Slash Commands

```bash
opencode     # or claude, or codex
```

| Command | What it does |
|---------|-------------|
| `/init-cv <path>` | Import master CV from PDF or YAML |
| `/chameleon <url-or-text>` | Full pipeline: analyze → tailor → render |
| `/tailor-cv --analysis <id> --cv <name>` | Tailor from saved analysis |
| `/score-cv --analysis <id> --cv <path>` | Score against analysis |
| `/cover-letter <url-or-text>` | Generate cover letter |
| `/question "<text>"` | Answer screening question |
| `/render-cv [file]` | Re-render a YAML to PDF |
| `/scan-jobs [--query]` | Scan job platforms |
| `/job-matcher score --job-url <url>` | Score job against your profile |

---

### 3. CLI — Headless / Scripting

```bash
# ── Unified CLI (recommended) ──────────────────────────────────────────

# Tailor a CV from text
./chameleon tailor "Senior Rust Engineer at Acme Corp..." --company Acme

# Tailor from a URL (auto-crawls the job posting)
./chameleon tailor https://jobs.example.com/senior-rust-engineer

# Tailor from a file
./chameleon tailor jd.txt --company Acme --title "Rust Engineer"

# Pipe a job description via stdin
cat jd.txt | ./chameleon tailor --company Acme

# Score a job match against your profile
./chameleon score "Python developer, Django, PostgreSQL..."
./chameleon score https://jobs.example.com/python-dev --json

# Scan job platforms
./chameleon scan -q "rust engineer" --tier1
./chameleon scan -q "python" -p remoteok,remotive --json
./chameleon scan --all --limit 10 -o output/scans/results.json

# Render a YAML to PDF
./chameleon render templates/david_acme_rust_engineer_cv.yaml

# ── Windows ─────────────────────────────────────────────────────────────
chameleon.bat tailor "Senior Rust Engineer..." --company Acme
chameleon.bat score "Python developer..."
chameleon.bat scan -q "rust engineer" --tier1

# ── Direct Python modules (alternative) ─────────────────────────────────

# Tailor a CV directly
python3 -m scripts.tailor_cv "Senior Rust Engineer at Acme..." --company Acme --title Engineer

# Score a job against your profile
python3 -m scripts.job_matcher "Python developer..." --json

# Scan job platforms
python3 -m scripts.job_scanner.scanner --query "rust engineer" --platforms remoteok,hn_hiring --json

# Render a YAML
make render FILE=templates/david_acme_rust_engineer_cv.yaml

# ── Make targets ────────────────────────────────────────────────────────

make tailor JD="Senior Rust Engineer..." COMPANY=Acme
make score JD="Python developer..."
make scan QUERY="rust engineer" PLATFORMS=remoteok,hn_hiring
make scan-all QUERY="python"
make scan-tier1
make list-platforms
```

---

## Example Workflow

```bash
# 1. Import your master CV
/init-cv ~/Documents/resume.pdf
# → templates/david_cv.yaml

# 2. Tailor for a job posting
/chameleon https://jobs.example.com/senior-engineer-123
# → Analysis:      output/job_analyses/a7c19f2d__Acme__Rust_Engineer.json
# → Tailored YAML: templates/david_acme_rust_engineer_cv.yaml
# → PDF:           output/david_acme_rust_engineer_cv.pdf

# 3. Score the result against the same analysis
/score-cv --analysis a7c19f2d --cv templates/david_acme_rust_engineer_cv.yaml
# → Score: 85/100 (Languages: 22, Frameworks: 20, Domains: 23, CV Alignment: 20)
```

---

## How It Works

### 4-Pass Pipeline

When you invoke a tailor (`Ctrl+T` or `/chameleon`), the pipeline runs in 4 passes:

```
Pass 1: TailoringBrief     Algorithmic JD analysis — seniority, gaps, repo matching
Pass 2: AI Tailor          LLM rewrites summary, reorders highlights/skills
Pass 3: AI Review          Double review with tiebreaker, applies corrections
Pass 4: Render             rendercv → PDF (+ optional ATS ghost injection)
```

### ATS Ghost Injection

When `ats_ghost_enabled` is on, the PDF is post-processed to inject invisible keyword text (`font-size: 1px, color: white`) at the bottom of every page. This ensures ATS parsers see important keywords even if the layout is unusual. Extra terms can be configured in Settings.

---

## Project Layout

```
.chameleon/              Config JSON, SQLite DB, fonts, cache
.claude/                 AI skills + agents (OpenCode / Claude Code)
.agents/                 AI skills + agents (Codex)
opencode.json            OpenCode project config (12 commands, permissions)
templates/               Master + tailored CV YAMLs
output/                  Rendered PDFs, job analysis JSONs
profiles/                GitHub profile data
chameleon.sh             CLI entry point (Unix/Mac)
chameleon.bat            CLI entry point (Windows)
scan.sh / scan.bat       Quick scanner wrapper
score.sh / score.bat     Quick scorer wrapper
tui.sh / tui.bat         TUI launcher
scripts/
  tui/                   Textual TUI (6 tabs, 19 keybindings)
  job_scanner/           20-platform job scanner
  tailor_cv.py           4-pass pipeline entry point
  tailor_brief.py        Algorithmic JD analysis
  tailor_prompts.py      AI prompt templates
  job_matcher.py         Scoring engine (4-category rubric)
  config.py              JSON-backed configuration
  db.py                  SQLite persistence
  render.py              RenderCV wrapper
  ats_ghost.py           Invisible ATS keyword injection
docs/
  ARCHITECTURE.md        Component architecture, data flow, config ref
  TUI.md                 Full TUI keybinding and tab reference
```

---

## Configuration

All settings live in `.chameleon/config.json`. Editable live via the Settings tab.

| Category | Key | Default | Description |
|----------|-----|---------|-------------|
| **Paths** | `master_cv_path` | `templates/tupa_cv.yaml` | Master CV YAML |
| | `profile_path` | `profiles/github_repos.json` | GitHub profile JSON |
| | `opencode_bin_path` | `~/.opencode/bin/opencode` | Path to opencode binary |
| **Scan** | `scan_queries` | `["python", "rust", "ai engineer"]` | Default scan queries |
| | `scan_platforms` | `"remoteok,remotive,hn_hiring"` | Default platforms |
| **Scoring** | `score_weight_*` | `25` each | Category weights (total 100) |
| | `score_threshold_strong` | `80` | Minimum score for "strong match" |
| | `score_threshold_good` | `60` | Minimum score for "good match" |
| | `score_threshold_moderate` | `40` | Minimum score for "moderate match" |
| **CV Design** | `cv_font_family` | `"Source Sans Pro"` | Font for rendered PDF |
| | `cv_font_size_body` | `9.5pt` | Body font size |
| | `cv_line_spacing` | `0.8em` | Line spacing |
| | `cv_entry_spacing` | `0.2cm` | Space between entries |
| | `cv_primary_color` | `#2b3a67` | Primary accent color |
| | `cv_secondary_color` | `#3a5a8c` | Secondary accent color |
| | `cv_page_margin_*` | `1.0-1.5cm` | Page margins |
| **ATS** | `ats_ghost_enabled` | `true` | Invisible keyword injection |
| | `ats_ghost_extra_terms` | `"django, flutter, ..."` | Extra ATS keywords |
| | `ats_ghost_font_size` | `1` | Font size for ghost text (px) |
| | `ats_ghost_color` | `#ffffff` | Font color for ghost text |

---

## Constraints

- **Never fabricate** experience, skills, metrics, titles, or dates
- **Preserve all facts** — company names, titles, locations, dates are immutable
- **Never edit the master CV** — always write a new file to `templates/`
- **Match JD language** — if the JD says "CI/CD" and your CV says "continuous integration", use "CI/CD"
- **2 pages max** — drop lower-impact bullets before adding new ones

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Ctrl+T` does nothing | No job selected | Select a row in the Jobs tab first |
| Tailor hangs / never completes | opencode binary not found | Set `opencode_bin_path` in Settings tab |
| Tailor hangs / never completes | opencode timeout (180s default) | Wait — long prompts take time; check Scanner tab for progress |
| `make render` fails | RenderCV not installed | Run `make install-tools` |
| Scan returns no results | Platform parser needs update | Try `--platforms hn_hiring` (most stable parser) |
| Tailored tab is empty | Tailor never succeeded | Check Scanner tab for error messages |
| `Ctrl+T` says "already in progress" | Previous tailor still running | Wait for completion or restart the TUI |
| PDF has no content / blank | Incompatible YAML schema | Run `/init-cv` on your master CV to normalize |
| AI assistant command not found | Skill not loaded | Check `opencode.json` has `.claude/skills` in `skills` array |
| ATS ghost not working | Feature disabled | Enable `ats_ghost_enabled` in Settings tab |
| Job URLs not opening | No `open`/`xdg-open` on system | Install `xdg-utils` (Linux) or check OS path |

---

## Architecture

```
┌──────────┐  ┌──────────┐  ┌──────────────────┐
│   TUI    │  │   CLI    │  │  AI Assistant     │
│ (Textual)│  │ (Python) │  │ (Claude/Codex/OC) │
└────┬─────┘  └────┬─────┘  └────────┬─────────┘
     │             │                  │
┌────┴─────────────┴──────────────────┴──────────┐
│              Python Backend                      │
│  tailor_cv.py  tailor_brief.py  job_matcher.py   │
│  config.py     db.py            render.py         │
│  job_scanner/  ats_ghost.py                      │
└──────────────────────────────────────────────────┘
     │             │                  │
┌────┴─────────────┴──────────────────┴──────────┐
│              Storage                             │
│  .chameleon/   templates/   output/   profiles/  │
└──────────────────────────────────────────────────┘
```

Key design decisions:
- **Layered architecture** — interfaces never touch storage directly
- **Subprocess kill registry** — no orphan processes on crash
- **TeeStream** — stdout from background threads appears in TUI log in real time
- **Crash-safe notifications** — debug toasts never throw, even during shutdown

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full detail.

---

## OpenCode Integration

This project provides `opencode.json` at the root — OpenCode auto-loads it on open:

- **12 slash commands** registered with usage hints (`/chameleon`, `/tailor-cv`, `/score-cv`, etc.)
- **Skill paths**: `.claude/skills/` and `.agents/skills/` scanned for `SKILL.md` definitions
- **All standard tools** pre-authorized (read, edit, bash, glob, grep, task, webfetch, websearch, question, skill)
- **Batch tool** enabled for parallel operations
- **Instructions**: `AGENTS.md` loaded as project context

For Claude Code: `CLAUDE.md` (synced copy of AGENTS.md) is auto-loaded on open.

---

## License

MIT — see [LICENSE](LICENSE).
