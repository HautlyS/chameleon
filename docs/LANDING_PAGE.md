# Chameleon — Landing Page Setup Guide

## Design Read

> SaaS landing page for developers and job seekers, with a **NeoBrutalism × AMOLED × Thin Modern** language, leaning toward raw CSS with monochrome palette and a single electric accent, maximum contrast, true black backgrounds.

## The Aesthetic

This landing fuses three design dialects into one coherent system:

| Dialect | Role in the blend | Visual signature |
|---------|-------------------|------------------|
| **NeoBrutalism** | Structure & hierarchy | Thick black borders (`3px solid #000`), raw asymmetrical grids, flat unshadowed surfaces, bold typography, composition over decoration |
| **AMOLED** | Canvas & atmosphere | True black (`#000000`) backgrounds that melt into the display, vibrant accent that floats on the void, minimum energy draw |
| **Thin Modern** | Typography & polish | Light font weights (300-400) at display sizes, generous leading, fine horizontal rules, precise spacing that keeps the brutalist bones from feeling crude |

### Three Dials

```
DESIGN_VARIANCE:  9   — Asymmetric, offset, raw compositions
MOTION_INTENSITY: 4   — Static-first, subtle reveals only
VISUAL_DENSITY:   3   — Art-gallery breathing room on AMOLED void
```

## Color System

No beige, no brass, no warm cream. The palette is binary with one electric interruption.

| Token | Hex | Usage |
|-------|-----|-------|
| `--ink` | `#000000` | True AMOLED black — page background, card fills, button backgrounds |
| `--surface` | `#0a0a0a` | Off-black for tile variation when pure black needs relief |
| `--surface-elevated` | `#141414` | Slightly lifted surface for hover/card states |
| `--border` | `#ffffff` | White borders on black — the brutalism signature |
| `--border-subtle` | `rgba(255,255,255,0.12)` | Fine hairlines when thick white is too loud |
| `--text-primary` | `#ffffff` | Headlines, body, navigation |
| `--text-secondary` | `rgba(255,255,255,0.55)` | Muted copy, meta labels |
| `--text-tertiary` | `rgba(255,255,255,0.3)` | Fine print, legal |
| `--accent` | `#00e5ff` | Electric cyan — the single accent (CTAs, links, focus rings, decorative rules) |
| `--accent-dim` | `rgba(0,229,255,0.15)` | Accent tint for hover backgrounds, subtle highlights |

**Why electric cyan?** Against true black, cyan (`#00e5ff`) produces the highest perceived brightness differential without eye strain. It reads as tech, signal, and future — fitting for an AI-powered resume tool. One accent, locked across the entire page.

## Typography

```css
--font-display: 'Geist Display', 'Inter Display', system-ui, sans-serif;
--font-body:    'Geist', 'Inter', system-ui, sans-serif;
--font-mono:    'Geist Mono', 'JetBrains Mono', 'SF Mono', monospace;
```

| Token | Size | Weight | Line Ht | Tracking | Use |
|-------|------|--------|---------|----------|-----|
| `--text-hero` | clamp(2.5rem, 6vw, 4.5rem) | 300 | 1.05 | -0.02em | Hero headline — thin, airy, commanding |
| `--text-display` | clamp(1.75rem, 3.5vw, 2.75rem) | 400 | 1.1 | -0.015em | Section headings |
| `--text-title` | 1.25rem | 500 | 1.2 | -0.01em | Card titles, feature names |
| `--text-body` | 1rem | 400 | 1.6 | normal | Paragraphs |
| `--text-small` | 0.875rem | 400 | 1.5 | normal | Captions, meta |
| `--text-mono` | 0.8125rem | 400 | 1.4 | +0.02em | Code, stats, labels |
| `--text-button` | 0.9375rem | 500 | 1 | -0.01em | CTA labels |

**No serif anywhere.** Geist Display at weight 300 for the hero establishes the thin-modern half of the triad. Weight 500 is reserved for interactive labels only — no mid-weight body text (consistent with the Apple DS principle of 300/400/600/700 ladder, with 500 absent from body).

## Layout Architecture

```
┌─────────────────────────────────────────┐
│  GLOBAL NAV (fixed top, true black)      │  → 64px height, white links
├─────────────────────────────────────────┤
│  HERO (100dvh)                           │  → Left: headline + sub + CTA
│  Left stack  │  Right visual             │  → Right: abstract brutalist shape
├─────────────────────────────────────────┤
│  "TRUSTED BY" logo wall                  │  → Mono logos, border-top/bottom
├─────────────────────────────────────────┤
│  FEATURES (bento grid, 4 cells)          │  → Asymmetric: 2fr 1fr / 1fr 1fr
├─────────────────────────────────────────┤
│  HOW IT WORKS (3-step horizontal)        │  → Numbered steps, thick dividers
├─────────────────────────────────────────┤
│  TESTIMONIALS (2-col quote cards)        │  → Thick white borders, raw
├─────────────────────────────────────────┤
│  FINAL CTA (full-width)                  │  → Massive headline, single CTA
├─────────────────────────────────────────┤
│  FOOTER (true black, minimal)            │  → 3-col link columns, fine print
└─────────────────────────────────────────┘
```

### Grid rules
- Max content width: `1200px` (`max-w-[1200px] mx-auto`)
- Section vertical rhythm: `py-24` (6rem) desktop, `py-16` mobile
- Border-driven section separation (not margins) — each section gets `border-t: 3px solid white` except hero and final CTA
- Edge-to-edge dark tiles with no rounding (radius 0 everywhere)

## Components

### Global Nav
```
┌──────────────────────────────────────┐
│  ◇ chameleon    Features  How  Docs  │  [Get Started]
└──────────────────────────────────────┘
```
- True black background (`#000`)
- White text, 14px, weight 400, uppercase tracking `0.08em`
- Right CTA is the accent pill
- No hamburger below 768px — condense labels before collapsing
- 64px height, single-line at all desktop sizes

### Hero
```
┌─────────────────────┬─────────────────┐
│                     │                 │
│  Tailor your resume │  ┌───────────┐  │
│  to any job in      │  │  █████████ │  │
│  one command.       │  │  ██ ██████ │  │
│                     │  │  █████ ███ │  │
│  Paste a JD. Get a  │  │  ████████  │  │
│  PDF. No fluff.     │  │  █████████ │  │
│                     │  └───────────┘  │
│  [Try It Now]  [Docs]                 │
│                     │                 │
└─────────────────────┴─────────────────┘
```
- Left: 55% width, right: 45% width
- Headline max 2 lines, subtext max 20 words
- CTA pair: primary accent pill + secondary ghost pill
- Right side: abstract brutalist shape (pure CSS — layered white borders on black, rotated squares, a code-like ornament)
- No image needed — the shape IS the visual
- Hero top padding: max `pt-24`

### Feature Bento (4 cells)
```
┌──────────────────────┬───────────────┐
│                       │               │
│  CLI-native          │  AI analysis   │
│  workflow            │  engine        │
│                       │               │
│  ─────────────       │  ───────────  │
│  No web UI needed.   │  Extracts      │
│  Your terminal is    │  skills,       │
│  the dashboard.      │  keywords,     │
│                       │  seniority.    │
│                       │               │
├──────────────────────┴───────────────┤
│                                       │
│  ┌────────────────┬─────────────────┐ │
│  │  ATS-ready PDF  │  Score your CV  │ │
│  │  by RenderCV    │  0-100 match    │ │
│  │                 │                 │ │
│  │  Typst backend  │  4 categories   │ │
│  │  no LaTeX       │  + evidence     │ │
│  └────────────────┴─────────────────┘ │
│                        (2 bottom cells)│
└─────────────────────────────────────────┘
```
- Top row: 2 cells, split 1:1
- Bottom row: 2 cells, split 1:1 but narrower — creates bento asymmetry
- Each cell has thick white border (`3px solid #fff`), true black fill
- Cell heading in `--text-title`, body in `--text-body`
- Row 1 has `border-bottom: 3px solid #fff` dividing the two rows

### How It Works (3 steps)
```
── 01 ──────────────────────────────────────
Paste a job URL or description
──────────────────────────────────────
── 02 ──────────────────────────────────────
Chameleon analyzes the JD against your CV
──────────────────────────────────────
── 03 ──────────────────────────────────────
Download your tailored PDF, ready to submit
──────────────────────────────────────
```
- Horizontal layout on desktop, stacked on mobile
- Each step: large number (96px, weight 200, accent color) + heading + short body
- Steps connected by thick white horizontal rules (3px)
- No arrows, no icons — pure typographic flow

### Testimonials
```
┌────────────────────────┬────────────────────────┐
│                        │                        │
│ "I used to spend 45    │ "The ATS ghost         │
│ minutes tailoring each │ injection alone got me │
│ resume. Now it's one   │ 3x more callbacks.     │
│ command."              │ Insane tool."          │
│                        │                        │
│ — Sarah K.             │ — Marcus T.            │
│ Senior Engineer        │ Product Designer       │
│                        │                        │
└────────────────────────┴────────────────────────┘
```
- 2-column grid on desktop, 1-column on mobile
- White 3px border around each card
- Quote in `--text-body` weight 300, italic
- Attribution below in `--text-small`, weight 400
- No rating stars, no avatars, no logos — just words

### Final CTA
```
┌──────────────────────────────────────────┐
│                                          │
│           Stop rewriting.                │
│           Start tailoring.               │
│                                          │
│            [ Install Now ]               │
│                                          │
│        No signup. No credit card.        │
│        One command, one PDF.             │
│                                          │
└──────────────────────────────────────────┘
```
- Centered, massive (2-line headline in hero scale)
- Single primary CTA
- Tiny sub-line below CTA in `--text-tertiary`

### Footer
```
┌──────────────┬──────────────┬──────────────┐
│ Product      │ Resources     │ Company       │
│              │              │               │
│ Features     │ Documentation │ GitHub         │
│ CLI          │ Examples      │ License        │
│ Integrations │ Blog          │ Contact        │
│ Pricing      │ FAQ           │               │
│              │              │               │
│ © 2026 Chameleon. MIT License.              │
└──────────────────────────────────────────────┘
```
- True black background, `--text-secondary` for links
- Column headings in `--text-mono` uppercase, tracking `0.08em`
- Link items in `--text-small`, `rgba(255,255,255,0.5)`
- `border-top: 1px solid rgba(255,255,255,0.12)` only

## Motion

At `MOTION_INTENSITY: 4`, the page is almost static. The only motion:

1. **Hero fade-in** on load: headline fades up (600ms, ease-out), then CTA buttons stagger (200ms delay each)
2. **Border draw** on section entry: the thick white borders that separate sections draw in from left on scroll (CSS `animation-timeline: view()` or IntersectionObserver)
3. **CTA hover**: `transform: scale(1.02)` + accent fill shift — no scale-down, brutalism pushes forward

All motion respects `prefers-reduced-motion` — collapse to instant reveal.

## Dark Mode

There is no light mode. The entire page is built on true black. This is intentional:

- **AMOLED-first**: the page is designed for the void
- **No theme toggle**: one mode, no ambiguity
- **Accessibility**: all text meets WCAG AAA on `#000` (white 21:1 contrast, accent 8.6:1 at minimum)

If a light mode is required later, invert the palette: white canvas, black ink, same accent.

## Responsive Strategy

| Breakpoint | Changes |
|-----------|---------|
| ≤ 768px | Hero stacks (text full-width, shape moves below or disappears). Bento becomes single column. 3-step becomes vertical list. 2-col testimonials stack. |
| 769-1024px | Hero stays split but shape shrinks. Nav condenses (hide secondary links, keep logo + CTA). |
| ≥ 1025px | Full layout as described. Content max-width 1200px. |

## Files

The landing page consists of:

```
landing/
├── index.html        # Main HTML document
├── style.css         # All styles (no framework)
└── script.js         # Minimal JavaScript (scroll reveal, nav behavior)
```

## Deployment

This is a static site. Deploy anywhere static hosting works:

```bash
# Netlify / Vercel — drag landing/ folder
# GitHub Pages — push landing/ to gh-pages branch
# Any S3/Cloudflare — sync landing/ to bucket
```

No build step required. No framework to install. Open `landing/index.html` in a browser to preview.

## Pre-Flight Checklist (abridged from design-taste skill)

- [ ] ZERO em-dashes (`—`) anywhere on the page
- [ ] Page Theme Lock: one theme (dark/AMOLED) for the entire page
- [ ] Color Consistency Lock: `#00e5ff` is the only accent on the page
- [ ] Shape Consistency Lock: all radius = 0 (brutalist) except pill CTAs
- [ ] Button Contrast: white text on accent passes WCAG AA (8.6:1)
- [ ] CTA Button Wrap: no CTA label wraps at desktop (max 3 words per button)
- [ ] Hero fits viewport: headline ≤ 2 lines, subtext ≤ 20 words, CTA visible
- [ ] Hero top padding: max `pt-24`
- [ ] Hero stack: max 4 elements (no eyebrow, headline, subtext, CTAs)
- [ ] Eyebrow count: ≤ ceil(sectionCount / 3) — hero counts as 1
- [ ] No split-header pattern (no left-huge-headline + right-tiny-paragraph)
- [ ] Zigzag alternation cap: no 3+ consecutive same-layout sections
- [ ] No duplicate CTA intent across the page
- [ ] Logo wall = logos only (no industry labels under logos)
- [ ] No decorative status dots
- [ ] No scroll cues (`Scroll`, `↓ scroll`)
- [ ] No version labels in hero
- [ ] No section-numbering eyebrows
- [ ] No locale/weather/time strips
- [ ] No em-dash anywhere (enforced in headlines, body, quotes, attribution)
- [ ] Motion claimed = motion shown (fade-in + border draw implemented)
- [ ] Reduced motion honored
- [ ] Viewport stability: `min-height: 100dvh` on hero (not `height: 100vh`)
- [ ] Content density: ≤ 25-word sub-paragraphs, no data-dump sections
- [ ] Quotes ≤ 3 lines, attribution clean (hyphen, not dash)
