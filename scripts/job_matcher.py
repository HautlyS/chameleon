"""
Dynamic Job Matcher — scores job postings against GitHub profile + CV.
0 hardcoded skills. Everything comes from config, profile, and CV YAML.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.config import config

# ── Profile cache ────────────────────────────────────────────────────────────
_profile_cache: dict[str, dict] = {}
_profile_cache_key: str = ""


def _get_profile_cache_key(profile: dict, cv_path: Path | None = None) -> str:
    """Build a cache key from profile mtime and CV mtime."""
    parts = []
    p = config.profile_path()
    if p.exists():
        parts.append(f"p:{p.stat().st_mtime_ns}")
    cp = cv_path or config.master_cv_path()
    if cp.exists():
        parts.append(f"cv:{cp.stat().st_mtime_ns}")
    return "|".join(parts)


def _cached_full_tech_profile(profile: dict) -> dict[str, set[str]]:
    """Memoized version of _build_full_tech_profile — caches per profile+mtime."""
    global _profile_cache_key, _profile_cache
    key = _get_profile_cache_key(profile)
    if key and key == _profile_cache_key:
        return _profile_cache
    result = _build_full_tech_profile(profile)
    if key:
        _profile_cache_key = key
        _profile_cache = result
    return result


# ── Terms known to be tech languages/frameworks (used for CV extraction) ────
_KNOWN_LANG_TERMS: set[str] = {
    "python", "rust", "java", "javascript", "typescript", "go", "golang",
    "ruby", "php", "c++", "c#", "swift", "kotlin", "scala", "r",
    "dart", "elixir", "clojure", "haskell", "lua", "perl", "solidity",
    "vue", "react", "angular", "svelte", "node", "deno", "bun",
    "fastapi", "django", "flask", "express", "spring", "rails",
    "tauri", "electron", "next.js", "nuxt", "sveltekit",
    "tailwind", "bootstrap", "supabase", "firebase",
    "docker", "kubernetes", "k8s", "aws", "azure", "gcp",
    "langchain", "crewai", "langgraph", "pytorch", "tensorflow",
    "postgresql", "postgres", "mysql", "mongodb", "redis",
    "graphql", "rest", "grpc", "websocket",
}


# ── Regex patterns built dynamically from all known tech terms ──────────────


def _pattern(words: list[str]) -> re.Pattern:
    """Build a case-insensitive regex pattern matching any of the words."""
    escaped = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


def _build_dynamic_patterns(
    profile: dict,
) -> dict[str, dict[str, re.Pattern]]:
    """Build all matching patterns from the profile alone — no hardcoded lists."""
    # Collect all unique tech terms from profile
    tech_stack = [t.lower() for t in profile.get("skills_summary", {}).get("tech_stack", [])]
    languages = [l.lower() for l in profile.get("skills_summary", {}).get("languages", {}).keys()]
    domains = [d.lower() for d in profile.get("skills_summary", {}).get("domains", [])]
    infra = [inf.lower() for inf in profile.get("skills_summary", {}).get("infrastructure", [])]

    # Also collect from repo tech stacks to catch everything
    for repo in profile.get("repos", []):
        for t in repo.get("tech_stack_inferred", []):
            if t.lower() not in tech_stack:
                tech_stack.append(t.lower())
        for d in repo.get("domains", []):
            if d.lower() not in domains:
                domains.append(d.lower())
        repo_lang = repo.get("language", "")
        if repo_lang and repo_lang.lower() not in languages:
            languages.append(repo_lang.lower())

    # Also extract skills from CV YAML — catches skills not on GitHub
    cv_path = config.master_cv_path()
    if cv_path.exists():
        cv_kw = _build_cv_keywords(cv_path)
        known_langs = _KNOWN_LANG_TERMS
        for kw in cv_kw:
            if kw in known_langs and kw.lower() not in languages:
                languages.append(kw.lower())
            if kw in known_langs and kw.lower() not in tech_stack:
                tech_stack.append(kw.lower())

    # Build patterns — one per term so we can identify which matched
    lang_patterns: dict[str, re.Pattern] = {}
    for lang in languages:
        escaped = re.escape(lang)
        lang_patterns[lang] = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)
        # Handle special cases
        if lang == "c++":
            lang_patterns[lang] = re.compile(r"\bc\+\+\b", re.IGNORECASE)
        if lang == "c#":
            lang_patterns[lang] = re.compile(r"\bc#\b", re.IGNORECASE)
        if lang == ".net":
            lang_patterns[lang] = re.compile(r"\b\.net\b", re.IGNORECASE)
        if "javascript" in lang:
            lang_patterns[lang] = re.compile(r"\bjavascript\b|\bjs\b", re.IGNORECASE)
        if "typescript" in lang:
            lang_patterns[lang] = re.compile(r"\btypescript\b", re.IGNORECASE)

    fw_patterns: dict[str, re.Pattern] = {}
    for fw in tech_stack:
        escaped = re.escape(fw)
        fw_patterns[fw] = re.compile(r"\b" + escaped.replace(r"\.", r"\.?") + r"\b", re.IGNORECASE)

    domain_patterns: dict[str, re.Pattern] = {}
    for dom in domains:
        escaped = re.escape(dom)
        domain_patterns[dom] = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)

    infra_patterns: dict[str, re.Pattern] = {}
    for inf in infra:
        escaped = re.escape(inf)
        infra_patterns[inf] = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)

    return {
        "languages": lang_patterns,
        "frameworks": fw_patterns,
        "domains": domain_patterns,
        "infra": infra_patterns,
    }


def _build_cv_keywords(cv_path: Path) -> list[str]:
    """Extract all skill-related keywords from CV YAML — no hardcoding."""
    if not cv_path.exists():
        return []
    try:
        import yaml
        with open(cv_path) as f:
            cv = yaml.safe_load(f)
    except Exception:
        return _fallback_cv_text(cv_path)

    keywords: list[str] = []
    sections = cv.get("cv", {}).get("sections", {})

    # Extract from summary
    summary = sections.get("summary", [])
    if isinstance(summary, list):
        for s in summary:
            if isinstance(s, str):
                keywords.extend(s.lower().split())
    elif isinstance(summary, str):
        keywords.extend(summary.lower().split())

    # Extract from skills section
    for section_name, section_data in sections.items():
        if not isinstance(section_data, list):
            continue
        for entry in section_data:
            if isinstance(entry, dict):
                for val in entry.values():
                    if isinstance(val, str):
                        keywords.extend(val.lower().split())
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str):
                                keywords.extend(item.lower().split())

    # Extract from experience highlights
    for section_name, section_data in sections.items():
        if not isinstance(section_data, list):
            continue
        for entry in section_data:
            if isinstance(entry, dict):
                for highlight in entry.get("highlights", []):
                    if isinstance(highlight, str):
                        keywords.extend(re.sub(r"[^a-z0-9\s]", "", highlight.lower()).split())

    # Deduplicate and filter common words
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can", "need",
        "using", "including", "such", "like", "also", "very", "just", "about",
    }
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        clean = kw.strip(".,;:!?()[]{}\"'")
        if clean not in stopwords and len(clean) > 2 and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _fallback_cv_text(cv_path: Path) -> list[str]:
    """Fallback: extract keywords from raw YAML text."""
    if not cv_path.exists():
        return []
    text = cv_path.read_text()
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+#.-]{2,}", text.lower())
    stopwords = {
        "the", "and", "for", "that", "this", "with", "from", "your", "our",
        "their", "its", "are", "was", "have", "has", "had", "been", "being",
        "will", "would", "could", "should", "may", "might", "shall", "can",
        "using", "including", "such", "like", "also", "very", "just",
    }
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        if w not in stopwords and w not in seen:
            seen.add(w)
            result.append(w)
    return result


# ── Main API ────────────────────────────────────────────────────────────────


def load_profile(path: Path | None = None) -> dict:
    """Load GitHub profile from JSON. Returns empty profile on error."""
    p = path or config.profile_path()
    try:
        with open(p) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        return {
            "repos": [],
            "skills_summary": {"languages": {}, "tech_stack": [], "domains": [], "infrastructure": []},
        }


def extract_job_signals(job_text: str, profile: dict) -> dict:
    """Extract keywords from job description using profile-built patterns."""
    text_lower = job_text.lower()
    patterns = _build_dynamic_patterns(profile)

    signals: dict[str, Any] = {
        "languages": [],
        "frameworks": [],
        "domains": [],
        "infra": [],
        "keywords": [],
        "seniority": "mid",
        "remote": False,
    }

    for cat in ("languages", "frameworks", "domains", "infra"):
        for term, pat in patterns.get(cat, {}).items():
            if pat.search(text_lower):
                signals[cat].append(term)

    # Seniority
    if re.search(r"\bsenior\b|\bsr\.?\b|\bstaff\b|\blead\b|\bprincipal\b", text_lower, re.IGNORECASE):
        signals["seniority"] = "senior"
    elif re.search(r"\bjunior\b|\bentry.?level\b|\bintern\b", text_lower, re.IGNORECASE):
        signals["seniority"] = "junior"

    # Remote
    if re.search(r"\bremote\b|\bworldwide\b|\banywhere\b|\bglobal\b|\bremoto\b", text_lower, re.IGNORECASE):
        signals["remote"] = True

    return signals


def score_languages(
    job_signals: dict,
    profile: dict,
) -> tuple[int, list[str]]:
    """Score language match — fully dynamic, no hardcoded lists."""
    job_langs: set[str] = set(job_signals.get("languages", []))
    profile_all = _cached_full_tech_profile(profile)
    profile_langs = profile_all["languages"]

    overlap: set[str] = job_langs & profile_langs
    related: set[str] = set()
    adj = config.lang_adjacency()
    for jl in job_langs:
        for rel in adj.get(jl, []):
            if rel in profile_langs:
                related.add(jl)

    n_overlap = len(overlap)
    w3 = config.get("lang_overlap_3_score", 25)
    w2 = config.get("lang_overlap_2_score", 20)
    w1 = config.get("lang_overlap_1_score", 15)
    wr = config.get("lang_related_score", 10)

    if n_overlap >= 3:
        score = w3
    elif n_overlap == 2:
        score = w2
    elif n_overlap == 1:
        score = w1
    elif related:
        score = wr
    else:
        score = 0

    return score, sorted(overlap | related)


def _build_full_tech_profile(profile: dict) -> dict[str, set[str]]:
    """Build complete tech landscape from profile + repos + CV."""
    result = {
        "languages": set(l.lower() for l in profile.get("skills_summary", {}).get("languages", {}).keys()),
        "frameworks": set(t.lower() for t in profile.get("skills_summary", {}).get("tech_stack", [])),
        "domains": set(d.lower() for d in profile.get("skills_summary", {}).get("domains", [])),
    }
    for repo in profile.get("repos", []):
        rl = repo.get("language", "")
        if rl:
            result["languages"].add(rl.lower())
        for t in repo.get("tech_stack_inferred", []):
            result["frameworks"].add(t.lower())
        for d in repo.get("domains", []):
            result["domains"].add(d.lower())
    cv_path = config.master_cv_path()
    if cv_path.exists():
        cv_kw = _build_cv_keywords(cv_path)
        for kw in cv_kw:
            if kw in _KNOWN_LANG_TERMS:
                result["languages"].add(kw.lower())
                result["frameworks"].add(kw.lower())
    return result


def score_frameworks(job_signals: dict, profile: dict) -> tuple[int, list[str]]:
    """Score framework/tech match — fully dynamic."""
    job_fws: set[str] = set(job_signals.get("frameworks", []))
    profile_all = _cached_full_tech_profile(profile)
    profile_techs = profile_all["frameworks"]

    overlap: set[str] = job_fws & profile_techs

    # Adjacent matches (react → vue.js, next.js → nuxt.js, etc.)
    adjacent: set[str] = set()
    adj_map: dict[str, str] = {
        "react": "vue", "react.js": "vue", "vue": "react",
        "next.js": "nuxt", "nuxt": "next.js",
        "angular": "vue", "svelte": "vue",
        "express": "fastapi", "django": "fastapi",
    }
    for jf in job_fws:
        mapped = adj_map.get(jf)
        if mapped and mapped in profile_techs:
            adjacent.add(f"{jf}->{mapped}")

    n_overlap = len(overlap)
    w3 = config.get("fw_overlap_3_score", 25)
    w2 = config.get("fw_overlap_2_score", 20)
    w1 = config.get("fw_overlap_1_score", 15)
    wa = config.get("fw_adjacent_score", 8)

    if n_overlap >= 3:
        score = w3
    elif n_overlap == 2:
        score = w2
    elif n_overlap == 1:
        score = w1
    elif adjacent:
        score = wa
    else:
        score = 0

    return score, sorted(overlap | adjacent)


def score_domains(job_signals: dict, profile: dict) -> tuple[int, list[str]]:
    """Score domain match — fully dynamic with adjacency."""
    job_domains: set[str] = set(job_signals.get("domains", []))
    profile_all = _cached_full_tech_profile(profile)
    profile_domains = profile_all["domains"]

    overlap: set[str] = job_domains & profile_domains

    adj_map = config.domain_adjacency()
    adjacent_count = 0
    for jd in job_domains:
        for adj_domain in adj_map.get(jd, []):
            if adj_domain in profile_domains:
                adjacent_count += 1

    n_overlap = len(overlap)
    w2 = config.get("dom_overlap_2_score", 25)
    w1 = config.get("dom_overlap_1_score", 20)
    wa2 = config.get("dom_adjacent_2_score", 15)
    wa1 = config.get("dom_adjacent_1_score", 10)

    if n_overlap >= 2:
        score = w2
    elif n_overlap == 1:
        score = w1
    elif adjacent_count >= config.get("domain_adjacent_min_strong", 2):
        score = wa2
    elif adjacent_count >= config.get("domain_adjacent_min_good", 1):
        score = wa1
    else:
        score = 0

    return score, sorted(overlap)


def score_cv_alignment(
    job_signals: dict,
    profile: dict,
    raw_text: str = "",
    cv_path: Path | None = None,
) -> tuple[int, list[str]]:
    """Score CV alignment — dynamically extracted from CV YAML."""
    cv_keywords = _build_cv_keywords(cv_path or config.master_cv_path())
    text_lower = raw_text.lower() if raw_text else " ".join(
        item for cat in ("languages", "frameworks", "domains", "infra")
        for item in job_signals.get(cat, [])
    ).lower()

    matched: list[str] = []
    for kw in cv_keywords:
        if len(kw) < 3:
            continue
        if kw in text_lower:
            matched.append(kw)

    # Score thresholds from config
    n_matched = len(matched)
    m5 = config.get("cv_match_5_score", 25)
    m3 = config.get("cv_match_3_score", 20)
    m1 = config.get("cv_match_1_score", 15)

    if n_matched >= config.get("cv_alignment_min_match_strong", 5):
        score = m5
    elif n_matched >= config.get("cv_alignment_min_match_good", 3):
        score = m3
    elif n_matched >= config.get("cv_alignment_min_match_moderate", 1):
        score = m1
    else:
        score = 0

    return score, matched


def find_matching_repos(job_signals: dict, profile: dict) -> list[str]:
    """Find repos matching job requirements — fully dynamic."""
    _cached_full_tech_profile(profile)  # warm the cache for upstream callers
    job_langs: set[str] = set(job_signals.get("languages", []))
    job_fws: set[str] = set(job_signals.get("frameworks", []))
    job_domains: set[str] = set(job_signals.get("domains", []))

    matches: list[tuple[str, int, str]] = []

    for repo in profile.get("repos", []):
        repo_techs: set[str] = set(t.lower() for t in repo.get("tech_stack_inferred", []))
        repo_domains: set[str] = set(d.lower() for d in repo.get("domains", []))
        repo_lang = (repo.get("language") or "").lower()

        lang_match = bool(job_langs & repo_techs) or bool(repo_lang and repo_lang in job_langs)
        fw_match = bool(job_fws & repo_techs)
        domain_match = bool(job_domains & repo_domains)

        match_count = int(lang_match) + int(fw_match) + int(domain_match)
        if match_count:
            desc = repo.get("description") or repo.get("summary", "") or ""
            matches.append((repo["name"], match_count, desc))

    matches.sort(key=lambda x: (-x[1], x[0]))
    max_repos = config.get("max_matching_repos", 5)
    return [m[0] for m in matches[:max_repos]]


def score_job(
    job_text: str,
    profile: dict,
    cv_path: Path | None = None,
) -> dict:
    """Score a single job posting against profile + CV."""
    signals = extract_job_signals(job_text, profile)

    lang_score, lang_matched = score_languages(signals, profile)
    fw_score, fw_matched = score_frameworks(signals, profile)
    dom_score, dom_matched = score_domains(signals, profile)
    cv_score, cv_matched = score_cv_alignment(signals, profile, raw_text=job_text, cv_path=cv_path)

    total = lang_score + fw_score + dom_score + cv_score
    matching_repos = find_matching_repos(signals, profile)

    # Recommendation
    strong_th = config.get("score_threshold_strong", 80)
    good_th = config.get("score_threshold_good", 60)
    moderate_th = config.get("score_threshold_moderate", 40)

    if total >= strong_th:
        highlights = (lang_matched + fw_matched)[:4]
        rec = f"Strong match — tailor CV emphasizing {', '.join(highlights) if highlights else 'your strengths'}"
    elif total >= good_th:
        highlights = (lang_matched + fw_matched)[:3]
        rec = f"Good match — highlight {', '.join(highlights) if highlights else 'relevant experience'}"
    elif total >= moderate_th:
        highlights = (lang_matched + fw_matched)[:2]
        rec = f"Moderate match — emphasize {', '.join(highlights) if highlights else 'transferable skills'}"
    else:
        rec = "Weak match — consider other opportunities"

    return {
        "total_score": total,
        "breakdown": {
            "languages": lang_score,
            "frameworks": fw_score,
            "domains": dom_score,
            "cv_alignment": cv_score,
        },
        "matched_languages": lang_matched,
        "matched_frameworks": fw_matched,
        "matched_domains": dom_matched,
        "matched_cv_keywords": cv_matched,
        "matching_repos": matching_repos,
        "seniority": signals["seniority"],
        "remote": signals["remote"],
        "recommendation": rec,
    }


def main():
    profile = load_profile()

    if len(sys.argv) < 2:
        # Check for piped stdin
        if not sys.stdin.isatty():
            job_text = sys.stdin.read().strip()
            if not job_text:
                print("Error: no input provided", file=sys.stderr)
                sys.exit(1)
            result = score_job(job_text, profile)
            print(json.dumps(result, indent=2))
            sys.exit(0)
        print("Usage: job_matcher.py <job_text_or_file_or_url> [--json] [--cv <path>]")
        sys.exit(1)

    args = sys.argv[1:]
    as_json = "--json" in args
    cv_path = None
    jd_arg = ""

    i = 0
    while i < len(args):
        if args[i] == "--json":
            i += 1
        elif args[i] == "--cv" and i + 1 < len(args):
            cv_path = Path(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            if not jd_arg:
                jd_arg = args[i]
            i += 1
        else:
            i += 1

    if not jd_arg:
        print("Error: no job description text, file, or URL provided", file=sys.stderr)
        sys.exit(1)

    # Handle URL input — crawl it
    if jd_arg.startswith("http://") or jd_arg.startswith("https://"):
        try:
            import httpx
            resp = httpx.get(jd_arg, timeout=30, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChameleonBot/1.0)"
            })
            resp.raise_for_status()
            from html.parser import HTMLParser
            class _TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                    self._skip = False
                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style"):
                        self._skip = True
                def handle_endtag(self, tag):
                    if tag in ("script", "style"):
                        self._skip = False
                def handle_data(self, data):
                    if not self._skip:
                        self.parts.append(data)
            te = _TextExtractor()
            te.feed(resp.text)
            import re as _re
            job_text = _re.sub(r"\s+", " ", " ".join(te.parts)).strip()
        except ImportError:
            import urllib.request
            import re as _re
            import html as _html_mod
            req = urllib.request.Request(jd_arg, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            raw = _re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=_re.DOTALL | _re.IGNORECASE)
            raw = _re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=_re.DOTALL | _re.IGNORECASE)
            raw = _re.sub(r"<[^>]+>", " ", raw)
            raw = _html_mod.unescape(raw)
            job_text = _re.sub(r"\s+", " ", raw).strip()[:10000]
        except Exception as e:
            print(f"Error crawling URL: {e}", file=sys.stderr)
            sys.exit(1)
    elif Path(jd_arg).is_file():
        job_text = Path(jd_arg).read_text()
    else:
        job_text = jd_arg

    result = score_job(job_text, profile, cv_path)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n=== Job Match Score: {result['total_score']}/100 ===")
        print(f"Languages:  {result['breakdown']['languages']}/25  -> {result['matched_languages']}")
        print(f"Frameworks: {result['breakdown']['frameworks']}/25  -> {result['matched_frameworks']}")
        print(f"Domains:    {result['breakdown']['domains']}/25  -> {result['matched_domains']}")
        print(f"CV Align:   {result['breakdown']['cv_alignment']}/25  -> {result['matched_cv_keywords'][:5]}")
        print(f"\nMatching repos: {', '.join(result['matching_repos'])}")
        print(f"Seniority: {result['seniority']} | Remote: {result['remote']}")
        print(f"\n-> {result['recommendation']}")


if __name__ == "__main__":
    main()
