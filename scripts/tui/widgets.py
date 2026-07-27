"""Reusable widgets: NanoEditor and SettingsPane."""
from __future__ import annotations

from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Select, Static, TextArea

from scripts.config import config


# ═════════════════════════════════════════════════════════════════════════════
#  NANO EDITOR
# ═════════════════════════════════════════════════════════════════════════════
class NanoEditor(Vertical):
    DEFAULT_CSS = """
    NanoEditor { height: 1fr; }
    NanoEditor #editor_text { height: 1fr; border: tall $primary; }
    NanoEditor #editor_status { dock: bottom; height: 1; background: $primary; color: $text; padding: 0 1; }
    NanoEditor #editor_hints { dock: bottom; height: 1; background: $secondary-darken-2; color: $text-muted; padding: 0 1; }
    """
    _filename: str | None = None
    _original_text: str = ""
    BINDINGS = [
        Binding("ctrl+x", "editor_save_exit", "Save & Exit", show=True),
        Binding("ctrl+g", "editor_goto", "Go To", show=True),
    ]

    def compose(self):
        yield TextArea(id="editor_text")
        yield Static("  ^X Save&Exit  ^G GoTo", id="editor_hints")
        yield Static("  [bold]New Buffer[/bold]                                                   Ln 1, Col 1", id="editor_status")

    def load_text(self, text: str, filename: str | None = None) -> None:
        try:
            ta = self.query_one("#editor_text", TextArea)
            ta.load_text(text or "")
            self._original_text = text or ""
            if filename:
                self._filename = filename
            self._update_status()
            ta.focus()
        except Exception:
            pass

    def get_text(self) -> str:
        try:
            return self.query_one("#editor_text", TextArea).text
        except Exception:
            return ""

    def is_modified(self) -> bool:
        try:
            return self.query_one("#editor_text", TextArea).text != self._original_text
        except Exception:
            return False

    def _update_status(self) -> None:
        try:
            ta = self.query_one("#editor_text", TextArea)
            loc = ta.cursor_location
            lines = loc[0] + 1
            col = loc[1] + 1
            modified = " [+]" if self.is_modified() else ""
            name = self._filename or "New Buffer"
            self.query_one("#editor_status", Static).update(
                f"  [bold]{name}{modified}[/bold]"
                f"{'':>{max(1, 60 - len(name) - len(modified))}}"
                f"Ln {lines}, Col {col}"
            )
        except Exception:
            pass

    def on_text_area_cursor(self) -> None:
        self._update_status()

    def on_text_area_changed(self) -> None:
        self._update_status()

    def action_editor_save_exit(self) -> None:
        from scripts.tui.app import ChameleonTUI
        app = self.app
        if isinstance(app, ChameleonTUI):
            app._save_editor_content()
            try:
                app.query_one("#main_tabs").active = "tab_jobs"
            except Exception:
                pass

    def action_editor_goto(self) -> None:
        from scripts.tui.screens import GotoLineScreen
        try:
            ta = self.query_one("#editor_text", TextArea)
            self.app.push_screen(GotoLineScreen(ta))
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
#  SETTINGS PANE
# ═════════════════════════════════════════════════════════════════════════════
class SettingsPane(VerticalScroll):
    """Dynamic settings editor — all config keys editable."""

    DEFAULT_CSS = """
    SettingsPane { height: 1fr; }
    SettingsPane .section-title {
        background: $primary-darken-1; color: $text;
        padding: 0 1; height: 2; content-align: left middle;
        text-style: bold; margin: 1 0 0 0;
    }
    SettingsPane .setting-row { height: 3; padding: 0 1; layout: horizontal; }
    SettingsPane .setting-label { width: 32; content-align: left middle; color: $text-muted; }
    SettingsPane .setting-value { width: 1fr; }
    SettingsPane #settings_actions { height: 4; padding: 1; layout: horizontal; }
    SettingsPane #settings_actions Button { margin: 0 1; }
    SettingsPane #font_preview {
        height: 3; padding: 0 2;
        background: $surface-darken-1; color: $text;
        content-align: center middle;
        margin: 0 1;
    }
    SettingsPane #settings_status {
        height: 1; padding: 0 1; color: $text-muted;
        text-style: italic;
    }
    """

    _SECTION_ICONS: dict[str, str] = {
        "Paths": "\U0001f4c1",
        "Scanner": "\U0001f50d",
        "Matching": "\u2694",
        "AI Reviewer": "\U0001f916",
        "Telegram Bot": "\U0001f4e2",
        "WhatsApp": "\U0001f4ac",
        "Bridge/RSS": "\U0001f4e1",
        "Colors": "\U0001f3a8",
        "Fonts": "\u270d",
        "Cache": "\U0001f4be",
        "Rate Limits": "\u23f1",
        "ATS Ghost Text": "\U0001f47b",
    }

    def compose(self):
        from scripts.fonts import list_available_fonts, get_current_font

        all_cfg = config.all()
        # Keys already handled by the explicit font selector
        font_handled_keys = {"cv_font_family"}

        keys_by_section: dict[str, list[str]] = {
            "Paths": [k for k in all_cfg if k.endswith("_path") or k.endswith("_dir")],
            "Scanner": [k for k in all_cfg if k.startswith("scan_")],
            "Matching": [k for k in all_cfg if k.startswith("score_") or k.startswith("lang_") or k.startswith("fw_") or k.startswith("dom_") or k.startswith("domain_")],
            "AI Reviewer": [k for k in all_cfg if k.startswith("opencode_") or k.startswith("model_")],
            "Telegram Bot": [k for k in all_cfg if k.startswith("telegram_")],
            "WhatsApp": [k for k in all_cfg if k.startswith("evolution_") or k.startswith("whatsapp_")],
            "Bridge/RSS": [k for k in all_cfg if k.startswith("rss_") or k.startswith("webhook_")],
            "Colors": [k for k in all_cfg if k.startswith("color_")],
            "Fonts": [k for k in all_cfg if k.startswith("cv_font_") and k not in font_handled_keys],
            "Cache": [k for k in all_cfg if k.startswith("cache_")],
            "Rate Limits": [k for k in all_cfg if k.startswith("rate_") or k.startswith("max_retry") or k.startswith("retry_")],
            "ATS Ghost Text": [k for k in all_cfg if k.startswith("ats_ghost_")],
        }

        for section, keys in keys_by_section.items():
            if not keys:
                continue
            icon = self._SECTION_ICONS.get(section, "\u25cf")
            yield Static(f"  {icon} {section}", classes="section-title")
            for key in keys:
                val = all_cfg[key]
                with Horizontal(classes="setting-row"):
                    yield Static(key, classes="setting-label")
                    if isinstance(val, bool):
                        yield Select(
                            [("true", "true"), ("false", "false")],
                            value=str(val).lower(),
                            id=f"set_{key}",
                            classes="setting-value",
                        )
                    elif isinstance(val, int):
                        yield Input(value=str(val), id=f"set_{key}", classes="setting-value", type="integer")
                    elif isinstance(val, float):
                        yield Input(value=str(val), id=f"set_{key}", classes="setting-value")
                    elif isinstance(val, list):
                        yield Input(value=",".join(val), id=f"set_{key}", classes="setting-value")
                    else:
                        yield Input(value=str(val), id=f"set_{key}", classes="setting-value")

        yield Static("  Font Preview & Selection", classes="section-title")
        yield Static(get_current_font(), id="font_preview")
        fonts = list_available_fonts()
        font_options = [(f["family"], f["family"]) for f in fonts[:50]]
        yield Select(font_options, value=get_current_font(), id="set_cv_font_family", classes="setting-value")

        with Horizontal(id="settings_actions"):
            yield Button("Save to Disk", id="btn_save_config", variant="primary")
            yield Button("Reload Config", id="btn_reload_config", variant="default")
            yield Button("Reset to Defaults", id="btn_reset_config", variant="error")
            yield Button("Clear Cache", id="btn_clear_cache", variant="default")
        yield Static("[dim]Changes apply in memory instantly. Press Save to persist.[/dim]", id="settings_status")

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        key = event.select.id
        if key and key.startswith("set_"):
            cfg_key = key[4:]
            val = event.value
            if val == "true":
                config.set(cfg_key, True)
            elif val == "false":
                config.set(cfg_key, False)
            else:
                config.set(cfg_key, val)
            _update_font_preview(self)

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        key = event.input.id
        if key and key.startswith("set_"):
            cfg_key = key[4:]
            raw = event.value.strip()
            all_cfg = config.all()
            current = all_cfg.get(cfg_key)
            if isinstance(current, bool):
                config.set_nopersist(cfg_key, raw.lower() == "true")
            elif isinstance(current, int):
                try:
                    config.set_nopersist(cfg_key, int(raw))
                except (ValueError, TypeError):
                    pass
            elif isinstance(current, list):
                config.set_nopersist(cfg_key, [x.strip() for x in raw.split(",") if x.strip()])
            else:
                config.set_nopersist(cfg_key, raw)
            _update_font_preview(self)

    @on(Button.Pressed, "#btn_save_config")
    def on_save(self) -> None:
        config.persist()
        self.notify("Config saved to disk", timeout=2)
        try:
            self.query_one("#settings_status", Static).update("[green]\u2714 Saved to .chameleon/config.json[/green]")
        except Exception:
            pass

    @on(Button.Pressed, "#btn_reload_config")
    def on_reload(self) -> None:
        config.reload()
        _update_font_preview(self)
        self.notify("Config reloaded from disk", timeout=2)

    @on(Button.Pressed, "#btn_reset_config")
    def on_reset(self) -> None:
        from scripts.config import DEFAULTS
        config.set_many(dict(DEFAULTS))
        config.persist()
        _update_font_preview(self)
        self.notify("Config reset to defaults", timeout=2)

    @on(Button.Pressed, "#btn_clear_cache")
    def on_clear_cache(self) -> None:
        from scripts.cache import cache_clear
        n = cache_clear()
        self.notify(f"Cleared {n} cached items", timeout=2)


def _update_font_preview(pane: SettingsPane) -> None:
    from scripts.fonts import get_current_font
    try:
        st = pane.query_one("#font_preview", Static)
        current = get_current_font()
        st.update(f"  Current font: [bold]{current}[/bold]  |  Sample: The quick brown fox...")
    except Exception:
        pass
