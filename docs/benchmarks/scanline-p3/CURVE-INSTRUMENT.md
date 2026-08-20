# The HScroll ramp reader — a curve detector built before any curve exists

**Parcel:** Scanline P3, Phase 0, Task 2 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Tool:** `tools/parallax_hscroll_probe.py` · **Unit tests:** `tools/test_parallax_hscroll_probe.py` (34)
**Engine bytes changed:** none. This parcel is instrument-only.

---

## 1. Why the ordering is the point

Design §8.3 names the instrument curves need: *"after `Parallax_Update` on a pinned camera
state, read the HScroll buffer RAM and compare every line word in the curve span against the
comptime-expected ramp (derived, not copied); repeat across a camera sweep."*

Nothing in the tree reads that buffer as a derived expectation. `parallax_cost_probe.py`
measures what the walker COSTS; no tool has ever looked at what it WROTE.

Building the reader after Task 10 would give the curve mechanism a witness written to agree
with it — the vacuous-gate pattern this tree keeps rediscovering. So the reader lands first,
and Task 2's acceptance criterion is the inversion of normal red-first: **the checker must be
proven to detect curve-shaped output while no mechanism in the ROM can produce any.** Section 5
is that proof.

---

## 2. The buffer layout, transcribed

| fact | value | source |
|---|---|---|
| symbol | `Hscroll_Buffer` | `engine/ram.emp:270` |
| size | 896 bytes | `engine/ram.emp:270` — `[u8; 896]` |
| shape | 224 entries x 4 bytes | same line: *"224 lines x 4 bytes (FG + BG)"* |
| entry | FG word (big-endian) then BG word | `engine/level/parallax.emp:1305-1322` (`.lb_line`), `:1327-1341` (`.lf_line`), `:1350-1371` (`.lg_line`) |
| flat path | one `move.l` per line, `d0 = FG<<16 \| BG` | `parallax.emp:1444-1470`, packed at `:1284-1287` |
| per-cell mode | 28 longwords, same shape, lines 28..223 left stale | `parallax.emp:1495-1541` |
| mode key | per-line iff either H-deform table is non-NULL **or** the config carries an anchor | `parallax.emp:1012-1024` (twin in `engine.buffers`) |
| band partition | band *i* covers `[top[i], top[i+1])`; the last ends at 224 | `parallax.emp:1274-1283` |
| band tops unit | ROM entries in Plane-B **cells**, shadow view in **screen lines** — the same byte | `parallax.emp:82-101` |

Two supporting layouts the derivation needs, also transcribed with cites in the tool:
`band_entry` (10 bytes, `parallax.emp:69-80`), `parallax_config` (28 bytes,
`engine/structs.emp:161-190`), and the patch-record block `Raster_Patch_Tab` points at
(word count then 10-byte entries of `line_src`/`band_lo_fl`/`band_hi_fl`/`rec_off`/`rec_len`,
`engine/effects/raster.emp:1783-1812`).

---

## 3. The derived expectation

**Derived, never snapshot — and the line between an INPUT and an EXPECTATION is the design.**
The probe reads the walker's inputs and recomputes what the fill must have written, using the
fill's own arithmetic. It never reads a line's expectation off a neighbouring line, off the
buffer, or off a nearby pin. (Reading a deform table is reading an *operand*, exactly as
`parallax_cost_probe` reads the shipped config header; it is not reading the answer.)

**Stage A — derive the shadow view.** Step 4a's vscroll rotation (`parallax.emp:687-770`) and
Step 4b's anchored split (`:887-993`), recomputed from the config bytes, the live
`Parallax_Current_Vscroll_BG`, the live `Parallax_Current_Scroll_A/B`, and the resolved anchor
line; checked against `Parallax_Shadow_Bands` / `Parallax_Shadow_Scroll_A/B`.

This stage is not decoration. **The shadow band count lives only in `d7` and exists nowhere in
RAM**, and the fill's band partition is undefined without it — Step 4b makes the view one entry
longer than the config says, and the leftover entries below it are last frame's. Deriving the
count and then proving the derivation against the machine's own shadow view is how the probe
knows the partition it is about to check lines against.

The anchor line is resolved exactly as `parallax.emp:802-885` resolves it, including the three
states that are easy to get wrong: `L <= 0` splits at line 0 and is deliberately **not**
band-clamped; below `band_lo+1` it clamps **up**; past `band_hi+1` the raster record is not
emitted and there is **no split at all**.

**Stage B — derive the buffer.**

```
FG(line) = scroll_a[band]                                             flat on FG
         = scroll_a[band] + (sext8(tab_fg[(phase_fg + band_phase + camY   + line) & $FF]) >> shift_a)
BG(line) = scroll_b[band]                                             flat on BG
         = scroll_b[band] + (sext8(tab_bg[(phase_bg + band_phase + vscroll + line) & $FF]) >> shift_b)
```

A channel samples iff its table pointer is non-NULL **and** the band's shift != 15. The two
different phase folds are the layer anchor (Harmony study defect #2, `parallax.emp:1298-1302`
and `:1317-1320`): the FG index folds `Camera_Y`'s pixel high word, the BG index folds
`Parallax_Current_Vscroll_BG`, so the wave rides the art rather than the screen.

For the shipped flat path this collapses to exactly what the plan asks for: **per-band-stepped
constants**, one `(FG, BG)` pair per band, derived from the band's own scroll words.

### The sample point is a breakpoint, and that was not optional

The first draft sampled after `run_frames`. It reported **90 mismatching BG words starting at
line 70**, at two of five camera positions — lines 0..69 carrying the new deform phase and
70..223 the previous frame's. That is a **torn read** presented as a walker defect, which is
worse than having no instrument.

`run_frames` returns on a VIDEO frame boundary, which the main-loop tick is not aligned to, and
a camera write triggers a full tile-cache re-stream that lags the loop for many frames. So every
sample is now taken with the machine stopped at **`Parallax_Update`'s entry**: the previous call
has fully completed (the fill is the last thing the routine does), nothing is half-written, and
the next has not started. Two further traps fell out of getting that right, both recorded in the
tool:

- **A breakpoint at the PC you are already stopped at re-triggers instantly.** The sweep arm ran
  24 iterations against one frozen tick and reported 24 identical failures against a walker that
  was simply never called again. One `emulator/step` before arming fixes it.
- **`wait_for_break` can return on a stop that is not your breakpoint** (the `step` above emits
  one). The stop PC is now verified against `Parallax_Update` and the resume is retried; without
  that, 6 of 24 sweep samples were taken mid-tick.

The one value belonging to the tick *about to* run rather than the one just finished is the
anchor latch (`Effects_LatchWorldLines` runs earlier in the loop). The probe cross-checks it
against `Effects_World_Y - Camera_Y`: under a frozen, written camera the two cannot differ, and
a disagreement is reported as a **setup failure**, never as a walker defect.

---

## 4. The three arms

| arm | camera | asserts |
|---|---|---|
| `frozen` (default) | `Debug_Scene_Freeze = 1`, `Camera_X`/`Camera_Y` **written** between samples | Stage A + Stage B exactly, at 5 pinned positions |
| `sweep` | free-running, `emulator/hold` right | continuity + the one-tick-lagged FG tracking identity + monotonicity. Never an exact word, never a cycle |
| `redfirst` | frozen | the red-first proof of section 5 |

They are separate runs on purpose. §8.3 wants a camera sweep because at-rest captures hide
scroll artifacts; the walker's arithmetic wants a frozen camera because under sustained motion
one logic tick spans two video frames. Both are true, so both exist, and the moving arm is
deliberately the weaker one.

The sweep arm's continuity bound is **derived, not typed**: `2 * (max|table| >> min live
shift)` over the tables actually attached, per channel. Today that is FG 0 (no FG table) and
BG 4; measured interior max |d1| over 24 moving frames is FG 0, BG 1. The arm also refuses to
pass if the camera never moved — every assertion in it is conditional on motion, so a still
camera would make it a gate that asserted nothing.

The frozen arm's positions are not all invented: the first is `(None, None)`, the boot camera
untouched, so one position is always a state the ROM actually reaches.

---

## 5. THE RED-FIRST PROOF

`python3 tools/parallax_hscroll_probe.py --arm redfirst --rom s4.debug.bin --lst s4.debug.lst`

The ramp is a **quadratic bow** — `BG(L) = base + (L*L >> 7)`, `FG(L) = base - (L >> 1)` — and
it is outside what any deform table can emit, asserted rather than claimed
(`test_the_ramp_is_outside_what_any_deform_table_can_emit`): a deform sample is a signed byte,
so the widest excursion any table can produce anywhere on the screen is `127 - (-128) = 255` at
shift 0, and the shipped tables are amplitude 8..96 at shift >= 1. The ramp's BG excursion is
**+388** with a monotonically rising first difference — a non-constant second difference no flat
path and no sine table can produce.

Verbatim, at the boot camera on `s4.debug.bin` (config `$01230C` = `ParallaxConfig_OJZ_Underwater`,
per-line, 5 shadow bands, tops `[0, 48, 80, 112, 224]`, anchor L = 80):

```
[0] CONTROL — the shipped state against its derived expectation
    GREEN as required: all 224 entries match

[1] RAMP INSTALLED — quadratic bow, 224 entries, BG $FFD0 -> $0154 (excursion +388 px)
    ramp smoothness (what a curve mechanism would look like):
      FG: interior steps 220  nonzero 108  max|d1| 1  max|d2| 1  d1 range [-1, +0]
          d1 histogram {-1: 108, 0: 112}
      BG: interior steps 220  nonzero 188  max|d1| 4  max|d2| 1  d1 range [+0, +4]
          d1 histogram {0: 32, 1: 63, 2: 62, 3: 56, 4: 7}

[2] RED — the same checker, ramp in RAM, shipped-derived expectation
    RED as required.
  434 mismatching words; first 6:
    line   2 FG: expected $FFA0 (-96)  got $FF9F (-97)
    line   3 FG: expected $FFA0 (-96)  got $FF9F (-97)
    line   4 FG: expected $FFA0 (-96)  got $FF9E (-98)
    line   5 FG: expected $FFA0 (-96)  got $FF9E (-98)
    line   6 FG: expected $FFA0 (-96)  got $FF9D (-99)
    line   7 FG: expected $FFA0 (-96)  got $FF9D (-99)

[3] GREEN — the same checker, same RAM, the RAMP's own expectation
    GREEN as required: all 224 entries match the ramp expectation

[4] RESTORE — write the derived words back, re-check
    GREEN as required

[5] RESTORE BY THE WALKER — let it refill, re-derive from scratch
    GREEN as required: all 224 entries match after the walker refilled
```

Five things about that transcript are load-bearing:

1. **Step 0 is a control.** If the shipped state does not derive green, nothing below means
   anything and the arm exits without running the poison.
2. **Steps 2 and 3 run the SAME checker over the SAME RAM**, differing only in the expectation.
   That is what proves the checker is reading the buffer and not its own prior belief.
3. **The mismatch is NAMED** — line, channel, expected, got — not "something differed".
4. **434 of 448 words differ, not 448.** The 14 that match are the lines near the ramp's origin
   where the bow has not yet left the flat value. Reporting the honest count rather than
   rounding it up is the difference between a measurement and a claim.
5. **Step 5 removes the poison by letting the WALKER overwrite it**, and re-derives from
   scratch. A restore that only writes back what the tool expected would prove nothing about
   the machine.

The instrument has also gone red on its own account, unplanned: Stage A caught the torn-read
episode of section 3 by reporting `shadow band 1 top: derived 24, machine 0` before Stage B ever
compared a line. Both stages are known to fire.

---

## 6. The smoothness metric T10 inherits

Every arm prints per-line first differences of both channels, split into **band-interior** steps
and **band-edge** steps. A band boundary is a legitimate discontinuity — the two bands carry
different scroll factors — so folding edge steps into the same statistic would make any
multi-band config look rough and would hide a genuinely jagged curve inside one band.

Reported per channel: interior step count, non-zero count, **max |d1| (step)**, **max |d2|
(jerk)**, the d1 range, the full d1 histogram, and each band edge's step named by line.

`max |d2|` is there because a step bound alone is not a smoothness test: two spliced ramps of
equal step never exceed `|d1| = 2` and are still kinked, which
`test_second_difference_catches_a_kink_a_first_difference_bound_misses` pins.

**The baseline T10 moves off** (shipped `s4.debug.bin`, boot camera, config `$01230C`):

| channel | interior steps | non-zero | max \|d1\| | max \|d2\| | d1 histogram |
|---|---|---|---|---|---|
| FG | 220 | 0 | 0 | 0 | `{0: 220}` |
| BG | 220 | 35-37 | 1 | 2 | `{-1: ~19, 0: ~184, 1: ~17}` |

FG is flat everywhere (no FG table on this config). BG's motion is entirely the shimmer table at
shift 2 below the anchored split — amplitude 8 sampled at shift 2 can only step by 0 or +-1, and
it does exactly that. The non-zero count varies with the deform phase across camera positions;
the bounds do not.

---

## 7. Verification

| lane | result |
|---|---|
| `pytest tools` (the build.sh runner: `python3 -m pytest tools -q --no-header -p no:cacheprovider`) | **1177 passed, 3 skipped** — baseline 1143/3 in this worktree plus this parcel's 34, and the same total through `DEBUG=1 ./build.sh`, so the new file is wired to the build's own lane rather than run only by hand. `AEON_SKDISASM_DIR` must be set or 9 collision-importer tests fail on a missing donor, unrelated to this parcel |
| ROM bytes | **zero**, and checked on all four shapes rather than on sonic4 alone (the deb2-appendix trap: a zero-byte DEBUG-only label once moved `demo.bin` while `s4.bin` did not move at all). `s4.debug.bin` `2a482069`/714655 · `s4.bin` `aa30c5b4`/698760 · `demo.debug.bin` `e78af69e`/100785 · `demo.bin` `9b4c3df3`/96079. The identity is structural as well as measured: `git status` carries three **untracked additions** under `tools/` and `docs/` and no modification to any tracked file the build reads |
| determinism | three full `--arm all` runs, JSON output **byte-identical** (`runA == runB == runC`) |
| wall clock | ~30-34 s for `--arm all` (three headless boots), at load average 4.7-8.0 with parallel lanes running |
| arms | `frozen` PASS at 5 positions · `redfirst` PASS · `sweep` PASS (24 moving frames, Camera_X 112 -> 480) |

---

## 8. What Task 10 should do with this

- Add a curve fixture the way `parallax_cost_probe` adds a cost fixture — a config built in RAM
  with `Parallax_Current_Config` aimed at it — and extend `derive_hscroll` with the curve
  lowering's arithmetic. The checker, the reporting and the smoothness readout need no change.
- **The expectation must be extended, not relaxed.** If a curve lands and Stage B is edited to
  stop checking the lines it covers, the instrument has been converted into the thing it exists
  to prevent.
- Run `--arm sweep` too. The frozen arm cannot see a curve that only breaks under motion, and
  that is most of what a curve is for.
- The `--arm redfirst` ramp is a permanent self-test of the checker. If a future change makes
  step 2 go green, the checker stopped checking.
