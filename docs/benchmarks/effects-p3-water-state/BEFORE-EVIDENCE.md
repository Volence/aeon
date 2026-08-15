# Water off-screen state — the BEFORE measurement

**Date:** 2026-08-15 · **Shape:** `s4.debug.bin`, master `eb48808d` (chain 124), CRC `9c63bc1a`
**Instrument:** oracle, pinned camera via `Debug_Scene_Freeze`, row-diff of two reset-anchored captures.

## Why an A/B of two ANCHORS, not two cameras

The defect is "the top rows never go under". As one capture it is unmeasurable — a screenshot cannot
say which rows *should* have been wet. As a difference between two anchor positions at ONE camera it
is exact: the art is pixel-identical in both, so every differing row is a row the water tint reached
and every identical row is one it did not.

Moving the CAMERA instead would have changed the art underneath and confounded the diff.

## THE FIRST PROTOCOL WAS CONTAMINATED, AND ITS CONTROL IS WHAT CAUGHT IT

The obvious method — freeze the scene, write anchor A, capture, write anchor B, capture — was run
first and **its determinism control failed**: two captures of the SAME config, 10 frames apart,
differed by **15,846 of 71,680 pixels**. `Debug_Scene_Freeze` skips `Camera_Update` and
`EntityWindow_Scan`; it does not stop `BgAnim_Update`, so the background keeps animating between
captures and every row carries drift.

The A/B taken that way gave the same row bands the corrected protocol later confirmed — and it was
still worthless, because nothing in it could distinguish "these rows are identical because the tint
never reached them" from "these rows happen to have no animated content". A measurement that cannot
fail is not evidence. (Standing lesson in this lane: a manual measurement giving a different answer
every time is not weak evidence, it is ABSENT evidence. This is the same class, one step subtler —
the numbers were stable enough to look convincing.)

### The SECOND protocol was ALSO wrong, and its control caught it too

Anchoring both captures to a fixed frame count after `emulator_reset` gave 0 differing pixels on
the first pair tried — and that was luck, not a property. Re-run on a later build, two identical
runs differed by **20,834 pixels**. Two independent causes:

1. **`emulator_reset` is DEFERRED** (it returns `{"deferred": true}`) — it does not necessarily
   land before the next `press`. Measured: the same "reset then 180 frames" gave `Frame_Counter`
   175 on one run and **319** on another. A fixed press count is not a fixed point in the run.
2. **The background animation is not driven by the frame count anyway.** `BgAnim_Update`
   (`engine/level/bg_anim.emp:124-140`) selects per band between `Camera_X`, `Camera_Y` and
   `Logic_Tick` — the **lag-immune** tick. Two ROMs that lag differently are at different animation
   phases at the same `Frame_Counter`.

### The protocol that actually holds

```
reset
press z x2 ; read Frame_Counter  -> MUST be ~0, else the reset has not landed; reset again
press z x180                              // boot into the OJZ scene
Debug_Scene_Freeze = 1                    // skips Camera_Update -> a written camera stays put
Camera_Y           = 400 << 16
Effects_World_Y[0] = <anchor>             // the ONLY thing that differs between runs
press z x(250 - Frame_Counter) ; verify Frame_Counter == 250
screenshot
```

**Determinism control under this protocol: two identical runs differ by 0 of 71,680 pixels** —
and unlike the first 0, this one survived being re-run on a different build.

### The standing rule this leaves: SAME-ROM pixels, CROSS-ROM structure

Even frame-pinned, **cross-build pixel comparison is not reliable** (cause 2 above): baseline vs a
provably no-op refactor still differed by 13,270 canopy pixels. So:

- **Same-ROM pixel A/B is sound** (control = 0) — that is what the submerged-vs-dry gate is, and it
  is the claim this parcel actually has to prove.
- **Cross-ROM claims use structural reads, not pixels.** `Raster_Buf_B`'s arm words encode the
  schedule the patcher computed, which is precisely the quantity in question, and they are
  animation-immune. Symbol addresses move between builds — re-look them up, never carry them over.

Addresses drift with every RAM change; the ones here are `s4.debug.bin` at the commit named above.

## The two configs

Channel 0 is `fx_tint_band(line:100, slot:0, pal_line:2, entry:4, count:3, sh:1)`, band 3..214 in
FIRE lines. `Raster_PatchAll` clamps, so:

| run | anchor | L = anchor - 400 | fire line after clamp |
|---|---|---|---|
| A | 224 | -176 → **submerged** | pinned to lo, 3 |
| B | 700 | +300 → fully **dry** | pinned to hi, 214 |

## Result

| rows | verdict | meaning |
|---|---|---|
| **0..1** | **IDENTICAL** | **THE DEFECT** — fully submerged renders these exactly as fully dry |
| 2..213 | differ (130 px on row 2, 124 on row 213, of 320) | the tint reached these rows |
| 214..223 | identical | both states are wet here (B's own boundary lands at 214) |

Total differing: 40,300 px.

**The measured stripe is 2 rows, not the 3 the work order reports.** Not a contradiction of the
owner's observation — 3 is what the band floor predicts (`lo: 3` in fire lines = screen 4), 2 is
what the display does. The two runs also disagree by one on which row the boundary owns: fire line 3
first differs at row 2, fire line 214 first differs at row 214. Both readings are consistent with the
boundary row itself being partially written by a mid-line CRAM write. The parcel does not need to
resolve it, and the gate is phrased against rows 0..1 either way.

## The structural baseline (cross-build claims rest on this, not on pixels)

`Raster_Buf_B` at the submerged config (camera 400, anchors 224 / 314), read on the baseline ROM:

```
0004 8A00 0000 8AD4 0000 8AFF 0002 0000
 |    |         |         |
 |    |         |         park — nothing follows record 3
 |    |         arm 1: gap $D4 = 212 -> channel 1 fire line 215 (clamped to its lo)
 |    arm 0: gap 0 -> channel 0 fire line 2 (clamped to its lo; band lo 3 SCREEN = 2 FIRE)
 pal_dirty_mask %0100 — CRAM line 2, re-shipped from Palette_Buffer every frame
```

Both channels are pinned at their band floors, which is the defect stated in the schedule instead
of in pixels. At the mid config (camera 144) the same words read `8A4D` / `8A87`: fire line 79 =
screen 80 = anchor 224 - camera 144, unclamped and tracking the world.

## What the AFTER measurement must show

1. **Rows 0..1 DIFFER** between the two anchors, same ROM — the submerged state reaches the screen
   top. This is the parcel.
2. **The schedule is untouched.** The arm words above must be byte-identical after the change, at
   BOTH configs: the ship is an addition at frame top, and it must not move a fire.
3. The determinism control still reports 0.
4. **A poison test**: with `Effects_Offscreen_Entry` zeroed by hand at runtime, rows 0..1 must go
   identical again. Same ROM, so it is sound — and it proves the gate measures THIS mechanism
   rather than something adjacent that happened to change with it.

## Captures

`det-run1.png` (submerged) · `det-dry.png` (dry) · `det-run2.png` (the control's twin of run 1) —
scratch, not committed. Pixels stay out of the repo (the `replay_runner` framebuffer parcel's
standing rule); this report is the artifact.
