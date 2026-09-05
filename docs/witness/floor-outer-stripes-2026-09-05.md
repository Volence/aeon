# Floor: why the outer beams pointed away, and what the wrap actually costs

His words: *"That floor is actually almost perfect, the first few are good then a
few after get weird and point away, but they continue to move like they should,
is this the art that's the problem?"*

**This page has been wrong twice and is now on its third answer. Both earlier
answers are kept below, because both were believed and acted on.**

| version | said the defect was | verdict |
|---|---|---|
| 1 | `abs(u)` in `render_band` folding the fan's halves | **FALSE.** Measured: 0 of 65536 pixels differ with it removed |
| 2 | a fan cannot tile a 512-px wrap, so ship parallel planks | **THE MEASUREMENT WAS WRONG AND THE CONCLUSION WITH IT** — see §2 |
| 3 | the wrap is a CAMERA-TRAVEL budget, not a tiling problem | current — see §3 |

---

## 1. The line version 1 blamed is a NO-OP

Version 1 said the defect was `render_band()` keying the pattern on `|u|`.
**MEASURED: rendering the band with `abs(u)` and with signed `u` differs on 0 of
65536 pixels.** Both quantities the pattern was keyed on are already even in `u`.
Anyone acting on that diagnosis would have deleted the `abs()`, rebuilt, and seen
the picture not move.

## 2. Version 2's quantisation table measured the wrong constraint

Version 2 argued the fan out of existence like this: removing the wrap's copies
means making the drawn period an exact divisor of 512 at every row; forcing that
"to an even integer" leaves only six distinct periods over 43 rows, held for runs
of up to 12 pixel rows, which is a run of vertical stripes.

**The constraint in that sentence is not the constraint.** 18 px is an even
integer and does not divide 512. Divisibility is a statement about the BEAM
COUNT: the period must be `512/n` for integer `n`, and `512/n` need not be an
integer at all. That is a far finer grid — `n` even gives 25.6, 21.3, 18.3, 16.0,
14.2... where the old table could only offer 18, 16, 14, 12, 10, 8.

So the fan was retired on a measurement of something else, and parallel planks
shipped for part of the day. The owner rejected them the same afternoon:

> *"it has the correct floor but not the correct effect, the effect should make
> it so when one of the beams of the floor at the top hits the center, the bottom
> should hit the center. the other had that effect a little, this just
> consistently skews and continues to do so"*

He was right on the mechanism as well as the look: a shear's on-screen angle is
`skew - camX*F/span`, so it ROTATES with the camera — measured +0.5 px/row at
camera 0, through vertical at ~36, to -5.3 px/row at 420.

## 3. What the wrap actually costs: 192 px of camera travel

The finer grid does tile. **It also loses, for a different reason, and that
reason is the one worth keeping.**

A wrap-exact period (`512/n`, `n` integer) is a STAIRCASE in the depth row, while
the engine's curve ramps its scroll factor LINEARLY over the same rows. The fan
survives horizontal scroll only when the two are the same function — the ratio
scroll/period must be constant — so a staircase against a ramp scatters the
composited lattice phase. **MEASURED, peak-to-peak over the seam rows, in
periods** (0 = a perfect fan, 0.5 = rows half a beam out of step):

| camera x | 0 | 180 | 420 | 900 |
|---|---|---|---|---|
| wrap-exact period | 0.00 | 0.30 | **0.65** | **0.89** |
| linear period | 0.00 | 0.12 | 0.18 | 0.12 |

The centre beam's worst row-to-row jump goes 0.1 px to 4.8 px at camera 420. It
trades a defect that arrives at camera 195 for one that arrives at 90.

**So the linear period is kept, and the wrap is paid for in camera travel
instead.** Plane B wraps every 512 px against a 320-px screen, so the floor's
near row may slide 192 px before the window shows the NEXT copy of the fan, whose
apex is at screen 159.5 + 512 = 671.5, off the side. Its beams lean hard the
other way — *"the first few are good then a few after get weird and point away"*.
The slide rate is the scene's curve end factor, so the onset is at `camX = 192/F`.

**MEASURED** by letting every adjacent-row seam pair vote for the column its beam
converges on, and counting votes more than 60 px off the true apex. 8-20% is the
nearest-neighbour matcher's own noise:

| curve `To(..)` | camX 0 | 90 | 180 | 300 | 420 | 600 | 900 | 1400 | onset |
|---|---|---|---|---|---|---|---|---|---|
| `FACTOR_1` | 8% | 17% | 21% | 35% | **62%** | **97%** | 99% | 100% | 195 |
| `FACTOR_1_2` | 8% | 20% | 17% | 12% | 13% | 35% | 69% | 100% | 389 |
| `FACTOR_1_4` | 8% | 18% | 20% | 10% | 17% | 12% | 14% | 43% | 778 |
| `FACTOR_1_8` | 8% | 11% | 18% | 21% | 18% | 10% | 15% | 19% | 1557 |

`FACTOR_1` is what the scene carried, and its row IS the owner's report.

### Why the scene ships `FACTOR_1_8` and not `FACTOR_1_4`

Because the ROM said so and nothing else could. The lab chord that selects this
scene is **START+RIGHT x20**, and RIGHT is a direction as well as the row hotkey,
so **selecting the row leaves `Camera_X` at 736** — measured by
`tools/perspective_floor_witness.py`. At `FACTOR_1_4`'s clean range of 768 the
owner arrives 32 px inside the edge. `FACTOR_1_8` puts that landing at the
halfway mark with about 800 px of clean travel ahead of it.

**The cost is scroll RATE**, and it is his to reverse: the floor's near row now
moves at an eighth of the camera rate. The fan's GEOMETRY does not depend on the
factor at all — the apex sits on screen column 159.5 for any F, because the art's
period and the engine's ramp are both linear in the depth row and only their
ratio matters. The table above is the exchange rate and the knob is one
identifier in `games/sonic4/data/effects/ojz_scenes.emp`.

## 4. What is NOT available, so it is not re-proposed

**A fan that is clean at every camera x does not exist in the art.** A finite
wrapping plane holds a PERIODIC texture and a fan is not periodic. The two
escapes are both outside the art:

  * **A per-row scroll gain that follows the wrap-exact staircase.** That closes
    the ratio exactly and would be clean at every camera x. The parallax band
    vocabulary cannot express it: band factors are at most two shift terms, so
    the achievable set is `2^-a +- 2^-b`, and forcing `512/n(dy)` proportional to
    one of those drives `n` onto powers of two — a four-step fan.
  * **Per-column VSRAM**, which can spread parallel beams into a fan by the
    effect rather than the art. Costed but not built: 16-px granularity over
    twenty columns, it breaks the floor's hard horizon line into dashes, and it
    spends the V axis that scene 20's V-cone already holds.

## 5. Budget

121 tiles of the 123 the band reclaims, 0 appended, `band_reserve` untouched at
80. The recycler now also reclaims slots NO layout cell references — the shear
had stranded 84 of them and left this band a 39-slot budget that every later bake
would have inherited.

`lod_px` 20 is that ceiling talking, not taste: the tile count is almost entirely
the SEAM-ROW count, because no two rows share a period and therefore no two rows
share a tile. Measured at pitch 32: lod 10 gives 247 tiles / 49 seam rows, 12
gives 240/45, 14 gives 204/40, 16 gives 176/36, **20 gives 121/27**. Flattening
the depth shade ramp buys nothing (3.6/2.4 to 3.2/3.2 moves 121 to 122). So the
fan draws on the nearest 27 of the floor's 72 rows and the rest is graded floor.
More rows needs `band_reserve` to come down, which is the owner's number.

## 6. Where the gates stand

`tools/test_perspective_floor.py` — five arms, every number voted off rendered
pixels:

  * `test_drawn_beam_period_is_proportional_to_the_depth_row` — the fan's law in
    the art, as the SPREAD of period/row (0.66% shipped; 2% tolerance) rather
    than as a fitted intercept, because every seam row sits in the near third of
    the band and extrapolating to the horizon multiplies the noise by the lever
    arm.
  * `test_composited_beams_converge_on_the_screen_centre_column` — the owner's
    property, on the art composited through curve_probe's transcription of the
    engine ramp at camera 0/180/420. **Its expectation comes from `SCREEN_W`,
    not from the art's `vp_col`** — the first draft took it from `vp_col` and
    stayed GREEN when the apex moved 64 px off centre.
  * `test_committed_override_carries_the_generated_band`
  * `test_baked_plane_b_carries_the_generated_band` — one stage further down the
    pipeline: `zone_bg.bin` + `bg_tiles.bin`, the files the build consumes.
  * `test_scene_curve_band_matches_the_art_band` — no longer pins the end factor;
    the composited arm tests it the way it matters.

Retired with the shear, and stated rather than deleted:
`test_drawn_planks_are_one_translation_tiled_lattice`. Its four checks were real
properties of that art, but "one period for the whole band" is the exact opposite
of a fan and would now FAIL the correct subject.

`tools/perspective_floor_witness.py` boots the ROM and compares the live Plane-B
nametable and the live VRAM tiles against the generator — 1024 words and 65536
pixels, byte-identical — and reports `Camera_X`. It deliberately does NOT score
the beams off `emulator/scanlines`: scene 20 renders the band under a
shadow/highlight mask that varies along a row, masking Plane A puts the server
onto a post-hoc `stateRender` that cannot see a per-line ramp at all, and
inverting the mask by colour did not close against the runtime CRAM. That absence
is printed on every run.
