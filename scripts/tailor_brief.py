"""
Tailoring Brief Engine — deep algorithmic analysis of JD vs CV + repos.
Produces a comprehensive TailoringBrief with experience mapping,
repo analysis, gap detection, and highlight suggestions.
0 hardcoded — all driven from profile + CV + config.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.config import config
from scripts.job_matcher import (
    load_profile, _build_dynamic_patterns, _build_cv_keywords,
    extract_job_signals, find_matching_repos, _build_full_tech_profile,
)


def load_cv_yaml(path: Path | None = None) -> dict:
    """Load and parse the master CV YAML."""
    path = path or config.master_cv_path()
    if not path.exists():
        return {}
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def analyze_seniority(jd_text: str) -> dict:
    """Deep seniority analysis from JD text."""
    lower = jd_text.lower()
    signals = {
        "level": "mid",
        "years_required": 0,
        "leadership": False,
        "mentorship": False,
        "autonomy": False,
        "confidence": 0.0,
    }
    # Extract years
    years = re.findall(r"(\d+)\+?\s*(?:years|yrs)", lower)
    if years:
        signals["years_required"] = max(int(y) for y in years)

    # Level indicators
    if re.search(r"\bsenior\b|\bsr\.?\b|\bstaff\b|\blead\b|\bprincipal\b", lower):
        signals["level"] = "senior"
        signals["confidence"] += 0.4
    if re.search(r"\bjunior\b|\bentry.?level\b|\bintern\b", lower):
        signals["level"] = "junior"
        signals["confidence"] += 0.3
    if re.search(r"\bmid.?level\b|\bintermediate\b", lower):
        signals["level"] = "mid"
        signals["confidence"] += 0.2
    if re.search(r"\blead\b|\bhead\b|\bmanager\b|\bdirector\b", lower):
        signals["leadership"] = True
        signals["confidence"] += 0.3
    if re.search(r"\bmentor\b|\bcoach\b|\bguide\b", lower):
        signals["mentorship"] = True
        signals["confidence"] += 0.2
    if re.search(r"\bself.?starter\b|\bindependent\b|\bautonomous\b|\bownership\b", lower):
        signals["autonomy"] = True
        signals["confidence"] += 0.2
    if re.search(r"\b5\s*\+?\s*years?\b|\b7\s*\+?\s*years?\b|\b10\s*\+?\s*years?\b", lower):
        signals["level"] = "senior"
        signals["confidence"] = max(signals["confidence"], 0.6)
    return signals


def extract_jd_sections(jd_text: str) -> dict:
    """Split JD into sections (about, requirements, responsibilities, etc.)."""
    lower = jd_text.lower()
    sections: dict[str, str] = {"full_text": jd_text}
    # Common section headers in JDs
    # Headers frequently have content on the same line (for example,
    # ``Requirements: Python, Docker``), so do not require a second newline.
    # Keep matches anchored to line starts to avoid classifying prose as a section.
    patterns = [
        (r"(?im)^[ \t]*(about the company|our company|the company)\s*:?[ \t]*", "company_about"),
        (r"(?im)^[ \t]*(requirements|what you need|qualifications|skills)\s*:?[ \t]*", "requirements"),
        (r"(?im)^[ \t]*(responsibilities|what you.?ll do|role|key duties)\s*:?[ \t]*", "responsibilities"),
        (r"(?im)^[ \t]*(nice to have|bonus|preferred|plus)\s*:?[ \t]*", "bonus"),
        (r"(?im)^[ \t]*(benefits|what we offer|perks)\s*:?[ \t]*", "benefits"),
        (r"(?im)^[ \t]*(about|overview|who we are)\s*:?[ \t]*", "about"),
    ]
    for pat, key in patterns:
        m = re.search(pat, lower)
        if m:
            start = m.end()
            # Find next section or end
            next_pats = [p for p, k in patterns if k != key]
            end = len(jd_text)
            for np, _ in patterns:
                nm = re.search(np, lower[start:])
                if nm:
                    end = min(end, start + nm.start())
            sections[key] = jd_text[m.start():end].strip()
    return sections


def analyze_experience_relevance(
    cv: dict, signals: dict, jd_text: str
) -> list[dict]:
    """Score each experience entry against the JD."""
    experiences = cv.get("cv", {}).get("sections", {}).get("experience", [])
    results: list[dict] = []
    lower = jd_text.lower()

    for exp in experiences:
        company = exp.get("company", "Unknown")
        position = exp.get("position", "")
        highlights = exp.get("highlights", [])
        highlight_text = " ".join(h.lower() for h in highlights)
        exp_text = f"{position.lower()} {highlight_text}"

        # Score relevance
        lang_matches = sum(1 for l in signals.get("languages", []) if l in exp_text)
        fw_matches = sum(1 for f in signals.get("frameworks", []) if f in exp_text)
        dom_matches = sum(1 for d in signals.get("domains", []) if d in exp_text)
        total_keywords = lang_matches + fw_matches + dom_matches

        # Find specific keywords from JD that appear in this experience
        matching_keywords: list[str] = []
        for kw in re.findall(r"\b[a-z][a-z0-9+#.-]{2,}\b", lower):
            if kw in exp_text and len(kw) > 2:
                matching_keywords.append(kw)

        # Score 0-100
        max_possible = max(len(signals.get("languages", [])) * 2, 1)
        max_possible = max(max_possible, 1)  # prevent ZeroDivisionError
        relevance_score = min(int((total_keywords / max_possible) * 100), 100)

        results.append({
            "company": company,
            "position": position,
            "relevance_score": relevance_score,
            "keyword_matches": matching_keywords[:10],
            "highlight_count": len(highlights),
            "suggested_order_priority": 0,
            "highlights_analysis": [
                {
                    "text": h,
                    "relevance": sum(1 for kw in matching_keywords if kw in h.lower()),
                    "jd_language_alignment": _compute_alignment(h, lower),
                }
                for h in highlights
            ],
        })

    # Rank by relevance
    results.sort(key=lambda x: -x["relevance_score"])
    for i, r in enumerate(results):
        r["suggested_order_priority"] = i + 1
    return results


def _compute_alignment(text: str, jd_lower: str) -> float:
    """Compute how well a highlight aligns with JD language (0.0-1.0)."""
    words = set(re.findall(r"\b[a-z][a-z0-9+#.-]{2,}\b", text.lower()))
    jd_words = set(re.findall(r"\b[a-z][a-z0-9+#.-]{2,}\b", jd_lower))
    if not words:
        return 0.0
    overlap = words & jd_words
    return len(overlap) / max(len(words), 1)


def find_gaps(signals: dict, cv: dict) -> list[dict]:
    """Find gaps between JD requirements and CV content."""
    cv_text = json.dumps(cv).lower() if cv else ""
    jd_terms = set(
        signals.get("languages", []) + signals.get("frameworks", [])
        + signals.get("domains", [])
    )
    gaps: list[dict] = []
    for term in jd_terms:
        if term not in cv_text:
            gaps.append({
                "term": term,
                "category": (
                    "language" if term in signals.get("languages", [])
                    else "framework" if term in signals.get("frameworks", [])
                    else "domain"
                ),
                "severity": "high" if term in signals.get("languages", []) else "medium",
                "mitigation": "Use adjacent experience" if term in _get_adjacent_terms(cv, term) else "Cannot fabricate — omit",
            })
    return gaps


def _get_adjacent_terms(cv: dict, term: str) -> set[str]:
    """Check if a close-adjacent term exists in the CV."""
    cv_text = json.dumps(cv).lower()
    adj_map = {
        "react": ["vue", "vue.js", "typescript", "javascript"],
        "angular": ["vue", "vue.js", "typescript"],
        "next.js": ["nuxt", "nuxt.js", "vue"],
        "django": ["fastapi", "python"],
        "flask": ["fastapi", "python"],
        "express": ["fastapi", "python", "node.js"],
        "svelte": ["vue", "javascript", "typescript"],
        "pytorch": ["langchain", "crewai", "ai", "ml", "rag"],
        "tensorflow": ["langchain", "crewai", "ai", "ml", "rag"],
        "aws": ["azure", "docker", "kubernetes", "s3", "ec2"],
        "gcp": ["azure", "docker", "kubernetes"],
        "mysql": ["postgresql", "sqlite"],
        "mongodb": ["postgresql", "sqlite", "redis"],
        "graphql": ["rest", "rest api", "api"],
        "kubernetes": ["docker", "docker-compose", "containerized"],
    }
    for adj in adj_map.get(term, []):
        if adj in cv_text:
            return {adj}
    return set()


def analyze_repos_for_jd(profile: dict, signals: dict) -> list[dict]:
    """Deep repo analysis — find which repos map to which JD needs."""
    results: list[dict] = []
    job_langs = set(signals.get("languages", []))
    job_fws = set(signals.get("frameworks", []))
    job_domains = set(signals.get("domains", []))

    for repo in profile.get("repos", []):
        name = repo.get("name", "")
        lang = (repo.get("language") or "").lower()
        techs = set(t.lower() for t in repo.get("tech_stack_inferred", []))
        domains = set(d.lower() for d in repo.get("domains", []))
        desc = repo.get("description") or repo.get("summary", "") or ""

        lang_overlap = (job_langs & techs) or (lang and lang in job_langs)
        fw_overlap = bool(job_fws & techs)
        dom_overlap = bool(job_domains & domains)
        score = int(bool(lang_overlap)) + int(fw_overlap) + int(dom_overlap)

        if score > 0:
            matched_terms = list(
                (job_langs & techs) | (job_fws & techs) | (job_domains & domains)
            )
            # Suggest CV highlight angle based on repo
            suggestion = _suggest_repo_highlight(name, desc, matched_terms, signals)
            results.append({
                "repo_name": name,
                "language": lang,
                "match_score": score,
                "matched_terms": matched_terms,
                "description": desc,
                "suggested_highlight_for_cv": suggestion,
            })

    results.sort(key=lambda x: -x["match_score"])
    return results[: config.get("max_matching_repos", 5)]


def _suggest_repo_highlight(
    name: str, desc: str, terms: list[str], signals: dict
) -> str:
    """Suggest a CV highlight angle based on repo match."""
    domains = signals.get("domains", [])
    lang_str = ", ".join(terms[:3]) if terms else "relevant technologies"
    domain_hint = f" in {domains[0]}" if domains else ""
    return f"Built {name} using {lang_str}{domain_hint} — {desc[:100] if desc else 'hands-on implementation'}"


def generate_brief(
    jd_text: str,
    profile: dict,
    cv: dict,
) -> dict:
    """Generate the complete TailoringBrief."""

    signals = extract_job_signals(jd_text, profile)
    seniority = analyze_seniority(jd_text)
    jd_sections = extract_jd_sections(jd_text)
    experience_analysis = analyze_experience_relevance(cv, signals, jd_text)
    gaps = find_gaps(signals, cv)
    matching_repos = find_matching_repos(signals, profile)
    repo_analysis = analyze_repos_for_jd(profile, signals)
    cv_keywords = _build_cv_keywords(config.master_cv_path())

    # Compute alignment score (0-100)
    # Part 1: what fraction of CV keywords appear in the JD (0-50)
    kw_matches = sum(1 for kw in cv_keywords if kw in jd_text.lower())
    kw_ratio = kw_matches / max(len(cv_keywords), 1)
    # Part 2: how many distinct signal categories are represented (0-50)
    lang_count = len(signals.get("languages", []))
    fw_count = len(signals.get("frameworks", []))
    dom_count = len(signals.get("domains", []))
    signal_categories = sum(1 for c in (lang_count, fw_count, dom_count) if c > 0)
    signal_score = (signal_categories / 3) * 50
    alignment_score = min(int(kw_ratio * 50 + signal_score), 100)

    return {
        "summary": {
            "target_role": _extract_role(jd_text),
            "target_company": _extract_company(jd_text),
            "alignment_score": alignment_score,
            "seniority": seniority,
            "signal_count": {
                "languages": signals.get("languages", []),
                "frameworks": signals.get("frameworks", []),
                "domains": signals.get("domains", []),
            },
        },
        "jd_sections": {k: v[:500] for k, v in jd_sections.items() if k != "full_text"},
        "experience_analysis": experience_analysis,
        "gaps": gaps,
        "matching_repos": matching_repos,
        "repo_analysis": repo_analysis,
        "keywords": cv_keywords[:50],
    }


def _extract_role(text: str) -> str:
    lines = text.strip().split("\n")
    return lines[0][:100] if lines else "Unknown Role"


def _extract_company(text: str) -> str:
    for line in text.split("\n")[:10]:
        lower = line.lower().strip()
        if lower.startswith("company:"):
            return line.split(":", 1)[1].strip()
        # Match " at CompanyName" only at start or after a space, not inside words
        import re as _re
        m = _re.search(r"(?:^|\s)at\s+([A-Z][^\n-]{2,40})", line)
        if m:
            return m.group(1).strip()
    return "Unknown Company"


def render_brief_text(brief: dict) -> str:
    """Render the TailoringBrief as formatted text for the opencode prompt."""
    lines: list[str] = []
    s = brief["summary"]
    lines.append("=" * 72)
    lines.append(f"TAILORING BRIEF: {s['target_role']} @ {s['target_company']}")
    lines.append(f"Alignment Score: {s['alignment_score']}/100")
    lines.append(f"Seniority: {s['seniority']['level']} ({s['seniority']['years_required']}yrs req)")
    lines.append(f"Signals — Languages: {', '.join(s['signal_count']['languages'][:8]) or 'none found'}")
    lines.append(f"Signals — Frameworks: {', '.join(s['signal_count']['frameworks'][:8]) or 'none found'}")
    lines.append(f"Signals — Domains: {', '.join(s['signal_count']['domains'][:6]) or 'none found'}")
    lines.append("=" * 72)

    # Experience analysis
    lines.append("\n--- EXPERIENCE RELEVANCE MAPPING ---")
    for exp in brief.get("experience_analysis", []):
        lines.append(f"\n[{exp['suggested_order_priority']}] {exp['company']} — {exp['position']}")
        lines.append(f"    Relevance: {exp['relevance_score']}/100 | Priority in CV: {exp['suggested_order_priority']}")
        lines.append(f"    Keyword overlap: {', '.join(exp['keyword_matches'][:6]) or 'none'}")
        for ha in exp.get("highlights_analysis", []):
            alignment = "✓" if ha.get("jd_language_alignment", 0) > 0.3 else "△" if ha.get("jd_language_alignment", 0) > 0.1 else "✗"
            lines.append(f"    [{alignment}] {ha['text'][:80]}...")

    # Matching repos
    lines.append("\n--- MATCHING REPOS & CV HIGHLIGHT SUGGESTIONS ---")
    for ra in brief.get("repo_analysis", []):
        lines.append(f"\n  [{ra['match_score']}] {ra['repo_name']} ({ra['language']})")
        lines.append(f"      Matches: {', '.join(ra['matched_terms'][:5])}")
        lines.append(f"      CV Angle: {ra['suggested_highlight_for_cv'][:120]}")

    # Gaps
    gaps = brief.get("gaps", [])
    if gaps:
        lines.append("\n--- GAPS (JD terms NOT in CV) ---")
        for g in gaps:
            lines.append(f"  [{g['severity']}] {g['term']} ({g['category']}) — {g['mitigation']}")
    else:
        lines.append("\n--- GAPS: None detected ---")

    lines.append("\n--- PRIORITY KEYWORDS FOR ATS ---")
    for kw in brief.get("keywords", [])[:20]:
        lines.append(f"  • {kw}")

    return "\n".join(lines)
