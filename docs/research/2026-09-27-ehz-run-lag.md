# Lag while running through Emerald Hill (2026-09-27)

The owner, 2026-09-27: *"I still feel slight lag running through ehz even as a character."* He plays
the Sonic 2 clip act (`S2CLIP=s2_ehz_cpz`), mostly the DEBUG shape `s4.s2clip.debug.bin`, running,
not flying.

Branch `perf/ehz-run-lag`, based on `origin/master` `366b777c` (after the lines-everywhere
merge `19978b00`; first based on `0cf75f6e` and rebased, every number below re-measured on the
rebased builds unless it says otherwise). Tools and raw results:
`docs/research/2026-09-27-ehz-run-lag/`.

## The answer

The lag the owner feels while running is **not parallax**. Each lag frame on a run is one tick in
which the tile cache decodes **3 to 6 blocks at once** (about 11.5k cycles each), at the moment the
camera crosses a block row or column. The cache still leads the screen by its full margin at that
moment, so none of that work was urgent. Parallax (15.5k cycles every tick) is part of the baseline
the burst lands on.

Two engine changes:

1. **Soft decompress budget** (`engine/level/tile_cache.emp`, `engine/system/constants.emp`). A tick
   decodes at most `BLOCK_DECOMP_SOFT` = 1 block while the FILLED cache leads the visible screen
   by at least 8 rows and 10 columns on every side (half its margin). Otherwise it gets the full 6,
   as before. The same blocks are decoded in the same order, only later.
2. **Faster curve line loop** (`engine/level/parallax.emp` `.lp_curve`): the FG word is packed into
   the accumulator's high half so one `move.l` writes each line, and the loop is 8x unrolled. That
   is 21.25 cycles a line, down from 34; the output is identical.

| leg (S2 clip unless named) | before `366b777c` | after | same ticks |
|---|---|---|---|
| **run, release** `s4.s2clip.bin` | **31** / 1232 | **1** / 1202 | 1201 |
| **run, DEBUG** `s4.s2clip.debug.bin` | **39** / 1240 | **6** / 1207 | 1201 |
| spindash run, release | 34 / 1277 | 2 / 1245 | 1243 |
| spindash run, DEBUG | 45 / 1288 | 7 / 1250 | 1243 |
| fly diagonal, DEBUG, whole act | 37 / 1100 | 35 / 1098 | 1063 |
| fly diagonal, DEBUG, Emerald Hill band (camera y < 1024) | 33 / 89 | 29 / 85 | 56 |
| fly right / fly down, DEBUG | 0 / 0 | 0 / 0 | 1100 / 400 |
| canonical OJZ run, release `s4.bin` | 11 / 1800 | 2 / 1791 | 1789 |
| canonical OJZ run, DEBUG `s4.debug.bin` | 26 / 1800 | 2 / 1776 | 1774 |
| canonical OJZ fly diagonal, DEBUG | 14 / 700 | 12 / 698 | 686 |
| canonical OJZ fly right / down, DEBUG | 0 / 0 | 0 / 0 | 700 / 700 |

Figures are **lag frames / video frames over the same span of logic ticks** (both legs are cut at
the smaller tick count; `spancmp.py`'s rule). Lag counts are deterministic headless counts
(`oracle-aether`, no pacing). The full table with the path, coverage and parallax checks per leg
is `results/final_table.txt`.

## Legs and the probe

`run_probe.py` is new. The perf survey's physics legs scheduled inputs **per video frame**, so a ROM
with different lag took a different path, and a cross-ROM comparison measured two different runs.
This probe keys every input to **logic ticks since the leg started**. It records the player path by
tick, so two ROMs' paths can be compared tick by tick.

- **run**: hold right; jump (C for 16 ticks) when the player first reaches x 1330 and 4620 on the
  ground. Those are Emerald Hill act 1's bridges (object $11 in `s2disasm/level/objects/EHZ_1.bin`).
  The clip carries **no objects**, so each bridge is a gap to jump. The leg also jumps when the
  player's x has not grown for 12 ticks. It runs from spawn to player x 5850.
- **spin**: the same, plus a spindash (down, C x4, release) on the ground at x 1700 and 3200.
- **DEBUG shape**: the probe presses B first to leave free flight, then settles for 120 frames.
- **fly** legs: held directions in DEBUG free flight.
- **Canonical run**: right, with C held for ticks [0,10) of every 45, for 1800 frames.

**Paths agree across ROMs.** Tick counts are equal on every leg. The camera agrees at every tick of
every DEBUG run leg. A handful of ticks per leg read a player position 1 to 7 px off, and the next
tick agrees exactly (listed in the table). That is the snapshot landing mid-tick, because
`run_frames` stops at a fixed cycle, not at VBlank. The 2026-09-25 bisect's `pathcmp` saw the same
thing. Fly-leg cameras differ at 1 tick in about 700 to 1100.

**Spawn to the tunnel is not reachable by a script, and possibly not by the owner.**
- Past x 5850 the running route drops into the pit under the missing bridge at x 6040 (y ~950). No
  drive tried got out: jump when stuck, extra jump triggers at 5200 and 5450, or a spindash.
- Warping to (6300, 690) above it, the player then oscillates between x 6530 and 6870 in front of a
  spring route (object $41 at 6472), and never passes.

So the run legs cover **spawn to x 5850, 53% of Emerald Hill**, all of it inside the band the owner
plays. The fly legs cover the whole act. Bouncing in that dead end cost **98 lag frames in 1500**
(DEBUG). This is the perf survey's candidate 7, the thrash lead, reproduced on the owner's act. It
was measured once and is not diagnosed.

## Where the lag was (before, `366b777c`)

By player x (release run, lag per 1024 px): `0:2 1024:15 2048:4 3072:3 4096:7 5120:0`. Half the lag
is in x 1024 to 2047: the first hills and the first bridge, where the camera moves vertically the
most. DEBUG run: `0:2 1024:16 2048:6 3072:5 4096:8 5120:2`.

**Per overrunning tick** (`pertick.py`, DEBUG run, 36 lag windows). Each lag window is 3 frames
around one lag frame, and each holds exactly one main-loop tick (checked: one `Parallax_Update` call
per window). The control column is 40 quiet windows, 80 ticks.

| routine (inclusive, cycles per tick) | overrunning tick | ordinary tick |
|---|---|---|
| `Tile_Cache_Fill` | **98,568** | 14,276 |
| . `TileCache_DecompressBlock` | **61,166 (5.17 calls)** | 2,137 (0.33) |
| . `TileCache_FillRow` | 52,609 (1.50 calls) | 1,198 |
| . `TileCache_FillColumn` | 28,143 | 9,124 |
| . `PageCache_PatchRun_Seq` | 13,804 | 572 |
| `Parallax_Update` | 15,517 | 15,519 |
| `RunObjects` | 13,071 | 13,597 |
| `Section_UpdateColumns` | 6,921 | 6,656 |
| `Render_Sprites` | 5,085 | 5,778 |
| `Canopy_Probe` (DEBUG only) | 4,026 | 4,026 |
| `PageCache_Audit` slices (DEBUG only) | 3,483 | 3,015 |

- Decodes per lag window: **6 in 22 of 36** (the budget's ceiling), 5 in 4, 4 in 4, 3 in 6.
- Decodes per control window: 0 in 29 of 40.
- Over the whole leg (whole-leg segment profile, measured on the pre-rebase base `f2926873`) the
  fill made 620 decodes in 1201 ticks. Of these, 384 were speculative and
  236 were demand decodes: 138 from `FillRow`, over only 120 row fills, and 98 from `FillColumn`.
  The row prefetch rarely lands ahead of a hill's camera motion. The burst is the demand fill
  catching up in one tick.

**DEBUG-only share, plainly: small, and not the cause.** The release shape lagged 31 on the same
run where DEBUG lagged 39, so the release shape had the same problem. Upper bounds from stubbing each
routine to `rts` on the run leg:

| DEBUG run leg, stubbed routine | before `77e017db` | after `08cad480` |
|---|---|---|
| nothing | 39 | 6 |
| `Canopy_Probe` | 34 | 5 |
| `PageCache_Audit` | 39 | 6 |
| both | 33 | 5 |
| `Parallax_Update` (the whole routine; the picture stops scrolling) | 29 | 1 |

`Canopy_Probe` is 4,026 cycles every tick and worth about 5 frames before and 1 after. It stays
armed; that is the owner's call. The amortised audit is worth nothing on this leg. Asserts are not
separable by stubbing. The only DEBUG-only rows visible in the profile are the object-loop assert
wrapper's call sites, whose self cost is under 10 cycles per tick.

## Fix 1: the soft decompress budget

`BLOCK_DECOMP_BUDGET` (6) bounds how many blocks one tick may decode. `TileCache_FillRow` and
`FillColumn` resume a partial row or column next tick. The cache margin, 16 rows and 20 columns
beyond the screen, is the slack a deferred decode lands in.

**A lower fixed budget fixed the run and broke flight.** Measured on the pre-rebase base
`f2926873`, DEBUG:

| budget | run leg | fly diagonal | worst undrawn visible rows (bottom) |
|---|---|---|---|
| 6 (shipped) | 40 | 37 | 2 |
| 4 | 34 | 37 | 2 |
| 3 | 24 | **72** | **62** |
| 2 | 14 | **81** | **90** |
| 1 | 8 | **148** | **268** |

The fill has no catch-up headroom (`VFILL_ROWS_PER_FRAME`'s note: 2 rows per tick equals the
camera's 16 px cap). Under sustained diagonal flight a deferred row is never recovered, the backlog
reaches the screen, and the lag grows with it.

**The lead test.** Before resetting the allowance, `Tile_Cache_Fill` measures how far the FILLED
cache leads the screen on each side:

- **rows**: bottom = `Cache_Bottom_Row - (camY + SECTION_V_REACH_PX)/8`; top = `camY/8 -
  Cache_Top_Row`;
- **columns**: right = `Cache_Head_Col - (camX + SECTION_H_REACH_PX)/8`; left = `camX/8 -
  Cache_Left_Col`.

Each fill loop commits its edge word before filling. So the one pending partial row
(`Cache_Fill_RowResume_Row`) and the one pending column (`Cache_Fill_Resume_Col`) are cut out of the
extent on the side they lie on. A pending row or column on screen forces the hard budget.

The allowance is `BLOCK_DECOMP_SOFT` when every side leads by at least `BLOCK_FILL_LEAD_ROWS` = 8
(`TILE_CACHE_MARGIN_V`/2) and `BLOCK_FILL_LEAD_COLS` = 10 (`TILE_CACHE_MARGIN_H`/2). Otherwise it is
the full budget. The check costs about 150 cycles a tick.

- The camera moves at most 2 rows or 2 columns a tick, and the lead is re-tested every tick. So a
  deferral costs at most that much lead before the hard budget, the old behaviour, returns.
- Near an act edge the lead is short by construction, so the fill stays on the hard budget there.
  That is conservative.
- The prefetch tail draws from the same allowance, so a soft tick speculates at most once. No fly
  leg measured a regression from that (table below).

**Choosing the numbers** (pre-rebase base, DEBUG; run leg / fly diagonal; base 40 / 37):

| soft | lead rows/cols | run | fly diag |
|---|---|---|---|
| 2 | 8 / 10 | 15 | 40 |
| 3 | 8 / 10 | 24 | 38 |
| 2 | 12 / 15 | 19 | 39 |
| 1 | 12 / 15 | 16 | 38 |
| **1** | **8 / 10** | **8** | **37** |

Fly right and fly down stayed 0 in every variant measured. The response is not monotone in the soft
value; I did not model why, and picked the measured best.

**Picture check (coverage).** On every leg of both builds the probe reads the streamer's four
written edges (`Section_{Right,Left}_Col_Written`, `Section_{Bottom,Top}_Row_Written`) after each
frame. It reports how many **visible** tile columns and rows were not yet drawn. A value above 0 is
a hole on screen.

- The shipped ROM shows up to 2 on the leading edges in free flight. That is the draw lag at a
  mid-frame sample, and it is the baseline.
- After the change, the worst value on every axis of every leg is **equal or lower** (it went from 1
  to 0 on the DEBUG runs).
- The fixed budget 3 showed 62 there. The instrument sees the failure this design avoids.

The existing `tools/tile_cache_fill_gate.py` (recorded columns match the cache) runs as a child of
`tools/effects_gates.py`; that ritual's result for this parcel is in DEFERRED_WORK's
PERF-EHZ-RUN-LAG entry.

**Ensures, red-first.** Each mutation was made on disk and built with FAST DEBUG. The file was then
restored from HEAD and the restored tree built with rc 0 (`results/redfirst_ensures.txt`).

| mutation | result |
|---|---|
| `BLOCK_DECOMP_SOFT` = 0 | refused, rc 1, own message |
| `BLOCK_DECOMP_SOFT` = 7 | refused, rc 1, own message |
| `BLOCK_FILL_LEAD_ROWS` = 2 | refused, rc 1, own message |
| `BLOCK_FILL_LEAD_ROWS` = 16 | refused, rc 1, own message |
| `BLOCK_FILL_LEAD_COLS` = 2 | refused, rc 1, own message |
| `BLOCK_FILL_LEAD_COLS` = 20 | refused, rc 1, own message |

## Fix 2: the curve line loop (parallax)

**The brief's prime suspect, priced.** On the run leg, `Parallax_Update` is 15.5k cycles per tick. A
decomposition build (tail calls turned into calls, measurement only, not landed) split it as follows:

| part | cycles per tick |
|---|---|
| `Parallax_Fill_PerLine` | 7.8k |
| `Parallax_Step4_Fill` self | 3.7k |
| `Parallax_Update` self | 1.9k |
| `Decode_Factor_A`/`_B` (7 bands) | 1.4k |
| `Parallax_Step5_Vscroll` self | 0.4k |

Of the fill, EHZ's 80 curve lines were about 2.7k at 34 cycles a line. The flat lines are already
an 8x unrolled `move.l` at about 13 cycles each, so they have no headroom. The ripple band (21 lines,
about 45 cycles each) saves about 4 cycles a line packed, which is not worth a change.

**The new loop.**
- The FG word rides in `d1`'s high half: `swap d0 / swap d1 / move.w d0,d1 / swap d1`, once per band.
- A line is `move.l d1,(a4)+ / add.w d3,d6 / addx.w d2,d1`, 8x unrolled with a remainder tail.
- Cost: 21.25 cycles a line in whole groups, 30 in the 0-7-line tail. The saving is about 1.0k
  cycles per tick with EHZ's curve on screen.
- `addx.w` touches only the low word, so the FG half survives. The values, their order and the
  carry parked in `Parallax_Curve_Carry` are the one-line loop's.
- A computed-entry (Duff) first cut was **refused by the contract closure**. `sigil build --report
  contracts` reported `[proc.clobber-undeclared] Parallax_Fill_PerLine a0` and `d7`: the closure
  reads a computed `jmp` as leaving the proc past its `preserves(a0/d7)` restore, with or without a
  `targets(...)` clause. The shipped shape is the house's own unroll-plus-tail shape (`.lp_flat`).

**What it bought** (pre-rebase base, the two changes separated):

| leg | soft budget alone | + curve loop |
|---|---|---|
| DEBUG run | 8 | 6 |
| fly-diagonal EHZ band | 33 | 31 |
| (stubbing all of parallax on the after build) | | run 1 |

What is left of parallax is mostly per-band work in the 7-band record (Step 4, the factor decodes,
the per-band dispatch).

**Picture identity (the parallax output).**

1. **On the running machine.** On every frame that ends one on-time tick, the probe reads the whole
   `Hscroll_Buffer` (224 lines, FG and BG words), `Parallax_Vscroll_Column_Buf` (the VSRAM column
   image) and `Vscroll_Factor`, keyed by tick. `dumpcmp.py` then compares two ROMs at every tick
   whose camera agrees:

   | build pair | leg | ticks compared | ticks that differ |
   |---|---|---|---|
   | before vs after | release run | 1,183 | **0** |
   | before vs after | DEBUG run | 1,201 | **0** |
   | before vs after | DEBUG spindash run | 1,243 | **0** |
   | before vs after | S2 clip fly diagonal (whole act, CPZ included) | 1,062 | **0** |
   | before vs after | S2 clip fly right | 1,100 | **0** |
   | before vs after | canonical OJZ, every leg | per leg | **0** |
   | curve loop alone, pre-rebase | DEBUG run | 1,201 | **0** |
   | curve loop alone, pre-rebase | fly diagonal | 1,063 | **0** |

   The one-tick camera-mismatch ticks are counted per leg in `results/final_table.txt` and are
   never compared.

   **The check was red first.** An unroll mutant, line 7's `add.w d3,d6` dropped (built, then the
   file restored from HEAD), differed at 1,188 of 1,201 ticks on the clip run and 682 of 1,063 on
   the diagonal. The canonical mutant differed at 137 of 1,795 run ticks and 174 of 688 diagonal
   ticks, but at **0** of 700 on canonical fly right. That leg never shows a curve, so its identity
   is not evidence.
2. **On the built machine code.** `curve_rom_exact.py` is the 2026-09-25 tool, copied here with its
   interpreter extended by the three new opcodes (`andi.w`, `lsr.w`, `move.l Dn,(An)+`). It runs the
   hoist and the fill block straight out of each ROM image against `base + floor(k*spread/span)`.

   | ROM | exhaustive | split |
   |---|---|---|
   | clip `08cad480` | **0 of 50,400** | **0 of 20,000** |
   | canonical `917d73ff` | **0 of 50,400** | **0 of 20,000** |
   | unroll mutant | 50,173 of 50,400 (RED) | 1,867 of 2,000 (RED) |

## Content options, priced, not done (the owner's look)

Byte patches of the EHZ record on the **after** DEBUG build (`patch_ehz.py`, 2026-09-25):

| option | run leg | fly-diagonal EHZ band |
|---|---|---|
| as built | 6 | 31 / 87 |
| ripple band flat (21 lines, S2's static frame-0 ripple gone) | 6 | 29 / 85 |
| curve flat (EHZ's ground ramp gone, band 144-223 at camX/8) | 6 | 29 / 85 |
| both | 6 | 27 / 83 |

- The fly legs use the survey's `leg_probe.py`, whose band starts one tick earlier than
  `run_probe`'s, so 31 here is 29 in the table at the top.
- **On the run the owner described, neither option buys anything.** They buy 2 to 4 frames only at
  sustained max-diagonal flight. Not recommended; listed so the choice is his.
- Fewer curve lines (S2's hold groups as flat steps) was not measured. It is bounded by the "curve
  flat" row.

## What remains (after)

- **The run legs have 1 (release) to 6 (DEBUG) lag frames left.** The overrunning ticks are now
  **column and row copy** at spindash speed: `TileCache_FillColumn` 50.7k cycles per tick, with
  `PageCache_PatchRun_Col` at 17.7 calls and 23.9k cycles. They hold only one decode each
  (`results/after_debug_spin_pertick.txt`). This is the streaming act's translating copy
  (bounded-direct regime). Resident acts no longer pay it since RESIDENT-PLAIN-COPY.
- **Parallax is still 14.6k per tick.** Stubbing it entirely takes the DEBUG run from 6 to 1, an
  upper bound. The rest is per-band overhead. The survey's candidate 5 (cheaper per-band work) is
  where more would come from; it is not built.
- **The oscillation thrash** at x 6530 to 6870: 98 lag frames in 1500 while bouncing. Not diagnosed.
- **Max-diagonal free flight** is still over budget on every act (ARC-CLOSEOUT): Emerald Hill band
  29/85.

## CRCs (FAST builds; `results/crc_*.txt`)

| ROM | before `366b777c` | after |
|---|---|---|
| `s4.bin` | `699ce90a` / 829,076 | `562a7dbe` / 829,266 |
| `s4.debug.bin` | `9cc47356` / 856,248 | `917d73ff` / 856,446 |
| `s4.s2clip.bin` | `2b825ead` / 928,681 | `9a39a48b` / 928,871 |
| `s4.s2clip.debug.bin` | `77e017db` / 955,668 | `08cad480` / 955,864 |

The full (non-FAST) builds and `landing_build.sh` are recorded in DEFERRED_WORK's entry,
PERF-EHZ-RUN-LAG.

## Method notes

- **No emulator MCP.** Every run is the headless `oracle-aether` subprocess, with sockets under
  `$HOME/ehzlag/sock`, not `/tmp`.
- **Load.** Headless lag counts do not change with host load. Loadavg is recorded per leg in
  `results/legs_*.meta` (4.8 to 7.2).
- **Lag-frame attribution.** `lagwin.py` picks a 3-frame window around each DEBUG lag frame, plus
  40 quiet controls. It re-runs the same deterministic leg and arms the profiler only in those
  windows. `pertick.py` divides by the ticks actually inside each window. The oracle per-frame ring
  carries totals only, so this is how a single tick gets a routine breakdown.
- **Tools.** `run_probe.py`, `lagwin.py`, `pertick.py`, `pathview.py`, `spancmp.py`, `dumpcmp.py`,
  `legtable.py`, `final_legs.sh`, `final_table.py` and `curve_rom_exact.py` are in the directory
  above. The slim leg JSONs (the dump bytes reduced to SHA-1s) are in `results/legs_slim.tar.gz`.
