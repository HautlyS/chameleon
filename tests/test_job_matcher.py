"""Tests for the job matcher scoring engine."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.job_matcher import (
    extract_job_signals,
    score_job,
    score_languages,
    score_frameworks,
    score_domains,
    score_cv_alignment,
    _build_dynamic_patterns,
    _build_full_tech_profile,
)


SAMPLE_PROFILE = {
    "skills_summary": {
        "languages": {"Python": 5, "TypeScript": 3, "Rust": 2},
        "tech_stack": ["Django", "React", "Docker", "FastAPI"],
        "domains": ["web-apps", "devops", "ai/ml"],
        "infrastructure": ["AWS", "GCP"],
    },
    "repos": [
        {
            "name": "test-repo",
            "language": "Python",
            "tech_stack_inferred": ["Python", "Django"],
            "domains": ["web-apps"],
            "description": "A test repo",
        }
    ],
}


SAMPLE_JD = """
Senior Python Developer at Acme
We are looking for a senior Python developer with Django and FastAPI experience.
You will work on web applications deployed on AWS.
Requirements: Python, TypeScript, Docker, Kubernetes
Nice to have: React, GraphQL
"""


def test_extract_job_signals():
    signals = extract_job_signals(SAMPLE_JD, SAMPLE_PROFILE)
    assert "python" in signals["languages"]
    assert "typescript" in signals["languages"]
    assert "django" in signals["frameworks"] or "fastapi" in signals["frameworks"]
    assert signals["seniority"] == "senior"


def test_score_languages():
    signals = extract_job_signals(SAMPLE_JD, SAMPLE_PROFILE)
    score, matched = score_languages(signals, SAMPLE_PROFILE)
    assert 0 <= score <= 25
    assert len(matched) > 0


def test_score_frameworks():
    signals = extract_job_signals(SAMPLE_JD, SAMPLE_PROFILE)
    score, matched = score_frameworks(signals, SAMPLE_PROFILE)
    assert 0 <= score <= 25


def test_score_domains():
    signals = extract_job_signals(SAMPLE_JD, SAMPLE_PROFILE)
    score, matched = score_domains(signals, SAMPLE_PROFILE)
    assert 0 <= score <= 25


def test_score_job_returns_all_keys():
    result = score_job(SAMPLE_JD, SAMPLE_PROFILE)
    assert "total_score" in result
    assert "breakdown" in result
    assert "matched_languages" in result
    assert "matched_frameworks" in result
    assert "matched_domains" in result
    assert "matched_cv_keywords" in result
    assert "matching_repos" in result
    assert "seniority" in result
    assert "remote" in result
    assert "recommendation" in result
    assert 0 <= result["total_score"] <= 100


def test_score_job_breakdown_weights():
    result = score_job(SAMPLE_JD, SAMPLE_PROFILE)
    bd = result["breakdown"]
    total = bd["languages"] + bd["frameworks"] + bd["domains"] + bd["cv_alignment"]
    assert total == result["total_score"]


def test_empty_profile():
    empty = {
        "repos": [],
        "skills_summary": {"languages": {}, "tech_stack": [], "domains": [], "infrastructure": []},
    }
    result = score_job(SAMPLE_JD, empty)
    assert result["total_score"] >= 0


def test_empty_jd():
    result = score_job("", SAMPLE_PROFILE)
    assert 0 <= result["total_score"] <= 100


def test_seniority_detection():
    signals = extract_job_signals("Senior Staff Lead Engineer at BigCo", SAMPLE_PROFILE)
    assert signals["seniority"] == "senior"
    signals = extract_job_signals("Junior entry-level intern position", SAMPLE_PROFILE)
    assert signals["seniority"] == "junior"
    signals = extract_job_signals("Mid-level software engineer", SAMPLE_PROFILE)
    assert signals["seniority"] == "mid"


def test_remote_detection():
    signals = extract_job_signals("Remote worldwide position", SAMPLE_PROFILE)
    assert signals["remote"] is True
    signals = extract_job_signals("On-site in New York", SAMPLE_PROFILE)
    assert signals["remote"] is False


def test_profile_cache():
    p1 = _build_full_tech_profile(SAMPLE_PROFILE)
    p2 = _build_full_tech_profile(SAMPLE_PROFILE)
    assert p1 == p2
    assert "python" in p1["languages"]
    assert "django" in p1["frameworks"]
    assert "web-apps" in p1["domains"]


def test_dynamic_patterns_built():
    patterns = _build_dynamic_patterns(SAMPLE_PROFILE)
    for cat in ("languages", "frameworks", "domains", "infra"):
        assert cat in patterns
        assert len(patterns[cat]) > 0
