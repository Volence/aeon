# Parallax per-band overhead, round 3: the anchored split keeps the key (2026-09-28, PERF-PARALLAX-PPB4)

Rounds 1 and 2 (`docs/research/2026-09-28-parallax-perband.md` and `-perband-2.md`, merges
`d33fa8d0` and `c06c786b`) left the anchored region as the one place the caches never paid:
Step 4b's split rewrote the shadow view, so it dropped Step 4a's key, and the next tick rebuilt
the view and re-marked the selection. This round is rider PPB-4, with PPB-10 priced alongside it.

Branch `perf/parallax-ppb4`, based on `origin/master` `0a368458`. Tools and raw results are in
`docs/research/2026-09-28-parallax-perband-3/`. The legs, the probe, `pxsum.py` and
`cmptable.py` are round 1's (`docs/research/2026-09-28-parallax-perband/`), reused unchanged.

## The answer

- **The anchored region is 16% cheaper when the camera holds its height, with identical
  output.** `Parallax_Update` (inclusive) went 14,428 -> 12,127 cycles a tick on the anchored
  right leg. Round 2 estimated ~2k; this is 2,301.
- **The anchored down leg did not gain: 14,933 -> 14,972 (+39).** Flying down moves
  `Vscroll_BG & 511` on 50 of 60 ticks, so Step 4a misses its key and rebuilds as before, and the
  split is fresh every tick. The +39 is the keep decision on each fresh split.
- **RAM: +4 bytes, and no headroom lost in either shape.** `Parallax_State` grew 852 -> 856 B. The
  alignment pad before `Player_Pos_Ring` absorbed the 4 bytes, so `Game_RAM_End` did not move.
  Round 1's sketch was a 528-byte pristine copy of the view; that turned out not to be needed.
- **PPB-10 was not built.** It does not pay in this structure. The price is below.
- **Controls:** the EHZ clip legs are unchanged to the cycle. Canonical OJZ is +4 to +22.
  Lag did not move on any leg.

## Referents

Every figure is from a FAST build of the named tree, run under the headless `oracle-aether`
subprocess (`/home/volence/sonic_hacks/oracle/target/release/oracle-aether`). It has no pacing,
so lag counts are deterministic. The legs are round 1's 14 (`legs.sh`), and the profiler uses
the callers lens, re-armed every 1024 px of camera x. `results/crcs.txt` has every build.

| tree | `s4.bin` | `s4.debug.bin` | `s4.s2clip.bin` | `s4.s2clip.debug.bin` |
|---|---|---|---|---|
| base `0a368458` | `f52861a3` / 830,971 | `24b22fa8` / 858,024 | `bf8b0231` / 930,579 | `7d250025` / 957,442 |
| first cut (`c7319627`) | `2db7633c` / 831,347 | `59fd0f8c` / 858,422 | `e0f6ffc1` / 930,951 | `d958b481` / 957,816 |
| derive once on the first kept tick (not landed) | `3cdeca31` / 831,373 | `86130491` / 858,446 | `921d5381` / 930,975 | `1ad8436c` / 957,859 |
| final (`65e8b882`, the branch's code) | `20d741cc` / 831,279 | `63b70f76` / 858,352 | `48a5ab6e` / 930,881 | `af7ba248` / 957,746 |

The base reproduces round 2's final numbers to the cycle (anchored right 14,428, down 14,933,
EHZ DEBUG run 11,176, canonical DEBUG run 7,434), so the tree between `c06c786b` and `0a368458`
moved nothing here.

## RAM, measured from the listings

`SYSTEM_STACK` is `$FFFFFF00` in both shapes. Headroom is `SYSTEM_STACK - Game_RAM_End`.

| shape | `Game_RAM_End` before | after | headroom before | after |
|---|---|---|---|---|
| release (`s4.lst`) | `$FFFFC102` | `$FFFFC102` | 15,870 B | 15,870 B |
| DEBUG (`s4.debug.lst`) | `$FFFFF130` | `$FFFFF130` | 3,536 B | 3,536 B |

- `Parallax_Shadow_Split` is at `$FFFF8BDC`, after the key, and `Parallax_State_End` moved
  `$FFFF8BF4` -> `$FFFF8BF8`.
- Everything from `Parallax_Band_Sel` up to the alignment pad before `Player_Pos_Ring`
  (`$FFFFBF00` release, `$FFFFEF00` DEBUG) moved +4 bytes. `Player_Pos_Ring` and everything
  after it did not move (`results/ramshift_*.txt`).
- So the DEBUG shape keeps its ~3.5 KB, well above the 2 KB floor the brief set.

## The design

A split changes the view in ways that depend only on the view and the config: the records are
shifted down, the split entry is copied, the deform shifts are overridden, and
`CURVE_FLAG_CONT_BIT` is set. Given the same key, all of that comes out the same again. Only
two things change from tick to tick: the anchor line L, and the scroll words, which Step 4a
re-rotates unsplit on every tick. So the smallest design keeps the SPLIT view under the key,
not a pristine copy beside it:

1. **Keep** (in Step 4b's `.anchor_have_k`). The split keeps the key when two things hold: the
   key is live, which makes this a ROM config's view, and the view has no curve layer
   (`Parallax_Curve_Walk`'s count is 0). It then records the split entry's slot, k+1, in
   `Parallax_Shadow_Split`. Otherwise it drops the key, as every split did before (`.anchor_drop`).
2. **Reuse** (in `.anchor_kept`). On a key hit, a non-zero slot means the view is last tick's
   split. The split is still right if L is still inside the band it split, which is the band
   `.anchor_find_k` would find in the unsplit view. In the split view that is
   `parent top <= L < successor top`, where the parent is the slot above the split entry and the
   successor is the slot below it (or the screen bottom). Tops never decrease, so this is
   exactly find_k's answer, equal tops included. When it holds, the tick only re-shifts the
   scroll words and retops the split entry. That is the shared tail `.anchor_scroll`, which a
   fresh split also runs.
3. **Restart** (in `.anchor_restart`). If L has left the band, or there is no split this tick
   (the line is below the screen, or past the channel's raster band: `.anchor_no_split`), the
   kept split is wrong. Step 4b then clears the key and the slot and jumps back to `.step4a`. The
   rebuild clears the slot too.
4. **Why no curve layer.** The curve hoist runs between Step 4a and Step 4b, and it walks slots
   that describe the unsplit view. A kept split must never meet it, and an empty walk skips the
   hoist outright.
5. **The selection stays `$FF` on every split view, kept or not.** A kept split keeps the run
   along with the flag, so its kept ticks skip the selection pass as well.

### Three cuts, measured (`results/cmp_base_v1.txt`, `cmp_base_v2.txt`, `cmp_base_noderive.txt`, `cmp_base_v4.txt`)

| cut | anchored right | anchored down | shadow-key witness |
|---|---|---|---|
| base | 14,428 | 14,933 | GREEN (unextended) |
| 1. a fresh split re-derives the selection (clears the flag) | 12,013 | **15,398** | GREEN |
| 2. derive once, on the first kept tick (a provisional marker) | 12,033 | 14,990 | **RED** (at the marker) |
| 3. never derive: `$FF` on every split view (landed) | 12,127 | 14,972 | GREEN |

- **Cut 1 lost on the down leg (+465).** Every tick there is a fresh split, so every tick paid
  the selection pass (~150 cycles a slot) on the 5-slot split view.
- **Cut 2 bought 94 cycles a tick on the right leg over cut 3.** The price was a marker for the
  provisional bytes, and a split view whose cache no forced rebuild reproduces: a fresh split
  marks `$FF`, while a kept one holds exact bytes. The witness compares the caches as well as
  the output, and it went RED on the marker (`results/witness_v3_provisional_red.txt`, run on
  cut 2 plus the restart's own clear below, crc `12a68daa`). The output was still identical. Cut 3 gives up the 94 cycles and keeps the cache deterministic.
- **The restart clears its own slot.** A measurement build with the rebuild's clear removed
  hung the canonical run at 0 logic ticks, because the restart looped. The same build with the
  restart's own clear ran (`tools/ed_noclr.py`, `L_p4_noclr` / `_noclr2`, not kept). The
  restart is a loop, so it must not depend on another block to terminate it.

### What each tick costs now

- **A kept tick on a ROM config:** the Step 4a key hit, the scroll re-rotation, the kept check
  (two compares), the scroll shift, and the retop. That replaces a view rebuild, the record
  shift-down, the split entry copy, and the override walk.
- **A tick with no split, on a config with an anchor channel:** +22 cycles for
  `.anchor_no_split`'s `tst.w` plus the taken `beq`. The canonical OJZ spawn config (`$01487E`,
  `pcfg_anchor_ch` 0) takes this exit on every tick of the canonical run: its line never splits
  there (`--watch` over 1,800 ticks: the slot stayed 0 and the key stayed live throughout). That
  is the whole +22 on `cdebug_run` / `cplain_run`.
- **A rebuild:** +16 cycles for the `clr.w Parallax_Shadow_Split`. The other canonical legs'
  +4 to +5 is this, spread over their rebuild ticks.

## Before / after (base `0a368458` -> final `65e8b882`; same tick spans)

`results/cmp_base_v4.txt`. Lag is counted as lag frames / video frames over the same span of
logic ticks.

| leg | lag before | lag after | parallax cyc/tick before -> after | output |
|---|---|---|---|---|
| clip run, release | 0 / 1201 | 0 / 1201 | 11,058 -> 11,058 | 0 of 1,197 ticks differ |
| clip spindash run, release | 1 / 1244 | 1 / 1244 | 11,060 -> 11,060 | 0 of 1,240 |
| clip run, DEBUG | 6 / 1207 | 6 / 1207 | 11,176 -> 11,176 | 0 of 1,201 |
| clip spindash run, DEBUG | 5 / 1248 | 5 / 1248 | 11,177 -> 11,177 | 0 of 1,243 |
| clip fly diagonal, whole act | 20 / 1100 | 20 / 1100 | 9,405 -> 9,405 | 0 of 1,080 |
| clip fly diagonal, EHZ band | 16 / 72 | 16 / 72 | 11,048 -> 11,048 (segment 0) | (row above) |
| clip fly right / down | 0, 0 | 0, 0 | 9,121 -> 9,121 / 11,218 -> 11,218 | 0 of 1,100 / 400 |
| canonical fly diagonal | 12 / 700 | 12 / 700 | 7,484 -> 7,488 | 0 of 688 |
| canonical fly right / down | 0, 0 | 0, 0 | 6,606 -> 6,610 / 6,927 -> 6,932 | 0 of 700 each |
| canonical run, release / DEBUG | 0 / 1800 | 0 / 1800 | 7,318 -> 7,339 / 7,434 -> 7,456 | 0 of 1,800 each |
| **canonical anchored region, right** | 0 / 60 | 0 / 60 | **14,428 -> 12,127** | 0 of 60 |
| **canonical anchored region, down** | 0 / 60 | 0 / 60 | **14,933 -> 14,972** | 0 of 60 |

- **One path row differs on one leg.** On the clip DEBUG spindash leg at tick 606, the player's
  recorded y is 896 on the base and 897 on the branch. Ticks 605 and 607 agree, and so does the
  camera; the parallax output is identical at every tick, and the parallax cycles are identical.
  The base re-run against itself shows 0 path differences (`results/cmp_base_base2_debug_spin.txt`),
  so the probe is deterministic on one ROM. The branch moves code and RAM addresses (+4 B after
  `Parallax_Band_Sel`), which shifts where the probe's once-a-frame sample falls. That is the
  same class as round 2's tick-326 row. It is an observation, not a proven mechanism.
- **Decomposition was not measured this round.** Round 1's `decomp.py` rewrite was not
  re-validated against the new Step 4b labels, so the table above is inclusive `Parallax_Update`
  only.

## Correctness

1. **Leg identity.** `Hscroll_Buffer`, the VSRAM column buffer and `Vscroll_Factor`: 0 differing
   ticks on all 14 legs, base -> final (and base -> first cut, base -> cut 2).
2. **The fixture matrix.** `tools/parallax_hscroll_identity.py --ref <base capture>` on the final
   canonical DEBUG ROM reports "OK — every fixture's Hscroll_Buffer is byte-identical to the
   reference", exit 0, with ragged spans 4 and wrapping frames 240 (`results/ident_*.txt`). Its
   fixtures are RAM configs, which are never keyed, so no split is ever kept there, and they
   exercise only the drop path.
3. **The kept split, differentially.** `tools/parallax_shadow_key_witness.py` is extended:
   - **Capture.** It captures `Parallax_Shadow_Split` (it is in the tail it already compares, and
     it is now named in `TAIL_FIELDS`).
   - **Forced run.** The forced run pokes the slot to 0, as well as the key and the selection flag.
   - **Two new required classes:**
     - `kept`: the pre-frame key was live, with a kept split, and vs was unchanged.
     - `resplit`: a kept split whose slot changed in the frame, which means the line left the
       band and Step 4b restarted.
   - **The `split` class** now counts kept splits as well as dropped ones.
   - **A new leg, `anchor still`.** The camera holds at the anchored region's `wy - 2`, and the
     channel's own sweep (`anchor_sweep(4, 1)`, measured L 98..130 there,
     `results/probe_still_sweep.txt`) carries the line across the edge between the view's
     first two bands (115), once each way, per 512 ticks. The leg runs up to 600 samples and
     stops after two resplits. It is the only leg that reaches `resplit` reliably: a moving
     camera moves vs, because DEBUG flight steps 16 px and vs is camera / 8, so the line never
     crosses an edge under an unchanged key.
   - **On the final ROM:** exit 0, 581 samples, hit 581, vs-moved 50, split 500, kept 460,
     resplit 3, 0 differ (`results/witness_v4.txt`). About 7 s a run.
   - **Before the extension,** on the first cut, the unextended witness reported COULD NOT RUN:
     split 0. The kept split keeps the key, so its only signal for a split (the key reading 0)
     never fired. That is the witness failing safe, not a pass.

**Red-first.** `build_mutant3.sh` keeps each mutation on disk (`results/mutants/mut*.diff`) and
restores every file from HEAD afterwards. `mutants3_all.sh` runs the canonical identity legs
against the base and the witness on each.

| mutant | identity legs vs base | witness |
|---|---|---|
| L: the kept check drops the successor test | green on all 5 legs | **RED**, exit 1, 200 samples differ |
| M: the kept check drops the parent test | green on all 5 legs | **RED**, exit 1, 266 differ |
| N: the retop is deleted (fresh and kept) | **RED**: anchored right 56/60, down 14/60 | green (both runs retop the same wrong way) |
| P: the rebuild does not clear the slot | **RED**: anchored down 39/60, diagonal 1/688 | **RED**, exit 1, 652 differ |
| R: the no-split exit ignores a kept split | **RED**: canonical run 1800/1800, diagonal 112/688, down 114/700 | **RED**, exit 1, 60 differ |
| Q: the keep ignores the curve condition | green | green: **a COVERAGE GAP, not a pass** |
| S: `SHADOW_SPLIT_LONGS` 0 | build refused: "the kept anchored split reserves 0 bytes, not the 4 …" (and the span drift ensure) | n/a |

- **Two instruments, two blind spots.**
  - L and M are invisible to the legs. None of them holds a line crossing a band edge under an
    unchanged key; only the witness's still leg does.
  - N is invisible to the witness, because both of its runs take the same broken tail. Only
    the legs, which compare against the base, see it.
- **Q is the untested clause.** No shipped config and no leg pairs an anchored split with a
  curve layer: EHZ's curve config has no anchor channel. The fixture matrix cannot reach it
  either, because its configs are RAM, and RAM configs are never kept. The clause is argued at
  the code (the hoist walks unsplit slots), not measured. It is booked as an open rider.

## PPB-10: the selection byte's reason bits, priced and not built

PPB-10 would let the fill skip its inline tests on a sampled band by carrying FG, BG, curve and
remap as bits in the selection byte. Round 2 said it is worth doing only together with PPB-4.

- **What it would buy, on what the views hold today.**
  - EHZ's 7-slot view has 2 non-zero bytes: the BG-sampled band and the curve.
  - The canonical spawn config's 6-slot view has 1 (`tools/probe_sel.py`, on the
    final FAST ROMs).
  - Split views hold `$FF` (cut 3 above), so PPB-10 buys nothing there unless they get exact
    bytes.
- **Estimated saving per sampled band: ~60 cycles.** The inline decision for a BG-only band
  with a live FG table is about 150 cycles: the remap `tst.l`, the curve `btst`, and the FG and
  BG tests. A bit dispatch is about 80. This is an instruction count, not a measurement. So
  roughly 60 a tick on EHZ, and 0 to 60 on canonical OJZ.
- **What exact split-view bytes are worth, measured:** 94 cycles a tick on the right leg (cut 2
  against cut 3), and they cost the witness its determinism.
- **What blocks it.** Under `CAP_DEFORM` the bits would replace the inline remap and curve tests,
  but a game with curves or a remap and no deform still needs those tests. That leaves two
  shapes:
  - elide them with `if CAP_DEFORM == 0`, the inverted gate the span model forbids (the
    config-level table hoist's comment in `Parallax_Fill_PerLine`);
  - keep them reachable for the `$FF` escape and add a second, bit-driven decision path beside
    them, which is two decision paths for ~60 cycles a band.

  Making split views exact as well means either deriving on every fresh split (+465 measured on
  the down leg) or a byte transform in the split, which is new code, about n+1 slots x ~40
  cycles (estimated).
- **Verdict:** under 1% on any leg, against a second decision path in the hottest routine.
  PPB-10 stays open with this price.

## Landing evidence

The full record is in `docs/DEFERRED_WORK.md` PERF-PARALLAX-PPB4. Every run below used full
builds at `e028714d` (the branch plus a tools/docs-only merge of `origin/master` `8c6bb74c`):

- `tools/landing_build.sh` exit 0, `finished=0`.
- Both S2CLIP builds rc 0.
- The effects-gates ritual rc 0: 23 gates, 42 rows, 0 FAIL.
- The extended witness is GREEN on the landing `s4.debug.bin`.
- The landing ROMs are byte-identical to the FAST final builds measured above: `s4.bin`
  `20d741cc`, `s4.debug.bin` `63b70f76`, clip `48a5ab6e` / `af7ba248`.

## Open

1. **The keep's curve clause is untested (mutant Q).** A fixture that installs a ROM config
   with both an anchor channel and a curve layer would be needed. RAM fixtures cannot reach it,
   because they are never kept.
2. **A vertically scrolling anchored region still rebuilds every tick** (the down leg). The
   rebuild's cost there is the rotation and rebase of the whole view on each vs change.
   PPB-9's per-config selection, and a rebuild that re-rotates rather than re-copies, are the
   levers.
3. **+22 cycles a tick on a config with an anchor channel whose line does not split.** This is
   the price of knowing whether a kept split must be undone. Packing the slot into a word the
   no-split path already reads would remove it. Nothing on that path reads our RAM today.
4. **PPB-8 again.** The DEBUG RAM layout moved 4 B, from `Parallax_Band_Sel` to the pad before
   `Player_Pos_Ring`, so the replay net's RAM-hash checkpoints have the GPL-A3-3 question again.
   Not measured here.
5. **PPB-10**, above.

## Tools (in `docs/research/2026-09-28-parallax-perband-3/`)

- `build_mutant3.sh` builds mutants L, M, N, P, R, Q and S, and `mutants3_all.sh` runs them
  with their legs and the witness.
- `collect.sh` gathers everything into `results/`.
- `tools/`:
  - `probe_split.py`: a per-tick trace of the split slot, vs, L and the shadow tops;
  - `probe_sel.py`: the selection bytes, shadow tops and shifts of a booted ROM's view;
  - `variant_build.sh`: a measurement-only canonical DEBUG build with one edit, restored after;
  - `ed_noderive.py`: cut 3 from cut 2;
  - `ed_noclr.py`: the no-rebuild-clear measurement;
  - `ramshift.py`: the RAM symbol shift between two listings.
- Round 1's `build4.sh`, `legs.sh`, `pxsum.py` and `cmptable.py` were used unchanged.
