from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import BridgeConfig


def main():
    ap = argparse.ArgumentParser(description="Chameleon Bridge — bot-facing API for chameleon")
    ap.add_argument("command", nargs="?", help="Command to run")
    ap.add_argument("--query", "-q", default="", help="Search query")
    ap.add_argument("--platforms", "-p", default="remoteok,remotive,hn_hiring", help="Platforms")
    ap.add_argument("--limit", "-l", type=int, default=15, help="Jobs per platform")
    ap.add_argument("--analysis", "-a", default="", help="Analysis ID or path")
    ap.add_argument("--yaml", "-y", default="", help="YAML path to render")
    ap.add_argument("--cv", "-c", default="", help="CV YAML path for cover-letter/question")
    ap.add_argument("--jd", "-j", default="", help="JD file path for question command")
    ap.add_argument("--company", help="Company name")
    ap.add_argument("--title", help="Role title")
    ap.add_argument("--extra", "-e", default="", help="Extra ATS terms (comma-separated) for ghost")
    ap.add_argument("--single", action="store_true", help="Single review instead of double")
    ap.add_argument("--subscribe", default="", help="Phone number to subscribe for RSS alerts")
    ap.add_argument("--unsubscribe", default="", help="Phone number to unsubscribe from RSS alerts")
    ap.add_argument("--json", action="store_true", help="JSON output")

    args = ap.parse_args()

    try:
        config = BridgeConfig()
    except Exception as e:
        print(json.dumps({"error": f"Config load failed: {e}"}))
        sys.exit(1)

    try:
        from .chameleon_client import ChameleonClient
        client = ChameleonClient(config.project_root)
    except ImportError as e:
        print(json.dumps({"error": f"Bridge client not available: {e}. Run: pip install -r requirements.txt"}))
        sys.exit(1)

    try:
        _run_command(args, client, ap)
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)


def _run_command(args, client, ap):
    if args.command == "scan":
        jobs = client.scan_jobs(query=args.query, platforms=args.platforms, limit=args.limit)
        if args.json:
            print(json.dumps(jobs, indent=2))
        else:
            for j in jobs:
                if "error" in j:
                    print(f"  Error: {j['error']}")
                else:
                    print(f"  {j.get('title', '?')} @ {j.get('company', '?')} — {j.get('source', '?')}")

    elif args.command == "analyses":
        analyses = client.list_analyses()
        if args.json:
            print(json.dumps(analyses, indent=2))
        else:
            for a in analyses:
                print(f"  {a['id']} — {a['company']} / {a['role']}")

    elif args.command == "tailored":
        cvs = client.list_tailored_cvs()
        if args.json:
            print(json.dumps(cvs, indent=2))
        else:
            for cv in cvs:
                print(f"  {cv['title']} @ {cv['company']} — Score: {cv['score']} — {cv.get('yaml_path', '')}")

    elif args.command == "render":
        if not args.yaml:
            print(json.dumps({"error": "--yaml is required for render command"}))
            sys.exit(1)
        result = client.render_cv(args.yaml)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"  Rendered: {result['pdf']}")
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "cover-letter":
        if not args.yaml:
            print(json.dumps({"error": "--yaml with JD text file is required for cover-letter"}))
            sys.exit(1)
        jd_text = Path(args.yaml).read_text(encoding="utf-8")
        result = client.cover_letter(jd_text, cv_path=args.cv or None)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print(result["cover_letter"])
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "question":
        if not args.yaml:
            print(json.dumps({"error": "--yaml with question text file is required for question"}))
            sys.exit(1)
        question_text = Path(args.yaml).read_text(encoding="utf-8")
        jd_text = Path(args.jd).read_text(encoding="utf-8") if args.jd else ""
        result = client.answer_question(question_text, jd_text=jd_text, cv_path=args.cv or None)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print(result["answer"])
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "tailor":
        if not args.yaml:
            print(json.dumps({"error": "--yaml with JD text file path is required for tailor"}))
            sys.exit(1)
        jd_text = Path(args.yaml).read_text(encoding="utf-8")
        result = client.tailor_cv(jd_text, company=args.company or "", title=args.title or "")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print(result.get("output", "Tailored successfully"))
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "analysis":
        if not args.analysis:
            print(json.dumps({"error": "--analysis is required for analysis command"}))
            sys.exit(1)
        result = client.get_job_analysis(args.analysis)
        if args.json:
            print(json.dumps(result or {"error": "Analysis not found"}, indent=2))
        else:
            if result:
                print(f"  Company: {result.get('company_name', '?')}")
                print(f"  Role: {result.get('role_title', '?')}")
            else:
                print(f"  Analysis not found: {args.analysis}")

    elif args.command == "score":
        if not args.analysis:
            print(json.dumps({"error": "--analysis is required for score command"}))
            sys.exit(1)
        analysis = client.get_job_analysis(args.analysis)
        if not analysis:
            print(json.dumps({"error": f"Analysis not found: {args.analysis}"}))
            sys.exit(1)
        jd_text = analysis.get("raw_jd", "") or analysis.get("description", "")
        if not jd_text:
            print(json.dumps({"error": "No job description in analysis"}))
            sys.exit(1)
        result = client.score_job(
            title=analysis.get("role_title", ""),
            company=analysis.get("company_name", ""),
            description=jd_text,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            score = result.get("score", 0)
            print(f"  Score: {score}/100")

    elif args.command == "ghost":
        if not args.yaml:
            print(json.dumps({"error": "--yaml with PDF path is required for ghost command"}))
            sys.exit(1)
        result = client.inject_ghost(
            args.yaml,
            jd_text=Path(args.jd).read_text(encoding="utf-8") if args.jd else "",
            extra_terms=args.extra or "",
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print(f"  ATS ghost injected: {result.get('terms_injected', 0)} terms")
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "review":
        if not args.yaml:
            print(json.dumps({"error": "--yaml with YAML path and --jd with JD file are required for review"}))
            sys.exit(1)
        jd_text = Path(args.jd).read_text(encoding="utf-8") if args.jd else ""
        if not jd_text:
            print(json.dumps({"error": "Job description file required (--jd)"}))
            sys.exit(1)
        result = client.review_cv(args.yaml, jd_text, single=args.single)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            review = result.get("review", {})
            if review:
                print(f"  Score: {review.get('overall_score', '?')}/100")
                print(f"  Approved: {result.get('approved', False)}")
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

    elif args.command == "subscribe":
        if not args.subscribe:
            print(json.dumps({"error": "--subscribe with phone number is required"}))
            sys.exit(1)
        config_subs = config._data.get("bridge", {})
        whatsapp_subs = config_subs.get("whatsapp", {}).get("notify_numbers", [])
        phone = args.subscribe
        if phone not in whatsapp_subs:
            whatsapp_subs.append(phone)
            config_subs.setdefault("whatsapp", {})["notify_numbers"] = whatsapp_subs
            if "bridge" not in config._data:
                config._data["bridge"] = {}
            config._data["bridge"] = config_subs
            config.save()
        print(json.dumps({"success": True, "subscribed": phone, "all_subscribers": whatsapp_subs}))

    elif args.command == "unsubscribe":
        if not args.unsubscribe:
            print(json.dumps({"error": "--unsubscribe with phone number is required"}))
            sys.exit(1)
        config_subs = config._data.get("bridge", {})
        whatsapp_subs = config_subs.get("whatsapp", {}).get("notify_numbers", [])
        phone = args.unsubscribe
        if phone in whatsapp_subs:
            whatsapp_subs.remove(phone)
            config_subs.setdefault("whatsapp", {})["notify_numbers"] = whatsapp_subs
            config._data["bridge"] = config_subs
            config.save()
        print(json.dumps({"success": True, "unsubscribed": phone, "all_subscribers": whatsapp_subs}))

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
