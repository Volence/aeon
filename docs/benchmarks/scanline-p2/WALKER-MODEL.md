# The parallax walker's fitted cost model

**Parcel:** Scanline Services P2, Phase 0, Task 4.
**Tool:** `tools/parallax_cost_probe.py`
**Instrument:** oracle (old), headless harness, per-routine profiler row.
**ROM:** `s4.debug.bin`, crc `d22dda85`, branch `measure/scanline-p2-phase0` off master `18af84f3`.
**Sample:** 31 frames per fixture, **3 independent boots**, spread **0** on all 17 fixtures.
**Wall clock:** final run 2026-08-19T15:20:44-04:00 (`up 1 day, 15:44`, load 6.36) to 15:22:58
(`up 1 day, 15:46`, load 5.82) — **134 s** for 3 boots x 17 fixtures. Probe only; the build is
separate.

`INSTRUMENT-PARITY.md`'s three standing caveats apply to every number here, **caveat 0 in
particular: these are IDEAL CYCLES.** Oracle's clock never receives bus, VDP or DMA stall time
(`M68000.cpp:1029-1031`). See §6 for what that costs this model specifically.

---

## 1. What is measured, and how a fixture exists at all

**Response variable:** `Parallax_Update`'s per-routine row, **inclusive of its callees**.
Verified on this ROM rather than assumed: `Parallax_Update` 19511 contains
`Parallax_Fill_PerLine` 14866 plus `Decode_Factor_A/B` 766, and
`GameState_OJZScroll_Update` 35125 contains all of it. One row is therefore the whole walker,
which is the quantity design §5 axis 1 budgets.

**Fixture installation — no ROM bytes, no rebuild, no engine hook.** A parallax config is a
28-byte header plus a `band_entry` array reached through ONE RAM pointer, so a fixture is a
config built in RAM with the pointer aimed at it — `raster_cost_probe`'s trick in a different
module:

| poke | why |
|---|---|
| `Debug_Scene_Freeze = 1` | camera pinned, so `Parallax_CheckBoundary` (edge-triggered on the section under the camera) never fires and cannot install a real config over the fixture |
| `Parallax_Transition_Frames = 0` | forces `Parallax_Update`'s `.use_current` arm; a live transition would drive from `Target_Config` |
| `Parallax_Target_Config = 0` | as above |
| `Parallax_Current_Config = &Replay_Record_Buf` | the fixture |

The scratch is `Replay_Record_Buf` — 8 KB, DEBUG-shape only, inert unless the replay recorder
is recording. Every fixture is a MUTATION of the shipped `ParallaxConfig_OJZ_Default` bytes
rather than a header invented here, so each one is a single edit away from something real.

**Three derived checks, every fixture, every boot** — the equivalent of `raster_cost_probe`'s
`calls`:

1. `Parallax_Current_Config` still points at the fixture (nothing re-installed over it).
2. The fixture's bytes are unchanged (`Replay_Record_Idx` stayed 0 — the recorder never woke
   up and wrote through it).
3. `Parallax_Shadow_Bands` tops are read back, and the anchored fixtures must show a DIFFERENT
   top sequence from their un-anchored neighbours. Without this an anchored fixture can reach
   `.bands_ready` through the overlay's own early-outs and measure the early-out instead of the
   split — a gate asserting only "something ran". Both anchored pairs differ; the split
   happened.

**The camera is frozen and that is load-bearing for the arithmetic, not only for
reproducibility.** Under sustained motion the main loop overruns a video frame
(`ENGINE-BASELINE.md` §2), one logic tick spans two frames, and a per-frame average stops
being one call of the walker.

## 2. The parameter set, and how it maps to the plan's names

The plan asks for per-layer, per-line-mode, per-curve, per-deform-ref and re-glue. Those are
the design doc's scene vocabulary; the walker that exists today has these cost axes, and they
correspond:

| plan's name | this walker | fixtures |
|---|---|---|
| per-layer | band count | W1/W2/W3 (per-cell), W5/W6 (per-line) |
| per-line-mode | an H-deform table attached at all — this is what selects `Parallax_Fill_PerLine` over `_PerCell` AND flips reg `$0B` | W4 vs W0 |
| per-curve | deform SAMPLING running: a table attached AND `band_deform_shift != 15` | W7, W13, W8, W14, W15 |
| per-deform-ref | the V-deform table reference (per-column VSRAM instead of whole-plane) | W9 |
| re-glue | Step 4b's anchored overlay: it SPLITS a band and re-glues the shadow list one entry longer | W10, W12, W16 |

A name with no fixture would be a fitted parameter nothing measured, which is the defect this
phase exists to avoid.

## 3. The fixtures

Each varies ONE thing from a named neighbour. Spread 0 across 3 boots on every row.

| fix | bands | mode | sampled lines FG/BG/both | `Parallax_Update` | varies |
|---|---|---|---|---|---|
| W0 | 1 | per-cell | 0/0/0 | 3022 | the floor |
| W1 | 2 | per-cell | 0/0/0 | 3792 | band count vs W0 |
| W2 | 3 | per-cell | 0/0/0 | 4539 | band count vs W1 |
| W3 | 4 | per-cell | 0/0/0 | 5286 | band count vs W2 |
| W4 | 1 | per-line | 0/0/0 | 4540 | line mode vs W0 |
| W5 | 2 | per-line | 0/0/0 | 5409 | band count vs W4 |
| W6 | 3 | per-line | 0/0/0 | 6255 | band count vs W5 |
| W7 | 1 | per-line | 224/0/0 | 21611 | FG sampling vs W4 |
| W8 | 1 | per-line | 0/0/224 | 32801 | BG sampling vs W7 |
| W9 | 1 | per-cell | 0/0/0 | 4446 | V-deform table vs W0 |
| W10 | 2 | per-line | 224/0/0 | 22937 | anchored overlay vs W5 |
| W11 | 1 | per-line | 0/0/0 | 4540 | deform SPEED vs W4 — **the control** |
| W12 | 3 | per-line | 224/0/0 | 23782 | band count vs W10 |
| W13 | 1 | per-line | 0/224/0 | 21625 | BG-ONLY sampling vs W4 |
| W14 | 2 | per-line | 112/0/0 | 13945 | sampled LINES vs W7 |
| W15 | 3 | per-line | 80/0/0 | 12352 | sampled LINES vs W14 |
| W16 | 4 | per-line | 0/144/0 | 19289 | anchor-DRIVEN sampling vs W12 — the shipped shape |

**W11 is a clean control:** advancing the deform phase accumulators costs **exactly 0** — it
reads 4540, byte-for-byte W4's figure.

## 4. The model

```
cycles =  base
        + band_percell x (bands - 1)                    [per-cell mode]
        + line_mode + band_perline x (bands - 1)        [per-line mode]
        + multiband                                     [once, at bands >= 2]
        + line_fg_only x LINES
        + line_bg_only x LINES
        + line_both    x LINES
        + vdeform                                       [a V-deform table attached]
        + anchor                                        [see §5 — NOT a constant]
```

Fitted over the **14 un-anchored fixtures**, exact least squares, **max |residual| = 0.27
cycles**:

| parameter | cycles | what it is |
|---|---|---|
| `base` | **3021.94** | 1 band, per-cell, nothing on |
| `band_percell` | **746.94** | each band past the first, per-cell |
| `line_mode` | **1518.02** | attaching an H-deform table at all |
| `band_perline` | **845.97** | each band past the first, per-line |
| `multiband` | **23.21** | once, at bands >= 2, in BOTH modes |
| `line_fg_only` | **76.21** | one screen line sampling the FG curve |
| `line_bg_only` | **76.27** | one screen line sampling the BG curve |
| `line_both` | **126.17** | one screen line sampling BOTH |
| `vdeform` | **1424.06** | a V-deform table attached (per-column VSRAM) |

0.27 cycles against measurements that are integers and a fit that is real-valued: this is
rounding, not structure. The model is 0-residual for the un-anchored walker.

## 5. THE RESIDUAL IS THE DELIVERABLE — three times it forced a change

The plan says a non-zero residual must name its missing parameter or be recorded unexplained,
never smoothed. It happened three times, and each time the fit was ALREADY good before the
point that broke it. That is the part worth carrying forward: a perfect fit over a fixture set
that cannot see a parameter is not evidence the parameter is absent.

### (a) `multiband` — 9.2 cycles, named

The first fit (per-band slopes only) left max |residual| 9.2, and the SIGN PATTERN named it:
the 1 -> 2 band step measured 770 per-cell and 869 per-line, while every later step measured
747 and 846. A constant **+23 paid once, on the first extra band, in both modes**.

That is Step 4a's `.find_k` probe loop: at `band_count` 1 the `cmp.w d7, d2` with `d2 = d7 = 1`
branches straight to `.found_k` and the loop body never runs. An indicator column is the honest
shape for a cost like that; a per-band slope forced to absorb it is what produced the residual.
Residual after: 0.3.

### (b) sampling is PER LINE, not per channel — 1702.7 cycles, named

The second fit had per-channel indicators and fitted W0..W12 to 0.3 cycles while saying the FG
channel costs 17071 and the BG channel 11190 — a **53% asymmetry between two channels doing the
same work**. Nothing in the fixture set contradicted it, so the fit was perfect and the model
was wrong.

**W13 (BG-only sampling) contradicted it**: 21625 against W7's 21611, i.e. the channels are
within 14 cycles of each other. Max |residual| blew up 0.3 -> 1702.7 the moment that point
entered — the model failing usefully.

**W14/W15 then fixed the unit.** They sample only their LOWER band, 112 and 80 lines, which
separates "the channel is on" from "224 lines sample" — collinear until then, because every
earlier fixture sampled all bands or none. The marginal costs over the matching no-sampling
fixture:

| | lines | marginal | per line |
|---|---|---|---|
| W7 − W4 | 224 | 17071 | **76.21** |
| W14 − W5 | 112 | 8536 | **76.21** |
| W15 − W6 | 80 | 6097 | **76.21** |

Linear in lines, to two decimal places, with **no fixed transition term at all**. The
`sample_any` = 5895 the previous parameterization produced was an artifact of its own shape.

**And the third column, `line_both`, is why two are not enough.** One FG line is 76.21 and one
BG line 76.27, but a line sampling BOTH is **126.17, not 152.5**. The per-line loop shares its
index and phase work across the planes, so the second channel on the same line costs 50 rather
than 76. Two columns cannot express that, and a two-column fit left a 5895-cycle residual
sitting entirely on the one fixture where both channels are live.

### (c) `anchor` is NOT a constant — 195.9 cycles, NAMED BUT NOT FITTED

Including the three anchored fixtures takes max |residual| from 0.27 to **195.9**. Re-fitting
without them separates a model that IS zero-residual from an overlay term that is not constant.
The overlay's measured cost over the un-anchored model, per fixture:

| fixture | bands | sampled | split line | overlay cost |
|---|---|---|---|---|
| W10 | 2 | FG, all 224 lines | 80 | **+456.7** |
| W12 | 3 | FG, all 224 lines | 80 | **+455.7** |
| W16 | 4 | BG, 144 lines, **turned on BY the anchor** | 80 | **+1204.7** |

The first two agree to **one cycle**. The third is **749 dearer**, and W16 is the one with the
shipped shape: `ParallaxConfig_OJZ_Underwater`'s four ROM bands all say 15 (no deform) and the
anchor's `pcfg_anchor_dsb` is what switches BG sampling on below the split. So in W10/W12 the
overlay merely re-writes shifts the bands already carried, while in W16 it changes the filler's
LOOP TYPE at the split — bands above take `.lp_flat`, bands below take the sampling loop.

**The suspected missing parameter, named:** a per-band cost that DIFFERS between a flat band and
a sampling band. It is collinear with `band_perline` in every un-anchored fixture (they all have
uniform band types), which is exactly why nothing there could see it.

**Deliberately NOT fitted.** A column excited by a single fixture would drive the residual to
zero without evidence and would be indistinguishable from a wrong value — the defect this whole
phase exists to avoid. Two regimes are recorded in the toml instead
(`anchor_cycles_reglue_only`, `anchor_cycles_shipped_shape`) with the status field saying so.

## 6. Out-of-sample: does it predict the shipped config?

The config actually live at the idle baseline is **`ParallaxConfig_OJZ_Underwater`**, not
`ParallaxConfig_OJZ_Default` — checked by reading `Parallax_Current_Config` on the running
machine. Its shape, from the shadow view at that camera:

- 4 authored bands, anchored on channel 0, split latched at **screen line 80**
- ROM band shifts all 15; `pcfg_anchor_dsb` = 2, so **BG samples the 144 lines below the split**
- shadow view: 5 bands — `[0, 48, 80, 112, 224]`, with dsb 15/15/2/2/2

| | cycles |
|---|---|
| model (un-anchored terms + `anchor_cycles_shipped_shape`) | 19288.7 |
| measured `Parallax_Update` at the idle baseline | **19511** |
| gap | **+222.3 (1.1%)** |

The remaining gap is the shipped config's own band tops and scroll-factor shifts, which change
the `Decode_Factor_A/B` work the fixtures hold constant. Recorded, not tuned away.

**This check is why the per-line unit exists at all.** The per-channel model predicted **7100**
for the same config against a measured 19511 — off by 12411 — because it scored an anchored
config's ROM band entries as "no sampling" and could not express a partial screen. The failure
was only visible out of sample.

## 7. Carried finding: nominal timings near VDP ports

The standing expectation was that nominal 68000 timings **over-predict** near VDP-port writes,
and that this model would show it. **It does not, and the reason is the instrument, not the
walker.** Oracle's cycle clock excludes bus and VDP stall entirely
(`INSTRUMENT-PARITY.md` caveat 0), so a port write costs its nominal cycles here by
construction. This model is therefore an **ideal-cycle** model: correct for CPU work, blind to
the stall a real bus would add on the HScroll buffer writes and the reg `$0B` assertion.

Booked rather than assumed away. Re-taking these fixtures on an instrument that counts stall —
oracle-next's profiler, whose v1 rows carry `stallCycles` per routine — is what would answer it,
and it is the same migration path caveats 0 and 2 already name.

## 8. What this model does NOT cover

- **One camera state.** Frozen at the idle baseline (OJZ act 1 section 0, `Camera_X` 96,
  `Camera_Y` 144). The split line L = 80 is a property of THAT camera; an anchored config's
  sampled-line count moves with the camera, and the model takes L as an input rather than
  predicting it.
- **`v_factor_bg` is pinned to 15 (locked) in every fixture**, so Step 5's vscroll lerp is
  skipped throughout and its cost is inside `base`, not resolved. A config that lerps is
  unmeasured.
- **Transitions are off** (`Parallax_Transition_Frames` = 0). A mid-transition frame drives from
  `Target_Config` and runs a per-band scroll lerp; unmeasured, and it is design §5's transition
  frame, i.e. Task 12's subject.
- **Ideal cycles** — see §7.
- **`multiband` and `anchor` are the two weakest terms.** `multiband` is 23 cycles fitted over
  many fixtures and solid; `anchor` has two regimes, three data points, and a named unmodelled
  parameter. Do not build a gate on `anchor` without more fixtures.

---

## 9. RE-FIT after `perf/parallax-unroll` (2026-08-20) — the model used as a regression net

The streaming arc's coda parcel rewrote the two SINGLE-CHANNEL sampling loops
(`.band_fg_only`, `.lp_bg`) — pointer-walk sampling, an unpacked base-scroll register, and an
8x unroll. `.lp_both` and `.lp_flat` were left alone deliberately, so their terms are
CONTROLS. The P3 standing rule is that a parcel lands at unchanged parameters except the ones
it changes; this is that check. Same fixtures, same probe, `s4.debug.bin` crc `5be03175`,
3 boots, spread 0.

| parameter | before | after | delta | |
|---|---|---|---|---|
| `base` | 3021.95 | 3021.88 | −0.07 | unchanged |
| `band_percell` | 746.95 | 746.88 | −0.07 | unchanged |
| `line_mode` | 1518.05 | 1518.14 | +0.09 | unchanged |
| `band_perline` | 845.89 | 845.70 | −0.19 | unchanged |
| `multiband` | 23.16 | 23.41 | +0.25 | unchanged |
| `line_both` | 126.17 | 126.07 | −0.10 | **CONTROL — the untouched loop held** |
| `vdeform` | 1424.05 | 1424.12 | +0.07 | unchanged |
| `line_fg_only` | 76.21 | **30.97** | **−45.24** | the parcel's subject |
| `line_bg_only` | 76.27 | **31.84** | **−44.43** | the parcel's subject |
| `samp_band` | 0.59 | **148.91** | **+148.32** | NEW — see below |

Predicted from instruction timings before measuring: 43.25 cycles per sampled line against a
13.25-cycle flat line, i.e. a marginal **30.0**. Measured 30.97 and 31.84. The prediction was
made on nominal 68000 timings and it held to ~1.5 cycles, which is worth recording given the
standing warning about nominal math near VDP ports — §7 explains why it holds *here*: this
instrument does not count stall, so nominal is what it measures by construction.

### The residual named §5(c)'s missing parameter into existence

Run against the SHIPPED nine-parameter model, the un-anchored max |residual| goes
**0.27 → 42.45**. That is not noise and it was not smoothed. Adding ONE column — a fixed cost
a single-channel SAMPLED band pays and a flat band does not — returns it to **0.38**, and
(the part that matters) returns every other coefficient to its pre-parcel value, as the table
above shows.

**That column is exactly the parameter §5(c) already named and deliberately declined to fit:**
"a per-band cost that DIFFERS between a flat band and a sampling band ... collinear with
`band_perline` in every un-anchored fixture". Two things changed:

1. **It became visible.** W14/W15 (one sampled band among two and three) are the fixtures that
   break the collinearity, and they were added for a different reason. Fitted on the BEFORE
   numbers the coefficient is **0.59 cycles** — the old sampling loop had essentially no
   per-band setup, which is why it hid inside the 0.27 residual for a whole parcel.
2. **The parcel made it large.** The new loop hoists a walk pointer, a base-scroll register,
   a wrap split and the group/tail control out of the line body — the whole point — and that
   is a ~149-cycle fixed price per sampled band. Predicted from the instruction sequence:
   ~156. It is a real cost and it belongs in the model.

The break-even is **149 / 44.5 ≈ 3.3 lines**: any sampled band taller than four scanlines is
ahead, and the shipped shapes sample 144 and ~176.

**Not folded into `tools/parallax_cost_probe.py`.** The tool's `PARAMS`/`design_row` are the
subject of P3 Task 1's anchor work and this parcel does not own them; the re-fit above is an
offline least-squares over the tool's own printed measurements. **Ask, for whoever next edits
the tool: add `samp_band` as a tenth column.** Until then the tool will keep printing a
~42-cycle un-anchored residual on any ROM carrying this fill, and that number is explained
here rather than mysterious. Note also that the residual should now be read at
`|residual| ≈ 42` as the healthy state, not 0.27.
