#!/bin/bash
# scan.sh — quick job scanner CLI wrapper
set -euo pipefail
CHAMELEON_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CHAMELEON_DIR"

VENV_PYTHON=".venv/bin/python3"
if [[ ! -f "$VENV_PYTHON" ]]; then
    VENV_PYTHON="python3"
fi

exec "$VENV_PYTHON" -m scripts.job_scanner.scanner "$@"
