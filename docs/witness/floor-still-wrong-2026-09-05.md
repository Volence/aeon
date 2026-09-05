# Floor, "still wrong": what his picture is, and what our design can and cannot do

Subject: the owner's capture of 7f34863c, committed at
`empyrean/docs/captures/2026-09-05-owner-floor-fan-still-wrong.png`. His verdict:
*"unfortunately it's still wrong"*.

Every claim below is labelled **MEASURED** (a number read off pixels, off the
repo, or off `curve_probe`'s transcription of the engine ramp) or **DERIVED** (a
consequence of those numbers plus the code). Nothing here booted an emulator.

Reference: `oracle` `247d316`, `docs/2026-09-05-toystory-floor-recon.md`. Its
result inverts the frame and is used throughout.

---

## 0. The referent for the capture, established before anything is read from it

**MEASURED.** The crop is 856 x 178 in RGBA, 17 distinct colours. Its colours are
the OJZ wood ramp under a `v * 255 / 7` channel expansion, not the `v * 36` one
this repo's previewer uses: the 3-bit triple (5,3,1) arrives as `#B66D24` where
`v*36` gives `#B46C24`. 74.8% of the crop is `WOOD[3]`, 13.4% `WOOD[4]`, 5.5%
`WOOD[1]` (exact), 0.5% `WOOD[0]` (exact). **It is not shadowed**, unlike the
headless captures of the same scene committed at 7f34863c, whose floor band
comes back at half brightness.

**MEASURED.** Vertical alignment, fitted from the art's own horizontal features
rather than assumed: the four dark bands in the crop sit at crop rows 23.5,
41.0, 69.0, 164.0, i.e. spacings of 17.5, 28.0, 95.0 crop px. The generator's
cross seams are computed at screen lines 168, 174, 184, 217 (spacings 6, 10,
33). The fit is **2.8654 crop px per screen line, crop row 0 = screen line
159.79, worst residual 0.36 crop px over the four features**. So the crop covers
**screen lines 159.8 to 221.9**, and the measured spacings are 6.11, 9.77, 33.15
screen lines against the computed 6, 10, 33.

**DERIVED, and it matters for both questions:** those four bands being the art's
own cross seams, at the right spacings, means **the artwork in his picture is
ours**. The coordinator's estimate of 2.68x was close; the measured vertical
scale is 2.8654 and the horizontal is near 2.65 to 2.70, so the pixels are not
square.

**MEASURED.** His capture is not any of the three committed at 7f34863c
(cameras 736, 1216, 1856): those are shadowed, dark, and carry different content.

---

## 1. (b) Why the top rows are flat horizontal bands

### The answer: the ART is flat there. The ramp cannot be a cause, even in principle.

**DERIVED, and this disposes of the proposed mechanism without needing a
number.** Per-line HScroll translates each scanline **rigidly**. A rigid
horizontal translation cannot create or destroy horizontal variation inside a
row. So no ramp, vanishing or steep, can make a row that has vertical structure
look flat, or make a flat row show structure. **"The rows near the top cannot
shear, so we see the art's horizontal lines" attributes to the scroll an effect
the scroll has no mechanism for.** The horizontal lines are there because the art
draws them and nothing else is drawn beside them.

**MEASURED, and the premise is separately false.** The per-row shear does not
vanish near the top. Nominal rate is `camX * F / 72`, constant in the depth row;
at camera 736 with `To(FACTOR_1_8)` that is 1.278 px per row. The engine's
integer table (curve_probe) emits adjacent-line differences of 1 and 2 px,
sampled at lines 155, 175, 195, 215, 222: `-2, -1, -2, -1, -1`. **It is as large
at the top of the band as at the bottom.**

**MEASURED, what is actually there.** In the Plane-B-only prediction over the
crop's 67 lines, **51 lines are a single flat colour** and only 16 carry any
horizontal variation at all.

**MEASURED / DERIVED from the shipped knobs.** Seams are drawn only where the
beam period exceeds `lod_px` 20, i.e. depth row 45 and below, i.e. **screen lines
197 to 223, which is 27 of the 72 floor lines**; full seam contrast only from
line 210. Lines 152 to 196, **45 lines**, draw no beam at all. What is drawn
there instead is exactly what the crop shows: cross seams (computed at 168, 174,
184, 217) and depth-shade steps (computed at 158 and 218), all horizontal by
construction.

### Is it fixable by tuning, or only by redrawing?

**By tuning, at a measured price.** It is a tile-budget wall, not a geometric
one. **MEASURED** tile cost at the shipped pitch of 32, against the **123 slots
the band reclaims**:

| `lod_px` | unique tiles | rows drawing seams |
|---|---|---|
| 20 (shipped) | **121** | 27 of 72 |
| 16 | 176 | 36 |
| 14 | 204 | 40 |
| 12 | 240 | 45 |
| 10 | 247 | 49 |
| 6 | 296 to 322 | 58 |

Flattening the depth shade ramp buys nothing (3.6/2.4 to 3.2/3.2 moves 121 to
122), because the count is almost entirely the seam-row count: no two rows share
a period, so no two rows share a tile.

**DERIVED, the second and harder floor.** The period goes to zero at the horizon,
so seams closer together than about 4 px alias into a solid band whatever the
budget allows. At pitch 32 that is depth rows below 9, i.e. **screen lines 152 to
160 can never carry drawn beams**. Everything between 161 and 196 is purchasable
with `band_reserve`, which is the owner's number.

### Against the reference

Toy Story's top rows converge because its **art** converges, all the way up. That
is consistent with our finding and it is the same statement: in both engines the
convergence visible in a row is a property of what is drawn in that row. The
difference is that they draw it everywhere and we stop at line 197 for budget.

---

## 2. (a) Why several centres are visible at once

### What each hypothesis forbids, stated before it was tested

| hypothesis | it FORBIDS | outcome |
|---|---|---|
| H1 the 512 wrap showing two copies | any wrap while the near row's scroll is under 192 px; more than two centres | **forbidden at the sampled cameras** |
| H2 the art repeats within the plane | the live plane being a single-apex render | **REFUTED** |
| H3 the per-column VSRAM cone | a horizontal art feature staying flat across the screen | **REFUTED** |
| H4 his picture is our art plus our modelled ramp | a fit no better than chance at every camera | **REFUTED** |

**H1, MEASURED.** Plane B wraps every 512 px against a 320 px screen, so 192 px
of slack. At camera 736 with `To(FACTOR_1_8)` the maximum scroll over the band is
**91 px**; at 1216 it is 150. Under 192 there is no second copy on screen at all,
so at those cameras H1 is forbidden. It is permitted at 1856 (235 px).

**H2, REFUTED by measurement already in hand** (previous parcel, re-checked): the
live Plane-B nametable rows 48 to 63 are byte-identical to `zone_bg.bin` (1024
words) and the live VRAM tiles are byte-identical to the generator's single-apex
render (**65536 pixels over 121 distinct tiles**). The plane carries exactly one
apex.

**H3, REFUTED.** The scene authors
`v_deform: SceneVDeform.ScreenFloor(DeformTable_Perspective, 0, 2)`, which is
`v_column_floor_screen(edge_offset: 24)` shifted right by 2: **DERIVED**, a
per-column-pair vertical offset of 0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 6 px going out
from the apex column, reaching 6 px at the screen edges in 16 px steps. That
would bend every horizontal art feature into a V of amplitude 6 screen lines.
**MEASURED: the cross seam at line 168 is flat to 0.3 screen lines across the
crop's 19 column pairs.** The cone is not displacing this band.

**H4, REFUTED, and this is the parcel's main result.** Predicting the
Plane-B-only screen from the shipped art plus curve_probe's ramp and scoring the
mean distance from each measured seam to the nearest predicted seam:

| search | free parameters | best fit |
|---|---|---|
| camera only | camX 0..3400 | 7.07 px (chance 8.45) |
| plus scale and offset | + hscale 2.3..4.5, xoff +-160 | **6.67 px** (1st pct 7.51, chance 15.05) |
| plus the ramp's top line | + rampTop 128..188 | 6.11 px (1st pct 7.12) |
| each curve end factor | FACTOR_1 / 1_2 / 1_4 / 1_8 | 6.25 / 6.69 / 6.69 / 6.63 px |

**POSITIVE CONTROL, run through the identical code and the identical grids.** A
synthetic picture that IS the shipped art plus the modelled ramp at a known
camera (1200), upscaled to the same 856 x 178 with the same non-square scales and
the same `v*255/7` palette, is recovered at **1.08 px** in the wide grid and
**0.88 px** in the ramp-top grid. **What would have falsified the conclusion: any
combination fitting his crop at control grade, about 1 px. None did; the best was
5.6x worse.**

### So: the art is ours, the scroll is not what we model

**DERIVED.** The cross seams are scroll-invariant and they match our art. The
beam lattice is entirely scroll-dependent and it matches nothing we can model.
The departure is therefore in the per-line horizontal scroll actually applied,
not in the artwork.

**I cannot name the mechanism, and I am stopping there rather than filling the
gap.** The measurement that would settle it is a read of the live 224-entry
Plane-B HScroll table at his camera position, compared against
`curve_probe.derive_curve_buffer`. Two outcomes, and what each forbids: if they
agree, the fault is downstream of the table and my model of the art-to-screen
mapping is wrong somewhere I have not looked; if they disagree, the fault is in
what writes the table, and the disagreement's shape names it. I am not permitted
an emulator, so this is an ask, not a result.

### One thing I could NOT confirm: the count of centres

**I decline to give a number, and the reason is the failure oracle recorded.** My
first apex-vote histogram had peaks near screen x 375 and -137, spaced **505**,
and 512 is exactly the plane wrap: a beautiful confirmation of my own prior
hypothesis. It was an artifact. Adjacent crop rows are 0.35 screen lines apart,
so a half-pixel seam-centre error becomes 1.4 px per line of slope noise. Redone
over a 4 to 6 line baseline the distribution is broad, not multi-peaked
(332 votes, median 262.7, interquartile range 204.7 to 373.2, i.e. 169 px wide).
Two methods, two different answers, so **the honest report is that the beams do
not converge on a single column and I have no trustworthy count**. Locating the
wrap by a spacing that matched what I expected is the same shape of error as
locating a scroll table by a sawtooth that matched what was expected.

---

## 3. What our design can and cannot produce

This is the part that lets him choose between real options.

### CAN

1. **A vanishing point pinned to the SCREEN centre column at every camera x.**
   **DERIVED:** with the drawn period proportional to the depth row and the
   scroll also proportional to it, a beam sits at
   `screen x = vx + dy * (j*P - camX*F/span)`, a straight line through
   `(vx, dy = 0)` for every beam index and every camera. `vx` is plane 159.5,
   which is screen column 159.5. **The reference measures Toy Story as not having
   this property**, and its own note says a screen-anchored vanishing point is a
   different technique for which that ROM is not a reference.
2. **Beams that relabel as he walks**, so the floor slides under a fixed
   convergence rather than the convergence sliding with the floor.
3. **Zero net tile cost at the shipped settings.** **MEASURED:** 121 tiles into
   the 123 slots the band reclaims, 0 appended, `band_reserve` untouched at 80.

### CANNOT

1. **Cover the whole floor band inside the budget.** 27 of 72 rows at 121 tiles;
   40 rows costs 204; 49 rows costs 247. The band reclaims 123.
2. **Survive unlimited camera travel.** **MEASURED** (apex vote, share of beams
   voting for an apex more than 60 px off, against an 8 to 20% matcher baseline)
   under `To(FACTOR_1)`: 8% at camera 0, 17% at 90, 21% at 180, 35% at 300, 62%
   at 420, 97% at 600. Onset is `camX = 192/F`, so 195, 389, 778, 1557 px for
   FACTOR_1, 1_2, 1_4, 1_8.
3. **Do what Toy Story does.** Ours bakes plane B statically from
   `editor_bg_override.json`; there is no streaming path for BG art. Theirs has
   nothing to wrap because nothing repeats.

### The cost comparison

| | Toy Story (oracle, measured) | ours (measured) |
|---|---|---|
| technique | painted into fixed art, whole plane scrolls uniformly | per-line HScroll ramp against a depth-proportional drawn period |
| raster effect | none | one per-line HScroll ramp |
| unique floor tiles | ~190+ across five cell-rows | **121** across 27 lines; 204 for 40 lines |
| streaming | required, art is unique per cell | none, and none available |
| wrap | none, nothing repeats | 512 px, costing a **192 px** camera-travel budget per unit of F |
| vanishing point | **travels with the world** | **pinned to the screen centre** |
| moving the vanishing point | redraw the art | one identifier |

**DERIVED, the honest read of that table:** extending our fan to a comparable
five-cell-row band costs 204 tiles, the same order as their 190+. The difference
is not the tile count, it is that **theirs streams and ours must fit all at once**
inside a 400-tile `bg_region` carrying an 80-tile reserve, and that **theirs buys
a world-anchored vanishing point while ours buys a screen-anchored one.**

**The choice is his and it is between two products, not two qualities.** A
world-anchored floor is the shipped, proven, unlimited-travel option and it is
what the reference measures. A screen-anchored floor is what his sentence asked
for (*"when one of the beams of the floor at the top hits the center, the bottom
should hit the center"*, and *"if you keep moving it continuously does that?"*),
and no commercial reference has been found for it. Nothing should be drawn until
he picks.
