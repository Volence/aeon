# The parallax walker's fitted cost model

**Parcel:** Scanline Services P2 Phase 0 Task 4 (original), **re-measured and superseded by
Scanline Services P3 Phase 0 Task 1, 2026-08-20.**
**Tool:** `tools/parallax_cost_probe.py`
**Instrument:** oracle (old), headless harness, per-routine profiler row.
**ROM:** `s4.debug.bin`, crc `2a482069`, len 714655, branch `measure/p3-t1-anchor-regimes` off
master `08e87cbc`.
**Sample:** 31 frames per fixture, **3 independent boots**, spread **0** on all 26 fixtures and
on the out-of-sample row. Every window verified **preemption-free (frames/tick 31/31, lag 0)**.
**Wall clock:** final run 2026-08-20T04:20:11-04:00 (`up 2 days, 4:44`, load 6.09) to 04:23:50
(`up 2 days, 4:47`, load 6.47) — **219 s** for 3 boots x 26 fixtures + 3 out-of-sample rows.
Reproduced 04:33:26 (`up 2 days, 4:57`, load 6.59) to 04:37:04 (`up 2 days, 5:00`, load 7.12) —
**218 s**, and **every fixture row byte-identical across the two sweeps** (6 independent boots
in total), same fitted coefficients to 1e-9, same 13.271684 max residual, zero derived-check
failures in both. Probe only; the build is separate.

`INSTRUMENT-PARITY.md`'s three standing caveats apply to every number here, **caveat 0 in
particular: these are IDEAL CYCLES.** Oracle's clock never receives bus, VDP or DMA stall time
(`M68000.cpp:1029-1031`). See §6 for what that costs this model specifically.

---

## 0. SUPERSESSION NOTICE — what P3 Task 1 changed, and why

> Read this before quoting any number from the P2 revision of this file. Three things changed,
> and the first invalidates every coefficient the P2 revision published.

**(a) Every P2 row was DILUTED, and the file said so without checking it.** §1 below already
carried the sentence "one logic tick spans two frames, and a per-frame average stops being one
call of the walker" — and then guarded it with the frozen camera alone. The per-routine row is a
per-**video-frame** average; a single lag frame inside the 31-frame window scales the whole
profile by ticks/frames. Measured: the window immediately after a fixture install ALWAYS lags,
and one window in ~four lags thereafter at the idle baseline. So the P2 sweep's rows were
`x 30/31`, and the fixtures whose windows caught two lag frames were `x 29/31`.

The proof is arithmetic, not assertion — every P2 coefficient divided by its P3 counterpart:

| coefficient | P2 | P3 (clean) | ratio | 30/31 = 0.96774 |
|---|---|---|---|---|
| `base` | 3021.94 | 3144.00 | 0.9612 | |
| `band_percell` | 746.94 | 772.00 | 0.9675 | ✓ |
| `band_perline` | 845.97 | 874.00 | 0.9679 | ✓ |
| `multiband` | 23.21 | 24.00 | 0.9671 | ✓ |
| `vdeform` | 1424.06 | 1472.00 | 0.9674 | ✓ |
| `line_fg_only` (at shift 3) | 76.21 | 78.75 | 0.9678 | ✓ |
| `line_both` (at shift 3) | 126.17 | 137.21 | **0.9195** | **29/31 = 0.9355** |

`line_both` is the outlier because it is excited by ONE fixture (W8), and W8's window caught two
lag frames. A column identified by a single point cannot show a residual — it absorbs whatever
distorted it. That is the same defect §5(b) is a postmortem for, arriving through the instrument
instead of through the parameterization.

**The probe now checks it.** `Frame_Counter` and `Logic_Tick` bracket the profiled window; the
window is re-taken (bounded) until they agree, and a fixture that cannot run preemption-free
FAILS. Found by a shift-value sweep whose per-line cost went **negative** from shift 3 to shift 4
and positive again — the full per-routine diff showed every unrelated row (`RunObjects`,
`TouchResponse`, `Tile_Cache_Fill`) down by exactly 30/31 and `VInt_Lag` up 167 → 423. The
machine had started lagging; the loop had not got cheaper.

**(b) §5(c)'s hypothesis is REFUTED, and the 748 it named was an artifact.** See §5(c) below,
rewritten in place. Short form: the "two regimes" were the dilution in (a) — W10/W12 were
`x 29/31` while the model fitted to them was `x 30/31` — plus a genuinely missing per-line term
(the deform SHIFT value, §4). Measured clean, the anchored overlay has one regime whose driver is
the overlay's own loop trip count.

**(c) Two parameters were missing and are now measured**: `shift_lines` (exactly 2.00 cyc per
line per shift unit) and `anchor_ops` (59.3 cyc per overlay loop iteration). `band_sampling` —
§5(c)'s named parameter — is now a fitted column too, and reads **exactly 0.00** on this loop
shape.

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

**The derived checks, every fixture, every boot** — the equivalent of `raster_cost_probe`'s
`calls`. Three in P2, five now, and every one of them can FAIL THE RUN (exit 5) rather than
print a warning:

1. `Parallax_Current_Config` still points at the fixture (nothing re-installed over it).
2. The fixture's bytes are unchanged (`Replay_Record_Idx` stayed 0 — the recorder never woke
   up and wrote through it).
3. **The split witness, now two-sided.** An anchored fixture can reach `.bands_ready` through the
   overlay's own early-outs and measure the early-out instead of the split — a gate asserting
   only "something ran".
   - *(3a, new)* Shadow slot `band_count` is **poisoned with `$FF`** before the window. Step 4a
     writes exactly `band_count` entries (`.copy_band`, dbf over d7); slot `band_count` is
     written by Step 4b's split and by nothing else. So an anchored fixture must overwrite it
     and an un-anchored one must leave it — a two-sided witness that needs no neighbour. The
     un-anchored half is what proves the poison reaches the machine at all.
   - *(3b, P2's)* the neighbour differential: an anchored fixture's shadow tops must differ from
     a same-band-count un-anchored fixture's. W24 was added so the 4-band anchored fixtures have
     a partner; a pair with mismatched band counts answers "the shapes differ", not "the split
     happened".
   - **Poisoned red-first (2026-08-20).** Setting W16's `pcfg_anchor_ch` to `$FF` exits 5 with
     `W16 vs W24: shadow tops IDENTICAL — no split`, and W16's row collapses 19932 → 7322.
     **The slot witness does not catch it** — with `anchor_ch = $FF` the fixture is legitimately
     un-anchored, so "slot still `$FF`" is the correct verdict for what the config now says.
     Only the neighbour differential sees that the fixture stopped being the thing it claims to
     measure. Neither witness is sufficient alone; that is why both are kept.
4. **(new) The window is preemption-free**: `Frame_Counter` and `Logic_Tick` bracket it and must
   agree, with `Lag_Frame_Count` unchanged. See §0(a) — this is the check whose absence made
   every P2 number 3.3% low. All 26 fixtures × 3 boots read **31/31, lag 0**.
5. **(new) The world anchor stayed poked** for the split-position fixture (W20 moves
   `Effects_World_Y[0]`, and the preset installer writes that bank).

**The camera is frozen and that is load-bearing for the arithmetic, not only for
reproducibility.** Under sustained motion the main loop overruns a video frame
(`ENGINE-BASELINE.md` §2), one logic tick spans two frames, and a per-frame average stops
being one call of the walker. **Freezing the camera is necessary and was not sufficient** — the
idle baseline lags on its own, roughly one window in four, which is what check 4 exists for.

## 2. The parameter set, and how it maps to the plan's names

The plan asks for per-layer, per-line-mode, per-curve, per-deform-ref and re-glue. Those are
the design doc's scene vocabulary; the walker that exists today has these cost axes, and they
correspond:

| plan's name | this walker | fixtures |
|---|---|---|
| per-layer | band count | W1/W2/W3 (per-cell), W5/W6/W24 (per-line) |
| per-line-mode | an H-deform table attached at all — this is what selects `Parallax_Fill_PerLine` over `_PerCell` AND flips reg `$0B` | W4 vs W0 |
| per-curve | deform SAMPLING running: a table attached AND `band_deform_shift != 15` | W7, W13, W8, W14, W15 |
| per-curve AMPLITUDE | the deform shift VALUE — `asr.w d3, d1` is a register-count shift, 6+2n | W22, W23 |
| per-curve BAND COUNT | how many bands take a sampling loop rather than `.lp_flat` | W25 |
| per-deform-ref | the V-deform table reference (per-column VSRAM instead of whole-plane) | W9 |
| re-glue | Step 4b's anchored overlay: it SPLITS a band and re-glues the shadow list one entry longer | W10, W12, W16-W21 |

A name with no fixture would be a fitted parameter nothing measured, which is the defect this
phase exists to avoid.

## 3. The fixtures

Each varies ONE thing from a named neighbour. Spread 0 across 3 boots on every row; every window
31 frames / 31 ticks, lag 0. **The P2 revision's numbers are superseded — see §0(a); the ones
below are preemption-free on ROM `2a482069`.**

| fix | bands | mode | sampled FG/BG/both | `Parallax_Update` | varies |
|---|---|---|---|---|---|
| W0 | 1 | per-cell | 0/0/0 | 3144 | the floor |
| W1 | 2 | per-cell | 0/0/0 | 3940 | band count vs W0 |
| W2 | 3 | per-cell | 0/0/0 | 4712 | band count vs W1 |
| W3 | 4 | per-cell | 0/0/0 | 5484 | band count vs W2 |
| W4 | 1 | per-line | 0/0/0 | 4692 | line mode vs W0 |
| W5 | 2 | per-line | 0/0/0 | 5590 | band count vs W4 |
| W6 | 3 | per-line | 0/0/0 | 6464 | band count vs W5 |
| W7 | 1 | per-line | 224/0/0 | 22332 | FG sampling vs W4 |
| W8 | 1 | per-line | 0/0/224 | 35428 | BG sampling vs W7 |
| W9 | 1 | per-cell | 0/0/0 | 4616 | V-deform table vs W0 |
| W10 | 2 | per-line | 224/0/0 | 24508 | anchored overlay vs W5 |
| W11 | 1 | per-line | 0/0/0 | 4692 | deform SPEED vs W4 — **the control** |
| W12 | 3 | per-line | 224/0/0 | 25440 | band count vs W10 |
| W13 | 1 | per-line | 0/224/0 | 22346 | BG-ONLY sampling vs W4 |
| W14 | 2 | per-line | 112/0/0 | 14410 | sampled LINES vs W7 |
| W15 | 3 | per-line | 80/0/0 | 12764 | sampled LINES vs W14 |
| W16 | 4 | per-line | 0/144/0 | 19932 | anchor-DRIVEN sampling vs W12 — the shipped shape |
| **W17** | 2 | per-line | 0/144/0 | 17944 | band count vs W16, sampled lines held at 144 |
| **W18** | 4 | per-line | 0/0/0 | 8826 | overlay writes FLAT shifts vs W16 |
| **W19** | 4 | per-line | 144/0/0 | 19898 | channel vs W16 (BG → FG) |
| **W20** | 4 | per-line | 0/128/0 | 18704 | split POSITION vs W16 (world anchor +16 px) |
| **W21** | 2 | per-line | 0/0/0 | 6856 | band count vs W18 — the 2×2's fourth cell |
| **W22** | 1 | per-line | 224/0/0 | 21884 | deform SHIFT VALUE vs W7 (3 → 2) |
| **W23** | 1 | per-line | 224/0/0 | 23228 | deform SHIFT VALUE vs W22 (2 → 5) |
| **W24** | 4 | per-line | 0/0/0 | 7338 | band count vs W6 |
| **W25** | 2 | per-line | 224/0/0 | 23230 | sampling BANDS vs W14 (1 → 2) |

**W11 is still a clean control:** advancing the deform phase accumulators costs **exactly 0** —
4692, byte-for-byte W4's figure.

**W20 is a second control, and an unusually strong one.** Moving the world anchor +16 px moves
the realized split 80 → 96 and the sampled-line count 144 → 128, and its overlay cost lands
within **1 cycle** of W16's. The split POSITION is free; only what it implies about the line
counts is not. That is `sampled_lines(split)` validating itself against a state it was not
tuned on.

## 4. The model

```
cycles =  base
        + band_percell x (bands - 1)                    [per-cell mode]
        + line_mode + band_perline x (bands - 1)        [per-line mode]
        + multiband                                     [once, at bands >= 2]
        + line_fg_only x LINES                          [at deform shift 0]
        + line_bg_only x LINES                          [at deform shift 0]
        + line_both    x LINES                          [at deform shift 0]
        + shift_lines  x SUM(shift over sampled channel-lines)
        + band_sampling x (bands taking a sampling loop)
        + vdeform                                       [a V-deform table attached]
        + anchor + anchor_ops x (overlay loop trips)    [see §5]
```

Fitted over the **18 un-anchored fixtures**, exact least squares, **max |residual| = 0.00
cycles** — not "0.3, which is rounding", but exactly zero to the printed precision:

| parameter | cycles | what it is |
|---|---|---|
| `base` | **3144.00** | 1 band, per-cell, nothing on |
| `band_percell` | **772.00** | each band past the first, per-cell |
| `line_mode` | **1548.00** | attaching an H-deform table at all |
| `band_perline` | **874.00** | each band past the first, per-line |
| `multiband` | **24.00** | once, at bands >= 2, in BOTH modes |
| `line_fg_only` | **72.75** | one screen line sampling the FG curve, at shift 0 |
| `line_bg_only` | **72.81** | one screen line sampling the BG curve, at shift 0 |
| `line_both` | **125.21** | one screen line sampling BOTH, at shift 0 |
| `shift_lines` | **2.00** | per line, per unit of deform shift, per channel |
| `band_sampling` | **-0.00** | §5(c)'s parameter — exactly zero on THIS loop shape |
| `vdeform` | **1472.00** | a V-deform table attached (per-column VSRAM) |

**`shift_lines = 2.00` is a derived constant the fixtures happened to confirm exactly, which is
the strongest form this file has produced.** The sampled line loops end in `asr.w d3, d1` — a
REGISTER-count shift, `6 + 2n` cycles on the 68000. Two independent steps, both over 224 lines:

| | shift step | marginal | per line per shift unit |
|---|---|---|---|
| W7 − W22 | 2 → 3 | 448 | **2.0000** |
| W23 − W7 | 3 → 5 | 896 | **2.0000** |

The P2 revision had no such column, so its per-line coefficients were the shift-3 values dressed
as constants — and the shipped config samples at shift **2**, which is where that error went
(§5(c)). At shift 3 the FG per-line cost is `72.75 + 3x2 = 78.75`, which is what P2's diluted
76.21 corresponds to (`78.75 x 30/31 = 76.21`).

**Whole-model fit, all 26 fixtures including the anchored ones and both anchor columns:
max |residual| = 13.3 cycles (0.04% of the largest fixture)** — down from the P2 revision's
195.9. The anchored fixtures are no longer a separate story with a separate table.

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

### (c) `anchor` — the P2 "two regimes" were an ARTIFACT. **REFUTED 2026-08-20, P3 Task 1.**

> **What P2 recorded, kept verbatim so the correction has a subject.** Including the three
> anchored fixtures took max |residual| from 0.27 to 195.9, and the overlay's cost over the
> un-anchored model read **W10 +456.7, W12 +455.7, W16 +1204.7** — the first two agreeing to one
> cycle and the third **749 dearer**. P2 named the cause as the overlay "changing the filler's
> LOOP TYPE at the split", and the suspected missing parameter as *"a per-band cost that DIFFERS
> between a flat band and a sampling band... collinear with `band_perline` in every un-anchored
> fixture (they all have uniform band types)"*. It was deliberately not fitted, and two labelled
> regimes went into the toml instead.

**The premise is false on its own fixture set.** W14 and W15 are NOT uniform-band-type: W14 is
2 bands with only the lower sampling, W15 is 3 with only the lowest. Each marginal over the
matching no-sampling fixture is `(c_sampling_band − c_flat_band) + LINES x line_fg_only`, so
differencing two of them isolates the per-line slope and back-substitution isolates the band-type
delta. On the preemption-free rows it comes out **exactly zero**, three times:

```
W7  − W4 = 22332 − 4692 = 17640   over 224 sampled lines
W14 − W5 = 14410 − 5590 =  8820   over 112 sampled lines
W15 − W6 = 12764 − 6464 =  6300   over  80 sampled lines
line_fg_only(at shift 3) = (17640 − 8820) / 112 = 78.7500
  W7  band-type delta = 17640 − 224 x 78.75 = +0.00
  W14 band-type delta =  8820 − 112 x 78.75 = +0.00
  W15 band-type delta =  6300 −  80 x 78.75 = +0.00
```

W25 confirms it directly rather than by differencing: it turns W14's upper band on too, taking
the sampling-band count 1 → 2 at +112 lines, and costs `23230 − 14410 = 8820 = 112 x 78.75`
exactly — **the second sampling band is free.** `band_sampling` is now a fitted column and reads
**-0.00**.

**So what WAS the 749?** Two instrument defects and a real, much smaller effect, and the
reconstruction is exact. W10 and W12's windows caught **two** lag frames (`x 29/31`) while the
un-anchored model they were scored against was fitted on `x 30/31` rows; and W16 samples at
deform shift **2** while P2's per-line coefficients were measured at shift 3, so it was
over-charged. Feeding the clean model back through both distortions reproduces the published
numbers:

| fixture | clean overlay cost | reconstruct at P2's dilution + P2's model | P2 published |
|---|---|---|---|
| W10 | **+1278.0** | `24508 x 29/31 − 22480.2` = +446.7 | +456.7 |
| W12 | **+1336.0** | `25440 x 29/31 − 23326.1` = +472.6 | +455.7 |
| W16 | **+1533.0** | `19932 x 30/31 − 18084.0` = **+1205.1** | **+1204.7** |

W16 to **0.4 cycles**. The "second regime" was W10/W12 losing ~790 cycles of apparent overlay to
an extra lag frame, partly offset by W16 losing ~280 to the missing shift term.

**The 2×2 that settles it.** Four cells crossing band count against whether the overlay changes
the filler's loop type at the split (turn-on = ROM bands flat, `pcfg_anchor_dsb` switches BG
sampling on below the split; flat overlay = the overlay writes 15 and nothing samples):

|  | 2 bands | 4 bands | band-count effect |
|---|---|---|---|
| overlay CHANGES loop type | W17 **+1293** | W16 **+1533** | **+240** |
| overlay changes none | W21 **+1266** | W18 **+1488** | **+222** |
| loop-type effect | **+27** | **+45** | |

W17 is constructed so the sampled-line count is identical to W16's (2 bands top at 0/112, 4 at
0/56/112/168, and with the split at 80 both sample lines 80..224 = 144), so that column varies
band count **alone**. The verdict is unambiguous: **the loop-type change costs 27-45 cycles, not
749. Band count costs 222-240 over 2 → 4.** Channel is +25 (W19 vs W16); split position is +1
(W20 vs W16).

**The anchor is now FITTED, with a name and a mechanism.** Its driver is the overlay's own loop
trip counts, which are a function of the band count `n` and the index `k` of the band the split
lands in and nothing else (`engine/level/parallax.emp:889-987`): `.anchor_find_k` runs
`min(k+1, n-1)` times, `.anchor_shift_band` and `.anchor_shift_scroll` run `n-1-k` each (skipped
at 0), and the `.anchor_shift_write` override walk runs `n-k`. Summing them:

```
anchor = 982.2 + 59.27 x overlay_loop_trips        max |residual| 27.6 cycles over 8 fixtures
```

| fixture | trips | measured | model | residual |
|---|---|---|---|---|
| W21 | 5 | +1266.0 | +1278.5 | −12.5 |
| W10 | 5 | +1278.0 | +1278.5 | −0.5 |
| W17 | 5 | +1293.0 | +1278.5 | +14.5 |
| W12 | 6 | +1336.0 | +1337.8 | −1.8 |
| W18 | 9 | +1488.0 | +1515.6 | −27.6 |
| W19 | 9 | +1508.0 | +1515.6 | −7.6 |
| W16 | 9 | +1533.0 | +1515.6 | +17.4 |
| W20 | 9 | +1534.0 | +1515.6 | +18.4 |

**ONE lumped count and not four columns, deliberately.** Four columns would need four independent
`(n, k)` classes; this fixture set has three — `(2,0)`, `(3,1)`, `(4,1)` — so a four-column fit
would be exactly identified and its residual zero by construction, which is the defect §5(b) is a
postmortem for. The lumped form asserts the weaker, testable claim that the four loops cost about
the same per iteration: it fits **59.3 cycles**, against a hand count of **62** for the
`.anchor_find_k` body.

**And the residual it leaves is not noise — it is the loop-type effect, unfitted on purpose.**
±27.6 cycles, and it orders exactly as the 2×2 says it should: flat-overlay cells low (W21 −12.5,
W18 −27.6), FG-sampling in the middle (W19 −7.6), BG-sampling high (W17 +14.5, W16 +17.4, W20
+18.4). One fixture pair per cell is not enough to fit a column, so it is recorded here with its
measured magnitudes and left in the residual.

### (d) Carried forward: `band_sampling` is real on OTHER loop shapes

`band_sampling = 0.00` is a property of **this** filler, not of the walker forever. The parallax
fill-unroll parcel (branch `perf/parallax-unroll`, unmerged at the time of writing) halves the
per-line sampling marginals by unrolling the sampled loops, which moves work out of the per-line
body and into the per-band prologue — and it measures the SAME column at a **~149-cycle** class,
restoring its residual. Its pre-unroll value on its own base is **0.59**, which agrees with the
0.00 measured here to within its own rounding.

Two parcels reached the same physical cost from opposite directions, which is the strongest
identification either could get: **a per-sampling-band setup cost that is ~0 on the un-unrolled
filler and ~149 once the loops are unrolled.** The column now exists in the model with a measured
value on this shape, so the unroll parcel re-measures a named row instead of introducing one.
Note the regime this file's numbers belong to: **pre-unroll master `08e87cbc`**.

## 6. Out-of-sample: does it predict the shipped config?

**The probe measures this itself now** — one extra pass per boot with NOTHING poked but the
camera freeze, reading whichever config the section under that camera installed. It is
`ParallaxConfig_OJZ_Underwater` at `$01230C`, not `ParallaxConfig_OJZ_Default`, so this row is
the only test of the model the fixture set could not have been tuned to pass.

Its shape, read from the running machine:

- 4 authored bands, anchored on channel 0, latched L = **80**, transition frames 0
- shadow view, 5 bands, `(top, dsa, dsb)`:
  `[(0,15,15), (48,15,15), (80,15,2), (112,15,2), (224,15,2)]` — split slot poison overwritten
- split band `k = 1`, overlay trips 9; **BG samples the 144 lines below the split, at shift 2**

| | cycles |
|---|---|
| model (all 13 fitted terms) | 19915.3 |
| measured `Parallax_Update`, 3 boots, spread **0**, 31/31 frames/ticks | **20162** |
| gap | **+246.7 (1.22%)** |

**The terms are read from the SHADOW VIEW, not re-derived from the ROM entries, and that is a
correction this task made.** The fixtures pin `v_factor_bg` to 15, so Step 4a's rotation is the
identity and a fixture's ROM tops *are* its shadow tops. The shipped config does not pin it: its
tops are rotated by `Vscroll_BG >> 3` and clamped at 28 cells. Scoring it off its ROM entries put
the split at line 48 when the latch and the shadow view both say 80. Reading the filler's actual
inputs is strictly better evidence than re-deriving two engine steps in Python and hoping they
agree.

The remaining +1.22% is the shipped config's own band tops and scroll-factor shifts, which change
the `Decode_Factor_A/B` work the fixtures hold constant. Recorded, not tuned away — and it is
essentially the same fraction the P2 revision reported (+1.1%), which is the honest reading: this
task did not improve the out-of-sample gap, it made the in-sample residual mean something.

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
  predicting it. **W20 partially lifts this**: it moves the split without moving the camera (by
  poking `Effects_World_Y[0]`, which `Effects_LatchWorldLines` re-derives L from), and shows the
  split position itself costs 1 cycle. What is still uncovered is a camera that moves the band
  tops and scroll factors as well.
- **One loop shape.** Every coefficient here is measured on the **un-unrolled** per-line filler
  at master `08e87cbc`. `band_sampling` in particular is 0 on this shape and ~149 on the unrolled
  one — see §5(d). A model coefficient is a property of the code it was measured against, and
  this file's clean-constant trap has now bitten twice.
- **`v_factor_bg` is pinned to 15 (locked) in every fixture**, so Step 5's vscroll lerp is
  skipped throughout and its cost is inside `base`, not resolved. A config that lerps is
  unmeasured.
- **Transitions are off** (`Parallax_Transition_Frames` = 0). A mid-transition frame drives from
  `Target_Config` and runs a per-band scroll lerp; unmeasured, and it is design §5's transition
  frame, i.e. Task 12's subject.
- **Ideal cycles** — see §7.
- **`anchor` is now gateable; `band_sampling` is the weak term.** P2 said "`anchor` has two
  regimes, three data points, and a named unmodelled parameter — do not build a gate on it
  without more fixtures." It now has **eight** fixtures across three overlay-trip counts, one
  regime, and a residual of ±27.6 cycles whose sign pattern is itself explained (§5(c)). A gate
  on `anchor + anchor_ops` is supportable at that tolerance. What is NOT gateable is
  `band_sampling`: it reads 0 here and ~149 on the unrolled filler, so any budget that leans on
  it must name the loop shape it was measured against.
- **`multiband` = 24 is solid** — fitted over many fixtures, and Task 7 of the P3 plan rewrites
  the `.find_k` loop that produces it, so it is due for re-measurement rather than carrying.

---

## 9. P3 Task 1 — what to re-run, and the exit codes

```bash
python3 tools/parallax_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 3 \
        --out /tmp/walker.json
```

Exit 0 = every derived check passed. Exit 5 = a derived check FAILED and **the cycle rows in that
run are not evidence** — the run prints which fixture and which check. Exit 3 = ROM or symbol
precondition. Exit 4 = too few fixtures to fit.

The run takes ~220 s for 3 boots x 26 fixtures on an otherwise-idle machine. **If it takes ten
times that, look for an orphaned `oracle_gui`** — a killed probe run leaves its headless emulator
spinning at ~300% CPU, and it does not stop on its own. `pgrep -a -f oracle-old/linux-port/build`
and kill the stale PID; the sweep this file was measured on went from 43+ minutes to 3.5 the
moment one was cleared.

---

## 10. RE-FIT after (landed after T1; regime column per §5(c)/§8) `perf/parallax-unroll` (2026-08-20) — the model used as a regression net

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
