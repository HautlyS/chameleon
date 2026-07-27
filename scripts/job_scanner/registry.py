"""Parser registry — import all parsers here to auto-register them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseParser

_registry: dict[str, type[BaseParser]] = {}


def register_parser(cls: type[BaseParser]) -> type[BaseParser]:
    """Decorator to register a parser class."""
    _registry[cls.platform_name] = cls
    return cls


def get_parser(platform: str) -> type[BaseParser] | None:
    """Get a parser class by platform name."""
    _ensure_loaded()
    return _registry.get(platform)


def get_all_parsers() -> dict[str, type[BaseParser]]:
    """Get all registered parsers."""
    _ensure_loaded()
    return dict(_registry)


def list_platforms() -> list[str]:
    """List all available platform names."""
    _ensure_loaded()
    return sorted(_registry.keys())


_loaded = False

def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    _loaded = True
    from .parsers import (  # noqa: F401
        himalayas,
        remoteok,
        remotive,
        weworkremotely,
        hn_hiring,
        jobicy,
        adzuna,
        jooble,
        arc,
        crypto_careers,
        dailyremote,
        relocate,
        web3_career,
        ycomb,
        linkedin,
        indeed,
        wellfound,
        flexjobs,
        opentoworkremote,
        remote_rocketship,
    )
