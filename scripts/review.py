from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.tailor_cv import double_review, _extract_yaml_from_response, _opencode_run
from scripts.tailor_prompts import REVIEW_PROMPT


def main():
    ap = argparse.ArgumentParser(description="Run AI double-review on a tailored CV")
    ap.add_argument("yaml_path", help="Path to the tailored YAML file")
    ap.add_argument("--jd", "-j", default="", help="Job description text file")
    ap.add_argument("--jd-text", default="", help="Job description text directly")
    ap.add_argument("--single", action="store_true", help="Single review instead of double")
    ap.add_argument("--json", action="store_true", help="JSON output")

    args = ap.parse_args()

    yaml_path = Path(args.yaml_path)
    if not yaml_path.exists():
        _output({"success": False, "error": f"YAML not found: {yaml_path}"}, args.json)
        sys.exit(1)

    jd_text = ""
    if args.jd:
        jd_path = Path(args.jd)
        if jd_path.exists():
            jd_text = jd_path.read_text(encoding="utf-8")
    if args.jd_text:
        jd_text = args.jd_text

    if not jd_text:
        _output({"success": False, "error": "Job description required (--jd or --jd-text)"}, args.json)
        sys.exit(1)

    tailored_yaml = yaml_path.read_text(encoding="utf-8")

    if args.single:
        from scripts.tailor_cv import ai_review
        approved, review, corrections = ai_review(jd_text, tailored_yaml)
        result = {
            "success": True,
            "approved": approved,
            "single_review": True,
            "review": review,
            "corrections": corrections,
        }
    else:
        approved, consolidated, corrections_text = double_review(jd_text, tailored_yaml)
        result = {
            "success": True,
            "approved": approved,
            "double_review": True,
            "review": consolidated,
            "corrections": corrections_text,
        }

    _output(result, args.json)
    sys.exit(0 if result.get("success") else 1)


def _output(result: dict, as_json: bool):
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        review = result.get("review", {})
        if review:
            score = review.get("overall_score", 0)
            missing = review.get("missing_terms", [])
            concerns = review.get("fabrication_concerns", [])
            print(f"Score: {score}/100")
            print(f"Missing terms: {len(missing)}")
            if concerns:
                print(f"Fabrication concerns: {len(concerns)}")
            by_section = review.get("by_section", {})
            if by_section:
                print(f"By section: {json.dumps(by_section)}")
            print(f"Approved: {result.get('approved', False)}")
        else:
            print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)


if __name__ == "__main__":
    main()
