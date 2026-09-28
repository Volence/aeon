# Parallax per-band overhead (2026-09-28, PERF-PARALLAX-PERBAND)

The target was `docs/DEFERRED_WORK.md`, PERF-EHZ-RUN-LAG open item 4: "Parallax is still 14.6k per
tick in EHZ, mostly per-band work for the 7-band record." The per-line curve loop was already
packed and unrolled by that parcel, so this one went after the per-band part.

Branch `perf/parallax-perband`, based on `origin/master` `3db049cd`. Tools and raw results:
`docs/research/2026-09-28-parallax-perband/`.

## The answer

- **Parallax is 18% cheaper on every leg, and its output is byte-identical.** `Parallax_Update`
  (inclusive, the whole pipeline) went from 14,461 to 11,814 cycles a tick on the clip's EHZ
  DEBUG run, and from 10,117 to 8,270 on the canonical OJZ DEBUG run.
- **Most of the saving is one change.** Step 4a rebuilt the rotated shadow band view every tick.
  That view depends only on the config's ROM bytes and `Vscroll_BG & 511`, and Emerald Hill is
  vertically locked. It is now rebuilt only when that pair changes: 2,617 -> 430 cycles a tick
  on EHZ.
- **The lag frames the owner feels while running did not move** (DEBUG run 6 -> 6, release 0 -> 0).
  The upper bound says why: removing Step 5, Step 4 and the fill altogether, 8.6k more a tick,
  takes the DEBUG run to 0. So each of the six overrunning ticks is over by more than the 2.65k
  saved here. The fly-diagonal EHZ band did gain: 18 / 74 -> 16 / 72.
- **One lever is blocked by sigil, not by design.** Inlining `Decode_Factor_A/_B` (about 0.5k
  cycles a tick on EHZ) makes two rows of sigil's frozen contract-closure baseline stop firing,
  and the build fails. Measured, below.

## Referents

Every figure is from a FAST build of the named tree. The emulator is the headless `oracle-aether`
subprocess (`legs.sh`, which drives this directory's copy of the 2026-09-27 `ehz_run_probe.py`). It
has no pacing, so lag counts are deterministic. The profiler is armed with the callers lens and
re-armed per 1024 px of camera x. The oracle binary is
`/home/volence/sonic_hacks/oracle/target/release/oracle-aether` (oracle `5cc841f7`).

| tree | `s4.bin` | `s4.debug.bin` | `s4.s2clip.bin` | `s4.s2clip.debug.bin` |
|---|---|---|---|---|
| base `3db049cd` | `d2c5842a` / 829,987 | `1000eded` / 856,982 | `69873061` / 929,590 | `69340439` / 956,402 |
| step 1 (Step 4a key) | `8c575974` / 830,143 | `f9ebb328` / 857,142 | `ab90f7a4` / 929,751 | `ee64b808` / 956,564 |
| step 2 (= the branch's code) | `fb86e15e` / 830,169 | `743e3ca2` / 857,170 | `116ab256` / 929,777 | `d7f19db3` / 956,590 |

The legs are PERF-EHZ-RUN-LAG's (`final_legs.sh`, same drives and flags). The one addition is
two ANCHORED legs, which warp into OJZ region 5 (`ParallaxConfig_OJZ_Underwater`, channel-0 world
anchor 2272). There the split is on screen every tick, and none of the old legs held one.

- **Clip run:** spawn to player x 5850, jumping at x 1330 and 4620. It covers 53% of Emerald Hill.
- **Fly legs:** DEBUG free flight.
- **Canonical run:** right, with C held for ticks [0,10) of every 45.
- **Load:** loadavg per leg is in `results/legs_*.meta` (10 to 20). Headless lag counts do not
  depend on host load.

## Where the cycles went (base)

The shipped pipeline is ONE call: Step 3 tail-branches to Step 5, Step 5 to Step 4, and Step 4 to
the fill. The profiler attributes by call, so all of it lands in `Parallax_Update`'s self column.
`decomp.py` is measurement only, never landed. It turns each tail branch into `jbsr` / `rts` and
lifts Step 4a and the curve hoist into their own procs, so each part gets its own row. Every added
call costs 34 cycles, which is included in the figures and not subtracted.

EHZ DEBUG run, cycles per tick (`results/decomp_pxsum.txt`):

| part | base | after (`results/decomp2_pxsum.txt`) |
|---|---|---|
| `Parallax_Fill_PerLine` (lines ~4.95k + per-band dispatch ~1.9k) | 6,887 | 6,748 |
| Step 4a: find k, rotate/copy 7 x 32-byte records, rebase tops | **2,617** | **430** |
| `Parallax_Update` self (config select, reg $0B, the band loop) | 1,910 | 1,622 |
| `Decode_Factor_A` + `_B` (14 calls) | 1,379 | 1,379 |
| curve hoist (2 divides, far-end decode, walk over 7 bands) | 1,003 | 975 |
| `Parallax_Step5_Vscroll` self | 356 | 356 |
| Step 4 rest (4b test, phase advance) | 191 | 191 |

These match the brief's figures from the 2026-09-27 study: Step 4 3.7k is 2.6k + 1.0k + 0.2k here,
and "update + factor decodes 3.3k" is 1.9k + 1.4k.

**Per-tick invariant or dynamic, for EHZ's 7-band record (v_factor 15, a vertically locked plane):**

- **Invariant: the whole shadow record view.** The rotation start k, the rebased tops and every
  copied field depend on (config, `vs`), and `vs` never changes on EHZ. That is the 2.6k.
- **Invariant: each band's loop selection in the fill.** The table pointers, the deform shifts and
  the curve flag are all in the shadow record. Only the phases change. It could be cached under
  the same key, but not in the record format or the RAM layout aurora and the tools read.
  Priced below, not built.
- **Invariant: the per-frame lerp decision.** Snap pending or no transition was tested per band.
  It is now tested once per frame.
- **Dynamic: every factor value.** Both planes' decodes depend on camX, and so does the curve's
  spread and its divides. The curve's on-screen span, the divisor, IS invariant on EHZ (80 lines,
  locked), but it is not invariant in general, and the divide takes both the quotient and the
  remainder of the per-tick spread.
- **Dynamic: the scroll words' rotation into the shadow.** It is cheap: two runs of `move.w (a)+`,
  about 250 cycles for 7 bands.

## How the references do it

- **S.C.E.'s `ApplyDeformation`** (`Engine/Core/Deformation Script.asm:150`) walks a ROM
  band-height list directly. It subtracts each height from the BG camera Y until it reaches the
  first visible band, then fills. There is no copy and no shadow view. The per-band values come
  from a per-zone routine that writes a small `HScroll_table` first.
- **S3K** (for example `HCZ2_Deform`, `sonic3k.asm:106182`) computes those per-band values as a
  fixed-point progression. The camera X is taken to 16.16 once, then for each band group
  `sub.l d1,d0`, one 8-cycle instruction.
- **Neither reference re-derives anything per band that the frame did not change.** That is the
  principle the Step 4a key applies. The progression encoding would replace our two-shift
  factor decode per band. It is a record-format change, so it is priced below and not built.
- **Thunder Force IV's bands are screen-anchored** (ARCH §4.6 "why the search stays a search"), so
  it never seeks at all.

## What changed

1. **Step 4a frame-coherence key** (`engine/level/parallax.emp`, Step 4a banner;
   `engine/ram.emp`). The view is rebuilt only when (config, `vs`) differs from
   `Parallax_Shadow_Key_Config` / `_VS`. The scroll words are re-rotated every tick from the cached
   k. Four clauses keep the cached view exact, and each is written at the code:
   - Only a ROM config is keyed. The address test is below $400000. A RAM config, meaning the
     DEBUG scratch an editor pokes in place or a probe fixture, rebuilds every tick as before.
   - Step 4b's split rewrites the view, so it drops the key. The curve hoist rewrites
     `bc_step` / `bc_frac` every tick for every band that reads them.
   - `Parallax_Init`'s per-act clear zeroes the key.
   - The scroll words are never cached.

   The miss path walks its source cursor instead of re-deriving it per band. The new RAM is
   8 bytes at the tail of `Parallax_State`, and `PARALLAX_STATE_LONGS`' head went 104 -> 112.
2. **Per-band work that was per-frame** (step 2).
   - The snap/transition lerp decision is made once, into bit 31 of d6. The divs.w four-point
     argument is restated for where the test now lives.
   - The scroll cursors step through post-increments on the stores and on the fill's pack,
     where they were separate `addq`s.
   - `adda.l #imm` becomes `lea`.
   - The role-swapped pack is the normal pack plus one `swap`.

## Before / after (base `3db049cd` -> the branch; same tick spans)

`results/cmp_base_s2.txt`, `results/cmp_base_s2_anchor.txt`. Lag is lag / video frames over the
same span of logic ticks.

| leg | lag before | lag after | parallax cyc/tick before -> after | output |
|---|---|---|---|---|
| clip run, release | 0 / 1201 | 0 / 1201 | 14,344 -> 11,697 | 0 of 1,199 ticks differ |
| clip spindash run, release | 1 / 1244 | 1 / 1244 | 14,346 -> 11,699 | 0 of 1,240 |
| **clip run, DEBUG** | **6 / 1207** | **6 / 1207** | **14,461 -> 11,814** | 0 of 1,200 |
| clip spindash run, DEBUG | 5 / 1248 | 5 / 1248 | 14,464 -> 11,816 | 0 of 1,242 |
| clip fly diagonal, DEBUG, whole act | 23 / 1100 | 20 / 1097 | 12,127 -> 10,055 | 0 of 1,077 |
| **clip fly diagonal, EHZ band** (cam y < 1024) | **18 / 74** | **16 / 72** | 14,293 -> 11,679 (segment 0) | (in the row above) |
| clip fly right / down, DEBUG | 0 / 1100, 0 / 400 | 0, 0 | 11,814 -> 9,784 / 14,512 -> 11,858 | 0 of 1,100 / 400 |
| canonical fly diagonal, DEBUG | 12 / 700 | 12 / 700 | 9,727 -> 8,200 | 0 of 688 |
| canonical fly right / down, DEBUG | 0, 0 | 0, 0 | 9,062 -> 7,532 / 9,233 -> 7,751 | 0 of 700 / 700 |
| canonical run, release / DEBUG | 0 / 1800, 0 / 1800 | 0, 0 | 10,000 -> 8,154 / 10,117 -> 8,270 | 0 of 1,800 each |
| canonical anchored region, right / down (DEBUG) | 0 / 60, 0 / 60 | 0, 0 | 14,686 -> 14,314 / 15,352 -> 14,843 | 0 of 60 each |

Step 1 alone: EHZ DEBUG run 14,461 -> 12,274 and canonical 10,117 -> 8,585
(`results/cmp_base_s1.txt`). Step 2 on top: 12,274 -> 11,814 and 8,585 -> 8,270
(`results/cmp_s1_s2.txt`). Both steps are byte-identical against their predecessor on every leg.

- **Why the anchored legs gain little.** The split rewrites the view every tick, so the key never
  holds, and 4a rebuilds (1.4k) exactly as before (`results/decomp2_pxsum.txt`,
  `cdebug_anchor_right`). Only step 2's per-band savings reach it.
- **The upper bound on the run leg.** Parallax_Update returns after its band loop, so Step 5,
  Step 4 and the fill never run and the picture stops (`build_mutant.sh S`,
  `results/cmp_s2_stubT.txt`). The cost falls to 3.2k a tick, 8.6k below the branch. With that:
  - the DEBUG run goes 6 -> 0;
  - the EHZ-band diagonal goes 16 / 72 -> 10 / 66.

  So the run's six overrunning ticks each overrun by more than the 2.65k this parcel removed, and
  by less than the 11.2k the stub removes. Any further parallax saving counts toward that gap.
  The 2026-09-27 study stubbed the WHOLE routine instead. That no longer builds
  (`results/stub_full_refused.txt`): with the decode calls unreachable, sigil's closure baseline
  reports `GONE firings: Parallax_Update @ Decode_Factor_A :: d2 (got 0, want 1)`.

## Correctness

1. **The parallax output on the running machine.** On every frame that ends one on-time tick,
   `ehz_run_probe.py --dump` reads the whole `Hscroll_Buffer`, `Parallax_Vscroll_Column_Buf` and
   `Vscroll_Factor`. `cmptable.py` compares two ROMs at every tick whose camera agrees, which is
   `dumpcmp.py`'s rule. Result: 0 differing ticks on all 14 legs, base -> step 1 -> step 2.
2. **The fixture matrix.** `tools/parallax_hscroll_identity.py --ref <base capture>` on the
   branch's canonical DEBUG gives "OK — every fixture's Hscroll_Buffer is byte-identical to the
   reference" (`results/ident_base.txt`, `results/ident_s2.txt`). Those fixtures are RAM configs,
   so they exercise only the rebuild path.
3. **The cached path, differentially: `tools/parallax_shadow_key_witness.py` (new, wired).** At
   each sampled tick it checkpoints and runs a frame the ROM's way. It then restores, pokes the key
   to 0 to force the rebuild, runs again, and compares the outputs plus the whole shadow arrays.
   Three coverage classes are required to be non-zero:
   - hit: the key was live;
   - vs-moved: `vs` changed under a live key;
   - split: Step 4b split a ROM config's view.

   On the branch (crc `743e3ca2`): exit 0, 180 samples, hit 81, vs-moved 10, split 99, 0 differ.

**Red-first**, on rebuilt ROMs. `build_mutant.sh` keeps each mutation on disk (`results/mutantA.diff`,
`mutantB.diff`) and restores the file from HEAD afterwards:

| mutant | witness | leg dumps |
|---|---|---|
| A: the key ignores `vs` | exit 1, 13 of 180 samples differ | 13 of 688 `cdebug_diag` ticks differ |
| B: the split keeps the key | exit 1, 118 of 180 differ | 112 of 688 `cdebug_diag` + 18 of 60 `cdebug_anchor_right` |

Mutant A is invisible on the clip legs, because both clip zones are vertically locked. It is also
invisible on the anchored-right leg, where `vs` is constant. The canonical diagonal and the
witness's anchor-down leg are the legs that see it.

## Blocked: inlining the factor decodes

`Parallax_Update` calls `Decode_Factor_A` and `_B` once per band each. Inlining both saves the
`jbsr` / `rts` pair (34 cycles) per call and the `d3` stack borrow of a two-term decode. That is
about 7 x 68 + 24 ≈ 0.5k cycles a tick on EHZ. The block is sigil's frozen closure baseline,
`crates/sigil-harness/src/contract_baseline.rs`, which pins two rows:

- `("Parallax_Update", "Decode_Factor_A", "d2")` in `D1C_BASELINE`, all shapes;
- `("Parallax_Update", "Decode_Factor_B", "d2")` in `D1C_DEMO_EXTRA`, demo.

A baseline row that stops firing fails the build as GONE, measured here with the full-routine
stub. So removing the calls needs a paired sigil commit, and this lane does not touch sigil's
tree. Filed as a rider for the sigil lane in DEFERRED_WORK.

## Open, priced, not built

1. **The decode inline** (above): ~0.5k cycles a tick on EHZ. Needs the sigil baseline edit.
2. **A factor PROGRESSION encoding** (S3K's `sub.l` per band). It would replace the per-band
   two-shift decode with one add, about 100 -> 10 cycles a band per plane. It changes the band
   record that `effects_gen` / aurora emit, so a design note comes first. The decode calls are
   pinned anyway.
3. **Caching the fill's per-band loop selection under the same key.** About 80 cycles a band, so
   ~0.5k a tick on EHZ. Recording the selection needs RAM beside the view, and the split path
   would still recompute it.
4. **Keeping the view across an anchored split.** The split mutates the view in place, so an
   anchored region rebuilds every tick (1.4k). A pristine copy plus a split-only rewrite would
   keep the key. That is 528 more bytes of RAM at MAX 16, for OJZ's one anchored region.
5. **The curve hoist's walk over non-curve bands.** About 55 cycles a band, ~0.3k a tick on EHZ.
   The curve bands present under a live key could be remembered.
6. **Flat lines by `movem.l`** (per line, not per band). About 4 cycles a line over EHZ's ~123 flat
   lines is ~0.5k, less the register setup. The fill has few free registers.
7. **`[parallax.cost_model]` in `tools/effects_budget_model.toml` is now stale.** Its rows are a
   property of the walker they were fitted on ("the next parcel that touches a Parallax_*
   routine re-measures"). Every band term moved down. It is not gated anywhere (its fitting
   probe's `main()` runs nowhere, per the keepalive census). It was not re-fitted here.

## Tools

In this directory:

- `build4.sh`: the four FAST shapes of the working tree.
- `build_decomp.sh` + `decomp.py`: the decomposition build.
- `build_mutant.sh`: mutants A and B and the stub S.
- `legs.sh` and `legs_multi.sh`: the legs.
- `ehz_run_probe.py`: the 2026-09-27 probe plus `--watch`.
- `pxsum.py`: parallax cycles by part.
- `cmptable.py`: lag, cycles, path and output identity.
- `witness_runs.sh`: the new witness over several ROMs.
