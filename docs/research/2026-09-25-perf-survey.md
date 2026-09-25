# Perf survey: flying through the acts, looking for lag (2026-09-25)

Research parcel, no engine or game change. The owner asked: *"Next up can you fly through things
and see if you can detect any lag and see if we want to do anything for performance?"* This
report measures lag on the four shapes he can load, finds which routines own the cycles, prices
each candidate fix with a removal probe where one was possible, and ranks them.

**Base:** origin/master `09185beb`, branch `research/perf-survey`. Every ROM below was built in
this worktree with the pinned `SIGIL_BUILD`/`SIGIL_EMIT`. Tools and raw results are in
`docs/research/2026-09-25-perf-survey/`.

## The shortlist (ranked; the reasoning is in "Recommended order")

| # | candidate | measured or estimated gain (lag frames, named leg) | cost | engine / content | canonical bytes | risk |
|---|---|---|---|---|---|---|
| 1 | **Amortise `PageCache_Audit`** (DEBUG only). Today it runs as one 203k to 236k cycle call (1.6 to 1.85 frames) every 128 ticks | MEASURED (stub): canonical fly right 6/364 → **0**/358, down 6/369 → **0**/363, diagonal 49/412 → 44/407. On the clip (with Canopy also off) fly right 16/1014 → **0**/998, down 7/370 → **0**/363 | S | engine (DEBUG) | DEBUG shape only; release unchanged | low: the audit's coverage is kept, only its timing changes |
| 2 | **Cheaper parallax per-line fill**, which matters most for the Sonic 2 EHZ scroll record (15.5k to 17k cyc/tick against OJZ's 9k to 11k) | MEASURED UPPER BOUND (routine removed): clip EHZ-band diagonal 44/100 → 15/71, clip whole diagonal 60 → 29, CPZ fly-down 34 → 27, canonical diagonal 49 → 32. A real optimisation gets some fraction of this. **Which fraction is not measured** | M | engine (the filler) or content (fewer curve lines in the EHZ record) | yes (engine) / clip only (content) | medium: the effects gates cover this code (`tools/effects_gates.py` ritual) |
| 3 | **Resident acts: bake physical tile words at build time and copy without translating.** Removes the per-word translate in `PageCache_PatchRun_Seq/_Col` (about 97 cycles a word on the direct loop) | MEASURED with a stand-in plain-copy loop: canonical diagonal 34/397 → **20**/383, with audit and Canopy off in both. ESTIMATE for release: in the physics fall shaft, Seq+Col cost 18.9k/tick, of which about 14.6k/tick is removable (derivation below) | M-L | engine + level tool | yes (code and act data) | medium: touches the art-pool contract. Streaming acts keep the translating path |
| 4 | **CPZ's general patch loop** (S2CLIP-LAG residue 1). The clip leaves the bounded-direct regime when you fly *down* in Chemical Plant | Leg: CPZ painted rows, fly down, **30/150**. `PatchRun_Seq` costs 2.95k per call there against 1.56k on the direct loop, which is **+15.6k cyc/tick**. ESTIMATE: about 12 to 18 of the 30 frames (derivation below) | L (its own design parcel) | engine | no, until a canonical act streams | medium to high |
| 5 | **Disarm `Canopy_Probe` by default** (DEBUG only; 4.0k to 4.1k cyc every tick) | MEASURED (stub): canonical diagonal 49/412 → 41/404 | S | engine (DEBUG) | DEBUG only | low, but it is the owner's call: it is a live canopy-gap instrument (DEFERRED_WORK "CANOPY GAP" items) |
| 6 | **A lag-leg lane over a clip shape** (S2CLIP-LAG residue 3). Gain: none. It is the regression net the streaming path lacks | n/a. This survey shows why it is needed: the EHZ-band diagonal moved from the post-fix record of 26/82 to **44/100** with no lane noticing | S-M | tooling | no | low |
| 7 | **Investigate a tile-cache thrash when the camera oscillates** (an unverified lead) | Release physics run, stuck bouncing at camera x ~1000 to 1070: 24/600, with `TileCache_DecompressBlock` at 0.68 calls/tick while the camera barely moves. Flying right at full speed makes 0.43 calls/tick. NOT VERIFIED; no gain claimed | S to diagnose | engine | n/a | n/a |

"Upper bound" means the routine was replaced by `rts`. A real fix keeps the work, so it buys at
most that much. The stub changes what the game does (stubbed parallax stops scrolling), and it
answers only "how many lag frames is this routine worth on this leg".

## ROMs measured

| shape | file | CRC32 | bytes | notes |
|---|---|---|---|---|
| canonical release | `s4.bin` | `950f7d28` | 822,103 | changed since the S2CLIP-LAG study's `6d1af7a3`, but lag is identical on every shared leg (below) |
| canonical DEBUG | `s4.debug.bin` | `a0e248e7` | 848,768 | was `62238a15`; same lag on every shared leg |
| clip release | `s4.s2clip.bin` | `aa258967` | 921,571 | byte-identical to the main checkout's file |
| clip DEBUG | `s4.s2clip.debug.bin` | `c7d567ab` | 948,046 | byte-identical to the main checkout's file |

The clip builds first REFUSED in this worktree: the donor trees `games/sonic4/data/donors/`
are gitignored and absent in a fresh worktree. I ran `python3 tools/s2_zone_convert.py convert
s2disasm@EHZ` and `@CPZ` as the refusal instructed (0 differing cells), then rebuilt. The CRC
match with the main checkout shows the conversion reproduced the owner's data.

Residency after boot (`residency_read.py`): canonical has 10 pool pages, fully resident, direct
map `$FF`. The clip now has **17** pool pages against `PAGE_FRAMES` = 12 (it was 14 at the
S2CLIP-LAG study), is not resident, and boots in the bounded-direct regime (`Direct_Map` = 1).
Read at the end of each leg, the clip **stays bounded** on fly right, the diagonal and the physics
run, and **drops to the general loop (0)** on the new fly-down-in-CPZ leg.

## Lag table (headless, deterministic)

Figures are `lag frames / video frames while the camera moves`. A lag frame is a VBlank that ran
`VInt_Lag` because the main loop was late: Σ dFrame_Counter − Σ dLogic_Tick, which on every DEBUG
leg equals the `Lag_Frame_Count` delta. **Lag counts are deterministic.** Reruns of the same ROM
and drive gave the same numbers: the prior harness (r4) and this survey's probe (s1/s3) agree on
every fly leg. Loadavg is the 1-minute figure at the leg's start and end. Loadavg changes
wall-clock only, never these counts.

"NEW" marks a leg the S2CLIP-LAG study did not have.

### Canonical OJZ act 1

| leg | `s4.debug.bin` a0e248e7 | `s4.bin` 950f7d28 | loadavg |
|---|---|---|---|
| fly right | 6/364 (all 6 are audit pairs) | n/a (no free flight) | 11.9 → 13.3 |
| fly down | 6/369 (cam y < 1024: 2/58) | n/a | 13.3 → 15.1 |
| fly diagonal (max) | **49/412** (y < 1024: 17/73) | n/a | 15.1 → 17.0 |
| physics run, prior drive (B at start, C every 45) | 66/1,179 | 33/1,161 | 19.4 → 17.1 / 16.2 → 15.4 |
| physics run, this probe's drive (no B in release) | 66/1,179 | 55/1,838 (stuck bouncing ~600 frames at x ~1030) | 17.0 → 20.1 / 21.9 → 26.5 |
| NEW spindash every 150 frames | 9/355 (stuck at x 983) | **21/1,183** (whole act) | 20.1 → 21.9 / 26.5 → 25.9 |

The DEBUG legs are byte-for-byte the prior study's figures (6/364, 6/369, 49/412, 66/1,179)
and the release physics leg too (33/1,161), though both canonical CRCs have changed since.

**Where the release lag falls.** Physics run, this drive: the fall down the shaft (camera y 1136
→ 4616, rows 1250 to 1500) is **17/250**, with work at 0.776 frames/tick. `Tile_Cache_Fill` is
47.5k/tick there (`TileCache_FillRow` 31.8k at 1.89 rows/tick, `PageCache_PatchRun_Seq` 14.4k)
and `Parallax_Update` 12.8k. Bouncing in place at x ~1030 (rows 400 to 1000) is **24/600** at
0.467 frames/tick average. That lag is spiky, and the block decompressor runs there (see
candidate 7).

### Sonic 2 clip act (`s2_ehz_cpz`)

| leg | `s4.s2clip.debug.bin` c7d567ab | `s4.s2clip.bin` aa258967 |
|---|---|---|
| fly right (whole act, to x 16064) | 16/1,014 (all audit pairs: 2 every 128 ticks) | n/a |
| fly down (x 96) | 7/370; EHZ band y < 1024: 3/59 | n/a |
| fly diagonal | 60/1,058; **EHZ band y < 1024: 44/100** | n/a |
| physics run | 71/2,839 | 22/2,790 (prior drive: 18/2,783) |
| NEW spindash | 32/355 (stuck at x 1367) | 16/351 (stuck at x 1367) |
| NEW fly right to x 14400, then **down through CPZ** | after the turn 34/459; **CPZ painted rows (to y ~1800): 30/150** | n/a |
| NEW fly right to x 14400, then **diagonal through CPZ** | after the turn 70/495 | n/a |
| NEW EHZ→CPZ tunnel at speed (`tunnel_run_witness.py`, 6 runs) | 6/6 crossed, lag 3/3/0/3/0/0 per run (right 0/$600/$1000, then left), 0 faults | n/a |

Against the S2CLIP-LAG post-fix record (DEFERRED_WORK): fly down EHZ band 3/59 **same**; physics
release 14/2,437 then, 18/2,783 now (prior drive; the act is wider); **diagonal EHZ band 26/82
then, 44/100 now: worse.** See candidate 2 for what the profile shows about the difference.

Host side (wall-clock, NOT deterministic): the prior harness's headless `run_frames(1800)`
phase ran at **153.5 to 403.4 fps** (2.6× to 6.7× real time) across the ten r4 legs at loadavg
10 to 22. The lowest figure was taken at loadavg 11.6 → 18.4, with other load on the
box (this worktree's builds had finished). The headless core keeps real time on this box. The player was not
measured (see the last section).

## Where the cycles go (whole-leg profiles, cycles per logic tick)

These come from the oracle exact per-invocation profiler, armed over the whole leg with the
callers lens (`leg_probe.py --profile`). The completeness identity remainder is **0** on every
profile, with nothing truncated. 127,840 cycles is one NTSC video frame. "Work" is the sample
minus `VSync_Wait`, inclusive.

| routine (call site) | canon diag | canon down | release fall window | clip EHZ-diag window | clip CPZ-down band |
|---|---|---|---|---|---|
| work, frames/tick | 0.851 | 0.568 | 0.776 | 1.165 | 0.872 |
| `Tile_Cache_Fill` (← `GameState_OJZScroll_Update`) | 55.1k | 29.3k | 47.5k | 82.6k | 70.5k |
| `TileCache_FillRow` (← `Tile_Cache_Fill`) | 28.7k | 25.0k | 31.8k | 41.3k | 55.5k |
| `PageCache_PatchRun_Seq` (← `TileCache_FillRow`) | 13.7k (1.37k/call) | 13.3k (1.56k/call) | 14.4k | 19.6k | **33.2k (2.95k/call, general loop)** |
| `PageCache_PatchRun_Col` (← `TileCache_CopyBlockColumn`) | 10.5k | n/a | 4.5k | 12.4k | n/a |
| `TileCache_DecompressBlock` → `S4LZ_DecompressDict` | 4.1k → 3.1k | 1.8k → 1.3k | 6.5k → 4.9k | 21.1k → 19.5k | 19.2k → 17.8k (~11.8k per block) |
| `Parallax_Update` (← `GameState_OJZScroll_Update`) | 11.6k | 9.4k | 12.8k | **16.7k** | 8.3k |
| `PageCache_Prefetch` scan (← `PageIn_Process` ← `VSync_Wait`, the idle slot) | ~0 | ~0 | ~0 | 13.2k | 18.7k |
| `Canopy_Probe` (← `Section_UpdateColumns`, DEBUG) | 4.0k | 4.0k | 0 (release) | 4.0k | 4.0k |
| `PageCache_Audit` (← `GameState_OJZScroll_Update`, DEBUG, 1 call per 128 ticks) | 236k per call | 236k per call | 0 | 203k per call | 221k per call |
| `RunObjects` | 2.9k | 2.8k | 10.5k | 8.6k | 2.1k |

Constant costs on every leg: `VBlank_Handler` 9k to 12k (inside it, `Process_DMA_Critical`
about 2.6k), `Render_Sprites` 2.6k to 6.9k, `Player_Main` 8k to 10k in physics play,
`Section_UpdateColumns` 3k to 13k. Full per-leg top-30 tables with callers are in
`results/s1_canonical_profiled.txt`, `results/s3_clip_profiled.txt` and `results/w_*.txt`.

## The candidates, with how each gain was derived

**1. `PageCache_Audit` pairs (DEBUG).** Every 128 ticks one call walks the pool and the
nametable: **235,862** cycles per call (canonical fly right; 4 calls, 943,450 total), 202,859 on
the clip. Each call is two lag frames on every leg, every act, and it is the whole DEBUG baseline
on straight flight. Stubbing it (`results/st_audit.txt`): fly right 6 → 0 and down 6 → 0. The
DEBUG shape is what the owner flies, so this is a visible 2-frame hitch every ~2.1 s.

Fix shape (not designed here): audit a slice per tick (for example 1/128 of the pages or rows),
or run it only in the idle slot. The engine already banks idle-time work
(`PageIn_Process` from `VSync_Wait`).

**2. Parallax.** `Parallax_Update` is 9k to 11k/tick on OJZ and **15.5k to 17k/tick in Emerald
Hill** on the clip. In the S2CLIP-LAG study's matching window it was 8.7k. The clip manifest says
that since "B-2" each zone's preset binds its own Sonic 2 scroll record. EHZ's is the per-line
one. The per-line curve cost was measured before at 40.75 cyc/line
(`docs/benchmarks/scanline-p3/CURVES.md`).

Removal probe (`results/st_c_parallax.txt`, `st_parallax.txt`): clip EHZ-band diagonal 44/100 →
15/71, clip whole diagonal 60 → 29, CPZ down after the turn 34 → 27, canonical diagonal 49 → 32.
The EHZ-band number now **beats** the post-fix record (26/82), which is consistent with B-2's
parallax being the reason the band got worse since the fix. That is **not bisected**: the tunnel,
the CPZ widening and 14 → 17 pages landed in the same window. A realistic fix is a faster
per-line filler, or fewer curve lines in the EHZ record. Its fraction of the upper bound is not
measured.

**3. Translate-free copy for resident acts.** On a fully resident act every nametable word still
goes through the page map in `PageCache_PatchRun_Seq/_Col` (`pc_patch_run_direct`). Measured cost:
canonical down, 13.3k/tick over 8.55 runs of about 16 words, so **~97 cycles a word**. I replaced
both entries with a plain copy loop (Seq: `move.w (a0)+,(a1)+` / `dbf`; Col: the same with the
32/160-byte strides): Seq `5340 32d8 51c8fffc 4e75`, Col `5340 3290 41e80020 43e900a0
51c8fff4 4e75`, crc `e206b300`. The art is then
wrong on screen (local words land untranslated), so it prices the proposed implementation, not
the picture. Canonical diagonal, with audit and Canopy off in both: **34/397 → 20/383**. Fly
right and down stayed 0.

The real fix: for an act that is fully resident (`Direct_Map` `$FF`), have the level tool emit
blocks whose words are already physical, and select the plain copy per act. Streaming acts keep
the translating loops.

ESTIMATE for release (release has no free flight, and physics legs cannot be compared across
ROMs; see the last section): in the fall window Seq+Col is 18.9k/tick. At the measured ~97 cycles
a word against ~22 for the naive copy, **~14.6k/tick** is removable, which takes work from 0.776
to ~0.66 frames/tick. How many of that window's 17 lag frames it removes is not measured.

**4. CPZ general loop (residue 1, now measured on a leg).** Flying down through Chemical Plant's
painted rows: 30/150. `PageCache_EndBoundedRegime` fires inside that window (0.01 calls/tick).
From then on `PatchRun_Seq` costs **2.95k per call** (general loop: page-table translate plus
refcount per word) against 1.56k on canonical's direct loop, **+15.6k/tick** at 11.3 calls/tick.
In the same window the prefetch scan is 18.7k/tick in the idle slot, and S4LZ block decode is
17.8k/tick (CPZ blocks ~11.8k each). Stubbing prefetch made this leg worse (34 → 37 after the
turn), so the scan is paying its way.

ESTIMATE of the gain from giving the general loop direct-loop cost: the window's total is 158.9k
cycles/tick (1.243 frames). Minus 15.6k gives 143.3k (1.121), which over its 120 ticks is ~14.5
lag frames instead of 30. This assumes lag scales with the mean, which the lumpy idle spin
(`VSync_Wait` self 19.5k/tick) says it does not exactly. I give it as **~12 to 18 of 30**. The
levers DEFERRED_WORK names (idle-time mark-sweep liveness, or a per-section translated map) are
unchanged and still unmeasured.

**5. `Canopy_Probe` (DEBUG).** 4,026 to 4,139 cycles every tick, which matches its own derived
prediction of 4,073. Stub: canonical diagonal 49 → 41; fly right and down unchanged. It is an
armed instrument for the canopy-gap hunt ("A CAUSE WAS FOUND … THE SEARCH BEYOND IT IS CLEAN",
2026-09-03). Whether to keep it armed in every DEBUG build is the owner's call.

**6. Regression net.** The clip's EHZ-band diagonal went from 26/82 (post-fix record) to 44/100
and nothing flagged it. The canonical shapes never leave the resident early-outs, so
`landing_build.sh` and the nightly cannot see the streaming path. `leg_probe.py` over a clip
DEBUG shape (fly diagonal plus CPZ down), with a committed ceiling, would be the net. It is not
built here. Any lane must be proven red-first.

**7. Oscillation thrash (lead only).** In the release physics run the drive got stuck bouncing at
camera x ~1000 to 1070, y ~355 to 413, for about 600 frames. `TileCache_DecompressBlock` ran 0.68
times per tick there (callers: `Tile_Cache_Fill` speculative sites 2.8k/tick, `FillRow` 1.8k,
`FillColumn` 1.5k), against 0.43 per tick flying right at 16 px/tick. With 16 round-robin staging
slots and a cache window that slides with the camera, an oscillating camera plausibly re-stages
the same blocks. **Not verified**: I have no per-tick attribution (see below). A player
repeatedly jumping at a wall is a plausible but uncommon state.

## Recommended order, and why

1. **Audit amortise (1), with Canopy (5) decided in the same breath.** Smallest cost, zero
   release risk. It removes the one hitch the owner meets on *every* act in the shape he flies:
   straight flight goes to 0 lag on both acts. Decide Canopy at the same time, because both are
   "what DEBUG instruments cost" and he can judge them together.
2. **Parallax (2).** It is the biggest single measured item on the content he flew most recently
   (EHZ band 44 → 15 upper bound). It is the most likely reason that band regressed since the lag
   fix, and it also helps OJZ (49 → 32 upper bound). Start by pricing a faster per-line filler
   against the S2 EHZ record's line count, because the realistic fraction is unmeasured.
3. **Translate-free resident copy (3).** It has the biggest measured gain *with a realistic
   replacement* on canonical (diagonal 34 → 20). It moves canonical bytes and touches the
   art-pool contract, so it wants a design pass. It is also the only candidate that speeds the
   release fall shaft (estimate only).
4. **Regression lane (6)** before or with (4). Streaming work without a net is how the band
   regression went unseen.
5. **CPZ general loop (4).** Real (30/150 flying down in CPZ). It is L-sized and only hurts
   streaming acts. It is the mega-act goal's problem more than today's.
6. **Thrash lead (7):** diagnose only if the owner reports lag while jumping in place.

With 1, 3 and 2 (as its full removal) stacked, the canonical max diagonal goes 49 → 34 → 20 →
**11/374** (`results/st_plaincopy_par.txt`). The remainder is the known max-diagonal fill cost
(ARC-CLOSEOUT).

## What I could NOT measure (not zero, not measured)

- **The owner's window / host-side player.** No `mcp__oracle__*`, and his process was not
  touched. Only the headless core was timed (above). The S2CLIP-LAG open item (his player thread
  at 95.9% of a core) is unchanged. **Tag for controller.**
- **Any on-screen look.** Pixels are not a gate here. Whether a hitch is *visible*, and how the
  EHZ/CPZ flights look, is the owner's look. **Tag for controller.**
- **"Many objects on screen."** No shipped act has one: OJZ act 1 has 11 objects (8 in section 0),
  and the clip carries none of Chemical Plant's objects. `Spring_Main` appears (up to 6.4
  calls/tick), which is the most any leg saw. A stress leg needs content that does not exist.
- **Physics legs across stub ROMs.** Inputs are scheduled per *video* frame, so when lag changes,
  the player's path changes. The audit-stub physics run got stuck at x 1074 and ran 3,000 frames.
  Only fly legs (camera path fixed by the input) are compared across ROMs. So **every release
  gain in this report is an estimate.** Release has no free flight.
- **Spindash legs ran short.** The spin drive gets stuck at x 983 (canonical DEBUG) and x 1367
  (clip, both shapes) within ~350 frames. Only release canonical spun through the whole act
  (21/1,183).
- **Per-lag-frame attribution.** The profiler's per-frame ring carries totals only, and a
  one-frame sample holds zero whole frames (tried: every `sampleCycles` was 0, so the tool was
  reverted, not kept). Hotspots are window or leg averages. Spikes are inferred.
- **Bisecting the EHZ-band regression** (26/82 → 44/100): each clip build is ~6 min plus a donor
  convert. The profile points at B-2 parallax, which is consistent with the parallax-stub result,
  but it is not proven.
- **The realistic fraction** of the parallax upper bound, and the **CPZ general-loop gain**:
  estimates above, labelled.
- **The thrash lead:** not verified.

## Method and tools (all in `docs/research/2026-09-25-perf-survey/`)

- `leg_probe.py` imports the S2CLIP-LAG study's transport and counters
  (`lag_flythrough_probe.py`: `Server`, `rd`, `syms`, `snap`, `summarise`) and adds:
  - a spindash drive;
  - two-phase legs (`--then-dirs/--then-at-x`);
  - whole-leg or windowed profiling with the callers lens;
  - `--read-at-end` for RAM bytes such as `PageCache_Direct_Map`;
  - a server log.

  One transport defect was found while building it. The Python Aether client reads replies with
  `asyncio` `readline()`, whose 64 KiB default line limit a whole-leg profile reply with callers
  exceeds. The client then reports "bus connection closed". The probe raises the reader limit.
  **This is worth a fix in `empyrean/clients/python/aether.py`** (cross-repo; not touched here).
- `run_survey.sh` (profiled leg sets `canon` / `clip`), `stub_legs.sh` (unprofiled legs on one
  ROM), and `stub_rom.py` (writes `rts` or a hand-assembled body at a `.lst` label into a scratch
  copy, refusing unknown or ambiguous labels and bodies that overrun the next label). Every run
  wrote a `.meta` with each leg's rc and loadavg and a `finished=<n>` stamp. All are in `results/`
  and every stamp equals its leg count. `summarise_survey.py` prints DID NOT RUN for a missing
  leg.
- The prior harness `docs/research/2026-09-25-s4-lag/run_legs.sh` was rerun unchanged on the
  four ROMs (`results/r4.meta`, `finished=10`, `results/r4_prior_harness_rerun.txt`). Note: that
  script is committed without the execute bit, so it runs as `bash run_legs.sh`.
- `.pyc` caches were cleared before measuring. One headless emulator ran at a time, and no
  emulator MCP tool was used.
- Raw per-frame rows and profiles for every leg: `results/leg_json.tar.gz`.
