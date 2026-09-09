# The FG art pool working set — how many pages does a screen actually need?

**Date:** 2026-09-09
**Tool:** `tools/fg_working_set.py` (`report`, `--json`) — every number below is
re-derivable by running it. Do not hand-copy these figures forward; re-run.
**Tests:** `tools/test_fg_working_set.py`, run by `build.sh`'s pre-build pytest lane.
**Subject:** OJZ act 1, the only act this engine has.

---

## READ THIS BEFORE QUOTING A NUMBER

**This is a measurement over baked data. It is not an observation of the running
engine, and it cannot be.**

OJZ act 1 bakes 10 pool pages against `PAGE_FRAMES = 12`. `Level_LoadArt`
therefore bulk-loads every page at level init and latches
`PageCache_Direct_Map`, and in that regime nothing is ever evicted or paged in
at runtime — `page_cache.emp`'s own header calls the refcount invariant
"VACUOUS in that regime". **Steady-state page streaming has never run on a
shipped act.** So there is no running behaviour to record: what follows is what
a *smaller* cache *would* have to hold, computed from the same bytes the engine
reads.

Concretely, the misreading to refuse: *"the engine was measured holding 8 pages
per screen"* is false. Nothing was measured holding anything. The claim is
*"the nametable words a screen can draw reference at most 8 distinct pool
pages, so a cache of fewer than 8 frames could not have drawn that screen."*

---

## THE THREE NUMBERS

| # | quantity | value | window it is over |
|---|---|---|---|
| 1 | **Peak working set — the screen** | **8 distinct pool pages** | 41x29 tiles (320x224 px, worst sub-tile alignment) |
| 1 | Peak working set — the engine's real residency window | **9 pages** | 80x60 tiles (the tile cache) |
| 1 | Peak working set — with today's pinning policy | **10 pages (= the whole pool)** | any of the above |
| 2 | **Lookahead needed** | **none measurable on this act** — the peak is 8 flat from +0 to +64 columns (0 to 512 px) of lookahead | visible window widened in the travel direction |
| 3 | **Re-entry frequency** (worst case, 8 frames, pinning off) | **0.464 re-entries per 1000 px** vertical, 0.050 horizontal; 26% / 8% of page-ins | LRU over the tile-cache window |

And the answer they are for:

> **The smallest usable `PAGE_FRAMES` on this act is 9** (576 tiles, returning
> **192 tiles** to objects), or **8** (512 tiles, **256 tiles** returned) if the
> tile-cache margin is halved as well. **Neither is reachable while the current
> pinning policy stands**, which forces 10 (640 tiles, 128 returned).
>
> **CPU and DMA are not what stops it.** Even a 2-frame cache costs only 36% of
> idle CPU and 11% of the NTSC DMA budget. The wall is the *instantaneous peak*:
> below it there is no frame to allocate.

---

## 1. PEAK WORKING SET

### What the window is, and why there are three of them

The owner's framing was *"does our view need that many loaded at once to have
seamless gameplay"*. Three concentric windows answer three different versions
of that, and they are not interchangeable:

| window | size | derivation |
|---|---|---|
| `visible` | 41 x 29 tiles | `SCREEN_LAST_COL_MAX + 1` x `SCREEN_LAST_ROW_MAX + 1`; those are `(7 + SCREEN_WIDTH - 1) >> 3` and `(7 + SCREEN_HEIGHT - 1) >> 3` — the widest tile span a sub-tile camera offset can produce over 320x224 px |
| `plane_fill` | 42 x 30 tiles | `SECTION_H_REACH_COLS_MAX + 1` x `SECTION_V_REACH_ROWS_MAX + 1` — what `Section_UpdateColumns`/`UpdateRows` actually write into the VDP plane |
| `tile_cache` | 80 x 60 tiles | `TILE_CACHE_COLS` x `TILE_CACHE_ROWS` |

**The engine's residency requirement is the tile cache, not the screen.** From
`engine/level/page_cache.emp`'s header, verbatim:

> `pf_refcount` counts nametable words currently in the tile cache that
> reference the frame. Eviction only of refcount-0 unpinned frames => a physical
> index baked into a live cache word can never dangle.

So a page must stay resident for as long as any of the 4800 tile-cache cells
name it — 4.3x the screen's area. That is the single most consequential fact in
this measurement, and it means the screen's own working set is a *lower* bound
on what a frame count must cover, not the answer.

### Method

For every section 0..8: decode `sec{N}_blocks.bin` (the S4LZ block index +
dictionary that actually ships — `sec{N}_strips_a.bin` is an intermediate that
nothing embeds) into 256 blocks of 16x16 nametable words, and map each word the
way `page_cache.emp`'s `.sb_loop` does:

```
local  = word & NT_TILE_MASK          // 11 bits
if local == 0: no page                // blank-first invariant, map[0] == 0
global = sec{N}_local_map[local]      // u16
if global == 0: no page               // "global 0 = blank -> no page"
page   = global >> PAGE_FRAME_TILE_SHIFT
```

That gives a 768 x 768 act-wide grid of page ids (3x3 sections of
`SECTION_SIZE >> 3` = 256 tiles). Per-page integral images then answer
"which pages does this rectangle contain" in O(1), and every window placement
inside the act is enumerated. The integral answer is held to a direct scan on
400 random rectangles by `test_page_set_matches_bruteforce`.

### Results

```
window                      size   peak  +pinned   placements
visible                    41x29      8       10       538720
visible_tile_aligned       40x28      8       10       540189
plane_fill                 42x30      8       10       537253
tile_cache                 80x60      9       10       488501
```

Histogram (pages referenced -> number of camera placements):

| pages | visible | tile_cache |
|---|---|---|
| 0 | 402306 | 297849 |
| 1 | 33036 | 29628 |
| 2 | 43023 | 39871 |
| 3 | 23845 | 33139 |
| 4 | 11829 | 15153 |
| 5 | 13643 | 37860 |
| 6 | 5890 | 10544 |
| 7 | 3025 | 6923 |
| 8 | **2123** | 14574 |
| 9 | — | **2960** |

The 0-page bucket is 75% of visible placements. That is the act being 79% air
(see Limits), not a property of the engine.

### Where the peaks are — and they are two different kinds of finding

**The screen's peak of 8 is a broadly high floor, not one bad screen.** It
occurs at 2123 camera placements spanning x 904..2584, y 160..4472 — several
sections — and at two distinct page sets: `{0,1,2,3,4,5,6,7}` (section 0's
entire palette) and `{0,1,2,3,4,5,8,9}`. No art edit removes it; it is what
section 0 looks like.

**The tile cache's peak of 9 is one localised configuration.** 2960 placements
confined to x 1472..2664, y 4200..4352, all at the single page set
`{0,1,2,3,4,5,7,8,9}` — which is exactly section 6's `{0,1,7,8,9}` unioned with
section 7's `{0,1,2,3,4,5,7,8,9}`. The 9th page is bought by an 80-column
window **straddling the section 6/7 boundary**, and by nothing else.

### The tile-cache margin lever

`constants.emp` asserts `TILE_CACHE_COLS >= TILE_CACHE_MARGIN_H +
SECTION_H_REACH_COLS_MAX + 1` (and the row twin), so the smallest legal cache at
a given margin is derivable, and the margin can be priced in pages:

| margin h/v | smallest legal cache | peak |
|---|---|---|
| 0/0 | 42x30 | 8 |
| 5/4 | 47x34 | 8 |
| 10/8 | 52x38 | **8** |
| 15/12 | 57x42 | 9 |
| 20/16 | 62x46 | 9 |
| 20/16 (shipped) | 80x60 | 9 |

Halving the margin gives back exactly one frame = 64 tiles, by making the cache
too narrow to hold two sections' art at once. The cost of that margin is a
separate question (it is the streaming lead the fill relies on) and is **not**
priced here.

### Pinning is the binding constraint on this act

Five of ten pages are pinned: `[0, 1, 7, 8, 9]`.

* **Page 0's pin is structural.** `tools/ojz_strip_gen.py`'s `mark_pinned_pages`
  pins it unconditionally because global slot 0 is the blank tile every air cell
  renders, and a blank word is the literal `$0000` the VDP reads as tile 0.
* **The other four are policy** — `PIN_SECTION_FRACTION = 0.75`: a page at least
  75% of sections reference is never evicted.

Union any peak-8 screen with those five and you get all ten pages. So **under
today's pinning policy the frame requirement for this act is the whole pool,
whatever a screen needs.** That is why the tables below report both regimes.

---

## 2. LOOKAHEAD

### The derivation, with every input's source

| input | value | source |
|---|---|---|
| ZX0 decode, one 64-tile (2 KB) page | ~45,000 cycles | `docs/ENGINE_ARCHITECTURE.md` §9.7, 2026-08-05 measurement |
| average idle per frame | ~42,500 cycles | same measurement, same sentence |
| landing DMA | 1 frame | `engine/level/page_in.emp` — one `QueueDMA_Important` entry, drained next VBlank |
| camera speed cap | 16 px/frame | `CAM_MAX_X_STEP` (`engine/level/camera.emp`, file-local, "this file-pair IS the truth"), `CAM_MAX_Y_STEP` (`constants.emp`) |

`ceil(45000 / 42500) = 2` frames of idle to decode, `+1` for the landing =
**3 frames of page-in latency**. At the 16 px/frame camera cap that is **48 px =
6 tile columns of lookahead**.

Note the camera cap, not a player speed, is the right number: spindash tops out
at `SPINDASH_BASE + SPINDASH_CHARGE_MAX` = `$1000` = 16 px/frame, which is
exactly where the camera clamps, so the camera cap is the ceiling for both.

### The curve — which is the actual deliverable

| +cols | +px | frames at cap | peak |
|---|---|---|---|
| 0 | 0 | 0.0 | 8 |
| 1..4 | 8..32 | 0.5..2.0 | 8 |
| **6** | **48** | **3.0** | **8** |
| 8, 12, 16, 20, 24, 32 | 64..256 | 4..16 | 8 |
| 39, 41, 48, 64 | 312..512 | 19.5..32 | 8 |
| 96 | 768 | 48 | 10 |

**The lookahead costs nothing on this act.** The peak is flat at 8 from zero
lookahead all the way to 512 px, and only moves when the window grows to 137
columns — a full section's width, at which point it is measuring "how many pages
does a whole section span", not lookahead.

**This flat result was treated as a suspected confound, and the suspicion was
discharged by demonstration rather than by argument.** The sweep deliberately
runs past the region where it is flat: the +96 row moves to 10, so the model
*can* see a change and the plateau is a property of the data. A sweep that
stopped at +32 would have been indistinguishable from a broken measurement.

---

## 3. RE-ENTRY FREQUENCY

This prices the owner's own proposal: *"can't we just have the same amount of
pages decompressed (12?) but not have it all loaded to vram at the same time?"*
— keeping decompressed pages in work RAM so a re-entry costs a 2 KB DMA instead
of a second full ZX0 decode. **That lever only pays if re-entry is common.**

Method: LRU over the tile-cache window. Every traverse of the act on both axes
(709 horizontal rows, 689 vertical columns), stepping one tile (8 px) at a time.
A page the window references that is not resident is a page-in; a page-in whose
page was evicted earlier in the same traverse is a re-entry.

Per 1000 px of camera travel:

| frames | h, pinned as shipped | h, pinning off | v, pinning off | re-entry share (h/v, unpinned) |
|---|---|---|---|---|
| 2 | UNMEASURABLE (5 pinned > 2 frames) | 3.347 | 7.668 | 85% / 85% |
| 4 | UNMEASURABLE | 2.376 | 4.970 | 81% / 79% |
| 5 | UNMEASURABLE (every frame pinned; no eviction candidate) | 1.542 | 3.688 | 73% / 74% |
| 6 | 1.088 | 0.976 | 2.708 | 63% / 68% |
| 7 | 0.819 | 0.262 | 1.422 | 31% / 52% |
| 8 | 0.480 | 0.050 | 0.464 | 8% / 26% |
| 9 | 0.268 | 0.005 | 0.000 | 1% / 0% |
| 10-12 | 0.000 | 0.000 | 0.000 | 0% |

Readings:

* **Vertical churn is ~2.3x horizontal at every frame count.** A
  horizontal-only measurement would have understated the whole table. This is
  reported as its own row rather than folded into an average.
* **Re-entry is where the pain is, when there is pain.** Below 7 frames,
  60-85% of every page-in is a page the cache already had. A work-RAM
  decompressed-page tier would convert those from a 45 K-cycle decode into a
  2 KB DMA — i.e. it would remove roughly 80% of the streaming CPU cost at
  small frame counts.
* **Above 8 frames the lever is worthless on this act** (0.8% and 0% of
  page-ins are re-entries at 9 frames). So the proposal is real, but it is a
  lever for the *aggressive* end of the range, not for a modest 12 -> 10 trim.
* **The UNMEASURABLE rows are reported as unmeasurable, never as 0.** A
  4-frame cache with 5 pinned pages "never evicts" and would literally compute
  zero re-entries, which reads as the best possible result.

---

## 4. CANDIDATE `PAGE_FRAMES`

`pages/frame` is the **worst single traverse's** page-in rate (max over both
axes, pinning off) scaled by the 16 px/frame camera cap — not the act average,
which is diluted by 709 traverses of mostly-air rows. `%idle CPU` is against
ARCH §9.7's ~42.5 K idle cycles at ~45 K cycles per page; `%DMA` is
`ART_POOL_PAGE_BYTES` against `DMA_BUDGET_NTSC` (6144).

| frames | pool tiles | tiles to objects | fits, pinning off | fits, as pinned | pages/frame | % idle CPU | % DMA |
|---|---|---|---|---|---|---|---|
| 2 | 128 | 640 | **no** | **no** | 0.3367 | 35.7 | 11.2 |
| 3 | 192 | 576 | **no** | **no** | 0.3222 | 34.1 | 10.7 |
| 4 | 256 | 512 | **no** | **no** | 0.2787 | 29.5 | 9.3 |
| 5 | 320 | 448 | **no** | **no** | 0.2438 | 25.8 | 8.1 |
| 6 | 384 | 384 | **no** | **no** | 0.2003 | 21.2 | 6.7 |
| 7 | 448 | 320 | **no** | **no** | 0.1364 | 14.4 | 4.5 |
| 8 | 512 | 256 | **no**\* | **no** | 0.0592 | 6.3 | 2.0 |
| 9 | 576 | 192 | yes | **no** | 0.0319 | 3.4 | 1.1 |
| 10 | 640 | 128 | yes | yes | 0.0290 | 3.1 | 1.0 |
| 11 | 704 | 64 | yes | yes | 0.0290 | 3.1 | 1.0 |
| **12 (today)** | **768** | **0** | yes | yes | 0.0290 | 3.1 | 1.0 |

\* 8 frames fits the *screen's* peak but not the shipped 80-column tile cache's
peak of 9. It becomes a yes if `TILE_CACHE_MARGIN_H/V` is halved (see the margin
lever above).

### What "does not fit" means — mechanically

Not "more churn". At a frame count below the instantaneous peak,
`PageCache_AllocFrame` finds no free and no evictable frame (every resident
frame has `pf_refcount > 0` or is pinned) and falls into `.thrash`:

* **DEBUG:** `raise_error "PageCache_AllocFrame: no free/evictable frame (thrash bug)"` — the crash screen.
* **release:** returns the `PAGE_NOT_RESIDENT` sentinel; `PageIn_Process`
  (`engine/level/page_in.emp:242`) takes `.alloc_fail`, the page never lands,
  and the screen draws whatever was in that frame.

So the `fits` column is a hard floor.

### The reading

**Churn never becomes the reason to stop.** Even the 2-frame cache — an eighth
of today's pool — costs 36% of idle CPU and 11% of the DMA budget on the worst
traverse. Neither is comfortable, but neither is the wall. **The wall is the
peak**, and the three things that set it, in order of how much they cost:

1. **Pinning policy: 10 frames.** Five pinned pages, four of them by the 75%
   rule, and their union with any busy screen is the whole pool. Lifting the
   policy (keeping only page 0's structural pin) is worth 1-2 frames on this act
   and would be worth much more on an act with more distinct art.
2. **Tile-cache width: 9 -> 8 frames.** The 9th page exists only because an
   80-column cache can straddle the section 6/7 boundary. Halving the margin
   removes it, at a streaming-lead cost this measurement does not price.
3. **The screen itself: 8 frames.** A broadly high floor across section 0. This
   is the irreducible number for this act's art.

**Best case on OJZ act 1 without changing art: 8 frames = 512 tiles, returning
256 tiles (12.5% of VRAM) to objects.** For scale, `docs/generated/vram-map-sonic4.md`
today gives all shipped object and character art 142 tiles — so 256 tiles is
roughly **2.8x the entire current object budget**.

---

## WHAT I COULD NOT GROUND

1. **The ZX0 decode rate and the idle budget were cited, not re-measured.**
   45 K cycles/page and 42.5 K idle/frame both come from ARCH §9.7's 2026-08-05
   measurement. Re-measuring them needs an emulator, which this lane does not
   run. **TAGGED for a runtime check.** They enter only the lookahead
   derivation and the `% idle CPU` column; the peak and the `fits` columns —
   the load-bearing results — do not depend on them at all.
2. **Whether frame 0 must hold page 0.** A blank nametable word is literal
   `$0000` and displays VRAM tile 0, so page 0 must live in frame 0 for air to
   render as air. Nothing in `page_cache.emp` asserts that; it holds today
   because the free list starts at frame 0, `Level_LoadArt` loads pages in
   order, and page 0 is pinned so it never moves. **This is an observation, not
   a proven invariant** — if the pinning policy is lifted, page 0's pin must be
   kept for this reason and an `ensure`/assert is worth adding.
3. **The cost of shrinking `TILE_CACHE_MARGIN_H/V`.** Priced in pages here;
   not priced in streaming lead, fill stalls, or teleport behaviour. That is a
   separate measurement.
4. **Reachability.** Every window placement inside the act rectangle is
   enumerated, including camera positions a player can never reach. The peak is
   therefore an **upper bound**. (The first peak-8 placement in scan order is
   x=928, y=160 — a few hundred pixels from the spawn at
   `start_local_x/y = $100` — so this particular peak is plainly reachable.)

---

## LIMITS — what would make this unrepresentative

**This is ONE ACT, and a small, unusual one.**

* **79% air.** Per-section air-block fractions: 0.656, 0.789, 0.812, 0.797,
  0.812, 0.812, 0.793, 0.797, 0.789. A dense act — solid terrain, no sky —
  would raise every number, because the 0-page and 1-page histogram buckets
  would collapse.
* **The pool is 612 tiles in 10 pages.** An act with more distinct art has more
  pages, and the peak is bounded above only by how many pages a window can
  span. Nothing here says 8 generalises.
* **Six of nine sections were cloned from section 0** (`act_descriptor.emp`:
  "Row 1 = Sec3,Sec4,Sec5 (clone Sec0 art, distinct sky tint)"). Their page sets
  bear it out — sections 2, 4, 5, 6 all reference exactly `{0,1,7,8,9}`, the
  pinned set. Only sections 0, 1, 7, 8 carry distinct art. So the act supplies
  roughly **four** independent samples, not nine.
* **It is a 3x3 grid — wide AND tall.** The vertical churn figures are real
  measurements over that grid. But a *deliberately* vertical act (a climb, a
  shaft) would traverse section boundaries vertically far more often than this
  one does, and the tile cache's 60-row height straddles a boundary the same way
  its 80-column width does.
* **A denser act, a vertical act, or one with more distinct art per screen would
  all raise the peak.** The right response to this document is to re-run the
  tool on the second act when there is one, not to carry 8 forward.

---

## THE GATE

`tools/test_fg_working_set.py` — 17 tests, run by `build.sh`'s **pre-build
pytest lane** (`python3 -m pytest tools -m "not needs_build"`, which sweeps
`tools/test_*.py` at maxdepth 1). Nothing here reads a build artifact.

Every claim the tests make was proven RED by an applied source mutation, with
the mutated line read back off disk and `git diff --stat` shown, then restored
by `git checkout --` from a **committed** baseline. `tools/__pycache__` and
`.pytest_cache` were cleared before every run (a same-length mutation in the
same second is otherwise served from cache — this repo has four measured false
greens from exactly that).

| # | mutation applied | red result |
|---|---|---|
| 1 | `_integral`: `run += row_src[c]` -> `run += 0` | 5 failed, 12 passed — `test_page_set_matches_bruteforce` ("integral [] != scan [0,1,2,3,4,5]"), `test_page_set_covers_the_whole_grid`, and all three LRU tests |
| 2 | `Model.win_visible` -> the literal `(40, 28)` instead of the derived pair | 1 failed — `test_windows_are_derived_from_engine_constants`: `assert (40, 28) == (41, 29)` |
| 3 | `traverse_reentry`'s pinned-overflow return -> `{"page_ins": 0, "re_entries": 0, "re_entries_per_1000px": 0.0, ...}` | 1 failed — `test_unmeasurable_never_renders_as_a_number` |
| 4 | `ConstantSource.get`: `raise KeyError(...)` -> `return 0` | 1 failed — `test_missing_constant_is_loud`: "DID NOT RAISE KeyError" |

Baseline after all four restores: **17 passed**. Full pre-build lane on this
tree: **2346 passed, 2 skipped, 13 deselected**, plus 5 pre-existing errors in
`tools/test_extern_guard_reachability.py` that are unrelated to this parcel —
that lane needs artifacts an earlier `build.sh` stage generates
(`engine/debug/generated/*.bin`), which a never-built worktree does not have.

Expectations are **derived, not copied**:

* `test_windows_are_derived_from_engine_constants` re-derives each window from
  the *primitive* constants (`SCREEN_WIDTH`, `SCREEN_HEIGHT`,
  `TILE_CACHE_COLS/ROWS`), not from the same derived names the model used —
  otherwise the check and the subject would be one expression agreeing with
  itself.
* `test_vram_map_agrees_with_the_pool_ceiling` reads
  `docs/generated/vram-map-sonic4.md` and refuses to proceed if the
  `fg_art_pool` row disagrees with `POOL_TILE_CEILING`. The map was regenerated
  at the start of this work (`python3 tools/gen_vram_map.py --game sonic4 --toml
  games/sonic4/vram.toml --map-doc <tmpfile>`, then `diff`ed against the
  committed copy) and is byte-identical to it.
* `test_lru_reentry_hand_worked` fixes the simulation semantics against a
  4-cell grid whose page-in and re-entry counts are worked step by step in the
  docstring.

Unmeasurable is loud in three places: a cache too small to hold the pinned set,
a cache with no eviction candidate, and a window larger than the act all report
`unmeasurable` or raise — never 0, never green.
