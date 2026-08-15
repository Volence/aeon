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

**The fix is to anchor both captures to the same absolute frame from power-on**, so the animation
phase is identical by construction rather than by hope:

```
reset
press z x180                              // boot into the OJZ scene
Debug_Scene_Freeze ($FF8D2C) = 1          // skips Camera_Update -> a written camera stays put
Camera_Y           ($FFA4C8) = 400 << 16
Effects_World_Y[0] ($FF8ABA) = <anchor>   // the ONLY thing that differs between runs
press z x30
screenshot
```

`emulator_press` advances exactly N frames and pauses, so the sequence is reproducible.

**Determinism control under the corrected protocol: two identical runs differ by 0 of 71,680
pixels.** That control is what makes every number below mean something, and it must be re-run
beside the AFTER captures — it also catches nondeterminism creeping into the emulator or the ROM.

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

## What the AFTER capture must show

1. **Rows 0..1 DIFFER** between the two anchors — the submerged state reaches the screen top.
2. The mid-screen state is **untouched**: anchor 224 / camera 144 (L = 80) pixel-identical to the
   pre-change build under the same protocol. This parcel fixes the L <= 0 state and must not move
   the ordinary one.
3. The determinism control still reports 0.

## Captures

`det-run1.png` (submerged) · `det-dry.png` (dry) · `det-run2.png` (the control's twin of run 1) —
scratch, not committed. Pixels stay out of the repo (the `replay_runner` framebuffer parcel's
standing rule); this report is the artifact.
