# Pricing the plane-size lever: is 64x64 earning its 512 tiles?

**Date:** 2026-09-09 · **Branch:** `measure/plane-size-lever` · **Status:** measurement, no
behaviour changed. This parcel PRICES the lever; pulling it is the owner's ruling.

## The question, and whose it is

The owner, 2026-09-08:

> "I'm half wondering too if we should have the nametable for bg at 64x32 since the sonic
> games can handle that with bgs that are like 5x as tall or long as our current one"

Aeon runs both scroll planes at 64x64 (VDP reg `$10` = `$11`), 8 KB each, 512 tiles of VRAM
between them — 25% of all VRAM, holding no art. The classic Sonic games run 64x32. Plane size
is ONE register shared by A and B: it is both planes or neither. So the owner's question about
the background necessarily prices the foreground too, and the foreground is what 64x64 was
chosen for.

## The two stated reasons, verbatim

`docs/ENGINE_ARCHITECTURE.md` §2.3, "Why 64x64 scroll planes ($9011)":

| Property | 64x32 ($9001) | 64x64 ($9011) |
|---|---|---|
| Vertical buffer | ~32px beyond 224px display | ~288px beyond display |
| VSRAM deformation range | ±32px per column | ±288px per column |

> "With 64x32, fast vertical scrolling constantly hammers nametable updates with only 4 rows of
> buffer. With 64x64, 36 rows of buffer absorbs even the fastest vertical movement."

Those are the two claims under test. Result up front: **reason 1 is refuted by the engine's own
code — the mechanism it describes is not implemented.** Reason 2 is under measurement.

---

## Part 1 — What a vertical transition actually costs per frame

### 1.1 The booked fact that no longer holds

Memory carries "teleports are pure rebases; seam freeze 13 frames to 0". **That is superseded.**
`docs/ENGINE_ARCHITECTURE.md:19` describes the shipped camera as a

> "continuous world-space camera over a 64x64 wrapping VDP plane (classic S2/S3K — **no slots,
> no teleport, no rebase**)"

and §2.3's lifecycle note repeats it ("no slots or teleports are reintroduced"). So the row-cost
question has the plain shape after all: a continuous camera scrolling a wrapping ring. It is
modelled as "how fast can the camera move", because that is what the code does.

### 1.2 The production rate, derived from the engine's own constants

`engine/system/constants.emp`:

| Constant | Line | Value | Meaning |
|---|---|---|---|
| `CAM_MAX_Y_STEP` | 1049 | `16` | max camera Y movement, px/frame |
| `VFILL_ROWS_PER_FRAME` | 1006 | `2` | tile rows the vertical fill may produce per frame |
| `SECTION_V_REACH_PX` | 879 | `SCREEN_HEIGHT + 7` = `231` | camera-relative far edge, Y |
| `SECTION_V_REACH_ROWS_MAX` | 881 | `(7 + 231) >> 3` = `29` | rows past the camera's own row |
| `PLANE_V_CELLS` | 595 | `64` | plane height in cells |
| `TILE_CACHE_ROWS` | 329 | `60` | viewport 28 + margin 16x2 |

The engine asserts the coupling itself (`constants.emp:1058`):

```
ensure(CAM_MAX_Y_STEP <= VFILL_ROWS_PER_FRAME * 8,
       "camera Y step outruns the vertical tile-cache fill rate ...")
```

**16 px/frame = exactly 2 rows/frame, and the fill produces exactly 2 rows/frame.** Production
equals consumption at the cap, with — in the comment's own words at `constants.emp:999` —
"ZERO catch-up headroom".

**So: how many nametable rows must be produced per frame at the fastest legal vertical camera
speed? Two.** Not "as many as the buffer can absorb" — two, capped by `VFILL_ROWS_PER_FRAME`,
which is itself the thing that bounds `CAM_MAX_Y_STEP`.

### 1.3 The decisive measurement: the streamer never uses the off-screen rows

`engine/level/section.emp`, the bottom-edge vertical loop (~line 778):

```
        move.l  Camera_Y, d6
        swap    d6
        move.w  d6, d7
        addi.w  #SECTION_V_REACH_PX, d7        // SCREEN_HEIGHT + 7
        lsr.w   #3, d7                          // d7 = bottom_needed world row
```

and the top-edge loop (~line 830):

```
        lsr.w   #3, d6
        move.w  d6, d7                          // d7 = top_needed world row
```

`d7` is the loop's stop target. **The bottom target is the bottom of the viewport; the top
target is the top of the viewport.** The vertical streamer draws exactly the visible window and
not one row further. It has no lead term, no prefetch distance, and no configurable margin.

This is the whole of reason 1. The doc credits 64x64 with "36 rows of buffer [that] absorbs even
the fastest vertical movement" — but **nothing ever writes into those 36 rows.** They hold the
wrap twin of world content 64 rows (512 px) away, left there the last time the camera passed
that plane row. The rows are drawn just-in-time at the viewport edge, which is precisely what a
64x32 engine does, and precisely what the owner said the originals do.

The build guard that would have caught a real dependency is `constants.emp:912`:

```
ensure(SECTION_V_REACH_ROWS_MAX <= PLANE_V_CELLS - 1,
       "the row fill reaches {SECTION_V_REACH_ROWS_MAX} rows past the camera's own row,
        but the plane ring is only {PLANE_V_CELLS} cells tall ...")
```

Today: `29 <= 63` — 34 rows of slack, and the comment beside it says so ("22 and 34 columns of
slack, which is the number the derivation needed and could not find written down anywhere").

**At 64x32 this guard reads `29 <= 31`. It still passes, with 2 rows of slack.** The engine's own
declared streaming contract survives the shrink.

### 1.4 Do 4 spare rows cover it?

The viewport spans 224 px = 28 whole rows, plus a partial row at each edge when the camera Y is
not row-aligned: 30 rows touched worst case. A 32-row plane holds 30 viewport rows **plus 2**.

Walk the worst case. Let the plane hold world rows `[B-31, B]` with `B` = viewport bottom, so the
viewport is `[B-29, B]`. The camera descends 16 px = 2 rows. `.bot_loop` writes rows `B+1, B+2`.
Row `B+1` lands at plane row `(B+1) & 31`, which currently holds world row `B-31` — four rows
above the new viewport top (`B-27`), i.e. off-screen. **No visible cell is overwritten.** The
same walk at 64x64 clobbers world row `B-63` instead. Both are off-screen; the difference is
invisible.

**Answer: yes, 4 spare rows cover it — 2 are enough, and 64x32 supplies 2.** The minimum that
works is `SECTION_V_REACH_ROWS_MAX + 1 = 30` rows, which is what the engine already asserts. The
margin required is set by the fill rate matching the camera cap, not by the plane height.

The residual risk is unchanged by plane size and worth stating plainly: with zero catch-up
headroom, a frame whose fill is deferred (plane buffer full, or a lag frame skipping
`VInt_DrawLevel`) shows an undrawn row at the leading edge. **At 64x64 that row shows the wrap
twin from 512 px away; at 64x32 it shows the twin from 256 px away. Both are garbage. The
artifact is the same artifact.** 64x64 does not buy a graceful degradation here, because the
streamer never banked anything in the space that would have provided one.

### 1.5 The plane buffer gets CHEAPER, not tighter

`PLANE_BUFFER_SIZE = 1536` (`constants.emp:839`). The per-entry costs are spelled in the
producers:

| Entry | Source | Bytes at 64x64 | Bytes at 64x32 |
|---|---|---|---|
| FG column (`Draw_TileColumn`) | `plane_buffer.emp:68` — `8 + PLANE_V_CELLS*2` | **136** | **72** |
| FG row (`Draw_TileRow_FromCache`) | `plane_buffer.emp:295` — `4 + PLANE_H_CELLS*2` | **132** | 132 (unchanged) |
| BG column (`Draw_BG_TileColumn`) | `plane_buffer.emp:524` — `4 + 64*2` | **132** | 68 |

The brief's measured figure — `Plane_Buffer_Ptr` peaked at **272 B** of 1536 under horizontal
motion — **derives exactly**: `2 columns/frame x 136 B = 272 B`. The measurement was at the
camera cap, and it is the horizontal axis, which is the expensive one.

The vertical axis this question is about costs `2 rows/frame x 132 B = 264 B`. Sustained
**diagonal** at both caps is therefore `272 + 264 = 536 B` of 1536 — still far under the
drop threshold. That threshold is not a tuned number either; it is spelled inline at
`section.emp:686/744` as `PLANE_BUFFER_SIZE - 2 - (8 + PLANE_V_CELLS*2)` = `1536 - 2 - 136` =
**1398**, which is where the brief's figure comes from.

**At 64x32 the same worst-case diagonal costs `2x72 + 2x132 = 408 B`, and the column drop
threshold rises to `1536 - 2 - 72 = 1462`.** Halving the plane height halves the dominant
producer, because a column write is `PLANE_V_CELLS` words and a row write is `PLANE_H_CELLS`
words — and only the former shrinks.

The same halving lands in the VBlank DMA window. `VInt_Level` charges the plane drain against
`DMA_Budget_Remaining` (seeded from `DMA_BUDGET_NTSC = 6144`, `constants.emp:670`), so a 64x32
column write hands 64 bytes per column back to the art streamer's Important/Deferrable queues.

**Conclusion for Part 1: the per-frame vertical row cost is 2 rows (264 B), it is set by
`VFILL_ROWS_PER_FRAME` and not by the plane, the plane's extra 32 rows are never written by the
vertical streamer, and shrinking the plane makes the horizontal streamer measurably cheaper.
Reason 1 does not survive contact with the code.**

---

## Part 2 — What the VSRAM range is actually used for

`±288 px` is a capability. The question is which shipped effect needs more than `±32 px`.

### 2.1 What consumes plane slack is the SPREAD, not the offset

Every column independently indexes a 224 px window into a 512 px (or 256 px) tall plane, and the
VDP masks the vscroll value to the plane height, so any single column can be displaced anywhere —
it just wraps. What costs you is the **difference between columns in one frame**: once
`max(offset) - min(offset)` exceeds `plane_height - screen_height`, some column is showing content
that is simultaneously on screen elsewhere, i.e. visibly duplicated art.

That is where 288 comes from: `512 - 224 = 288` at 64x64, `256 - 224 = 32` at 64x32. **Note the
doc's own figure is mis-stated as `±288`. It is a 288 px total budget, not ±288** — you can spend
it as `0..+288` or as `-144..+144`, but not both ways at once. Same for the `±32`.

### 2.2 The data format cannot express more than ±128 px

`engine/level/parallax.emp:2864-2867`, `Parallax_Step5_Vscroll`'s `.col` loop — the single place a
deform table becomes a VSRAM offset:

```
        move.b  (a1, d4.w), d5                      // sample (signed byte)
        ext.w   d5
        asr.w   d3, d5                              // offset = sample >> v_deform_shift_bg
```

The source is a **signed byte** and the scale is an arithmetic **right** shift — never a left
shift. So a table entry is bounded to `-128..+127` before scaling, and scaling only ever shrinks
it. **The maximum per-column spread this pipeline can physically request is 255 px, at shift 0.**

That is already below 288. The `±288 px per column` capability the design doc credits 64x64 with
**is not reachable through the shipped authoring path at all** — no scene could ask for it if it
wanted to. Reaching it would need a widened table format, which nothing has proposed.

### 2.3 Consumer table — every call site, by the magnitude it actually requests

Enumerated by call site across `engine/level/parallax*`, `engine/effects/raster*`,
`engine/level/bg_anim.emp` and the shipped scenes under `games/sonic4/data/`. Magnitudes were
derived by rebuilding each generator's table bit-for-bit (the exact `asr.w`/mask/clamp arithmetic)
and sliding the engine's own 20-column read window across every reachable phase, then taking
`max - min` per window. The rebuild reproduces the design doc's own inline hand-derived table
(`shift 2 → 6 px edge bow`) exactly, which is the check that the model is the code's model.

| Call site | What it is | Shipped scene(s) that reference it | Peak per-column spread |
|---|---|---|---|
| `parallax.emp:2864` `.col`, table `deform_sine(amp:20, period:64)` (`DeformTable_Rocking`), shift 0 | Timer-mode rocking | `Scene_Rocking_Slow`, `Scene_Rocking`, `Scene_Rocking_Fast` (`ojz_scenes.emp:566-571`) | **31 px** |
| `parallax.emp:2796` screen-anchor + `.col`, `v_column_floor_screen(edge_offset:24)`, shift 0, lean_gain 2 | Perspective floor | `Scene_Perspective` (`ojz_scenes.emp:713`) | **31 px** |
| same, shift 0, lean_gain 4 | Perspective floor, faster lean | `Scene_Perspective_Dramatic` (`ojz_scenes.emp:714`) | **31 px** (gain changes lean *rate*, not the `VP_LEAN_MAX`-bounded apex range) |
| same, shift 2, lean_gain 0 (apex pinned) | Perspective floor, subtle | `Scene_Perspective_Subtle` (`ojz_scenes.emp:712`) | **6 px** |
| same, shift 2, lean_gain 0 | Perspective floor | `Scene_Perspective_Floor` (registry 20, `ojz_scenes.emp:931`) | **6 px** |
| `raster_dsl.emp:614` `fx_vscroll_split` → `stream_vsram(2, …)` | Whole-plane-B mid-frame scroll split | `ojz_effects.emp:1147, 1908, 2136` | **0 px of spread** — writes the *same* value to every column; it is a split, not a deformation |
| `parallax_dsl.emp:220` `v_column_perspective`, `:230` `v_column_floor` | Table generators | **DECLARED BUT UNREFERENCED** — no shipped scene points at either; `ojz_scenes.emp:120-138` records `v_column_floor` as the OLD table, superseded 2026-09-04 | n/a |
| `engine/level/bg_anim.emp` | — | Touches no VSRAM at all (zero `vscroll`/`VSRAM` hits) | n/a |

`test/poison/*.emp` also spell `v_deform:`, but those are deliberate red-first gate fixtures, not
shipped content.

### 2.4 Verdict on reason 2

**The largest per-column vertical deformation spread any shipped aeon scene requests is 31 px.**

- Does anything exceed **32 px**? **No.** Every shipped scene sits at or under 31 px — one pixel
  under the 64x32 budget, across all seven scenes that use the feature.
- Does anything exceed **256 px**? **No, and nothing can**: the signed-byte table format caps the
  representable spread at 255 px (§2.2), so 288 px was never reachable.

Two things are true at once here and both matter. The shipped scenes fit inside 32 px — but they
fit with **one pixel** of margin, which is not comfort, it is coincidence. Nothing in the engine
constrains a scene to 31 px; `deform_sine(amp:20)` at shift 0 happens to land there, and
`deform_sine(amp:24)` would not. **This is the finding that most constrains the recommendation,
and it is the one I would put in front of the owner first.** See Part 4.

## Part 3 — The honest cost of the other direction

*(pending)*

## Part 4 — Recommendation and its falsifier

*(pending)*
