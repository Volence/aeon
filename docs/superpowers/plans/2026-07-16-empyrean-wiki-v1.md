# Empyrean Wiki v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish the Empyrean wiki v1 — a central hub artifact plus the §0 Boot exemplar page — per `docs/superpowers/specs/2026-07-16-empyrean-wiki-design.md`.

**Architecture:** Each page is one self-contained HTML file in `empyrean/wiki/`, published as one Claude Artifact with a stable URL recorded in `urls.json`. A canonical `theme.css` is copied into each page's inline `<style>`. Cross-links are plain `<a href>` between artifact URLs, wired in a backfill pass after first publish.

**Tech Stack:** Hand-authored HTML/CSS/JS (no build step, no external assets — artifact CSP), Claude Artifact tool for publishing, git (empyrean repo) for sources.

**Execution constraints:**
- **Publishing tasks (5, 7) require the Artifact tool and must run in the controller session, NOT in subagents.** Content drafting (Tasks 3, 4, 6) may be delegated to subagents.
- All wiki source commits go to the **empyrean repo** (`/home/volence/sonic_hacks/empyrean`, branch `main`). Use `git -C /home/volence/sonic_hacks/empyrean` and add exact paths only.
- The published mockup artifact (`https://claude.ai/code/artifact/952d8cff-84d8-4fe8-861b-5fcec6fdfaf0`) is a separate artifact; do not redeploy over it.

---

### Task 1: Scaffold `empyrean/wiki/`

**Files:**
- Create: `empyrean/wiki/README.md`
- Create: `empyrean/wiki/urls.json`

- [ ] **Step 1: Create the directory and README**

Write `empyrean/wiki/README.md`:

```markdown
# Empyrean Wiki

AI-authored visual wiki for the Empyrean suite, published as interlinked Claude
Artifacts. Spec: `aeon/docs/superpowers/specs/2026-07-16-empyrean-wiki-design.md`.

## Layout

- `theme.css` — canonical design system. Every page carries a copy in its inline
  `<style>`; if a page's inline block differs from this file, the page is stale.
- `hub.html` — the central hub (suite map + Aeon section grid).
- `aeon/section-N-*.html` — one page per Aeon engine section.
- `urls.json` — registry: page file → published artifact URL/title/favicon.

## Maintenance (for future Claude sessions)

1. Edit the page source here. If `theme.css` changed, re-copy it into every page.
2. Redeploy with the Artifact tool, passing the page's `url` from `urls.json`
   (required to target an existing artifact from a new session). Keep the same
   favicon and `<title>`.
3. Verify the published page (load it, exercise interactive widgets, click links).
4. Commit the source change to this repo with exact paths.

## Content rules

- Every technical claim traces to code or a verified doc section. Where
  `ENGINE_ARCHITECTURE.md` and the code disagree, state what the code does and
  flag the divergence.
- Invented teaching material is welcome in explainers but must be visually
  distinct (`.teach` block) from real engine excerpts (attributed `file:line`).
- Never pin ROM sizes or other constantly-changing numbers.
- All colors must be legal Genesis 9-bit CRAM colors (channels from
  00/22/44/66/88/AA/CC/EE).
```

- [ ] **Step 2: Create the URL registry skeleton**

Write `empyrean/wiki/urls.json`:

```json
{
  "hub": {
    "file": "hub.html",
    "title": "EMPYREAN — Engine & Toolset Wiki",
    "favicon": "🕹️",
    "url": null
  },
  "aeon/section-0-boot": {
    "file": "aeon/section-0-boot.html",
    "title": "Aeon §0 — Boot & Hardware Init",
    "favicon": "⚡",
    "url": null
  }
}
```

- [ ] **Step 3: Verify JSON parses**

Run: `jq . /home/volence/sonic_hacks/empyrean/wiki/urls.json`
Expected: pretty-printed JSON, exit 0.

- [ ] **Step 4: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/README.md wiki/urls.json
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: scaffold — README + URL registry"
```

---

### Task 2: Canonical design system (`theme.css`)

**Files:**
- Create: `empyrean/wiki/theme.css`

- [ ] **Step 1: Write `theme.css`**

Full contents (derived from the approved mockup; all colors 9-bit legal):

```css
/* Empyrean wiki design system. Copy this whole file into each page's <style>.
   All colors are legal Genesis 9-bit CRAM colors (channels 00/22/44/66/88/AA/CC/EE). */
:root{
  --ground:#000022; --panel:#222244; --panel2:#000044; --line:#444466;
  --ink:#EEEEEE; --dim:#AAAACC; --accent:#4466EE; --gold:#EEAA00;
  --learn:#44CC88; --code-bg:#000000;
  --mono:ui-monospace,"Cascadia Mono","DejaVu Sans Mono",monospace;
}
html{background:var(--ground);}
body{font-family:system-ui,-apple-system,"Segoe UI","DejaVu Sans",sans-serif;
  color:var(--ink); background:var(--ground); line-height:1.6; margin:0;
  padding:0 1.25rem 5rem;}
.wrap{max-width:52rem; margin:0 auto;}
.wrap-wide{max-width:64rem; margin:0 auto;}

/* page header */
header.page{padding:2.2rem 0 1.4rem; border-bottom:1px solid var(--line);
  background:repeating-linear-gradient(0deg,transparent 0 3px,rgba(0,0,0,.35) 3px 4px);}
.eyebrow{font-family:var(--mono); font-size:.72rem; letter-spacing:.22em;
  color:var(--gold); text-transform:uppercase; margin:0 0 .5rem;}
h1{font-family:var(--mono); font-size:1.7rem; margin:0 0 .4rem;
  letter-spacing:.02em; text-wrap:balance;}
.sub{color:var(--dim); max-width:44rem; margin:0;}
.crumb{font-family:var(--mono); font-size:.72rem; color:var(--dim);
  letter-spacing:.08em; margin:0 0 .9rem;}
.crumb a{color:var(--accent); text-decoration:none;}
.crumb a:hover,.crumb a:focus-visible{text-decoration:underline;}

/* prose */
h2{font-family:var(--mono); font-size:1.15rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--gold); margin:2.6rem 0 .5rem;}
h3{font-family:var(--mono); font-size:1rem; margin:1.8rem 0 .4rem;}
p,li{max-width:42rem;}
a{color:var(--accent);}
hr{border:0; border-top:1px solid var(--line); margin:2.5rem 0;}

/* code */
pre{background:var(--code-bg); border:1px solid var(--line); border-radius:4px;
  padding:.8rem 1rem; overflow-x:auto; font-size:.8rem; line-height:1.5;
  font-family:var(--mono);}
pre .c{color:#668866;} pre .k{color:#4466EE;} pre .n{color:#EEAA00;}
code{font-family:var(--mono); font-size:.85em; color:var(--gold);}
.src{display:block; font-family:var(--mono); font-size:.65rem; color:var(--dim);
  letter-spacing:.08em; margin:.2rem 0 0; text-transform:none;}

/* explainer (collapsible, learner layer) */
details.explain{border:1px solid var(--learn); border-radius:4px; margin:1rem 0;
  max-width:42rem; background:rgba(68,204,136,.05);}
details.explain summary{cursor:pointer; padding:.5rem .8rem; color:var(--learn);
  font-family:var(--mono); font-size:.78rem; letter-spacing:.06em; list-style:none;}
details.explain summary::before{content:"▸ ";}
details.explain[open] summary::before{content:"▾ ";}
details.explain summary:focus-visible{outline:2px solid var(--learn); outline-offset:-2px;}
details.explain .x-body{padding:0 .9rem .8rem; font-size:.93rem;}

/* invented teaching example — visually distinct from real excerpts */
.teach{border:1px dashed var(--learn); border-radius:4px; padding:.6rem .9rem;
  margin:.8rem 0; max-width:42rem;}
.teach .t-tag{font-family:var(--mono); font-size:.62rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--learn); display:block; margin-bottom:.25rem;}

/* decision block */
.decision{border-left:3px solid var(--gold); background:rgba(238,170,0,.06);
  padding:.6rem .9rem; margin:1.1rem 0; max-width:42rem;}
.decision .d-tag{font-family:var(--mono); font-size:.65rem; letter-spacing:.18em;
  text-transform:uppercase; color:var(--gold); display:block; margin-bottom:.2rem;}

/* divergence flag (doc vs code) */
.diverge{border-left:3px solid #EE4444; background:rgba(238,68,68,.07);
  padding:.5rem .9rem; margin:1rem 0; max-width:42rem; font-size:.93rem;}
.diverge .v-tag{font-family:var(--mono); font-size:.62rem; letter-spacing:.18em;
  text-transform:uppercase; color:#EE4444; display:block; margin-bottom:.2rem;}

/* provenance chips */
.prov{display:flex; flex-wrap:wrap; gap:.35rem; margin:.5rem 0 0;}
.prov span{font-family:var(--mono); font-size:.68rem; letter-spacing:.04em;
  border:1px solid var(--line); border-radius:3px; padding:.12rem .5rem; color:var(--dim);}
.prov span.yes{border-color:var(--accent); color:var(--ink);}
.prov span.no{opacity:.55;}
.prov-label{font-family:var(--mono); font-size:.65rem; letter-spacing:.15em;
  text-transform:uppercase; color:var(--dim); margin:.8rem 0 0;}

/* expand-all switch */
.xall{font-family:var(--mono); font-size:.72rem; letter-spacing:.1em;
  text-transform:uppercase; padding:.4rem .9rem; cursor:pointer; border-radius:4px;
  background:transparent; color:var(--learn); border:1px solid var(--learn);}
.xall:focus-visible{outline:2px solid var(--learn); outline-offset:2px;}

/* data tables (register maps etc.) */
.tbl{overflow-x:auto; margin:1rem 0;}
table{border-collapse:collapse; font-size:.82rem;}
th,td{border:1px solid var(--line); padding:.35rem .6rem; text-align:left;
  vertical-align:top;}
th{font-family:var(--mono); font-size:.68rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--dim); background:var(--panel2);}
td code{font-variant-numeric:tabular-nums;}
tr.hi td{background:rgba(68,102,238,.12);}

/* figures / diagrams */
figure.diagram{border:1px solid var(--line); border-radius:5px;
  background:var(--panel2); padding:1rem; margin:1.2rem 0; overflow-x:auto;}
figure.diagram figcaption{font-family:var(--mono); font-size:.68rem;
  color:var(--dim); letter-spacing:.1em; text-transform:uppercase; margin-top:.6rem;}

/* hub cards */
.hub-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(13rem,1fr));
  gap:.7rem; margin:.8rem 0 0;}
a.card,div.card{border:1px solid var(--line); border-radius:5px; padding:.8rem .9rem;
  background:var(--panel2); display:flex; flex-direction:column; gap:.25rem;
  color:var(--ink); text-decoration:none;}
a.card:hover,a.card:focus-visible{border-color:var(--accent); outline:none;}
a.card:focus-visible{box-shadow:0 0 0 2px var(--accent);}
.card.tool{border-color:var(--accent);}
.card.soon{opacity:.45;}
.card .no{font-family:var(--mono); font-size:.65rem; color:var(--gold);
  letter-spacing:.15em;}
.card .nm{font-family:var(--mono); font-size:.95rem;}
.card .ds{font-size:.78rem; color:var(--dim); line-height:1.4;}
.card .soon-tag{font-family:var(--mono); font-size:.6rem; letter-spacing:.15em;
  text-transform:uppercase; color:var(--dim);}
.hub-h{font-family:var(--mono); font-size:.7rem; letter-spacing:.2em;
  text-transform:uppercase; color:var(--dim); margin:1.6rem 0 .2rem;}

footer.page{margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line);
  font-family:var(--mono); font-size:.68rem; color:var(--dim); letter-spacing:.06em;}

@media (prefers-reduced-motion: no-preference){
  details.explain .x-body{animation:fade .18s ease;}
  @keyframes fade{from{opacity:0}to{opacity:1}}
}
```

- [ ] **Step 2: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/theme.css
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: canonical theme.css design system"
```

---

### Task 3: §0 fact-check notes (doc vs. code)

**Files:**
- Read: `aeon/docs/ENGINE_ARCHITECTURE.md:147-847` (§0.1–§0.14)
- Read: `aeon/engine/system/vectors.asm`, `boot.asm`, `vdp_init.asm`, `z80_init.asm`, `header.inc`, `hblank.asm`, `vblank.asm`
- Create: `<scratchpad>/section0-facts.md` (working notes, not committed)

- [ ] **Step 1: Read doc §0 in full** (lines 147–847 of `ENGINE_ARCHITECTURE.md`).

- [ ] **Step 2: Cross-check the high-risk claims against code.** For each, record `VERIFIED (file:line)` or `DIVERGES (doc says X, code does Y)` in the notes file:
  - Initial SSP value and Reset PC (`vectors.asm` vs doc table §0.1)
  - RAM-patched HBlank vector — stub exists and reads a RAM pointer (`vectors.asm`/`hblank.asm`)
  - TMSS sequence — soft-reset checks *before* TMSS write, version-register nibble test (`boot.asm` vs §0.2)
  - VDP register init table — all 24 values (`vdp_init.asm` vs §0.3 table). Diff every value; the wiki reproduces this table and must match **code**, not doc
  - VDP shadow table exists in RAM (`vdp_init.asm`/`ram.asm` vs §0.4)
  - Z80 init order and PSG/YM silencing (`z80_init.asm` vs §0.5–0.6)
  - DMA-parallel memory clear actually implemented (`boot.asm`/`vdp_init.asm` vs §0.7 — doc marks it NOVEL; confirm it shipped)
  - Region detection mechanism (§0.8) and controller init (§0.9)
  - Boot order list (§0.12) vs the actual instruction order in `boot.asm`

- [ ] **Step 3: Write the notes file** at the scratchpad path with one line per claim: status, evidence pointer, and (if divergent) the sentence the wiki should say instead.

- [ ] **Step 4: Report divergence count.** If any DIVERGES, they become `.diverge` blocks in Task 4 — the page states code truth and flags the doc.

---

### Task 4: Author `aeon/section-0-boot.html`

**Files:**
- Create: `empyrean/wiki/aeon/section-0-boot.html`
- Source of truth: Task 3 notes + code files

**Content structure** (14 doc subsections grouped into a readable narrative):

1. **Header** — eyebrow `AEON ENGINE · SECTION 0`, title "Boot & Hardware Init", sub: what the first ~2,000 cycles do. Breadcrumb `EMPYREAN / AEON / §0 BOOT` (hub link wired in Task 7; use `href="#"` placeholder until then). Expand-all-explainers button in the header.
2. **The first 256 bytes** (§0.1) — vector table narrative + *interactive vector-table diagram*: a 64-cell SVG/HTML grid; clicking a cell shows that vector's purpose and Aeon's value in a caption line. Decision blocks: SSP=`$FFFFFF00` (with provenance chips), RAM-patched HBlank, VBlank-in-ROM, TRAP-vectors-for-debug. Explainers: "What is a vector table?", "What is the stack?"
3. **Proving we're a licensed game** (§0.2) — TMSS narrative + real `boot.asm` excerpt with `file:line` attribution. Explainer: the 1989 lawsuit story. Decision: soft-reset check ordering.
4. **Programming the video chip** (§0.3–0.4) — *interactive VDP register table*: all 24 registers, each row expandable/highlightable to show the "why" (values from **code**, per Task 3). Explainer: "What is the VDP?" Decision: 64×64 planes; shadow table (from Batman & Robin, chips).
5. **Waking the sound hardware** (§0.5–0.6) — Z80 bus request/reset, PSG silence, YM reset. Explainers: "Why does a Genesis have two CPUs?", "Why must the Z80 be stopped?"
6. **Clearing 64KB the clever way** (§0.7) — DMA-parallel clear. Teaching example (`.teach` block): invented toy timeline comparing naive clear vs DMA-parallel. Explainer: "What is DMA?"
7. **Where in the world is this console?** (§0.8–0.9) — region detection, timing constants, controller ports. Explainer: 50Hz vs 60Hz and why PAL games ran slower.
8. **The interrupt switchboard** (§0.10–0.11) — dispatch architecture, soft-reset/CrossResetRAM.
9. **The whole sequence** (§0.12) — *boot-timeline diagram*: ordered horizontal/vertical stepper of the boot phases with one-line descriptions, matching verified code order.
10. **The assembler does the work** (§0.13–0.14) — build-time generation, compile-time validation; real excerpt of a build-time `error` guard.
11. **Footer** — "Part of the Empyrean wiki · maintained by Claude · last updated 2026-07-16" + link back to hub (placeholder until Task 7).

**Component markup patterns** (use exactly these classes from `theme.css`):

```html
<!-- explainer -->
<details class="explain">
  <summary>New here? — What is a vector table?</summary>
  <div class="x-body">…prose…</div>
</details>

<!-- invented teaching example -->
<div class="teach"><span class="t-tag">Teaching example — not engine code</span>
  …toy scenario…</div>

<!-- decision with provenance -->
<div class="decision"><span class="d-tag">Decision</span>
  …what + why…
  <p class="prov-label">Who does what</p>
  <div class="prov"><span class="yes">Vectorman ✓ …</span><span class="no">S.C.E. — …</span></div>
</div>

<!-- real code excerpt -->
<pre>…asm with .c/.k/.n spans…</pre>
<span class="src">engine/system/boot.asm:6</span>

<!-- divergence flag (only if Task 3 found one) -->
<div class="diverge"><span class="v-tag">Doc divergence</span>
  The architecture doc says X; the code does Y (file:line). This page follows the code.</div>
```

**Expand-all switch JS** (include verbatim):

```html
<script>
function expandAll(btn){
  const all = document.querySelectorAll('details.explain');
  const open = ![...all].every(d=>d.open);
  all.forEach(d=>d.open=open);
  btn.textContent = open ? 'Collapse all explainers' : 'Expand all explainers';
}
</script>
<button class="xall" onclick="expandAll(this)">Expand all explainers</button>
```

- [ ] **Step 1: Write the page** following the structure above. Inline the full current `theme.css` in `<style>`. Set `<title>Aeon §0 — Boot &amp; Hardware Init</title>`. No `<!DOCTYPE>/<html>/<head>/<body>` wrapper tags (artifact publisher adds them). Every real excerpt gets a `.src` attribution; every invented example gets a `.teach` wrapper; every claim comes from Task 3 notes.

- [ ] **Step 2: Static checks**

Run: `grep -c 'details class="explain"' empyrean/wiki/aeon/section-0-boot.html`
Expected: ≥ 6 (one per planned explainer minimum).

Run: `grep -n 'TBD\|TODO\|lorem' empyrean/wiki/aeon/section-0-boot.html`
Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/aeon/section-0-boot.html
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: Aeon §0 Boot exemplar page (pre-publish, hub links pending)"
```

---

### Task 5: Publish §0 page (controller session only)

- [ ] **Step 1: Publish** with the Artifact tool: `file_path` = the section-0 file, `favicon` = `⚡`, `description` = "Aeon engine §0 — boot & hardware init, from vector table to game loop, with beginner explainers." Do NOT pass `url` (new artifact).

- [ ] **Step 2: Record the URL** in `empyrean/wiki/urls.json` under `aeon/section-0-boot.url`.

- [ ] **Step 3: Verify the published page** — load the artifact URL: explainers expand/collapse, expand-all toggles, vector-table diagram click works, register table interaction works, no horizontal body scroll, code blocks scroll internally.

- [ ] **Step 4: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/urls.json
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: record §0 artifact URL"
```

---

### Task 6: Author `hub.html`

**Files:**
- Create: `empyrean/wiki/hub.html`

**Content structure:**

1. Header — eyebrow `THE EMPYREAN SUITE`, title "EMPYREAN", sub: one-paragraph suite thesis (a ground-up Genesis engine and the toolchain around it, documented down to first principles).
2. `hub-h` "The Suite" + `hub-grid` of `card tool` divs: AEON, SIGIL, ORACLE, SERAPH, AURORA — one-line honest descriptions (Sigil: "from-scratch Rust assembler, byte-identical output"; Oracle: "emulator/debugger with deep inspection"; Seraph: "the DAW"; Aurora: "the editor"). All `div.card.tool.soon` with `<span class="soon-tag">page coming</span>` except none link yet (tool pages are out of scope v1).
3. `hub-h` "Aeon — the engine, section by section" + `hub-grid` of all ten section cards (§0–§9, names/one-liners from `ENGINE_ARCHITECTURE.md` System Index, lines 11–27). §0 is an `<a class="card">` whose `href` is the URL recorded in `urls.json`; §1–§9 are `div.card.soon` with `soon-tag`.
4. Footer — "AI-authored · maintained on request · sources in empyrean/wiki/".

- [ ] **Step 1: Write `hub.html`** (inline theme.css copy, `<title>EMPYREAN — Engine &amp; Toolset Wiki</title>`, §0 card href = real URL from urls.json).

- [ ] **Step 2: Static check** — `grep -c 'card soon' empyrean/wiki/hub.html` → expected ≥ 13 (9 sections + 5 tools, minus the linked §0). Confirm exactly one `<a class="card"` (the §0 link).

- [ ] **Step 3: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/hub.html
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: Empyrean hub page (§0 linked, rest marked coming)"
```

---

### Task 7: Publish hub + backfill cross-links (controller session only)

- [ ] **Step 1: Publish hub** — Artifact tool, `favicon` = `🕹️`, `description` = "Central hub for the Empyrean suite wiki — Aeon engine sections and toolset pages." No `url` param (new artifact).

- [ ] **Step 2: Record hub URL** in `urls.json` under `hub.url`.

- [ ] **Step 3: Backfill §0 links** — in `section-0-boot.html`, replace both `href="#"` placeholders (breadcrumb EMPYREAN/AEON and footer hub link) with the hub URL.

- [ ] **Step 4: Redeploy §0** — Artifact tool with the SAME `file_path` as Task 5 (same-session redeploy targets the same URL), same favicon `⚡`, label `link-backfill`.

- [ ] **Step 5: Verify navigation both ways** — hub §0 card → §0 page; §0 breadcrumb → hub.

- [ ] **Step 6: Commit**

```bash
git -C /home/volence/sonic_hacks/empyrean add wiki/urls.json wiki/aeon/section-0-boot.html
git -C /home/volence/sonic_hacks/empyrean commit -m "wiki: hub published; cross-links backfilled into §0"
```

---

### Task 8: Final verification & handoff

- [ ] **Step 1: Registry consistency** — `jq -e '.hub.url and .["aeon/section-0-boot"].url' wiki/urls.json` → `true`. Every artifact URL appearing in an `href` in either HTML file must equal the corresponding `urls.json` entry (grep each URL and compare).

- [ ] **Step 2: Theme sync check** — the inline `<style>` in both pages contains the current `theme.css` content (spot-check a late rule, e.g. `footer.page`).

- [ ] **Step 3: Full visual pass** on both published artifacts (widgets, links, mobile-width check via narrow window: no horizontal body scroll).

- [ ] **Step 4: Verify empyrean repo is clean** — `git -C /home/volence/sonic_hacks/empyrean status -s wiki/` → empty.

- [ ] **Step 5: Report to user** — both URLs, divergences found in Task 3 (if any), and the open question for the fan-out phase: approve the exemplar format before building §1–§9.
