# Tile-budget deep dive — why a 612-tile level fails a 1536-tile VRAM

**Date:** 2026-06-22
**Trigger:** OJZ act1 section-0 layout edits "weren't showing in game." Build was
silently failing on a tile-budget check; user's intuition was that the content is
mostly-repeated and shouldn't need so many tiles. **The intuition was correct.**

## TL;DR

The whole OJZ level uses **612 distinct tiles**. The FG VRAM pool holds **1,536
tiles**. The level fits in VRAM **2.5× over** — VRAM is 60% empty. The build fails
anyway because the engine decompresses each section's art through a **300-tile RAM
staging buffer** (`Decomp_Buffer`, 9,600 bytes) in a single pass, and section 0's
art is 603 tiles (19,296 bytes). **The per-section streaming + its 300-tile RAM
buffer is the sole bottleneck; it is over-engineered for any level that fits VRAM.**

## The numbers (measured from the saved layout + decompressed art)

| Quantity | Value | Source |
|---|---|---|
| FG VRAM capacity | **1,536 tiles** | `tools/ojz_strip_gen.py:116 REGION1_TILE_CAPACITY` |
| Whole level distinct tiles (9 sections) | **612** | union of `section_*.tiles.bin` |
| Section 0 distinct tiles | 602 | `section_0.tiles.bin` |
| Sections 1–8 | 100–176 each (≈10 *new* beyond s0) | per-section |
| VRAM reserved by current build | **884** (272 duplicated) | `export/vram_bases.asm` bases [0, 603] |
| RAM decompress buffer (`Decomp_Buffer`) | **300 tiles / 9,600 B** | `engine/level/load_art.asm:38` |
| Section 0 art blob | 603 tiles / 19,296 B → **fails the 9,600 check** | build output |
| Free VRAM with whole level loaded | **924 tiles** | 1536 − 612 |

### Section 0's 602 tiles are genuinely distinct (not bloat)
- 0 exact-duplicate tiles, **0 mergeable even up to flip** — the dedup is correct.
- Only 9% are within 4px of another used tile; not near-duplicate spam.
- 42% are used exactly once (detailed one-off organic art).
- 22 distinct chunks, 64 placements; the chunks barely share tiles, so 22 chunks → 602.

### Comparison to a real Genesis zone (Sonic 2 EHZ)
- EHZ `ArtKos_EHZ` = **914 tiles in VRAM, 688 distinct** — for the **whole zone**.
- Sonic 2 loads that **once** and the entire zone draws from it (fixed tileset).
- Our **whole level (612)** is *smaller* than EHZ's tileset, yet our engine streams
  per-section with a 300-tile cap — **3× tighter per section than S2's whole-zone budget.**

## Why the waste happens

`ojz_strip_gen.generate()` always runs the generic streaming pipeline:
1. Dedup all referenced tiles → **612** canonical tiles (correct).
2. 2-color the 3×3 section grid (DSATUR) → groups {0,2,4,6,8} and {1,3,5,7}.
3. Assign each color group its **own** VRAM region → bases `[0, 603]`.
4. Emit a per-color-group art blob; a section loads its group's blob into VRAM.

Because every section uses ≈the same 612 tiles, the two color regions overlap
heavily — **272 tiles are stored twice** (884 reserved vs 612 distinct). And each
group's blob (603 tiles) must decompress through the 300-tile `Decomp_Buffer` →
**hard fail.** The color-grouping/streaming is designed for levels whose total tiles
*exceed* VRAM; for a level that fits, it only adds duplication and an artificial cap.

## The fix (recommended): whole-level shared tileset, loaded once (the Sonic 2 model)

When a level's total distinct tiles ≤ VRAM capacity (612 ≤ 1536, with 924 to
spare), skip color-grouping entirely:

- **Build (`ojz_strip_gen`)**: emit ONE shared tileset of all 612 tiles; remap every
  section's block tile-references to the shared slot space (the dedup already
  produces this before grouping splits it). Optionally split the blob into ≤300-tile
  segments for the loader.
- **Engine (`load_art` / level init)**: load the shared tileset once at init by
  decompressing in N ≤300-tile passes (612 → 3 passes through `Decomp_Buffer`),
  DMA'ing each to consecutive VRAM. Then the per-section **art** reload is gone; the
  nametable tile-cache streaming (layout) is unchanged.

Result: section 0 builds untouched, 612/1536 VRAM used, 0 duplication, behaves like
a real Genesis zone. Keep the per-section streaming path for a *future* level whose
total exceeds 1536 (pick the path by total-tile count at build time).

### Alternative (smaller, keeps streaming): multi-pass per-section decompress
Allow a section's blob to exceed 300 tiles by decompressing in multiple ≤300-tile
passes to consecutive VRAM. Keeps color-grouping (so the 272-tile duplication
remains) but unblocks over-budget sections. Less clean than the shared-tileset fix.

## Verification note
Build's VRAM check (884 < 1536) PASSES; the ONLY failure is the `Decomp_Buffer`
9,600-byte staging check. Confirmed by the single build error:
`sec0_tiles.bin is 19296 bytes — exceeds Decomp_Buffer capacity (9600)`.
A tile-loading change can be verified by emulator SCREENSHOT (does the art render
correctly?) — the OJZ build boots a scroll-test harness where player physics is
frozen, but tile/plane rendering is live.
