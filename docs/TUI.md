# Chameleon TUI — Terminal User Interface

The TUI is a full-featured terminal application built with [Textual](https://textual.textualize.io/) for managing job scans, tailoring CVs, and tracking applications — all without leaving the terminal.

## Quick Start

```bash
# Linux / macOS
./tui.sh

# Windows
tui.bat

# Or directly
python3 -m scripts.tui_app
```

## Tabs

| Tab | ID | Purpose |
|-----|----|---------|
| **Jobs** | `tab_jobs` | Browse scanned/pasted jobs with scores, details, and gap analysis |
| **Editor** | `tab_editor` | Edit raw job description text with a built-in nano-style editor |
| **Profile** | `tab_profile` | View your GitHub profile (languages, tech stack, repos) |
| **Scanner** | `tab_scanner` | See live scan progress and pipeline logs (tailor output appears here) |
| **Tailored** | `tab_tailored` | View tailored CVs with diffs, scores, and PDF links |
| **Settings** | `tab_settings` | Configure paths, scan queries, score weights, fonts, and more |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit (with confirmation) |
| `Ctrl+S` | Scan job platforms (uses configured queries) |
| `Ctrl+Shift+S` / `F2` | Custom scan with platform/query options |
| `Ctrl+N` | Paste a job description manually |
| `Ctrl+E` | Edit selected job's description |
| `Ctrl+T` | Tailor CV for the selected job |
| `Ctrl+R` | Re-score all jobs |
| `Ctrl+D` | Delete selected job (with confirmation) |
| `Ctrl+O` | Open job URL in browser |
| `Enter` | Show job detail or tailored CV diff |
| `/` | Focus search bar |
| `F1` | Help screen |
| `F5` | Refresh / re-score |
| `↑/↓` | Navigate rows |
| `Ctrl+1`-`6` | Switch tabs (via Textual default) |

## Jobs Tab

The Jobs tab shows all scanned/pasted jobs in a table:

```
Score  Company              Role                                 Remote Source
─────  ────────────────────  ──────────────────────────────────────  ────── ────────────
 85    Acme Corp             Senior Rust Engineer                   Y      remoteok
 72    Beta Inc              Full-Stack Developer                   Y      hn_hiring
```

Select a row with `↑/↓` and press `Enter` to see the full detail panel:

- **Score breakdown** — Languages, Frameworks, Domains, CV Alignment
- **Matched signals** — specific skills and keywords that matched
- **Gap analysis** — missing requirements with severity and mitigation suggestions
- **Experience fit** — how each past role maps to the JD
- **Repo matches** — GitHub repos that demonstrate relevant skills
- **Role context** — seniority level, years required, leadership/mentorship signals
- **Tailoring recommendation** — actionable suggestions for CV customization
- **Quick actions** — auto-generated list of what to do next

## Tailored Tab

After tailoring a CV (`Ctrl+T`), the Tailored tab shows:

- Table of tailored CVs with Company, Role, Score, and PDF filename
- Side-by-side diff view between the master CV and tailored YAML
- Added/removed line counts
- Direct links to rendered PDF and YAML

Diff coloring:
- **Green** (`+`) — added or reworded content
- **Red** (`-`) — removed or replaced content
- **Cyan** (`@@`) — diff section headers

## Scanner Tab

Live log of all background operations:

- Job platform scans
- CV tailoring pipeline (phases 1-4 with timing)
- AI review results
- Render status

The scanner tab is where progress output from `tailor_and_render()` appears in real time via `TeeStream`.

## Settings Tab

All configuration is editable live. Changes persist to `.chameleon/config.json`:

- **Paths**: master CV, GitHub profile, templates, output directories
- **Scan**: queries, platforms, limit, timeout
- **Scoring**: category weights, thresholds, max repos
- **CV Design**: font family, sizes, spacing, colors, margins
- **Tailoring**: summary length, opencode binary path
- **ATS Ghost**: toggle invisible keyword injection, extra terms, font size/color

## Launcher Details

### `tui.sh` (Linux / macOS)

```bash
./tui.sh              # Launch TUI
./tui.sh --help       # Show help
./tui.sh --version    # Show version
```

Resolves the project root from the script location, validates `.venv/bin/python3` exists, and launches.

### `tui.bat` (Windows)

```batch
tui.bat               # Launch TUI
tui.bat --help        # Show help
tui.bat --version     # Show version
```

Same logic using `Scripts\python.exe`.
