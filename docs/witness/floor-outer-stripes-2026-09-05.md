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
