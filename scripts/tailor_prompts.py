"""
Prompt templates for one-shot opencode calls in the tailoring pipeline.
Every prompt is designed to return structured output (YAML or JSON).
"""
from __future__ import annotations

TAILOR_PROMPT = """You are a CV tailoring engine that outputs raw YAML and nothing else.

CRITICAL RULE: Output ONLY the tailored YAML document. No greetings, no explanations, no file operations, no markdown fences, no backticks, no commentary. The first character of your output must be 'c' (from 'cv:') and the last character must be the last character of the YAML document.

## Rules
1. Keep the `design` section EXACTLY as it was in the input CV. Do not modify it.
2. For every experience section (every company/position pair):
   - **Preserve the truth** — never fabricate a role, company, date, or technology.
   - **Rephrase every highlight to maximize relevance** to the JD keywords and domains.
   - Lead with the most relevant highlight for each experience.
3. Rewrite the **summary** to directly address the JD. First sentence = role statement. Second sentence = portfolio-scale evidence.
4. Keep **skills** section labels unchanged. Re-order and re-word details within each label to prioritize JD-relevant terms.
5. Reorder **experience** sections by relevance to the JD (most relevant first).
6. Keep only the 2-4 most relevant **projects**.
7. Education and languages are unchanged.

## Input
### MASTER CV (YAML)
{cv_yaml}

### TAILORING BRIEF
{brief_text}

Output ONLY the raw YAML document starting with 'cv:' — no other text at all.
"""


REVIEW_PROMPT = """You are a CV alignment auditor. Your task is to compare the **TAILORED CV** against the **JOB DESCRIPTION** and produce an alignment audit.

## Review criteria
1. **Skill coverage**: Are all JD-required languages/frameworks/tools present in the CV?
2. **Experience proof**: Does each JD responsibility have a matching experience highlight?
3. **Seniority match**: Does the CV project the right seniority level for the role?
4. **Domain relevance**: Are the domains mentioned in the JD reflected in the CV?
5. **ATS keywords**: Are key JD terms present in the CV for ATS scanning?
6. **Truth**: Does anything in the tailored CV appear fabricated or misleading?
7. **Language/tone**: Is the language confident, accomplishment-oriented, and professional?

## Output format
Return a JSON object with these keys:
```json
{{
  "overall_score": <int 0-100>,
  "by_section": {{
    "summary": <int 0-100>,
    "skills": <int 0-100>,
    "experience": <int 0-100>,
    "projects": <int 0-100>
  }},
  "missing_terms": ["term1", "term2"],
  "present_terms": ["term3", "term4"],
  "alignment_gaps": [
    {{"section": "experience", "company": "...", "issue": "..."}}
  ],
  "fabrication_concerns": ["..."] or [],
  "corrections_needed": [
    {{"section": "experience|summary|skills|projects", "path": "...", "current": "...", "suggested": "..."}}
  ],
  "approved": <true|false>
}}
```

## Input
### JOB DESCRIPTION
```
{jd_text}
```

### TAILORED CV (YAML)
```yaml
{tailored_yaml}
```

Return ONLY the JSON object — no commentary or markdown fences.
"""


FIX_PROMPT = """You are a CV editor. Apply the following corrections to the TAILORED CV YAML.

## Rules
1. Return ONLY valid YAML — no commentary, no markdown fences.
2. Keep the `design` section EXACTLY as-is.
3. Make ONLY the changes specified in the corrections list.
4. Preserve all other content exactly.

## Corrections to apply
{corrections_json}

## Current Tailored YAML
```yaml
{tailored_yaml}
```

Return ONLY the corrected YAML document.
"""
