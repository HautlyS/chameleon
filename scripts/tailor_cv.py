"""
Chameleon CV Tailor — three-pass pipeline:
1. Algorithmic TailoringBrief (deep JD analysis + experience mapping + repo matching)
2. One-shot AI tailor (opencode run → tailored YAML)
3. AI review pass (opencode run → alignment audit + corrections)
4. Render (rendercv → PDF)

0 hardcoded — all driven from profile, CV, and config.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yaml

from scripts.config import config
from scripts.tailor_brief import (
    generate_brief,
    load_cv_yaml,
    render_brief_text,
)
from scripts.tailor_prompts import TAILOR_PROMPT, REVIEW_PROMPT, FIX_PROMPT
# ats_ghost is imported lazily in tailor_and_render (optional, requires pypdf)

# ── Global subprocess registry for kill-on-shutdown ────────────────────────
_running_processes: list[subprocess.Popen] = []
_processes_lock = threading.Lock()


def _track_process(proc: subprocess.Popen) -> None:
    with _processes_lock:
        _running_processes.append(proc)


def _untrack_process(proc: subprocess.Popen) -> None:
    with _processes_lock:
        try:
            _running_processes.remove(proc)
        except ValueError:
            pass


def kill_all_processes() -> None:
    """Kill every tracked subprocess. Safe to call from any thread."""
    with _processes_lock:
        for proc in _running_processes:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        _running_processes.clear()


_running = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _opencode_run(prompt: str, timeout_s: int = 120) -> tuple[bool, str]:
    """Run opencode with a one-shot prompt. Returns (success, response_text).

    The subprocess is registered in the global kill registry so it can be
    aborted on crash/shutdown from any thread.
    """
    opencode_bin = config.opencode_bin()
    if not opencode_bin.exists():
        return False, f"opencode not found at {opencode_bin}"

    env = {
        **config.env(),
        "OPENCODE_CLI_DISABLE_ANIMATION": "true",
    }

    # Always run opencode from the chameleon project root so it finds config
    chameleon_root = Path(__file__).resolve().parent.parent

    try:
        proc = subprocess.Popen(
            [str(opencode_bin), "run", prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(chameleon_root),
            env=env,
        )
    except FileNotFoundError:
        return False, f"opencode binary not executable at {opencode_bin}"

    _track_process(proc)
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
    finally:
        _untrack_process(proc)

    if proc.returncode != 0:
        stderr = (err or "").strip()
        return False, (stderr or f"opencode exited non-zero ({proc.returncode})")[:200]
    out = (out or "").strip()
    if not out:
        return False, (err or "opencode produced no output").strip()[:200]
    return True, out


def _extract_yaml_from_response(text: str) -> str:
    """Extract YAML from a response that may contain markdown fences or file paths."""
    # Case 1: the AI wrote a file and tells us the path
    m = re.search(r"(?:written to|saved to|saved at|saved as|→|->)[\s:]*`?([^\s`]+\.yaml)`?", text, re.IGNORECASE)
    if m:
        path_candidate = m.group(1).strip().strip("'\"")
        p = Path(path_candidate)
        if p.exists():
            return p.read_text()
        p2 = Path.cwd() / path_candidate
        if p2.exists():
            return p2.read_text()

    # Case 2: between ```yaml fences
    m = re.search(r"```(?:yaml)?\s*\n(.+?)\n```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Case 3: between plain ``` fences that happen to be YAML
    m = re.search(r"```\s*\n(cv:.+?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Case 4: content starting with cv: (multiline)
    m = re.search(r"(?:^|\n)(cv:[\s\S]*)", text)
    if m:
        return m.group(1).strip()

    return text.strip()


def _extract_json_from_response(text: str) -> dict | None:
    """Extract JSON from a response that may have markdown fences."""
    m = re.search(r"```(?:json)?\s*\n(.+?)\n```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find {...} in the response
        m2 = re.search(r"(\{.*\})", raw, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Pass 1: Algorithmic Tailoring Brief
# ---------------------------------------------------------------------------


def build_tailoring_brief(
    jd_text: str, profile: dict | None = None
) -> dict:
    """Build a comprehensive TailoringBrief from JD + profile."""
    cv = load_cv_yaml(config.master_cv_path())
    if profile is None:
        from scripts.job_matcher import load_profile
        profile = load_profile()
    brief = generate_brief(jd_text, profile, cv)
    return brief


# ---------------------------------------------------------------------------
# Pass 2: One-shot AI Tailor via opencode
# ---------------------------------------------------------------------------

_TAILOR_RETRIES = 2


def ai_tailor(jd_text: str, brief_text: str, cv_yaml: str) -> tuple[bool, str]:
    """Run one-shot opencode tailor. Returns (success, tailored_yaml)."""
    prompt = TAILOR_PROMPT.format(cv_yaml=cv_yaml, brief_text=brief_text)
    for attempt in range(1 + _TAILOR_RETRIES):
        ok, response = _opencode_run(prompt, timeout_s=180)
        if not ok:
            if attempt < _TAILOR_RETRIES:
                continue
            return False, f"opencode call failed: {response}"

        yaml_text = _extract_yaml_from_response(response)
        if not yaml_text.startswith("cv:"):
            if attempt < _TAILOR_RETRIES:
                continue
            return False, f"Response does not start with 'cv:':\n{yaml_text[:200]}"

        # Validate it parses as YAML
        try:
            parsed = yaml.safe_load(yaml_text)
            if not parsed or "cv" not in parsed:
                if attempt < _TAILOR_RETRIES:
                    continue
                return False, "Parsed YAML missing 'cv' top-level key"
        except Exception as e:
            if attempt < _TAILOR_RETRIES:
                continue
            return False, f"YAML parse failed: {e}"

        return True, yaml_text

    return False, "Max retries exceeded"


# ---------------------------------------------------------------------------
# Pass 3: AI Review Pass
# ---------------------------------------------------------------------------

_REVIEW_RETRIES = 2
_REVIEW_MIN_SCORE = 70


def ai_review(jd_text: str, tailored_yaml: str) -> tuple[bool, dict | None, str | None]:
    """Run one-shot opencode review. Returns (approved, review_json, corrections_text)."""
    prompt = REVIEW_PROMPT.format(jd_text=jd_text, tailored_yaml=tailored_yaml)
    for attempt in range(1 + _REVIEW_RETRIES):
        ok, response = _opencode_run(prompt, timeout_s=120)
        if not ok:
            if attempt < _REVIEW_RETRIES:
                continue
            return False, None, f"Review call failed: {response}"

        review = _extract_json_from_response(response)
        if not review:
            if attempt < _REVIEW_RETRIES:
                continue
            return False, None, f"Could not parse review JSON:\n{response[:300]}"

        score = review.get("overall_score", 0)
        approved = score >= _REVIEW_MIN_SCORE and not review.get("fabrication_concerns")
        review["approved"] = approved

        corrections = review.get("corrections_needed", [])
        corrections_text = json.dumps(corrections, indent=2) if corrections else None

        return approved, review, corrections_text

    return False, None, "Max review retries exceeded"


def double_review(jd_text: str, tailored_yaml: str) -> tuple[bool, dict, str | None]:
    """Run two independent reviews + optional tiebreaker.

    Returns (approved, consolidated_review, corrections_text).
    The consolidated review takes the lower score and the union of corrections.
    """
    # Run two reviews
    r1_ok, r1, c1 = ai_review(jd_text, tailored_yaml)
    r2_ok, r2, c2 = ai_review(jd_text, tailored_yaml)

    reviews = []
    if r1_ok and r1:
        reviews.append(r1)
    if r2_ok and r2:
        reviews.append(r2)

    if not reviews:
        return False, {"overall_score": 0, "approved": False}, None

    # Consolidate — take the lower/more conservative score
    scores = [r.get("overall_score", 0) for r in reviews]
    final_score = min(scores)
    tiebreaker_needed = max(scores) - min(scores) > 15

    # If scores diverge by >15, run tiebreaker
    if tiebreaker_needed and len(reviews) == 2:
        _, r3, c3 = ai_review(jd_text, tailored_yaml)
        if r3:
            reviews.append(r3)
            scores.append(r3.get("overall_score", 0))
            final_score = sorted(scores)[len(scores) // 2]  # median

    # Merge corrections (union)
    all_corrections: list[dict] = []
    seen_corrections: set[str] = set()
    for r in reviews:
        for corr in r.get("corrections_needed", []):
            key = json.dumps(corr, sort_keys=True)
            if key not in seen_corrections:
                seen_corrections.add(key)
                all_corrections.append(corr)

    # Merge missing terms (union)
    all_missing: list[str] = []
    seen_missing: set[str] = set()
    for r in reviews:
        for term in r.get("missing_terms", []):
            if term.lower() not in seen_missing:
                seen_missing.add(term.lower())
                all_missing.append(term)

    # Merge gaps (union)
    all_gaps: list[dict] = []
    seen_gaps: set[str] = set()
    for r in reviews:
        for gap in r.get("alignment_gaps", []):
            key = json.dumps(gap, sort_keys=True)
            if key not in seen_gaps:
                seen_gaps.add(key)
                all_gaps.append(gap)

    # Take the most conservative fabrication concerns
    all_concerns: list[str] = []
    seen_concerns: set[str] = set()
    for r in reviews:
        for c in r.get("fabrication_concerns", []):
            if c.lower() not in seen_concerns:
                seen_concerns.add(c.lower())
                all_concerns.append(c)

    approved = final_score >= _REVIEW_MIN_SCORE and not all_concerns

    # Per-section scores: take the lower score for each section
    by_section = {}
    section_keys = ["summary", "skills", "experience", "projects"]
    for sk in section_keys:
        sec_scores = [r.get("by_section", {}).get(sk, 0) for r in reviews if r.get("by_section")]
        by_section[sk] = min(sec_scores) if sec_scores else 0

    consolidated = {
        "overall_score": final_score,
        "by_section": by_section,
        "missing_terms": all_missing,
        "present_terms": reviews[0].get("present_terms", []) if reviews else [],
        "alignment_gaps": all_gaps,
        "fabrication_concerns": all_concerns,
        "corrections_needed": all_corrections,
        "approved": approved,
        "_scores": scores,
        "_tiebreaker": tiebreaker_needed,
    }

    corrections_text = json.dumps(all_corrections, indent=2) if all_corrections else None
    return approved, consolidated, corrections_text


def apply_corrections(tailored_yaml: str, corrections_text: str) -> str:
    """Apply corrections via opencode fix pass."""
    prompt = FIX_PROMPT.format(
        corrections_json=corrections_text,
        tailored_yaml=tailored_yaml,
    )
    ok, response = _opencode_run(prompt, timeout_s=120)
    if not ok:
        return tailored_yaml
    fixed = _extract_yaml_from_response(response)
    if fixed.startswith("cv:"):
        return fixed
    return tailored_yaml


# ---------------------------------------------------------------------------
# Pass 4: Render
# ---------------------------------------------------------------------------


def _find_rendercv() -> Path | None:
    """Locate the rendercv binary, checking venv, PATH, and common locations."""
    import shutil as _shutil
    chameleon_root = Path(__file__).resolve().parent.parent
    # Check venv first (platform-aware)
    venv_bin = chameleon_root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    ext = ".exe" if sys.platform == "win32" else ""
    rendercv_path = venv_bin / f"rendercv{ext}"
    if rendercv_path.exists():
        return rendercv_path
    # Check if on PATH
    on_path = _shutil.which("rendercv")
    if on_path:
        return Path(on_path)
    return None


def render_yaml(yaml_path: Path) -> tuple[bool, str]:
    """Render YAML to PDF using rendercv. Returns (success, message).

    The subprocess is registered in the global kill registry so it can be
    aborted on crash/shutdown from any thread.
    """
    chameleon_root = Path(__file__).resolve().parent.parent
    rendercv_path = _find_rendercv()
    output_dir = config.output_dir()
    output_dir.mkdir(exist_ok=True)

    if rendercv_path is None:
        return False, "rendercv not found. Run: make install-tools"

    stem = yaml_path.stem
    tmp = Path(yaml_path.name)
    shutil.copy2(yaml_path, tmp)

    try:
        proc = subprocess.Popen(
            [
                str(rendercv_path), "render", str(tmp),
                "--pdf-path", str(output_dir / f"{stem}.pdf"),
                "--typst-path", str(output_dir / f"{stem}.typ"),
                "--markdown-path", str(output_dir / f"{stem}.md"),
                "--html-path", str(output_dir / f"{stem}.html"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(chameleon_root),
        )
    except FileNotFoundError:
        return False, f"rendercv binary not executable at {rendercv_path}"

    _track_process(proc)
    try:
        out, err = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        return False, "Render timeout (60s)"
    except Exception as e:
        proc.kill()
        proc.wait(timeout=5)
        return False, str(e)
    finally:
        _untrack_process(proc)
        tmp.unlink(missing_ok=True)

    if proc.returncode == 0:
        pdf_path = output_dir / f"{stem}.pdf"
        return True, str(pdf_path) if pdf_path.exists() else "Rendered (no PDF)"
    else:
        err = (err or out or "unknown error").strip()[:300]
        return False, err


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def tailor_and_render(
    jd_text: str,
    company: str = "",
    title: str = "",
    profile: dict | None = None,
    skip_review: bool = False,
    skip_render: bool = False,
) -> tuple[bool, str, str]:
    """
    Full three-pass pipeline: Brief → AI Tailor → AI Review → Render.
    Returns (success, message, output_path).
    """
    global _running
    _running = True
    start_ms = _now_ms()

    master_cv_path = config.master_cv_path()
    if not master_cv_path.exists():
        _running = False
        return False, f"Master CV not found: {master_cv_path}", ""

    # Derive company/title from JD text if not provided
    if not company or not title:
        lines = jd_text.strip().split("\n")
        first_line = lines[0].strip() if lines else "Unknown Role"
        if not title:
            title = first_line[:80]
        # Try to find company in first few lines
        for line in lines[1:8]:
            m = re.search(r"(?:at|@|Company[:\s]*)(.+?)(?:\s*[-–—]|\s*$)", line)
            if m:
                company = m.group(1).strip()
                break
        if not company:
            company = "Unknown"

    safe_co = re.sub(r"[^a-zA-Z0-9]", "_", company)[:20]
    safe_role = re.sub(r"[^a-zA-Z0-9]", "_", title)[:20]
    raw = f"{company}{title}".encode()
    try:
        analysis_id = hashlib.md5(raw, usedforsecurity=False).hexdigest()[:8]
    except TypeError:
        analysis_id = hashlib.md5(raw).hexdigest()[:8]
    cv_basename = master_cv_path.stem.replace("_cv", "") or "cv"
    yaml_name = f"{cv_basename}_{safe_co}_{safe_role}_cv.yaml"
    yaml_path = config.templates_dir() / yaml_name

    # ======================================================================
    # PASS 1: Algorithmic Tailoring Brief
    # ======================================================================
    print(f"[1/4] Building TailoringBrief for '{title}' @ '{company}'...", flush=True)
    brief = build_tailoring_brief(jd_text, profile)
    brief_text = render_brief_text(brief)
    print(f"      Alignment: {brief['summary']['alignment_score']}/100 | "
          f"Gaps: {len(brief['gaps'])} | "
          f"Matching repos: {len(brief.get('repo_analysis', []))}", flush=True)

    # Save analysis artifact
    analysis_dir = config.analyses_dir()
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_name = f"{analysis_id}__{safe_co}__{safe_role}.json"
    analysis_path = analysis_dir / analysis_name
    analysis_artifact = {
        "company_name": company,
        "role_title": title,
        "analysis_id": analysis_id,
        "alignment_score": brief["summary"]["alignment_score"],
        "seniority": brief["summary"]["seniority"],
        "signal_count": {
            k: len(v) for k, v in brief["summary"]["signal_count"].items()
        },
        "gaps": brief["gaps"],
        "brief_summary": brief_text[:500],
    }
    try:
        analysis_path.write_text(json.dumps(analysis_artifact, indent=2))
    except Exception:
        pass

    # ======================================================================
    # PASS 2: One-shot AI Tailor
    # ======================================================================
    print(f"[2/4] Running one-shot AI tailor (opencode)...", flush=True)
    cv_yaml = master_cv_path.read_text()
    ok, tailored_yaml = ai_tailor(jd_text, brief_text, cv_yaml)
    if not ok:
        _running = False
        return False, f"AI tailoring failed: {tailored_yaml}", str(analysis_path)

    print(f"      YAML generated ({len(tailored_yaml)} chars)", flush=True)

    # ======================================================================
    # PASS 3: AI Review
    # ======================================================================
    review_result = None
    if not skip_review:
        print(f"[3/4] Running double AI review (opencode x2, tiebreaker if needed)...", flush=True)
        approved, review_result, corrections_text = double_review(jd_text, tailored_yaml)

        if review_result:
            score = review_result.get("overall_score", 0)
            concerns = review_result.get("fabrication_concerns", [])
            gaps_found = review_result.get("alignment_gaps", [])
            missing = review_result.get("missing_terms", [])
            raw_scores = review_result.get("_scores", [score])
            print(f"      Scores: {' + '.join(str(s) for s in raw_scores)} -> final={score}/100", flush=True)
            print(f"      Missing: {len(missing)} | Gaps: {len(gaps_found)} | Concerns: {len(concerns)}", flush=True)

        if corrections_text:
            n_corrections = len(json.loads(corrections_text))
            print(f"      Applying {n_corrections} corrections (union of both reviews)...", flush=True)
            tailored_yaml = apply_corrections(tailored_yaml, corrections_text)
            print(f"      Corrections applied", flush=True)
        elif review_result and not approved and not corrections_text:
            print(f"      Review not approved (score {review_result.get('overall_score', 0)} < {_REVIEW_MIN_SCORE}) but no corrections provided — proceeding with generated YAML", flush=True)
    else:
        print(f"[3/4] Review skipped", flush=True)

    # ======================================================================
    # Write tailored YAML
    # ======================================================================
    yaml_path.write_text(tailored_yaml)
    print(f"      Saved: {yaml_path}", flush=True)

    # ======================================================================
    # PASS 4: Render
    # ======================================================================
    output_path = str(yaml_path)
    ghost_injected = False
    if not skip_render:
        print(f"[4/4] Rendering PDF...", flush=True)
        render_ok, render_msg = render_yaml(yaml_path)
        if render_ok:
            output_path = render_msg
            print(f"      PDF: {render_msg}", flush=True)

            # PASS 5: ATS Ghost Text Injection (if enabled)
            if config.get("ats_ghost_enabled", False):
                pdf_path = Path(render_msg)
                if pdf_path.exists():
                    from scripts.ats_ghost import collect_ats_terms as _collect, inject_ghost_text as _inject
                    extra = config.get("ats_ghost_extra_terms", "")
                    # Collect keywords from signals + gaps + extra terms
                    signal_terms = (
                        brief["summary"]["signal_count"]["languages"]
                        + brief["summary"]["signal_count"]["frameworks"]
                    )
                    gap_terms = [g["term"] for g in brief.get("gaps", [])]
                    existing_kws = list(
                        set(
                            signal_terms + gap_terms
                            + [kw for exp in brief.get("experience_analysis", [])
                               for kw in exp.get("keyword_matches", [])]
                        )
                    )
                    all_terms = _collect(
                        jd_text,
                        extra_terms=extra,
                        existing_keywords=existing_kws,
                    )
                    if all_terms:
                        ok_ghost = _inject(pdf_path, all_terms)
                        ghost_injected = ok_ghost
                        if ok_ghost:
                            print(f"      ATS ghost text injected ({len(all_terms)} terms)", flush=True)
                        else:
                            print(f"      ATS ghost text injection failed", flush=True)
        else:
            print(f"      Render issue: {render_msg}", flush=True)

    elapsed = _now_ms() - start_ms
    _running = False

    summary = (
        f"Tailored in {elapsed/1000:.1f}s\n"
        f"  Analysis: {analysis_path}\n"
        f"  YAML: {yaml_path}\n"
        f"  PDF: {output_path if not skip_render else 'skipped'}\n"
        f"  Alignment: {brief['summary']['alignment_score']}/100"
    )
    if ghost_injected:
        summary += " | ATS ghost: ✓"
    if review_result:
        raw_scores = review_result.get("_scores", [])
        if raw_scores:
            summary += f" | Reviews: {', '.join(str(s) for s in raw_scores)}"
        summary += f" | Final: {review_result.get('overall_score', '?')}/100"
    return True, summary, output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Tailor a CV from job-description text, a file, or a job-posting URL."
    )
    parser.add_argument("jd", nargs="?", help="Job description text, path, or URL")
    parser.add_argument("--company", default="", help="Company name override")
    parser.add_argument("--title", default="", help="Role title override")
    parser.add_argument("--no-review", action="store_true", help="Skip AI review")
    parser.add_argument("--no-render", action="store_true", help="Skip PDF rendering")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parsed = parser.parse_args()

    jd_arg = parsed.jd
    if not jd_arg and not sys.stdin.isatty():
        jd_arg = sys.stdin.read().strip()
    if not jd_arg:
        parser.error("a job description text, file, or URL is required")

    # Handle URL input
    if jd_arg.startswith("http://") or jd_arg.startswith("https://"):
        print("[*] Crawling URL...", file=sys.stderr)
        try:
            import httpx
            resp = httpx.get(jd_arg, timeout=30, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Chameleon/1.0)"
            })
            resp.raise_for_status()
            from html.parser import HTMLParser
            class _TE(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                    self._skip = False
                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style"): self._skip = True
                def handle_endtag(self, tag):
                    if tag in ("script", "style"): self._skip = False
                def handle_data(self, data):
                    if not self._skip: self.parts.append(data)
            te = _TE()
            te.feed(resp.text)
            import re as _re
            desc = _re.sub(r"\s+", " ", " ".join(te.parts)).strip()
        except ImportError:
            import urllib.request
            import re as _re
            import html as _hm
            req = urllib.request.Request(jd_arg, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            raw = _re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=_re.DOTALL | _re.IGNORECASE)
            raw = _re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=_re.DOTALL | _re.IGNORECASE)
            raw = _re.sub(r"<[^>]+>", " ", raw)
            raw = _hm.unescape(raw)
            desc = _re.sub(r"\s+", " ", raw).strip()[:10000]
        except Exception as e:
            print(f"Error crawling URL: {e}", file=sys.stderr)
            sys.exit(1)
    elif Path(jd_arg).is_file():
        desc = Path(jd_arg).read_text()
    else:
        desc = jd_arg

    ok, msg, output_path = tailor_and_render(
        desc,
        company=parsed.company,
        title=parsed.title,
        skip_review=parsed.no_review,
        skip_render=parsed.no_render,
    )

    if not parsed.json:
        # Keep CLI output portable on Windows consoles configured for cp1252.
        print(f"\n{'PASS' if ok else 'FAIL'}: {msg}")
        sys.exit(0 if ok else 1)

    if parsed.json:
        import json as _json
        print(_json.dumps({
            "success": ok,
            "message": msg,
            "output_path": output_path,
        }, indent=2))
    else:
        print(f"\n{'✓' if ok else '✗'} {'PASS' if ok else 'FAIL'}: {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
