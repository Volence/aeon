# §2 Phase 2 — Per-layer measurements

Running tally as A.1 → A.5 ship. Each row is the same OJZ Act 1 build pass; columns reflect what each layer adds on top of the previous. Numbers come verbatim from `python3 tools/ojz_strip_gen.py generate`.

## OJZ Act 1, all 16 sections, current strip-height envelope

| Layer | Strip height | Source indices referenced | Max source index | Indices ≥1536 (nametable collision) | Deduped pool | Max remapped index | Pool fits 1536? | Deduped blob bytes (uncompressed) | S4LZ blob bytes | VRAM region(s) used |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| **Pre-A.1** | 32 | n/a (no walk) | n/a | **would clobber** | n/a — fixed 322-tile slug | n/a | n/a | 10,304 | n/a | $0000-$2840 (322 tiles, no actual nametable mapping; high indices rendered as garbage) |
| **A.1** | 48 | 14 (min=0, max=1856) | **1856** | **2** | **10** (28.6% reduction) | **9** | yes | 320 | **262** (ratio 0.819, tile-delta) | $0000-$013F (10 tiles) |
| A.2 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |
| A.3 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |
| A.4 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |
| A.5 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |

## A.2 spill path validated on synthetic stress

OJZ act 1 doesn't naturally exceed 1536 tiles — the deduped pool is only 10 tiles. To confirm A.2's spill path works end-to-end, the build was run with `--force-region1-cap=5`, artificially capping region 1 at 5 tiles and forcing 5 tiles into region 2 ($F800-$F89F). Exodus screenshot of the forced-spill build is byte-identical to the default-build screenshot — proves the nametable remap correctly references both regions and the runtime loader DMAs to the right VRAM addresses.

The forced-spill row's max remapped index of **1988** demonstrates the tile-index field successfully spans into region 2's slot range (1984+). That's the spec's promise (the 11-bit tile-index field can address the entire 2048-tile VRAM space), made real.

## Headline: A.1 closes the OJZ visibility deferred item

The deferred-work entry "OJZ Tile Art Loading — Full Terrain Visibility" pointed at this exact bug: strips reference tile index **1856**, which lands inside Plane A's nametable at VRAM byte $C000 (= tile slot 1536). Loading "tiles 0-1856 linearly" clobbers the nametable.

**Pre-A.1:** Old pipeline shipped a fixed 322-tile slug (`OJZ_TILES_COUNT = 322`) regardless of what the strips referenced. Anything strip-referenced ≥ 322 rendered as garbage. The visible test showed only sky tiles because that's the band where indices stayed below 322.

**Post-A.1:** Strips' tile-index field is rewritten via `remap_nametable_word`. The 14 unique source indices the strips reference (max 1856) collapse to a 10-tile canonical pool (max remapped index 9), with H/V flip bits XOR'd to recover original orientation. Nametable references stay safely below 1536. Plane A nametable preserved.

**Source indices the strips reference (before remap):**
`[0, 36, 67, 68, 142, 248, 256, 320, 321, 848, 1280, 1344, 1536, 1856]`

Indices 1536 and 1856 are the two collision-risk entries. After remap, both rewrite to compact canonical indices.

## A.1 caveats / future bigger numbers

The 14-references / 10-deduped figures are small because the visible 48-row strip band only samples chunk-rows 0-2 of OJZ's 16-row layouts (sky + cloud + first ground band). The sprite attribute table parks at VRAM $D800 (= nametable row 48), capping strip height there. Future bigger numbers expected when:

- A.4 streaming + vertical-axis section transitions let camera traverse more of each section's 16 chunk-rows
- Or sprite table relocation (out of A.1 scope) unlocks strip rows 48-63

A.1's job is to plumb the pipeline correctly so when bigger numbers arrive, the remap produces correct output. The 14→10 dedupe ratio (28.6%) is the genuine algorithmic win on this dataset; the bigger story is the index-ceiling drop from **1856 → 9**, which is what unblocks rendering the first ground band.

## Methodology

`python3 tools/ojz_strip_gen.py generate` prints an "OJZ Act 1 — Phase A.1 measurement" block at the end of each run, with all metrics in this table. Each new layer's plan extends the build tool to print additional rows; numbers in this file are copied verbatim from those outputs.
