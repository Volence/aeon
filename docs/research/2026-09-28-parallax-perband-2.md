# Parallax per-band overhead, round 2 (2026-09-28, PERF-PARALLAX-PERBAND-2)

Round 1 (`docs/research/2026-09-28-parallax-perband.md`, merge `d33fa8d0`) left seven riders.
This round took three of them: PPB-3, PPB-5 and PPB-6. It also re-ran the walker model's
fitting probe for PPB-7. PPB-1 (needs a paired sigil commit), PPB-2 (a record-format change)
and PPB-4 (+528 B RAM) were out of scope.

Branch `perf/parallax-perband-2`, based on `origin/master` `e76dcea9`. Tools and raw results
are in `docs/research/2026-09-28-parallax-perband-2/`. The legs, the probe, `pxsum.py` and
`cmptable.py` are round 1's (`docs/research/2026-09-28-parallax-perband/`), reused unchanged.

## The answer

- **Parallax is 5.4% cheaper on Emerald Hill and 10% cheaper on canonical OJZ, with
  byte-identical output.** `Parallax_Update` (inclusive) went 11,814 -> 11,176 cycles a tick
  on the clip's EHZ DEBUG run, and 8,270 -> 7,434 on the canonical OJZ DEBUG run.
- **All three items paid, but not by round 1's estimates.** On the EHZ run: PPB-5 bought 246,
  PPB-3 349 and PPB-6 only 43. PPB-6 was estimated at ~0.5k. It pays ~16 cycles per group of
  8 flat lines, after a 32-cycle setup per band, and EHZ's flat bands are short (11 to 58
  lines). OJZ's are tall, so PPB-6 is worth 265 there.
- **The anchored region got slightly dearer:** +114 / +90 cycles a tick on the two anchored legs
  (14,314 -> 14,428 and 14,843 -> 14,933). That region rebuilds and splits the view every
  tick, so both caches are rebuilt there and never reused. The cost breakdown is below.
- **Lag did not move on any leg.** The DEBUG run is still 6 / 1207 and the EHZ band of the
  diagonal is still 16 / 72. This was expected: round 1's upper bound showed each overrunning
  tick is over by more than several thousand cycles, and this round removed 0.64k.
- **PPB-7: the fitting tool exists and was re-run** (`tools/parallax_cost_probe.py`, 26
  fixtures, 3 boots). Its rows were recorded but not promoted into the model's primary rows, for
  two reasons given below. The main one: its fixtures are RAM configs, which are never keyed, so
  since round 1 the model prices only the rebuild path.

## Referents

Every figure is from a FAST build of the named tree, run under the headless `oracle-aether`
subprocess (`/home/volence/sonic_hacks/oracle/target/release/oracle-aether`). It has no
pacing, so lag counts are deterministic. The legs are round 1's 14 (`legs.sh`). The profiler
uses the callers lens and is re-armed every 1024 px of camera x.

| tree | `s4.bin` | `s4.debug.bin` | `s4.s2clip.bin` | `s4.s2clip.debug.bin` |
|---|---|---|---|---|
| base `e76dcea9` | `76835839` / 830,244 | `dd3cf064` / 857,247 | `5a25334f` / 929,852 | `2a3eda50` / 956,667 |
| PPB-5 (`c8971d36`) | `a51bd515` / 830,405 | `08a6f881` / 857,410 | `d5637cb3` / 930,013 | `caab8dec` / 956,828 |
| PPB-3 first cut (not landed) | `3f3d318d` / 830,781 | `21df68fc` / 857,810 | `802d6be3` / 930,389 | `5e731cf2` / 957,204 |
| PPB-3 (`e33390b4`) | `c0da08f7` / 830,807 | `ca37c52e` / 857,856 | `3d8eb944` / 930,417 | `e200256e` / 957,250 |
| PPB-6 (`73773349`, the branch's code) | `26525a48` / 830,827 | `c426c836` / 857,856 | `64b26b08` / 930,437 | `43d6def7` / 957,250 |

`results/crcs.txt` has each tree's HEAD. Load is recorded per leg in `results/legs_*.meta`.
It was 5 to 15 during these runs; the headless lag counts do not depend on it.

## What changed

### PPB-5: the curve hoist walks only the view's curve layers

The hoist walked every shadow band, spending ~56 cycles on each one that was not a curve. On
Emerald Hill that was six of the seven bands, every tick.

- **The change.** Step 4a's rebuild path now derives a range `[first, first + count)` of the
  slots that hold a curve layer, and stores it in `Parallax_Curve_Walk`. The hoist walks only
  that range, with the loop it always had, so a non-curve slot inside the range is still
  skipped by its own `btst`.
- **Why the range cannot go stale.**
  - It is a function of the view, and it is derived on every rebuild, a RAM config's included.
  - A key hit keeps it together with the view.
  - Step 4b's split runs after the hoist and drops the key, so the range never describes a
    split view.
- **RAM:** 4 B under `CAP_FACTOR_CURVE`, at the tail of `Parallax_State`.
- **Measured:** the hoist went 975 -> 728 cycles a tick on EHZ (decomposition build,
  `results/decomp_*_pxsum.txt`). On canonical OJZ it went 334 -> 38, because no OJZ config has
  a curve layer and the hoist now stops at its first test.

### PPB-3: the fill's per-band loop selection, cached under the same key

The fill re-decided every band's line loop every tick. A flat band paid about 116 cycles to
arrive at `.lp_flat` again: the remap `tst.l` (26), the curve `btst` (26) and the deform tests
(64).

- **The cache.** A selection pass just before the fill writes one byte per shadow slot into
  `Parallax_Band_Sel`. A zero byte means "the inline tests would take `.lp_flat` and mark no
  remap".
- **The fill.** It tests the byte first (`lea` + `tst.b (a0,d7.w)` + `beq`, 32 cycles).
  - A zero byte goes straight to `.lp_flat`.
  - Any other byte falls into the inline tests unchanged. So the only new claim the code makes
    is what a zero byte means.
- **Stored reversed.** Slot i's byte is at index n-1-i, which is the value the fill's own
  down-counter d7 holds after its `subq`. No new register is needed.
- **When the pass runs.** Only while `Parallax_Band_Sel_Valid` is 0. Step 4a's rebuild and
  `Parallax_Init` clear it.
  - The pass's inputs are the view and the config's two table pointers. The config is half of
    the key, so on a hit the bytes still describe the view.
  - Under `CAP_MULTI_DEFORM_TABLE` the pass reads each band's own table pair, as the fill does.
- **The split.** Step 4b's split does not re-derive the bytes. It fills them all with `$FF`
  and sets the flag. A non-zero byte claims nothing, so it is correct for any view.
  - Why not re-derive: the first cut did, and it measured **+900 cycles a tick** on the
    anchored legs (`results/cmp_p5_p3first.txt`). The pass costs ~150 a slot, it would run on
    every anchored tick, and it would save only the few flat slots such a view has.
  - The `$FF` run is a constant 4 longs (`fill_band_sel_longs`).
- **Capability.** The mechanism is gated on `CAP_DEFORM`, whose tests are the largest part of
  the per-band decision. It costs 20 B of RAM there, and demo pays nothing. A game with curves or
  a remap but no deform keeps the inline tests it had.
- **Measured:** on EHZ -349, on OJZ run -275, and on the anchored legs +266 / +239
  (`results/cmp_p5_p3.txt`).

### PPB-6: flat lines by `movem.l`

- **The change.** A group of 8 flat lines is now written by two `movem.l d0/d3/d5-d6, -(a0)`,
  with a0 walking down from the band's end. That is 90 cycles a group, against 106 for 8
  `move.l` plus the `dbf`.
  - `movem` has no post-increment store form, so the band is written backwards, and a4 steps
    to the band end first, computed from the span. That also removes one of the two failure
    modes the flat tail's banner lists: a4 can no longer fall out of step with d4.
  - Four copies of d0, because d0/d3/d5/d6 are the only free data registers on the flat path.
- **Setup:** +32 cycles a band, so a flat band gains from its third group.
- **Measured:** on EHZ -43; on OJZ run -265, fly right -356, anchored -164 / -130
  (`results/cmp_p3_p6.txt`).
- **What would buy more.** More copies of d0. The spare address and data registers are the
  fill's cross-loop contract (a1-a3, a5/a6, d4, d7). Spilling a5/a6 costs ~50 cycles a band,
  which is more than the short bands gain, so it was not done.

## Before / after (base `e76dcea9` -> the branch; same tick spans)

`results/cmp_base_final.txt`. Lag is counted as lag frames / video frames over the same span
of logic ticks.

| leg | lag before | lag after | parallax cyc/tick before -> after | output |
|---|---|---|---|---|
| clip run, release | 0 / 1201 | 0 / 1201 | 11,697 -> 11,058 | 0 of 1,200 ticks differ |
| clip spindash run, release | 1 / 1244 | 1 / 1244 | 11,699 -> 11,060 | 0 of 1,242 |
| **clip run, DEBUG** | **6 / 1207** | **6 / 1207** | **11,814 -> 11,176** | 0 of 1,200 |
| clip spindash run, DEBUG | 5 / 1248 | 5 / 1248 | 11,816 -> 11,177 | 0 of 1,242 |
| clip fly diagonal, whole act | 20 / 1100 | 20 / 1100 | 10,055 -> 9,405 | 0 of 1,080 |
| **clip fly diagonal, EHZ band** | **16 / 72** | **16 / 72** | 11,679 -> 11,048 (segment 0) | (row above) |
| clip fly right / down | 0, 0 | 0, 0 | 9,784 -> 9,121 / 11,858 -> 11,218 | 0 of 1,100 / 400 |
| canonical fly diagonal | 12 / 700 | 12 / 700 | 8,200 -> 7,484 | 0 of 688 |
| canonical fly right / down | 0, 0 | 0, 0 | 7,532 -> 6,606 / 7,751 -> 6,927 | 0 of 700 each |
| **canonical run, release / DEBUG** | 0 / 1800 | 0 / 1800 | 8,154 -> 7,318 / **8,270 -> 7,434** | 0 of 1,800 each |
| canonical anchored region, right / down | 0 / 60 | 0 / 60 | 14,314 -> 14,428 / 14,843 -> 14,933 | 0 of 60 each |

- **Per step, EHZ DEBUG run:** 11,814 -> 11,568 (PPB-5) -> 11,219 (PPB-3) -> 11,176
  (PPB-6).
- **Per step, OJZ DEBUG run:** 8,270 -> 7,974 -> 7,699 -> 7,434.
- **Decomposition, EHZ DEBUG run** (`build_decomp.sh`, base -> final):

  | part | base | final |
  |---|---|---|
  | fill | 6,748 | 6,334 |
  | curve hoist | 975 | 728 |
  | Step 4a | 430 | 430 |
  | the rest of Step 4 | 191 | 213 (+22: the selection flag test) |

- **Why the anchored legs went up.** Decomposition, anchored right, base -> final:

  | part | base | final | why |
  |---|---|---|---|
  | Step 4a | 1,438 | 1,702 | +264: the curve-walk scan runs on every rebuild |
  | hoist | 275 | 37 | the scan above pays for this |
  | the rest of Step 4 | 1,593 | 1,697 | +104: the split's `$FF` run and the flag |
  | fill | 8,586 | 8,569 | PPB-6's gain, less 32 cycles a band for the selection test that never passes there |

  PPB-4 (keep the view across a split) would turn both caches into hits there as well.
- **One path row differs on two legs.** It is on the clip DEBUG run and spindash legs, at tick
  326: the player's recorded x is 1,339 on the base and 1,334 on the branch. It is the same
  tick on every compared build, the camera agrees, and the path agrees again on the next tick.
  It is the probe's once-per-frame sample landing either side of a lag frame at the x-1330
  jump trigger, not a divergence. PPB-5 to PPB-3 and PPB-3 to PPB-6 show 0 path differences on
  every leg.

## Correctness

1. **Leg identity.** On every frame that ends an on-time tick, `ehz_run_probe.py --dump` reads
   `Hscroll_Buffer`, `Parallax_Vscroll_Column_Buf` and `Vscroll_Factor`, and `cmptable.py`
   compares them at every tick where the camera agrees. Result: 0 differing ticks on all 14
   legs, base -> PPB-5 -> PPB-3 -> PPB-6.
2. **The fixture matrix.** `tools/parallax_hscroll_identity.py --ref <base capture>` on the
   final canonical DEBUG ROM reports "OK — every fixture's Hscroll_Buffer is byte-identical to
   the reference", exit 0, with coverage witnesses ragged spans 4 and wrapping frames 240
   (`results/ident_*.txt`). Its fixtures are RAM configs, so they exercise the rebuild and
   selection path on every tick.
3. **The cached path, differentially.** `tools/parallax_shadow_key_witness.py` was extended in
   two ways:
   - its forced run also pokes `Parallax_Band_Sel_Valid` to 0;
   - its capture now takes in the key and the two caches kept under it. The shadow capture is
     now exact: it used to over-read 32 bytes past `Parallax_Shadow_Scroll_B`.

   On the final ROM: exit 0, 180 samples, hit 81, vs-moved 10, split 99, 0 differ.

**Red-first.** `build_mutant2.sh` keeps each mutation on disk (`results/mutants/mut*.diff`)
and restores every file from HEAD afterwards.

| mutant | identity legs vs base | witness |
|---|---|---|
| C: the selection marks a BG-sampled slot flat | RED: EHZ run 1201/1201, EHZ diagonal 1080/1080 ticks differ | green (both paths share the wrong pass) |
| D: the split sets the flag but leaves the bytes | RED: anchored right 58/60, anchored down 42/60, canonical diagonal 2/688 | green (both runs split) |
| K: Step 4a's rebuild keeps the selection | RED: clip diagonal 398/1080 | **RED, exit 1, 81/180 at `Parallax_Band_Sel`**; the unextended witness on the same ROM: exit 0 |
| E: the curve walk count is one short | RED: EHZ run 1200/1200, clip diagonal 682/1080, canonical diagonal 188/688 | green |
| F: one `movem.l` of the two in a flat group | RED: every leg (e.g. EHZ run 1200/1200, OJZ down 700/700) | green |

The witness is green on C, D, E and F by construction. It compares a kept cache against a
forced re-derivation, and those mutants break the derivation itself, so both runs are wrong the
same way. The leg identity against the base is the check that sees them. K is the class of bug
the witness exists for, and the extension is what catches it.

The four new `ensure`s were each refused by the build on a mutation
(`results/mutants/mut{G,H,I,J}_build.txt`):

| mutation | refused by |
|---|---|
| `CURVE_WALK_WORDS` one word short | "the curve hoist walk reserves 2 bytes, not the 4 …" |
| `BAND_SEL_BYTES` 4 short | "the fill's cached loop selection reserves 16 bytes, not the 20 …" |
| `BAND_SEL_N` folds the retired `$0001` bit | "BAND_SEL_N is 0 but this game's Game.SCANLINE_CAPS & CAP_DEFORM is 4 …" |
| `MAX_PARALLAX_BANDS` 18 | "MAX_PARALLAX_BANDS is 18, not a multiple of 4 …" |

## PPB-7: the walker model

- **How it was fitted before.** `[parallax.cost_model]` in `tools/effects_budget_model.toml` is
  the output of `tools/parallax_cost_probe.py`. That probe runs 26 RAM-config fixtures, each
  one edit from `ParallaxConfig_OJZ_Default`, 3 boots each, and fits an additive model by least
  squares. Its last promotion was P3 Task 13, 2026-08-22.
- **The re-run.** Base `dd3cf064` and final `c426c836`, `--repeat 3`, spread 0, every window
  preemption-free, exit 0 (`results/cost_probe_*.txt`).

| term | toml (P3 tip) | base `e76dcea9` | final (this branch) |
|---|---|---|---|
| base | 4664.0 (derived) | 5455.7 | 4776.2 |
| band_perline | 854.0 | 958.0 | 1026.5 |
| multiband | 20.0 | 42.8 | 106.2 |
| line_fg_only / bg_only / both | 26.0 / 26.9 / 124.5 | 26.0 / 27.2 / 124.7 | 30.6 / 31.9 / 129.3 |
| shift_lines | 2.0 | 2.0 | 2.0 |
| band_sampling | 154.0 | 164.6 | 103.5 |
| vdeform | 1472.0 | 1554.3 | 1569.8 |
| anchor / anchor_ops | 981.4 / 60.77 | 1068.3 / 102.9 | 1001.2 / 102.2 |
| max \|residual\|, all 26 (un-anchored 18) | 43.6 (0.00) | 64.5 (67.6) | 72.9 (47.5) |
| out-of-sample (the idle ROM config) | +2.11% | model 9330.6 vs 8252, **-13.1%** | model 8988.4 vs 6950, **-29.3%** |

**Recorded as a re-take block in the toml, not promoted.** The primary rows and their mirror
in `engine/level/scene_dsl.emp` (`SB_WALK_*_X100`, the comptime axis-1 scene budget) are
unchanged, for two reasons:

1. **The fixtures measure a path shipped configs mostly no longer take.** A fixture is a RAM
   config. A RAM config is never keyed, so every fixture tick rebuilds the view and re-runs the
   selection pass. A ROM config takes the key hit on every tick where its vs holds. The
   out-of-sample row is the only ROM config the probe measures, and it shows the gap: the model
   over-predicts it by 13% after round 1 and by 29% after this round. As an upper bound that is
   safe, but it no longer describes the walker's common case.
2. **The additive model has stopped fitting to zero.** Its max residual on the un-anchored 18
   was 0.00 at the P3 tip and is 47.5 now (67.6 already on the base). No column describes what
   changed:
   - a flat band now costs differently from a sampled one in the selection test;
   - the curve walk's cost depends on where the curve layers sit;
   - `.lp_flat`'s cost is now per group plus a per-band setup.

   Promoting coefficients from a model that no longer fits would move the build's comptime
   budget off a number whose error is no longer bounded. That is a budget-policy change for the
   owner, so it is booked (DEFERRED_WORK rider PPB-7, now PPB-7b) and not made silently here.

## Open, priced, not built

1. **PPB-4, which is now worth more.** Keeping the view across an anchored split would turn
   Step 4a, the curve walk and the selection into hits on the anchored region. Estimated from
   the decomposition above: ~1.7k (4a) + ~0.1k (split run) + ~0.15k (selection tests), for
   +528 B RAM at MAX 16.
2. **Cheaper misses for vertically scrolling configs.** The selection pass costs ~120-150 a
   slot and runs on every vs change. The selection is a function of the ROM bands alone, so it
   could be cached per config and rotated by k like the scroll words (~25 a slot). That needs
   another MAX-byte array and a config key. OJZ's diagonal and down legs still gained 224 and
   263 cycles a tick without it, so it was not built.
3. **More `movem` copies.** See PPB-6: blocked by the fill's register contract, not by
   design.
4. **The selection byte's bits.** The byte only says zero or non-zero. Carrying the four
   reasons (FG, BG, curve, remap) as bits would let the inline path skip its tests too, about
   20-40 cycles per sampled band. The catch: the `$FF` split marking would then be wrong, so
   the split would have to re-derive, which is the +900 above. It is worth doing only together
   with PPB-4.

## Tools (in `docs/research/2026-09-28-parallax-perband-2/`)

- `build_mutant2.sh` builds the code mutants C/D/K/E/F and the ensure mutants G/H/I/J.
- `mutants_all.sh` builds every mutant, then runs the code mutants' identity legs and the
  witness.
- `witness_runs2.sh` runs the extended witness over several ROMs.
- `collect.sh` and `collect_mutants.sh` gather the results into `results/`.
- Round 1's `build4.sh`, `build_decomp.sh`, `legs.sh`, `pxsum.py` and `cmptable.py` were used
  unchanged.
