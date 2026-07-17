# Empyrean Wiki — Design

**Date:** 2026-07-16
**Status:** Approved (brainstorm complete)
**Mockups:** https://claude.ai/code/artifact/952d8cff-84d8-4fe8-861b-5fcec6fdfaf0 (Option B selected)

## What it is

An AI-authored visual wiki for the Empyrean suite, published as interlinked Claude
Artifacts. A central hub page maps the suite (Aeon, Sigil, Oracle, Seraph, Aurora) and
Aeon's ten engine sections; each engine section gets its own page. Claude authors all
content — technical decision records, beginner explainers, and interactive
visualizations. It is *maintained*, not self-generating: when the engine changes, the
user asks for a refresh and the affected pages are updated and redeployed to the same
URLs.

Two audiences, one document per page:

1. **The engineer/decision record** — what Aeon chose, why, and how it compares to the
   eight reference games.
2. **The learner** — someone who wants to learn Genesis engine/game programming from
   near zero, served by inline explainers layered into the same narrative.

## Architecture

- **One page = one self-contained HTML file = one artifact = one stable URL.**
- **Sources live in `empyrean/wiki/`** (suite-level repo): `hub.html`, `aeon/` subfolder
  for section pages, committed to git. Updates are ordinary diffs.
- **`empyrean/wiki/urls.json`** — registry mapping each page file to its published
  artifact URL, so any future session can redeploy the same page to the same address
  (the Artifact tool needs the URL to target an existing artifact from a new session).
- **Cross-links** are plain `<a href>` between artifact URLs (CSP blocks embedded
  resources, not navigation). First publish needs a one-time backfill pass:
  publish pages → record URLs in `urls.json` → wire nav links → redeploy.
- **Design system**: canonical `empyrean/wiki/theme.css` in the repo; its contents are
  copied to the top of each page's inline `<style>` (artifacts cannot share files),
  followed by a `/* Page-specific styles */` banner and any page-local rules. One
  source of truth to copy from; a page is out of date if the theme portion above the
  banner drifts from `theme.css`. Page-local rules below the banner are intentional.
- **No external assets ever** — inline SVG/JS/CSS only, per the artifact CSP.

## Page format (Option B — one narrative, inline explainers)

Each section page is a single technical narrative with these components:

- **Explainer boxes** (green, collapsible `<details>`): inline wherever a concept would
  lose a newcomer. Plus a page-level "expand all explainers" switch (recovers most of
  the depth-toggle option's benefit without duplicating the article).
- **Teaching examples are allowed to be invented.** Explainers may use made-up toy
  code, simplified numbers, analogies, and hypothetical scenarios when that teaches
  better than the real thing. Invented material must be visually distinct from real
  engine excerpts (labeled "teaching example" vs. a real `file:line`-attributed
  excerpt) so a reader always knows which is which.
- **Decision blocks** (gold, left-ruled): what Aeon chose, why, and "who does what"
  provenance chips across the reference games (Vectorman, Gunstar Heroes, Alien
  Soldier, S.C.E., Batman & Robin, Thunder Force IV, Ristar, sonic_hack).
- **Interactive diagrams** where the subject earns them (inline SVG/JS). For §0:
  clickable vector-table map, VDP register-init table with per-register "why",
  boot-sequence timeline. Not every page needs every widget — diagrams serve the
  content, not the reverse.
- **Real code excerpts** from actual source files, short and pointed, attributed to
  their file paths.
- **Breadcrumb nav** (EMPYREAN / AEON / §N) linking back to the hub.

## Visual identity

- Every color is a legal Genesis 9-bit CRAM color (channels from
  00/22/44/66/88/AA/CC/EE) — a subject-derived constraint, kept for the real wiki.
- Monospace headers, hardware-manual register-table aesthetic, scanline texture
  accents, dark blue ground (#000022), gold decision accents (#EEAA00), green learner
  accents (#44CC88), blue interactive accents (#4466EE).

## Content sourcing & honesty

- `aeon/docs/ENGINE_ARCHITECTURE.md` is the backbone for engine pages.
- Every page gets **cross-checked against the actual code before publishing** — the
  architecture doc drifts (2026-07-15 alignment audit: doc claimed palette cross-fade
  shipped; zero code exists). Where doc and code disagree, the wiki states what the
  code does and flags the divergence; it never repeats an unverified doc claim.
- Never pin ROM sizes or other constantly-changing numbers; describe mechanisms.

## V1 scope

Hub + one exemplar section page: **§0 Boot / Hardware Init** (natural starting point,
self-contained, best teaching hook — TMSS, vectors, VDP init, Z80 bus).

On the v1 hub, only the §0 card links anywhere; all other section and tool cards
render in a visibly unpublished state (dimmed, no link) until their pages exist.

After the exemplar's form is approved by the user, the remaining nine Aeon sections and
the suite tool pages (Sigil, Oracle, Seraph, Aurora) fan out mechanically — drafting
parallelizable with agents, with a foreground accuracy pass before publishing each.
Fan-out is explicitly out of scope for the v1 implementation plan.

## Maintenance model

On demand. The user says "update the wiki for X"; Claude re-reads the relevant sources
and recent commits, updates the affected page source(s) in `empyrean/wiki/`, redeploys
to the same URLs via `urls.json`, and commits the source changes.

## Verification

- Visual check of each published artifact (load it, exercise the interactive widgets).
- Link check: every cross-link resolves to the URL recorded in `urls.json`.
- Accuracy pass: each technical claim on a page traced to code or to a verified doc
  section before publish.

## Out of scope (v1)

- The nine remaining Aeon section pages and suite tool pages (fan-out phase).
- Any automated regeneration pipeline — the wiki is AI-maintained by request.
- Public hosting beyond claude.ai artifacts (artifacts are private-by-default; sharing
  is the user's call per page).
