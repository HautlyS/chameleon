# Skill: Dynamic Job Matcher

Match job postings against HautlyS's live GitHub profile + master CV to find the best opportunities.

## When to Use
- After scanning jobs from MCPs or the job scanner
- When the user wants to find the best matching roles
- Before creating tailored CVs (to prioritize which jobs to tailor for)

## How It Works

1. Load the GitHub profile from `/home/hautly/chameleon/profiles/github_repos.json`
2. Load the master CV from `/home/hautly/chameleon/templates/tupa_cv.yaml`
3. For each job listing, compute a match score based on:
   - **Language match** (0-25): Does the job's required languages overlap with GitHub languages?
   - **Framework match** (0-25): Do the job's frameworks/tools match inferred tech stack?
   - **Domain match** (0-25): Does the job's industry/domain match repo domains?
   - **CV alignment** (0-25): Does the job description match CV experience/skills?
4. Return top matches ranked by score

## Scoring Rubric

### Language Match (0-25)
| Overlap | Score |
|---------|-------|
| 3+ languages match | 25 |
| 2 languages match | 20 |
| 1 language matches | 15 |
| Related language (e.g., JS↔TS) | 10 |
| No match | 0 |

### Framework Match (0-25)
| Overlap | Score |
|---------|-------|
| 3+ frameworks match | 25 |
| 2 frameworks match | 20 |
| 1 framework matches | 15 |
| Adjacent ecosystem (e.g., Vue↔React) | 8 |
| No match | 0 |

### Domain Match (0-25)
| Overlap | Score |
|---------|-------|
| Exact domain (e.g., cryptography→security) | 25 |
| Adjacent domain (e.g., file-mgmt→enterprise) | 18 |
| General tech overlap | 10 |
| No domain match | 0 |

### CV Alignment (0-25)
| Match | Score |
|-------|-------|
| 3+ CV sections align with JD | 25 |
| 2 CV sections align | 20 |
| 1 CV section aligns | 15 |
| Skills mention only | 10 |
| No alignment | 0 |

## Output Format

```json
{
  "matches": [
    {
      "rank": 1,
      "job_title": "...",
      "company": "...",
      "url": "...",
      "total_score": 87,
      "breakdown": {
        "languages": 25,
        "frameworks": 20,
        "domains": 22,
        "cv_alignment": 20
      },
      "matched_repos": ["Cybermanju-Drive", "any-proxy"],
      "matched_cv_sections": ["skills", "experience", "projects"],
      "recommendation": "Strong match — tailor CV emphasizing Rust + crypto + desktop"
    }
  ],
  "summary": {
    "total_jobs_scored": 20,
    "strong_matches": 5,
    "good_matches": 8,
    "weak_matches": 7
  }
}
```

## GitHub Profile Data

Source: `/home/hautly/chameleon/profiles/github_repos.json`

### Key Repos by Domain

**Cryptography / Security:**
- Cybermanju-Drive — ML-KEM, ML-DSA, SLH-DSA, ChaCha20Poly1305, Tantivy BM25

**Desktop Apps:**
- Cybermanju-Drive — Tauri v2 + Rust + Vue 3
- MagicCursor — Tauri + Vue.js + WebGL2 + GPU fluid sim
- Earth_Guardians_App — Tauri 2 + Vue 3 + Supabase

**Web Apps / Full-Stack:**
- Autitude — Nuxt.js healthcare platform
- Earth_Guardians_App — Vue 3 + Pinia + Supabase PWA
- any-proxy — OpenAI-compatible API gateway

**AI / ML:**
- Cybermanju-Drive — embeddings, similarity search, DBSCAN clustering
- any-proxy — LLM routing (DeepSeek, Qwen, Claude, OpenHands)

**DevOps / Tooling:**
- audit-auto — JavaScript automation
- cosmic-update — system update tool
- any-proxy — Docker + systemd + CI/CD

### Inferred Tech Stack (from repos)
- **Languages:** Rust (10), JavaScript (8), TypeScript (7), Vue (5), Shell (3)
- **Frameworks:** Tauri, Vue.js, Nuxt.js, Supabase, Playwright
- **Domains:** cryptography, file-management, geospatial, AI/ML, web-automation, desktop-apps, devops, healthcare
- **Infrastructure:** Docker, GitHub Actions, systemd, WASM

## Usage

```
# Score a single job
python3 -m scripts.job_matcher score --job-url "https://..."

# Score all jobs from a scan
python3 -m scripts.job_matcher score --scan-file "output/scan_results.json"

# Rank top N matches
python3 -m scripts.job_matcher rank --top 10
```

## Integration with Chameleon Workflow

1. Scan jobs → `job_scanner`
2. Score matches → `job_matcher` (this skill)
3. Pick top matches → user selects
4. Tailor CVs → `chameleon` / `tailor-cv`
5. Render PDFs → `rendercv`
