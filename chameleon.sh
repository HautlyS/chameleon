#!/bin/bash
# Chameleon CLI — unified entry point for tailoring, scoring, scanning, cover letters
set -euo pipefail

CHAMELEON_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$CHAMELEON_DIR/.venv/bin/python3"

# ── Resolve venv python ──────────────────────────────────────────────────
find_python() {
    if [[ -f "$VENV_PYTHON" ]]; then
        echo "$VENV_PYTHON"
    elif command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON_BIN="$(find_python)"
if [[ -z "$PYTHON_BIN" ]]; then
    echo "[!] No Python found. Install Python 3.10+ and run: make install-tools" >&2
    exit 1
fi

# ── URL crawler: fetch job description from a URL ────────────────────────
crawl_url() {
    local url="$1"
    "$PYTHON_BIN" -c "
import sys
try:
    import httpx
except ImportError:
    import urllib.request
    import re
    import html as html_mod
    req = urllib.request.Request('$url', headers={'User-Agent': 'Mozilla/5.0 (compatible; ChameleonBot/1.0)'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8', errors='replace')
    text = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    print(text[:10000])
    sys.exit(0)

try:
    resp = httpx.get('$url', timeout=30, follow_redirects=True, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; ChameleonBot/1.0)'
    })
    resp.raise_for_status()
    from html.parser import HTMLParser
    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.skip = False
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self.skip = True
        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self.skip = False
        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)
    te = TextExtractor()
    te.feed(resp.text)
    text = ' '.join(te.parts)
    import re as _re
    text = _re.sub(r'\s+', ' ', text).strip()
    print(text[:10000])
except Exception as e:
    print(f'Error crawling URL: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# ── Read stdin if available ──────────────────────────────────────────────
read_stdin() {
    if [[ ! -t 0 ]]; then
        cat
    fi
}

# ── Help ─────────────────────────────────────────────────────────────────
show_help() {
    cat <<'EOF'
Chameleon CLI — AI Resume Tailor

Usage:
  chameleon tailor <jd_text_or_url_or_file> [options]   Tailor CV for a job
  chameleon score <jd_text_or_url_or_file> [options]   Score job match
  chameleon scan  [options]                            Scan job platforms
  chameleon cover <jd_text_or_url_or_file> [options]   Generate cover letter
  chameleon render <yaml_path>                         Render YAML to PDF
  chameleon init <pdf_or_yaml_path>                    Import master CV
  chameleon tui                                        Launch the TUI
  chameleon help                                       Show this help

TAILOR options:
  --company <name>      Company name (auto-detected if omitted)
  --title <role>        Role title (auto-detected if omitted)
  --no-review           Skip AI review pass
  --no-render           Skip PDF rendering
  --cv <path>           Master CV path (default: from config)
  --json                Output JSON instead of text

SCORE options:
  --cv <path>           CV path to score against
  --json                Output JSON

SCAN options:
  -q, --query <query>   Search keywords
  -p, --platforms <list> Comma-separated platforms
  -a, --all             Scan all platforms
  --tier1               Tier 1 platforms only (API/RSS)
  -n, --limit <n>       Max jobs per platform (default: 25)
  -o, --output <file>   Save results to JSON file
  --json                Output JSON
  --list-platforms       List available platforms

COVER options:
  --resume <path>       Resume YAML to ground the letter
  --greeting <name>     Custom greeting name

INPUT:
  <text>                Job description text in quotes
  <url>                 Job posting URL (will be crawled)
  <file>                Path to a text file with the JD
  Piped stdin           Cat a file or pipe text

EXAMPLES:
  ./chameleon tailor "Senior Rust Engineer at Acme..." --company Acme
  ./chameleon tailor https://jobs.example.com/senior-rust
  ./chameleon score "Python developer, Django, PostgreSQL..."
  ./chameleon scan -q "rust engineer" --tier1 --json
  ./chameleon cover https://example.com/job --resume templates/david_cv.yaml
  cat jd.txt | ./chameleon tailor --company Acme --title Engineer
  ./chameleon render templates/david_acme_rust_engineer_cv.yaml

EOF
    exit 0
}

# ── Main dispatch ────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    show_help
fi

COMMAND="$1"
shift

case "$COMMAND" in
    tailor|tailor-cv)
        JD_INPUT=""
        COMPANY=""
        TITLE=""
        NO_REVIEW=""
        NO_RENDER=""
        CV_PATH=""
        AS_JSON=""

        while [[ $# -gt 0 ]]; do
            case "$1" in
                --company)  COMPANY="$2"; shift 2 ;;
                --title)    TITLE="$2"; shift 2 ;;
                --no-review) NO_REVIEW="yes"; shift ;;
                --no-render) NO_RENDER="yes"; shift ;;
                --cv)       CV_PATH="$2"; shift 2 ;;
                --json)     AS_JSON="yes"; shift ;;
                -*)         echo "Unknown option: $1" >&2; exit 1 ;;
                *)          JD_INPUT="$1"; shift ;;
            esac
        done

        if [[ -z "$JD_INPUT" ]]; then
            JD_INPUT="$(read_stdin)"
        fi

        if [[ -z "$JD_INPUT" ]]; then
            echo "Error: No job description provided. Pass text, URL, file path, or pipe via stdin." >&2
            echo "Usage: chameleon tailor <jd_text_or_url_or_file> [--company X] [--title Y]" >&2
            exit 1
        fi

        if [[ "$JD_INPUT" =~ ^https?:// ]]; then
            echo "[*] Crawling URL: $JD_INPUT" >&2
            JD_TEXT="$(crawl_url "$JD_INPUT")"
            if [[ -z "$JD_TEXT" ]]; then
                echo "Error: Failed to crawl URL" >&2
                exit 1
            fi
        elif [[ -f "$JD_INPUT" ]]; then
            JD_TEXT="$(cat "$JD_INPUT")"
        else
            JD_TEXT="$JD_INPUT"
        fi

        cd "$CHAMELEON_DIR"
        set -- "$JD_TEXT"
        [[ -n "$COMPANY" ]] && set -- "$@" "--company" "$COMPANY"
        [[ -n "$TITLE" ]] && set -- "$@" "--title" "$TITLE"
        [[ -n "$NO_REVIEW" ]] && set -- "$@" "--no-review"
        [[ -n "$NO_RENDER" ]] && set -- "$@" "--no-render"
        [[ -n "$AS_JSON" ]] && set -- "$@" "--json"
        exec "$PYTHON_BIN" -m scripts.tailor_cv "$@"
        ;;

    score|score-cv|match)
        JD_INPUT=""
        CV_PATH=""
        AS_JSON=""

        while [[ $# -gt 0 ]]; do
            case "$1" in
                --cv)     CV_PATH="$2"; shift 2 ;;
                --json)   AS_JSON="yes"; shift ;;
                -*)       echo "Unknown option: $1" >&2; exit 1 ;;
                *)        JD_INPUT="$1"; shift ;;
            esac
        done

        if [[ -z "$JD_INPUT" ]]; then
            JD_INPUT="$(read_stdin)"
        fi

        if [[ -z "$JD_INPUT" ]]; then
            echo "Error: No job description provided." >&2
            echo "Usage: chameleon score <jd_text_or_url_or_file> [--cv <path>] [--json]" >&2
            exit 1
        fi

        if [[ "$JD_INPUT" =~ ^https?:// ]]; then
            echo "[*] Crawling URL: $JD_INPUT" >&2
            JD_TEXT="$(crawl_url "$JD_INPUT")"
            if [[ -z "$JD_TEXT" ]]; then
                echo "Error: Failed to crawl URL" >&2
                exit 1
            fi
        elif [[ -f "$JD_INPUT" ]]; then
            JD_TEXT="$(cat "$JD_INPUT")"
        else
            JD_TEXT="$JD_INPUT"
        fi

        cd "$CHAMELEON_DIR"
        set -- "$JD_TEXT"
        [[ -n "$CV_PATH" ]] && set -- "$@" "--cv" "$CV_PATH"
        [[ -n "$AS_JSON" ]] && set -- "$@" "--json"
        exec "$PYTHON_BIN" -m scripts.job_matcher "$@"
        ;;

    scan|scan-jobs)
        cd "$CHAMELEON_DIR"
        exec "$PYTHON_BIN" -m scripts.job_scanner.scanner "$@"
        ;;

    cover|cover-letter)
        JD_INPUT=""
        RESUME_PATH=""

        while [[ $# -gt 0 ]]; do
            case "$1" in
                --resume)   RESUME_PATH="$2"; shift 2 ;;
                -*)         echo "Unknown option: $1" >&2; exit 1 ;;
                *)          JD_INPUT="$1"; shift ;;
            esac
        done

        if [[ -z "$JD_INPUT" ]]; then
            JD_INPUT="$(read_stdin)"
        fi

        if [[ -z "$JD_INPUT" ]]; then
            echo "Error: No job description provided." >&2
            echo "Usage: chameleon cover <jd_text_or_url_or_file> [--resume <path>]" >&2
            exit 1
        fi

        if [[ "$JD_INPUT" =~ ^https?:// ]]; then
            echo "[*] Crawling URL: $JD_INPUT" >&2
            JD_TEXT="$(crawl_url "$JD_INPUT")"
        elif [[ -f "$JD_INPUT" ]]; then
            JD_TEXT="$(cat "$JD_INPUT")"
        else
            JD_TEXT="$JD_INPUT"
        fi

        # Save extracted text and show instructions
        COVER_DIR="$CHAMELEON_DIR/output/cover_letters"
        mkdir -p "$COVER_DIR"
        COVER_FILE="$COVER_DIR/cover_$(date +%Y%m%d_%H%M%S).txt"
        echo "$JD_TEXT" > "$COVER_FILE"
        echo "[*] Job description saved to: $COVER_FILE" >&2
        echo "[*] To generate a cover letter, run in opencode:" >&2
        echo "    opencode" >&2
        echo "    /cover-letter --resume ${RESUME_PATH:-<resume_yaml>}" >&2
        ;;

    render)
        if [[ $# -lt 1 ]]; then
            echo "Error: No YAML path provided." >&2
            echo "Usage: chameleon render <yaml_path>" >&2
            exit 1
        fi
        cd "$CHAMELEON_DIR"
        exec "$PYTHON_BIN" scripts/render.py "$@"
        ;;

    init|init-cv)
        if [[ $# -lt 1 ]]; then
            echo "Error: No file path provided." >&2
            echo "Usage: chameleon init <pdf_or_yaml_path>" >&2
            exit 1
        fi
        echo "[*] CV initialization requires an AI assistant (use /init-cv in opencode)."
        echo "    opencode"
        echo "    /init-cv $1"
        ;;

    tui)
        cd "$CHAMELEON_DIR"
        exec ./tui.sh "$@"
        ;;

    help|--help|-h)
        show_help
        ;;

    --version|-v)
        echo "Chameleon CLI v1.0"
        exit 0
        ;;

    *)
        echo "Unknown command: $COMMAND" >&2
        echo "Run 'chameleon help' for usage." >&2
        exit 1
        ;;
esac
