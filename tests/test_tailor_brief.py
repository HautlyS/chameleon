"""Tests for the tailoring brief engine."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.tailor_brief import (
    analyze_seniority,
    extract_jd_sections,
    _compute_alignment,
    _extract_role,
    _extract_company,
)


SAMPLE_JD = """
Senior Rust Engineer at Acme Corp
We are looking for a senior engineer with 5+ years of Rust experience.
Requirements: Rust, TypeScript, distributed systems, kubernetes.
Nice to have: WebAssembly, gRPC.

About the company:
Acme Corp builds developer tools.

Responsibilities:
Design and implement distributed systems.
Mentor junior engineers.
"""


def test_analyze_seniority():
    result = analyze_seniority(SAMPLE_JD)
    assert result["level"] == "senior"
    assert result["years_required"] == 5
    assert result["mentorship"] is True


def test_analyze_seniority_junior():
    jd = "Junior Python developer internship position"
    result = analyze_seniority(jd)
    assert result["level"] == "junior"


def test_extract_jd_sections():
    sections = extract_jd_sections(SAMPLE_JD)
    assert "requirements" in sections
    assert "responsibilities" in sections
    assert "full_text" in sections
    assert len(sections["requirements"]) > 0


def test_compute_alignment():
    text = "Built distributed systems with Rust and Kubernetes"
    jd = "We use Rust, kubernetes, and distributed systems"
    score = _compute_alignment(text, jd)
    assert 0.0 <= score <= 1.0
    assert score > 0


def test_compute_alignment_no_match():
    text = "Designed UI components with React"
    jd = "Rust backend distributed systems engineer"
    score = _compute_alignment(text, jd)
    assert score == 0.0


def test_extract_role():
    role = _extract_role(SAMPLE_JD)
    assert "Senior" in role
    assert "Acme" in role


def test_extract_company():
    company = _extract_company(SAMPLE_JD)
    assert "Acme" in company
