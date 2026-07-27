from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.config import config


def _opencode_run(prompt: str, timeout_s: int = 120) -> tuple[bool, str]:
    opencode_bin = config.opencode_bin()
    if not opencode_bin.exists():
        return False, f"opencode not found at {opencode_bin}"

    env = {**config.env(), "OPENCODE_CLI_DISABLE_ANIMATION": "true"}
    chameleon_root = Path(__file__).resolve().parent.parent

    try:
        proc = subprocess.Popen(
            [str(opencode_bin), "run", prompt],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=str(chameleon_root), env=env,
        )
    except FileNotFoundError:
        return False, f"opencode binary not executable at {opencode_bin}"

    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        return False, f"opencode timed out after {timeout_s}s"
    except Exception as e:
        proc.kill()
        proc.wait(timeout=5)
        return False, str(e)

    if proc.returncode != 0:
        return False, (err or f"opencode exited non-zero ({proc.returncode})").strip()[:200]
    out = (out or "").strip()
    if not out:
        return False, (err or "opencode produced no output").strip()[:200]
    return True, out


QUESTION_PROMPT = """Answer the following job application question in exactly 1 paragraph.
Write in simple, direct first-person language grounded in the resume and job context provided.
Answer the question directly in the first sentence.
Use assertive framing when supported, prefer one strong impact detail over a stack list.
Do not turn the answer into a cover letter, resume summary, or ATS keyword dump.

## QUESTION
{question_text}

## JOB DESCRIPTION
{jd_text}

## RESUME YAML
{cv_yaml}

Return ONLY the answer paragraph — no greeting, no sign-off, no markdown.
"""


def answer_question(question_text: str, jd_text: str, cv_path: str | Path) -> dict:
    cv_yaml = Path(cv_path).read_text(encoding="utf-8")
    prompt = QUESTION_PROMPT.format(
        question_text=question_text.strip(),
        jd_text=jd_text.strip() if jd_text else "(not provided)",
        cv_yaml=cv_yaml,
    )
    success, result = _opencode_run(prompt)
    if success:
        return {"success": True, "answer": result}
    return {"success": False, "error": result}


def main():
    ap = argparse.ArgumentParser(description="Answer a screening question from JD + CV")
    ap.add_argument("question_file", help="Path to file containing the question text")
    ap.add_argument("--jd", "-j", default=None, help="Path to job description text file (optional)")
    ap.add_argument("--cv", "-c", default=None, help="Path to CV YAML (default: master CV from config)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    question_text = Path(args.question_file).read_text(encoding="utf-8").strip()
    jd_text = Path(args.jd).read_text(encoding="utf-8") if args.jd else ""
    cv_path = args.cv or config.master_cv_path()

    result = answer_question(question_text, jd_text, cv_path)

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            print(result["answer"])
        else:
            print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
