# STITCHED-ACT-PAGE-ORDER: foreground tile-page orders measured against M-B's windows

> **Research slice for STITCHED-ACT-PAGE-ORDER (2026-09-16).** Tool-only measurement. No shipped order,
> engine file or ROM byte changes here. Tool: `tools/megaact_page_order.py` (built on
> `tools/megaact_window_pageset.py`). Evidence, all in this directory: `09-page-order-results-s2.json`,
> `09-page-order-results-s3k.json`, `09-page-order-results-ojz.json`, `09-page-order-timing-s3k-chain.json`.
> Donors as M-B: s2disasm `e45ebf3`, skdisasm `2fcd861`.
>
> Labels: **MEASURED** = printed by the tool from donor or editor data run through the replayed pipeline.
> **DERIVED** = computed from measured numbers or read from source at this revision. **INFERRED** = a reading
> of code, or a cause, that nothing here ran. No label below is stronger than what backs it.

---

## Verdict

**Yes, at 12 frames. No, at 10.**

One candidate order, `refined_zonesplit`, keeps **every camera window of every M-B population at or under 12
frames**. That covers S2 and S3K single zones, pairs, the offset sweeps, the junctions (both alignments) and
both whole-game rows. It is MEASURED on exactly M-B's acts, with M-B's numbers re-derived first as a control.

`refined_zonesplit` = a Hilbert-curve spatial order, then a deterministic swap search that attacks the windows
over budget, with dedupe keyed per zone.

| Population (windows counted) | Shipped: worst, windows over 12 | `refined_zonesplit`: worst, windows over 12 | `refined_zonesplit`: windows over 10 |
|---|---|---|---|
| S3K pairs, seam windows (1,086,092) | 15, 11,208 in 11 acts | **12, 0** | 21,763 in 27 acts |
| S3K pairs, one-zone windows (65,185,448) | 16, 513,992 in 26 acts | **12, 0** | 1,158,124 in 64 acts |
| S3K offset sweep, seam windows (766,300) | 18, 43,059 in 32 acts | **12, 0** | 3,803 in 13 acts |
| S3K junctions, junction windows (146,624) | 21, 68,957 in 45 acts | **12, 0** | 21,625 in 42 acts |
| S3K 10-zone row, all windows (4,868,730) | 18, 227,206 (4.67%) | **12, 0** | 183,187 (3.76%) |
| S2 junctions, junction windows (109,968) | 17, 10,296 in 12 acts | **12, 0** | 7,894 in 26 acts |
| S2 8-zone row, all windows (1,120,183) | 13, 11,575 (1.03%) | **12, 0** | 30,757 (2.75%) |
| OJZ act 1, all windows (257,367) | 10, 0 | 10, 0 | 0 |

All cells MEASURED ("acts" = acts with at least one such window; percentages DERIVED from the counts).

What this does **not** settle:

1. **No order gets the multi-zone populations under 10.** The best result at 10 frames is still 3.76% of the S3K
   row's windows over (MEASURED). A try at refining toward 10 made things worse on the acts it was tried on (see
   "Screened out").
2. **There is no margin at 12.** The worst window is exactly 12 wherever the search had work to do, because 12 is
   what it stops at (by construction; this is not a confound). 54,237 S3K-row windows need exactly 12 frames
   (MEASURED). A static count at the budget is necessary, not sufficient, for no soft-lock: M-B's list of transient
   demand (stalled columns keeping old references, in-flight decodes, prefetch) all lands on those windows.
3. **The order is a heuristic.** It met the target on these 404 acts. That does not prove it will on an authored
   mega-act. Adopting it without a build-time check on the placed act would be trusting a search, not a bound.

---

## Research: how others order streamed tile sets (brief, and what was actually read)

- **No reference engine pages a level tileset at this granularity, so none has an order to copy.**
  - S.C.E. loads a zone's primary and secondary 8x8 art as whole KosPlus modules and waits for the queue to empty
    (`Sonic-Clean-Engine-S.C.E.-/Engine/Core/Load Level.asm:10-31`, read this parcel).
  - S3K appends the secondary set after the primary (the `LoadLevelLoadBlock` path M-B's loader replicates).
  - Alien Soldier and Gunstar Heroes stream per-scene lists of 376 to 711 tiles into fixed VRAM ranges, and
    Vectorman loads its stage bank atomically (`03-vectorman-gunstar-aliensoldier.md` T1, T3, T8).
  - Batman & Robin swaps about 78 tiles per scripted scene (`04-batman-tf4-ristar.md`).

  The last two points come from the committed slices, not re-read here. Their "order" is a set partition by scene
  or zone. The nearest analogue in this parcel is the per-zone dedupe policy (`*_zonesplit`), not a tile order.
- **Virtual texturing** (van Waveren, *Software Virtual Textures*, cited in `06-...` and `engine/level/page_cache.emp:10`).
  Pages are spatial tiles of one 2D texture, so locality comes for free. Aeon's pages hold deduplicated tiles
  referenced from anywhere, which is why order matters here and not there. (DERIVED from the cited design.)
- **Space-filling curves.** Kamel and Faloutsos, *Hilbert R-tree* (VLDB 1994,
  https://www.vldb.org/conf/1994/P500.PDF). They order data by the Hilbert value of a rectangle's centre so that
  nearby objects share disk pages, and report up to 28% fewer disk accesses than the R*-tree. Read at abstract
  level only. This parcel tried both a centre key (`hilbert_centroid`) and a first-occurrence key
  (`hilbert_first`).
- **Co-occurrence packing.** Pettis and Hansen, *Profile Guided Code Positioning* (PLDI 1990,
  https://dl.acm.org/doi/10.1145/93542.93550). Greedy: merge the heaviest co-use edge first, "closest is best".
  Read at abstract/summary level only. `footprint_pack` is a greedy of that family on window co-occurrence.
- **Local search.** The refinement is a Kernighan-Lin-style swap search: fixed part sizes, moves judged by an exact
  change in cost. It is named from background knowledge; no source was read for it in this parcel.

---

## Candidates, and the policies each one takes

Every candidate puts the blank canonical at pool slot 0, which the engine requires
(`tile_dedupe.pin_blank_tile_first`; the tool refuses an order that does not). Everything after the order is the
unmodified pipeline, called by `megaact_window_pageset.run_pipeline(order_fn=...)`: the 64-tile split, the
75%-of-sections pin rule and the per-section local palette refusal.

| Candidate | Order | Shared-across-zone tiles | Near-singleton tiles |
|---|---|---|---|
| `shipped` | `order_pool_spatially`: first occurrence, flat section order, column-major | one pool slot (shipped dedupe) | no policy |
| `hilbert_first` | by the first 4x4-tile block the tile occurs in along a Hilbert curve over the act | one slot | no policy: placed at its first use |
| `hilbert_centroid` | by the Hilbert index of the tile's mean cell position | one slot | no policy |
| `footprint_pack` | page 0 = blank + the 63 widest tiles; each later page seeded by the earliest unassigned tile on the curve, then grown by the tile that adds the fewest new sample windows (stride 20x16) | one slot | no policy |
| `refined` | `hilbert_first`, then `refine_order` (below) | one slot | no special case: the search's move targets them (a "light" page is one with few present tiles, and the move evicts exactly those tiles) |
| `*_zonesplit` | the same order, after dedupe is keyed by (zone, canonical) | **one slot per zone**, so no window can reference another zone's page | as the base order |

**`refine_order`.** Everything below is DERIVED from the tool source at this revision.

- **Samples.** It scores superset samples: sample (i, j) is the union of every real window with left in
  [8i, 8i+7] and even top in [4j, 4j+2]. A real window's page count is therefore at most its sample's count.
- **Cost.** State is `cnt[sample, page]`. The cost is the sum of phi(pages) with phi(k) = 4^(k-10) - 1 above 10:
  steep, so one window at 13 is never traded for many at 11.
- **Move.** Take the worst non-stuck sample over 12. For each of its 5 lightest unpinned pages P and 6 heaviest
  pages Q:
  1. Move P's present tiles (at most 32) into Q.
  2. Swap back the same number of Q tiles that are absent from that sample, preferring tiles co-present with P
     elsewhere.
  3. If no single Q works, try once more with the group split round-robin across those pages.

  A move is kept only if the sample loses a page and the cost over every touched sample falls. Page sizes never
  change.
- **Loop.** Each sample gets one attempt per pass, and a new pass starts only if the last one kept a move. The
  budget is 6,000 tries per round: a count, not a time, so the output does not depend on machine speed.
- **Pins.** Rounds repeat with the shipped pin rule's pages counted as always present, until the pinned set stops
  growing (at most 3 rounds).
- **Output.** Within a page, the base order's sequence is kept, so a search that makes no moves returns the base
  order exactly.
- **Final numbers.** All numbers in this report are re-measured on the exact windows, never taken from the samples.

## What is counted, and the controls (all MEASURED)

`needed` is M-B's count: |pinned ∪ pages referenced by the window's non-blank words|, with the shipped pin rule
re-applied to each candidate's pages. It is also reported with only page 0 pinned (`needed_pin0`), and against
M-B's any-order floor ceil(distinct tiles / 64) as `gap = needed - floor`. Window geometry is M-B's (80x60, even
tops, every whole-tile left), and so are the populations. They are read from M-B's committed JSON (the pair list,
the worst and calm pair its ranking chose for the offset sweep, the junction triples and alignments, the row), so
nothing is re-ranked per candidate.

Controls. Every one runs inside `report` and refuses the run on failure; the JSON carries each result.

1. **Glue replay against the committed OJZ bake** (M-B's control, unchanged): 589,824 of 589,824 cells, 9 of 9
   local maps, pinned `[0,1,7,8,9]`.
2. **Presence counting.** The tool's per-page bounding-box counts were compared with
   `megaact_window_pageset.presence_counts` (full-grid integral images) on every window of LRZ1|CNZ1 under
   `shipped` and `footprint_pack`, and under `refined_zonesplit` in the later files. That is 1,096,110 or 1,644,165
   windows, plus 300 or 450 pure-Python direct scans. Result: 0 differences.
   - The Hilbert function is checked to be a bijection with unit steps on 64x64.
3. **Shipped re-derives M-B.** For every act, the `shipped` candidate's pages, pool, pinned set, and per-class
   positions/max/p50/p99/over-12/over-10 were compared with the values M-B committed.
   - S2: 157 acts, 2,877 values, 0 mismatches. S3K: 247 acts, 4,281 values, 0 mismatches.
   - **Poison:** feeding `refined_zonesplit`'s numbers into the shipped slot gives 1,134 of 2,877 (S2) and 2,164 of
     4,281 (S3K) mismatches.
4. **OJZ page payloads.** The `shipped` order's page payloads equal the committed `act_pool_page0..9.bin` byte for
   byte, and its ZX0/raw election reproduces the committed `.zx0` sizes (salvador,
   `tools/regenerate-level.sh`'s rule).
5. **Populations complete.** S2: 8 singles, 56 pairs, 44 offsets, 48 junction acts, 1 row. S3K: 10, 90, 82, 64, 1.
   Both match M-B's JSON.
6. **The CLI refuses unknown modes.** `megaact_page_order` is in `test_cli_dispatch_refuses.py` `_FIXED`
   (tripwires on `build_report`, `control_presence`) and `_ROSTER` (census 14 -> 15).
   - The census row was red before registration.
   - With a fall-through mutation on disk (unknown mode calling `build_report`), the two tripwire rows went red
     (2 failed, 1 passed).
   - The file was then restored from the committed baseline, and all 26 rows pass.

## Results: Sonic 3 & Knuckles (MEASURED)

Column meanings:

- **Windows.** Every distinct window in the class, summed over the acts.
- **p50 / p99.** Pooled over those windows.
- **Acts.** Acts having at least one such window.
- **Page-0-only pin.** The same count with only page 0 pinned.
- **Extra pool tiles.** The largest pool growth over `shipped` in any act of the group.

**Pairs, seam windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 90 | 1,086,092 | 15 | 5 / 13 | 11,208 (11) | 29,450 (22) | 10,735 / 27,994 | 6 / 12 | 0 |
| hilbert_first | 90 | 1,086,092 | 17 | 5 / 12 | 8,210 (8) | 39,815 (30) | 4,181 / 33,474 | 6 / 15 | 0 |
| hilbert_centroid | 90 | 1,086,092 | 20 | 8 / 17 | 132,945 (58) | 293,182 (79) | 125,195 / 271,585 | 6 / 17 | 0 |
| footprint_pack | 90 | 1,086,092 | 22 | 7 / 16 | 79,802 (47) | 193,627 (68) | 56,545 / 137,781 | 6 / 19 | 0 |
| refined | 90 | 1,086,092 | 12 | 5 / 11 | 0 (0) | 25,844 (29) | 0 / 24,952 | 6 / 10 | 0 |
| hilbert_first_zonesplit | 90 | 1,086,092 | 14 | 5 / 12 | 3,424 (7) | 27,485 (27) | 3,424 / 27,485 | 6 / 12 | 7 |
| footprint_pack_zonesplit | 90 | 1,086,092 | 22 | 7 / 16 | 73,985 (45) | 181,625 (69) | 55,870 / 141,216 | 6 / 19 | 7 |
| **refined_zonesplit** | 90 | 1,086,092 | **12** | 5 / 11 | **0 (0)** | 21,763 (27) | 0 / 21,682 | 6 / 10 | 7 |

**Pairs, one-zone windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 90 | 65,185,448 | 16 | 6 / 12 | 513,992 (26) | 3,364,263 (70) | 336,847 / 2,729,426 | 8 / 13 | 0 |
| hilbert_first | 90 | 65,185,448 | 17 | 6 / 13 | 782,668 (27) | 3,244,483 (72) | 542,951 / 2,648,640 | 8 / 15 | 0 |
| hilbert_centroid | 90 | 65,185,448 | 15 | 8 / 13 | 1,099,215 (21) | 8,618,420 (74) | 637,947 / 7,081,221 | 8 / 13 | 0 |
| footprint_pack | 90 | 65,185,448 | 18 | 7 / 16 | 4,865,736 (49) | 11,949,974 (86) | 3,777,769 / 9,377,919 | 8 / 15 | 0 |
| refined | 90 | 65,185,448 | 12 | 6 / 11 | 0 (0) | 1,799,664 (72) | 0 / 1,497,496 | 8 / 11 | 0 |
| hilbert_first_zonesplit | 90 | 65,185,448 | 14 | 6 / 11 | 148,789 (12) | 1,791,065 (64) | 148,776 / 1,712,851 | 8 / 11 | 7 |
| footprint_pack_zonesplit | 90 | 65,185,448 | 18 | 7 / 15 | 3,953,029 (46) | 11,086,715 (82) | 3,345,735 / 9,278,021 | 8 / 15 | 7 |
| **refined_zonesplit** | 90 | 65,185,448 | **12** | 6 / 11 | **0 (0)** | 1,158,124 (64) | 0 / 1,083,884 | 8 / 11 | 7 |

**Offset sweep (LRZ1|CNZ1 and SOZ1|ICZ1, B shifted in 16-tile steps), seam windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 82 | 766,300 | 18 | 4 / 16 | 43,059 (32) | 87,369 (36) | 43,059 / 87,363 | 6 / 15 | 0 |
| hilbert_first | 82 | 766,300 | 12 | 4 / 10 | 0 (0) | 2,735 (13) | 0 / 2,735 | 6 / 9 | 0 |
| hilbert_centroid | 82 | 766,300 | 21 | 7 / 18 | 85,254 (40) | 197,679 (52) | 85,251 / 197,660 | 6 / 17 | 0 |
| footprint_pack | 82 | 766,300 | 20 | 5 / 17 | 62,778 (33) | 109,429 (42) | 61,707 / 107,982 | 6 / 17 | 0 |
| refined | 82 | 766,300 | 12 | 4 / 10 | 0 (0) | 4,473 (14) | 0 / 4,473 | 6 / 9 | 0 |
| hilbert_first_zonesplit | 82 | 766,300 | 12 | 4 / 10 | 0 (0) | 2,753 (13) | 0 / 2,753 | 6 / 9 | 2 |
| footprint_pack_zonesplit | 82 | 766,300 | 20 | 4 / 17 | 59,188 (33) | 116,359 (42) | 57,861 / 115,428 | 6 / 17 | 2 |
| **refined_zonesplit** | 82 | 766,300 | **12** | 4 / 10 | **0 (0)** | 3,803 (13) | 0 / 3,803 | 6 / 10 | 2 |

**Junctions (32 placements x 2 alignments), junction windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 64 | 146,624 | 21 | 12 / 18 | 68,957 (45) | 93,827 (56) | 68,951 / 92,803 | 6 / 17 | 0 |
| hilbert_first | 64 | 146,624 | 23 | 10 / 18 | 42,780 (40) | 66,147 (51) | 40,575 / 65,209 | 6 / 20 | 0 |
| hilbert_centroid | 64 | 146,624 | 24 | 13 / 22 | 78,507 (56) | 105,427 (60) | 76,124 / 104,524 | 6 / 21 | 0 |
| footprint_pack | 64 | 146,624 | 25 | 13 / 21 | 73,951 (52) | 101,214 (58) | 73,707 / 101,202 | 6 / 21 | 0 |
| refined | 64 | 146,624 | 12 | 9 / 12 | 0 (0) | 20,524 (41) | 0 / 20,524 | 6 / 10 | 0 |
| hilbert_first_zonesplit | 64 | 146,624 | 20 | 10 / 18 | 37,582 (34) | 60,951 (50) | 36,467 / 59,184 | 6 / 16 | 10 |
| footprint_pack_zonesplit | 64 | 146,624 | 25 | 13 / 21 | 80,533 (57) | 106,044 (60) | 80,533 / 106,044 | 6 / 21 | 10 |
| **refined_zonesplit** | 64 | 146,624 | **12** | 9 / 12 | **0 (0)** | 21,625 (42) | 0 / 21,625 | 6 / 10 | 10 |

**10-zone row AIZ2 … LRZ1 (164 sections), all windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 1 | 4,868,730 | 18 | 6 / 14 | 227,206 (1) | 785,573 (1) | 227,206 / 785,573 | 8 / 14 | 0 |
| hilbert_first | 1 | 4,868,730 | 18 | 6 / 15 | 335,663 (1) | 905,802 (1) | 335,663 / 905,802 | 8 / 14 | 0 |
| hilbert_centroid | 1 | 4,868,730 | 20 | 7 / 16 | 580,216 (1) | 1,308,455 (1) | 580,216 / 1,308,455 | 8 / 16 | 0 |
| footprint_pack | 1 | 4,868,730 | 21 | 6 / 17 | 449,503 (1) | 758,895 (1) | 449,503 / 758,895 | 8 / 16 | 0 |
| refined | 1 | 4,868,730 | 13 | 6 / 12 | 2,559 (1) | 303,840 (1) | 2,559 / 303,840 | 8 / 11 | 0 |
| hilbert_first_zonesplit | 1 | 4,868,730 | 14 | 5 / 13 | 75,063 (1) | 318,075 (1) | 75,063 / 318,075 | 8 / 12 | 41 |
| footprint_pack_zonesplit | 1 | 4,868,730 | 18 | 6 / 14 | 187,171 (1) | 522,998 (1) | 187,171 / 522,998 | 8 / 15 | 41 |
| **refined_zonesplit** | 1 | 4,868,730 | **12** | 5 / 12 | **0 (0)** | 183,187 (1) | 0 / 183,187 | 8 / 10 | 41 |

**Single zones, all windows**

Every candidate is at worst 12 with 0 windows over 12 (every S3K zone alone fits its 12 frames). Over 10, as
windows (acts):

| Candidate | Over 10 | With page-0-only pin |
|---|---|---|
| shipped | 128,346 (2) | 28,238 |
| hilbert_first, refined, hilbert_first_zonesplit, refined_zonesplit | 98,026 (2) | 45,939 |
| hilbert_centroid | 406,104 (3) | 153,167 |
| footprint_pack, footprint_pack_zonesplit | 660,060 (2) | 405,061 |

For `shipped`, the two acts are CNZ1 and SOZ1, matching M-B (125,111 + 3,235 = 128,346). The other candidates'
acts were not broken out here; the JSON has them per act.

## Results: Sonic 2 (MEASURED)

**Junctions (24 placements x 2 alignments), junction windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 48 | 109,968 | 17 | 8 / 16 | 10,296 (12) | 18,654 (24) | 10,296 / 18,654 | 6 / 15 | 0 |
| hilbert_first | 48 | 109,968 | 15 | 8 / 14 | 7,688 (14) | 21,762 (32) | 7,308 / 20,434 | 6 / 13 | 0 |
| hilbert_centroid | 48 | 109,968 | 19 | 10 / 17 | 24,968 (28) | 49,036 (40) | 24,160 / 46,760 | 6 / 16 | 0 |
| footprint_pack | 48 | 109,968 | 17 | 9 / 16 | 12,246 (30) | 34,404 (40) | 12,186 / 34,288 | 6 / 14 | 0 |
| refined | 48 | 109,968 | 12 | 8 / 12 | 0 (0) | 10,738 (28) | 0 / 9,998 | 6 / 10 | 0 |
| hilbert_first_zonesplit | 48 | 109,968 | 15 | 8 / 14 | 7,286 (12) | 20,766 (30) | 7,286 / 20,766 | 6 / 13 | 229 |
| footprint_pack_zonesplit | 48 | 109,968 | 17 | 9 / 15 | 10,328 (26) | 32,544 (38) | 10,328 / 32,544 | 6 / 14 | 229 |
| **refined_zonesplit** | 48 | 109,968 | **12** | 8 / 12 | **0 (0)** | 7,894 (26) | 0 / 7,894 | 6 / 10 | 229 |

**8-zone row EHZ … MTZ (42 sections), all windows**

| Candidate | Acts | Windows | Worst | p50 / p99 | Over 12: windows (acts) | Over 10: windows (acts) | Over 12 / over 10, page-0-only pin | Worst floor / worst gap | Extra pool tiles |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 1 | 1,120,183 | 13 | 7 / 13 | 11,575 (1) | 120,238 (1) | 11,575 / 120,238 | 7 / 11 | 0 |
| hilbert_first | 1 | 1,120,183 | 13 | 7 / 12 | 8,680 (1) | 132,737 (1) | 8,680 / 132,737 | 7 / 11 | 0 |
| hilbert_centroid | 1 | 1,120,183 | 24 | 9 / 23 | 160,101 (1) | 338,773 (1) | 160,101 / 338,773 | 7 / 22 | 0 |
| footprint_pack | 1 | 1,120,183 | 21 | 7 / 14 | 68,763 (1) | 201,193 (1) | 68,763 / 201,193 | 7 / 18 | 0 |
| refined | 1 | 1,120,183 | 13 | 7 / 12 | 27 (1) | 96,040 (1) | 27 / 96,040 | 7 / 10 | 0 |
| hilbert_first_zonesplit | 1 | 1,120,183 | 12 | 6 / 11 | 0 (0) | 30,757 (1) | 0 / 30,757 | 7 / 10 | 245 |
| footprint_pack_zonesplit | 1 | 1,120,183 | 20 | 7 / 15 | 72,211 (1) | 147,042 (1) | 72,211 / 147,042 | 7 / 17 | 245 |
| **refined_zonesplit** | 1 | 1,120,183 | **12** | 6 / 11 | **0 (0)** | 30,757 (1) | 0 / 30,757 | 7 / 10 | 245 |

**Pairs, offsets and singles, S2**

Worst window and windows over 12 / over 10, with window counts as in M-B. Full per-candidate rows are in
`09-page-order-results-s2.json` `summary`.

| Population | shipped | refined | refined_zonesplit |
|---|---|---|---|
| Pairs, seam (360,398) | 9; 0 / 0 | 12; 0 / 2,223 | **10; 0 / 0** |
| Pairs, one-zone (14,078,638) | 14; 52,723 / 598,514 | 12; 0 / 540,396 | **12; 0 / 210,433** |
| Offsets, seam (256,829) | 10; 0 / 0 | 12; 0 / 1,838 | **8; 0 / 0** |
| Singles (845,680) | 10; 0 / 0 | 10; 0 / 0 | 10; 0 / 0 |

**S2 seams got slightly worse:** the pair seam worst went from 9 to 10 under `refined_zonesplit` (and to 12 under
`refined`). Still 0 over 10.

## OJZ act 1, the act that ships today (MEASURED)

257,367 windows. No candidate goes over 12 or over 10.

| Candidate | Worst | p50 / p90 / p99 | Windows needing 6+ | Windows needing 8+ | Pinned | Page ROM (ZX0/raw elected) |
|---|---|---|---|---|---|---|
| shipped | 10 | 5 / 5 / 10 | 25,231 | 17,625 | [0,1,7,8,9] | 11,964 B |
| hilbert_first = refined = both zonesplits | 10 | 5 / 6 / 10 | **40,092** | 17,385 | [0,2,7,8,9] | 11,870 B (-94) |
| hilbert_centroid | 9 | 5 / 6 / 9 | 33,518 | 7,394 | [0,1,5,6,7] | 12,000 B (+36) |
| footprint_pack (both) | 10 | 2 / 5 / 10 | 16,139 | 9,975 | [0,9] | 11,888 B (-76) |

**The recommended order makes OJZ slightly worse in the middle of the distribution.** Worst stays 10, and windows
at 8+ are about equal, but windows needing 6 or more pages rise from 25,231 to 40,092 (p90 5 -> 6). OJZ is a
single zone whose 10 pages fit the 12 frames, so none of this is over budget. The refinement made 0 moves on OJZ
(no sample over 12), so the change is `hilbert_first` versus the shipped walk. Page ROM is MEASURED for the art
pool pages only; the section block streams also change and were not measured.

## Build-time cost (MEASURED)

Measured on the whole S3K row: 164 sections, about 5,900 pool tiles, 4,868,730 windows. Single process on the
16-core dev box, load average 7.9 at start and 6.7 at end (other work was running). File:
`09-page-order-timing-s3k-chain.json`.

| Candidate | Order computation | Of which refinement |
|---|---|---|
| shipped | 0.001 s | |
| hilbert_first | 1.54 s | |
| hilbert_centroid | 0.05 s | |
| footprint_pack | 3.20 s | |
| refined | 33.7 s | 32.2 s (6,026 tries, try cap hit) |
| hilbert_first_zonesplit | 1.28 s | |
| footprint_pack_zonesplit | 3.19 s | |
| **refined_zonesplit** | **3.49 s** | 2.03 s (78 tries, 26 kept) |

**OJZ act 1** (the shipped loop), from `09-page-order-results-ojz.json`, load average about 8: shipped 0.000 s,
`hilbert_first` 0.004 s, `refined_zonesplit` 0.111 s. These times cover the order function only, in the replay.
The re-bake's other passes are not included.

**The expensive acts are junctions, not the row.** In the parallel population runs (8 workers, so contended), the
slowest `refined_zonesplit` order took 48.3 s (LRZ1|CNZ1 over MGZ1, section-aligned). Four of the 404 acts' rounds
hit the 6,000-try cap (all S3K junctions with CNZ1), and those acts still measured at or under 12.

## What adopting `refined_zonesplit` would change

**Pipeline.** DERIVED from source unless marked.

1. **Pass 4 of `ojz_strip_gen.generate()`.** Replace `order_pool_spatially` with `hilbert_first` +
   `refine_order`, which needs each tile's cell positions, not just per-section lists. The refinement also calls
   the pin rule, so Pass 7's inputs are needed earlier.
2. **Dedupe keyed by region.** Only for acts with more than one region. The act model has regions
   (`games/sonic4/data/generated/ojz/act1/regions.emp`), but whether a region is the right key for a donor zone
   is INFERRED. For OJZ (one zone) the key changes nothing: every OJZ row above is identical with and without the
   split (MEASURED).
3. **A build-time check.** `megaact_window_pageset`'s count of the placed act, refusing any window over the
   evictable budget. Without it, the order's result is a search outcome with no guarantee (see Verdict item 3).

**OJZ act 1's generated files that move** (`games/sonic4/data/generated/ojz/act1/`):

- `act_pool_page0..9.bin` and their `.zx0`: 10 of 10 page payloads differ (MEASURED in replay).
- `ojz_act_pool_manifest.emp` / `.json`: pinned flags `[0,1,7,8,9]` -> `[0,2,7,8,9]`; the pool stays 612 tiles in 10
  pages (MEASURED).
- `sec0..8_local_map.bin`: 8 of 9 differ (MEASURED).
- `sec*_strips_a.bin`, `sec*_strips_source.bin`: 44,223 of 589,824 cells change local index (MEASURED in replay).
- `sec*_blocks.bin`, `sec_block_blobs.emp`, `sec_block_dicts.emp`, `ojz_act_pool.emp`: built from the above, so
  INFERRED to move.
- ROM bytes: page blobs -94 B (MEASURED); block streams not measured.

**Tools and prose that pin today's order:**

- `megaact_window_pageset.py control` replays the shipped order against the bake, so it must replay the new one.
- `fg_working_set.py` numbers.
- `engine/system/constants.emp:470` and `docs/ENGINE_ARCHITECTURE.md:5488` pinned-page prose (already stale per
  M-B).
- The `tools/.cache/` re-bake cache. Whether it keys on the order code is INFERRED, not checked.

**Engine.** No `.emp` change is implied. Prefetch reads the ahead strip's cell pages, not neighbouring page ids
(`engine/level/page_in.emp:156-159`), so nothing at runtime assumes that adjacent page numbers are spatially near.
That is INFERRED from that call site only; eviction was not read.

**ROM for the zone split, stitched acts only.** Extra pool tiles, MEASURED: +245 in the S2 row (EHZ and HTZ load
the same art file, so they share many tiles), +229 in S2 junctions, +41 in the S3K row. Their bytes were not
measured. At OJZ's measured 11,870 B / 612 tiles = 19.4 B per tile, +245 tiles would be about 4.8 KB (DERIVED
estimate; donor tiles compressing like OJZ's is INFERRED).

**`MAX_ACT_SECTIONS`.** No interaction. An order changes neither the section count (S3K row still 164 against 48)
nor the local palette sizes: max 1,032 entries, 1,033 with the split, 0 refusals in every candidate (MEASURED).
Pages stay far below `PAGE_TABLE_MAX` 256 (93 pages in the S3K row).

## Pinning's interaction (MEASURED)

- **The shipped pin rule adds real overflow under the shipped order.** S3K pair one-zone windows: 513,992 over 12,
  but 336,847 with only page 0 pinned. Single S3K zones over 10: 128,346 as shipped, 28,238 with only page 0.
- **A refinement that ignores the pin rule is caught by it.** With the broader moves but only page 0 counted,
  MHZ1|CNZ1 still measured 13 while no sample was over 12. The samples upper-bound the page-0-only count, and the
  rule had pinned pages [0,14], so the 13 is the rule's page (MEASURED counts, DERIVED attribution). Once the
  search counts the rule's pages, it measures 12 (pinned [0,13,14]). In the committed runs, both columns show 0
  windows over 12 in every multi-zone population above; they still differ slightly over 10 (for example S3K pair
  seams, 21,763 vs 21,682).
- **At 10 frames the rule still dominates single zones.** Under `refined_zonesplit`, CNZ1 pins 9 of 12 pages
  (`pinned [0..8]`, MEASURED in a spot run), leaving 1 evictable frame at 10. The pin rule does not know the frame
  count (M-B), and no order fixes that.

## Screened out (MEASURED unless marked)

- **`hilbert_centroid` and `footprint_pack` are worse than shipped** on most multi-zone populations (tables above).
  - A widest-tile-first footprint greedy and a Hilbert key on each tile's most-used block (`hilbert_mode`) were
    also worse on 4 prototype acts. For example, `hilbert_mode` on LRZ1|CNZ1 had seam worst 19 against shipped 15.
    These prototypes are not in the tool.
  - Cause, MEASURED at LRZ1|CNZ1: the greedy's summed page footprints were 37,385 sample bits against
    `hilbert_first`'s 27,382. INFERRED: the last pages fill with leftover tiles scattered across the act, and those
    pages are referenced everywhere.
- **A tile's centroid is a bad key** (INFERRED): a zone-wide tile's mean position is the zone centre, so wide tiles
  land in the centre's local pages.
- **`hilbert_first` alone is not enough.** It fixes S3K offsets but makes the S3K row worse than shipped (335,663
  vs 227,206 windows over 12). The zone split and the refinement are both needed:
  - `refined` without the split leaves 2,559 over 12 in the S3K row;
  - the split without refinement leaves 75,063.
- **Refining toward 10 did not work.** A second stage aimed at 10 frames was prototyped with denser 4x2 samples on
  2 acts. LRZ1|CNZ1 over-10 windows went 587 -> 663, and SOZ1|CNZ1 over FBZ1 went 1,369 -> 1,202, at 53-80 s per
  act. Not kept.
- **Earlier refinement settings** (stuck samples reset on every kept move, no split moves, 3 light x 4 heavy
  pages, groups of 16, 4,000 tries, pin rule ignored) left S3K junctions at 2,844 windows over 12 in 13 acts (worst 15). That run's JSON was superseded,
  not committed; the numbers are from its log and summary.

## Unsolved, and fallback levers (named, not built)

- **10 frames.** No order gets there (above). The levers left, all INFERRED to help and unmeasured:
  - a frame-aware pin rule, or no pins beyond page 0 in multi-region acts;
  - smaller window margins (`TILE_CACHE_MARGIN_H/V`), trading prefetch reach for fewer referenced pages;
  - 32-tile pages, which double the page count but halve the cost of a page drawn in for a few cells;
  - per-region pools with a region-crossing handover, the full version of what the zone split approximates.
- **Margin at 12.** Windows sit exactly at 12 in every stress population. M-E (the runtime soft-lock confirmation)
  and the transient-demand items in M-B's "does not cover" are still owed before 12 is known to be enough.
- **Guarantee.** A build-time refusal on the placed act (above) is the only thing that turns this search into a
  bound.
- **Not covered, as M-B.** Object and sprite art, the BG plane, animated tiles, eviction order in motion, real
  authored placements, and the 164-vs-48 section cap.

## Reproduce

```bash
python3 tools/megaact_page_order.py control
AEON_SALVADOR=<path to salvador> python3 tools/megaact_page_order.py report --game ojz --json docs/research/megaact-bg-streaming/09-page-order-results-ojz.json
python3 tools/megaact_page_order.py report --game s2  --jobs 6 --json docs/research/megaact-bg-streaming/09-page-order-results-s2.json
python3 tools/megaact_page_order.py report --game s3k --jobs 8 --json docs/research/megaact-bg-streaming/09-page-order-results-s3k.json
python3 tools/megaact_page_order.py report --game s3k --only chain --json docs/research/megaact-bg-streaming/09-page-order-timing-s3k-chain.json
```

Measured wall times on the dev box, contended: S2 124 s, S3K 583 s (8 workers), S3K chain alone 76 s. Each run
prints `finished=ok`. `report` refuses if any control fails. Salvador defaults to `tools/bin/salvador`; without it,
`ojz_rom` records that it did not run.
