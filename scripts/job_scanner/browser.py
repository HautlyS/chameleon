"""Browser automation module for anti-bot / JS-dependent job sites.

Supports Playwright (auto-installed) with a graceful fallback
to plain HTTP when the browser is not available.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any


class _FakeResp:
    """Mimics httpx.Response so callers don't need branching logic."""
    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def json(self) -> Any:
        import json
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


# Lazy singleton for the browser manager
_BROWSER_INSTANCE: dict[str, Any] = {}


def _get_playwright_page(headless: bool = True, timeout_ms: int = 30000) -> Any:
    """Lazy-init a Playwright browser page. Returns None on failure."""
    global _BROWSER_INSTANCE
    if "page" in _BROWSER_INSTANCE:
        try:
            _BROWSER_INSTANCE["page"].evaluate("1")
            return _BROWSER_INSTANCE["page"]
        except Exception:
            pass

    try:
        from playwright.sync_api import sync_playwright as _sp
    except ImportError:
        return None

    try:
        p = _sp().start()
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = ctx.new_page()
        page.set_default_timeout(timeout_ms)
        _BROWSER_INSTANCE["playwright"] = p
        _BROWSER_INSTANCE["browser"] = browser
        _BROWSER_INSTANCE["context"] = ctx
        _BROWSER_INSTANCE["page"] = page
        return page
    except Exception:
        return None


def is_playwright_available() -> bool:
    """Check if Playwright + chromium are installed."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    try:
        from playwright.sync_api import sync_playwright as _sp  # noqa: F401
        return True
    except ImportError:
        return False


def browser_get(
    url: str,
    timeout: int = 15,
    wait_for: str | None = None,
    wait_selector: str | None = None,
    scroll: bool = False,
    headless: bool = True,
) -> _FakeResp | None:
    """Fetch a page using Playwright, falling back to None.

    Parameters
    ----------
    url : str
        The URL to fetch.
    timeout : int
        Page load timeout in seconds.
    wait_for : str, optional
        A CSS selector or XPath to wait for before returning.
    wait_selector : str, optional
        Alias for wait_for.
    scroll : bool
        If True, scroll to bottom to trigger lazy loading.
    headless : bool
        Run browser in headless mode.
    """
    page = _get_playwright_page(headless=headless, timeout_ms=timeout * 1000)
    if page is None:
        return None

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        # Wait for network idle (up to half the timeout)
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout * 500, 10000))
        except Exception:
            pass
        # Wait for a specific selector if requested
        selector = wait_for or wait_selector
        if selector:
            try:
                page.wait_for_selector(selector, timeout=5000)
            except Exception:
                pass
        # Scroll to trigger lazy content
        if scroll:
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
            except Exception:
                pass
        html = page.content()
        return _FakeResp(text=html, status_code=200)
    except Exception:
        return None


def browser_extract_json(
    url: str,
    timeout: int = 15,
    script_pattern: str | None = None,
    headless: bool = True,
) -> list[dict] | dict | None:
    """Fetch a page via browser and extract embedded JSON data.

    Parameters
    ----------
    url : str
        The URL to fetch.
    timeout : int
        Page load timeout in seconds.
    script_pattern : str, optional
        Regex pattern to find JSON inside <script> tags.
        If None, returns full page as text.
    headless : bool
        Run browser in headless mode.
    """
    page = _get_playwright_page(headless=headless, timeout_ms=timeout * 1000)
    if page is None:
        return None

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout * 500, 10000))
        except Exception:
            pass

        if script_pattern:
            content = page.content()
            import json
            for m in re.finditer(script_pattern, content, re.DOTALL):
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
            return None
        else:
            return page.content()
    except Exception:
        return None


def close_browser() -> None:
    """Clean up browser resources."""
    global _BROWSER_INSTANCE
    try:
        if "page" in _BROWSER_INSTANCE:
            _BROWSER_INSTANCE["page"].close()
        if "context" in _BROWSER_INSTANCE:
            _BROWSER_INSTANCE["context"].close()
        if "browser" in _BROWSER_INSTANCE:
            _BROWSER_INSTANCE["browser"].close()
        if "playwright" in _BROWSER_INSTANCE:
            _BROWSER_INSTANCE["playwright"].stop()
    except Exception:
        pass
    _BROWSER_INSTANCE = {}


def install_playwright(progress_callback=None) -> bool:
    """Install Playwright and chromium browser."""
    try:
        import subprocess
        if progress_callback:
            progress_callback("Installing Playwright Python package...")
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "playwright"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            if progress_callback:
                progress_callback(f"pip install failed: {r.stderr}")
            return False

        if progress_callback:
            progress_callback("Installing Chromium browser (~150MB)...")
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            if progress_callback:
                progress_callback(f"chromium install failed: {r.stderr}")
            return False

        if progress_callback:
            progress_callback("Playwright + Chromium installed successfully!")
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"Install error: {e}")
        return False
