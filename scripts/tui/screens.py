"""Modal screens for the Chameleon TUI."""
from __future__ import annotations

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea

from scripts.config import config


class DeleteConfirmScreen(ModalScreen[bool]):
    CSS = """
    DeleteConfirmScreen { align: center middle; }
    #del_dialog { width: 52; height: 10; border: thick $error; background: $surface; padding: 1 2; }
    #del_dialog Button { margin: 0 1; }
    """

    def __init__(self, job_title: str, company: str) -> None:
        super().__init__()
        self._job_title = job_title
        self._company = company

    def compose(self):
        with Vertical(id="del_dialog"):
            yield Static("[bold red]\u26a0 Delete Job?[/bold red]")
            yield Static("")
            yield Static(f"  [bold]{self._job_title}[/bold]")
            yield Static(f"  [dim]at {self._company}[/dim]")
            yield Static("")
            yield Static("[dim]This cannot be undone.[/dim]")
            yield Static("")
            with Horizontal():
                yield Button("Delete", id="btn_del_yes", variant="error")
                yield Button("Cancel", id="btn_del_no", variant="default")

    @on(Button.Pressed, "#btn_del_yes")
    def on_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_del_no")
    def on_cancel(self) -> None:
        self.dismiss(False)


class GotoLineScreen(ModalScreen[None]):
    CSS = """
    GotoLineScreen { align: center middle; }
    #goto_dialog { width: 40; height: 7; border: thick $primary; background: $surface; padding: 1 2; }
    """

    def __init__(self, textarea: TextArea) -> None:
        super().__init__()
        self._ta = textarea
        self._max = max(1, textarea.text.count("\n") + 1)

    def compose(self):
        with Vertical(id="goto_dialog"):
            yield Static(f"[bold]Go to line (1-{self._max}):[/bold]")
            yield Input(placeholder="Line number", id="goto_input", type="integer")
            yield Static("[dim]Enter to go, Escape to cancel[/dim]")

    @on(Input.Submitted, "#goto_input")
    def on_submit(self, event: Input.Submitted) -> None:
        try:
            line = int(event.value)
            if 1 <= line <= self._max:
                self._ta.move_cursor((line - 1, 0))
        except (ValueError, TypeError):
            pass
        self.dismiss()


class PasteJobScreen(ModalScreen[dict | None]):
    CSS = """
    PasteJobScreen { align: center middle; }
    #paste_dialog { width: 80; height: 32; border: thick $primary; background: $surface; padding: 1 2; }
    #paste_dialog TextArea { height: 1fr; border: solid $secondary; }
    #paste_status { dock: bottom; height: 1; padding: 0 1; color: $text-muted; }
    """
    BINDINGS = [Binding("ctrl+s", "save_paste", "Save")]

    def compose(self):
        with Vertical(id="paste_dialog"):
            yield Static("[bold]\u270e Paste Job Description[/bold]")
            yield Static("[dim]Paste the full job posting below. Title = first line, company auto-detected.[/dim]")
            yield TextArea(id="paste_text")
            yield Static("[dim]Ctrl+S to save  |  Escape to cancel[/dim]", id="paste_status")

    def action_save_paste(self) -> None:
        try:
            text = self.query_one("#paste_text", TextArea).text.strip()
        except Exception:
            text = ""
        if not text:
            self.dismiss(None)
            return
        lines = text.split("\n")
        title = lines[0][:80] if lines else "Pasted Job"
        company = "Unknown"
        for line in lines[:15]:
            lower = line.lower()
            if "company:" in lower:
                company = line.split(":", 1)[1].strip()
                break
            elif " at " in lower and len(line) < 60:
                parts = line.split(" at ", 1)
                if len(parts) == 2:
                    company = parts[1].strip()
                    break
        self.dismiss({
            "title": title, "company": company, "description": text,
            "location": "Unknown", "remote": False, "source": "pasted",
            "url": "", "salary": "",
        })


class HelpScreen(ModalScreen[None]):
    CSS = """
    HelpScreen { align: center middle; }
    #help_dialog { width: 76; height: auto; max-height: 88%; border: thick $primary; background: $surface; padding: 1 2; overflow: auto; }
    #help_dialog Static { width: 100%; }
    """
    BINDINGS = [Binding("escape", "dismiss_help", "Close")]

    def compose(self):
        s = config.get("score_threshold_strong", 80)
        g = config.get("score_threshold_good", 60)
        m = config.get("score_threshold_moderate", 40)
        with Vertical(id="help_dialog"):
            yield Static("[bold]\u2593 Chameleon Job TUI \u2014 Help[/bold]\n")

            yield Static("[bold]\u2500\u2500 Navigation \u2500\u2500[/bold]")
            yield Static("  [bold]\u2191\u2193[/bold]         Navigate job table")
            yield Static("  [bold]Enter[/bold]     Select job for detail view")
            yield Static("  [bold]/[/bold]         Focus search bar\n")

            yield Static("[bold]\u2500\u2500 Core Actions \u2500\u2500[/bold]")
            yield Static("  [bold]Ctrl+S[/bold]    Scan job platforms")
            yield Static("  [bold]Ctrl+N[/bold]    Paste a job description manually")
            yield Static("  [bold]Ctrl+R[/bold]    Re-score all loaded jobs")
            yield Static("  [bold]Ctrl+E[/bold]    Open selected job in nano editor")
            yield Static("  [bold]Ctrl+T[/bold]    Tailor CV \u2192 adds to Tailored tab")
            yield Static("  [bold]Ctrl+D[/bold]    Delete selected job (with confirm)")
            yield Static("  [bold]Ctrl+O[/bold]    Open job URL in browser")
            yield Static("  [bold]F2[/bold]        Scan with custom query/platforms")
            yield Static("  [bold]F5[/bold]        Refresh / re-score all\n")

            yield Static("[bold]\u2500\u2500 Editor \u2500\u2500[/bold]")
            yield Static("  [bold]Ctrl+X[/bold]    Save & exit editor")
            yield Static("  [bold]Ctrl+G[/bold]    Go to line number\n")

            yield Static("[bold]\u2500\u2500 Scoring Guide \u2500\u2500[/bold]")
            yield Static(f"  [bold bright_green]{s}+[/bold bright_green]    [bold bright_green]Strong[/bold bright_green]   \u2014 tailor immediately")
            yield Static(f"  [bold yellow]{g}-{s-1}[/bold yellow]    [bold yellow]Good[/bold yellow]      \u2014 worth applying")
            yield Static(f"  [bold dark_orange]{m}-{g-1}[/bold dark_orange]   [bold dark_orange]Moderate[/bold dark_orange]  \u2014 tailor with caution")
            yield Static(f"  [bold red]0-{m-1}[/bold red]    [bold red]Weak[/bold red]       \u2014 consider other opportunities\n")

            yield Static("  [bold]F3[/bold]        Open setup wizard (CV, AI, Telegram, WhatsApp)\n")

            yield Static("[bold]\u2500\u2500 Tips \u2500\u2500[/bold]")
            yield Static("  \u2022  Tailored CVs show diffs against your master CV")
            yield Static("  \u2022  Settings tab saves changes to .chameleon/config.json")
            yield Static("  \u2022  Scan results persist in SQLite across restarts")
            yield Static("  \u2022  Press F3 to re-run the setup wizard anytime\n")

            yield Static("[dim]Press [bold]Escape[/bold] to close[/dim]")

    def action_dismiss_help(self) -> None:
        self.dismiss()


class ConfirmQuitScreen(ModalScreen[None]):
    CSS = """
    ConfirmQuitScreen { align: center middle; }
    #quit_dialog { width: 45; height: 9; border: thick $error; background: $surface; padding: 1 2; }
    #quit_dialog Button { margin: 0 1; }
    """

    def compose(self):
        with Vertical(id="quit_dialog"):
            yield Static("[bold]Quit Chameleon TUI?[/bold]")
            yield Static("Unsaved editor changes will be lost.")
            yield Static("")
            with Horizontal():
                yield Button("Quit", id="btn_quit_yes", variant="error")
                yield Button("Cancel", id="btn_quit_no", variant="default")

    @on(Button.Pressed, "#btn_quit_yes")
    def on_quit(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_quit_no")
    def on_cancel(self) -> None:
        self.dismiss(False)


class CustomScanScreen(ModalScreen[None]):
    """Modal for custom scan query/platform input."""
    CSS = """
    CustomScanScreen { align: center middle; }
    #scan_dialog { width: 60; height: auto; border: thick $primary; background: $surface; padding: 1 2; }
    #scan_dialog Input { margin: 0 0 1 0; }
    #scan_help { color: $text-muted; text-style: dim; }
    """

    def compose(self):
        with Vertical(id="scan_dialog"):
            yield Static("[bold]\u25b6 Custom Scan[/bold]")
            yield Static("")
            yield Static("Queries (comma-separated):")
            queries = ",".join(config.scan_queries())
            yield Input(value=queries, id="cs_queries", placeholder="python, rust, ai engineer")
            yield Static("Platforms (comma-separated):")
            yield Input(value=config.scan_platforms(), id="cs_platforms", placeholder="remoteok,remotive,hn_hiring")
            yield Static("Limit per query:")
            yield Input(value=str(config.scan_limit()), id="cs_limit", type="integer", placeholder="15")
            yield Static("[dim]Available: remoteok, remotive, hn_hiring, indeed, linkedin, ycombinator...[/dim]", id="scan_help")
            yield Static("")
            with Horizontal():
                yield Button("Scan", id="cs_scan", variant="primary")
                yield Button("Cancel", id="cs_cancel", variant="default")

    @on(Button.Pressed, "#cs_scan")
    def on_scan(self) -> None:
        from scripts.tui.app import ChameleonTUI
        queries = self.query_one("#cs_queries", Input).value.strip()
        platforms = self.query_one("#cs_platforms", Input).value.strip()
        limit_raw = self.query_one("#cs_limit", Input).value.strip()
        app = self.app
        if not isinstance(app, ChameleonTUI):
            self.dismiss()
            return
        q_list = [q.strip() for q in queries.split(",") if q.strip()]
        if not q_list:
            q_list = config.scan_queries()
        p_str = platforms or config.scan_platforms()
        try:
            limit_val = int(limit_raw) if limit_raw else config.scan_limit()
        except (ValueError, TypeError):
            limit_val = config.scan_limit()
        app._scanning = True
        app._scan_count = 0
        app._scan_total = len(q_list)
        app._update_status()
        try:
            app.query_one("#main_tabs").active = "tab_scanner"
        except Exception:
            pass
        app._log(f"[yellow]Custom scan: platforms={p_str}, limit={limit_val}, queries={q_list}[/yellow]")
        app._start_scan_worker(q_list, p_str)
        self.dismiss()

    @on(Button.Pressed, "#cs_cancel")
    def on_cancel(self) -> None:
        self.dismiss()


class SetupWizardScreen(ModalScreen[bool]):
    """Multi-step setup wizard for CV, GitHub, AI reviewer, Telegram, WhatsApp."""

    CSS = """
    SetupWizardScreen { align: center middle; }
    #wizard_dialog { width: 84; height: 36; border: thick $primary; background: $surface; padding: 1 2; }
    #wizard_header { dock: top; height: 3; background: $primary-darken-1; color: $text; padding: 0 1; text-style: bold; content-align: left middle; }
    #wizard_body { height: 1fr; overflow-y: auto; }
    #wizard_body Input { margin: 0 0 1 0; }
    #wizard_body .wiz-label { color: $text-muted; text-style: dim; }
    #wizard_body .wiz-section { text-style: bold; color: $text; padding: 1 0 0 0; }
    #wizard_body .wiz-hint { color: $text-muted; text-style: dim; }
    #wizard_body .wiz-status { text-style: italic; }
    #wizard_footer { dock: bottom; height: 4; padding: 0 1; }
    #wizard_footer Button { margin: 0 1; }
    #wizard_progress { dock: top; height: 1; background: $surface-darken-1; margin: 0; }
    #wizard_status { dock: bottom; height: 1; padding: 0 1; color: $text-muted; text-style: italic; }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("ctrl+n", "next_step", "Next"),
        Binding("ctrl+p", "prev_step", "Back"),
    ]

    STEPS = [
        "welcome",
        "cv_setup",
        "github_profile",
        "ai_reviewer",
        "telegram",
        "whatsapp",
        "bridge",
        "summary",
    ]

    STEP_LABELS = {
        "welcome": "Welcome",
        "cv_setup": "CV Setup",
        "github_profile": "GitHub Profile",
        "ai_reviewer": "AI Reviewer",
        "telegram": "Telegram Bot",
        "whatsapp": "WhatsApp / Evolution API",
        "bridge": "RSS Bridge",
        "summary": "Summary",
    }

    def __init__(self) -> None:
        super().__init__()
        from scripts.config import config
        self._cfg = config
        self._step_idx = 0
        self._values: dict[str, object] = dict(config.all())

    def _step_count(self) -> int:
        return len(self.STEPS)

    def _current_step(self) -> str:
        return self.STEPS[self._step_idx]

    def compose(self):
        with Vertical(id="wizard_dialog"):
            yield Static("", id="wizard_header")
            yield Static("", id="wizard_progress")
            with VerticalScroll(id="wizard_body"):
                pass
            yield Static("", id="wizard_status")
            with Horizontal(id="wizard_footer"):
                yield Button("Back (Ctrl+P)", id="wiz_prev", variant="default")
                yield Button("Next (Ctrl+N)", id="wiz_next", variant="primary")
                yield Button("Skip", id="wiz_skip", variant="default")
                yield Button("Cancel (Esc)", id="wiz_cancel", variant="error")

    def on_mount(self) -> None:
        self._render_step()

    def _render_step(self) -> None:
        step = self._current_step()
        total = self._step_count()
        idx = self._step_idx + 1
        pct = int((idx / total) * 100)
        bar_filled = max(0, pct // 5)
        bar_empty = max(0, 20 - bar_filled)

        try:
            self.query_one("#wizard_header", Static).update(
                f"  Step {idx}/{total}: {self.STEP_LABELS.get(step, step)}"
            )
            self.query_one("#wizard_progress", Static).update(
                f"[dim][{'█' * bar_filled}{'░' * bar_empty}] {pct}%[/dim]"
            )
        except Exception:
            pass

        is_first = self._step_idx == 0
        is_last = self._step_idx == total - 1
        try:
            self.query_one("#wiz_prev", Button).display = not is_first
            self.query_one("#wiz_next", Button).label = "Finish" if is_last else "Next (Ctrl+N)"
            self.query_one("#wiz_skip", Button).display = step not in ("welcome", "summary")
        except Exception:
            pass

        try:
            self.query_one("#wizard_status", Static).update(
                "[dim]Tab/Shift+Tab between fields  |  Ctrl+N Next  |  Ctrl+P Back  |  Esc Cancel[/dim]"
            )
        except Exception:
            pass

        body = self.query_one("#wizard_body")
        body.remove_children()

        renderer = getattr(self, f"_render_{step}", self._render_placeholder)
        renderer(body)

        # Focus first input if any
        try:
            first_input = body.query(Input).first()
            first_input.focus()
        except Exception:
            pass

    def _emit_body_text(self, body, lines: list[str]) -> None:
        """Add a Static widget with the given text lines."""
        body.mount(Static("\n".join(lines)))

    def _emit_input_row(self, body, label: str, config_key: str, placeholder: str = "",
                        input_type: str = "text", hint: str = "") -> None:
        body.mount(Static(f"  {label}", classes="wiz-label"))
        current = self._values.get(config_key, "")
        body.mount(Input(
            value=str(current) if current else "",
            placeholder=placeholder,
            id=f"wiz_{config_key}",
            type=input_type,
        ))
        if hint:
            body.mount(Static(f"  {hint}", classes="wiz-hint"))

    def _render_welcome(self, body) -> None:
        self._emit_body_text(body, [
            "[bold]Welcome to Chameleon Setup Wizard[/bold]",
            "",
            "This wizard will guide you through configuring Chameleon.",
            "You can skip any step and change settings later.",
            "",
            "[bold]You will configure:[/bold]",
            "",
            "  [bold]1[/bold]  [bold]Master CV[/bold]  \u2014 Your YAML resume path",
            "  [bold]2[/bold]  [bold]GitHub Profile[/bold]  \u2014 Skill matching data",
            "  [bold]3[/bold]  [bold]AI Reviewer[/bold]  \u2014 Model endpoint",
            "  [bold]4[/bold]  [bold]Telegram Bot[/bold]  \u2014 Remote access",
            "  [bold]5[/bold]  [bold]WhatsApp[/bold]  \u2014 Evolution API setup",
            "  [bold]6[/bold]  [bold]RSS Bridge[/bold]  \u2014 Auto scanning",
            "  [bold]7[/bold]  [bold]Summary[/bold]  \u2014 Apply changes",
            "",
            "[bold green]Press Ctrl+N to start or Esc to skip.[/bold green]",
        ])

    def _render_cv_setup(self, body) -> None:
        from pathlib import Path
        templates_dir = self._cfg.resolve("templates_dir")
        existing = sorted(templates_dir.glob("*.yaml")) if templates_dir.exists() else []
        current = self._values.get("master_cv_path", "templates/master_template.yaml")

        self._emit_body_text(body, [
            "[bold]Master CV YAML[/bold]",
            "",
            "[dim]Path to your master resume in RenderCV YAML format.[/dim]",
            "",
        ])
        if existing:
            self._emit_body_text(body, ["[dim]Detected YAML files in templates/:[/dim]"])
            for p in existing[:8]:
                rel = str(p.relative_to(templates_dir.parent))
                marker = "[green]\u2713 CURRENT[/green]" if rel == current else "    "
                self._emit_body_text(body, [f"  {marker} [dim]{rel}[/dim]"])
            body.mount(Static(""))
        self._emit_input_row(body, "Path to CV YAML (relative to project root):",
                             "master_cv_path", placeholder="templates/master_template.yaml")
        self._emit_body_text(body, [
            "",
            "[dim]Tip: Use /init-cv in the CLI to import from PDF.[/dim]",
        ])

    def _render_github_profile(self, body) -> None:
        current = self._values.get("profile_path", "profiles/github_repos.json")
        exists = self._cfg.resolve("profile_path").exists()
        status = "[green]\u2713 File exists[/green]" if exists else "[red]\u2717 File not found[/red]"

        self._emit_body_text(body, [
            "[bold]GitHub Profile[/bold]",
            "",
            f"  {status}",
            "",
        ])
        self._emit_input_row(body, "Path to GitHub profile JSON (relative):",
                             "profile_path", placeholder="profiles/github_repos.json")
        self._emit_body_text(body, [
            "",
            "[dim]Generate with: python3 -m scripts.github_scraper <username>[/dim]",
        ])

    def _render_ai_reviewer(self, body) -> None:
        self._emit_body_text(body, [
            "[bold]AI Reviewer / OpenCode[/bold]",
            "",
            "[dim]Configure the AI model used for tailoring and scoring.[/dim]",
            "",
        ])
        self._emit_input_row(body, "OpenCode binary path:",
                             "opencode_bin_path", placeholder="~/.opencode/bin/opencode")
        self._emit_input_row(body, "OpenCode API URL:",
                             "opencode_api_url", placeholder="http://localhost:4096")
        self._emit_input_row(body, "Model provider (opencode, openai, anthropic, groq):",
                             "model_provider", placeholder="opencode")
        self._emit_input_row(body, "Model ID:",
                             "model_id", placeholder="big-pickle")
        self._emit_body_text(body, [
            "",
            "[dim]Examples: anthropic/claude-3-5-sonnet-20241022, openai/gpt-4-turbo[/dim]",
        ])

    def _render_telegram(self, body) -> None:
        self._emit_body_text(body, [
            "[bold]Telegram Bot[/bold]",
            "",
            "[dim]Set up remote tailoring via Telegram.[/dim]",
            "",
        ])
        self._emit_input_row(body, "Bot Token (from @BotFather):",
                             "telegram_bot_token", placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        self._emit_input_row(body, "Allowed User IDs (comma-separated):",
                             "telegram_allowed_user_ids", placeholder="123456789,987654321")
        self._emit_body_text(body, [
            "",
            "[dim]Leave blank to skip Telegram setup (can configure later).[/dim]",
        ])

    def _render_whatsapp(self, body) -> None:
        self._emit_body_text(body, [
            "[bold]WhatsApp / Evolution API[/bold]",
            "",
            "[dim]Configure WhatsApp integration via Evolution API.[/dim]",
            "",
        ])
        self._emit_input_row(body, "Evolution API URL:",
                             "evolution_api_url", placeholder="http://localhost:8080")
        self._emit_input_row(body, "Evolution API Key:",
                             "evolution_api_key", placeholder="your-api-key")
        self._emit_input_row(body, "WhatsApp Instance Name:",
                             "whatsapp_instance_name", placeholder="chameleon")
        self._emit_body_text(body, [
            "",
            "[dim]Leave API Key blank to skip WhatsApp setup (can configure later).[/dim]",
        ])

    def _render_bridge(self, body) -> None:
        self._emit_body_text(body, [
            "[bold]RSS Job Scanner Bridge[/bold]",
            "",
            "[dim]Automated job scanning settings for the bridge process.[/dim]",
            "",
        ])
        self._emit_input_row(body, "Scan interval (minutes):",
                             "rss_scan_interval_minutes", placeholder="60",
                             input_type="integer")
        self._emit_input_row(body, "High score threshold:",
                             "rss_high_score_threshold", placeholder="70",
                             input_type="integer")
        self._emit_body_text(body, [
            "",
            "[dim]Scan queries and platforms can be set in Settings > Scanner.[/dim]",
        ])

    def _render_summary(self, body) -> None:
        lines = [
            "[bold]Setup Summary[/bold]",
            "",
            "[dim]Review your configuration. Press Finish to save.[/dim]",
            "",
        ]
        # Check browser automation
        browser_ok = False
        try:
            from scripts.job_scanner.browser import is_playwright_available
            browser_ok = is_playwright_available()
        except Exception:
            pass
        browser_icon = "[green]\u2713[/green]" if browser_ok else "[yellow]\u26a0[/yellow]"
        lines.append(f"[bold]Browser Automation:[/bold]")
        lines.append(f"  {browser_icon} Playwright + Chromium ({'Available' if browser_ok else 'Not installed - run: make install-playwright'})")
        lines.append("")

        sections = [
            ("CV & Profile", ["master_cv_path", "profile_path"]),
            ("AI Reviewer", ["opencode_bin_path", "opencode_api_url", "model_provider", "model_id"]),
            ("Telegram", ["telegram_bot_token", "telegram_allowed_user_ids"]),
            ("WhatsApp", ["evolution_api_url", "evolution_api_key", "whatsapp_instance_name"]),
            ("Bridge", ["rss_scan_interval_minutes", "rss_high_score_threshold"]),
        ]
        for section_name, keys in sections:
            lines.append(f"[bold]{section_name}:[/bold]")
            for k in keys:
                val = self._values.get(k, "")
                display = str(val)
                if k in ("telegram_bot_token", "evolution_api_key") and len(str(val)) > 8:
                    s = str(val)
                    display = s[:6] + "..." + s[-4:]
                icon = "[green]\u2713[/green]" if val else "[dim]\u2014[/dim]"
                short_key = k.replace("_", " ").title()
                lines.append(f"  {icon} [dim]{short_key}:[/dim] [bold]{display}[/bold]")
            lines.append("")
        lines.append("[bold green]Press Finish to save all settings.[/bold green]")
        self._emit_body_text(body, lines)

    def _render_placeholder(self, body) -> None:
        self._emit_body_text(body, ["[dim]Step content not found[/dim]"])

    # ── Navigation ─────────────────────────────────────────────────────
    def _collect_values(self) -> None:
        body = self.query_one("#wizard_body")
        for key in list(self._values.keys()):
            try:
                inp = body.query_one(f"#wiz_{key}", Input)
                val = inp.value.strip()
                current = self._cfg.all().get(key)
                if isinstance(current, int):
                    try:
                        self._values[key] = int(val) if val else current
                    except ValueError:
                        pass
                elif isinstance(current, bool):
                    self._values[key] = val.lower() == "true"
                else:
                    self._values[key] = val or current
            except Exception:
                pass

    def action_next_step(self) -> None:
        self._collect_values()
        if self._step_idx < self._step_count() - 1:
            self._step_idx += 1
            self._render_step()
        else:
            self._finish_wizard()

    def action_prev_step(self) -> None:
        self._collect_values()
        if self._step_idx > 0:
            self._step_idx -= 1
            self._render_step()

    def _finish_wizard(self) -> None:
        self._collect_values()
        self._values["setup_wizard_completed"] = True
        self._values["setup_wizard_version"] = 1
        updates = {k: v for k, v in self._values.items() if k in self._cfg.all()}
        self._cfg.set_many(updates)
        self._cfg.sync_to_bridge()
        self.dismiss(True)

    @on(Button.Pressed, "#wiz_next")
    def on_wiz_next(self) -> None:
        self.action_next_step()

    @on(Button.Pressed, "#wiz_prev")
    def on_wiz_prev(self) -> None:
        self.action_prev_step()

    @on(Button.Pressed, "#wiz_cancel")
    def on_wiz_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#wiz_skip")
    def on_wiz_skip(self) -> None:
        self._collect_values()
        self._step_idx = min(self._step_idx + 1, self._step_count() - 1)
        self._render_step()

    def action_dismiss(self) -> None:
        self.dismiss(False)
