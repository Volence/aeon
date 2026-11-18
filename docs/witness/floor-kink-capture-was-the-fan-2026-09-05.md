# The "two floors with a kink" capture was the FAN (addendum, 2026-09-05 afternoon)

> **Correction, 2026-11-17 (review before landing).** Sections 1 to 4 hold: the 14:46Z capture is the fan (b89b13de) running in a window that opened the ROM before the shear's last write (empyrean OVERSEER-LOG 14:43Z and 15:28Z). Two things below are wrong. **§5:** `test_baked_plane_b_carries_the_generated_band` could not have caught this. It checks the baked files on disk, and §4 shows those were already correct; the fault was a stale emulator process, which no file check can see. The arm makes the hand-decode a one-command check; it does not prevent a stale window. The arm that landed on master is 4fc9b56b's (row-major since 455523e6), not this branch's. **§6:** overtaken. The owner saw the shear on his machine at 15:36Z (`2026-09-05-owner-floor-planks-no-convergence.png`) and rejected it ("this just consistently skews"), and the fan came back in e54779a5. See §2 of the main page.

> Landed 2026-11-17 from branch `fix/floor-kink-stale-rom-2026-09-05` (`884d2a51`), where it was appended to [`floor-outer-stripes-2026-09-05.md`](floor-outer-stripes-2026-09-05.md). Master has since rewritten that page into three versions, so this addendum stands alone here. "This document" in §5 means that page. The branch's §6 is dropped: it was overtaken, see the correction above and §2 of that page. Small slips found in review: dy 0 and 1 are `WOOD[1]` and `WOOD[2]`, not `WOOD[3]`; "top 28 rows" should be 29; the shear counts in the §2 table were taken over a 320-px window (over the full 512 px they are 16/16/24).

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
