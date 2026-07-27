"""Font manager for CV rendering — Google Fonts integration + local fallbacks.

0 hardcoded font paths. TUI can install, preview, and select fonts dynamically.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from scripts.config import config

# Built-in Google Fonts that work with RenderCV/Typst
BUILTIN_FONTS: list[dict[str, Any]] = [
    {"family": "Source Sans Pro", "category": "sans-serif", "builtin": True},
    {"family": "Source Serif Pro", "category": "serif", "builtin": True},
    {"family": "Source Code Pro", "category": "monospace", "builtin": True},
    {"family": "IBM Plex Sans", "category": "sans-serif", "builtin": True},
    {"family": "IBM Plex Serif", "category": "serif", "builtin": True},
    {"family": "Inter", "category": "sans-serif", "builtin": True},
    {"family": "Roboto", "category": "sans-serif", "builtin": True},
    {"family": "Lato", "category": "sans-serif", "builtin": True},
    {"family": "Open Sans", "category": "sans-serif", "builtin": True},
    {"family": "Noto Sans", "category": "sans-serif", "builtin": True},
    {"family": "Noto Serif", "category": "serif", "builtin": True},
    {"family": "Merriweather", "category": "serif", "builtin": True},
    {"family": "Playfair Display", "category": "serif", "builtin": True},
    {"family": "Fira Sans", "category": "sans-serif", "builtin": True},
    {"family": "Cabin", "category": "sans-serif", "builtin": True},
    {"family": "Montserrat", "category": "sans-serif", "builtin": True},
    {"family": "Nunito", "category": "sans-serif", "builtin": True},
    {"family": "Poppins", "category": "sans-serif", "builtin": True},
    {"family": "Raleway", "category": "sans-serif", "builtin": True},
    {"family": "Ubuntu", "category": "sans-serif", "builtin": True},
]

# Google Fonts CSS API base for downloading
GFONTS_API = "https://fonts.googleapis.com/css2?family={family}:wght@300;400;500;600;700&display=swap"


def list_available_fonts() -> list[dict[str, Any]]:
    """List all available fonts (built-in + locally installed)."""
    fonts = list(BUILTIN_FONTS)

    # Check for locally downloaded fonts
    fonts_dir = config.fonts_dir()
    if fonts_dir.exists():
        for f in fonts_dir.glob("*"):
            if f.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2"):
                fonts.append({
                    "family": f.stem,
                    "category": "local",
                    "builtin": False,
                    "path": str(f),
                    "format": f.suffix[1:],
                })

    # Check system fonts (Linux fc-list)
    try:
        result = subprocess.run(
            ["fc-list", "--format=%{family}\n"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            families = [f.strip() for f in line.split(",")]
            for fam in families:
                if fam and not any(
                    f["family"].lower() == fam.lower() for f in fonts
                ):
                    fonts.append({
                        "family": fam,
                        "category": "system",
                        "builtin": False,
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for f in fonts:
        key = f["family"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def download_font(family: str) -> tuple[bool, str]:
    """Download a Google Font for local use."""
    fonts_dir = config.fonts_dir()
    fonts_dir.mkdir(parents=True, exist_ok=True)
    safe_name = family.replace(" ", "_")
    out_path = fonts_dir / f"{safe_name}.ttf"
    if out_path.exists():
        return True, f"Already downloaded: {out_path}"

    css_url = GFONTS_API.format(family=family.replace(" ", "+"))
    try:
        req = urllib.request.Request(
            css_url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            css = resp.read().decode()
    except (urllib.error.URLError, OSError) as e:
        return False, f"Failed to fetch font CSS: {e}"

    # Extract first .ttf or .woff2 URL from the CSS
    urls = re.findall(r"url\(([^)]+)\)", css)
    if not urls:
        return False, "No font URL found in Google Fonts CSS"

    font_url = urls[0]
    try:
        req = urllib.request.Request(
            font_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        out_path.write_bytes(data)
        return True, f"Downloaded: {out_path} ({len(data) / 1024:.0f} KB)"
    except (urllib.error.URLError, OSError) as e:
        return False, f"Failed to download font file: {e}"


def get_current_font() -> str:
    """Get the currently configured CV font family."""
    return config.get("cv_font_family", "Source Sans Pro")


def set_font(family: str) -> None:
    """Set the CV font family in config."""
    config.set("cv_font_family", family)


def apply_font_to_master_cv(yaml_path: Path, family: str | None = None) -> bool:
    """Apply font settings to a CV YAML file."""
    if not yaml_path.exists():
        return False

    family = family or get_current_font()
    try:
        text = yaml_path.read_text()
        lines = text.split("\n")
        in_design = False
        design_end = 0
        has_font = False
        new_lines = []

        for i, line in enumerate(lines):
            if line.strip() == "design:":
                in_design = True
            if in_design and line.strip() == "":
                in_design = False
                design_end = i
            if in_design and "font:" in line:
                has_font = True

        new_lines = list(lines)
        if not has_font:
            insert_at = design_end if design_end else len(lines) - 1
            new_lines.insert(insert_at, f"    typography:")
            new_lines.insert(insert_at + 1, f"      font: {family}")
        else:
            new_lines = [
                re.sub(r"font:\s*.+", f"font: {family}", line)
                for line in new_lines
            ]

        yaml_path.write_text("\n".join(new_lines))
        return True
    except Exception:
        return False


def preview_text(family: str, sample: str = "The quick brown fox jumps over the lazy dog.") -> str:
    """Generate a text preview for a font family."""
    return f"[bold]{family}[/bold] — {sample}"
