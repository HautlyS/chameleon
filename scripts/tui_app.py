"""Chameleon Job TUI — backward-compatible entry point.

All logic now lives in scripts/tui/ package.
This file exists so `python scripts/tui_app.py` and the ./tui launcher keep working.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.tui.app import ChameleonTUI  # noqa: E402


def main() -> None:
    app = ChameleonTUI()
    app.run()


if __name__ == "__main__":
    main()
