# Floor: costing a per-row-period fan with no repeat, and what the gain change actually costs

**Costing only. Nothing was drawn, generated, baked or tuned.** Every number below
comes from `tools/perspective_floor_gen.py`'s own rasteriser and dedup, read in
memory, or from a declared constant. The generator was run once with `--report`,
which writes nothing.

**The headline is that the parcel as framed is mostly already built, the last
piece of it does not fix the reported defect, and the thing that does fix the
defect costs zero tiles.**

---

## 0. The four numbers, up front

| question | answer |
|---|---|
| Does our art already have a per-row period? | **Yes.** Every pixel row has its own period, and that is why no two rows share a tile. |
| Does it already avoid repeating within a plane width? | **82% of the way.** 157 of 192 fan cells carry art unique in position; 35 are exact repeats. |
| What does closing the last 18% cost? | **+76 tiles** (123 available, 199 needed). Fits only if `band_reserve` goes 80 to 4. |
| What does it buy for *"the first few are good then a few after get weird and point away"*? | **Nothing.** That defect is the 512 px plane wrap, and unique tiles inside the wrap are still inside the wrap. |

---

## 1. The budget, confirmed from source rather than from the brief

`python3 tools/perspective_floor_gen.py --report`, run 2026-09-05 in this tree:

```
  rows that draw beam seams         : 27 of 72 (period > lod 20.0 px)
  unique tiles the floor needs      : 121
    of which APPENDED (new tiles)   : 0
  slots reclaimable                 : 123 (121 band-exclusive + 2 unreferenced)
  blob length  320 -> 320   (capacity 400, static budget 320, band reserve 80)
```

Cross-checked against `tools/vram_map.py` (generated from `games/sonic4/vram.toml`):
`BG_TILE_CAPACITY = 400`, `BG_BAND_RESERVE = 80`, `BG_STATIC_TILE_BUDGET = 320`.
So the brief's figures hold: **121 of 123, `band_reserve` untouched at 80.**

### The ceiling nobody has written down yet

The blob is 320 tiles. The band owns 121 of them exclusively plus 2 unreferenced,
and matched 0 existing art, so **the rest of the plane owns 320 - 123 = 197 tiles**
that this band can never touch. Therefore, for any band tile count `X`:

    blob = 197 + X,   and blob <= BG_TILE_CAPACITY = 400

**`X <= 203`. That is the hard VRAM ceiling for this band**, and it is bounded by
`waterline_strips` at slot 1424, not by policy. `band_reserve` is policy: it is a
*generator* budget only (`tools/gen_vram_map.py:42-47`, *"Nothing else consumes it
yet"*), so spending into it displaces nothing running today, but it does spend the
headroom held for a future BgAnim band and it makes `vram.toml`'s declared static
budget wrong unless it is lowered in the same edit.

    band tiles  123 (today)  -> blob 320 -> band_reserve 80  (shipped)
    band tiles  158          -> blob 355 -> band_reserve <= 45
    band tiles  176          -> blob 373 -> band_reserve <= 27
    band tiles  199          -> blob 396 -> band_reserve <= 4
    band tiles  204          -> blob 401 -> OVER CAPACITY BY 1

---

## 2. What the band actually contains, measured cell by cell

Rasterised from `SHIPPED` and cut the way the bake cuts it. Cell rows 48..63,
apex at plane x 159.5 = cell 19.94:

| cell row | period across its 8 px rows | unique tiles, raw | unique, flip-canonical |
|---|---|---|---|
| 48..59 | 0.0 .. 17.6 | 1 each | 1 each |
| 60 | 18.0 .. 21.2 | 1 | 1 |
| 61 | 21.6 .. 24.8 | **54** | 40 |
| 62 | 25.2 .. 28.4 | **54** | 39 |
| 63 | 28.8 .. 32.0 | **49** | 37 |
|  | | | **121 total** |

**Three cell rows carry the fan.** Row 60 is nominally a seam row (period 21.2 > lod
20) but `lod_fade` 6 leaves its contrast at about 0.03 of a shade step, so it
rasterises to a single flat tile. Rows 48..59 are the graded floor and the wall
above it, 7 distinct tiles between them.

### Where the repeats are, and which of them are real

The two dedup mechanisms are not the same thing and only one of them is a repeat:

* **Flip merges (lossless).** `canon()` stores one canonical tile and sets the VDP's
  H/V bits so the rendered pixels are the original. Row 61 merges 14 tiles this way,
  62 merges 15, 63 merges 12. The H merges are the fan's own mirror symmetry about
  the apex and are *correct*: a left-leaning beam at plane x below 159.5 is the
  H-flip of a right-leaning one above it. The V merges are also lossless, and I
  checked this specifically because a V flip inside a fan row would invert a beam's
  lean: it does not, because the flag returned is the one that *reproduces* the
  original tile from the stored canonical form. **No wrong-leaning tile is emitted.**
* **Exact translation repeats (the real repeat).** Row 61: 10 cells. Row 62: 10.
  Row 63: 15. **35 of 192 fan cells, 18.2%.** They cluster at cells 1..42, i.e.
  around and left of the apex, where a whole number of beam periods happens to land
  on a whole number of cells across all eight pixel rows of the cell row at once.

So the honest statement of where we are: **the art already has a per-row period and
is already 82% free of repeat within a plane width.** The brief's premise that ours
"draws one fan into a plane that repeats" is true of the *plane*, not of the *tiles*.

For scale, Toy Story's roughly 38 unique tiles per cell row sits between our 37 and
our 40 flip-canonical counts. **We are not behind them on per-row tile variety.** We
are behind them on row count (3 against about 5) and on the plane wrap.

---

## 3. Costing "no repeat within a plane width"

Forcing all 64 cells of a fan row distinct means defeating both mechanisms above,
which needs asymmetric per-cell detail (grain, knots) added to the raster. The cost
is then exactly 64 per art row plus the graded rows, and it is independent of how
the detail is drawn:

    cost = 7 (graded/wall rows) + 64 * (art cell rows)

Measured against the lod sweep, all at `near_pitch` 32 (each row rendered and cut,
not extrapolated):

| `lod_px` | shipped tiles | art cell rows | per-art-row raw unique of 64 | **no-repeat cost** | blob | verdict |
|---|---|---|---|---|---|---|
| 10 | 247 | 6 | 63, 64, 62, 54, 54, 49 | **390** | 587 | over capacity by 187 |
| 12 | 240 | 6 | 55, 64, 62, 54, 54, 49 | **390** | 587 | over capacity by 187 |
| 14 | 204 | 5 | 62, 62, 54, 54, 49 | **326** | 523 | over capacity by 123 |
| 16 | 176 | 5 | 27, 62, 54, 54, 49 | **326** | 523 | over capacity by 123 |
| 18 | 158 | 4 | 56, 54, 54, 49 | **263** | 460 | over capacity by 60 |
| **20 (shipped)** | **121** | **3** | 54, 54, 49 | **199** | **396** | **fits, `band_reserve` 80 to 4** |
| 24 | 80 | 2 | 49, 49 | 135 | 332 | fits, reserve 80 to 68 |
| 28 | 51 | 2 | 15, 47 | 135 | 332 | fits, reserve 80 to 68 |

A `near_pitch` sweep at lod 20 was run as a control and is not a lever: coarsening
the pitch adds art rows and tiles without raising per-row uniqueness
(pitch 40 gives rows of 25/60/50/52/40 of 64; pitch 48 gives 9/58/54/47/43/36).

**So the literal parcel, at today's 3 art rows, costs 199 tiles against 123
available: over by 76, and it fits under the 203 hardware ceiling with 4 to spare
only by taking `band_reserve` from 80 to 4.**

**The literal parcel at Toy Story's row count is BLOCKED.** 5 art rows fully unique
is 326 tiles, a blob of 523 against a capacity of 400: **over by 123 tiles**. To
reach it the BG arena would have to grow from 400 to at least 523, which means
absorbing all 48 tiles of `waterline_strips` and then 75 more from another region.
That is a VRAM re-layout, not a bake.

There is one arithmetic coincidence worth flagging because it will otherwise be
rediscovered: **5 art rows at today's repeat level (lod 14, 204 tiles) is exactly
one tile over capacity.** lod 16 gives 5 art rows for 176 tiles and does fit.

---

## 4. The part that matters: this buys nothing for the reported defect

The onset of *"the first few are good then a few after get weird and point away"*
is derived in `docs/witness/floor-outer-stripes-2026-09-05.md` §3 and in the
generator's header, and it is a property of the **plane**, not of the tiles:

> Plane B wraps every 512 px against a 320 px screen, so the floor's near row may
> slide 192 px before the window shows the NEXT copy of the fan, whose apex is at
> screen 159.5 + 512 = 671.5, off the side.

Whatever tiles the 512 px are made of, the wrap shows **the same 512 px again**.
Making all 64 cells of a row distinct changes the pixels inside one copy; it does
not change that there is a second copy, nor where its apex is. **Option 1 below is
therefore a look improvement with no bearing on the defect the owner reported.**

The onset is `camX = 192/F`. That is the only quantity that moves it.

---

## 5. The option that does fix it, and it costs zero tiles

`games/sonic4/data/levels/ojz/act1/act_descriptor.emp` declares `GRID_W = 3`,
`GRID_H = 3`, and `SECTION_SIZE = $0800` (`engine/system/constants.emp:241`), so
the act is 6144 world px wide and **the camera x range is 0..5824**
(`SCREEN_WIDTH` 320).

The floor layer is `layer(world_y: 440, fa: FACTOR_1, fb: FACTOR_0,
curve: SceneCurve.To(FACTOR_1_8))` at `games/sonic4/data/effects/ojz_scenes.emp:869-870`,
spanning screen lines 152..223, so `span` = 72 and the ramp's zero is the apex row.

| curve end | clean range `192/F` | plane travel over the act | window sweep | covers the whole act? | `k` at camera 736 | `k` at camera 5824 |
|---|---|---|---|---|---|---|
| `FACTOR_1` | 192 | 5824 | 6144 px | no (3%) | 10.22 | 80.89 |
| `FACTOR_1_4` | 768 | 1456 | 1776 px | no (13%) | 2.56 | 20.22 |
| **`FACTOR_1_8` (shipped)** | **1536** | **728** | **1048 px** | **no (26%)** | **1.278** | **10.11** |
| `FACTOR_1_16` | 3072 | 364 | 684 px | no (53%) | 0.639 | 5.06 |
| **`FACTOR_1_32`** | **6144** | **182** | **502 px** | **YES (100%)** | **0.319** | **2.53** |

**`FACTOR_1_32` is the first factor whose clean range covers the act.** Equivalently:
the plane B window sweeps only 502 px across the entire act, which is less than the
512 px plane, so **the wrap never reaches the screen anywhere in OJZ act 1.** The
defect disappears for zero tiles, by moving one identifier at `ojz_scenes.emp:870`.
`FACTOR_1_32` exists in the vocabulary (`engine/level/parallax_dsl.emp:32`).

The model is confirmed against the running ROM, not asserted: `k = camX * F / span`
predicts 736 * 0.125 / 72 = **1.278 px/row**, against the **-1.282** measured on the
ROM at camera 736 (`docs/DEFERRED_WORK.md`, "SPREAD is the art, APEX is the
correction"). The same entry measured -2.113 at camera 1216 and -3.225 at 1856; the
formula gives 2.111 and 3.222.

**The cost of `FACTOR_1_32` is scroll rate and it is entirely a look call.** The
floor's near row slides 182 px across 6144 px of walking. At `FACTOR_1_16` it slides
364 px and stays clean for the first 53% of the act.

---

## 6. What changing the gain costs, checked rather than repeated

The brief's expectation was "nothing but a constant, since the fan's geometry is
indifferent to the curve end factor". **The first half checks out and the second
half has a correction that matters.**

**Confirmed: the geometry is F-indifferent.** From the generator's own equation (2),
the composited beam is `screen x = vx + dy * (j*P - camX*F/span)`. At `dy = 0` that
is `vx` for every `F` and every `camX`. The apex stays on screen column 159.5. No
tile changes, no re-bake, no re-rasterise. **The raw gain change is one identifier
and zero tiles**, and it moves the wrap onset in the same direction (better), which
is the reverse of a trade.

**Correction 1: "-1.28 versus -0.6" is not a comparison of two designs.** `k` is
linear in camera x through the origin, so the two numbers are points on two
different lines at two different camera positions, and theirs is unpublished. This
is already recorded in `docs/DEFERRED_WORK.md` and it is right.

**Correction 2, and this one is new: the camera-free comparable that DEFERRED_WORK
proposes as "the tuning target" cannot be tuned by F at all.** That entry offers
`dk / |d(base)|` as the F-free quantity, measuring ours at 0.04155 and 0.04119 and
theirs at 0.00986, and concludes *"ours responds about 4.2x more per unit of
background movement, and that, not any raw gain, is the tuning target"*.

For our ROM that ratio is **identically 1/24, for every F**. The layer is
`fb: FACTOR_0`, so the "base" sampled at line 176 is not a whole-plane base at all:
it is the ramp's own value 24 lines below its zero at line 152.

    k(camX)        = camX * F / 72          -> dk/dcamX      = F/72
    base(176)      = camX * F * 24 / 72     -> d(base)/dcamX = F * 24/72
    ratio          = (F/72) / (F*24/72)     = 1/24 = 0.04167,  F cancels

against 0.04155 and 0.04119 measured on two independent camera intervals. The
agreement is to about a third of a percent, and the derivation says the quantity is
`1 / (lines from the ramp's zero to the sample line)` and nothing else.

**Consequence for the owner's ask.** There are two different "gains" and they cost
very different things:

* **The raw per-row lean `k`.** Free. One identifier. `FACTOR_1_16` puts `k` at
  0.639 px/row at the lab camera (736), which is essentially their measured 0.6.
  **Checkable prediction for the foreground:** at `FACTOR_1_16` and camera 736 the
  ramp totals 46 px over 72 lines, so the table's line-to-line deltas become **-1
  and 0** rather than today's -1 and -2, which is exactly the signature Oracle read
  off Toy Story.
* **The camera-free ratio `dk/d(base)` = 1/24.** Not free and not reachable by F.
  Moving it means moving the apex row away from the floor band, i.e. changing
  `horizon_row` in the art and `world_y` in the layer together. Their 0.00986 would
  put their ramp zero about 101 lines above line 176, i.e. roughly 77 lines above
  their floor's top edge, where ours sits *on* it. That is a different floor
  geometry, it re-rasterises the whole band, and its tile count would have to be
  re-measured. **Carry DEFERRED_WORK's own caveat: their `d(base)` may mix a real
  whole-plane base with their ramp, which would make 0.00986 an underestimate.**

---

## 7. Streaming, if the design needs it

**It is specified but not built, and it sits behind two other unbuilt things.**
`docs/DEFERRED_WORK.md` carries "SPEC: BG tile paging - the 448 region as a residency
cache (step 2b)" with a full design at `docs/research/2026-08-29-bg-tile-paging.md`:
**4 aeon parcels + 1 tools parcel**, about 320 B engine ROM, about 75 B RAM
(`PAGE_FRAMES_MAX` 15 to 23, which owes the pin/goldens ritual), zero new VRAM. It is
explicitly *"a hard dependency, not an optimisation"* on the nametable streamer,
whose own build order (same file, "SPEC: Per-section background grid with seam
streaming") puts the **horizontal axis at step (c) of five**, because horizontally
there is no single BG camera, only per-band `Parallax_Current_Scroll_B`.

That spec's verdict on the general version of this question is discouraging and
should be quoted: *"It buys nothing for horizontal variety: the shipped art uses
<= 16 distinct tiles per 64-cell row; art that is horizontally unique needs 1,856
tiles/window and no cache in this VRAM map holds that."* **That figure is for a
29-row window. Our band is 3 rows, so it does not transfer**, and the floor case is
about 10x smaller.

Sized for this band specifically. `Draw_BG_TileColumn` (`engine/level/plane_buffer.emp:521`)
already writes a 64-word plane B nametable column through `Plane_Buffer`; what is
missing is streaming the tile **art**, which `BG_Init` (`engine/level/bg.emp:88`)
loads once, whole, display off.

| curve end | unique fan cells needed over the act | ROM tiles at 3 art rows | raw ROM | resident tiles |
|---|---|---|---|---|
| `FACTOR_1` | 768 | 2304 | 73.7 KB | ~132 |
| `FACTOR_1_4` | 222 | 666 | 21.3 KB | ~132 |
| `FACTOR_1_8` | 131 | 393 | 12.6 KB | ~132 |
| `FACTOR_1_32` | 63 | 189 | 6.0 KB | fits statically, **no streamer needed** |

(Resident = the 40 visible cells plus margin, times 3 art rows; the plane's other
24 cell columns are off-screen and scrubbable, which is the spec's "write each row
twice" move.)

**The sharp way to put the trade: streaming buys scroll RATE, not uniqueness.** At
`FACTOR_1_32` the act's whole plane travel fits inside one plane width, so unique
art needs no streamer at all. A streamer only earns its keep if the owner wants both
a *fast* floor and unique art, and at `FACTOR_1` that is 73.7 KB of raw fan art plus
five parcels of engine work.

---

## 8. The options, with costs, in the order they cost

| # | option | tiles | `band_reserve` | fixes the reported defect? | other cost |
|---|---|---|---|---|---|
| 0a | `To(FACTOR_1_16)` | **0** | 80, untouched | **53% of the act** | floor slides 364 px over the act; `k` at camera 736 becomes 0.639, matching their 0.6 |
| 0b | `To(FACTOR_1_32)` | **0** | 80, untouched | **YES, act-wide** | floor slides 182 px over the act; reads close to painted |
| 1 | no repeat within a plane width, 3 art rows | 199 (+76) | 80 to 4 | **no** | needs asymmetric per-cell grain added to the raster; spends the BgAnim headroom |
| 2a | 4 art rows at today's repeat level (lod 18) | 158 (+35) | 80 to 45 | no | more fan depth, same wrap |
| 2b | 5 art rows at today's repeat level (lod 16) | 176 (+53) | 80 to 27 | no | 5 rows, first one faint |
| 2c | 5 art rows at lod 14 | 204 | n/a | no | **1 tile over hardware capacity** |
| 3 | 5 art rows AND no repeat (the literal Toy Story description) | 326 | n/a | no | **123 tiles over capacity. BLOCKED** without a VRAM re-layout |
| 4 | horizontal BG art streaming | 6 to 74 KB ROM | n/a | **yes, at any F** | 4+1 parcels behind 2 unbuilt specs; `PAGE_FRAMES_MAX` raise owes the pin/goldens ritual |

Options 0 and 1..2 are orthogonal and can be taken together: 0b plus 2b is
zero-defect and 5 art rows for 176 tiles and `band_reserve` 27.

---

## 9. What could not be settled here

* **Toy Story's camera x at the two floor captures.** Without it their `k` cannot be
  put on the same line as ours and "-0.6 versus -1.28" stays uncomparable. Needs the
  foreground.
* **A clean `$0D` read at their floor.** Oracle's read was at frame 22514 in a
  different scene where HSCR read whole-plane. The delta shape corroborates the base
  but the base is not measured at the floor. Stated here, not resolved.
* **Whether their `d(base)` mixes a whole-plane base with their ramp.** If it does,
  0.00986 is an underestimate and the geometric difference in §6 is larger than
  1/24 against 1/101.
* **The `FACTOR_1_16` delta-signature prediction** (-1 and 0 rather than -1 and -2
  at camera 736) is derived, not measured. `tools/floor_hscroll_dump.py` against a
  ROM built with that one identifier changed would settle it in one run. TAGGED for
  the foreground; a background agent may not touch an emulator.
* **Whether the 18.2% of exact repeats is visible at all.** They cluster around the
  apex where the beams are closest together. Nobody has looked at whether the owner
  can see them, and option 1 costs 76 tiles to remove something that may not be
  on screen.
