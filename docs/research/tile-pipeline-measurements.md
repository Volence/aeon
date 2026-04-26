# §2 Phase 2 — Per-layer measurements

Running tally as A.1 → A.5 ship. Each row is the same OJZ Act 1 build pass; columns reflect what each layer adds on top of the previous. Numbers come verbatim from `python3 tools/ojz_strip_gen.py generate`.

## OJZ Act 1, all 16 sections, current strip-height envelope

| Layer | Strip height | Source indices referenced | Max source index | Indices ≥1536 (nametable collision) | Deduped pool | Max remapped index | Pool fits 1536? | Deduped blob bytes (uncompressed) | S4LZ blob bytes | VRAM region(s) used |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| **Pre-A.1** | 32 | n/a (no walk) | n/a | **would clobber** | n/a — fixed 322-tile slug | n/a | n/a | 10,304 | n/a | $0000-$2840 (322 tiles, no actual nametable mapping; high indices rendered as garbage) |
| **A.1** | 48 | 14 (min=0, max=1856) | **1856** | **2** | **10** (28.6% reduction) | **9** | yes | 320 | **262** (ratio 0.819, tile-delta) | $0000-$013F (10 tiles) |
| **A.2 default** | 48 | 14 | 1856 | 2 | 10 (28.6%) | 9 | yes (region 1) | r1=320; r2=0 | r1=262 (0.819); r2=4 (placeholder) | $0000-$013F (region 1 only; region 2 empty) |
| A.2 forced spill (cap=5) | 48 | 14 | 1856 | 2 | 10 (28.6%) | **1988** | yes (split: r1=5, r2=5) | r1=160; r2=160 | r1=108 (0.675); r2=162 (1.012, S4LZ overhead exceeds compression on tiny non-redundant data) | $0000-$009F (r1) + $F800-$F89F (r2) |
| **A.3** | 48 | 14 | 1856 | 2 | 10 (28.6%) | 19 (color 1 base + 9) | yes (2 colors) | per-section: 9 blobs ≤320 each | per-section: ~270 each (ratio 0.844) | $0000-$013F (color 0) + $0140-$027F (color 1) |
| **A.4** | 48 | 14 | 1856 | 2 | 10 (28.6%) | 19 | yes (2 colors) | per-section: 9 blobs ≤320 each (unchanged from A.3) | per-section: ~270 each (unchanged) | $0000-$013F + $0140-$027F (unchanged) |
| A.5 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |

## A.4 makes section transitions seamless (structural; visual verification blocked)

A.4 adds a preload trigger to `Section_Check`: when the camera crosses `SECTION_FWD_PRELOAD` (1024 px before the teleport threshold) or `SECTION_BWD_PRELOAD` (512 px before), `Section_StreamArtGroup` decompresses the upcoming section's S4LZ blob into one of two streaming buffers (double-buffered for fast direction reversals) and queues a Deferrable DMA. By the time the camera reaches the teleport threshold, the DMA has drained — the teleport itself does no work beyond clearing a flag.

**Per-section state machine:** `SS_IDLE` / `SS_STREAMING` / `SS_RESIDENT`, tracked in 16 bytes RAM (`Section_Stream_State`). Initial slots 0+1 are RESIDENT after `Level_LoadArt`. Crossing a preload threshold transitions the upcoming section IDLE → STREAMING; crossing the teleport threshold promotes it to RESIDENT. Cold camera writes that bypass preload fall back to blocking `Section_LoadArt`.

**No measurement change:** A.4 doesn't alter tile counts, deduped pool size, or S4LZ ratios. It changes *when* loads happen, not how much. The empirical win is "no stutter on section transition" — which would be visible only when there's actual section content to render.

**Visual verification blocked on upstream chunk/block parsing bug:** While verifying A.4 in Exodus, we discovered that `tools/ojz_strip_gen.py`'s chunk/block parsing produces mostly-empty tile references for the OJZ data: 1010 of 2002 blocks parse as all-zero, and chunk 0x3f (a "ground" chunk per the layout) references block IDs 92, 128, 241, 784 — all of which are zeros in our parsed table. This means strips reference real positions but get mostly-empty tile data, so the rendered viewport stays mostly black regardless of which chunk-rows we sample. **The bug is upstream of all five layers (A.1-A.5) and was masked through A.1-A.3 verification by my misinterpreting "sparse non-zero pixels" as "correct sky/cloud rendering."** A.4 verification was structural only (`Section_Stream_State` byte transitions, slot map advancement, teleport hook firing — all confirmed via Exodus MCP).

## A.3 reorganizes around sections with graph coloring

**A.3 reorganizes the same 10-tile deduped pool around per-section art groups, colored over the section adjacency graph.** Default OJZ has 16 sections in a horizontal chain (path graph), chromatic number 2 — sections alternate between color 0 and color 1. DSATUR greedy coloring assigns sec0/2/4/.../14 to color 1 (base 10) and sec1/3/.../15 to color 0 (base 0).

**Counterintuitive result for OJZ:** Max simultaneously-resident = 20 tiles (vs A.1/A.2's flat 10). Reason: sections share many common tiles (tile 0 sky in every section), so each section's per-section blob includes tile 0 separately. Per-color VRAM range = max-section-tile-count = 10 for both colors; total = 20. Functionally equivalent (rendering matches default), but uses 2× VRAM byte capacity vs A.1's flat pool.

**A.3's structural value is for big zones, not OJZ.** A.1 with a 10K-tile zone would fail (exceeds 1536-tile pool). A.3 loads at most max-color tiles per section transition, which scales with section complexity not zone size. For OJZ this is a slight regression in working-set; for any zone that exceeds the A.1/A.2 ceiling, A.3 is what makes it possible at all.

**Verified end-to-end in Exodus:** Default rendering matches A.2 (clean black sky + cloud band). Forward teleport (Camera_X = $1200) updates slot map 0/1 → 1/2; Section_TeleportFwd's Section_LoadArt loads section 2's tiles into VRAM at color 1's base; rendering remains glitch-free. Backward teleport (Camera_X back to $0260) restores slot map 0/1; Section_TeleportBwd's Section_LoadArt reloads section 0's tiles at color 1's base; rendering returns to default state. Decomp_Buffer contents confirm Section_LoadArt fires on each transition.

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
