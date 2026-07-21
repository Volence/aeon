# ComfyUI AI Art Pipeline — Design

**Date:** 2026-07-12
**Status:** Approved (brainstorm 2026-07-12); Milestone 1 scoped
**Decisions locked with user:** backgrounds first · AI-proposes-palette (snap after) · full loop with human preview gate

## Problem

There is no art-production path for new Sonic 4 zones. All current level art is migrated
sonic_hack data. We want an AI-assisted path that produces **engine-legal** assets: Genesis
palette rules, 8×8 4bpp tiles, dedup budgets, and our editor/build formats — driven end-to-end
by Claude Code so the user only judges art, never runs tools.

## Feasibility summary (research 2026-07-12)

- **Engine side is already most of the pipeline.** `tools/ojz_strip_gen.py` performs dedup
  (flip-canonicalization), spatial ordering, paging, and ZX0 compression. An AI path only needs
  to deliver a quantized indexed image on the tile grid plus a palette line; a small ingest tool
  closes the gap to editor formats.
- **ComfyUI side is mature where Milestone 1 needs it**: pixel-art LoRAs (SDXL), downscale-to-grid
  + palette-quantize nodes (ComfyUI-PixelArt-Detector, PixydustQuantizer), seamless-tiling nodes,
  and a robust local MCP (artokun/comfyui-mcp, Claude Code plugin, arbitrary workflow JSON).
- **Hardware verified**: RTX 2080 Ti 11GB (SDXL comfortable; FLUX fp8 marginal), 550GB free disk.
  System Python is 3.14 — too new for ComfyUI; use a uv-managed 3.12 venv.
- **Known weak spots (by design, deferred)**: structured FG tilesets with matching edges
  (raw ComfyUI is poor; Retro Diffusion rd-tile is the Milestone 2 add-on candidate) and
  multi-frame character animation (unsolved identity drift; not targeted).

## Goals (Milestone 1)

An AI-generated **background** visible behind OJZ Act 1 in Oracle, produced by:
generate → quantize → preview gate (user approves) → ingest → build → Oracle verification,
with zero manual steps besides the approval.

## Non-goals (Milestone 1)

- FG terrain tilesets, autotiles, edge-matched transitions (Milestone 2; likely PixelLab/rd-tile assisted)
- Character or badnik sprite animation
- New-zone layout/section generation
- Any engine (68k/Z80) code changes — this is a tools/content pipeline only

## Hard constraints (engine facts the pipeline must satisfy)

| Constraint | Value |
|---|---|
| Tile | 8×8 px, 4bpp packed, 32 bytes |
| Palette | 15 colors + transparent per line; 9-bit RGB (3 bits/channel); RGB555-encoded words in `ojz_palette.bin` (96 B = 3 lines) |
| Palette lines | 3 usable per level (line 3 reserved for effects); BG typically owns one line |
| BG tile budget | **448 unique tiles** zone-wide (VRAM slots 1024–1471), after flip-canonical dedup |
| BG source format | `games/sonic4/data/editor/ojz_act1_bg_tiles.bin` (raw tiles) consumed by `ojz_strip_gen.py` |
| Wrapping | BG must tile seamlessly in X (horizontal parallax wrap) |

## Architecture

```
ComfyUI (local, RTX 2080 Ti)
  │  workflow JSON: prompt → SDXL + pixel-art LoRA → seamless-X → downscale-to-grid
  ▼
output PNG (large, unconstrained colors)
  │  tools/genesis_ingest.py
  │    1. extract 15-color palette (median-cut/K-means)
  │    2. snap palette to 9-bit RGB
  │    3. quantize image (dithering OFF by default — dithering destroys tile dedup)
  │    4. cut into 8×8 tiles, flip-canonical dedup (same logic as ojz_strip_gen)
  │    5. HARD GATE: unique tiles ≤ 448, else remediation ladder (see Error handling)
  │    6. emit preview sheet: quantized image + palette swatch + tile-count stats
  ▼
USER PREVIEW GATE (approve / regenerate)
  │  on approval: write ojz_act1_bg_tiles.bin (+ nametable layout) + BG palette line
  ▼
existing pipeline: ojz_strip_gen.py → build.sh → s4.bin
  ▼
Oracle: load, screenshot DURING scroll motion (at-rest shots hide parallax artifacts)
```

Claude Code drives every arrow: ComfyUI via the artokun MCP (fallback: raw HTTP `/prompt` API),
ingest/build via Bash, verification via Oracle MCP (foreground only — never from subagents).

## Components

1. **ComfyUI install** — `~/ComfyUI` (outside the repo), uv-managed Python 3.12 venv, CUDA.
   Models: SDXL base checkpoint + pixel-art LoRA (nerijs/pixel-art-xl or Pixel Art Diffusion XL).
   Custom nodes: ComfyUI-PixelArt-Detector, ComfyUI-seamless-tiling, ComfyUI-PixydustQuantizer.
   ~15GB disk. Run as a user service or launched on demand.
2. **MCP registration** — artokun/comfyui-mcp Claude Code plugin, pointed at the local instance.
   Treated as a convenience layer; the workflow must also be submittable via a plain script
   hitting ComfyUI's HTTP API so the pipeline survives MCP churn.
3. **`tools/comfy/bg_gen.json`** — checked-in parameterized workflow (prompt, seed, dimensions).
   Output sized to the BG plane in multiples of 16 px; generated large, downscaled to true
   pixel grid by the pixel-art nodes.
4. **`tools/genesis_ingest.py`** (new) — the piece nothing off-the-shelf provides:
   palette extract + 9-bit snap + quantize + tile cut + flip-canonical dedup + budget gate +
   preview sheet + editor-format emit. Reuses/imports the dedup logic from `tile_dedupe`
   rather than reimplementing it. `--palette <file>` flag reserved (lock-mode for retrofits)
   but extract-mode is the Milestone 1 default.
5. **Preview gate** — ingest writes `preview_<name>.png` + stats; user approves before any
   engine-consumed file is written. No auto-ingest in Milestone 1.
6. **Verification** — DEBUG build, Oracle load, mid-scroll screenshots; compare CRAM against
   the emitted palette line.

## Error handling

The expected failure mode is **tile-budget overflow** (organic AI output dedups far worse than
hand-drawn art — this is the single biggest risk in the design). Remediation ladder, in order:

1. Quantize harder / ensure dithering off (dither is the #1 dedup killer)
2. Posterize / flatten low-detail regions before tile cut
3. Reject with guidance: regenerate with a flatter, more repetitive prompt (sky bands,
   cloud shapes, silhouette hills — classic Genesis BG idioms exist *because* of this constraint)

The 448-tile check is a hard gate: no engine file is ever written from an over-budget image.
Other failures: ComfyUI job errors surface via MCP job status (retry/regen); build or Oracle
failures follow normal engine debugging practice.

## Testing

- `genesis_ingest.py` unit tests: known 16-color test image → exact expected tile bytes,
  palette snap correctness (every channel ∈ {0,2,4,…,14} <<1 in RGB555 terms), dedup count
  matches `ojz_strip_gen`'s on the same input, budget gate trips at 449.
- Golden check: re-ingesting the CURRENT OJZ BG art through the tool round-trips byte-identical.
- End-to-end: the Milestone 1 exit criterion itself (AI BG in Oracle, mid-scroll screenshots).

## Milestones

- **M1 (this spec):** BG pipeline end-to-end, OJZ Act 1 as proving ground.
- **M2:** FG terrain tilesets — add Retro Diffusion rd-tile (Replicate) as the primary external
  generator candidate; ingest spine unchanged. Requires edge-matching validation.
  (PixelLab.ai demoted: user has tried it and found results poor — 2026-07-12.)
- **M3:** Object sprites (static/few-frame) → `data/sprites/<name>/` + DPLC via existing tools.

## Alternatives considered

- **PixelLab.ai MCP as backbone** — turnkey, ships its own Claude Code MCP, but paid credits,
  less control, not Genesis-palette-native — and the user has already tried PixelLab with poor
  results. Rejected as backbone and demoted from the M2 shortlist.
- **Retro Diffusion (Replicate API)** — best purpose-built pixel model incl. tile mode, but
  API-only (weights unreleased, can't run in ComfyUI) and per-image cost. M2 add-on candidate.
- **Locked-palette generation** — feed existing palette into ComfyUI's quantizer. Rejected for
  M1 (new-zone use case wants AI-proposed palettes); preserved as ingest `--palette` lock mode.
