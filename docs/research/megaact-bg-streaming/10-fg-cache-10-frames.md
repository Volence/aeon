# FG-CACHE-10: can the stitched S2/S3K populations fit a 640-tile foreground cache?

> **Research slice for FG-CACHE-10-RESEARCH (2026-09-16/17).** Tool-only measurement. No engine file, constant,
> shipped order or ROM byte changes here. Tool: `tools/megaact_fg_cache10.py` (built on
> `tools/megaact_page_order.py` and `tools/megaact_window_pageset.py`). Donors as M-B and report 09:
> s2disasm `e45ebf3`, skdisasm `2fcd861`. Base: aeon `de9c72e7`.
>
> Evidence, all in this directory (`10-fg-cache-10-*.json`):
> `rederive-{ojz,s2,s3k}` (the control), `results-{ojz,s2,s3k}` (12 lever sets at 64/32-tile pages, every act),
> `results32a-*` and `results32b-*` (8 more 32-tile lever sets, every act), `screen1..5` and `axis` (subsets),
> `bursts-*` and `bursts32-s3k` (pages entering per window step), `rom-*` and `rom32-*` (page ROM under salvador).
>
> Labels as reports 08 and 09: **MEASURED** = printed by the tool from donor or editor data run through the
> replayed pipeline. **DERIVED** = computed from measured numbers or read from source at this revision.
> **INFERRED** = a reading of code, or a cause, that nothing here ran.

---

## Verdict

**Yes, 640 tiles can hold every window of every act, but not with 64-tile pages and not with the shipped 80x60
window.** One lever set gets there (MEASURED, every camera window of all 404 donor acts plus OJZ act 1, all window
classes):

1. the page-order search **aimed at the frame budget** instead of at 12;
2. **32-tile pages** (640 tiles = 20 frames);
3. **per-zone pages** (no page mixes two zones), with page 0 plus **frame-aware pins**;
4. a **56x48-tile cache window** (margins 8 columns / 10 rows each side, from 20 / 16).

With that one policy for every act: **0 windows over** in S3K (263,078,533 windows), S2 (57,359,163) and OJZ act 1
(263,886). A 64x48 window also reaches 0 if the build picks, per act, between per-zone pages and a shared page 0
(single policies leave 5 windows in 3 acts, and 10 in 2).

**Nothing with 64-tile pages reaches 0 on S3K.** The best is 540 windows over in 20 acts (worst 11), taking the best
of four pool policies per act at a 56x40 window. Every one of those 20 acts contains CNZ1. S2 alone does fit at
64-tile pages (64x48 or 56x40 window, shared page 0: 0 windows over).

**At the shipped 80x60 window nothing fits.** Even 32-tile pages with the per-act choice leave 428 S3K windows (8
acts) and 30 S2 windows (2 acts) over.

**OJZ act 1 does not regress** in any lever set measured (20 on every act, plus the screens): 0 windows over, and
frame-aware pins keep all 5 of its shipped pins (all 7 at 32-tile pages).

What this does **not** settle (details under "Unsettled"):

- **There is no margin.** The worst window equals the budget: 100,822 S3K windows need exactly 20 of 20 frames. M-B's
  transient demand (in-flight decode, stalled columns) lands on exactly those windows. M-E is still owed.
- **The smaller window costs streaming lead.** The fill runs 6 columns / 7 rows ahead of the plane at 56x48, against
  18 / 13 today. Whether that turns page-ins into camera holds is INFERRED below and **tagged for runtime**.
- **The search is a heuristic.** Near-identical settings move results by hundreds of windows. Only a build-time
  refusal on the placed act turns this into a guarantee.

### The owner's hypotheses, tested

| Hypothesis | Result |
|---|---|
| The window margin (lever 2) is the biggest win | **Partly wrong.** The biggest single step is aiming the search at the budget: S3K windows over 10 go 7,272,448 -> 450,502 at the shipped window. The window is the second lever, multiplicative with the first (-> 56,744 at 64x48, -> 15,634 at 56x40). Rows buy more than columns (axis probe below). |
| 32-tile pages help mainly via finer pinning | **Wrong.** Multi-zone acts pin only page 0 (at most 2 pins in any pair, junction or row). 32-tile pages help because a window's lightly used pages cost half as much each. At 56x40 they cut S3K 15,634 -> 1,361 with pinning unchanged. |

---

## Control first (MEASURED)

Before any lever number, `megaact_fg_cache10.py rederive` re-measured report 09's `shipped` and `refined_zonesplit`
candidates through **this tool's own pipeline and counting path**. It used the shipped geometry, 64-tile pages and
75% pins, and compared per-act pool size, pages, pins and needed / needed_pin0 (positions, max, p50, p99, over 12,
over 10) against 09's committed JSON:

| Game | Acts | Values | Mismatches |
|---|---|---|---|
| OJZ act 1 | 1 / 1 | 54 | 0 |
| S2 | 157 / 157 | 13,206 | 0 |
| S3K | 247 / 247 | 20,562 | 0 |

Controls inside every run (a failed one refuses the run):

1. **OJZ glue replay** against the committed bake (M-B's control): ok.
2. **Presence counting** (09's control): ok.
3. **`control_ext`, 12 comparisons.** The generalised pipeline (split policy, explicit page sizes) and refinement
   (explicit pages, same-zone moves) reproduce `megaact_window_pageset.run_pipeline` and `megaact_page_order`
   exactly: pool order, page grid, pins, local palette max. That covers LRZ1|CNZ1 and OJZ, splits none and zone,
   shipped and Hilbert orders. 09's `refined_zonesplit` is also reproduced end to end, and explicit contiguous page
   sizes give the same grid as the implicit split.
   - **Poison:** a 44x32 window that passes both engine ensures and binds, but misses the plane fill by one row at odd
     camera rows, is refused for that reason alone.
4. **Geometry check** at all 8 sub-tile offsets and both row parities, for every window tried. The held window must
   contain the plane fill's near and far edges, the far-edge clamp must bind, and the engine's own ensures must hold.
5. **Duplication fixup** (one screened lever): its incremental counts equal a from-scratch re-measure (0 windows
   differ, checked in every run that used it).
6. **Page ROM:** the `shipped` order re-derives OJZ's committed 11,964 B, and 09's order its 11,870 B.

---

## What is counted

The count is M-B's: `needed = |pinned ∪ pages referenced by the window's non-blank words|`. A window is over at
budget F when needed > F. F = 640 tiles / page size: 10 frames at 64 tiles, 20 at 32. The populations are M-B's,
read from its committed JSON: singles, pairs, offset sweeps, junctions in both alignments, and the whole-game rows.

Unlike 09's headline table, **every window class of every act** is counted. The junction acts' non-junction windows
and the offset acts' one-zone windows are where most of the residual lives.

Window geometry: `left = max(0, floor(camX/8) - MARGIN_H)`, `top = max(0, floor(camY/8) - MARGIN_V) & ~1`, held
COLSxROWS (M-B's derivation, `megaact_window_pageset.window_for_camera`, with the constants replaced). Shapes are
"screen plus margin each side" (COLS = 40 + 2·MARGIN_H, ROWS = 28 + 2·MARGIN_V) unless named otherwise. A smaller
window has slightly more distinct positions, so window totals differ between geometries.

---

## The levers, one at a time (MEASURED)

All windows of all acts, over the 640-tile budget. "Acts" = acts with at least one window over. Worst is in frames of
that page size (budget 10 or 20).

| Lever set | S3K over (acts), worst | S2 over (acts), worst | OJZ |
|---|---|---|---|
| **09's order** (`refined_zonesplit`), 80x60, 64-tile, 75% pins | 7,272,448 (218), 14 | 1,425,265 (86), 13 | 0 |
| Search aimed at 10, 4x try budget, frame-aware pins, 80x60 | 450,502 (129), 14 | 10,027 (31), 12 | 0 |
| + shared page 0, 80x60 | 69,478 (70), 13 | 1,428 (6), 12 | 0 |
| + per-zone pages instead, 80x60 | 271,075 (131), 13 | 2,851 (10), 11 | 0 |
| Aimed search, zone split, 64x48 | 56,744 (116), 13 | 2,366 (23), 12 | 0 |
| Aimed search, zone split, 56x40 | 15,634 (100), 12 | 50 (6), 11 | 0 |
| Aimed search, shared page 0, 64x48 | 9,966 (60), 12 | **0** | 0 |
| Aimed search, shared page 0, 56x40 | 3,251 (50), 12 | **0** | 0 |
| 56x40, best of 4 policies per act (64-tile) | 540 (20), 11 | **0** | 0 |
| 32-tile, zone split, 80x60 | 94,419 (123), 25 | 1,767 (9), 24 | 0 |
| 32-tile, 80x60, per-act (per-zone or shared page 0) | 428 (8), 22 | 30 (2), 21 | 0 |
| 32-tile, zone split, 56x40 | 1,361 (34), 23 | **0** | 0 |
| 32-tile, per-zone, 64x48 | 5 (3), 21 | **0** | 0 |
| 32-tile, shared page 0, 64x48 | 10 (2), 21 | **0** | 0 |
| **32-tile, 64x48, per-act choice of the two** | **0** | **0** | 0 |
| 32-tile, per-zone, 56x40 | 7 (1), 21 | **0** | 0 |
| **32-tile, 56x40, per-act choice** | **0** | **0** | 0 |
| **32-tile, per-zone, 56x48 (one policy)** | **0** | **0** | 0 |
| 32-tile, shared page 0, 56x48 | 2 (1), 21 | **0** | 0 |

Every row after the first two keeps the aimed search, 4x budget and frame-aware pins. The wider move search (`w`)
is used in every shared-page-0 row, every 32-tile per-zone or shared-page-0 row, and the 56x40 per-zone row; the
config name on each JSON entry is exact.

### Per population, 09's table format (MEASURED)

S3K, windows over the budget (acts), for 09's order at 80x60 against the recommended set (32-tile, per-zone, 56x48):

| Population (class) | 09's order, 80x60, 64-tile | 32-tile, per-zone, 56x48 |
|---|---|---|
| Singles, all | 98,026 (2) | 0 |
| Pairs, seam windows | 21,763 (27) | 0 |
| Pairs, one-zone windows | 1,158,124 (64) | 0 |
| Offset sweep, seam windows | 3,803 (13) | 0 |
| Offset acts, all windows | 2,618,950 (82) | 0 |
| Junctions, junction windows | 21,625 (42) | 0 |
| Junction acts, all windows | 3,192,398 (64) | 0 |
| 10-zone row, all windows | 183,187 (1) | 0 |

S2 under 09's order: pair one-zone 210,433 (14), offsets all 424,115 (23), junction windows 7,894 (26), junction
acts all 759,960 (48), row 30,757 (1). Under the recommended set, every S2 cell is 0.

Per-population numbers for every other lever set are in the `results*` JSONs (`acts[].configs[].needed`).

### Lever 1: pin policy

**Frame-aware pins** take the 75% rule's candidates and keep each one only if it pushes no window from at or under F
to over F. They leave the fit identical to page-0-only pins by construction, but they keep most pins, so churn does not
rise where it does not have to.

- **Multi-zone acts: no effect.** They pin page 0 only (at most 2 pins in any pair, junction or row, MEASURED).
- **Single S3K zones, where it matters:**
  - Under 09's order, CNZ1 has 96,341 windows over 10 with its 9 rule pins, and 44,364 with page 0 only.
  - With the aimed search and the 75% rule, CNZ1 has 5,862 windows over and SOZ1 9,557. With frame-aware pins both
    are 0, keeping 5 of 8 and 6 of 9 pins.
  - All other S3K and S2 singles keep every pin.
- **OJZ act 1 keeps all 5 pins** (7 at 32-tile pages).

### The aimed search (not on the owner's list; the biggest single lever)

This is 09's refinement unchanged in every respect except its target: a sample over F is attacked instead of a
sample over 12. It runs with page 0 counted as pinned, a 4x try budget (24,000), and, where marked `w`, twice the
light/heavy pages per move.

- 09 reported that "refining toward 10 made things worse". That was a second stage run from the 12-refined order with
  denser samples. The two-stage form measured worse here too: S3K row 10,978 against 2,663 aimed directly.
- Aiming from the Hilbert start works: 7,272,448 -> 450,502 S3K windows at the shipped window and pages.
- It is noisy. Wider moves, finer samples (stride 4x4) or an 8x budget moved single acts by hundreds of windows in
  both directions (`screen3`, `screen5`).
- No 32-tile run in the recommended sets hit its try cap. The largest order time was 8.0 s per act, contended.

### Lever 2: window size

- **Rows buy more than columns.** Probe on the 4 hardest S3K acts, 64-tile pages, shared page 0, aimed search
  (`axis`), windows over 10:

  | Window | S3K row | MHZ1\|CNZ1 over LBZ1 | SOZ1\|CNZ1 over LRZ1 | SOZ1\|ICZ1 over CNZ1 (aligned) |
  |---|---|---|---|---|
  | 56x60 (columns only) | 797 | 27 | 1,045 | 346 |
  | 80x40 (rows only) | 251 | 36 | 156 | 4 |
  | 56x48 | 125 | 38 | 206 | 84 |
  | 56x40 (`screen3`) | 0 | 123 | 40 | 20 |

- **With 09's order alone** (no aimed search), 64x48 cut the S3K row 183,187 -> 71,753 (`screen1`).
- **Mechanism, matching `2026-09-09-fg-working-set.md` on OJZ** (INFERRED here): a narrower window straddles fewer
  sections and zone regions, so it draws on fewer lightly used pages.

### Lever 3: 32-tile pages

Measured with the same 640 tiles (20 frames), dedupe and search, `max_move` scaled to half a page:

| Window | 64-tile, zone split | 32-tile, zone split |
|---|---|---|
| 80x60 | 450,502 | 94,419 |
| 56x40 | 15,634 | 1,361 |

32-tile pages are required for S3K to reach 0 in every set tried. The pages entering a window per one-step move rise
about 2.5-3x in count at 32 tiles (`bursts32`), which is about the same in bytes (DERIVED: 2 x 1,024 B against
2,048 B).

### Lever 4: pools

- **Per-zone pages** never mix two zones: a zone's last page is short. At 64 tiles they beat the plain zone split at
  every window (S3K: 271,075 vs 450,502 at 80x60, 49,109 vs 56,744 at 64x48, 5,753 vs 15,634 at 56x40) but lose to a
  shared page 0. At 32 tiles they are the best single policy (56x48: 0).
- **Shared page 0** keeps the blank plus the 63 (or 31) tiles with the widest act-wide window footprint deduped
  across zones in the always-pinned page 0. Everything else is zone-split. It is the best 64-tile policy (S2 reaches
  0) and a close second at 32 tiles.
- **Duplication fixup** (tiles copied into spare page slots to relieve a window, judged exactly): little gain.
  - 56x40, shared page 0: 3,251 -> 4,079 S3K windows with 2 spare slots per page (the reservation weakens the search
    more than the copies recover).
  - At most 42 tiles copied per act. 8 spare slots were worse again.
  - Not recommended.

---

## Costs

### ROM, page payloads (MEASURED, salvador + `regenerate-level.sh`'s ZX0/raw election; block streams not measured)

| Act | 09's order, 64-tile | Recommended (32-tile, per-zone) | Delta |
|---|---|---|---|
| OJZ act 1 | 11,870 B + 80 B manifest | 12,306 B + 160 B | +436 B, +80 B (+516 B against shipped 11,964 B) |
| S3K row | 85,652 B + 744 B | 88,650 B + 1,512 B | +2,998 B, +768 B |
| S2 row | 58,832 B + 504 B | 61,098 B + 1,032 B | +2,266 B, +528 B |

- Manifest bytes are 8 per page (`sizeof(PageManifest)`, `engine/level/page_cache.emp` ensure).
- Shared page 0 drops up to 29 pool tiles per act (cross-zone copies merged back into page 0).
- The zone split's pool growth over shipped dedupe is 09's (+245 tiles on the S2 row, +41 on S3K).

### Engine changes each lever needs (DERIVED from source unless marked; none made)

**Aimed search, frame-aware pins, per-zone pages, shared page 0: generator only.**

- These belong in `ojz_strip_gen` Pass 4 / Pass 7 (09's STITCHED-ACT-PAGE-ORDER wiring), with the search target read
  from `PAGE_FRAMES` and a **build-time refusal** of any window over budget. Frame-aware pins need that same window
  count at build time.
- **Per-zone short pages** need no runtime change:
  - `PageIn_Process` already reads a per-page tile count (`engine/level/page_in.emp:232`, `pm_tiles`, landing DMA =
    tiles·32).
  - The patch maps `global >> shift` to a page and `global & mask` into it (ARCH §9.7 F1). Global slot numbers
    therefore keep a gap after a short page, and the generator must number them so. (INFERRED consequence.)

**32-tile pages: constants plus RAM, not code paths.**

- `ART_POOL_PAGE_TILES` 64 -> 32 and `PAGE_FRAME_TILE_SHIFT` 6 -> 5 (`engine/system/constants.emp:380,437`, ensure-tied),
  plus `ojz_strip_gen.ART_POOL_PAGE_TILES`. `page_in.emp` already names 32-tile pages in its shift comment.
- **RAM:**
  - `PAGE_FRAMES_MAX` 15 -> at least 20 (`constants.emp:421`): +5 x 8 B `Page_Frames` (40 B) and +5 x 2 B `Page_Audit_Scratch` (DEBUG). This
    is a RAM-layout change that owes the pin/goldens ritual.
  - `Page_Audit_Snapshot[52]` (DEBUG) fails its ensure, `4 + 16 + 2·20 = 60 > 52` (`page_cache.emp:89`), and must grow.
- **Limits:** `PAGE_TABLE_MAX` 256 still holds (largest act 189 pages, MEASURED).
- **Per page (INFERRED):** decode work per page halves, and ZX0 cost scales with bytes. From ARCH §9.7's ~45 K
  cycles per 2 KB page against ~42.5 K idle cycles, that is about 22.5 K: one frame of idle plus the landing frame,
  2 frames of latency instead of 3.
- **Per frame:** `PAGE_PREFETCH_MAX` = 2 enqueues per frame covers 64 tiles instead of 128 unless raised. The
  AllocFrame stamp scan walks 20 frames instead of 12.

**Smaller window: constants, hand-spelled strides, RAM, and the lead the fill relies on.**

- **Constants:** `TILE_CACHE_COLS/ROWS/MARGIN_H/V` (`constants.emp:366-367,888-889`).
- **Strides:** the 80-column stride is hand-spelled at seven sites, each pinned by an ensure that fires loudly: the
  list in `Collision_GetType`'s ensure (`engine/level/collision_lookup.emp:28`).
- **RAM:** the tile cache shrinks from 14,400 B (9,600 nametable + 4,800 collision) to 8,064 B at 56x48 or 9,216 B
  at 64x48. This moves the RAM layout (pin/goldens ritual).
- **Collision range shrinks.** Collision outside the cache reads as air (`Collision_GetType`, `.cgt_air`).
  - At 56x48, collision stops about 64 px left, 56-64 px right, 80 px above and 64-72 px below the screen (the range
    depends on the camera's sub-tile offset and row parity). Today it stops about 160 / 152-160 / 128 / 120-128 px out
    (DERIVED from the window formula).
  - Only player code calls `Collision_GetType` today (MEASURED by grep: `games/sonic4/player/*`).
  - Entities load up to 384 px out horizontally (`ENTITY_LOAD_BUFFER`, `constants.emp:1169`), so a future badnik with
    floor sensors, or an off-screen sidekick running player code, would lose its floor sooner (INFERRED).
- **Lead** (MEASURED from the window model, worst sub-tile offset and parity): how far the held window reaches past
  the plane fill's edge.

  | Window | Right | Left | Down | Up |
  |---|---|---|---|---|
  | 80x60 (shipped) | 18 | 20 | 13 | 16 |
  | 64x48 | 10 | 12 | 7 | 10 |
  | 56x48 | 6 | 8 | 7 | 10 |
  | 56x40 | 6 | 8 | 3 | 6 |

  Also shrinking: the "structural slack" ARCH §4.7 relies on for the declared-not-filled partial (19 columns / 15 rows
  today).

**Timing, DERIVED from the cited latency, not measured. TAG: runtime.**

- A demand stall at the window's far edge holds the camera once the stalled cell is within `CLAMP_MARGIN_TILES` = 4
  of the visible edge (`constants.emp:557`).
- At the 16 px/frame cap (2 tiles/frame), that leaves (lead + 1 - 4) / 2 frames for k serial page-ins through the
  single staging slot. So k ≤ (lead - 3) / 6 at 64-tile pages (3 frames each) and k ≤ (lead - 3) / 4 at 32 tiles
  (2 frames each).
- **Today (64-tile, 80x60):** k = 2 horizontally, 1 vertically.
- **Recommended (32-tile, 56x48):** k = 0 to the right (lead 6 < 7), 1 down. The 64x48 alternative gives k = 1 on both.
- **Bursts exceed this at every geometry, including today's** (MEASURED, `bursts-s3k`): single one-step moves bring
  5-10 new 64-tile pages into the window on the S3K row. So the shipped engine already depends on block-ahead prefetch
  (up to one 16-tile block past the head, speculative, gated by the residency and lag guards) rather than on the lead
  alone.
- The smaller window removes most of the demand-only headroom. Whether prefetch covers the rest is **the runtime
  question.** It needs a hold count at maximum speed through a stitched act, which is M-E's rig.

**Build time (MEASURED, contended box, load average 13-24):** order function up to 8.0 s per act for the 32-tile
recommended sets. The 64-tile aimed search took up to ~96 s on the hardest junctions (`screen2`).

---

## Research: what was read

- **S3K** (`skdisasm/sonic3k.asm`, read this parcel):
  - `Find_Tile_FG` (≈19145) resolves collision for any world position straight from `Level_layout_header` RAM. There
    is no collision window to shrink.
  - `DrawTilesAsYouMove` (≈103169) draws strips 22 blocks wide / 16 tall, about one block past the 320x224 screen.
  - The plane needs only the screen plus a strip, but S3K's art is fully resident, so it never needs residency lead.
- **S.C.E.:** `GetFloorPosition_FG` (`Engine/Objects/Find Floor.asm:409`) reads the layout from ROM, so collision is
  again unbounded. Its art loads as whole KosPlus modules (slice 02).
- **Vectorman, Gunstar Heroes, Alien Soldier, Batman & Robin, Thunder Force IV, Ristar, sonic_hack:** not re-read.
  The committed slices 03 and 04 record that none pages a level tileset at this granularity, so none has a window
  margin or page size to copy.
- **Aeon's own OJZ margin sweep** (`docs/research/2026-09-09-fg-working-set.md`): halving the margins took OJZ's peak
  from 9 pages to 8, and the streaming-lead cost was left unpriced. This slice prices the lead (above) and extends
  the sweep to stitched acts.
- **Page size, online** (search-result level only):
  - Ausavarungnirun et al., *Techniques for Shared Resource Management in Systems with Throughput Processors*
    (https://arxiv.org/pdf/1803.06958): larger pages cut translation stalls; smaller pages cut demand-paging stalls
    "by decreasing the amount of unnecessary data transferred". That is the trade measured here: more manifest/table
    entries, less art dragged in per reference.
  - Unity's virtual texturing manual (https://docs.unity3d.com/6000.0/Documentation/Manual/svt-cache-management.html):
    tile size against pool size and thrash.

---

## Unsettled

1. **No margin at 20.**
   - 100,822 S3K windows (and 23,794 S2) need exactly 20 frames under the recommended set (MEASURED).
   - M-B's transient demand is not modelled: a stalled column keeping old references, an in-flight decode holding a
     detached frame, prefetch.
   - M-E (confirm the release soft-lock or hold at runtime) is still owed.
2. **Streaming timing of the smaller window.** Derived above, not run. TAG: runtime hold-rate measurement at 16 px/frame
   through a stitched act, 80x60 vs 56x48 vs 64x48.
3. **32-tile decode latency and prefetch coverage.** Derived from cited 45 K / 42.5 K cycle figures. TAG: runtime.
4. **Churn.** A 20-frame cache with a smaller window may evict and reload more on back-and-forth movement. The re-entry
   method in `2026-09-09-fg-working-set.md` was not re-run.
5. **Guarantee.** The search met the target on these 405 acts. An authored mega-act can still fail, so a build refusal
   is mandatory.
6. **Not covered, as M-B and 09:** object and sprite art, the BG plane, animated tiles, real authored placements, block
   stream ROM, and the 164-vs-48 section cap (unchanged: the S3K row still needs 164 sections).

---

## Recommendation

1. **Wire the aimed search, per-zone pages, frame-aware pins and the build refusal first** (STITCHED-ACT-PAGE-ORDER).
   - Generator only, no engine change.
   - It is needed at any budget. At 12 frames it only makes 09's result stronger.
   - At 64-tile pages it already fits every S2 population at 10 frames, given a 64x48 window and a shared page 0.
2. **Do not cut to 10 x 64-tile frames for stitched S3K content.** No 64-tile lever set tried fits it (best: 540
   windows, all in CNZ1 acts).
3. **If the owner wants 640 tiles for whole-game stitched acts, the measured path is 32-tile pages plus a 56x48 (or
   64x48) window.**
   - Do the 32-tile constant change as its own parcel (RAM ritual).
   - **Gate the window change on a runtime hold measurement first.** It is the lever with gameplay risk: lead, and
     collision range for future off-screen objects.
   - If the runtime says the smaller window holds the camera, 640 tiles is not available for stitched S3K acts, and the
     VRAM for objects has to come from elsewhere (REGIONS-P2-STEP8's plane cut, or objects sharing frames).
4. **OJZ act 1 is safe under every option** (0 over, pins kept). Its page ROM grows 436-516 B at 32-tile pages.

---

## Incidental findings

- **Report 09's "every window at or under 12" is scoped by window class.** Its junction acts' non-junction windows go
  over 12 under `refined_zonesplit`: S3K 3,875 windows in 23 acts (worst 14), S2 170 in 2 acts (worst 13). MEASURED
  from 09's own committed JSON. Its headline tables list only junction windows for those acts.
- **The row ensure is one row short at odd camera rows.**
  - `ensure(TILE_CACHE_ROWS >= TILE_CACHE_MARGIN_V + SECTION_V_REACH_ROWS_MAX + 1)` (`constants.emp:971`) allows a
    window whose even-rounded top leaves the held bottom one row short of the fill's far edge. That happens when
    ROWS = MARGIN_V + 30 and `(camY >> 3) - MARGIN_V` is odd.
  - DERIVED, and shown by the tool's 44x32 poison.
  - Not binding today (13 rows of lead). It would bite any window cut that sizes ROWS off the ensure.
- **One of 09's screening claims is narrower than it reads.** "Refining toward 10 did not work" holds for a second
  stage from the 12-refined order (reproduced here: worse). Aiming at 10 from the Hilbert start is the biggest lever
  measured in this slice.

---

## Reproduce

```bash
python3 tools/megaact_fg_cache10.py control
python3 tools/megaact_fg_cache10.py rederive --game s3k --jobs 8 --json <path>     # also s2, ojz
python3 tools/megaact_fg_cache10.py sweep --game s3k --jobs 12 --json <path> \
    --configs g56x48/32/perzone/rzsFt4w/frameaware,g64x48/32/perzone/rzsFt4w/frameaware,g64x48/32/page0shared/rzsFt4w/frameaware
AEON_SALVADOR=<salvador> python3 tools/megaact_fg_cache10.py rom --game s3k --only chain --configs g56x48/32/perzone/rzsFt4w/pin0
python3 tools/megaact_fg_cache10.py configs     # geometry facts + leads
```

- **Config names:** `<window>/<page tiles>/<split>/<order>/<pins>`.
  - split: `none | zone | perzone | page0shared`
  - order: `shipped | rzs12` (09's candidate), or `rzs[12]F[t<k>][s<k>][w][d<k>]`: search aimed at F, try budget
    ×k, sample stride, wider moves, k spare slots per page for the duplication fixup
  - pins: `rule75 | pin0 | frameaware`
- **Committed evidence was slimmed:** secondary histograms and percentiles dropped. `needed.all` histograms and every
  over-budget count are kept, and the analysis re-run on slimmed vs raw S3K output was byte-identical.
- **Wall times** (dev box shared with other work, load average 13-24, workers at nice 19):
  - rederive: S3K 5.4 min
  - 12 sets, every act: S2 3.6 min, S3K 86 min
  - 32-tile sets: S3K 5-9 min
- Every run prints `finished=ok`. A failed control prints `REFUSED`, and the run exits 2.
