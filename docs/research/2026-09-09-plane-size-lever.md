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

Both stated reasons fell. The plane size is nonetheless load-bearing — **for a third reason that
is written down nowhere.**

### 3.1 The real consumer: Plane B is a RESIDENT 512-px-tall background

`docs/ENGINE_ARCHITECTURE.md:1742`: Plane B is "Drawn once by `Section_RedrawPlanes` at level
init. Continuous scrolling never rebases or redraws Plane B during play."

`Draw_BG_TileColumn` — the BG streaming producer — exists at `plane_buffer.emp:521` and has
**zero callers** (grep across `engine/` and `games/` returns the definition and nothing else).
It was built and never wired up. So the background is not streamed; **the entire background image
must be resident in the plane at once**, and that is what the 64 rows actually buy.

**Measured, independently** (`games/sonic4/data/generated/ojz/act1/zone_bg.bin`, 8192 B,
decoded column-major per `blob[col*128 + row*2]`):

| Region | Cells | Non-zero | Unique tile indices |
|---|---|---|---|
| rows 0-31 | 2048 | **2048 (100%)** | 121 |
| rows 32-63 | 2048 | **2048 (100%)** | **248** |
| rows 48-63 | 1024 | **1024 (100%)** | 121 |

Rows 32-63 carry *more* tile variety than rows 0-31. This is real shipped content, and rows 48-63
specifically are the perspective-floor placeholder's exclusive target
(`tools/perspective_floor_gen.py:206`, `PLANE_ROWS = 64`).

**`docs/LEVEL_EDITOR_SPEC.md:256` is STALE** — it still claims "Rows 32-63 are init-only today
(the injector zero-pads 32-row layouts)". The bytes say otherwise. That line should be corrected
regardless of what happens to this lever.

Are those rows *reachable*? Yes. `SECTION_SIZE = $0800` (2048 px) over OJZ's 4x3 grid gives a
6144 px act; camera Y travel is ~5920 px; at `v_factor: 3` (`ojz_scenes.emp:233` — "eight times
compressed") the BG walks `5920 >> 3 = 740 px` of plane. All 512 rows pass the screen.

**But note what that number means: 740 > 512. The background already wraps mid-act today.**
64x64 does not solve the background-height problem; it only makes the repeat less frequent. This
is exactly why `docs/research/2026-08-29-tall-background-map.md` exists.

### 3.2 What concretely breaks

| # | Site | What it assumes | Severity |
|---|---|---|---|
| 1 | **`parallax.emp:685`** `PLANE_B_CELL_ROWS = 64`, `PLANE_B_SPAN = 512` | Its comment claims it is "derived from the cell count rather than typed as 512" — **it is not.** It is a second independent literal `64`, referenced against `PLANE_V_CELLS` nowhere in the tree. Its own `ensure(PLANE_B_SPAN == 512, "PLANE_B_SPAN drifted from the 64x64 Plane-B geometry")` **would still pass** after a `PLANE_V_CELLS` edit. | **A guard that cannot fail on the change it names.** The most dangerous site in the inventory — every downstream `and.w #PLANE_B_SPAN-1` wrap mask would silently mask against a plane that no longer exists. |
| 2 | `boot_data.emp:186` `dc.b $11 // $10: 64x64 scroll planes` | The actual VDP register byte is hand-typed. **No `ensure` ties it to `PLANE_H_CELLS`/`PLANE_V_CELLS`.** | Missing guard: editing only the constants builds clean and desyncs from hardware. |
| 3 | `bg.emp:51` `BG_LAYOUT_SIZE = 64*64*2` | Literal, not `PLANE_H_CELLS*PLANE_V_CELLS*2`. | Mechanical, but silent. |
| 4 | The bare `#63` literals in `section.emp` (`:272,319,698,755,806,851` masks; `:708,765,816,861` wrap spans) and `plane_buffer.emp` (`:140,432,434,440`) | **Mixed axes.** `:698,755,708,765` are COLUMN (stay 63); `:806,851,816,861` and `plane_buffer.emp:140` are ROW (must become 31). None follow `PLANE_V_CELLS`. | Real hand-audit. This is the "a site that uses the wrong one is invisible" hazard the constants file warns about at `:845`. |
| 5 | Rows 32-63 of the shipped OJZ background, incl. the rows-48-63 perspective floor | Real content, deleted by the shrink unless a BG row streamer lands first. | **The blocking cost.** |
| 6 | `tools/depth_onset_probe.py:478`, `tools/warp_mailbox_gate.py:91,211`, `tools/boot_override_gate.py:317`, `tools/perspective_floor_gen.py:185` | Hardcoded 8192-byte / 64-row plane. | Mechanical, unguarded. (`tools/canopy_record.py` and friends parse `constants.emp` at runtime and auto-follow — no edit needed.) |

### 3.3 What gets BETTER

- **384 tiles returned**, not 256. `plane_a` 256→128 and `plane_b` 256→128 frees 256; and
  `spare_nametable` (128 tiles at $6000) exists *only* because it is "the only `$2000`-aligned run
  left and 128 tiles is exactly a 64x32 plane" (`DEFERRED_WORK.md:27511`) — a reservation held to
  serve as a future plane base. Shrink the planes and that purpose is met by their own freed
  tails, so the reservation releases. **256 + 128 = 384.**
- **Object VRAM goes from 128 tiles to over 500.** The object neighbourhood (tiles 896-1023) is
  fully spent today with 1 free tile — the owner's "we can't have space for 0 objects".
- **The window plane becomes real.** `vram.toml` declares `window_plane` with
  `overlay_with = ["plane_b"]` — it aliases Plane B's tail and is unusable. At 64x32 Plane B ends
  exactly where the window begins and the overlap disappears, for free.
- **The horizontal streamer gets cheaper** (§1.5): 136 B → 72 B per column entry, and the same
  64 bytes/column back into the VBlank DMA window.
- **A column write stops zero-filling.** `Draw_TileColumn` emits `PLANE_V_CELLS` = 64 rows from a
  60-row cache and **zero-fills the last 4** (`plane_buffer.emp:160-168`, `.pA_zero`). At 32 rows
  the cache covers the plane entirely and the zero-fill legs become dead code.

---

## Part 4 — Recommendation, and the measurement that would refute it

### The recommendation

**Do not pull the lever today. Sequence it behind one specific piece of work: wire up a Plane B
row streamer. Then pull it, and take 384 tiles.**

The reasoning, stated so it can be attacked:

1. **Neither documented reason for 64x64 survives measurement.** The vertical buffer is never
   written (§1.3 — the streamer's stop target is the viewport). The VSRAM range is capped at
   255 px by the signed-byte table format and no shipped scene asks for more than 31 px (§2).
   **`docs/ENGINE_ARCHITECTURE.md` §2.3 should be corrected on both counts regardless of the
   ruling** — right now it justifies a 512-tile spend with two claims the code contradicts.
2. **But the plane is load-bearing anyway**, for the unwritten third reason: Plane B is a resident
   512-px background with no row streamer. Shrinking it today deletes shipped, on-screen art.
   *That* is what 64x64 is actually buying — and it is worth saying plainly that the engine has
   been paying 512 tiles for a reason nobody could have found in the docs.
3. **The gate is small and already scoped.** `docs/research/2026-08-29-tall-background-map.md`
   prices the BG streamer at "one new producer, one scheduler, 4 bytes of RAM, no new VRAM, and
   ~33 bytes/frame of DMA", with `Draw_BG_TileColumn` already written. And it reframes the whole
   question the way the owner did: **S3K's planes are 512x256** and S3K got a 2,816-px background
   out of that 256-px window by streaming. The owner's instinct is the S3K design.
4. **64x64 does not actually solve the problem it is being kept for.** OJZ already needs 740 px
   of background against a 512-px plane (§3.1). The background wraps mid-act *today*. Once a row
   streamer exists, plane height stops mattering almost entirely — which is precisely why the
   shrink becomes cheap right after that work and expensive before it.

Order of operations: (a) fix the two doc claims and the stale `LEVEL_EDITOR_SPEC.md:256`; (b) wire
`Draw_BG_TileColumn` into a vertical BG scheduler; (c) fix the `PLANE_B_CELL_ROWS` guard so it
actually derives from `PLANE_V_CELLS`, and add the missing `ensure` tying `boot_data.emp`'s
`$11` to the constants — **these two guards must land before the flip, not with it**, because
both are silent; (d) then flip, and audit the mixed-axis `#63` literals as its own step.

### The derived threshold this rests on

At the camera cap the BG moves `16 >> 3 = 2 px/frame`, so it crosses one tile row **every 4
frames**. A BG row entry is `4 + PLANE_H_CELLS*2 = 132 B` (plane width is unchanged by this
lever), i.e. **33 B/frame** against a 1536 B plane buffer and a 6144 B NTSC DMA window — **0.5% of
the window.** (This derivation, made independently here from `CAM_MAX_Y_STEP` and `v_factor: 3`,
lands on the same ~33 B/frame the 2026-08-29 doc reports — an agreement between two derivations,
not a number copied from a neighbouring doc.)

### What would prove me wrong

Name the falsifier precisely, or the recommendation is a preference:

1. **The BG row streamer's real cost exceeds the derived 33 B/frame by more than ~10x.** My case
   rests on that figure. Measure `Plane_Buffer_Ptr` peak and the VBlank DMA charge under sustained
   vertical motion *with the streamer wired*, on the DEBUG shape. If sustained diagonal +
   BG-streaming peak crosses the 1462 B column drop threshold, or the DMA window starves the art
   streamer, then the resident background is the right design and 64x64 must stay. **This is the
   single measurement that decides it.**
2. **A scene requests more than 32 px of per-column deformation.** My §2 result is a fact about
   *today's* seven scenes, and they clear 32 px by **one pixel**. `deform_sine(amp: 24)` at shift 0
   would break it. If the owner's authoring plans include stronger vertical deformation, reason 2
   becomes true prospectively even though it is false today — and the correct response is a
   `ensure` capping authored deform spread at `PLANE_V_CELLS*8 - SCREEN_HEIGHT`, which does not
   exist and should regardless of this ruling.
3. **Rows 32-63 turn out to be reachable only through content that cannot be re-authored.** I
   showed they are populated and reachable; I did *not* show the perspective-floor placeholder can
   be reproduced by a streamer. If that feature structurally needs 16 resident rows below the
   viewport, it is a counter-example to step (b).

### What I could NOT measure — TAGGED for the controller

Everything above is source, baked data and derivation. Two claims would benefit from a runtime
confirmation I did not run, and neither changes the recommendation:

- **Runtime confirmation that `Section_Bottom_Row_Written` never exceeds `(camY+231)>>3`** during
  sustained vertical motion. The static case is strong — `d7` is the loop's stop target, and
  `Draw_TileRow_FromCache` has exactly two callers, both in that loop — so I record this as
  closed by source, not as a gap.
- **The §1.5 plane-buffer figures under sustained VERTICAL motion.** The booked 272 B peak covers
  horizontal motion only. My 264 B vertical / 536 B diagonal figures are *derived* from the entry
  sizes and the camera cap, not observed. Worth an `ab_runner` pass on the DEBUG shape before the
  flip, and it is the same run as falsifier 1.

**No gate was added by this parcel** — it is a measurement, and a gate whose red I had not proven
would be worse than none.
