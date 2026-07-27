"""Chameleon TUI — main application class.

Scan, score, search, edit, tailor, diff, settings.
"""
from __future__ import annotations

import atexit
import json
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    DataTable, Footer, Header, Input, RichLog, Static, TabbedContent, TabPane, Tree,
)

# ── Project root on sys.path (needed for scripts.* imports) ───────────────
_CHAMELEON = Path(__file__).resolve().parent.parent.parent
if str(_CHAMELEON) not in sys.path:
    sys.path.insert(0, str(_CHAMELEON))

from scripts.config import config
from scripts.db import (
    compute_job_id, delete_job, get_all_jobs, get_tailored_cvs,
    save_jobs, save_tailored_cv, update_job_score,
)
from scripts.job_matcher import load_profile, score_job, extract_job_signals, find_matching_repos
from scripts.tailor_cv import kill_all_processes as kill_tailor_processes, tailor_and_render
from scripts.tailor_brief import (
    analyze_seniority, analyze_experience_relevance, analyze_repos_for_jd,
    find_gaps, load_cv_yaml, generate_brief, render_brief_text,
)

from scripts.tui.helpers import make_diff, safe_str, score_badge, score_bar, score_summary, truncate
from scripts.tui.screens import (
    ConfirmQuitScreen, CustomScanScreen, DeleteConfirmScreen, HelpScreen, PasteJobScreen,
    SetupWizardScreen,
)
from scripts.tui.widgets import NanoEditor, SettingsPane

# ── Paths (from config, not hardcoded) ─────────────────────────────────────
PROFILE_PATH = config.profile_path()
CV_PATH = config.master_cv_path()
SCANS_DIR = config.scans_dir()
ANALYSES_DIR = config.analyses_dir()
TEMPLATES_DIR = config.templates_dir()
VENV_PYTHON = config.venv_python()


# ═══════════════════════════════════════════════════════════════════════════
#  TeeStream — duplicate stdout to terminal AND TUI log in real-time
# ═══════════════════════════════════════════════════════════════════════════
class TeeStream:
    """Writes to both the real stdout and a TUI log callback, line by line."""

    def __init__(self, real_stdout: TextIO, log_cb) -> None:
        self._real = real_stdout
        self._log = log_cb
        self._buf = ""

    def _real_open(self) -> bool:
        """Check whether the real stream accepts writes (handles missing .closed)."""
        real = self._real
        if real is None:
            return False
        try:
            return not real.closed  # type: ignore[union-attr]
        except AttributeError:
            return True  # no .closed attr => assume open (e.g. Textual's _PrintCapture)

    def write(self, text: str) -> None:
        if self._real_open():
            try:
                self._real.write(text)
                self._real.flush()
            except (BrokenPipeError, OSError, AttributeError):
                pass
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                try:
                    self._log(f"[dim]tailor|[/dim] {line}")
                except Exception:
                    pass

    def flush(self) -> None:
        if self._real_open():
            try:
                self._real.flush()
            except (BrokenPipeError, OSError, AttributeError):
                pass
        if self._buf.strip():
            try:
                self._log(f"[dim]tailor|[/dim] {self._buf.strip()}")
            except Exception:
                pass
            self._buf = ""

    def fileno(self) -> int:
        return self._real.fileno()

    def close(self) -> None:
        pass  # don't close the real stdout — we don't own it

    def isatty(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════
class ChameleonTUI(App):
    """Chameleon Job TUI — scan, score, search, edit, tailor, diff, settings."""

    TITLE = "Chameleon \u2014 Job Matcher TUI"
    SUB_TITLE = "Scan \u00b7 Score \u00b7 Search \u00b7 Tailor \u00b7 Diff \u00b7 Settings"

    CSS = """
    Screen { background: $surface; }

    /* ── Search bar ── */
    #search_bar { dock: top; height: 3; background: $surface-darken-1; padding: 0 1; layout: horizontal; border-bottom: solid $primary-darken-2; }
    #search_bar Input { width: 1fr; }
    #search_count { width: auto; content-align: right middle; padding: 0 1 0 0; color: $text-muted; min-width: 8; }

    /* ── Status + hints ── */
    #status_line { dock: bottom; height: 1; background: $secondary-darken-2; color: $text-muted; padding: 0 1; }
    #key_hints { dock: bottom; height: 1; background: $primary-darken-1; color: $text; padding: 0 1; text-style: dim; }

    /* ── Tabs ── */
    #main_tabs { height: 1fr; }
    TabbedContent > TabPane { padding: 0; }

    /* ── Jobs tab ── */
    #job_table { height: 1fr; }
    #detail_pane { width: 1fr; height: 1fr; border: tall $primary-darken-1; background: $surface-darken-1; }

    /* ── Editor tab ── */
    #editor_container { height: 1fr; }
    #editor_placeholder { width: 100%; height: 100%; content-align: center middle; text-align: center; color: $text-muted; padding: 2 4; }

    /* ── Profile tab ── */
    #profile_tree { height: 1fr; }

    /* ── Scanner tab ── */
    #scan_log { height: 1fr; }

    /* ── Tailored tab ── */
    #tailored_table { height: 1fr; }
    #diff_view { width: 1fr; height: 1fr; border: tall $success-darken-1; background: $surface-darken-1; }
    #diff_stats { dock: top; height: 3; background: $success-darken-2; color: $text; padding: 0 1; text-style: bold; }
    #diff_stats Static { width: auto; }

    /* ── Empty states ── */
    .empty-state {
        width: 100%; height: 100%;
        content-align: center middle; text-align: center;
        color: $text-muted; padding: 2 4;
    }
    .empty-state .title { text-style: bold; color: $text; margin-bottom: 1; }
    .empty-state .hint { color: $text-muted; margin-top: 0; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "scan_jobs", "Scan"),
        Binding("ctrl+r", "rescore", "Score"),
        Binding("ctrl+e", "edit_job", "Edit"),
        Binding("ctrl+t", "tailor_cv", "Tailor"),
        Binding("ctrl+n", "paste_job", "Paste"),
        Binding("ctrl+d", "delete_job", "Delete"),
        Binding("ctrl+o", "open_url", "URL"),
        Binding("f1", "help_screen", "Help"),
        Binding("f2", "scan_with_options", "Scan+"),
        Binding("f3", "setup_wizard", "Setup"),
        Binding("f5", "refresh", "Refresh"),
        Binding("slash", "focus_search", "Search"),
    ]

    def __init__(self) -> None:
        super().__init__()
        try:
            self.profile = load_profile(PROFILE_PATH)
        except Exception:
            self.profile = {
                "repos": [],
                "skills_summary": {"languages": {}, "tech_stack": [], "domains": [], "infrastructure": []},
            }
        self.jobs: list[dict] = []
        self.scored_jobs: list[dict] = []
        self.filtered_jobs: list[dict] = []
        self.current_job_idx: int | None = None
        self._scanning = False
        self._rescoreing = False
        self._tailor_running = False
        self._scan_count = 0
        self._scan_total = 0
        self._search_query = ""
        self.tailored_cvs: list[dict] = []
        self.current_tailored_idx: int | None = None
        self._setup_status = self._check_setup()

        # ── Subprocess kill registry (scanner-level) ─────
        self._subprocs: list[subprocess.Popen] = []
        self._subprocs_lock = threading.Lock()
        self._shutting_down = False

        # ── Kill all child processes on exit ─────────────
        atexit.register(self._emergency_cleanup)

        # ── Trap SIGINT (Ctrl+C) to clean up before die ──
        signal.signal(signal.SIGINT, self._handle_sigint)

        # ── SIGPIPE protection (common in piped CLI usage) ──
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        except AttributeError:
            pass  # SIGPIPE not available on Windows

    # ── Crash-safe subprocess tracking ─────────────────────────────────
    def _track_proc(self, proc: subprocess.Popen) -> None:
        with self._subprocs_lock:
            self._subprocs.append(proc)

    def _untrack_proc(self, proc: subprocess.Popen) -> None:
        with self._subprocs_lock:
            try:
                self._subprocs.remove(proc)
            except ValueError:
                pass

    def _cleanup_subprocesses(self) -> None:
        """Kill all TUI-tracked subprocesses (scanner, etc.) plus tailor processes.
        Safe to call during atexit / early init — uses no TUI widgets."""
        lock = getattr(self, "_subprocs_lock", None)
        if lock is not None:
            with lock:
                for proc in getattr(self, "_subprocs", []):
                    try:
                        proc.kill()
                        proc.wait(timeout=3)
                    except Exception:
                        pass
                try:
                    self._subprocs.clear()
                except Exception:
                    pass
        kill_tailor_processes()

    def _emergency_cleanup(self) -> None:
        """Called by atexit and Ctrl+C — kills subprocesses only. No TUI widget access."""
        self._shutting_down = True
        self._cleanup_subprocesses()

    def _handle_sigint(self, signum: int, frame) -> None:
        """Traps Ctrl+C so we can kill subprocesses before Python exits."""
        self._emergency_cleanup()
        # Restore default handler and re-raise so the process stops
        signal.signal(signal.SIGINT, signal.default_int_handler)
        raise KeyboardInterrupt()

    # ── Crash-safe notifications ────────────────────────────────────────
    def _crash_notify(self, title: str, message: str = "", severity: str = "error") -> None:
        """Show a crash/debug toast with optional log entry. Never throws."""
        textual_sev = {"error": "error", "warning": "warning", "info": "information"}.get(severity, "error")
        try:
            tag = {"error": "[red]\u26a0 CRASH[/red]",
                   "warning": "[yellow]\u26a0 WARNING[/yellow]",
                   "info": "[cyan]\u2139[/cyan]"}.get(severity, "[red]\u26a0[/red]")
            line = f"{tag} {title}"
            if message:
                line += f" [dim]\u2014[/dim] {message}"
            self._log(line)
            self.notify(f"{title} {message}", timeout=8, severity=textual_sev)
        except Exception:
            pass  # last resort — if notify itself crashes, do nothing

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search_bar"):
            yield Input(placeholder="  /  Search by title, company, tag...", id="search_input")
            yield Static("", id="search_count")
        yield Static("", id="status_line")
        with TabbedContent(id="main_tabs"):
            with TabPane("Jobs", id="tab_jobs"):
                with Horizontal():
                    yield DataTable(id="job_table")
                    with VerticalScroll(id="detail_pane"):
                        yield Static(self._welcome_text(), id="empty_state", classes="empty-state")
                        yield RichLog(id="score_detail", auto_scroll=False, markup=True)
            with TabPane("Editor", id="tab_editor"):
                yield Static(self._editor_placeholder_text(), id="editor_placeholder", classes="empty-state")
                yield NanoEditor(id="editor_container")
            with TabPane("Profile", id="tab_profile"):
                yield Tree("GitHub Profile", id="profile_tree")
            with TabPane("Scanner", id="tab_scanner"):
                yield RichLog(id="scan_log", markup=True)
            with TabPane("Tailored", id="tab_tailored"):
                with Horizontal():
                    yield DataTable(id="tailored_table")
                    with VerticalScroll(id="diff_view"):
                        yield Static(self._tailored_placeholder_text(), id="tailored_empty", classes="empty-state")
                        yield RichLog(id="diff_log", auto_scroll=False, markup=True)
            with TabPane("Settings", id="tab_settings"):
                yield SettingsPane(id="settings_pane")
        yield Static(self._key_hints_for_tab("tab_jobs"), id="key_hints")
        yield Footer()

    def _welcome_text(self) -> str:
        s = self._setup_status if hasattr(self, "_setup_status") else {}
        lines = ["[bold]\u2593 Chameleon Job TUI[/bold]", ""]

        if s:
            if not s["cv_exists"] or not s["profile_exists"]:
                lines.append("[bold yellow]\u26a0 Setup Required[/bold yellow]")
                if not s["cv_exists"]:
                    lines.append(f"  [red]\u2717[/red] CV: [dim]{s['cv_path']}[/dim] [red]not found[/red]")
                else:
                    lines.append(f"  [green]\u2713[/green] CV: [dim]{s['cv_name']}[/dim]")
                if not s["profile_exists"]:
                    lines.append(f"  [red]\u2717[/red] Profile: [dim]{s['profile_path']}[/dim] [red]not found[/red]")
                else:
                    lines.append(f"  [green]\u2713[/green] Profile: [dim]{s['profile_repo_count']} repos[/dim]")
                lines.append("")
                lines.append("[bold]Press F3 to launch the Setup Wizard[/bold]")
                lines.append("")
            else:
                lines.append(f"[green]\u2713[/green] CV: [dim]{s['cv_name']}[/dim]  |  [green]\u2713[/green] Profile: [dim]{s['profile_repo_count']} repos[/dim]")
                lines.append("")

        lines.append("[dim]No jobs loaded yet.[/dim]")
        lines.append("")
        lines.append("[bold]Ctrl+S[/bold]   Scan job platforms")
        lines.append("[bold]Ctrl+N[/bold]   Paste a job description")
        lines.append("[bold]/[/bold]       Search & filter")
        lines.append("")
        lines.append("[dim]Tip: Tailored CVs appear in the Tailored tab with diffs[/dim]")
        return "\n".join(lines)

    def _editor_placeholder_text(self) -> str:
        return (
            "[dim]\u270e Editor[/dim]\n\n"
            "Select a job and press [bold]Ctrl+E[/bold] to edit its description.\n"
            "Changes are saved with [bold]Ctrl+X[/bold] and trigger a re-score."
        )

    def _tailored_placeholder_text(self) -> str:
        return (
            "[dim]\u2702 Tailored CVs[/dim]\n\n"
            "Select a job and press [bold]Ctrl+T[/bold] to tailor your CV.\n"
            "Tailored CVs appear here with diffs showing changes."
        )

    _TAB_HINTS: dict[str, str] = {
        "tab_jobs":    " \u2191\u2193 Navigate  Enter Select  Ctrl+S Scan  Ctrl+E Edit  Ctrl+T Tailor  Ctrl+D Delete  / Search  F3 Setup",
        "tab_editor":  " Ctrl+X Save&Exit  Ctrl+G GoTo  Ctrl+S Save  Esc Back",
        "tab_profile": " \u2191\u2193 Navigate  \u2195 Expand/Collapse  F3 Setup",
        "tab_scanner": " (background) Ctrl+S Scan  F2 Custom Scan  F3 Setup",
        "tab_tailored": " \u2191\u2193 Select  Ctrl+T Tailor new  Ctrl+R Rescore  F3 Setup",
        "tab_settings": " \u2191\u2193 Edit  Enter Confirm  Tab Next field  F3 Setup Wizard",
    }

    def _key_hints_for_tab(self, tab_id: str) -> str:
        hints = self._TAB_HINTS.get(tab_id, "")
        return f"[bold]F1[/bold] Help  [bold]F3[/bold] Setup {hints}  [bold]Ctrl+Q[/bold] Quit"

    # ── Mount ────────────────────────────────────────────────────────────
    def on_mount(self) -> None:
        self._setup_job_table()
        self._setup_tailored_table()
        self._load_profile_tree()
        self._update_status()
        self._load_saved_scans_worker()
        self._active_tab = "tab_jobs"

        # Launch setup wizard if CV or profile is missing (small delay for mount to finish)
        s = self._setup_status
        if not s.get("cv_exists") or not s.get("profile_exists"):
            self.set_timer(0.3, self._show_setup_wizard)
        elif not s.get("has_repos"):
            self.notify("GitHub profile has no repos. Scoring will be limited. Press F3 for Setup Wizard.", timeout=6)

    def _show_setup_wizard(self) -> None:
        def _on_result(result: bool | None) -> None:
            if result:
                self._setup_status = self._check_setup()
                self._load_profile_tree()
                self._update_status()
                config.set("setup_wizard_completed", True)
                self.notify("[bold green]\u2714 Setup complete![/bold green]", timeout=4)
                try:
                    self.query_one("#empty_state", Static).update(self._welcome_text())
                except Exception:
                    pass
            else:
                # Wizard skipped/cancelled — re-check status for stale warnings
                self._setup_status = self._check_setup()
                self._update_status()

        self.push_screen(SetupWizardScreen(), _on_result)

    @on(TabbedContent.TabActivated, "#main_tabs")
    def on_tab_changed(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.pane.id or "tab_jobs"
        self._active_tab = tab_id
        try:
            self.query_one("#key_hints", Static).update(self._key_hints_for_tab(tab_id))
        except Exception:
            pass

    # ── Helpers ──────────────────────────────────────────────────────────
    def _get_selected_job(self) -> dict | None:
        if self.current_job_idx is not None and 0 <= self.current_job_idx < len(self.filtered_jobs):
            return self.filtered_jobs[self.current_job_idx]
        return None

    def _get_selected_tailored(self) -> dict | None:
        if self.current_tailored_idx is not None and 0 <= self.current_tailored_idx < len(self.tailored_cvs):
            return self.tailored_cvs[self.current_tailored_idx]
        return None

    def _log(self, message: str) -> None:
        try:
            self.query_one("#scan_log", RichLog).write(message)
        except Exception:
            pass

    def _check_setup(self) -> dict[str, bool | str]:
        """Check which data sources are available. Returns status dict."""
        cv_ok = CV_PATH.exists()
        cv_name = CV_PATH.name if cv_ok else ""
        profile_ok = PROFILE_PATH.exists()
        has_repos = len(self.profile.get("repos", [])) > 0 if profile_ok else False
        profile_repo_count = len(self.profile.get("repos", [])) if profile_ok else 0
        return {
            "cv_exists": cv_ok,
            "cv_path": str(CV_PATH),
            "cv_name": cv_name,
            "profile_exists": profile_ok,
            "profile_path": str(PROFILE_PATH),
            "has_repos": has_repos,
            "profile_repo_count": profile_repo_count,
        }

    def _update_status(self) -> None:
        try:
            s = self._setup_status
            n = len(self.filtered_jobs)
            total = len(self.scored_jobs)

            # ── Setup warnings ──
            setup_warn = ""
            if not s["cv_exists"] and not s["profile_exists"]:
                setup_warn = "  \u26a0 [bold red]SETUP NEEDED:[/bold red] Missing CV + Profile  "
            elif not s["cv_exists"]:
                setup_warn = f"  \u26a0 [bold yellow]SETUP:[/bold yellow] CV not found ({s['cv_path']})  "
            elif not s["profile_exists"]:
                setup_warn = "  \u26a0 [bold yellow]SETUP:[/bold yellow] GitHub profile missing  "
            elif s["profile_exists"] and not s["has_repos"]:
                setup_warn = "  \u26a0 [bold yellow]SETUP:[/bold yellow] Profile has no repos  "

            # Job count with filtering info
            if self._search_query:
                count_str = f"  Jobs: [bold]{n}[/bold]/{total}"
            else:
                count_str = f"  Jobs: {total}"

            # Selected job
            sel = ""
            job = self._get_selected_job()
            if job:
                score = job.get("score", 0)
                sel = f"  \u2502  {truncate(job['company'], 20)} \u2014 {truncate(job['title'], 30)} {score_badge(score)}"

            # Activity indicators
            activity = ""
            if self._scanning:
                pct = int((self._scan_count / max(self._scan_total, 1)) * 100)
                activity = f"  \u2502  [bold cyan]\u25b6 Scanning[/bold cyan] {self._scan_count}/{self._scan_total} ({pct}%)"
            elif self._tailor_running:
                activity = "  \u2502  [bold green]\u2702 Tailoring...[/bold green]"
            elif self._rescoreing:
                activity = "  \u2502  [bold yellow]\u25b6 Scoring...[/bold yellow]"

            # Search info
            search = ""
            if self._search_query:
                search = f'  \u2502  [dim]filter: "{self._search_query}"[/dim]'
                try:
                    self.query_one("#search_count", Static).update(f"[dim]{n} match{'es' if n != 1 else ''}[/dim]")
                except Exception:
                    pass
            else:
                try:
                    self.query_one("#search_count", Static).update("")
                except Exception:
                    pass

            # Tailored count
            tailored = ""
            if self.tailored_cvs:
                tailored = f"  \u2502  [green]\u2702 {len(self.tailored_cvs)} tailored[/green]"

            self.query_one("#status_line", Static).update(
                f"{setup_warn}{count_str}{sel}{activity}{search}{tailored}"
            )
        except Exception:
            pass

    # ── Job table ────────────────────────────────────────────────────────
    def _setup_job_table(self) -> None:
        try:
            table = self.query_one("#job_table", DataTable)
            table.add_columns("Score", "Company", "Role", "Remote", "Source")
            table.cursor_type = "row"
        except Exception:
            pass

    def _refresh_job_table(self) -> None:
        try:
            table = self.query_one("#job_table", DataTable)
            table.clear()
            if self._search_query:
                q = self._search_query.lower()
                self.filtered_jobs = [
                    j for j in self.scored_jobs
                    if q in j["title"].lower() or q in j["company"].lower()
                    or q in " ".join(j.get("tags", [])).lower()
                    or q in j.get("source", "").lower()
                    or q in j.get("description", "").lower()
                ]
            else:
                self.filtered_jobs = list(self.scored_jobs)
            for job in self.filtered_jobs:
                badge = score_badge(job["score"])
                remote = "[green]Y[/green]" if job.get("remote") else "[dim]N[/dim]"
                table.add_row(
                    badge,
                    truncate(job["company"], 22),
                    truncate(job["title"], 38),
                    remote,
                    job.get("source", "?")[:12],
                )
            try:
                empty = self.query_one("#empty_state", Static)
                empty.display = not bool(self.scored_jobs)
            except Exception:
                pass
            self._update_status()
        except Exception:
            pass

    # ── Tailored table ──────────────────────────────────────────────────
    def _setup_tailored_table(self) -> None:
        try:
            table = self.query_one("#tailored_table", DataTable)
            table.add_columns("Company", "Role", "Score", "PDF")
            table.cursor_type = "row"
        except Exception:
            pass

    def _refresh_tailored_table(self) -> None:
        try:
            table = self.query_one("#tailored_table", DataTable)
            table.clear()
            for cv in self.tailored_cvs:
                score = cv.get("score", 0)
                badge = score_badge(score)
                pdf_name = Path(cv.get("pdf_path", "")).name if cv.get("pdf_path") else "-"
                table.add_row(
                    truncate(cv.get("company", "?"), 22),
                    truncate(cv.get("title", "?"), 30),
                    badge,
                    truncate(pdf_name, 30),
                )
            try:
                empty = self.query_one("#tailored_empty", Static)
                empty.display = not bool(self.tailored_cvs)
            except Exception:
                pass
            self._update_status()
        except Exception:
            pass

    def _show_tailored_diff(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.tailored_cvs):
            return
        self.current_tailored_idx = idx
        cv = self.tailored_cvs[idx]
        try:
            self.query_one("#tailored_empty", Static).display = False
        except Exception:
            pass
        try:
            diff_log = self.query_one("#diff_log", RichLog)
            diff_log.clear()

            # ── Header card ──
            score = cv.get("score", 0)
            diff_log.write(f"[bold]{'━' * 60}[/bold]")
            diff_log.write(f"[bold green]\u2702  {cv.get('company', '?')} \u2014 {cv.get('title', '?')}[/bold green]")
            diff_log.write(f"  {score_summary(score)}  {score_bar(score, width=20)}")
            pdf_name = Path(cv.get("pdf_path", "")).name if cv.get("pdf_path") else "-"
            yaml_name = Path(cv.get("yaml_path", "")).name if cv.get("yaml_path") else "-"
            diff_log.write(f"  [dim]PDF:[/dim]  {pdf_name}")
            diff_log.write(f"  [dim]YAML:[/dim] {yaml_name}")
            diff_log.write(f"[bold]{'━' * 60}[/bold]")
            diff_log.write("")

            # ── Diff ──
            original_path = config.master_cv_path()
            tailored_path = Path(cv.get("yaml_path", ""))
            if not tailored_path.exists():
                diff_log.write("[red]\u2717 Tailored YAML not found on disk[/red]")
                return
            original_text = original_path.read_text() if original_path.exists() else "(original not found)"
            tailored_text = tailored_path.read_text()
            diff_lines = make_diff(original_text, tailored_text, original_path.stem + ".yaml")
            if not diff_lines:
                diff_log.write("[dim]\u2714 No differences (identical to original)[/dim]")
                return

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            total = added + removed
            diff_log.write(f"[bold]  Diff:[/bold]  [green]+{added}[/green] added  [red]-{removed}[/red] removed  [dim]({total} changes)[/dim]\n")

            for line in diff_lines:
                if line.startswith("+++") or line.startswith("---"):
                    diff_log.write(f"[bold]{line}[/bold]")
                elif line.startswith("@@"):
                    diff_log.write(f"[bold cyan]{line}[/bold cyan]")
                elif line.startswith("+"):
                    diff_log.write(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    diff_log.write(f"[red]{line}[/red]")
                else:
                    diff_log.write(line)
        except Exception as e:
            try:
                self.query_one("#diff_log", RichLog).write(f"[red]Error reading diff: {e}[/red]")
            except Exception:
                pass

    # ── Profile tree ─────────────────────────────────────────────────────
    def _load_profile_tree(self) -> None:
        try:
            tree = self.query_one("#profile_tree", Tree)
            tree.root.expand()
            s = self._setup_status

            if not s["profile_exists"]:
                tree.root.label = "[red]\u26a0 Profile Not Found[/red]"
                tree.root.add_leaf(f"File: {s['profile_path']}")
                tree.root.add_leaf("[dim]Place a GitHub profile JSON at the path above[/dim]")
                tree.root.add_leaf("[dim]Run a scan in the Scanner tab or use Settings to change path[/dim]")
                return

            user = self.profile.get("user", "github_user")
            repos = self.profile.get("repos", [])
            tree.root.label = f"{user} \u2014 GitHub Profile ({len(repos)} repos)"

            if not repos and not any([
                self.profile.get("skills_summary", {}).get("languages", {}),
                self.profile.get("skills_summary", {}).get("tech_stack", []),
            ]):
                tree.root.add_leaf("[yellow]\u26a0 No repo data or skills found[/yellow]")
                tree.root.add_leaf("[dim]The profile file exists but contains no repos[/dim]")
                tree.root.add_leaf("[dim]Re-generate your GitHub profile or check the file format[/dim]")
                return

            langs = self.profile.get("skills_summary", {}).get("languages", {})
            if langs:
                lang_branch = tree.root.add(f"Languages ({len(langs)})")
                for lang, count in sorted(langs.items(), key=lambda x: -x[1])[:10]:
                    lang_branch.add_leaf(f"{lang} ({count} repos)")
                if len(langs) > 10:
                    lang_branch.add_leaf(f"[dim]... {len(langs) - 10} more[/dim]")
            techs = self.profile.get("skills_summary", {}).get("tech_stack", [])
            if techs:
                tech_branch = tree.root.add(f"Tech Stack ({len(techs)})")
                for tech in sorted(techs)[:15]:
                    tech_branch.add_leaf(tech)
                if len(techs) > 15:
                    tech_branch.add_leaf(f"[dim]... {len(techs) - 15} more[/dim]")
            doms = self.profile.get("skills_summary", {}).get("domains", [])
            if doms:
                dom_branch = tree.root.add(f"Domains ({len(doms)})")
                for dom in doms:
                    dom_branch.add_leaf(dom)
            infra = self.profile.get("skills_summary", {}).get("infrastructure", [])
            if infra:
                infra_branch = tree.root.add(f"Infrastructure ({len(infra)})")
                for i in infra:
                    infra_branch.add_leaf(i)
            if repos:
                rbranch = tree.root.add(f"All Repos ({len(repos)})")
                for repo in repos:
                    lang = repo.get("language") or "?"
                    desc = truncate(repo.get("summary") or "", 60)
                    rbranch.add_leaf(f"[{lang}] {repo['name']} \u2014 {desc}")
        except Exception:
            pass

    # ── Load saved scans + tailored CVs from SQLite (background) ───────
    @work(thread=True, exclusive=True, group="load_scans")
    def _load_saved_scans_worker(self) -> None:
        job_count = 0
        scan_count = 0
        analysis_count = 0
        tailored_count = 0

        db_jobs = get_all_jobs(limit=500)
        for job in db_jobs:
            self.call_from_thread(self._add_job_from_data, job, source=job.get("source", "db"), persist=False)
            job_count += 1

        if SCANS_DIR.exists():
            for f in sorted(SCANS_DIR.glob("*.json"))[-5:]:
                try:
                    data = json.loads(f.read_text())
                    items = data if isinstance(data, list) else data.get("jobs", [])
                    for job in items:
                        if not any(j.get("title", "").lower() == job.get("title", "").lower()
                                   and j.get("company", "").lower() == job.get("company", "").lower()
                                   for j in db_jobs):
                            self.call_from_thread(self._add_job_from_data, job, source=f.stem)
                            scan_count += 1
                except Exception as e:
                    self.call_from_thread(self._log, f"[red]Skip {f.name}: {e}[/red]")

        if ANALYSES_DIR.exists():
            for f in sorted(ANALYSES_DIR.glob("*.json"))[-10:]:
                try:
                    data = json.loads(f.read_text())
                    if not any(j.get("title", "").lower() == data.get("role_title", "").lower()
                               and j.get("company", "").lower() == data.get("company_name", "").lower()
                               for j in db_jobs):
                        self.call_from_thread(self._add_job_from_data, data, source="analysis")
                        analysis_count += 1
                except Exception:
                    pass

        db_tailored = get_tailored_cvs(limit=50)
        for tc in db_tailored:
            self.call_from_thread(self._add_tailored_cv_from_db, tc)
            tailored_count += 1

        if db_tailored:
            self.call_from_thread(self._refresh_tailored_table)

        total = job_count + scan_count + analysis_count + tailored_count
        if total == 0:
            self.call_from_thread(self._log, "[dim]No saved jobs. Press [bold]Ctrl+S[/bold] to scan or [bold]Ctrl+N[/bold] to paste a job.[/dim]")
        else:
            parts = []
            if job_count:
                parts.append(f"{job_count} jobs")
            if scan_count:
                parts.append(f"{scan_count} from scans")
            if analysis_count:
                parts.append(f"{analysis_count} from analyses")
            if tailored_count:
                parts.append(f"{tailored_count} tailored CVs")
            self.call_from_thread(self._log, f"[green]Loaded {', '.join(parts)}.[/green]")
            self.call_from_thread(self._show_loaded_jobs)
            self.call_from_thread(self._rescore_all)

    # ── Add job (memory + SQLite) ───────────────────────────────────────
    def _add_job_from_data(self, data: dict, source: str = "scan", persist: bool = True) -> None:
        if not isinstance(data, dict):
            return
        title = safe_str(data.get("title") or data.get("role_title") or data.get("job_title"), "Unknown")
        company = safe_str(data.get("company") or data.get("company_name"), "Unknown")
        key = f"{title.lower().strip()}|{company.lower().strip()}"
        for existing in self.jobs:
            ek = f"{existing['title'].lower().strip()}|{existing['company'].lower().strip()}"
            if ek == key:
                return
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        job = {
            "title": title,
            "company": company,
            "url": data.get("url") or data.get("apply_url") or "",
            "location": data.get("location") or "Remote",
            "description": data.get("description") or data.get("jd_text") or data.get("raw_text") or "",
            "salary": data.get("salary") or data.get("salary_range") or "",
            "source": source,
            "remote": bool(data.get("remote", False)),
            "tags": tags if isinstance(tags, list) else [],
            "score": data.get("score", 0),
            "score_detail": data.get("score_detail") or {},
        }
        self.jobs.append(job)
        if persist:
            try:
                save_jobs([job])
            except Exception:
                pass

    # ── Display loaded jobs immediately (before background scoring) ────
    def _show_loaded_jobs(self) -> None:
        self.scored_jobs = sorted(self.jobs, key=lambda j: -j.get("score", 0))
        self._refresh_job_table()

    # ── Scoring (background) ────────────────────────────────────────────
    def _rescore_all(self) -> None:
        if self._rescoreing:
            return
        self._rescoreing = True
        self._update_status()
        self._rescore_all_worker()

    @work(thread=True, exclusive=True, group="rescore")
    def _rescore_all_worker(self) -> None:
        for job in self.jobs:
            try:
                text = job.get("description") or f"{job.get('title', '')} {job.get('company', '')}"
                result = score_job(text, self.profile, CV_PATH)
                job["score"] = result.get("total_score", 0)
                job["score_detail"] = result
            except Exception:
                job["score"] = 0
                job["score_detail"] = {}
            try:
                job_id = compute_job_id(job.get("title", ""), job.get("company", ""))
                update_job_score(job_id, job["score"], job["score_detail"])
            except Exception:
                pass

        def _finish() -> None:
            self.scored_jobs = sorted(self.jobs, key=lambda j: -j.get("score", 0))
            self._rescoreing = False
            self._refresh_job_table()
            self.notify(f"Scored {len(self.jobs)} jobs", timeout=2)
        self.call_from_thread(_finish)

    # ── Job detail ───────────────────────────────────────────────────────
    def _enrich_job(self, job: dict) -> dict:
        """Compute enriched analysis for a job (gaps, experience fit, repo angles, seniority).
        Caches the result on the job dict so subsequent views are instant.
        Handles missing CV/profile gracefully with clear placeholders.
        """
        if job.get("_enriched"):
            return job
        try:
            s = self._setup_status
            desc = job.get("description", "")
            if not desc:
                job["_enriched"] = True
                job["_gaps"] = []
                job["_exp_fit"] = []
                job["_repo_angles"] = []
                job["_seniority_detail"] = {}
                job["_setup_notes"] = []
                return job

            setup_notes: list[str] = []
            if not s["cv_exists"]:
                setup_notes.append(f"No master CV at {s['cv_path']} \u2014 scoring limited to profile match only")
            if s["profile_exists"] and not s["has_repos"]:
                setup_notes.append("GitHub profile has no repos \u2014 repo matching unavailable")

            signals = extract_job_signals(desc, self.profile)
            cv = load_cv_yaml(CV_PATH) if s["cv_exists"] else {}
            job["_seniority_detail"] = analyze_seniority(desc)
            job["_exp_fit"] = analyze_experience_relevance(cv, signals, desc) if cv else []
            job["_gaps"] = find_gaps(signals, cv) if cv else []
            job["_repo_angles"] = analyze_repos_for_jd(self.profile, signals) if s["has_repos"] else []
            job["_setup_notes"] = setup_notes
            job["_enriched"] = True
        except Exception:
            job["_enriched"] = True
            for k in ("_gaps", "_exp_fit", "_repo_angles", "_seniority_detail", "_setup_notes"):
                job.setdefault(k, [] if k != "_seniority_detail" else {})
        return job

    def _show_job_detail(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.filtered_jobs):
            return
        self.current_job_idx = idx
        job = self.filtered_jobs[idx]
        try:
            self.query_one("#empty_state", Static).display = False
        except Exception:
            pass
        try:
            detail = self.query_one("#score_detail", RichLog)
            detail.clear()
            job = self._enrich_job(job)

            total = job.get("score", 0)
            sd = job.get("score_detail", {})
            bd = sd.get("breakdown", {})
            gaps = job.get("_gaps", [])
            exp_fit = job.get("_exp_fit", [])
            repo_angles = job.get("_repo_angles", [])
            sen_detail = job.get("_seniority_detail", {})

            def _bar(val: int, mx: int = 25, label: str = "") -> str:
                filled = int((val / mx) * 12)
                return f"  {label:<13} {'█' * filled}{'░' * (12 - filled)} {val}/{mx}"

            def _indicator(val: int, mx: int = 25) -> str:
                ratio = val / max(mx, 1)
                if ratio >= 0.8:
                    return "[green]\u2713[/green]"
                elif ratio >= 0.4:
                    return "[yellow]\u25b3[/yellow]"
                return "[red]\u2717[/red]"

            # ═══════════════════════════════════════════════
            #  CARD: Job Header
            # ═══════════════════════════════════════════════
            detail.write(f"[bold]{'━' * 52}[/bold]")
            detail.write(f"[bold blue]{job.get('title', 'Unknown')}[/bold blue]")
            detail.write(f"[bold]{job.get('company', 'Unknown')}[/bold]  [dim]\u2014[/dim]  {job.get('location', 'Unknown')}")
            if job.get("salary"):
                detail.write(f"[dim]\u25c8[/dim] Salary: {job['salary']}")
            remote_tag = "[green]\u2611 Remote[/green]" if job.get("remote") else "[dim]\u2610 On-site[/dim]"
            sen_tag = f"[bold cyan]{sen_detail.get('level', '?').upper()}[/bold cyan]" if sen_detail else ""
            detail.write(f"[dim]\u25c8[/dim] {remote_tag}  [dim]\u25c8[/dim] {sen_tag}  [dim]\u25c8[/dim] Source: {job.get('source', '?')}")
            if job.get("url"):
                detail.write(f"[dim]\u25c8[/dim] URL: [link={job['url']}]{truncate(job['url'], 50)}[/link]")
            if job.get("tags"):
                detail.write(f"[dim]\u25c8[/dim] Tags: [dim]{', '.join(job['tags'][:8])}[/dim]")
            detail.write(f"[bold]{'━' * 52}[/bold]")

            # ═══════════════════════════════════════════════
            #  CARD: Setup Notes (missing CV/profile)
            # ═══════════════════════════════════════════════
            setup_notes = job.get("_setup_notes", [])
            if setup_notes:
                detail.write("")
                for note in setup_notes:
                    detail.write(f"  [yellow]\u26a0 {note}[/yellow]")

            # ═══════════════════════════════════════════════
            #  CARD: Overall Score
            # ═══════════════════════════════════════════════
            detail.write("")
            detail.write(f"  {score_summary(total)}")
            detail.write(f"  {score_bar(total, width=28)}")
            detail.write("")

            # ═══════════════════════════════════════════════
            #  CARD: Score Breakdown
            # ═══════════════════════════════════════════════
            detail.write("[bold]  Score Breakdown:[/bold]")
            cats = [("Languages", bd.get("languages", 0)),
                    ("Frameworks", bd.get("frameworks", 0)),
                    ("Domains", bd.get("domains", 0)),
                    ("CV Alignment", bd.get("cv_alignment", 0))]
            for label, val in cats:
                detail.write(f"  {_bar(val, label=label)}  {_indicator(val)}")

            # ═══════════════════════════════════════════════
            #  CARD: Matched Signals
            # ═══════════════════════════════════════════════
            detail.write("")
            detail.write("[bold]  Matched Signals:[/bold]")
            matched_langs = sd.get("matched_languages", [])
            matched_fws = sd.get("matched_frameworks", [])
            matched_doms = sd.get("matched_domains", [])
            if matched_langs:
                detail.write(f"    [green]\u2713[/green] Languages:  {', '.join(matched_langs[:6])}")
            if matched_fws:
                detail.write(f"    [green]\u2713[/green] Frameworks: {', '.join(matched_fws[:6])}")
            if matched_doms:
                detail.write(f"    [yellow]\u25b3[/yellow] Domains:    {', '.join(matched_doms[:4])}")

            max_kw = config.get("max_cv_keywords_in_detail", 5)
            matched_cv = sd.get("matched_cv_keywords", [])[:max_kw]
            if matched_cv:
                detail.write(f"    [green]\u2713[/green] CV Match:   {', '.join(matched_cv)}")

            repos = sd.get("matching_repos", [])
            if repos:
                detail.write(f"    [green]\u2713[/green] Repos:      {', '.join(repos[:4])}")

            # ═══════════════════════════════════════════════
            #  CARD: Gap Analysis
            # ═══════════════════════════════════════════════
            if gaps:
                detail.write("")
                detail.write(f"[bold]  Missing Gaps ({len(gaps)}):[/bold]")
                high_gaps = [g for g in gaps if g.get("severity") == "high"]
                med_gaps = [g for g in gaps if g.get("severity") != "high"]
                for g in (high_gaps + med_gaps)[:8]:
                    sev = "[red]\u2717[/red]" if g.get("severity") == "high" else "[yellow]\u25b3[/yellow]"
                    cat = g.get("category", "?")[:8]
                    mit = g.get("mitigation", "")[:30]
                    detail.write(f"    {sev} [bold]{g['term']}[/bold] [dim]({cat})[/dim] [dim]\u2014[/dim] [italic]{mit}[/italic]")
                if len(gaps) > 8:
                    detail.write(f"    [dim]... and {len(gaps) - 8} more gaps[/dim]")
            else:
                detail.write("")
                detail.write("  [bold]  Missing Gaps:[/bold] [green]\u2714 None detected[/green]")

            # ═══════════════════════════════════════════════
            #  CARD: Experience Fit
            # ═══════════════════════════════════════════════
            if exp_fit:
                detail.write("")
                detail.write(f"[bold]  Experience Fit ({len(exp_fit)} entries):[/bold]")
                for exp in exp_fit[:5]:
                    score = exp.get("relevance_score", 0)
                    col = "green" if score >= 60 else "yellow" if score >= 30 else "dim"
                    kws = ", ".join(exp["keyword_matches"][:4]) if exp.get("keyword_matches") else ""
                    detail.write(f"    [{col}]\u2605[/{col}] [bold]{exp['company']}[/bold] \u2014 {exp['position']}")
                    detail.write(f"          Fit: [bold]{score}[/bold]/100  Keywords: [dim]{kws}[/dim]")

            # ═══════════════════════════════════════════════
            #  CARD: Repo Angles (CV suggestions)
            # ═══════════════════════════════════════════════
            if repo_angles:
                detail.write("")
                detail.write(f"[bold]  Repo Matches ({len(repo_angles)}):[/bold]")
                for ra in repo_angles[:4]:
                    detail.write(f"    [green]\u2605[/green] [bold]{ra['repo_name']}[/bold] [dim]({ra.get('language', '?')})[/dim]")
                    matched = ", ".join(ra.get("matched_terms", [])[:4])
                    if matched:
                        detail.write(f"          [dim]{matched}[/dim]")
                    if ra.get("suggested_highlight_for_cv"):
                        detail.write(f"          [italic]{ra['suggested_highlight_for_cv'][:80]}[/italic]")

            # ═══════════════════════════════════════════════
            #  CARD: Seniority & Context
            # ═══════════════════════════════════════════════
            if sen_detail:
                detail.write("")
                detail.write("[bold]  Role Context:[/bold]")
                yrs = sen_detail.get("years_required", 0)
                level = sen_detail.get("level", "?").title()
                leadership = sen_detail.get("leadership", False)
                mentorship = sen_detail.get("mentorship", False)
                autonomy = sen_detail.get("autonomy", False)
                detail.write(f"    Level: [bold]{level}[/bold]  Years req: [bold]{yrs}[/bold]")
                extras = []
                if leadership:
                    extras.append("[green]\u2713[/green] Leadership")
                if mentorship:
                    extras.append("[green]\u2713[/green] Mentorship")
                if autonomy:
                    extras.append("[yellow]\u25b3[/yellow] Autonomy")
                if extras:
                    detail.write(f"    {', '.join(extras)}")

            # ═══════════════════════════════════════════════
            #  CARD: Tailoring Recommendation
            # ═══════════════════════════════════════════════
            rec = sd.get("recommendation", "")
            if rec:
                detail.write("")
                detail.write("  [bold green]\u25b6[/bold green] [bold]Tailoring Rec:[/bold]")
                detail.write(f"    [italic]{rec}[/italic]")

            # ═══════════════════════════════════════════════
            #  CARD: Quick Tailor Action Summary
            # ═══════════════════════════════════════════════
            actions: list[str] = []
            if gaps:
                n_high = len([g for g in gaps if g.get("severity") == "high"])
                actions.append(f"Address {n_high} high-severity gap{'s' if n_high != 1 else ''} (omit/reframe)")
            if exp_fit and exp_fit[0].get("suggested_order_priority", 0) > 1:
                actions.append(f"Reorder experience: lead with {exp_fit[0]['company']}")
            if repo_angles:
                actions.append(f"Incorporate {repo_angles[0]['repo_name']} as project evidence")
            if sd.get("matched_cv_keywords"):
                matched_set = set(sd.get("matched_cv_keywords", []))
                jd_lower = (job.get("description", "") or "").lower()
                missing_ats = [kw for kw in (sd.get("matched_languages", []) + sd.get("matched_frameworks", []))
                               if kw not in matched_set and kw in jd_lower]
                if missing_ats:
                    actions.append(f"Add {missing_ats[0]} to CV keywords for ATS")
            if actions:
                detail.write("")
                detail.write("  [bold]Actions:[/bold]")
                for a in actions[:4]:
                    detail.write(f"    [dim]\u2192[/dim] [italic]{a}[/italic]")

            # ═══════════════════════════════════════════════
            #  CARD: Description (collapsed)
            # ═══════════════════════════════════════════════
            desc = job.get("description", "")
            if desc:
                detail.write("")
                detail.write(f"[dim]Raw JD ({len(desc)} chars):[/dim]")
                detail.write(f"[dim]{desc[:1200]}[/dim]")
        except Exception:
            pass
        self._update_status()

    # ── Search ───────────────────────────────────────────────────────────
    @on(Input.Changed, "#search_input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._search_query = event.value.strip()
        self.current_job_idx = None
        self._refresh_job_table()
        try:
            self.query_one("#score_detail", RichLog).clear()
        except Exception:
            pass

    @on(Input.Submitted, "#search_input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        if self.filtered_jobs:
            self.current_job_idx = 0
            self._show_job_detail(0)
            try:
                self.query_one("#job_table", DataTable).focus()
            except Exception:
                pass

    def action_focus_search(self) -> None:
        try:
            self.query_one("#main_tabs", TabbedContent).active = "tab_jobs"
            self.query_one("#search_input", Input).focus()
        except Exception:
            pass

    # ── Events: table ────────────────────────────────────────────────────
    @on(DataTable.RowSelected, "#job_table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is not None:
            self._show_job_detail(event.cursor_row)

    @on(DataTable.RowSelected, "#tailored_table")
    def on_tailored_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row is not None:
            self._show_tailored_diff(event.cursor_row)

    # ── Actions ──────────────────────────────────────────────────────────
    def action_quit(self) -> None:
        self.push_screen(ConfirmQuitScreen(), self._on_quit_result)

    def _on_quit_result(self, result: bool | None) -> None:
        if result is True:
            self._emergency_cleanup()
            self.exit()

    def action_scan_jobs(self) -> None:
        if self._scanning:
            self.notify("Scan already in progress", timeout=2)
            return
        try:
            self.query_one("#main_tabs", TabbedContent).active = "tab_scanner"
        except Exception:
            pass
        self._scanning = True
        queries = config.scan_queries()
        platforms = config.scan_platforms()
        self._scan_count = 0
        self._scan_total = len(queries)
        self._update_status()
        self._log(f"[bold]{'━' * 50}[/bold]")
        self._log(f"[bold cyan]\u25b6 Starting scan[/bold cyan]")
        self._log(f"  Platforms: [bold]{platforms}[/bold]")
        self._log(f"  Queries:   {', '.join(f'[{q}]' for q in queries)}")
        self._log(f"[bold]{'━' * 50}[/bold]")
        self._start_scan_worker(queries, platforms)

    @work(thread=True, exclusive=True, group="scanner")
    def _start_scan_worker(self, queries: list[str], platforms: str) -> None:
        limit = config.scan_limit()
        timeout = config.scan_timeout()
        try:
            for query in queries:
                if self._shutting_down:
                    self.call_from_thread(self._log, "[red]  Aborting scan — app is shutting down[/red]")
                    break
                self.call_from_thread(self._scan_count_increment, query)
                try:
                    proc = subprocess.Popen(
                        [
                            str(VENV_PYTHON), "-m", "scripts.job_scanner.scanner",
                            "--query", query,
                            "--platforms", platforms,
                            "--limit", str(limit),
                            "--json",
                        ],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, cwd=str(_CHAMELEON),
                    )
                    self._track_proc(proc)
                    try:
                        stdout, stderr = proc.communicate(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                        self.call_from_thread(self._log, f"[red]  X {query}: timeout ({timeout}s)[/red]")
                        continue
                    finally:
                        self._untrack_proc(proc)

                    if proc.returncode != 0:
                        err = (stderr or "").strip()[:200]
                        self.call_from_thread(self._log, f"[red]  X {query}: {err or 'exit code ' + str(proc.returncode)}[/red]")
                        continue
                    stdout = (stdout or "").strip()
                    if stdout:
                        data = json.loads(stdout)
                        jobs = data if isinstance(data, list) else data.get("jobs", [])
                        for job in jobs:
                            self.call_from_thread(self._add_job_from_data, job, source=f"scan:{query}")
                        self.call_from_thread(self._log, f"[green]  OK {query}: {len(jobs)} found[/green]")
                    else:
                        self.call_from_thread(self._log, f"[yellow]  -> {query}: no results[/yellow]")
                except json.JSONDecodeError as e:
                    self.call_from_thread(self._log, f"[red]  X {query}: bad JSON: {e}[/red]")
                except Exception as e:
                    self.call_from_thread(self._log, f"[red]  X {query}: {e}[/red]")
        finally:
            self._scanning = False
            self.call_from_thread(self._update_status)

        def _finish() -> None:
            self._show_loaded_jobs()
            self._rescore_all()
            self._log(f"[bold]{'━' * 50}[/bold]")
            self._log("[bold green]\u2714 Scan complete[/bold green]")
            self._log(f"[bold]{'━' * 50}[/bold]")
            self.notify("Scan complete", timeout=3)
        self.call_from_thread(_finish)

    def _scan_count_increment(self, query: str) -> None:
        self._scan_count += 1
        self._update_status()
        self._log(f"[dim]  -> {query}...[/dim]")

    def action_rescore(self) -> None:
        self._rescore_all()

    def action_edit_job(self) -> None:
        self._open_in_editor()

    def action_tailor_cv(self) -> None:
        self._tailor_current()

    def action_paste_job(self) -> None:
        self.push_screen(PasteJobScreen(), self._on_paste_result)

    def action_delete_job(self) -> None:
        self._delete_current()

    def action_open_url(self) -> None:
        self._open_url()

    # ── Shutdown lifecycle ──────────────────────────────────────────────
    def on_unmount(self) -> None:
        """Textual lifecycle hook — fires when the app is being torn down."""
        self._emergency_cleanup()

    def action_help_screen(self) -> None:
        self.push_screen(HelpScreen())

    def action_setup_wizard(self) -> None:
        """Re-open the setup wizard (F3)."""
        from scripts.tui.screens import SetupWizardScreen

        def _on_result(result: bool | None) -> None:
            if result:
                self._setup_status = self._check_setup()
                self._load_profile_tree()
                self._update_status()
                config.set("setup_wizard_completed", True)
                self.notify("[bold green]\u2714 Setup complete![/bold green]", timeout=4)
                try:
                    self.query_one("#empty_state", Static).update(self._welcome_text())
                except Exception:
                    pass
            else:
                self._setup_status = self._check_setup()
                self._update_status()

        self.push_screen(SetupWizardScreen(), _on_result)

    def action_refresh(self) -> None:
        self._rescore_all()

    def action_scan_with_options(self) -> None:
        self.push_screen(CustomScanScreen())

    # ── Editor ───────────────────────────────────────────────────────────
    def _open_in_editor(self) -> None:
        job = self._get_selected_job()
        if not job:
            self.notify("No job selected", timeout=2)
            return
        try:
            self.query_one("#main_tabs", TabbedContent).active = "tab_editor"
            try:
                self.query_one("#editor_placeholder", Static).display = False
            except Exception:
                pass
            editor = self.query_one("#editor_container", NanoEditor)
            text = job.get("description") or f"{job.get('title', '')} at {job.get('company', '')}\n\n{job.get('url', '')}"
            safe_co = job.get("company", "Unknown").replace(" ", "_").replace("/", "_")[:20]
            safe_title = job.get("title", "Unknown").replace(" ", "_").replace("/", "_")[:30]
            editor.load_text(text, filename=f"{safe_co}_{safe_title}.txt")
        except Exception:
            pass

    def _save_editor_content(self) -> None:
        job = self._get_selected_job()
        if not job:
            return
        try:
            editor = self.query_one("#editor_container", NanoEditor)
            text = editor.get_text()
            job["description"] = text
            self._rescore_all()
            self.notify(f"Saved & re-scoring: {job.get('title', '?')}", timeout=2)
        except Exception as e:
            self.notify(f"Save failed: {e}", timeout=3)

    # ── Tailor (background) ──────────────────────────────────────────────
    def _tailor_current(self) -> None:
        job = self._get_selected_job()
        if not job:
            self.notify("No job selected", timeout=2)
            return
        if self._tailor_running:
            self.notify("[yellow]Tailor already in progress — wait for it to finish[/yellow]", timeout=4)
            return
        self._tailor_running = True
        try:
            self.query_one("#main_tabs", TabbedContent).active = "tab_scanner"
        except Exception:
            pass
        try:
            self.query_one("#scan_log", RichLog).clear()
        except Exception:
            pass
        self._log(f"[bold]{'━' * 50}[/bold]")
        self._log(f"[bold cyan]\u2702 Tailoring CV:[/bold cyan] {job.get('title', '?')} at {job.get('company', '?')}")
        self._log(f"  [bold]Score:[/bold] {job.get('score', 0)}/100")
        self._log(f"[bold]{'━' * 50}[/bold]")
        self._log("[yellow]Starting tailor pipeline — progress will appear below in real-time...[/yellow]")
        self.notify("[bold]Tailoring CV...[/bold] check Scanner tab for progress", timeout=5)
        self._run_tailor_worker(job)

    @work(thread=True, exclusive=True, group="tailor")
    def _run_tailor_worker(self, job: dict) -> None:
        # Tee stdout so print(flush=True) from tailor_and_render appears in TUI log
        old_stdout = sys.stdout
        tee = TeeStream(sys.stdout, lambda line: None if self._shutting_down else self.call_from_thread(self._log, line))
        sys.stdout = tee
        try:
            ok, msg, path = tailor_and_render(
                job.get("description", ""),
                company=job.get("company", ""),
                title=job.get("title", ""),
            )
            if ok:
                yaml_path = ""
                pdf_path = ""
                for line in msg.split("\n"):
                    trimmed = line.strip()
                    if trimmed.startswith("YAML:"):
                        yaml_path = trimmed.split(":", 1)[1].strip()
                    elif trimmed.startswith("PDF:"):
                        pdf_path = trimmed.split(":", 1)[1].strip()
                self.call_from_thread(self._add_tailored_cv, job, yaml_path, pdf_path)
                self.call_from_thread(self._log, "[bold green]\u2714 CV tailored successfully![/bold green]")
                self.call_from_thread(self._log, f"[green]{msg}[/green]")
                self.call_from_thread(self._crash_notify, "Tailored", "Check Tailored tab", severity="info")
            else:
                self.call_from_thread(self._crash_notify, "Tailor failed", msg[:200], severity="warning")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.call_from_thread(self._crash_notify, "Tailor crashed", str(e)[:120], severity="error")
            self.call_from_thread(self._log, f"[red]{tb}[/red]")
        finally:
            sys.stdout = old_stdout
            self._tailor_running = False
            self.call_from_thread(self._update_status)

    def _add_tailored_cv_from_db(self, tc: dict) -> None:
        key = f"{tc.get('company', '').lower().strip()}|{tc.get('title', '').lower().strip()}"
        for existing in self.tailored_cvs:
            ek = f"{existing.get('company', '').lower().strip()}|{existing.get('title', '').lower().strip()}"
            if ek == key:
                return
        self.tailored_cvs.append(tc)

    def _add_tailored_cv(self, job: dict, yaml_path: str, pdf_path: str) -> None:
        key = f"{job.get('company', '').lower().strip()}|{job.get('title', '').lower().strip()}"
        for existing in self.tailored_cvs:
            ek = f"{existing.get('company', '').lower().strip()}|{existing.get('title', '').lower().strip()}"
            if ek == key:
                existing["yaml_path"] = yaml_path
                existing["pdf_path"] = pdf_path
                existing["score"] = job.get("score", 0)
                self._refresh_tailored_table()
                self._switch_to_tailored()
                return
        tc_entry = {
            "title": job.get("title", "Unknown"), "company": job.get("company", "Unknown"),
            "score": job.get("score", 0), "yaml_path": yaml_path, "pdf_path": pdf_path,
            "description": job.get("description", ""), "url": job.get("url", ""),
            "location": job.get("location", "Remote"), "remote": job.get("remote", False),
            "salary": job.get("salary", ""), "tags": job.get("tags", []),
            "source": job.get("source", "tailored"),
        }
        self.tailored_cvs.append(tc_entry)
        job_id = compute_job_id(job.get("title", ""), job.get("company", ""))
        try:
            save_tailored_cv(
                job_id=job_id,
                title=tc_entry["title"],
                company=tc_entry["company"],
                score=tc_entry["score"],
                yaml_path=str(yaml_path),
                pdf_path=str(pdf_path),
                description=tc_entry["description"],
                url=tc_entry["url"],
                location=tc_entry["location"],
                remote=tc_entry["remote"],
                salary=tc_entry["salary"],
                tags=tc_entry["tags"],
                source=tc_entry["source"],
            )
        except Exception as exc:
            self._log(f"[yellow]DB save warning: {exc}[/yellow]")
        self._refresh_tailored_table()
        self._switch_to_tailored()

    def _switch_to_tailored(self) -> None:
        try:
            self.query_one("#main_tabs", TabbedContent).active = "tab_tailored"
            self.notify("[bold green]\u2702 Switched to Tailored tab[/bold green]", timeout=3)
        except Exception as exc:
            self._log(f"[red]Error switching to Tailored tab: {exc}[/red]")
            return
        if self.tailored_cvs:
            try:
                table = self.query_one("#tailored_table", DataTable)
                last = len(self.tailored_cvs) - 1
                table.move_cursor(row=last, column=0)
                self._show_tailored_diff(last)
            except Exception as exc:
                self._log(f"[red]Error selecting tailored row: {exc}[/red]")

    # ── Delete (memory + SQLite) ────────────────────────────────────────
    def _delete_current(self) -> None:
        job = self._get_selected_job()
        if not job:
            self.notify("No job selected", timeout=2)
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self.jobs = [j for j in self.jobs if j is not job]
            self.scored_jobs = [j for j in self.scored_jobs if j is not job]
            self.filtered_jobs = [j for j in self.filtered_jobs if j is not job]
            job_id = compute_job_id(job.get("title", ""), job.get("company", ""))
            try:
                delete_job(job_id)
            except Exception:
                pass
            if self.current_job_idx is not None:
                if self.current_job_idx >= len(self.filtered_jobs):
                    self.current_job_idx = len(self.filtered_jobs) - 1 if self.filtered_jobs else None
            self._refresh_job_table()
            try:
                self.query_one("#score_detail", RichLog).clear()
            except Exception:
                pass
            self.notify(f"Deleted: {job.get('title', '?')}", timeout=2)

        self.push_screen(
            DeleteConfirmScreen(job.get("title", "?"), job.get("company", "?")),
            on_confirm,
        )

    # ── Open URL ─────────────────────────────────────────────────────────
    def _open_url(self) -> None:
        job = self._get_selected_job()
        if not job:
            self.notify("No job selected", timeout=2)
            return
        url = job.get("url")
        if not url:
            self.notify("No URL for this job", timeout=2)
            return
        try:
            import webbrowser
            webbrowser.open(url)
            self.notify(f"Opened: {truncate(url, 40)}", timeout=2)
        except Exception as e:
            self.notify(f"Failed: {e}", timeout=3)

    # ── Paste ────────────────────────────────────────────────────────────
    def _on_paste_result(self, result: dict | None) -> None:
        if result:
            self._add_job_from_data(result, source="pasted")
            self._rescore_all()
            self.notify(f"Added: {result.get('title', 'Unknown')}", timeout=3)
