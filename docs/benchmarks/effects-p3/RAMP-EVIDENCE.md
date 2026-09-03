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

### ⚠ SETTLED 2026-09-03 — THE RULE ABOVE IS THIS DOCUMENT'S OWN, AND IT NO LONGER DESCRIBES THE ENGINE

`tools/ramp_boundary_probe.py`. Read this section before quoting anything above it.

**The rule holds, but `j` does not start at 0, and the section above never said which line the
first DISPLAYED value lands on.** Measured on today's engine over **19 `top`s spanning 3..220** and
**9 run lengths from 1 to 111**, with two FLAT twins (step 0) of one record differing only in
`rrp_start` — every line the run reaches takes a constant offset and no line it misses can move, so
the first differing line IS the first reached line, with no floor-degeneracy anywhere:

| target | first screen line the run CHANGES | value on screen line `top + n` |
|---|---|---|
| VSRAM | **`top + 2`** — every one of the 19 tops, zero interior gaps | `start + (n-1) * step`, for `n >= 2` |
| CRAM  | **`top + 1`** | `start + n * step`, for `n >= 1` |

Equivalently, and this is the sentence the suite contract should carry: **value `j` = `start + j*step`
displays on `top + j + 1` for VSRAM and on `top + j`  for CRAM — and `j` STARTS AT 1.** The
interpreter adds the step *before* it writes (`move.l Raster_Ramp_Acc,d1; add.l Raster_Ramp_Step,d1;
… swap d1`), so `start` itself is never emitted. Measured directly at **+1 px/line**, where every
emitted value is distinct and the integer part is exact: screen line `top+1` is pixel-identical to a
V=0 reference, `top+2` carries shift 1, `top+3` shift 2, `top+4` shift 3 — at both `top` 112 and
`top` 40.

**The one-line CRAM/VSRAM gap this section calls the N+1 VSRAM latency is CONFIRMED, and the CRAM
half is measured here for the first time** — "What this does NOT establish" below says in as many
words that it never was. CRAM was read on the three tops (150, 190, 220) where the probed palette
entry demonstrably covers the `top` row itself, so "unreached" is distinguishable from "no pixel
uses that colour there"; a full-screen coverage pass runs first and the probe refuses to report a
boundary for an entry with no coverage.

**THE EXCERPT ABOVE IS NOT BLIND TO THIS, AND THAT MATTERS — the two measurements genuinely
disagree.** The published rows 116/124/140/156/172/184 are all *discriminating* (only row 112 is
not). Both PNGs beside this file are the **full 320×224 originals**, committed in `c2a7e1a9` with
this document, so every row can be re-derived rather than inferred from the seven: scored against
the original captures, the earlier rule matches **187 of 187** scorable rows and **37 of 37**
discriminating ones, while the rule measured today matches 157 and 7. The 2026-08-14 picture really
was one line higher than today's.

**Rebuilt on TODAY's ROM, the same fixture geometry gives the opposite verdict.** `top` 112,
`lines` 96, `+0.5 px/line`, VSRAM byte 2, synthesised at runtime into scratch RAM: the top+2 rule
matches 29 of 37 discriminating rows and the top+1 rule matches **0**. So the picture moved by
exactly one line between 2026-08-14 and 2026-09-03, in the same direction for **both** targets (the
gradient tier's documented CRAM landing is `top`; today it measures `top + 1`).

**WHICH SIDE MOVED IS OPEN AND IS NOT ASSERTED HERE.** Two candidates, and nothing measured
excludes either: (a) a change in the raster path after 2026-08-14 — `.dense_end` falling into
`.park`, the frame-rewind interlock, the `-4(a2)` respellings all post-date these captures; or
(b) the instrument — these PNGs came off the legacy Exodus-derived C++ core, and the Rust core
became the ratified default on 2026-08-26. That both targets moved together by exactly one line is
consistent with either. What would settle it: run a `c2a7e1a9`-era ROM (published `crc=475fa367`)
on the Rust core, or today's ROM on the legacy core. Booked in `docs/DEFERRED_WORK.md`,
"RAMP BOUNDARY".

Also measured and not documented anywhere before: a ramp WRITES the VSRAM entry, so after the run
ends the entry keeps its final value and every line below the run stays shifted for the rest of the
frame. `ramp_probe`'s 64-line run, declared to end at 192, changes the picture to 223. **So "the
last line that looks different" is not where a run ends** — measure the span by where the stepping
stops, not by where the difference stops.

And the consequence an author meets: a run of `lines` values occupies screen lines
`top+2 .. top+lines+1`, so the constructor's `top + lines <= 223` admits a VSRAM run whose LAST
value displays on line **224** and is never seen. `aurora_local_rampctl_probe` authors 220 lines and
**219 of them render**. The ceiling is not tightened — it exists for the frame-rewind interlock, and
tightening it would refuse a document that already ships — so it is stated at the `ensure` instead.

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

- ~~Not a CRAM ramp. Only the VSRAM target was measured; the CRAM landing line is asserted from
  the gradient tier's behaviour, not re-measured.~~ **CLOSED 2026-09-03** — measured, and it is
  `top + 1`, one line later than the gradient tier's documented `top`. See the SETTLED section.
- Not runtime mutation. The accumulator *lives* in RAM and the wire format seeds it, but nothing
  yet rewrites `Raster_Ramp_Step` per frame. That is the capability this unlocks, not a thing
  this fixture demonstrates.
- Not hardware. oracle is Exodus-derived and this project has no real hardware by policy.

## Environment note

The first attempt at this gate red-screened on the fixture **and on a known-good control ROM**,
which is what identified it as a wedged emulator session rather than a defect in the parcel.
`pkill -9 -x oracle_gui` and relaunch cleared it. Always run the known-good control before
attributing a red screen to your own change.
