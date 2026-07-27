"""Shared utility functions for the Chameleon TUI."""
from __future__ import annotations

import difflib

from scripts.config import config


def score_color(score: int) -> str:
    """Return Textual color markup for a match score."""
    return config.score_color(score)


def score_badge(score: int) -> str:
    """Return a colored score badge for DataTable display."""
    c = score_color(score)
    return f"[{c}]{score:>3}[/{c}]"


def score_bar(score: int, width: int = 20) -> str:
    """Return a visual score bar like [████████░░░░░░░░] 80/100."""
    filled = int((score / 100) * width)
    empty = width - filled
    c = score_color(score)
    bar = f"[{c}]{'█' * filled}[/{c}]" + f"[dim]{'░' * empty}[/dim]"
    return f"{bar} {score}/100"


def score_summary(score: int) -> str:
    """Return a one-line score label."""
    if score >= config.get("score_threshold_strong", 80):
        return "[bold bright_green]Strong Match[/bold bright_green]"
    elif score >= config.get("score_threshold_good", 60):
        return "[bold yellow]Good Match[/bold yellow]"
    elif score >= config.get("score_threshold_moderate", 40):
        return "[bold dark_orange]Moderate Match[/bold dark_orange]"
    return "[bold red]Weak Match[/bold red]"


def truncate(text: str, length: int) -> str:
    """Truncate text to length with ellipsis, respecting word boundaries."""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[: length - 1].rsplit(" ", 1)[0] + "\u2026"


def safe_str(val: object, default: str = "") -> str:
    """Convert val to str, returning default for None."""
    if val is None:
        return default
    return str(val)


def make_diff(old_text: str, new_text: str, filename: str = "cv") -> list[str]:
    """Produce a unified diff between two texts."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    return list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"original/{filename}",
        tofile=f"tailored/{filename}",
        lineterm="",
    ))
