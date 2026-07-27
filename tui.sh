#!/bin/bash
# Chameleon Job TUI — launcher script (Unix/Linux/macOS)
set -euo pipefail

CHAMELEON_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$CHAMELEON_DIR/.venv/bin/python3"

show_help() {
    cat <<EOF
Chameleon Job TUI — scan, score, tailor, and diff

Usage:  ./tui.sh [options]

Options:
  --help, -h    Show this help message
  --version     Show version info

Keybindings inside the TUI:
  Ctrl+S    Scan job platforms
  Ctrl+N    Paste a job description
  Ctrl+E    Edit selected job
  Ctrl+T    Tailor CV for selected job
  Ctrl+R    Rescore all jobs
  Ctrl+D    Delete selected job
  Ctrl+O    Open job URL in browser
  /         Search jobs
  F1        Help screen
  Ctrl+Q    Quit
  Ctrl+1-6  Switch tabs

EOF
    exit 0
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
fi

if [[ "${1:-}" == "--version" ]]; then
    echo "Chameleon Job TUI v1.0"
    exit 0
fi

# Ensure venv exists
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "[!] Virtual environment not found at $VENV_PYTHON"
    echo "    Run: ./chameleon setup"
    echo "    Or: python3 -m venv .venv && .venv/bin/pip install textual pyyaml httpx reportlab beautifulsoup4 lxml markdownify"
    exit 1
fi

# Quick dep check
$VENV_PYTHON -c "import textual" 2>/dev/null || {
    echo "[!] textual not installed. Run: $VENV_PYTHON -m pip install textual pyyaml httpx"
    exit 1
}

cd "$CHAMELEON_DIR" || exit 1
exec "$VENV_PYTHON" -m scripts.tui_app "$@"
