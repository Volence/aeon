# Audit-amortise: the DEBUG residency audit without the two-frame hitch (2026-09-26)

Candidate 1 of `docs/research/2026-09-25-perf-survey.md`, picked by the owner under
`PERF-PICK` (`audit-and-copy`). Branch `parcel/audit-amortise`, base `origin/master`
`91d4119c`. DEBUG shape only: the release ROM is byte-identical (below).

## What was wrong

`PageCache_Audit` (`engine/level/page_cache.emp`) is the DEBUG machine check on the
page-cache residency invariants. The level state called it every 128 logic ticks, and each
call walked the whole 4800-word tile-cache nametable in one go: 203k to 236k cycles, about
1.6 to 1.85 frames. That was two lag frames per interval on every leg, a visible stutter
every ~2.1 s in the build the owner flies. Stubbing it out (survey) took straight flight to
zero lag.

The task: keep the audit's coverage, change only its timing.

## The design, and the ones it beat

### What the walk is for, per regime

The audit runs in one of two regimes, and the nametable walk means something different in
each:

* **Latched regimes** (`PageCache_Direct_Map != 0`: the fully resident F1 regime, and the
  bounded-direct regime of a streaming act that is still on its bulk-loaded block). Every
  shipped act is here, and the clip is here until it flies down into Chemical Plant. The
  walk's only consumer is invariant **(b)**, "no nametable word names an unassigned frame".
  That is a **per-word predicate over one instant's state**.
* **General regime** (a streaming act that has allocated). The walk recomputes every frame's
  refcount and compares it to `pf_refcount`. That is a **sum over the whole nametable at one
  instant**.

Everything else the audit checks ((a) zero refcounts, (c) identity map, the PF_EVICTABLE
flags, page/frame bijectivity, orphan frames) reads the 12 frames and the 256-entry page
table. That is cheap, and it is whole-state, so it stays whole.

### Chosen: paced slices in the idle slot (latched regimes), atomic walk (general regime)

* The nametable is cut into 120 slices of 40 words. A slice is checked by `.dangling_walk`
  against a 32-bit mask of assigned frames that is built **in the same call**, from the same
  instant as the words it reads.
* **The idle slot does the work.** `VSync_Wait` calls `PageCache_Audit(PAGE_AUDIT_IDLE)` right
  after `PageIn_Process` (DEBUG only). It audits due slices while the V counter says a slice
  still fits before VBlank (`PAGE_AUDIT_IDLE_LAST_LINE` = line 212, a hand-priced ~2,650-cycle
  slice with a 2x margin). It tests `VBlank_Flag` after reading the V counter, so it never
  starts a slice after this frame's VBlank. It spends only time the frame would otherwise
  have spun away in `.wait`.
* **Pacing.** Slice *s* may be audited from interval tick *s+1*, and must be audited by tick
  *s+1+8* (`PAGE_AUDIT_SLACK_TICKS`). The level tick's `PageCache_Audit(PAGE_AUDIT_TICK)`
  audits any slice the idle slot left overdue, and the interval tick audits whatever is left.
  `Page_Audit_Late` counts the slices the ticks had to do.
* **Interval tick** (every 128): in a latched regime, the frame-level checks run whole. In the
  general regime, the old atomic walk and refcount comparison run, unchanged.
* `Tile_Cache_Init`'s tail (level init, warp) calls `PAGE_AUDIT_FULL`, which does everything
  in one call, as before.

### Rejected

| design | why not | measured |
|---|---|---|
| **Slices in the tick slot** (one 40-word slice per level tick) | It adds ~2-3k cycles to every tick's critical path. The diagonal leg's ticks sit near the frame edge, so it tipped 8 more of them over. Unrolling the walk to ~42 cycles/word changed nothing: the diagonal stayed at 51 either way | canonical diagonal **51**/414 (v1 and unrolled v2), against 48 at base and 43 with the slice work removed (`results/legs_tickslot_v*.txt`, `legs_expA_slices_off.txt`) |
| **Idle slot, unpaced** (the idle slot sweeps as fast as it can from the interval start) | Same lag as the chosen design. But an idle-rich interval sweeps at its start and an idle-starved one at its end, so two checks of one word could sit almost two intervals (~255 ticks) apart. That doubles the latency bound | identical lag to the chosen design (`legs_idle_unpaced.txt`) |
| **Idle slot with no in-tick deadline** (only the interval tick catches up) | Same latency-doubling problem as unpaced | not built |
| **Slicing the general regime's refcount sum** | A sum spread over ticks while `Tile_Cache_Fill` rewrites words is wrong in both directions. A word counted as frame A and then rewritten to B, while a not-yet-counted word goes from B to A, leaves every refcount unchanged and the partial sum off by one: a **false failure**. Opposite drifts could also cancel: a **false pass**. Fixing that needs a write barrier in the copy sites (candidate 3's code, off limits here), or a restart-on-write sweep. The fill writes on nearly every tick in motion (survey: 8.5 to 11.3 patch runs per tick), so a restarting sweep never finishes | not built. **Booked**: `docs/DEFERRED_WORK.md`, AUDIT-AMORTISE |
| **A generation counter + restart, for every regime** | Same starvation in motion. The latched regimes need no generation, because nothing is combined across ticks | not built |
| **A faster atomic walk** | The per-word floor is ~40 cycles, and 4800 x 40 = 192k is still 1.5 frames | not built |

## Why a sliced audit cannot report a false failure or a false pass on a consistent state that changed mid-sweep

The claim is about the latched regimes, the only place the walk is sliced. It rests on one
structural property, and the code is written so that the property can be read off it:

1. **Every predicate a slice evaluates reads one instant.** A slice call reads its 40 words
   and builds the assigned-frame mask from `Page_Frames[*].pf_page` inside the same
   `.dangling_walk` call, with no tick in between. The verdict for each word is "at this
   instant, this word names an assigned frame". The one thing that can run in the middle
   of a slice is the VBlank interrupt. It writes neither `Page_Frames` nor
   `Tile_Cache_Nametable`: their only writers are the `engine.page_cache` procs and the
   `engine.tile_cache` fills, all reached from the main thread (the fill from the level
   tick, the page-in's `PageCache_Publish`/`AllocFrame` from `PageIn_Process`, which has
   returned before the audit's idle call starts).
2. **No partial result crosses an instant.** The only state carried between slices is
   `Page_Audit_Slice` (which words to read next) and `Page_Audit_Ticks` (when they are due).
   Neither holds a count, a flag, or a mask. Contrast the general regime's walk, which
   carries per-frame counts in `Page_Audit_Scratch`. That walk is exactly why the general
   regime is not sliced.
3. **So:** a raise from a slice names a word that, **at the moment of the raise**, points at an
   unassigned frame. That is a real violation of (b) in that state, and the whole-walk audit
   would also have raised had it run at that instant. A state that was consistent at every
   instant cannot make any slice raise: **no false failure**. A slice pass means "these 40
   words were fine at this instant", never "the nametable was fine". What the sweep adds up
   to is a **coverage** statement, not a combined verdict: **no false pass** is built out of
   two instants.
4. **Regime changes mid-sweep** (bounded -> general, when `PageCache_EndBoundedRegime` runs
   from the idle slot) are read at each call. After the flip the idle slot stops, and the
   interval tick takes the general regime's atomic walk.
5. **Load and reload.** `PageCache_Init` zeroes `Page_Audit_Ticks` and `Page_Audit_Slice`.
   Pacing allows no slice while the tick count is 0, so `Level_LoadArt`'s `VSync_Wait` spins
   never check the previous act's nametable against a pool that was just reset.

**Measured, not only argued:**

* Nine flight legs (canonical and clip) with the camera rewriting the nametable every tick:
  zero raises, every leg ran to its end.
* The clip's fly-down-into-CPZ leg crosses the bounded -> general flip mid-leg
  (`PageCache_Direct_Map` read 0 at the end): no raise (`results/cpzdown_dm.txt`).

## Coverage kept, and the corruption catch (red-first)

`tools/pagecache_audit_poison.py` (wired in `tools/keepalive_manifest.toml`, keepalive lane)
gained three arms and a latency bound per arm. The bounds are derived from source:
`PAGECACHE_AUDIT_INTERVAL` from `engine/system/constants.emp`, and `PAGE_AUDIT_SLACK_TICKS`
from `engine/level/page_cache.emp`.

* **(b1), (b2):** plant ONE dangling nametable word, the corruption the sliced walk exists to
  catch. It is aimed at the first unassigned frame, read off the booted state (frame 10 on
  canonical), at the first word (slice 0) and at the last word (slice 119).
* **(g):** force `PageCache_Direct_Map` to 0, so that only the general regime's refcount sum,
  reached through the new interval-tick path, can raise.

| ROM | control | (a) rc | (b) frame unassigned | (c) identity | (b1) word, slice 0 | (b2) word, slice 119 | (g) general sum | exit |
|---|---|---|---|---|---|---|---|---|
| base `1ff17f52` (whole walk) | runs | 18 | 18 | 18 | 18 | 18 | 18 | 0 |
| **amortised** `d2a24d49` | runs | 18 | 18 | 18 | **19** | **10** | 18 | 0 |
| **RED-FIRST M1**: `.slices_now` returns without walking (on disk, `git diff` in the commit log) | runs | 18 | 18 | 18 | **NOT CAUGHT** | **NOT CAUGHT** | 18 | **1** |
| control M2: idle gate never passes (all slices done in-tick) | runs | 18 | 18 | 18 | 28 | 18 | 18 | 0 |

Figures are ticks from poke to halt, bounds 128 (frame-level) and 136 (word arms). M1 was
restored from the committed file (`git show HEAD:engine/level/page_cache.emp`) and the tree
checked clean afterwards. M2 shows the in-tick deadline doing the whole job when the idle
slot never has room: (b1) is caught at tick 28 = 18 to the interval + 10 (slice 0 is due at
1, forced at 1+8+1), inside the bound. M2 also shows `Page_Audit_Late` is a live counter:
601 on fly right and 606 on the diagonal with idle off, against **0 on every leg** with idle
on.

**Arm (b) halts via bijectivity, not via the walk.** Unassigning frame 1 also breaks
page/frame bijectivity, and that check runs on the interval tick. This was true before this
parcel too. (b1)/(b2) are the arms that reach the sliced walk, and M1 shows they are the
ones that go red without it.

**The latency bound moved from 128 to 136 ticks for the nametable half** (INTERVAL + slack).
The frame-level half is unchanged at 128. The corruptions the audit guards are monotone
(nothing re-derives them), so a later report is a later report, never a miss. Slack 0 would
give 129 ticks, but it forces in-tick work on every idle-starved tick, which is the cost the
tick-slot design measured.

## Lag, before and after (headless, deterministic)

Figures are `lag frames / video frames while the camera moves`. ROMs: base `91d4119c`
(`s4.debug.bin` `1ff17f52`, `s4.s2clip.debug.bin` `027639e8`) against this branch
(`d2a24d49`, `cd8afc64`). The legs are the survey's (`stub_legs.sh` argv). Raw output is in
`results/legs_base.txt` and `results/legs_after.txt`; every `.meta` carries its
`finished=` stamp (4+5 base, 9 after).

| leg | base | after | survey's audit stub (for reference) |
|---|---|---|---|
| canonical fly right | 6/364 | **0/358** | 0/358 |
| canonical fly down | 6/369 | **0/363** | 0/363 |
| canonical diagonal | 48/411 | **43/406** | 44/407 |
| canonical physics run | 64/1177 | 109/2999 | 109/2999 |
| clip fly right | 16/1014 | **0/998** | 0/998 (Canopy also off) |
| clip fly down | 7/370 | **0/363** | 0/363 (Canopy also off) |
| clip diagonal | 51/1049 | **38/1036** | 33/1031 (Canopy also off) |
| clip CPZ fly down (before/after the switch) | 48/1307 (14/908, 34/459) | **33/1292** (0/894, 33/458) | 26 (Canopy also off) |
| clip CPZ diagonal (before/after the switch) | 84/1343 (14/908, 70/495) | **70/1329** (0/894, 70/495) | 59 (Canopy also off) |

* `Page_Audit_Late` read 0 after every one of the nine "after" legs: the idle slot kept up
  everywhere, including the diagonal.
* **The physics run is not comparable across ROMs**, as the survey said. Inputs are
  scheduled per video frame, so when lag changes, the path changes. Both the survey's audit
  stub and this branch get stuck at x ~1074 and run the full 3000 frames.
* After the CPZ switch the clip is in the general regime. There the atomic walk still runs
  on the interval tick, so "after switch" is unchanged on the diagonal (70) and one better
  on fly-down (34 -> 33). The before-switch halves go to 0.
* Canopy is untouched (still armed). The survey's clip stub column had Canopy off too, which
  is why it is lower on the diagonals.

## Release bytes

| shape | before (`91d4119c`) | after |
|---|---|---|
| `s4.bin` | `0cd3ce63`, 828,920 B | `0cd3ce63`, 828,920 B |
| `s4.debug.bin` | `1ff17f52`, 855,585 B | `d2a24d49`, 855,935 B (+350 B) |

Release is untouched by construction. Every change is inside `if DEBUG == 1`. No new label
exists in release: the three modes are one proc, selected by `d0`. The new RAM is a DEBUG
`@shape_divergent` group at the RAM tail (+4 B, `Page_Audit_Slice`, `Page_Audit_Late`).
`engine/ram.emp`'s shape-divergence sum is re-measured to 12,480 B.

## What I could NOT measure

* **The owner's window.** Headless only, and no emulator MCP.
* **The slice's real cycle cost.** `PAGE_AUDIT_IDLE_MARGIN_LINES` is priced by hand from
  instruction timings (~2,650 cycles, ~5.4 lines, margin 12). The legs show the effect (idle
  kept up, no added lag), not the price.
* **The interval tick's frame-level cost** (~15k cycles est., mostly the 256-entry
  bijectivity loop). It stays in-tick and was not isolated. The canonical diagonal matching
  the slices-off experiment (43) says it costs no lag frame on these legs.
* **Streaming acts past their bulk block** keep the whole walk. Booked in `docs/DEFERRED_WORK.md`, AUDIT-AMORTISE, with the other residue.
