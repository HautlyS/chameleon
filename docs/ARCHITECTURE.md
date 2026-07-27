# Chameleon Architecture

Chameleon is organized as a layered system with three user-facing interfaces, a Python backend, and AI assistant integration.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                             │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  ┌────────┐ │
│  │  TUI     │  │  CLI         │  │  AI Assistant     │  │  Bots  │ │
│  │ (Textual)│  │  (Python)    │  │  (Claude/Codex/OC)│  │TG/WA   │ │
│  └────┬─────┘  └──────┬───────┘  └───────┬──────────┘  └───┬────┘ │
└───────┼───────────────┼──────────────────┼──────────────────┼──────┘
        │               │                     │
┌───────┴───────────────┴─────────────────────┴──────────────┐
│                   SCRIPTS LAYER                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  tui/app.py        tui/screens.py   tui/widgets.py   │  │
│  │  tui/helpers.py    tui_app.py                        │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  tailor_cv.py      tailor_brief.py  tailor_prompts.py│  │
│  │  job_matcher.py    ats_ghost.py     render.py        │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  config.py         db.py            cache.py         │  │
│  │  fonts.py                                           │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  job_scanner/ (scanner.py, base.py, registry.py,    │  │
│  │    cli.py, parsers/ (18 platforms))                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
        │               │                     │
┌───────┴───────────────┴─────────────────────┴──────────────┐
│                   STORAGE LAYER                             │
│  ┌──────────┐  ┌───────────┐  ┌────────┐  ┌─────────────┐ │
│  │ config   │  │ SQLite    │  │ YAML   │  │ output/     │ │
│  │ .chameleon│  │ jobs.db   │  │templates│  │ PDFs, HTML  │ │
│  │ config.json│  │            │  │ CVs    │  │ analyses    │ │
│  └──────────┘  └───────────┘  └────────┘  └─────────────┘ │
└────────────────────────────────────────────────────────────┘
```

## Component Overview

### User Interfaces

| Interface | Technology | Entry Point | Purpose |
|-----------|-----------|-------------|---------|
| **TUI** | Textual (Python) | `scripts/tui/app.py` → `ChameleonTUI` | Full terminal UI: browse jobs, tailor CVs, view diffs |
| **CLI** | Python argparse | `scripts/tailor_cv.py::main()` | Headless tailoring: `python3 -m scripts.tailor_cv` |
| **AI Assistant** | Claude Code / Codex / OpenCode | `/.claude/skills/*/SKILL.md` | Slash commands: `/chameleon`, `/tailor-cv`, etc. |
| **Telegram Bot** | TypeScript (grammY) | `chameleon-bot/opencode-telegram-bot/` → `make bot-telegram-dev` | Remote tailoring + job alerts via Telegram |
| **WhatsApp Bot** | TypeScript (Express) | `chameleon-bot/whatsapp-bot/` → `make bot-whatsapp-dev` | CV management + job alerts via WhatsApp |

### Python Backend

| Module | Purpose |
|--------|---------|
| `tui/app.py` | Main Textual application — 6 tabs, background workers, keyboard bindings |
| `tui/screens.py` | Modal screens: help, paste, delete confirm, custom scan |
| `tui/widgets.py` | NanoEditor (inline text editor), SettingsPane (live config editor) |
| `tui/helpers.py` | Diff generation, score badges/bars, text truncation |
| `tailor_cv.py` | 4-pass pipeline: Brief → AI Tailor → AI Review → Render |
| `tailor_brief.py` | Algorithmic JD analysis — gaps, experience fit, repo matching |
| `tailor_prompts.py` | AI prompt templates for tailor, review, and fix passes |
| `job_matcher.py` | Dynamic scoring engine — 4-category rubric against profile + CV |
| `render.py` | RenderCV wrapper — YAML → PDF/Markdown/HTML/PNG |
| `ats_ghost.py` | Invisible keyword injection into PDF for ATS parsing |
| `config.py` | JSON-backed, thread-safe configuration singleton |
| `db.py` | SQLite store for jobs, tailored CVs, scan records |
| `cache.py` | TTL-based file cache for scan results |
| `fonts.py` | Google Fonts download and management |
| `job_scanner/` | 18-platform job scanner with registry and CLI |

### AI Integration

```
┌──────────────────────────────────────────────────────┐
│                 AI ASSISTANT INTEGRATION              │
│                                                       │
│  Convenience Layer (opencode.json / CLAUDE.md)        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  opencode.json  →  skill paths, commands, agents │ │
│  │  AGENTS.md      →  Codex project instructions    │ │
│  │  CLAUDE.md      →  Claude Code instructions      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  Skill Layer (SKILL.md files)                         │
│  ┌──────────┐ ┌───────────┐ ┌─────────┐             │ │
│  │ chameleon│ │ tailor-cv │ │score-cv │  ...         │ │
│  │ SKILL.md │ │ SKILL.md  │ │SKILL.md │             │ │
│  └────┬─────┘ └─────┬─────┘ └────┬────┘             │ │
│       │             │            │                    │ │
│  ┌────┴─────────────┴────────────┴────────────────┐  │ │
│  │  Subagents (isolated LLM contexts)              │  │ │
│  │  ┌─────────────────┐ ┌──────────────────────┐   │  │ │
│  │  │ analyze-job-     │ │ update-cv-with-job-  │   │  │ │
│  │  │ posting (haiku)  │ │ posting (sonnet)     │   │  │ │
│  │  └─────────────────┘ └──────────────────────┘   │  │ │
│  │  ┌─────────────────┐                            │  │ │
│  │  │ score-cv-match   │                            │  │ │
│  │  │ (sonnet)         │                            │  │ │
│  │  └─────────────────┘                            │  │ │
│  └────────────────────────────────────────────────┘  │ │
└──────────────────────────────────────────────────────┘
```

**Agent responsibilities:**

| Agent | Model | Input | Output |
|-------|-------|-------|--------|
| `analyze-job-posting` | Haiku | Raw JD text | Structured JSON (skills, keywords, signals) |
| `update-cv-with-job-posting` | Sonnet | Analysis JSON + master YAML path | Tailored YAML file |
| `score-cv-match` | Sonnet | Analysis JSON + CV evidence + rubric | Score + breakdown + gaps |

## Data Flow: Full Tailor Pipeline

```
User input (URL or text)
        │
        ▼
┌──────────────────┐     ┌──────────────────────┐
│  1. Fetch/Debug  │────→│  2. analyze-job-      │
│  (webfetch or    │     │     posting (subagent) │
│   direct text)   │     │  → structured JSON     │
└──────────────────┘     └──────────┬───────────┘
                                    │
                          ┌─────────▼───────────┐
                          │  3. Save analysis    │
                          │  output/job_analyses/ │
                          │  <id>__<co>__<role>.json
                          └─────────┬───────────┘
                                    │
                          ┌─────────▼───────────┐
                          │  4. Resolve source   │
                          │     CV from templates/│
                          └─────────┬───────────┘
                                    │
                          ┌─────────▼───────────┐
                          │  5. update-cv-with-  │
                          │     job-posting      │
                          │     (subagent)       │
                          │  → tailored YAML     │
                          └─────────┬───────────┘
                                    │
                          ┌─────────▼───────────┐
                          │  6. Render YAML      │
                          │  → PDF / HTML / etc. │
                          │  (make render)       │
                          └─────────┬───────────┘
                                    │
                          ┌─────────▼───────────┐
                          │  7. Report output    │
                          │  path + analysis ID  │
                          └─────────────────────┘
```

### 4-Pass Pipeline (`tailor_and_render`)

When invoked from the TUI (`Ctrl+T`), the pipeline runs in a background thread:

```
Pass 1: TailoringBrief     Algorithmic JD analysis (no AI)
   └─ seniority, experience fit, gap analysis, repo matching

Pass 2: AI Tailor          One-shot opencode `run` call
   └─ rewrites summary, reorders highlights, reorders skills
   └─ retries up to 2 times on failure

Pass 3: AI Review          Double review with tiebreaker
   └─ 2 independent opencode review calls
   └─ if scores diverge >15, third tiebreaker review
   └─ union of corrections applied via FIX_PROMPT

Pass 4: Render             rendercv → PDF
   └─ optional ATS ghost text injection
```

## Storage Layout

```
.chameleon/
├── config.json          # All user configuration (editable via Settings tab)
├── jobs.db              # SQLite: jobs, tailored CVs, scan records
├── cache/               # TTL-cached scan results
└── fonts/               # Downloaded Google Fonts

templates/
├── <name>_cv.yaml              # Master CV
├── <name>_<company>_<role>_cv.yaml  # Tailored CVs

output/
├── <cv_name>.pdf / .html / .md / .typ / .png  # Render outputs
└── job_analyses/
    └── <analysis_id>__<company>__<role>.json     # JD analysis artifacts

profiles/
└── github_repos.json   # GitHub profile data (repos, languages, tech stack)
```

## Crash Safety & Error Handling

### Subprocess Kill Registry

All subprocesses (opencode, scanner, rendercv) use `subprocess.Popen` and register themselves in a global kill registry before they start. This ensures no orphan processes are left behind on crash or shutdown.

```
            ┌─────────────────────────┐
            │  _running_processes[]   │  (module-level list, thread-safe)
            │  _processes_lock        │
            └──────────┬──────────────┘
                       │
            ┌──────────▼──────────────┐
            │  kill_all_processes()    │  kills every registered Popen
            └──────────────────────────┘
```

**TUI layer** (`scripts/tui/app.py`):
- `_subprocs[]` tracks scanner processes (app-level)
- `kill_tailor_processes()` kills tailor/rendercv processes (module-level in `tailor_cv.py`)
- `_cleanup_subprocesses()` iterates both registries, kills, waits (3s timeout), clears
- `_emergency_cleanup()` is called from three paths:
  1. `on_unmount()` — Textual lifecycle (app teardown)
  2. `atexit` — Python interpreter shutdown
  3. `_handle_sigint()` — Ctrl+C trap
- `_shutting_down` flag prevents enqueuing new log/notify calls during shutdown
- `TeeStream` checks `_real.closed` and guards against `BrokenPipeError` during write

**Tailor layer** (`scripts/tailor_cv.py`):
- `_track_process()` / `_untrack_process()` manage the global `_running_processes` list
- `kill_all_processes()` is safe to call from any thread — iterates with lock, kills, waits
- All subprocesses use `proc.communicate(timeout=N)` with explicit `proc.kill()` on timeout
- `FileNotFoundError` caught at `Popen()` call site before registration

### Real-time Stdout Capture (TeeStream)

When the tailor pipeline runs in a background thread, `print(flush=True)` calls in `tailor_and_render()` are captured by `TeeStream` and forwarded to both:

1. The real terminal stdout (for terminal debugging)
2. The TUI Scanner tab log (via `call_from_thread(self._log, ...)`)

```
Thread stdout ──→ TeeStream ──→ real terminal stdout
                         └──→ call_from_thread(self._log) → TUI Scanner tab
```

This gives the user real-time visibility into all 4 phases of the pipeline without waiting for completion.

### Crash-safe Notifications (`_crash_notify`)

The `_crash_notify()` wrapper ensures debug toasts never crash the app:

- Writes to both TUI log (`self._log`) and toast (`self.notify`)
- Maps severity levels to Textual's severity enum (`error` → `"error"`, `warning` → `"warning"`, `info` → `"information"`)
- Wrapped in `try/except Exception: pass` as last resort
- Used in: tailor failure, tailor crash (with full traceback), scan errors

### Signal Handling

| Signal | Handler | Behavior |
|--------|---------|----------|
| `SIGINT` (Ctrl+C) | `_handle_sigint` | Kills all subprocesses, restores default handler, raises `KeyboardInterrupt` |
| `SIGPIPE` | `SIG_DFL` | Default handling to avoid spurious crashes in piped CLI usage |

### Bot Integration (chameleon-bot/)

The bot stack adds two external interfaces and an RSS job scanner:

```
chameleon-bot/
├── bridge/              # Python bridge layer (shared by both bots)
│   ├── chameleon_client.py   # Wraps chameleon scripts for programmatic access
│   ├── rss_scanner.py        # Periodic job scanning + notification dispatch
│   ├── telegram_dispatcher.py # Sends messages to Telegram Bot API
│   ├── whatsapp_dispatcher.py # Sends messages via Evolution API
│   ├── orchestrator.py       # Ties everything together
│   └── config.py             # Bridge-specific configuration
├── opencode-telegram-bot/  # Telegram bot (TypeScript, grammY)
│   └── → OpenCode SDK → chameleon skills
├── whatsapp-bot/           # WhatsApp bot (TypeScript, Express)
│   └── → Evolution API webhooks → Python bridge → chameleon scripts
├── run_bridge.py           # Entry point for RSS scanner daemon
├── docker-compose.yaml     # Full bot stack deployment
└── Dockerfile.bridge       # Bridge container
```

Data flow:

```
Telegram User
  → Telegram Bot (grammY)
  → OpenCode SDK → OpenCode Server
  → chameleon skills (/chameleon, /tailor-cv, etc.)
  → tailored CV in templates/

WhatsApp User
  → Evolution API
  → WhatsApp Bot webhook (Express)
  → Python Bridge (subprocess chameleon scripts)
  → tailored CV in templates/

RSS Scanner (periodic)
  → chameleon job_scanner (18 platforms)
  → score via job_matcher
  → TelegramDispatcher → Telegram notification
  → WhatsAppDispatcher → WhatsApp notification
```

## Config Reference

All config lives in `.chameleon/config.json`. Editable live via the Settings tab.

| Key | Default | Description |
|-----|---------|-------------|
| `master_cv_path` | `templates/tupa_cv.yaml` | Path to master CV YAML |
| `profile_path` | `profiles/github_repos.json` | GitHub profile JSON |
| `opencode_bin_path` | `~/.opencode/bin/opencode` | Path to opencode binary |
| `scan_queries` | `["python", "rust", "ai engineer"]` | Default scan queries |
| `scan_platforms` | `"remoteok,remotive,hn_hiring"` | Default platforms |
| `score_weight_*` | `25` each | Category weights (total 100) |
| `ats_ghost_enabled` | `false` | Toggle invisible keyword injection |
| `cv_font_family` | `"Source Sans Pro"` | Font for rendered PDF |
| `cv_line_spacing` | `"0.8em"` | Line spacing for compact layout |
