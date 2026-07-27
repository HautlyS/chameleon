from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.config import config
from scripts.ats_ghost import collect_ats_terms, inject_ghost_text, verify_ats_text


def main():
    ap = argparse.ArgumentParser(description="Inject ATS ghost text into a PDF")
    ap.add_argument("pdf_path", help="Path to the rendered PDF")
    ap.add_argument("--jd", "-j", default="", help="Job description text file (for keyword extraction)")
    ap.add_argument("--jd-text", default="", help="Job description text directly")
    ap.add_argument("--extra", "-e", default="", help="Extra comma-separated ATS terms")
    ap.add_argument("--verify", action="store_true", help="Verify ghost text is extractable")
    ap.add_argument("--json", action="store_true", help="JSON output")

    args = ap.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        result = {"success": False, "error": f"PDF not found: {pdf_path}"}
        _output(result, args.json)
        sys.exit(1)

    jd_text = ""
    if args.jd:
        jd_path = Path(args.jd)
        if jd_path.exists():
            jd_text = jd_path.read_text(encoding="utf-8")
    if args.jd_text:
        jd_text = args.jd_text

    extra_terms = args.extra or config.get("ats_ghost_extra_terms", "")

    # Collect terms from JD + extras
    if jd_text:
        signal_terms = []
        gap_terms = []
        terms = collect_ats_terms(
            jd_text,
            extra_terms=extra_terms,
            existing_keywords=list(set(signal_terms + gap_terms)),
        )
    else:
        terms = [t.strip() for t in extra_terms.split(",") if t.strip()]

    if not terms:
        _output({"success": False, "error": "No ATS terms to inject"}, args.json)
        sys.exit(1)

    ok = inject_ghost_text(pdf_path, terms)

    result = {
        "success": ok,
        "pdf_path": str(pdf_path),
        "terms_injected": len(terms),
        "terms": terms[:20],
    }

    if args.verify and ok:
        found, found_terms = verify_ats_text(pdf_path, terms[:5])
        result["verified"] = found
        result["found_terms"] = found_terms

    _output(result, args.json)
    sys.exit(0 if ok else 1)


def _output(result: dict, as_json: bool):
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            print(f"ATS ghost injected: {result['terms_injected']} terms into {result['pdf_path']}")
            if result.get("verified"):
                print(f"Verified: {len(result.get('found_terms', []))} terms extractable")
        else:
            print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
