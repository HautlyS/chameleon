"""
ATS Ghost Text — inject invisible keyword text into rendered PDF.
Uses reportlab to write invisible (white-on-white) text into the
PDF content stream so ATS parsers extract it while humans see nothing.
"""
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import letter


def collect_ats_terms(
    jd_text: str,
    extra_terms: str = "",
    existing_keywords: Sequence[str] | None = None,
    max_terms: int = 200,
) -> list[str]:
    """Collect all ATS-relevant terms from JD + extras."""
    seen: set[str] = set()
    terms: list[str] = []

    def add(t: str) -> None:
        t = t.strip().strip(",.;:")
        if t and len(t) > 1 and t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)

    if existing_keywords:
        for kw in existing_keywords:
            add(kw)

    lower = jd_text.lower()
    for m in re.finditer(r"\b[A-Z][a-z]+[A-Z][a-zA-Z]*\b", jd_text):
        add(m.group())
    for m in re.finditer(r"\b[a-z]+[-.][a-z]+\b", lower):
        add(m.group())

    ats_patterns = [
        r"\b(typescript|javascript|python|rust|go|golang|java|c\+\+|ruby|php|swift|kotlin|scala|r|dart|elixir|haskell|clojure)\b",
        r"\b(vue|react|angular|svelte|next\.?js|nuxt|remix|solid|express|fastapi|flask|django|spring|rails|laravel|asp\.net|node\.js|deno|bun)\b",
        r"\b(pytorch|tensorflow|langchain|crewai|autogen|semantic.?kernel|llama.?index|haystack|spacy|nltk|opencv|hugging.?face|transformers|diffusers)\b",
        r"\b(rag|embedding|vector.?db|pgvector|pinecone|weaviate|chroma|qdrant|milvus|redis|postgresql|mysql|mongodb|dynamodb|cosmos.?db)\b",
        r"\b(docker|kubernetes|k8s|helm|terraform|ansible|jenkins|github.?actions|gitlab.?ci|argocd|prometheus|grafana|datadog|new.?relic)\b",
        r"\b(aws|azure|gcp|cloud|s3|ec2|lambda|cloudflare|vercel|netlify|heroku|digital.?ocean|linode)\b",
        r"\b(tailwind|bootstrap|sass|less|css|html|webpack|vite|esbuild|rollup|babel)\b",
        r"\b(graphql|rest|grpc|websocket|mqtt|kafka|rabbitmq|nats|redis|celery|bull|sidekiq)\b",
        r"\b(pytest|jest|vitest|cypress|playwright|selenium|mocha|chai|rspec|junit|unittest)\b",
        r"\b(ci/cd|devops|mlops|data.?pipeline|etl|elt|data.?warehouse|data.?lake|olap|oltp)\b",
        r"\b(oauth|jwt|saml|oidc|sso|rbac|abac|pci|hipaa|gdpr|soc2|iso27001)\b",
        r"\b(agile|scrum|kanban|sprint|jira|confluence|notion|linear|asana|trello)\b",
        r"\b(microservice|monolith|serverless|edge|distributed.?system|event.?driven|cqrs|event.?sourcing)\b",
        r"\b(fastapi|flask|django|spring.?boot|express|koa|hono|actix|rocket|axum|poem)\b",
    ]
    for pat in ats_patterns:
        for m in re.finditer(pat, lower):
            add(m.group())

    phrases = re.findall(r"\b([A-Z][a-z]+ (?:[A-Z][a-z]+ ){0,2}[A-Z][a-z]+)\b", jd_text)
    for p in phrases:
        if len(p.split()) >= 2:
            add(p)

    if extra_terms:
        for t in extra_terms.replace(",", " ").split():
            add(t)

    return terms[:max_terms]


def _make_ghost_overlay_page(
    terms: list[str],
    width: float,
    height: float,
) -> BytesIO:
    """Create a PDF page as BytesIO with invisible ghost text.

    The text is drawn with fill opacity 0 and stroke opacity 0,
    so it is completely invisible to the human eye. ATS text
    extractors still see it because it exists in the content stream.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", 1)
    # Invisible: white fill + white stroke + zero opacity
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(1, 1, 1)
    c.setFillAlpha(0)
    c.setStrokeAlpha(0)

    keyword_text = " ".join(terms)
    # Write the keyword block near the bottom of the page
    text_object = c.beginText()
    text_object.setCharSpace(0.5)
    text_object.setTextOrigin(0, 0)
    # Write as a single long line (ATS parsers read this)
    text_object.textLine(keyword_text)
    # Also write a second line with terms reversed
    text_object.textLine(" ".join(reversed(terms)))
    c.drawText(text_object)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def inject_ghost_text(
    pdf_path: Path,
    terms: list[str],
) -> bool:
    """Inject invisible keyword text into every page of the PDF.

    Uses a reportlab-generated overlay page merged into each page's
    content stream. The text is white-on-white with zero opacity,
    completely invisible to humans. ATS parsers extract it because
    it is real text in the content stream.
    """
    if not pdf_path.exists() or not terms:
        return False

    try:
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            mb = page.mediabox
            pw = float(mb.width)
            ph = float(mb.height)

            # Distribute terms across pages (different order each page)
            chunk_size = max(1, len(terms) // max(len(reader.pages), 1))
            start = (i * chunk_size) % len(terms)
            chunk = terms[start : start + chunk_size] or terms

            overlay_buf = _make_ghost_overlay_page(chunk, pw, ph)
            overlay = PdfReader(overlay_buf)
            page.merge_page(overlay.pages[0], over=False)
            writer.add_page(page)

        writer.write(str(pdf_path))
        return True
    except Exception:
        return False


def verify_ats_text(pdf_path: Path, sample_terms: list[str] | None = None) -> tuple[bool, list[str]]:
    """Verify ghost keywords are extractable from the PDF.
    Returns (found_any, list_of_found_terms).
    """
    if not pdf_path.exists():
        return False, ["PDF not found"]
    try:
        reader = PdfReader(str(pdf_path))
        full_text = ""
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"
        found: list[str] = []
        check = sample_terms or ["python", "typescript", "docker", "rag", "postgresql", "kubernetes", "react", "vue", "fastapi", "aws"]
        for term in check:
            if term.lower() in full_text.lower():
                found.append(term)
        return (len(found) > 0, found)
    except Exception as e:
        return False, [str(e)]
