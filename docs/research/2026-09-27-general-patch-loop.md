# The general patch loop: row and column liveness masks instead of per-word refcounts (design, 2026-09-27)

Design parcel with measured prototypes. Nothing here is merged. **Base:** origin/master
`397b1c47` (branch `design/general-patch-loop`). Four prototype branches were cut from
`997212b0`, which differs from `397b1c47` only in `docs/lane-status.json`. Every ROM was
built in this worktree with the pinned `SIGIL_BUILD`/`SIGIL_EMIT`. The tools and raw
results are in `docs/research/2026-09-27-general-patch-loop/`.

## The question

Streaming acts leave the bounded-direct regime at their first frame allocation
(`PageCache_EndBoundedRegime`). From then on every patch run takes the general loop
(`pc_patch_run_loop`), which does two things per nametable word:

- it translates page to frame through `Page_Table`;
- it keeps a refcount pair: ref the new frame, unref the overwritten one, with the
  `PF_EVICTABLE` and `pf_stamp` transitions.

The survey (`2026-09-25-perf-survey.md`, candidate 4) priced this at 2.95k cycles per
`PatchRun_Seq` call, against 1.56k on the direct loop. It estimated the fix at 12 to 18 of
the 30 lag frames in Chemical Plant's painted rows. This parcel had three jobs:

1. find out which half costs what;
2. find a replacement for the half that matters that keeps eviction safe and keeps the DEBUG
   audit meaningful;
3. measure it.

## Answer in one table

The figures are lag frames / video frames in motion, from the survey's harness, on the clip
DEBUG shape `S2CLIP=s2_ehz_cpz` with `PageCache_Audit` live unless noted. "Band" is Chemical
Plant's painted rows, flying down after the turn at x 14400, camera y < 2048: the survey's
30/150 window. "Down" and "diag" are everything after the turn on the two CPZ legs. "EHZ
diag" is the whole diagonal leg from the start; it stays in the bounded regime (survey:
`Direct_Map` 1). `PatchRun_Seq` is cycles per call over the band window.

| lever | branch / ROM crc | CPZ band | CPZ down | CPZ diag | EHZ diag | fly right | `PatchRun_Seq` | kind of figure |
|---|---|---|---|---|---|---|---|---|
| base (origin/master) | `4a3bc66c` | **29/151** | **33/398** | **70/435** | 38/1036 | 0/998 | 2,936 | real |
| no refcount pair at all (unsafe) | `proto/gpl-norc` `3a7ce043` (audit stubbed) | 11/132 | 11/375 | 33/398 | 34/1032 | 0/998 | 1,731 | **upper bound**; eviction can take displayed art |
| no translation, no refcount (unsafe) | `proto/gpl-udirect` `c33749fa` (audit stubbed) | 13/133 | 13/376 | 24/387 | 34/1032 | 0/998 | 1,460 | **ceiling**, wrong picture; also drops demand page-ins |
| A0: exact sweep at every eviction, no barrier | `proto/gpl-sweeponly` `6fca468d` | 22/142 | 22/385 | 43/407 | 38/1036 | 0/998 | 1,889 | real (correct design) |
| A1: row masks, per-run OR into rows | `proto/gpl-rowlive` `30adfd8a` | 18/139 | 18/382 | 49/412 | 38/1036 | 0/998 | 2,001 | real |
| A2: row masks + column masks | `proto/gpl-rowlive2` `7c29c6b0` | 17/138 | 17/381 | 41/405 | 39/1037 | 0/998 | 1,936 | real; costs the bounded regime 1 frame |
| **A3 = A2 without the bounded-regime cost** | **`proto/gpl-rowlive3` `a65ea387`** | **17/138** | **17/381** | **42/406** | **38/1036** | **0/998** | **1,944** | **real: the recommended design** |
| B: translate once per section / per page | not built past the ceiling | | | | | | at most 1,944 → ~1,700 | see "Lever B" |

**Recommendation: A3.** It removes 12 of the band's 29 lag frames, 16 of 33 after the turn
flying down, and 28 of 70 on the CPZ diagonal. The canonical shapes, the bounded regime and
the clip release legs are unchanged. It also makes the general regime's DEBUG audit
sliceable (AA-1): the audit costs 0 lag frames there now, against 6 to 7 at base. The
survey's 12 to 18 estimate held for the band: 12 frames.

## What the refcounts protect today

This is read from `engine/level/page_cache.emp`, not assumed. It is what any replacement
has to keep.

1. **Eviction safety (spec §5).** `pf_refcount[f]` counts the `Tile_Cache_Nametable` words
   that name frame f. `PageCache_AllocFrame` only evicts a frame with refcount 0 that is
   not pinned (`PF_EVICTABLE` implies refcount 0). So no cache word ever names a frame
   whose page left.
   - During the decode, the evicted frame is detached (`pf_page = $FFFF`), and no word
     names it.
   - After the publish, no word shows the new page's art in the old page's place.
   - The scope is the 80x60 tile cache only. Plane A/B VRAM and `Plane_Buffer` hold
     copies of cache words and are not counted. The replacement keeps exactly this scope.
2. **Demand protection.** A page published for a demand stall is left unflagged until its
   first ref, so a second allocation cannot evict it before the stalled fill resumes. That
   would be a livelock.
3. **Eviction order.** `pf_stamp` is the time of the 1→0 release; the oldest candidate
   goes first (F-1).
4. **The DEBUG audit** (`PageCache_Audit`). In the general regime it recomputes every
   refcount from the whole nametable and compares, on one tick every 128. It also checks
   the flag, bijectivity and orphan invariants.
   - This is a **sum**, so it cannot be sliced without a write barrier (AA-1). It is the
     survey's 203k to 236k-cycle hitch, which still hits the clip after the turn.

Nothing outside this module reads `pf_refcount` or `PF_EVICTABLE` (grep, `engine/` and
`games/`).

## Measured first: which half costs what

Two throwaway probes on the clip DEBUG shape, with `PageCache_Audit` stubbed to `rts` in
the probe and in its base (`1f501e8d`), because a refcount-free loop fails the refcount
audit at once.

- **`proto/gpl-norc`** deletes the ref/unref pair and keeps the translation and the miss
  arm: `PatchRun_Seq` 2,920 → **1,731** cycles per call; band 26/148 → **11/132**.
- **`proto/gpl-udirect`** also runs the direct loop in the general arm (no translation,
  wrong picture): **1,460** per call; band 13/133.

So in the band the refcount pair is about **1.19k of the 1.46k per call** that separates the
general loop from a direct one. The translation is the other ~270. Profiled on the CPZ
diagonal after the turn (audit stubbed in all three), the Seq and Col patch runs cost:

| probe | Seq + Col per tick | work, frames per tick | lag |
|---|---|---|---|
| base | 25.7k | 0.689 | 64 |
| norc | 18.1k | 0.625 | 33 |
| udirect | 17.2k | 0.614 | 24 |

udirect's lag is lower than its cycles justify because it never issues a demand page-in (it
has no miss arm), so that 9-frame difference is confounded. Its cycles are the fair
ceiling (`results/lag_tables.txt`). The refcount pair is the lever; the translation is a
small second one.

## Lever A: liveness from the nametable instead of a count per word

A frame may be evicted when no cache word names it. That is a set question, not a count.
This lever answers it from the nametable, as an insertion-barrier mark phase, with no work
on the word being overwritten. The online survey below has the precedents. Three shapes
were built. All three keep the translation and the miss arm exactly as they are, and all
three replace eviction candidacy with one proc, `PageCache_PickVictim`.

**The invariant (A1-A3).** For every cache cell (r, c), at every instant anything reads it,
`frame(word) ∈ Page_Row_Live[r] ∪ Page_Col_Live[c]`. A1 has rows only. Each mask is a u32
with one bit per frame; `ensure(PAGE_FRAMES <= 32)`. What maintains it:

- **Sequential runs** (`TileCache_FillRow`, one cache row per run). The loop does
  `bset d2,d6` per word (d2 is the frame the translation already produced), and the run
  ends with `or.l d6,(a4)` into its row's mask. FillRow publishes `&Page_Row_Live[row]`
  once per row. Cost: 8 cycles a word plus about 60 a run.
- **Column runs** (`TileCache_CopyBlockColumn`, one cache column per run, with the wrap
  split by the caller). The same `bset`, then one `or.l` into the **column's** mask.
  A1 instead OR'd into every row the run touched, which cost ~30 cycles a word and is
  why A1 lost 6 frames to A0 on the diagonal.
- **Blank and zero-fill writes** store `$0000`, which is frame 0. Every row mask always
  carries bit 0: seeded at init, by every sweep, and by every Seq run.
- **The idle sweep** (`PageCache_LiveSweep`, in `VSync_Wait` after `PageIn_Process` and
  after the DEBUG audit's paced slices). It re-derives one row (80 words) or one column
  (60 words) at a time, exactly, while the V counter says one still fits. It is gated like
  the audit (line 212 and `VBlank_Flag`). A row's new mask is exact at the instant it is
  stored, and the barrier keeps it a superset after that. So masks shrink when content
  leaves, and they never under-state.
- **The forced full sweep** (`PageCache_LiveSweepAll`). It re-derives all 60 rows, which
  alone cover every cell, and clears every column mask **at the same instant**, because
  the invariant asks for row or column. It runs at `EndBoundedRegime`, replacing the
  refcount rebuild, and when `PickVictim` finds no candidate.
- **The miss arm** leaves the cell untouched, so its old frame is still in a mask.
- **Nothing interleaves.** The masks are read only by `PickVictim` (from `PageIn_Process`,
  in the idle slot) and by the audit (tick and idle slot). Neither can run between a
  word's write and its run's `or.l`. The miss arm's `PageCache_Request` only enqueues, and
  the VBlank handler writes neither the nametable nor the masks.

**Eviction rule (`PickVictim`).**

- A candidate is an assigned, unpinned frame that is not demand-held and whose bit is clear
  in the OR of the 60 row masks and 80 column masks.
- By the invariant, no cache word names it.
- As today, the victim's page leaves `Page_Table` before `AllocFrame` returns, so no word
  can come to name the frame until `PageCache_Publish` assigns its new page.
- If there is no candidate: one forced full sweep, then the same test on exact masks. Still
  none is the old thrash condition, with the same DEBUG raise and the same release
  re-queue. `Page_Live_Forced` counts the forced sweeps.

**Demand protection.** `Page_Hold_Mask`:

- `PageCache_Publish` sets the frame's bit for a demand page and clears it for a
  speculative one.
- The bit clears when a sweep or a `PickVictim` sees the frame live.
- A held frame is never a candidate.

This is the old rule, released at the first observation of a reference instead of at the
first ref. It can only hold longer, never shorter.

**Eviction order.** `pf_stamp` is refreshed for every frame `PickVictim` sees live, and the
oldest dead frame goes first. That is "last observed live", where the old code used "last
released". It is coarser, and measured it evicts the same number of pages:

- clip zigzag: 24 base, 24 A3;
- STRESS_ART zigzag: 20 base, 21 A1/A2.

Its hit rate under churn is **not measured**.

**Regime and load transitions.**

- **`PageCache_Init`** resets the masks (rows to {0}, columns empty), the hold mask and
  the pointers.
- **Leftover words at act load.** Before `Tile_Cache_Init`'s `TileCache_FillAll`, the cache
  may still hold the previous act's words, which the masks do not describe. The refcounts
  were zeroed at the same point, so this is today's exposure, unchanged. FillAll rewrites
  the whole window, and `PAGE_AUDIT_FULL` runs after it.
- **The DEBUG warp** needs nothing new: masks only over-state, and FillAll rewrites
  everything.
- **The bounded→general flip** happens in the idle slot. A3 publishes the mask pointers
  only while the latch reads 0, and the latch never returns to non-zero mid-act. So no run
  can use a stale pointer.
- **Frame 0** stays live forever, because every row mask carries bit 0. That is harmless:
  page 0 carries the blank tile at physical 0 and is pinned.

**The DEBUG audit, and AA-1.** The general regime's check becomes a **per-word predicate at
one instant**: the word names an assigned frame, and its row mask or its column mask
carries it.

- That is the property eviction relies on, checked directly instead of through a count.
- It slices exactly like the latched regimes' check. Each 40-word slice lies in one row
  and builds its assigned mask in the same call, so no verdict combines two instants
  (`2026-09-26-audit-amortise.md`'s argument, unchanged).
- The general regime therefore joins the paced idle-slot sweep, and the atomic 200k-cycle
  walk is gone.
- The frame-level checks run whole on the interval tick, as before. Bijectivity and
  the flag checks are unchanged. The orphan check becomes "an assigned, held frame that is
  not `PageIn_Cur_Frame`", the same leak class as before.

Measured, clip DEBUG, A3 with the audit live against A3 with it stubbed: band 17 = 17,
down 17 = 17, diagonal 42 = 42. **0 lag frames**, against base 29 vs 26 (band), 33 vs 26
(down) and 70 vs 64 (diagonal).

**Red first.** Each mutation was made on disk with `sed` on the prototype branch, then built
with FAST (clip DEBUG). The file was restored from the committed content with
`git show HEAD:<path> > <path>`, and the tree was checked clean each time
(`results/halts.txt`).

| mutation | CPZ down | CPZ diagonal |
|---|---|---|
| none (A3 `a65ea387`) | runs to (14400,5920) | runs to (16064,5920) |
| M1r: Seq run's `or.l d6,(a4)` → `nop` (A2) | **halts**: "a cache word names a frame its row and column liveness masks omit" | **halts**, same |
| M1c: Col run's `or.l d6,(a4)` → `nop` (A2) | runs (no column runs when flying straight down) | **halts** at (15280,976), same message |
| M1: A1's `bset d2,d6` → `nop` | **halts** (A1's "unassigned frame" message) | **halts** |

**The picture.** `pic_witness.py` resolves every cache word and every visible Plane A cell
through the VRAM it names: attribute bits plus the 32 pattern bytes. It compares two ROMs
at stop points matched by camera. It has to resolve, because a liveness lever frees
different frames, so raw words differ while the picture is the same ("raw cache words
differ" in the output).

- **Clip zigzag.** Right to x 14400, then down, left into Emerald Hill, up, right, down,
  left, up, right, left: 2,600 ticks, 52 points, 24 evictions.
  - A1, A2 and A3 against base: **identical at 52/52** (visible window and whole tile cache).
- **STRESS_ART zigzag** (41 pages over 15 frames). 22 points, but only 10 or 11 of them
  camera-matched, because the phase changes are polled per frame and drift by a tick or
  two. Unmatched points are printed as UNMATCHED, never as identical.
  - A1 and A2: **identical at every matched point**, 20-21 evictions, no halt.
  - A1 with the idle sweep stubbed: identical, and it took the forced-sweep path 3 times.

**What the witness cannot show, said plainly.** On the clip, even an unsafe build keeps the
picture:

- **norc** (no refcounts): identical at 52/52;
- **A1 with no barrier and no sweep, audit stubbed**: identical at 52/52;
- **M2** (liveness ignored entirely, FIFO by publish time): identical at 52/52, with a
  counter showing **0 live evictions in 30**.

With 12 frames and 17 pages, the oldest page is always dead on this content. So on
today's acts the liveness proof is **never load-bearing**: the gain is all per-word cost,
and the safety argument above is what carries correctness. Only STRESS_ART discriminates:

- M2 there made **119 live evictions** and the leg halted in the demand-stall watchdog;
- the no-barrier-no-sweep build halted in thrash (its holds never clear).

Neither failure showed as a wrong picture at a matched point before its halt. Treat the
witness as "no difference seen", not as proof.

### A0: the barrier-free variant (measured, not recommended)

`proto/gpl-sweeponly` drops the barrier and the idle sweep. `PickVictim` re-derives every
row (and clears the columns) before every choice, so it is exact at that instant and needs
no barrier. It is correct for the same reason as A3's forced path.

Measured: band 22/142 against A3's 17/138, diagonal 43 against 42.

- **Its cost is per eviction:** about 150k cycles in the idle slot, 0.03 calls a tick in
  the band, and each one can cross a VBlank.
- **A3's cost is per word.** On today's clip the two are close.
- **A mega-act evicts far more often** (DEFERRED_WORK S2CLIP-LAG item 1). A0's cost
  scales with evictions; A3's does not. That is why A3 is recommended and A0 is the
  fallback if the barrier ever has to go.

## Lever B: translate once instead of per word

What is left of the general loop's extra cost over a direct loop is the translation:
`lsr`, `Page_Table` byte read, `bmi`, mask, `lsl`, `or`.

- **Its ceiling is measured** (udirect): about **270 cycles per call** in the band, and
  0.9k per tick on the CPZ diagonal. That is 3 to 5% of the patch cost.
- The ceiling's lag figure is confounded, as above, so **there is no measured lag gain**
  for this lever.

**Variants considered, not built:**

- **A per-section translated map** (local → physical, staged with the section). Clip maps
  hold 253 to 528 entries (`OJZ_Sec*_LocalMap`, 0.5 to 1 KB each), and a window touches up
  to 4 sections, so 2 to 4 KB of RAM.
  - The DEBUG shape has **3,792 B** of headroom.
  - Every eviction or publish would have to invalidate or patch the entries of the page it
    moves: a scan per page event, or a generation rebuild.
  - It would recover at most the ~270.
- **A per-page delta table** (`physical = global + delta[page]`; a non-resident page's
  delta makes the sum negative, so one `bmi` tests residency). 512 B of RAM. By
  instruction count it saves only ~18 cycles a word once the barrier needs the frame
  number: the table would have to return the frame too (a long per page, 1 KB).
- **Translating the staged block in place.** Raw-direct blocks are staged zero-copy from
  ROM, and every eviction epoch would need a re-translation. This is the same rejection the
  resident plain copy recorded.

**Recommendation:** defer. It is worth at most ~270 of A3's 1,944 cycles per call. Revisit
only if a mega-act profile shows the translation, not the fill structure, on top.

## Lever C: copy all-resident runs without per-word work

In the general regime the physical word depends on the page's frame, so a run cannot be a
plain copy unless the staged words are already physical. That is lever B's staged-block
variant, rejected above. After A3 the per-word work that is not translation is one
`bset`, 8 cycles. **Nothing left to take.**

## Reference and online research

**Reference disassemblies** (Explore agent, file:line evidence in the task output).
None of the eight streams level art into reusable VRAM slots on the strength of what the
map still names:

- S.C.E., S3K and S2 load per act or at a boundary, into fixed slots;
- Batman & Robin and Vectorman resolve slots offline;
- Gunstar Heroes and Alien Soldier stream sprites into fixed windows;
- Thunder Force IV uses a bump allocator that never frees;
- Ristar loads per stage;
- sonic_hack has an unbuilt per-art-type refcount plan.

Aeon's per-word refcount has no precedent there, and neither does this lever.

**Online** (general-purpose agent):

- **SGDK** frees VRAM regions by single ownership (`vram.c`), with no sharing.
- **SpritesMind t=3244** proposes scanning columns as they scroll off. That is the nearest
  console precedent for deriving liveness from the map.
- **Virtual texturing** (van Waveren 2012; Barrett, GDC 2008) chooses victims by LRU over
  a feedback pass. It never proves a page unreferenced, because the page table falls back
  to a coarser mip. Aeon has no fallback, so LRU chooses **among** proven-dead frames and
  never proves.
- **GC write barriers**:
  - the Dijkstra insertion barrier (Go proposal 17503) is the right family: the map is the
    only root, so marking the written frame suffices and the overwritten one needs nothing;
  - card marking (Hölzle 1993) is the "dirty row" alternative. It was rejected here
    because horizontal scrolling dirties every row every tick, so the final re-scan never
    shrinks.

Sources are listed in the agent reports.

## The canonical shapes do not move

A3 on canonical OJZ (resident, `PAGECACHE_DIRECT_PLAIN`, latch 128):

- **DEBUG** fly right 0/358, down 0/363, diagonal 14/377, physics 7/335, spindash 5/1,174;
- **release** physics 3/1,295, spindash 1/1,169.

All seven are identical to base (`88e5b2e0`, `2f6354dc` → `8ea32a7b`, `78823c26`).

The clip release shape stays bounded throughout its physics legs: run 22/2,790 and spin
15/337, both equal to base (`8e044357` → `4eedd8f8`). A2 cost this shape 1 frame (spin
16/351), which is why A3 exists.

The only instructions A3 adds to the latched and bounded paths:

- a `tst.b`/`bne` in FillRow and in CopyBlockColumn;
- the call into `PageCache_LiveSweep`, which returns at once on a non-zero latch.

## Cost

- **RAM, both shapes, +576 B:**
  - `Page_Row_Live` 240 B and `Page_Col_Live` 320 B;
  - hold mask 4, two pointers 8, sweep cursor 2;
  - two prototype counter bytes, which the final build can make DEBUG-only.

  DEBUG headroom goes from 3,792 to ~3,216 B. `pf_refcount` becomes dead (8 bytes per frame
  stay for the power-of-two stride).
- **ROM:** DEBUG code +146 B (page_cache section 4,970 → 5,070 B; earlier modules +46).
  `EndOfRom` is unchanged in all four shapes: fixed-address placement absorbs it. Release
  code size was not isolated, because the module straddles a placement split at `$8000`.
  File sizes grow ~500 B, mostly the deb2 appendix.
- **Idle CPU:** the sweep takes the idle slot's leftovers (~15k cycles/tick in the band).
  Stubbing it moved nothing: A1 17 = 17 in the band with the audit stubbed, and A1 with the
  audit live 49 vs 52 on the CPZ diagonal, the swept build 3 lower.

## Release (plain shape): what could and could not be measured

**The brief asked for the four fly legs on the plain shape too; that cannot be done as
written.** Release has no free flight, so the plain clip shape can only run the physics and
spindash legs. Those stay in the bounded regime (above: unchanged). No release leg reaches
the general regime.

As a proxy, the general loop's DEBUG-only checks were removed from **both** base and A3
(`base_nochk` `c008f5d8`, `rowlive3_nochk` `d5d52fc1`), leaving the loop that release
assembles:

- band **24/146 → 15/135**;
- CPZ down after the turn 28 → 15;
- CPZ diagonal 66 → 32;
- `PatchRun_Seq` 2,640 → 1,816 cycles per call.

This is an estimate for release, not a release measurement. The rest of the DEBUG shape
(audit, Canopy) is still in these ROMs.

## Staged build plan

1. **The engine change, A3, written properly** (one parcel; it moves bytes in every shape).
   - **Rewrite from the prototype diff** (`proto/gpl-rowlive3` over `997212b0`) as final
     code, not a copy. Its comments are prototype notes.
   - **Remove the refcount machinery:**
     - the refcount walk in `PageCache_EndBoundedRegime`;
     - the refcount clears in `PageCache_ResetRefcounts` (rename it to what it now does:
       release holds);
     - the `PF_EVICTABLE` transitions and the victim scan's refcount assert;
     - `pf_refcount` itself, or keep the field and document it as padding.
   - **Replace the latched-regime audit arm (a), "zero refcounts".** It was the detector for
     "a general run ran under a latch". Its equivalent is "under a latch every row mask is
     exactly {0} and every column mask is empty": only a general run writes them, and the
     latch never returns mid-act.
   - **Split the general audit message** into "unassigned frame" and "frame outside its
     row/column masks".
   - **Re-aim `tools/pagecache_audit_poison.py` arm (g)** (it forces the general regime by
     poking `Direct_Map` to 0). Without mask pokes it would now halt through the masks, not
     the planted word. Give it a planted-word arm and a cleared-mask-bit arm, each red-first
     with the check mutated.
   - **Keep the counters DEBUG-only**, or drop them.
   - **Evidence:**
     - `landing_build.sh`, exit code pasted;
     - this parcel's `pic_witness.py` on the clip zigzag and on STRESS_ART, against the
       parent;
     - the CPZ legs.
   - **ARCH §9.7 update:** rewrite the refcount sentences in "Correctness invariants", "The
     streaming path" and the module header.
2. **A lane that runs the general regime on a built shape** (survey candidate 6). Today
   neither `landing_build.sh` nor the nightly builds a streaming shape, so nothing that
   gates a merge exercises this code, before or after stage 1. A clip DEBUG lane should:
   - run the two CPZ legs plus `halt_probe`;
   - ideally run the STRESS_ART zigzag with `pic_witness`;
   - carry a derived lag ceiling and be red-first.
   This is the net stage 1 needs **before** it can be called safe to keep.
3. **Optional, measured first:**
   - Seq runs publish the row pointer per row; a caller-held register would save the
     remaining ~40 cycles a row;
   - unroll the column sweep;
   - lever B, only on a mega-act profile.
4. **Owner calls:**
   - whether +576 B of RAM is acceptable in both shapes. DEBUG headroom goes to ~3.2 KB;
     the mega-act has not been sized against it;
   - whether "last observed live" LRU is acceptable without a churn hit-rate measurement.

## Open items (not measured, not zero)

- **Release fly legs:** impossible (no free flight). The proxy is above.
- **The liveness proof is not exercised by today's content.** 0 of 30 evictions were of
  live frames even when liveness was ignored. Only STRESS_ART makes it load-bearing, and
  there base itself halts:
  - fly right: thrash at (752,144);
  - fly diagonal: the orphan audit at (1712,1728).
  These halts are **pre-existing** (base `41401ef1`, `results/halts.txt`) and not caused by
  this parcel; A1/A2 halt at the same points with the same messages. They deserve their own
  booking: the orphan halt on the diagonal is a demand page published and never
  referenced.
- **LRU quality under churn** ("last observed live" vs "last released") is not measured.
- **The owner's look** at the clip in Chemical Plant on the A3 build: pixels are not a gate
  here.
- **The sweep's per-row price** is gated by hand like the audit's (12 lines of margin). It
  was profiled at ~2.5k cycles a row, but no instrument checks the margin.
- **Why A3 costs 1 frame more than A2 on the CPZ diagonal** (42 vs 41) was not bisected. The
  pointer-publish gate adds ~26 cycles a row in the general regime; the likely cause is
  threshold noise.
- **Two stale "Assertion failed" strings** in the `halt_probe`/`pic_witness` halt output are
  other RaiseError return addresses left on the stack. The tool prints every candidate. The
  PageCache message is the halt's.

## Branches and tools

| branch | tip | what |
|---|---|---|
| `design/general-patch-loop` | this commit | this report + tools + results |
| `proto/gpl-norc` | `8b0e4606` | probe: refcount pair deleted (upper bound, unsafe) |
| `proto/gpl-udirect` | `565faade` | probe: direct loop in the general arm (ceiling, wrong picture) |
| `proto/gpl-rowlive` | `33d3b8d3` | A1: row masks |
| `proto/gpl-sweeponly` | `3b9aaa9d` | A0: exact sweep per eviction |
| `proto/gpl-rowlive2` | `8e8b9a33` | A2: row + column masks |
| `proto/gpl-rowlive3` | `94cc63fa` | **A3: the recommended design's prototype** |

**Tools**, all in `docs/research/2026-09-27-general-patch-loop/`:

- **`gpl_probe.py`**: the survey's `leg_probe.py` with its socket moved off `/tmp`, which
  was over its disk quota. `GPL_WORDS` reads u16 counters whole.
- **`gpl_legs.sh`**: the survey's legs plus `cpzband`, the survey's 150-frame window
  profiled.
- **`gpl_summary.py`**: before/after/band tables, with DID NOT RUN for a missing leg.
- **`pic_witness.py`**: the resolved-picture witness, with multi-phase zigzag drives and
  halts named from the stacked RaiseError message.
- **`halt_probe.py`**: runs a leg until it halts, then names the RaiseError.

**Results:**

- `results/lag_tables.txt`: every leg quoted here. Four legs that were never requested
  print DID NOT RUN.
- `results/pic_witness.txt`: 11 comparisons, `finished=11`.
- `results/halts.txt`: 14 probes, `finished=1`.
- `results/legs.tar.gz`: raw rows, profiles and `.meta` files, 30 of them, each with its
  `finished=` stamp.

Lag counts are deterministic headless counts. Loadavg was 2.4 to 4.5 through the runs,
which changes wall-clock only. Builds took 8 to 13 s (FAST, clip) and 282 to 289 s
(STRESS_ART/STRESS_EVICT, full); each `build.meta` carries its uptime. No emulator MCP tool
was used. The `.pyc` caches were NOT cleared. The only imported modules
(`leg_probe.py`, `lag_flythrough_probe.py`) were never edited in this parcel; the edited
scripts run as `__main__`, which Python does not cache.
