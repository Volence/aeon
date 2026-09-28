# Tile-cache thrash on an oscillating camera (2026-09-28)

Branch `perf/oscillation-thrash`, based on `origin/master` `32a3f074`. Subject: the perf survey's
candidate 7 (`docs/research/2026-09-25-perf-survey.md`) and PERF-EHZ-RUN-LAG open item 2
(`docs/DEFERRED_WORK.md`): *why does a camera that barely moves decode more blocks per tick than
one flying at full speed?* Tools and raw results: `docs/research/2026-09-28-oscillation-thrash/`.

## The answer

1. **The thrash is real and is exactly "the same blocks, decoded again".** On an oscillating camera
   81% to 99% of block decodes are blocks the cache had already decoded; on straight flight, 0%.
   Pages play no part (0 page loads on every leg, both acts).
2. **The lag it caused is mostly gone on today's tree.** The soft decompress budget
   (PERF-EHZ-RUN-LAG) spreads the re-decodes to at most one per tick. The survey's OJZ bounce
   is now **0/1800** lag in both shapes (the survey measured 24/600 in that window); the EHZ
   dead end is **8/1500** (the 09-27 study measured 98/1500).
3. **Two mechanisms; the first is speculation.** The speculative column scan re-aims
   at every reversal, stages the block one past the far cache edge, the camera never gets
   there, and each such claim evicts one of the 16 round-robin staging slots holding the blocks
   the DEMAND fill re-reads at the window edges. Forcing speculation off cut a one-block
   oscillation from 518 decodes to 32 (and broke straight flight, so it is not the fix). The
   second (item 5) is the demand window itself on swings wider than its slack.
4. **Fix (landed on the branch): an arming run on the horizontal speculation.** The column scan
   and the corner stage only after the camera has moved `H_PFX_ARM` = 128 px (one block) with
   the direction latch since it was set or flipped. One-block oscillation: 518 -> 44 decodes
   (and 0 after warm-up); OJZ bounce 757 -> 560; EHZ dead end 319 -> 286. **No lag regression
   on any leg**, straight flight byte-for-byte the same decode count. A vertical arming run cut
   more decodes but cost 2-3 lag frames on the release EHZ run, so it is not landed (below).
5. **What is left is demand re-decoding, and it is design-sized.** A large bounce (OJZ: an
   18-column swing plus a 10-row swing; EHZ dead end: 71 columns) has a demand working set
   above 16 staging slots. The lever is staging capacity or the window's eviction policy
   (priced below), not a tweak.

## Hypotheses, what each forbids, what was measured

The instrument (`thrash_probe.py`) wraps the 2026-09-27 EHZ probe (tick-keyed inputs, same legs)
and reads `Block_Stage_Keys`, `Block_Stage_Gen`, the four cache edges and `Page_Table` after every
video frame. A tick claims at most 6 of the 16 slots and a claim never re-stages a live key, so
the slots whose key changed between two reads ARE that frame's decodes, named by block. The key
diff agreed with the `Block_Stage_Gen` delta on every frame of every leg (0 mismatch frames).
`analyse.py` then counts re-decodes of the same key, classifies each claim against the cache
window read the same frame (`in` = inside the window, a demand decode; `L/R/U/D` = past that edge,
speculation), and counts a claim as WASTED when round-robin evicts it (16 claims later, exact)
before the window ever reached its block.

| hypothesis | forbids | measured | verdict |
|---|---|---|---|
| **H0 control**: straight flight re-decodes nothing | re-decodes / wasted claims on straight flight | fly right / down, both acts: **0** re-decodes, **0** wasted | holds; the leg set can see the difference |
| **H1 block-cache eviction then re-decode** on reversal | a low re-decode share while oscillating | OJZ bounce 90%, EHZ dead end 81.5%, synthetic 128-px oscillation 93% re-decodes | confirmed |
| **H1a** the re-decodes come from speculation evicting edge blocks | re-decodes surviving with speculation OFF | X1 (speculation forced off): one-block oscillation **518 -> 32** decodes | confirmed for swings within the demand working set |
| **H1b** the demand window itself overflows staging | re-decodes vanishing with speculation off | X1: OJZ bounce still 442 decodes, 89% re-decodes | confirmed for large swings; design-sized |
| **H2 page ping-pong** | any page load on a resident act; on the clip, loads repeating | **0 page loads** on every leg of both acts (OJZ is resident, `PageCache_Direct_Map` $80; the clip bounded-direct, $01, never loaded a page after boot on these legs) | refuted on today's tree |
| **H3 soft/hard regime flipping** | a change in the TOTAL decode count (the budget only defers); bursts > 1 on lag ticks | every remaining clip lag tick carries ONE demand decode, no bursts; the budget cannot create decodes | refuted as a cause of decodes; it is what turned the old bursts into single decodes |

Every remaining lag frame on the clip run and dead-end legs (6 on the DEBUG run, 8 on the dead
end, 7 in the pit) carries one DEMAND decode, and in all but one of them the block had been
decoded before. That is H1b.

## Legs

Same vocabulary as the 09-27 study (`run_legs.sh`); all counts are deterministic headless counts
(`oracle-aether`, no pacing, one leg at a time), lag = video frames minus logic ticks, compared
over the same tick span (the 09-27 spancmp rule).

- **Controls**: DEBUG fly right / fly down, both acts.
- **OJZ bounce** (`c_run`, `c_run_dbg`): the 09-27 canonical run drive (right, C for 10 of every
  45 ticks, 1800 frames). On this tree it bounces from x ~926 to 1073 for most of the leg, which
  is the survey's candidate-7 subject.
- **Synthetic oscillation** in DEBUG free flight (camera path fixed by input): after a lead-in,
  right/left alternating every 4 or 8 ticks (64 / 128 px swings), and a diagonal version.
- **EHZ dead end** (`e_deadend_dbg`): warp to (6300, 690), then the auto drive (jump when stuck),
  1500 frames: the 09-27 study's open item 2.
- **EHZ pit** (`e_pit`, release and DEBUG): the auto run past x 5850 into the pit under the
  missing bridge; the one oscillation reachable in RELEASE (there is no release warp).
- **The 09-27 leg set unchanged** (`final_legs.sh`: runs, spindash runs, fly diag/right/down on
  both acts, with coverage and the parallax-output compare), as the no-regression control.

## Baseline on `32a3f074` (FAST builds; `results/crc_base.txt`)

| leg | ROM | lag / frames | decodes (per tick) | re-decodes | wasted spec |
|---|---|---|---|---|---|
| OJZ fly right (DEBUG) | `1000eded` | 0/700 | 180 (0.257) | 0% | 0 |
| OJZ fly down (DEBUG) | `1000eded` | 0/700 | 220 (0.314) | 0% | 0 |
| EHZ fly right (DEBUG) | `69340439` | 0/1100 | 500 (0.455) | 0% | 0 |
| OJZ bounce, release | `d2c5842a` | 0/1800 | 757 (0.421) | 90.2% | 255 |
| OJZ bounce, DEBUG | `1000eded` | 0/1800 | 757 (0.421) | 91.1% | 255 |
| OJZ osc 128 px | `1000eded` | 0/700 | 518 (0.740) | 93.1% | 164 |
| OJZ osc diagonal | `1000eded` | 4/700 | 614 (0.882) | 89.6% | 273 |
| EHZ run, release | `69873061` | 0/1201 | 481 (0.400) | 43.0% | 87 |
| EHZ run, DEBUG | `69340439` | 6/1207 | 479 (0.399) | 44.1% | not computed |
| EHZ dead end (DEBUG) | `69340439` | 8/1500 | 319 (0.214) | 81.5% | 75 |
| EHZ pit, release / DEBUG | | 1/3000, 7/3000 | 696, 694 | 57% | 150 |
| EHZ osc diagonal | `69340439` | 18/900 | 849 (0.963) | 92.6% | 361 |

Bytes: `s4.bin` 829,987 · `s4.debug.bin` 856,982 · `s4.s2clip.bin` 929,590 · `s4.s2clip.debug.bin`
956,402. The 09-27 DEBUG run leg reproduces that study's after figure exactly (6/1207).

Why a barely moving camera decodes more than a flying one: flying right, the column prefetch
stages each block column once, ahead of the window, and every staged block is used (0 wasted).
Bouncing, the window's edges cross the same block boundaries in both directions, the prefetch
stages a block column past whichever edge it last moved towards, and those claims push the
edge blocks out of the 16 slots before the next reversal needs them. OJZ's bounce touched 74
distinct blocks and decoded them 757 times; 48 of them, 614 times, after the first 400 ticks.

## Experiments (DEBUG shapes unless named; `results/table_base_vs_x*.txt`)

| build | change | OJZ osc 128 px | OJZ bounce | EHZ dead end | EHZ fly right | EHZ run rel / DEBUG |
|---|---|---|---|---|---|---|
| base | | 518 dec, 0 lag | 757, 0 | 319, 8 | 500, **0** | 0 / 6 |
| X1 | speculation forced off | 32, 3 | 442, 0 | 198, 8 | 488, **120** | n/a / 9 |
| X3 | arming run, H 128 px + V 16 rows | 44, 0 | 473, 0 | 262, 7 | 500, 0 | **2** / 5 |
| X4 | V 3 rows | 44, 0 | 524, 0 | 281, 8 | 500, 0 | **3** / 7 |
| X5 | V 8 rows | 44, 0 | 473, 0 | 262, 7 | 500, 0 | **3** / 6 |
| X6 / final | **H only** (V inert, then deleted) | **44, 0** | **560, 0** | **286, 8** | 500, 0 | **0 / 6** |

X2 was X3 without "the first motion after init arms at once": it cost 1-2 lag frames at the
start of every flight from rest (EHZ fly right 0 -> 1), so the first latch set arms immediately.

**The vertical arming run is not landed, by measurement.** At every value tried it put 2-3 lag
frames on the release EHZ run (0 -> 2/3) and spindash run (1 -> 3). The lag ticks (x 4809 and
5115) each held a DEMAND decode the base had prefetched: every hill crest is a vertical reversal,
and a delayed row prefetch becomes a demand decode. The horizontal axis has no such cost on the
runs because a run never reverses horizontally (0 leftward frames on the EHZ run).

## The fix

`engine/level/tile_cache.emp`, `Tile_Cache_Fill`'s column scan: `Cache_H_Pfx_Run` counts px moved
WITH the H direction latch since it was set or flipped (motion against it subtracts; clamped
0..`H_PFX_ARM`). The scan still derives and publishes `Cache_Pfx_Col_Target` (the page tier aims
by it); it only STAGES once the run has reached `H_PFX_ARM`. The corner block, which is horizontal
speculation too, has the same gate. The latch's first set after `Tile_Cache_Init` arms at once.
`H_PFX_ARM` = `BLOCK_TILE_SIZE` * 8 = 128 px, one block, with an ensure bounding it between one
tick of camera step (16 px) and the cache's horizontal margin (20 columns): past the margin the
demand fill would reach the block before the scan could stage it. Cost: 13 instructions on the
tail path per tick (about 60 cycles by instruction count, NOT measured). RAM: one word.

### Before / after, all legs (final FAST builds; `results/table_base_vs_fin.txt`, `results/final_table_base_vs_fin.txt`)

| leg | before | after |
|---|---|---|
| OJZ osc 128 px (DEBUG) | 0/700, 518 dec | 0/700, **44** dec (0 after warm-up) |
| OJZ osc 64 px | 0/700, 32 | 0/700, 28 |
| OJZ osc diagonal | 4/700, 614 | 4/700, **88** |
| OJZ bounce release / DEBUG | 0/1800, 757 | 0/1800, **560** |
| EHZ osc diagonal | 18/900, 849 | **16**/898, **78** |
| EHZ osc 64 px | 0/900, 112 | 0/900, 108 |
| EHZ dead end (DEBUG) | 8/1500, 319 | 8/1500, **286** |
| EHZ pit release / DEBUG | 1/3000, 696 / 7/3000, 694 | 1/3000, 642 / 7/3000, 640 |
| EHZ run release / DEBUG | 0/1201 / 6/1207, 481 / 479 | same, same decodes |
| fly right / down, both acts | 0 lag; 180 / 220 / 500 dec | identical |
| 09-27 set: clip run, spin (rel, DEBUG) | 0/1201, 1/1244, 6/1207, 5/1248 | identical |
| 09-27 set: clip fly diag / right / down | 23/1100 (EHZ band 18/74), 0, 0 | identical |
| 09-27 set: OJZ fly diag / right / down, run rel / DEBUG | 12/700, 0, 0, 0/1800, 0/1800 | identical |

Visible coverage (undrawn visible cells, read every frame) is identical on every leg of both
sets. The parallax output compare of the 09-27 set is 0 differing ticks on every leg. Paths agree
tick for tick (at most one mid-tick snapshot tick off, the 09-27 study's known artefact).

**Plainly: this fix removes CPU work, not lag, on the legs measured.** Lag moved only on the
EHZ oscillating diagonal (18 -> 16, both in the leg's opening diagonal). The lag the survey and
the 09-27 study saw on these legs had already been removed by the soft budget; what this buys
is 0.1 to 0.7 fewer ~11.5k-cycle decodes per tick while a camera swings, which is headroom for
whatever else lands on those ticks.

| ROM (final) | CRC32 | bytes |
|---|---|---|
| `s4.bin` | `421a8433` | 830,062 |
| `s4.debug.bin` | `318adbe6` | 857,039 |
| `s4.s2clip.bin` | `518bc1c3` | 929,665 |
| `s4.s2clip.debug.bin` | `f487505c` | 956,461 |

### The gate

`tools/oscillation_thrash_gate.py`, wired into `tools/effects_gates.py` after `tile_cache_fill`
(so the ritual and the nightly run it). DEBUG free flight swings by exactly `H_PFX_ARM` (read from
the listing), warms up two periods, counts `Block_Stage_Gen` over 600 ticks, expects **0**. The 0 is
derived: a one-block swing crosses at most one block-column boundary per edge, so its demand
working set is 2 x ((`TILE_CACHE_ROWS` - 1) / 16 + 2) = 10 blocks, which fits 16 slots (the gate
checks this and exits 2 if not); only speculation can claim. Red-first on disk
(`results/redfirst_gate.txt`): the col scan's two arming instructions removed, rebuilt: **RED, 452
claims**; restored from HEAD: GREEN, 0. Also GREEN on the clip DEBUG ROM
(`results/gate_clip_debug.txt`). The ensure was red-first at 16 and 168 px
(`results/redfirst_ensures.txt`).

## What is left, priced (design-sized, not built)

**Demand re-decoding on large swings (H1b).** With speculation quiet, the OJZ bounce still
decodes 560 blocks in 1800 ticks, 87% of them again, and the EHZ dead end 286. The swing is
bigger than the window's slack: the cache is 80 columns for a 41-column view, so a swing of D
columns re-fills D columns at each end on each reversal, and whenever that crosses a block
boundary its blocks have to be in staging. The two levers:

- **More staging slots.** 16 more slots = 12,288 bytes of RAM (768 each) plus 16 x 13 bytes of
  keys, pointers, maps and chain. `Game_RAM_End` is `$FFC102` against the stack at `$FFFF00`,
  so it would take most of the ~15.8 KB between them. The memo masks and eviction windows are
  exactly 16 wide (`rol.w`, a u16 mask; ensure'd at `BLOCK_STAGE_SLOTS` == 16), and
  `PageCache_Prefetch` clears the scan positions with four `clr.l`, so this is a widening of
  those to longs as well. OJZ's bounce touched 48 distinct blocks in its steady part, so even 32
  slots would not hold it outright; the gain is the residency lengthening past the bounce period
  (45 ticks), which is not measured. Estimate: M.
- **Window hysteresis on the trailing edge.** Keep the trailing columns on a reversal until the
  new leading side's lead falls below a threshold, instead of refilling to the full margin at
  once. Worked through: with an 80-column cache, a 41-column view and a minimum lead L on each
  side, a swing of up to 39 - 2L columns needs no refill (L = 10: 19 columns, just the OJZ
  bounce). The price is a shorter lead in sustained motion after a reversal unless the fill
  catches up faster than the camera, and a catch-up is a column-copy burst, which is exactly
  what OJZF-2 measured as lag. That changes the cache window contract (ARCH §9.7's margin), so
  it is a design parcel, not this one.

**Lag.** The remaining lag on these legs (EHZ run DEBUG 6, dead end 8, pit 7) is one demand
decode landing on an already heavy tick; OJZF-1 and PERF-EHZ-RUN-LAG items 3 and 4 (copy cost,
parallax per-band work) are the same budget.

## Method notes

- No emulator MCP; every run is the headless `oracle-aether` subprocess. `.pyc` caches were
  cleared before measuring. Headless lag counts do not depend on host load; loadavg per leg is in
  `results/legs_*.meta` (8.9 to 25.5 while other agents built).
- FAST builds throughout the measurement (byte-identical to canonical by construction; the full
  builds are the landing evidence in DEFERRED_WORK).
- The donor trees `games/sonic4/data/donors/` (gitignored) were copied from the main checkout to
  build the clip; the base clip CRCs are this worktree's.
- Tools: `thrash_probe.py`, `analyse.py`, `table.py`, `run_legs.sh`, `pack.sh`,
  `redfirst_ensures.sh`, `redfirst_gate.sh`. Raw leg JSONs: `results/legs_{base,x1,fin}.tar.gz`.
