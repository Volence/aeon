# §2 Phase 2 — Per-layer measurements

Running tally as A.1 → A.5 ship. Each row is the *same* OJZ Act 1 build pass; columns reflect what each layer adds on top of the previous.

| Date | Layer | What it does | OJZ Act 1 unique tiles after | Deduped pool S4LZ size | VRAM region(s) used | Pool fits in 1536 |
|------|-------|---|---:|---:|---|---|
| 2026-04-26 | Pre-A.1 baseline | Stream-0-only, raw export, no dedupe | 322 (referenced range, no dedupe) | n/a (raw 10240 B) | $0000-$2840 (320 tiles) | yes |
| 2026-04-26 | A.1 | Global dedupe + flip canonicalization + nametable remap; STRIP_TILE_HEIGHT 32→48 | **10** | tbd (see Task 9) | $0000-$0140 (10 tiles) | yes |

**A.1 caveat:** The 10-tile result reflects the visible strip band only (chunk-rows 0-2 of the 16-row OJZ layouts = sky + cloud + first ground band). The full 16-row layouts contain rich ground/terrain that's not currently sampled because the visible nametable region is capped at row 48 by the sprite attribute table at VRAM $D800. Larger numbers will surface when either:
- A.4 streaming + vertical-axis section transitions allow camera to traverse more of each section's 16 chunk-rows, or
- The sprite table gets relocated (out of A.1 scope; would unlock strip rows 48-63 for additional layout coverage).

The trivial dedupe ratio is *not* a sign that A.1 is broken — it's the honest baseline at the current visibility envelope. A.1's job is to plumb the pipeline so that when bigger numbers arrive (A.2-A.5 or via vertical streaming), the remap produces correct output.

**A.2 (multi-region VRAM packing):** to be filled when that layer ships.

**A.3 (graph coloring):** to be filled.

**A.4 (per-section S4LZ Deferrable streaming):** to be filled.

**A.5 (per-section background tiers):** to be filled.

## Methodology

`python3 tools/ojz_strip_gen.py generate` prints an "OJZ Act 1 — Phase A.1 measurement" block at the end of its run. After A.2-A.5 land, the same block extends with the new metrics. Numbers in this file are copied verbatim from those build-tool outputs.
