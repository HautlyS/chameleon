"""Base interface for job platform parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
import hashlib
import re
import time


@dataclass
class JobListing:
    """Unified job listing from any platform."""
    title: str
    company: str
    url: str
    location: str = ""
    remote: bool = True
    tags: list[str] = field(default_factory=list)
    salary: str = ""
    posted_at: str = ""
    description: str = ""
    source: str = ""
    job_id: str = ""

    def __post_init__(self):
        if not self.job_id:
            raw = f"{self.url}{self.title}{self.company}".encode()
            try:
                self.job_id = hashlib.md5(raw, usedforsecurity=False).hexdigest()[:12]
            except TypeError:
                self.job_id = hashlib.md5(raw).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)


class BaseParser(ABC):
    """Base class all platform parsers inherit from."""

    platform_name: str = "unknown"
    _last_request_time: float = 0.0
    _min_request_interval: float = 0.5

    @abstractmethod
    def fetch_jobs(
        self,
        query: str = "",
        tags: list[str] | None = None,
        limit: int = 25,
        **kwargs,
    ) -> list[JobListing]:
        """Fetch jobs from the platform. Must be implemented by subclasses."""
        ...

    def _rate_limit(self) -> None:
        """Simple rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _http_get(self, url: str, params: dict | None = None, headers: dict | None = None,
                   timeout: int = 15, retries: int = 2) -> object | None:
        """HTTP GET with retries and rate limiting. Returns httpx.Response or None."""
        self._rate_limit()
        default_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)"
        }
        if headers:
            default_headers.update(headers)

        for attempt in range(retries + 1):
            try:
                import httpx
                resp = httpx.get(url, params=params, headers=default_headers,
                                 timeout=timeout, follow_redirects=True)
                if resp.status_code in (429, 403):
                    if attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                resp.raise_for_status()
                return resp
            except ImportError:
                # Fallback to urllib if httpx not available
                import urllib.request
                import urllib.error
                import json as _json
                try:
                    if params:
                        from urllib.parse import urlencode
                        url = f"{url}?{urlencode(params)}"
                    req = urllib.request.Request(url, headers=default_headers)
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = resp.read().decode("utf-8", errors="replace")
                        # Return a minimal object mimicking httpx.Response
                        class _FakeResp:
                            def __init__(self, text, status_code=200):
                                self.text = text
                                self.status_code = status_code
                            def json(self):
                                return _json.loads(self.text)
                            def raise_for_status(self):
                                if self.status_code >= 400:
                                    raise Exception(f"HTTP {self.status_code}")
                        return _FakeResp(data)
                except Exception:
                    if attempt < retries:
                        time.sleep(1)
                        continue
                    return None
            except Exception:
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None
        return None

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags and decode entities from text."""
        import html
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _truncate(self, text: str, max_len: int = 500) -> str:
        """Truncate text to max_len chars."""
        if len(text) <= max_len:
            return text
        return text[:max_len].rsplit(" ", 1)[0] + "..."

    def _extract_next_data(self, html: str) -> dict | None:
        """Extract __NEXT_DATA__ JSON from a Next.js page."""
        import json
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        # Try data-inline-stat json
        m2 = re.search(r'data-inline-stat=["\']({.*?})["\']', html, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _extract_json_ld(self, html: str) -> list[dict]:
        """Extract all JSON-LD structured data blobs from HTML."""
        import json
        results = []
        for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    results.extend(data)
                else:
                    results.append(data)
            except json.JSONDecodeError:
                pass
        return results

    def _browser_get(self, url: str, timeout: int = 15, **kwargs) -> object | None:
        """Fetch a page using Playwright browser automation (anti-bot bypass)."""
        from .browser import browser_get
        return browser_get(url, timeout=timeout, **kwargs)

    def _browser_available(self) -> bool:
        """Check if Playwright browser automation is available."""
        from .browser import is_playwright_available
        return is_playwright_available()

    @staticmethod
    def _is_login_wall(text: str) -> bool:
        """Detect if the page is behind a login/authentication wall.

        Returns True if the page shows a sign-in wall (not just a form on
        a legitimate content page).
        """
        low = text.lower()
        markers = [
            "sign in to view", "sign in to see", "sign in to continue",
            "please sign in", "please log in", "please login",
            "create an account to view", "create your account to view",
            "join to view", "join to see", "subscribe to view",
            "login to view", "login to see",
            "auth-wall", "authentication-wall",
        ]
        # Require at least 2 markers to reduce false positives
        count = sum(1 for m in markers if m in low)
        return count >= 2
