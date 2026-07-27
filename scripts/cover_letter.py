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


COVER_LETTER_PROMPT = """Write a concise, first-person cover letter for a job application.

## Rules
- Default to exactly 2 paragraphs.
- Start with "Hey,"
- End with "Regards," and "David"
- Write in simple, direct first-person language grounded in the selected resume and job description.
- Lead with the strongest fit and one concrete impact detail when possible.
- Do not turn the letter into a stack list, ATS keyword dump, or generic enthusiasm.
- Do not use markdown formatting in the cover letter text.

## JOB DESCRIPTION
{jd_text}

## RESUME YAML
{cv_yaml}

Return ONLY the cover letter text with exactly 2 paragraphs, starting with "Hey," and ending with "Regards,\nDavid".
"""


def generate_cover_letter(jd_text: str, cv_path: str | Path) -> dict:
    cv_yaml = Path(cv_path).read_text(encoding="utf-8")
    prompt = COVER_LETTER_PROMPT.format(jd_text=jd_text.strip(), cv_yaml=cv_yaml)
    success, result = _opencode_run(prompt)
    if success:
        return {"success": True, "cover_letter": result}
    return {"success": False, "error": result}


def main():
    ap = argparse.ArgumentParser(description="Generate a cover letter from JD + CV")
    ap.add_argument("jd_file", help="Path to job description text file")
    ap.add_argument("--cv", "-c", default=None, help="Path to CV YAML (default: master CV from config)")
    ap.add_argument("--company", help="Company name")
    ap.add_argument("--title", help="Role title")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    jd_text = Path(args.jd_file).read_text(encoding="utf-8")
    cv_path = args.cv or config.master_cv_path()

    result = generate_cover_letter(jd_text, cv_path)

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        if result.get("success"):
            print(result["cover_letter"])
        else:
            print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
