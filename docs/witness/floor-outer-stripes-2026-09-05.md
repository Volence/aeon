# Floor: why the outer stripes pointed away, and what replaced the fan

His words: *"That floor is actually almost perfect, the first few are good then a
few after get weird and point away, but they continue to move like they should,
is this the art that's the problem?"*

**Yes, it was the art. This document's first version named the wrong line in it,
and that correction is the first section below.**

---

## 1. The line this document used to blame is a NO-OP

The first version of this page said the defect was `render_band()` keying the
pattern on `|u|`:

```
u = ((x - vx + 256.0) % 512.0) - 256.0
off = abs(u) / p
```

and that the `abs()` made the pattern even about `u = ±256`, reflecting the
fan's opposite half back.

**MEASURED: rendering the band with `abs(u)` and with signed `u` differs on 0 of
65536 pixels.** The `abs()` was doing nothing at all. Both quantities the pattern
is keyed on are already even in `u`: `frac = |off - j|` is even because
`j = round(u/p)` flips sign with `u`, and the tone is keyed on `|j|`. Anyone
acting on the old diagnosis would have deleted the `abs()`, rebuilt, and seen the
picture not move.

The evenness about `u = ±256` is real, but it comes from the **`% 512`** — which
is the plane wrap, not a choice anybody made.

## 2. What was actually wrong: the wrap COPIES the apex

A drawn board is the locus `|u| = j·p(dy)`, i.e. plane `x = vx ± j·P·dy + 512m`.
On screen, after the band's scroll `C·dy`:

```
x = vx + dy·(±jP - C) + 512m
```

Every board is a straight line through an apex at screen `x = vx + 512m`. Plane B
wraps every 512 px, so **the apex is copied every 512 px.** One copy is on
screen; the others are off the side. The boards belonging to an off-screen copy
converge off the side of the screen — and that is precisely "the first few are
good then a few after get weird and point away". His *"they continue to move like
they should"* is the tell: the per-row gain was never involved.

### Why it could not be fixed inside the fan

Removing the copies means making the drawn period an exact divisor of 512 at
every row. But the fan's period has to be proportional to `dy` (that is the whole
scroll law), and `512/p(dy)` is then a hyperbola. Forcing it to an even integer
quantises the pitch. **MEASURED on this band:**

| forced period | rows held | pixel rows of constant pitch |
|---|---|---|
| 18 | dy 30..33 | 4 |
| 16 | dy 34..37 | 4 |
| 14 | dy 38..43 | 6 |
| 12 | dy 44..51 | 8 |
| 10 | dy 52..63 | **12** |
| 8 | dy 64..71 | 8 |

Six distinct periods over the 43 rows that draw seams, held for runs of up to 12
pixel rows. A pitch held constant over a run of rows **is** a run of vertical
stripes — the exact defect commit 5751123d removed. Fan + wrap + closure: pick
two. This is a geometry result, not a budget one; the budget never entered.

## 3. What shipped instead: parallel planks

The owner chose the shape:

> *"I think our problem is we need it all just skewed in one direction instead of
> trying to work around it having one part point at us, so the art is consistent
> and the effect is consistent in what it's doing."*

Plank centres are now `vx + j·64 + 0.5·dy` — one lattice, one period, one lean.
64 divides 512 eight times and 8 is even, so the pattern tiles the wrap by pure
translation: no fold, no `% 512` in the rasteriser at all, no mirror axis, no
straddling plank, and no apex to copy.

**Tiles: 39, against the fan's 120**, into the 120 slots the band's own rows
recycle. 0 appended, 81 stranded, blob length 320 → 320, `band_reserve` untouched
at 80. The headroom paid for the recession cues a constant plank width no longer
gives: the depth shade ramp went 0.9 → 1.6 wood steps, and the perspective-spaced
cross seams went ON (+7 tiles; they were off under the fan because they did not
fit).

## 4. The two costs, so they are not discovered in a capture

**(a) There is no vanishing point.** Parallel planks converge nowhere. Chosen,
not regressed.

**(b) The plank angle rotates with the camera.** On-screen slope is `skew - C`,
and `C` is proportional to camera x. Measured off the engine's own ramp
(`tools/curve_probe.py`, via the previewer):

| camera x | 0 | 36 | 90 | 180 | 300 | 420 | 600 |
|---|---|---|---|---|---|---|---|
| C px/row | +0.000 | +0.507 | +1.254 | +2.507 | +4.169 | +5.845 | +8.338 |
| on-screen slope | **+0.500** | -0.007 | -0.754 | **-2.007** | -3.669 | **-5.345** | -7.838 |

So the planks lean right at camera 0, stand **vertical** at camera x ≈ 36, and
lean progressively further left after that; by camera 420 the prediction shows
them as near-horizontal streaking. Uniform at every instant — never two
directions at once, which is the whole ask — but not a fixed angle.

This is inherent to "one plank angle in the art plus a depth-ramped scroll". The
fan avoided it only by drawing every angle at once, which is what produced the
apex copies. **`--skew` does not fix it; it only moves where the vertical
crossing happens.** Setting `skew` to ~2.7 would re-centre the camera 0..420
range at ±2.7 px/row instead of +0.5..-5.3, at the price of the floor already
leaning hard at camera 0. The only lever that reduces the rotation itself is the
layer's `curve` end factor — a shallower ramp rotates slower and recedes less —
and that is the per-row gain, which the owner has said is correct and is not
being touched.

## 5. Where the gate stands

`tools/test_perspective_floor.py` retired `test_drawn_board_pitch_is_linear_in
_the_ramp_index` — with the reason written in the file, not silently. Under a
shear the period is constant by construction, so a fit of pitch against depth row
is a fit of a constant: slope 0, residual 0, and it would pass for any shear
including a broken one.

Its replacement, `test_drawn_planks_are_one_translation_tiled_lattice`, checks
the shear's four preconditions (one period; that period an even divisor of the
wrap; one non-zero lean; the tone alternation closing across x = 0) and keeps the
retired arm's non-negotiable property: every number is voted for off the rendered
pixels and nothing consults the generator's model. Its red-first battery, with
the mutations quoted from disk and the exit codes, is in the arm's docstring —
including the row where the first version of the arm stayed GREEN under a
mutation and a fourth check had to be added.

---

# ADDENDUM, 2026-09-05 afternoon: the "two floors with a kink" capture is the FAN

His words on the just-landed shear: *"dont know what aeon reloaded but the plank
still has the adjustment with the floor."* The capture is
`empyrean/docs/captures/2026-09-05-owner-floor-planks-kink.png`.

**THE ROM IN THAT CAPTURE IS NOT THIS TREE'S ROM. It is the fan, bake b89b13de,
and the shear never reached the machine he was looking at.** That is a measured
identification, not an inference from the timestamps, and the measurement is
below. Nothing in the art or the gain was wrong; there was nothing to fix.

## 1. What the capture actually shows, decoded

The capture is a 855x352 window crop at 2.63x. Reading the OJZ wood ramp back out
of it (`#240000 #482424 #904824 #B46C24 #D89048 #FCB46C` = WOOD[0..5]) gives a
row census with four hard boundaries:

| capture rows | wood indices present | screen rows | depth row dy |
|---|---|---|---|
| 6..63 | WOOD[0] only | 96..118 | wall |
| 64..156 | WOOD[1] only | 118..152 | wall |
| **160..231** | **WOOD[3] ONLY — no seams, no alternation** | **153..180** | **0..28** |
| 232..239 | WOOD[2] + WOOD[3] | 181..184 | 29..31 |
| 240..281 | WOOD[2] + WOOD[4] | 184..200 | 32..47 |
| 282..345 | WOOD[3] + WOOD[4] | 200..224 | 47..71 |

So the top 28 depth rows of the floor in his capture are **one flat slab of a
single colour**, and the boards switch on at one row. That is his kink.

## 2. Which art draws that, decided by run-length and not by eye

Horizontal transitions per depth row, both bands rasterised from their own
committed `editor_bg_override.json`:

| depth row dy | screen row | FAN (b89b13de) | SHEAR (this tree) |
|---|---|---|---|
| 0..28 | 152..180 | **0 transitions — `5*320`, literally one colour** | 7..24 |
| 29 | **181** | **20 — the boards switch on** | 12 |
| 33 | 185 | 36 | 16 |
| 54 | 206 | 32 | 14 |

**The shear has ZERO depth rows with no horizontal structure. The fan has 29 of
them, dy 0..28, and its first drawn row is dy 29 = screen line 181.** Predicting
the capture row for that boundary from the band placement alone — capture row 157
is dy 0, scale 2.63 — puts it at capture row **233**; the census above measures
the boundary at **232**. One image pixel.

The board WIDTHS settle it a second time. The fan's tone bands measure 28..30 px
at dy 33 and 47 px at dy 54 (they widen with depth, which is what a fan does);
the capture measures ~30 screen px at its dy-33 rows and ~47 at its dy-54 rows.
The shear's bands are 62..64 px on EVERY row by construction and would have
measured the same at both. The capture is the fan, twice over.

## 3. The two questions the brief asked, answered against the WRONG ROM anyway

Worth recording, because both answers are useful and neither one is "the gain":

* **The gain has no step.** `curve_probe.derive_curve_buffer()` over the shipped
  layer stack gives, for the 71 line-to-line differences inside the floor band,
  only the two adjacent integers that bracket the ideal rate at every camera x
  tested (0/36/90/180/300/420/600) — e.g. camera 180 is `-3,-2,-3,-2,...` for all
  71, camera 420 is `-6,-6,-6,-6,-6,-5` repeating. That is Bresenham dither on a
  straight line. There is no band boundary, no second regime, and no row where
  the rate changes character. The floor layer is the only curve layer and the
  four above it are flat `FACTOR_0`, so nothing else can contribute a step.
* **The kink does not move with camera x.** It is an ART row — the fan's seam
  suppression threshold — so it is pinned to screen line 181 at every camera x.
  What moves with camera x is the ANGLE on either side of it, which is why it
  reads as two floors leaning differently rather than as a shading band.

## 4. What the tree actually contains, checked end to end

Decoded and compared pixel for pixel, on `fix/floor-kink-stale-rom-2026-09-05`:

```
editor_bg_override.json          vs render_band()   0 of 65536 pixels differ
zone_bg.bin + bg_tiles.bin       vs render_band()   0 of 65536 pixels differ
```

The second line is the one nothing in the suite had ever checked, and checking it
by hand at a terminal is what this whole investigation cost. It is now
`test_baked_plane_b_carries_the_generated_band` in
`tools/test_perspective_floor.py`.

## 5. Why no gate could have caught the stale ROM, and what now can

The chain is `SHIPPED -> editor_bg_override.json -> zone_bg.bin + bg_tiles.bin ->
ROM`. `test_committed_override_carries_the_generated_band` holds the first link.
The second link was held only INDIRECTLY, by `tools/level_staleness.py` arm B,
which hashes the editor SOURCES and fails the build when they move without a
re-stamp — that answers *were the inputs re-baked*, never *did the bake produce
this picture*. The blob length cannot see a bad bake either: the floor recycles
its own slots, so 320 tiles stays 320 tiles whatever it draws.

Red-first, every mutation quoted from disk and restored from the committed
baseline (`git checkout --`), then re-run to green:

| mutation | new arm | other 3 arms | `level_staleness` |
|---|---|---|---|
| `bg_tiles.bin[0x1B02]` `0x14`->`0x15` (tile 216, band-referenced) | **RED (exit 1)** | pass | **exit 0 — blind** |
| `zone_bg.bin[0x1864:0x1868]` `44c644c7`->`44c744c6` (two band cells swapped) | **RED (exit 1)** | pass | **exit 0 — blind** |
| `bg_tiles.bin[0x0A00]` `0x38`->`0x39` (tile 79, NOT referenced by the band) | green | pass | exit 0 |
| `zone_bg.bin[0x1814]` low bit (col 48 row 10, outside the band) | green | pass | exit 0 |

The last two are controls and they are green ON PURPOSE: the arm is scoped to the
picture the floor band draws, so a byte no band cell reads is correctly not its
business. **The first attempt at the first mutation was one of those controls by
accident** — `bg_tiles.bin[0x0A00]` was picked before checking which tiles cell
rows 48..63 reference, it came back green, and it would have been reported as a
hole in the arm if the referenced-tile set had not been enumerated first. The
enumeration (39 tiles, indices 197..235, matching this document's own "39 unique
tiles") is what made the mutation land.

## 6. What is still open, and it is NOT this

Cost (b) in section 4 above — the plank angle rotating with the camera — has
still never been seen on a machine, because every capture so far has been of the
fan. It remains the thing to judge from a capture at three camera positions.
