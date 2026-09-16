# M-B: the tile-cache window's page set at seams and junctions between real classic zones

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** Tool-only measurement, no engine change.
> Tool: `tools/megaact_window_pageset.py`. Evidence: `08-m-b-results-s2.json`, `08-m-b-results-s3k.json`
> (both in this directory, produced by the tool at `0b4ddf1f` plus its docstring and JSON-format edits; the
> measuring code is unchanged). Donors: s2disasm `e45ebf3`, skdisasm `2fcd861`.
>
> Labels: **MEASURED** = printed by the tool from donor data run through the build pipeline.
> **DERIVED** = read or computed from engine source at this revision. **INFERRED** = a reading of code
> or a cause that nothing here ran. No label below is stronger than what backs it.

---

## Verdict

**As the pipeline ships today, the stress test cannot run across whole games.** It fails at 12 frames and fails
more often at 10. The seam is not the main problem.

1. **Sonic 2 seams fit.** Across all 56 ordered pairs of 8 zones, no seam window needs more than **9 frames**.
   None of 360,398 seam windows is over 12, and none is over 10. MEASURED.
2. **Sonic 3 & Knuckles seams do not fit everywhere.** Across 90 ordered pairs of 10 zones, the worst seam window
   needs **15 frames**. 11,208 of 1,086,092 seam windows are over 12, in 11 pairs (10 of the 11 involve CNZ1).
   29,450 are over 10, in 22 pairs. MEASURED.
3. **Three-zone junctions routinely fail.** In Sonic 2, 6 of 24 T-junctions have windows over 12 (worst 17). In
   S3K, 24 of 32 do (worst **21**), and for SOZ1|CNZ1 over FBZ1 **every one** of the 2,291 junction windows is
   over 12. MEASURED.
4. **The bigger failure is inside zones, not at seams.** Once zones share one act, windows touching only one zone
   go over budget too. In S2 pairs they reach 14 (7 of 56 pairs over 12). In S3K pairs they reach 16 (26 of 90
   pairs over 12, 70 of 90 over 10). The whole-game chains are over 12 at **1.03%** of camera windows for Sonic 2
   and **4.67%** for S3K, with 10.73% and 16.14% over 10. MEASURED.
5. **The cause is page order, not capacity.** No window in any act holds more than 452 distinct non-blank tiles.
   That is at most **8 pages** under *some* 64-tile packing. MEASURED count, DERIVED bound. So each over-budget
   window could fit on its own. The shipped first-occurrence order spreads a window's tiles over nearly every
   page of its zone, plus one page for each rare tile shared with another zone. This was MEASURED at two worst
   windows (see "Why").

Released as it is, each over-budget window is a spot where the fill cannot finish. Finding 1 of the review says
such a spot holds the release camera and never lets go. That consequence is INFERRED from code; M-E has not
confirmed it at runtime. Whether a stress test can exist is a question about the **page-ordering lever**, which
this slice did not measure (see "Open").

---

## What is counted

For every distinct window a camera can produce:

```
needed = | pinned pages  UNION  pages referenced by the non-blank nametable words in the 80x60 tile-cache window |
```

"Over budget at F" means `needed > F`. That is the same as "referenced unpinned pages > F - pinned", the number
of evictable frames. Two counts are reported alongside it:

- **referenced_only**: the same count without pinned pages.
- **any_order_page_floor**: `ceil(distinct non-blank tiles / 64)`. This is a lower bound for that one window
  under any packing into 64-tile pages. It is not a proof that one global order meets the bound for every
  window at once.

The windows are grouped by the number of zones whose cells they contain:

| Group | Definition |
|---|---|
| `interior_one_zone` | Cells from one zone only |
| `seam_two_plus_zones` | Cells from 2 or more zones |
| `junction_three_plus_zones` | Cells from 3 or more zones |

Each group also has a `reachable` subset, where some camera mapping to the window keeps its whole 40x28-tile
screen on painted zone cells. Restricting to reachable windows removes few over-budget windows, so the tables
quote the full sweep (JSON `needed_reachable` has the rest). Over-12 windows, full → reachable:

| Case | Full | Reachable |
|---|---|---|
| S2 pairs, interior | 52,723 | 51,653 |
| S3K pairs, seam | 11,208 | 10,402 |
| S3K chain | 227,206 | 223,238 |
| Junctions | identical | identical |

## Derived engine constants (DERIVED, this revision)

| Quantity | Value | Source |
|---|---|---|
| Tile-cache window | 80 cols x 60 rows | `engine/system/constants.emp:366-367` (`TILE_CACHE_COLS`, `TILE_CACHE_ROWS`) |
| Window margins | 20 cols, 16 rows | `constants.emp:888-889` |
| Far-edge reach | cam+327 px, cam+231 px | `constants.emp:927-928` (`SECTION_H/V_REACH_PX`) |
| Window position | left = max(0, floor(camX/8) - 20), top = max(0, floor(camY/8) - 16) & ~1 | `engine/level/tile_cache.emp:1194,1211` (cols), `:1294,1308` (rows); init `:750-755,788-790` |
| Page size | 64 tiles | `constants.emp:380` (`ART_POOL_PAGE_TILES`) |
| `POOL_TILE_CEILING` | 768 | `constants.emp:871` |
| `PAGE_FRAMES` | 768 / 64 = **12** | `constants.emp:405` |
| `PAGE_FRAMES_CLAMP` (shipped) | = `PAGE_FRAMES` (STRESS_EVICT = 0) | `constants.emp:506` |
| Pinned pages | page 0 always, plus any page referenced by at least 75% of the act's sections | `tools/ojz_strip_gen.py:142,826`; published pinned at `engine/level/page_cache.emp:427` |
| Blank words (global 0) take no reference | | `page_cache.emp:520,874` |
| No evictable frame, release | returns `PAGE_NOT_RESIDENT` | `page_cache.emp:331-335`; re-queued at `engine/level/page_in.emp:323-329` |
| `MAX_ACT_SECTIONS` | 48 | `constants.emp:872` |

How the window is placed (DERIVED): the fill's desired far edge is `((cam + reach) >> 3) + margin`. That is
`ct+60` or `ct+61` for columns and `rt+44` or `rt+45` for rows, and it always exceeds `left+79` / `top+59`, so
the COLS/ROWS clamp always binds. The window held is therefore exactly 80x60 from `left`/`top`, and it does not
depend on the direction of travel. The tool checks this at all 8 sub-pixel offsets on both axes, and refuses to
run if the check fails. At the zero clamp the held window is still 80x60, because `Tile_Cache_Init` commits
`Cache_Head_Col = left+79` and the far edge only moves back through the evict-at-capacity arms. The window
depends only on `floor(cam/8)`, so sweeping every whole-tile camera position is exhaustive. Rows only take even
tops.

**Evictable frames = 12 - pinned** (DERIVED). The pin rule is a fraction of sections, so it collapses as the act
grows. MEASURED pinned counts: 2 to 10 for single zones, 1 to 6 for pairs, 1 to 2 for junctions, and 1 for both
chains. Stitched acts therefore have 10 to 11 evictable frames at 12, and 8 to 9 at 10.

## Method

**Real pipeline, called unmodified:** `tile_dedupe.dedupe_tiles`, `order_pool_spatially`,
`pin_blank_tile_first` and `split_pool_into_pages`, plus `ojz_strip_gen.mark_pinned_pages`,
`build_section_local_map` and `chunk_get_tile_word`, plus the `ojz_common` Kosinski decoder and block/chunk
loaders.

**Adapter** (everything the tool changes or adds):

- **Sonic 2 donors.** Act 1 of EHZ, HTZ, CPZ, ARZ, CNZ, MCZ, OOZ and MTZ, from s2disasm. The layout is `$1000`
  bytes, with FG row r at `r*$100`. HTZ gets its supplement overlays: art at
  `ArtTile_ArtKos_NumTiles_HTZ_Main`, and blocks at the `Block_Table+$980` patch, parsed out of `s2.asm`.
  - Skipped: WFZ (a supplement over SCZ plus scripted scenes), SCZ (sky chase) and DEZ (one boss room).
- **S3K donors.** AIZ2, HCZ1, MGZ1, CNZ1, FBZ1, ICZ1, LBZ1, MHZ1, SOZ1 and LRZ1, from skdisasm
  `LevelLoadBlock` rows.
  - Art is Kosinski-moduled (KosM): the secondary set is appended at the primary's size, following
    `LoadLevelLoadBlock`. Every decoded size equals its module header.
  - Blocks and chunks are the primary and secondary Kosinski streams concatenated (`LoadLevelLoadBlock2`).
  - The FG rows come through the layout's row-pointer table.
  - AIZ1 is skipped (intro, xstart `$1308`).
- **Decode check.** ARZ, HTZ and MHZ1 were rendered and look like the real zones. Exact decoded sizes: S2 art
  sizes match `NumTiles`, the ARZ block count matches the disassembly's own `$320` comment, and KosM sizes match
  their headers. The native `kosdec` could not be used as a cross-check: it aborts on these files.
- **Crop.** Each zone is cropped to its `LevelSize` box: x from xstart to xend+320, y from max(0, ystart) to
  yend+224. Outside the box is VOID (blank).
  - Negative ystart (MTZ, MGZ1 and ICZ1 wrap vertically) is clamped to 0; the wrap is not modelled.
  - An S3K xend of `$6000`/`$7000` is a placeholder narrowed by resize events, so the layout width is used.
- **Stitching.**
  - Pairs: B abuts A's right edge, and the box tops are aligned.
  - Offset sweep: the worst and the calmest pair are re-run with B shifted vertically in 16-tile steps.
  - T-junctions: A and B sit side by side with their bottoms aligned, and C is directly below, centred on the
    A|B seam.
    - Each junction is run twice: once as placed, and once with the junction row pushed to a section boundary,
      so that C does not share section rows with A and B.
    - The triples are the three worst pairs times every other zone, plus the calmest pair times every other
      zone.
  - Chain: every zone of the game in play order, in one row.
- **Keys and glue.**
  - Source tiles are keyed by (zone, index). The 11-bit nametable field is not applied, because three dense
    zones carry more than 2048 source tiles. The engine's real 11-bit limit is the per-section local palette,
    and that one is enforced: the largest palette measured is 678 entries, with 0 refusals.
  - `generate()`'s passes 2 to 4 and 7 are replicated. Sections are 256x256 tiles in flat row-major order, and
    tiles are listed per section in column-major first-occurrence order.

**Controls (all MEASURED, and all run before any donor number is used):**

1. **Glue replay against the committed OJZ act-1 bake.** The replay reproduces:
   - pool 612 tiles, 10 pages, pinned `[0,1,7,8,9]`;
   - 9 of 9 section local maps, byte for byte;
   - the page of 589,824 of 589,824 cells, as `fg_working_set.load_page_grid` decodes them from the shipped
     block blobs.

   **Poison:** a row-major section walk turns the same control red (pinned `[0,1,4,7,8,9]`, 8 local maps
   differ, 5,736 cells differ).
2. **Window counts.** The numpy integral-image counts match a pure-Python direct scan, and the distinct-tile
   sweep matches `np.unique`. 203 windows were checked per game (200 random plus each group's peak), with 0
   mismatches. **Poison:** a window lower bound shifted by one gives 128 mismatches in 403 windows.

## Results: Sonic 2 (MEASURED)

**Single zones.** Each zone's whole pool fits in 12 frames, so the engine would keep it all resident and never
stream it.

| Zone | Pool tiles | Pages | Pinned | Worst window | Most distinct tiles in a window |
|---|---|---|---|---|---|
| EHZ | 480 | 8 | 5 | 8 | 343 |
| HTZ | 422 | 7 | 4 | 7 | 290 |
| CPZ | 619 | 10 | 7 | 10 | 408 |
| ARZ | 605 | 10 | 5 | 10 | 407 |
| CNZ | 512 | 8 | 8 | 8 | 277 |
| MCZ | 481 | 8 | 7 | 8 | 315 |
| OOZ | 483 | 8 | 6 | 8 | 332 |
| MTZ | 420 | 7 | 7 | 7 | 337 |

In **all 8** zones, some window references every page of the zone's pool, pinned pages aside (`referenced_only`
max = pages). In S3K the same is true of 7 of 10 zones.

**Ordered pairs (56).**

- 10 to 12 sections each, 11 to 20 pages, 1 to 6 pinned.
- **Seam windows:** 360,398 in total. Worst 9. Over 12: 0. Over 10: 0.
- Seam histogram (frames needed: windows): 1: 8,879; 2: 38,141; 3: 72,352; 4: 84,192; 5: 61,983; 6: 45,520;
  7: 31,654; 8: 15,215; 9: 2,462.
- Worst seams, all at 9: CNZ|MTZ, MCZ|CNZ, OOZ|EHZ, OOZ|HTZ, OOZ|MCZ, OOZ|MTZ and MTZ|CNZ. Example: MCZ|CNZ at
  camera (9488, 528) px references pages [0,1,2,3,5,7,8,9,10].
- Calmest pair: HTZ|ARZ, seam worst 4.
- **Interior windows:** worst **14**. 52,723 windows are over 12 (in 7 pairs) and 598,514 are over 10 (in 25
  pairs).

**Vertical offset sensitivity.** Seam worst: MCZ|CNZ ranges 5 to 9 over 21 offsets, and HTZ|ARZ ranges 2 to 10
over 23 offsets. No offset goes over 10.

**T-junctions (24).**

- Worst **17**. 5,148 of 54,984 junction windows are over 12 (in 6 acts), and 9,327 are over 10 (in 12 acts).
- Worst act: OOZ|MTZ over CNZ. 1,667 of its 2,291 junction windows are over 12, and 2,259 are over 10. Median
  14, worst 17, at camera (12048, 1984) px.
- The any-order floor at junction windows is at most 6.
- Section-aligned runs are identical here: every worst pair includes a zone 256 rows tall, so the junction row was
  already on a section boundary.

**Chain** EHZ|CPZ|ARZ|CNZ|HTZ|MCZ|OOZ|MTZ: 42 sections (limit 48), 59 pages, pinned [0], 1,120,183 windows.

| Group | Windows | Worst | p50 | p99 | Over 12 | Over 10 | Worst any-order floor |
|---|---|---|---|---|---|---|---|
| all | 1,120,183 | 13 | 7 | 13 | 11,575 (1.03%) | 120,238 (10.73%) | 7 |
| interior | 1,075,153 | 13 | 7 | 13 | 11,575 | 118,783 | 7 |
| seam | 45,030 | 12 | 4 | 11 | 0 | 1,455 | 5 |

Every chain window over 12 lies inside a single zone, and all of them need exactly 13. Their window lefts run from
tile 3,691 to 7,651, which is ARZ through MCZ.

## Results: Sonic 3 & Knuckles (MEASURED)

**Single zones.**

| Zone | Pool tiles | Pages | Pinned | Worst window | Over 10 | Most distinct tiles in a window |
|---|---|---|---|---|---|---|
| AIZ2 | 623 | 10 | 8 | 10 | 0 | 313 |
| HCZ1 | 651 | 11 | 5 | 10 | 0 | 301 |
| MGZ1 | 519 | 9 | 7 | 9 | 0 | 319 |
| CNZ1 | 725 | 12 | **10** | 12 | **125,111 of 296,343 (42%)** | 452 |
| FBZ1 | 511 | 8 | 8 | 8 | 0 | 280 |
| ICZ1 | 449 | 8 | 2 | 6 | 0 | 193 |
| LBZ1 | 632 | 10 | 5 | 10 | 0 | 272 |
| MHZ1 | 514 | 9 | 4 | 9 | 0 | 353 |
| SOZ1 | 691 | 11 | 8 | 11 | 3,235 | 421 |
| LRZ1 | 592 | 10 | 7 | 10 | 0 | 363 |

At 12 frames, every S3K zone on its own is fully resident. At 10 frames:

- **CNZ1 alone** has 10 pinned pages, meaning zero evictable frames. 42% of its windows need 11 or 12 frames.
  SOZ1 has 3,235 windows over 10.
- The pin rule does not know the frame count (`mark_pinned_pages`). DERIVED.

**Ordered pairs (90).**

- 23 to 48 sections each, 15 to 23 pages, 1 to 5 pinned.
- **Seam windows:** 1,086,092 in total. Worst **15**. 11,208 are over 12 (in 11 pairs) and 29,450 over 10 (in 22
  pairs).
- Seam histogram (frames needed: windows): 1: 15,354; 2: 69,614; 3: 143,319; 4: 203,441; 5: 179,095;
  6: 182,805; 7: 124,355; 8: 75,617; 9: 42,201; 10: 20,841; 11: 11,663; 12: 6,579; 13: 8,020; 14: 2,657;
  15: 531.
- **Interior windows:** worst 16. Over 12 in 26 pairs (513,992 windows); over 10 in 70 pairs.

| Pair | Seam worst | p50 / p90 / p99 | Over 12 / seam windows | Over 10 | Most tiles | Any-order floor | Worst camera (px) |
|---|---|---|---|---|---|---|---|
| LRZ1\|CNZ1 | 15 | 6 / 13 / 14 | 1,946 / 13,509 | 3,089 | 323 | 6 | (11864, 1840) |
| SOZ1\|CNZ1 | 15 | 5 / 13 / 15 | 1,460 / 13,509 | 1,998 | 225 | 4 | (17120, 2592) |
| MHZ1\|CNZ1 | 15 | 4 / 11 / 14 | 974 / 13,509 | 1,470 | 255 | 4 | (17488, 2640) |
| CNZ1\|LRZ1 | 14 | 6 / 13 / 13 | 1,483 / 13,509 | 2,433 | 307 | 5 | (14392, 976) |
| MGZ1\|CNZ1 | 14 | 4 / 12 / 14 | 1,153 / 15,168 | 2,570 | 274 | 5 | (12392, 2592) |
| LBZ1\|CNZ1 | 14 | 6 / 12 / 14 | 1,112 / 13,509 | 2,638 | 232 | 4 | (20280, 2592) |
| SOZ1\|ICZ1 (calmest) | 4 | 2 / 4 / 4 | 0 / 10,112 | 0 | n/a | n/a | n/a |

**Vertical offset sensitivity.**

- **LRZ1|CNZ1**: seam worst ranges 4 to **18** over 45 offsets. **32 of 45** offsets have windows over 12, and 36
  of 45 over 10. Top alignment (the headline number above) is not the worst case; the worst is 18, at B shifted
  up by 130 tiles.
- **SOZ1|ICZ1**: ranges 2 to 10. No offset goes over 10.

**T-junctions (32 placements × 2 alignments).**

| Alignment | Junction windows | Worst | Over 12 (acts) | Over 10 (acts) | Worst any-order floor | Acts over 48 sections |
|---|---|---|---|---|---|---|
| as placed | 73,312 | **21** | 44,475 (24) | 52,219 (29) | 6 | 11 of 32 |
| section-aligned | 73,312 | 19 | 24,482 (21) | 41,608 (27) | 6 | 26 of 32 |

Worst: SOZ1|CNZ1 over FBZ1, 48 sections. Over 12 at **2,291 of 2,291** junction windows. Median 16, worst 21, at
camera (17040, 3008) px, referencing 21 pages.

Aligning the junction to a section boundary lowers the counts but does not fix them. Some aligned acts come out
worse than unaligned ones (for example SOZ1|ICZ1 over FBZ1 goes from 0 to 646 windows over 12), because the added
blank rows shift which content shares a section.

**Chain** AIZ2 … LRZ1: 164 sections, **3.4 times `MAX_ACT_SECTIONS`**, so this act cannot be built today. 92 pages,
pinned [0], 4,868,730 windows.

| Group | Windows | Worst | p50 | p99 | Over 12 | Over 10 | Worst any-order floor |
|---|---|---|---|---|---|---|---|
| all | 4,868,730 | 18 | 6 | 14 | 227,206 (4.67%) | 785,573 (16.14%) | 8 |
| interior | 4,750,783 | 18 | 6 | 14 | 221,981 | 773,758 | 8 |
| seam | 117,947 | 17 | 7 | 15 | 5,225 (4.43%) | 11,815 | 5 |

Among reachable windows only, 6.99% are over 12 and 23.99% over 10.

## Why: the page order, measured at two worst windows (MEASURED)

**Sonic 2 chain, worst interior window** (ARZ, window left 3691, top 0), 12 referenced pages plus pinned page 0:

- **10 of the 12 are ARZ pages** (17 to 26). The window uses 1 to 59 tiles from each. Page 25 contributes a single
  cell.
- **Pages 4 and 8 are foreign.** They are brought in by 3 tiles in 7 cells that dedupe merged with tiles from EHZ,
  HTZ, CPZ, MCZ or OOZ.

**LRZ1|CNZ1, a peak seam window** (left 1463, top 214, needs 15), 15 pages including pinned page 0:

- Five pages are nearly empty: page 18 contributes 2 cells, page 13 contributes 4 cells of 1 tile, page 6
  contributes 4 cells, page 12 contributes 3 tiles, and page 17 contributes 8 tiles.
- Pages 0, 1 and 9 are shared by both zones. Page 9 alone covers 2,708 cells.

The measured shape: an 80x60 window references nearly every page of its zone. Pages it draws only a handful of
cells from, and pages dragged in by rare shared tiles, are what push it over.
The mechanism behind it is INFERRED:

- `order_pool_spatially` assigns pages by first occurrence in flat section order, walking column-major down a full
  2048 px column.
- A zone's early sections introduce most of its tileset, so a page is effectively "tiles first seen around column
  range k". The tiles one screen needs are scattered across all of those ranges.
- Dedupe across zones threads a zone's windows back to other zones' pages.
- Vertical stacking inside one section row interleaves both zones per column, which is why unaligned junctions come
  out worse.

This is the same structural observation `constants.emp:490-503` records for OJZ ("any window references ~every
page"), now measured on real multi-zone data.

The any-order floor stays at or below 8 everywhere (at or below 6 at every seam and junction window). The budget
problem is therefore the ordering, not the raw tile content of a window. MEASURED per window. The **existence** of
one global order that satisfies every window at once is not shown.

## Verdict against 12 and against 10 frames

| Case | At 12 frames (today) | At 10 frames (owner's lever) |
|---|---|---|
| S2 seams (56 pairs) | Fits: worst 9 | Fits: worst 9 |
| S2 T-junctions (24) | **Fails** in 6 (worst 17) | **Fails** in 12 |
| S2 whole-game chain | **Fails**: 1.03% of windows | **Fails**: 10.73% |
| S3K seams (90 pairs) | **Fails** in 11 (worst 15; 18 with a vertical offset) | **Fails** in 22 |
| S3K T-junctions (32) | **Fails** in 24 (worst 21) | **Fails** in 29 |
| S3K whole-game chain | **Fails** (4.67%), and over the section cap | **Fails** (16.14%) |
| Single S3K zone (CNZ1) | Fits (fully resident) | **Fails**: 42% of windows, with 10 pinned pages = 0 evictable frames |

All cells MEASURED. The "fits"/"fails" wording against runtime behaviour relies on the review's release soft-lock
reading (INFERRED; M-E). The 10-frame column assumes the lever keeps today's pin rule.

## What this does NOT cover

- **Object and sprite art, the BG plane, and animated tiles.** Animated tiles are counted as the static art in
  their slots, and dynamic art-load patterns are not modelled.
- **Transient frame demand.** A static count at or under the budget is necessary, not sufficient. Not covered:
  - a demand page that is published but not yet referenced (unflagged, so not evictable);
  - an in-flight decode holding a detached frame;
  - speculative prefetch pages.
  - **Stalled cells keep their old words and references.** `TileCache_HSlide` only moves the origin
    (`tile_cache.emp:2232-2244`), and a patch run leaves a non-resident cell untouched
    (`page_cache.emp` patch-run header). A stalled column can therefore still pin a page from the column it
    replaced. INFERRED from code; could be worse than the static count.
- **Eviction order under motion**, and whether a given over-budget window actually produces a hold.
  `art_hold_edge_check` engages only when the stalled cell is within `CLAMP_MARGIN_TILES` of the visible screen
  (`tile_cache.emp`, `constants.emp:557`), so which cell stalls first matters. Not simulated.
- **Real mega-act authoring.** The placements are mechanical. The camera boxes are the classic zones' own. No
  ring, object or collision data is involved. MTZ, MGZ1 and ICZ1 vertical wraps are clamped. Only act 1 was
  measured (act 2 for AIZ).
- **Runtime.** Nothing ran in an emulator. The soft-lock consequence is M-E's job.

## Incidental findings

- **Stale prose.**
  - `engine/system/constants.emp:470` says OJZ's pinned pages are "0/1/8/9".
  - `docs/ENGINE_ARCHITECTURE.md:5488` says "4 of the 10 pages are build-pinned".
  - The committed OJZ manifest pins **5**: `[0,1,7,8,9]`. MEASURED by the glue control. Not edited here.
- **The pin rule does not scale.**
  - At 75% of sections it pins 1 page in every multi-zone chain.
  - It pins 10 of 12 pages in CNZ1 alone, which would leave 0 evictable frames under the 10-frame lever. MEASURED
    pin counts, DERIVED consequence.
- **Whole-game acts do not fit `MAX_ACT_SECTIONS`.**
  - S3K's 10-zone chain needs 164 sections.
  - 11 of 32 S3K junction acts as placed (26 of 32 section-aligned) exceed 48.
  - The Sonic 2 chain fits at 42. MEASURED section counts against the DERIVED cap.

## Open

- **The lever this points at is page ordering,** for example ordering by window-sized spatial blocks, per-zone
  pages, or assigning cross-zone shared tiles differently. Its effect on these same windows is **not measured**.
  The tool can take an alternative order function against the same controls. That is the next measurement, if the
  owner wants the stress test.
- **M-E** (runtime release soft-lock) is still needed to turn "over budget" into observed behaviour.
- The vertical-offset result shows placement moves a pair's worst window by up to 14 frames (LRZ1|CNZ1: 4 to 18).
  Any authoring warning therefore has to run on the placed act, not on zone pairs in isolation.

## Reproduce

```bash
python3 tools/megaact_window_pageset.py control                     # glue vs the committed OJZ bake; exit 0 = ok
python3 tools/megaact_window_pageset.py report --game s2  --json docs/research/megaact-bg-streaming/08-m-b-results-s2.json
python3 tools/megaact_window_pageset.py report --game s3k --json docs/research/megaact-bg-streaming/08-m-b-results-s3k.json
```

Requires numpy and the s2disasm/skdisasm checkouts under the suite root, or `AEON_S2DISASM_DIR` /
`AEON_SKDISASM_DIR`. `report` refuses if either control fails. Each run prints `finished=ok` at the end.
Measured wall time: s2 about 1.7 min, s3k about 9.4 min.
