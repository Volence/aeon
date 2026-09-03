# `OP_RUN_RAMP` — the first COMPUTED per-line raster values in this engine

**Date:** 2026-08-14 · **Emulator:** oracle (Exodus-derived) · **Shape:** `DEBUG=1`
**Fixture:** `OJZ_TestRamp`, bound to OJZ act 1 section 0 so it is on screen at spawn.

## What it proves

Every dense effect before this streamed three baked words per line from ROM
(`OP_RUN_GRADIENT`), so it could not change without rebuilding the data — every dense effect was
a fixture, never a preset. `OP_RUN_RAMP` computes its per-line value from a **16.16 accumulator
held in RAM** (`Raster_Ramp_Acc` / `Raster_Ramp_Step`), so a game may rewrite the rate on any
frame. That is the dynamic-uniforms half the 2026-08-14 vocabulary review named as missing.

Pointed at VSRAM it is vertical scale: each scanline scrolls the plane by a different amount,
which is the squash / stretch / perspective-floor family. Five reference engines converged on
this exact shape (Ristar's floor at ROM `$061ACE`, Vectorman's table-free scaler at `$0006F6F8`,
plus Gunstar, Alien Soldier and Thunder Force IV) — **none of them can parameterise it from data
the way this can**, because in each case the rate is baked into the routine.

## Method

Two builds differing in exactly one constant, captured with plane A and sprites muted so the
plane B shift is unoccluded:

| build | `OJZ_RAMP_STEP` | ROM |
|---|---|---|
| ramp | `fp16(0, 128)` = +0.5 px/line | `crc=475fa367` |
| control | `fp16(0, 0)` = flat | `crc=35f6f392` |

The run writes the VSRAM entry rather than adding to it, so the control has to be a ramp too —
otherwise the comparison confounds "the ramp" with "the ramp replaced the parallax system's base
scroll". Run: `top = 112`, `lines = 96`, `cmd = vdp_comm(2, Vsram, Write)` (plane B).

**The step is 0.5 px/line deliberately.** A whole-pixel step would pass even if the fractional
half of the accumulator were dropped entirely. At 0.5 the integer output advances only every
*other* line, so the fixture fails loudly if the 16.16 arithmetic is wrong — the fixed point is
the feature, since it is what lets a rate be authored finer than a pixel.

## Result — 74 of 74 rows match the authored ramp exactly

Each screen row's actual shift was recovered by matching it against the control capture and
testing the **authored** hypothesis (never an argmin — the OJZ background is 64 px vertically
periodic, so a search aliases and reports false misses).

```
row 112  authored  0   differing px 0
row 116  authored  2   differing px 0
row 124  authored  6   differing px 0
row 140  authored 14   differing px 0
row 156  authored 22   differing px 0
row 172  authored 30   differing px 0
row 184  authored 36   differing px 0
                       74/74 rows exact
```

The shift climbs monotonically 0 → 36 across the run and advances every second line, which is
what a 0.5 px/line step in 16.16 must produce.

## The one surprise, measured rather than assumed: VSRAM lands on N+1 here too

The first pass scored 44/74, and **every miss was a row matching `authored - 1`**. The corrected
hypothesis matches 74/74:

> value `j` displays on screen line `top + j` for a **CRAM** target, and on `top + j + 1` for a
> **VSRAM** target.

That extra line is the same N+1 behaviour measured for a *sparse* `vsram` write earlier the same
day: a VSRAM write issued in line N's HBlank takes effect on N+1, while CRAM applies to the line
being set up. So a VSRAM ramp's `top` row still shows whatever scroll was live before the run.

### ⚠ CONTESTED AT THE BOUNDARY (2026-09-03) — this section's rule may be one line early

`tools/ramp_authored_witness.py` arm 4 measures the run's first line directly, with two FLAT twins
of one record differing only in `rrp_start` — every line the run reaches takes a constant offset and
no line it misses can move, so there is no floor-degeneracy at the boundary. It reads the first VSRAM
line as **`top + 2`**, on two documents with different tops: `aurora_local_rampctl_probe` (top 3 ->
first line 5) and `ramp_probe` (top 128 -> first line 130).

**The excerpt above cannot exclude that, and that is a fact about the sample, not about the care
taken.** It lists rows 112, 116, 124, 140, 156, 172, 184 — `top` and then nothing until `top + 4`;
the run's first three rows are absent. And at **+0.5 px/line** the first two emitted values floor to
0 and are pixel-identical to an untouched line. Whether the FULL 74-row set also misses it has not
been checked — if it does not, two instruments disagree, which is a larger problem than either
number. Booked in `docs/DEFERRED_WORK.md`, "RAMP BOUNDARY", with what would settle it.

Also measured in the same run and not documented anywhere before: a ramp WRITES the VSRAM entry, so
after the run ends the entry keeps its final value and every line below the run stays shifted for
the rest of the frame. `ramp_probe`'s 64-line run, declared to end at 192, changes the picture to
223.

**Not corrected inside the constructor, deliberately.** The bias would have to be conditional on
the target, which would put a silent one-line shift between two calls differing only in their
command word — exactly the surprise the sparse tier's single `-1` rule exists to avoid. It is
documented at the constructor instead.

## Cost

Not separately profiled. The ramp body is 7 instructions against the gradient body's 8, and both
share the same prologue (every-line arm + constant command) plus one added `tst.w` for the kind
dispatch, so it should sit within noise of the dense tier's measured ~342 cyc/line marginal.
**Stated as an expectation, not a measurement** — if a ramp is ever run at full-screen height,
profile it.

## What this does NOT establish

- Not a CRAM ramp. Only the VSRAM target was measured; the CRAM landing line is asserted from
  the gradient tier's behaviour, not re-measured.
- Not runtime mutation. The accumulator *lives* in RAM and the wire format seeds it, but nothing
  yet rewrites `Raster_Ramp_Step` per frame. That is the capability this unlocks, not a thing
  this fixture demonstrates.
- Not hardware. oracle is Exodus-derived and this project has no real hardware by policy.

## Environment note

The first attempt at this gate red-screened on the fixture **and on a known-good control ROM**,
which is what identified it as a wedged emulator session rather than a defect in the parcel.
`pkill -9 -x oracle_gui` and relaunch cleared it. Always run the known-good control before
attributing a red screen to your own change.
