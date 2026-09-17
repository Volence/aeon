# 11: runtime camera holds for the smaller tile-cache window, and 32-tile page decode time

> **Research parcel CACHE-WINDOW-HOLD-MEASURE (2026-09-17), branch `research/cache-window-hold`, base aeon
> `86ca33f9`.** This is the in-game test that decision card FG-CACHE-10-HOW (option `half-pages-smaller-window`)
> asks for before any engine change. No engine constant, generated file or shipped ROM byte changes here. Every
> variant ROM was built in the worktree and thrown away, and the tree was restored from HEAD before landing.
>
> Tool: `tools/cache_hold_probe.py` (new, `run` / `analyze`). Evidence: `11-cache-window-runtime-holds.json` in this
> directory: variant list with CRCs and pins, every run's summary, per-variant totals, pooled decode timings, hold
> locations, the static window analysis, and the failed attempts.
>
> Labels as reports 08-10. **MEASURED** means a running ROM produced the number. **DERIVED** means it was computed
> from measured numbers or read from source at this revision. **INFERRED** means it is a reading or a cause that
> nothing here ran.

---

## Verdict

**On the only subject that can be run today, the smaller windows hold the camera and 80x60 does not.** The subject is
OJZ act 1, squeezed until its worst camera window exactly fills the cache. That is the zero-margin condition report
10 found on 100,822 S3K windows. On that subject, at cap speed:

- **56x48 is the worst window in every configuration measured.** It holds at 64-tile and 32-tile pages, in the
  DEBUG and release shapes, and it is the only window that still holds with 2 frames of margin (MEASURED).
- **64x48 holds at zero margin with 32-tile pages** (1 hold tick per full-act run, 7-8 per hot-spot run). It is clean
  with 2 frames of margin and clean at 64-tile pages (MEASURED).
- **80x60 is clean except in one case.** It never holds in release. In DEBUG it holds only with 32-tile pages at zero
  margin: 5 ticks per full-act run and 2 per hot-spot run (MEASURED).
- **The holds are short, and nothing got stuck or faulted.** Holds come in 1-5 episodes per DEBUG run (up to 8 in release and 10 demand-only), and the longest
  episode is 12 frames. No run ended with a stuck camera and no fault fired, in 130 completed runs over
  749,128 logic ticks (MEASURED).

**This weakens the card's recommended option as written (56x48). It does not rule out 64x48 with some margin.** The
card makes its engine changes conditional on the in-game check being clean. On OJZ at zero margin, neither smaller
window is clean.

What these numbers **cannot** speak for:

- **Stitched S3K acts.** No loader builds one.
- **OJZ is a light subject.** It streams 2-4 of 20 pages at a time. Report 10 measured 5-10 new 64-tile pages
  entering a window per step on the S3K row. So OJZ's hold rate is plausibly a lower bound for stitched acts
  (INFERRED, not measured).
- **The heavy synthetic subject is BLOCKED.** That subject is `STRESS_UNIQUIFY`, and it is being fixed on another
  branch.

**Decode time, MEASURED:**

| | 64-tile page | 32-tile page |
|---|---|---|
| CPU cost | ~152 K 68000 clocks | ~75 K |
| Decode start to publish, DEBUG, in motion (mode) | 2 frames | 1 frame |
| Worst tail, DEBUG | 4 frames | 4 frames |
| Worst tail, release | 8 frames | 5 frames |

The per-page CPU cost is **about 3.4 times ARCH §9.7's 45 K figure**, which report 10's timing derivation rests on.
See "Decode timing".

### The expectation in the brief, tested

"OJZ act 1 shows zero holds at all three windows because it is far under budget, so the runtime test only means
something on a squeezed subject."

- **Right about shipped OJZ, but the reason is stronger than "far under budget".** The zero is structural. OJZ's
  10-page pool fits `PAGE_FRAMES_CLAMP` (12), so `Level_LoadArt` latches `PageIn_Fully_Resident`. Nothing is ever
  demanded, so no hold can fire. MEASURED: latch = $FF, 0 demands, 0 prefetches, 0 holds in both unsqueezed builds.
- **Right that only a squeezed subject means anything.**
- **Wrong that the squeezed subject shows zero.** It holds, and the holds are ordered by window size.

A second correction: **on OJZ the smaller window does not lower the static worst count at all.** It stays 9 at 64
tiles and 16 at 32 tiles for all three geometries (MEASURED, `static_window_analysis_committed_bake`). The runtime
difference therefore comes from lead and timing, not from fit.

---

## Subject, and what it covers

**Settled first:**

1. **No stitched act exists.** No loader builds a multi-zone act into the ROM. `STITCHED-ACT-PAGE-ORDER` open item 1
   says so, and `project.json` supplies one tileset per act. The only runtime act is OJZ act 1.
2. **Shipped OJZ cannot hold.** At the shipped budget (768 tiles = 12 frames of 64 tiles, or 24 frames of 32 tiles)
   the act is fully resident. MEASURED: `p64w80base` and `p32w80base` had 0 demands, 0 prefetches and 0 holds on
   both routes.
3. **Not used: the `STRESS_UNIQUIFY` / `STRESS_ART` re-bake.** The brief forbids it (broken, fixed on
   `fix/stress-uniquify-rebake`). It is the only shipped way to get a subject whose working set is much larger than
   the cache, so **the heavy-subject measurement is BLOCKED pending that fix.** `tools/cache_hold_probe.py` needs no
   change to run on it.

**The subject used (SYNTHETIC): "OJZ at its budget edge".**

- `PAGE_FRAMES_CLAMP` is spelled as the tightest frame count F at which every camera window still fits. This is the
  `STRESS_EVICT` mechanism written as a literal: `PageCache_Init` threads only F frames.
- The pins are re-baked for that F, exactly as the generator would place them at that budget. The re-bake uses
  `regenerate-level.sh` with `POOL_TILE_CEILING = page·F`, the ceiling is then put back to 768 for the build, and
  the page order stays on the shipped rung.
- The frame-aware pin rule drops pins until the worst window equals F.

| Page size | Pool | F (zero margin) | Pins at F | Worst window at F | F+2 (2 frames of margin) |
|---|---|---|---|---|---|
| 64 tiles | 10 pages | 9 | [0,1,7,8] | 9, 0 windows over | none (F+1 = pool, fully resident) |
| 32 tiles | 20 pages | 16 | [0,1,2,15] | 16, 0 windows over | 18, pins [0,1,2,15,16,17] |

Windows at the worst count (MEASURED by the bake's own `fg_page_order check`):

| Budget | 80x60 | 64x48 | 56x48 |
|---|---|---|---|
| 64-tile, F=9 | 5,896 | 4,029 | 3,629 |
| 32-tile, F=16 | 4,486 | 2,786 | 2,442 |
| 32-tile, F=18 | 2,582 | 1,826 | 1,546 |

**Smaller windows have fewer windows at the edge and still hold more.**

**What this subject is not:**

- It has one zone and one tileset, and at most 1 (64-tile) or 4 (32-tile) pages are non-resident at a time.
- There are no per-zone short pages, so `pm_tiles` < page size never runs. That is STITCHED-ACT-PAGE-ORDER item 3,
  still untested.
- There is no searched page order.
- Its densest windows sit in one region: camera x ≈ 600-1300, y ≈ 0-500.

---

## Instrument

**Emulator.** The Rust core (`oracle-aether`) through `tools/aether_instance.AetherInstance`, the owner-ruled default.
Every spawn asserts `implementation = oracle-rs` and reads the whole cart back against the file. Every run records
its cart note, and the ROM CRCs are in the evidence. No MCP was used.

The legacy harness (`launcher.headless_emulator`) was tried first and abandoned. Two of its 8 full runs failed, one on
a cart readback mismatch that did not reproduce and one on "bus connection closed". No legacy number is used.

**Driver: free flight on DEBUG, and why.**

- At the start of each leg the camera leader's `x_pos`/`y_pos` are poked. `Camera_Update` then steps the camera at
  its own 16 px/tick cap until it arrives, and the engine's real follow path does the driving.
- Free flight is the right driver here. The hold path reads only camera position against art residency, and the
  question is the cap-speed camera in every direction. Player physics cannot hold 16 px/tick vertically or
  diagonally.
- The cost: free flight says nothing about collision range, which is the other risk of a smaller window (report 10,
  costs). Nothing here measures it.
- A release build has no free flight. After the poke the player falls or runs under physics, so the camera leaves
  the commanded route and does not stay at the cap. Release rows (`r*`) are therefore **a different drive**, reported
  separately and never pooled.

**Routes, in camera pixels.**

- `all` sweeps the whole act, both ways each: 5 rows, 4 columns and 4 diagonals, about 8,440 logic ticks.
- `hot` makes 18 crossings of the dense region (rows y=32-176, columns x=560-880, diagonals), about 2,500 ticks.
- Legs that only reposition are excluded from totals.

**Holds, counted three ways.**

1. `clamp_ticks`: the DEBUG counter `Dbg_Cam_Clamp_Frames`, incremented on every tick `Camera_Update` sees a hold
   bit.
2. `hold_writes`: a bus write watch on `Camera_Art_Hold` counting nonzero writes. The fill re-derives the byte every
   pass, and this count works on release.
3. `hold_sampled`: the byte read after every video frame. This is the weakest count.

Counts 1 and 2 agree exactly on every `all` run. On `hot` runs `hold_writes` exceeds `clamp_ticks` by 1-3 (e.g. 20
vs 17). INFERRED: a bit set and cleared inside one tick without `Camera_Update` reading it. Both are in the evidence.
The watch log is checked contiguous (seq 0..n, no gaps) on every run.

**Determinism and phase.**

- The Rust core is deterministic. Two repeated runs were identical hit for hit: 10,935 and 3,717 hits, traces
  included.
- Variation therefore comes only from the phase at which a route starts. Each main configuration ran at 5 phases
  (settle 240/243/246/249/252 frames) on both routes. Hold counts moved by at most 2 across phases.

**Builds faithful (MEASURED).**

- The 32-tile page switch is pixel-identical to the shipped build at 4 camera spots.
- The smaller-window builds are pixel-identical at 3 spots. At the 4th, the whole difference is a 4 px horizontal
  shift of a BG layer that drifts with logic ticks: 128 of 52,000 pixels remain under the best shift, and the
  shipped ROM's own BG there moves 3 px per 30 ticks.
- The DEBUG residency audit ran every 128 ticks in every DEBUG run and never fired.

---

## Control first (MEASURED)

| Build | Route | Holds (`clamp_ticks` per run) | Demands | Why it is here |
|---|---|---|---|---|
| `p64w80base` (shipped constants) | all / hot | 0 / 0 | 0 / 0 | structural zero: fully resident latch $FF |
| `p32w80base` (32-tile, 24 frames) | all / hot | 0 / 0 | 0 / 0 | same |
| `c64w80f9m60`: F=9, `CLAMP_MARGIN_TILES` 4 -> 60 | all / hot | **11 / 20** | 3 / 6 | **positive control**: any demand stall anywhere in the window must hold. The instrument sees a hold on all three counts |
| `c64w80f9pfx0`: F=9, `PAGE_PREFETCH_MAX` 0 | all / hot | 0 / 0 | 10 / 13 | demand only at the shipped window: 18 columns of lead absorb 64-tile page-ins |

The positive control proves the chain: a stall sets the bit, the camera reads it, the counter increments and the
watch sees the write. So a zero in the table below comes from an instrument that has shown a nonzero on the same
build family.

---

## Holds per window (MEASURED, DEBUG, free flight, 16 px/tick cap)

Hold ticks per run, as min-max across 5 phases, with episodes per run in brackets. Report 10's leads (right / down, in
columns / rows) are DERIVED and shown for reference: 80x60 18 / 13, 64x48 10 / 7, 56x48 6 / 7.

| Page size, budget | Route | 80x60 | 64x48 | 56x48 |
|---|---|---|---|---|
| 64-tile, F=9 (zero margin) | all (~8,445 ticks) | **0** | **0** | 2 [1] |
| | hot (~2,505 ticks) | **0** | **0** | 4-5 [2-3] |
| 32-tile, F=16 (zero margin) | all | 5 [2] | 1 [1] | 3-4 [1-2] |
| | hot | 2 [1] | 7-8 [4-5] | **17-19 [4-5]**, longest episode 12 frames |
| 32-tile, F=18 (2 frames of margin) | all | **0** | **0** | 3 [2] |
| | hot | **0** | **0** | 3-4 [2-3] |

**Sensitivity: demand only (`PAGE_PREFETCH_MAX` 0), one phase.** This isolates what the lead alone covers:

| | Route | 80x60 | 64x48 | 56x48 |
|---|---|---|---|---|
| 64-tile F=9 | all / hot | 0 / 0 | 2 / 2 | 5 / 14 |
| 32-tile F=16 | all / hot | 7 / 5 | 3 / 4 | 7 / 16 |

**Where the holds are** (camera px, 32 px cells, settle 240; full list in `hold_where_settle240`):

- **Heading right** through camera x ≈ 670-740 on the top rows (y ≈ 32-64), on the X axis. This is the region of
  the act's worst window: tile left 73-99, top 0-4. It appears in every smaller-window configuration that holds.
- **Heading left** through x ≈ 1150-1250 at y ≈ 96-128, on the X axis: 64x48 and 56x48 at F=16, 56x48 at F=18.
- **Diagonal down-left** through (1216-1312, 352-480), on both axes. It accounts for most of 56x48's 17-19 at F=16
  (13 per run).
- **80x60 at F=16** holds only heading right at x ≈ 700-740, plus a Y-axis hold on the full-act diagonal up-left at
  (608-640, 608).

**Reading (DERIVED from the table):**

1. At 64-tile pages F=9, the two larger windows are clean even demand-only at 80x60. Only 56x48 holds with prefetch
   on. This matches report 10's derived "k = 0 to the right at lead 6".
2. At 32-tile pages F=16, more pages are non-resident at once (4 of 20 instead of 1 of 10), and every window holds.
   The count rises as the window shrinks, sharply on the hot route: 2 -> 7-8 -> 17-19.
3. Two frames of margin (F=18) clear 80x60 and 64x48 completely. 56x48 keeps holding in the same place heading right.
   **For 56x48 the lead, not the budget, is binding.** Report 10 flagged exactly this ("no demand-only headroom to the
   right") as a derivation. It is now MEASURED on OJZ.
4. Prefetch helps a lot at 64x48 and 56x48 on 64-tile pages (demand-only 14 -> 4-5 on hot at 56x48). It helps
   little at 56x48 on 32-tile pages (16 -> 17-19 on hot; prefetch-on is not better). INFERRED:
   `PAGE_PREFETCH_MAX` = 2 enqueues per frame covers half the tiles at 32-tile pages (report 10 costs). Nothing here
   varied it with prefetch on.

### Release shape (MEASURED, but a different drive: player physics after the poke, 2 phases, not pooled)

Release has no DEBUG counter, so these are `hold_writes` per run, with episodes in brackets.

| Budget | Route | 80x60 | 64x48 | 56x48 |
|---|---|---|---|---|
| 64-tile F=9 | all / hot | 0 / 0 | not built | 7 [2] / 2 [1] |
| 32-tile F=16 | all / hot | 0 / 0 | 1 [3] / 14-16 [7-8] | 17 [8] / 9 [5] |

- Same ordering: 80x60 never holds, and the smaller windows do, and more often than in DEBUG.
- The trajectories differ, and the release engine lacks the DEBUG audit. INFERRED: that shifts idle time and page-in
  timing. Release decode-to-publish tails are longer (8 and 5 frames, below).
- These rows confirm the direction of the DEBUG table and say nothing about exact rates.

---

## Decode timing (MEASURED)

Method: write watches on `PageIn_InFlight`, `PageIn_Suspended`, `PageIn_Saved_PC`, `PageIn_Cur_Page` and
`Page_Table`, stamped with master-clock time.

- **CPU per page** is the sum of the spans the decoder actually ran, in master clock / 7. Each span runs from decode
  start or resume to the VBlank preempt's `Saved_PC` write, or to completion.
- There are two DERIVED per-event corrections from 68000 timing tables: 262 clocks from IRQ entry to that write, and
  170 from the `Suspended` clear to the `rte` back into ZX0R. Both are under 0.4% of a page.
- Any HBlank handler inside a span is included. The init bulk load runs with the display off and serves as the
  uncontaminated reference; it agrees with the in-motion medians to within 3%.
- **Latency** is counted in video frames from decode start to `Page_Table[page]` being written, i.e. the page
  published and usable.

| | Decodes | Clocks, min / median / max | Preempts (mode) | Start -> publish, frames (histogram) |
|---|---|---|---|---|
| 64-tile, DEBUG, init (display off) | 300 | 74,216 / **152,093** / 164,406 | 1 | 1: 60, 2: 240 |
| 64-tile, DEBUG, in motion | 405 | 74,216 / **150,964** / 160,498 | 2 | 0: 60, 1: 57, **2: 197**, 3: 84, 4: 7 |
| 32-tile, DEBUG, init | 1,240 | 9,012 / **74,757** / 80,140 | 0 | 0: 62, 1: 1,178 |
| 32-tile, DEBUG, in motion | 1,969 | 9,012 / **74,688** / 81,496 | 1 | 0: 641, **1: 900**, 2: 384, 3: 37, 4: 7 |
| 64-tile, release, in motion | 52 | 74,216 / 153,803 / 163,348 | 3 | 0-8, **3-4 most**, tail 8 |
| 32-tile, release, in motion | 608 | 9,012 / 73,164 / 81,992 | 1 | 0: 178, **1: 286**, 2: 97, 3: 24, 4: 19, 5: 4 |

Minima are the short last page (64-tile page 9 is 36 tiles; 32-tile page 19 is 4 tiles). Page payloads are all ZX0,
682-1,466 B at 64 tiles and 562-824 B at 32 (`page_payloads`).

- **A 32-tile page costs half the CPU and publishes about one frame sooner** (mode 2 -> 1 in DEBUG, 3-4 -> 1 in
  release). That supports report 10's direction: "2 frames of latency instead of 3".
- **The absolute numbers do not match what that derivation used.**
  - ARCH §9.7 says "a 2 KB page ≈ 45 K cycles vs ~42.5 K average idle". Measured is ~152 K clocks for a 2 KB page,
    about 1.2 video frames of the whole CPU (128 K clocks per frame, DERIVED from 896,081 mclk per frame / 7).
  - Consistency check (MEASURED): 270 of 300 display-off 64-tile decodes needed a VBlank preempt. A 45 K decode would
    fit inside one near-idle frame.
  - This parcel did not re-derive what the 2026-08-05 measurement counted.
- **The tails matter more than the medians.** Four-frame tails at both sizes, and 5-8 frame tails in release, sit
  alongside the 1-12 frame hold episodes above. They are one plausible cause of the holds at small leads (INFERRED:
  hold episodes were not joined to specific slow decodes).

---

## What a variant build needed (DERIVED from the builds that passed)

Every variant built green in the FAST DEBUG or release shape. The full engine diff of the 32-tile 56x48 build is
reproducible from this list. The verification lanes were skipped, and the RAM layout and pins move, so none of this is
landable as is.

- **32-tile pages:**
  - `ART_POOL_PAGE_TILES` 32, `PAGE_FRAME_TILE_SHIFT` 5, `ART_POOL_PAGE_BYTES_SHIFT` 10.
  - `PAGE_FRAMES_MAX` 24 (ceiling kept at 768).
  - `Page_Audit_Snapshot` [u8; 52] -> [u8; 68], plus its ensure in `page_cache.emp`.
  - Re-bake.
  - Nothing else: `PageIn_Process` and the patch runs followed the constants. MEASURED pixel-identical.
- **56x48 / 64x48 window:**
  - `TILE_CACHE_COLS/ROWS/MARGIN_H/MARGIN_V`.
  - The seven stride sites named in `Collision_GetType`'s ensure, with their ensures: four `mul_const #80` sites,
    two `#160` sites, and the two `((x<<2)+x)<<4` chains in `TileCache_CopyBlockColumn`, respelled `lsl #6` (64) or
    `lsl #3; sub; lsl #3` (56).
  - Nothing else refused. `CLAMP_MARGIN_TILES` and the ROWS ensure were untouched. Report 10's odd-row finding does
    not bind at 48 rows.
- **Squeeze:** `PAGE_FRAMES_CLAMP` = F as a literal. Pins come from a re-bake at `POOL_TILE_CEILING` = page·F, and
  the ceiling is then restored to 768.
- **`ACT_ART_BUDGET` stayed at 4096 B** (4 pages per frame at 32 tiles) and **`PAGE_PREFETCH_MAX` stayed at 2**. The
  32-tile rows measure the page switch "by constants only", not a retuned one.

---

## Verdict on FG-CACHE-10-HOW

| Question | Answer from this parcel |
|---|---|
| Is the in-game check "clean" for the recommended 32-tile + 56x48? | **No.** 3-4 hold ticks per full-act run and 17-19 per hot-spot run at zero margin; still 3-4 with 2 frames of margin; 17 per run in release. On OJZ, the lightest subject available. |
| For 32-tile + 64x48? | **Not at zero margin** (1 per full run, 7-8 hot; release 1 and 14-16). **Clean with 2 frames of margin** in DEBUG. |
| Does 80x60 stay clean with 32-tile pages? | Clean in release, and clean with 2 frames of margin. **5 / 2 holds in DEBUG at zero margin.** |
| Does the smaller window's lead cost what report 10 derived? | **Yes, in direction and in the 56x48-right case.** Holds scale with lead, and 56x48 is bound by lead rather than budget. |
| Can this speak for stitched S3K at 20/20? | **No.** No subject exists, and the heavy stress subject is BLOCKED. INFERRED direction: S3K windows bring several times more new pages per step, so these rates are more likely a floor than a ceiling. |
| Soft-lock or fault at the budget edge? | **None** in 130 runs (no stuck leg, no fault, no DEBUG famine raise). OJZ only. |

**Recommendation.**

1. Do not adopt 56x48 on this evidence.
2. If the 640-tile cut still goes ahead, **64x48 is the window this runtime evidence leaves open**, and only with
   frame margin or a demonstrated fix for the zero-margin holds. Candidates: a higher `PAGE_PREFETCH_MAX` at 32-tile
   pages, or a wider lead in the travel direction. Neither was measured here. Report 10 found 64x48 statically fits
   S3K only with a per-act pool policy choice and has no margin.
3. **Re-run `tools/cache_hold_probe.py` on the `STRESS_ART` shape** once `fix/stress-uniquify-rebake` lands, and on
   the first stitched act a loader can build, before any window change. It needs no modification: pass `--pages` for
   the act's pool and `--hot-x/--hot-y` for its densest window.

---

## Unsettled

1. **Heavy subject: BLOCKED** on `fix/stress-uniquify-rebake` (STRESS_ART), and on a stitched-act loader.
2. **Collision range** of the smaller window (report 10 costs) is unmeasured. Free flight cannot see it.
3. **Prefetch at 32-tile pages.** `PAGE_PREFETCH_MAX` and `ACT_ART_BUDGET` were left at their 64-tile-era values.
   Whether retuning them removes the 64x48 zero-margin holds is not measured.
4. **The ARCH §9.7 45 K figure** disagrees 3.4x with this measurement. What the original measurement counted was not
   re-derived. The ARCH text now carries a pointer to this report.
5. **Episode causes.** Holds were located but not joined to the specific page-ins or decode tails behind them.
6. **Release rates** come from a different drive (physics after the poke). A release-shape cap-speed driver does not
   exist here.

---

## Reproduce

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
# 1. build a variant in a scratch worktree (constant edits listed under "What a variant build needed";
#    re-bake with tools/regenerate-level.sh at POOL_TILE_CEILING = page*F, restore 768, set PAGE_FRAMES_CLAMP = F)
FAST=1 DEBUG=1 ./build.sh
# 2. run (Rust core, full cart readback); --pages = the act's pool page count (Page_Table watch length)
python3 tools/cache_hold_probe.py run --rom s4.debug.bin --lst s4.debug.lst --out run.json --route all --pages 20 --settle 240
python3 tools/cache_hold_probe.py run --rom s4.debug.bin --lst s4.debug.lst --out hot.json --route hot --pages 20
# 3. summarise (holds three ways, where, decode timing)
python3 tools/cache_hold_probe.py analyze run.json hot.json --out summary.json
```

- Wall time: 43-84 s per `all` run and 13-52 s per `hot` run, with 5 in parallel. The box was contended: load average
  7-46 during the matrix, recorded per run in the evidence.
- The Rust core runs unpaced, so wall time does not affect any count.
- Every run prints `finished=ok`. A run that faults, or whose watch log is not contiguous, exits 2.
