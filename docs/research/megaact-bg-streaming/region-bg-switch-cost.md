# M-A: the measured cost of a region background switch

> Region bg switch, task 7 (plan `docs/superpowers/plans/2026-09-16-region-bg-switch.md`). Named
> outside the `08-*` series on purpose: that series belongs to another agent's foreground budget work.

**What was measured:** the DEBUG ROM's showcase region (x 1024..2047, y 2048..4095; its own
216-tile blob and a one-plane layout), crossed from an act-default neighbour on two routes, in the
headless emulator. **Instrument:** `python3 tools/bg_switch_gate.py --legs measure` (measurement
only, excluded from the default gate run). **Tree:** `parcel/region-bg-switch` at `41d6a846`, built
`FAST=1 DEBUG=1` (the FAST build is byte-identical to the canonical one by construction; the
canonical DEBUG build of the same commit was green through all 13 gate legs).

**Unit:** a *tick* is one pass of `GameState_OJZScroll_Update`. VBlanks were counted over the same
span from `Frame_Counter`: equal to the ticks on both routes, so **no lag frames occurred** and ticks
equal frames here.

## Results

| route | crossing -> arena settled (`BG_Tiles_Current` names the blob) | crossing -> all 29 visible Plane B rows show the new layout | crossing -> sweep retired (all 64 rows) |
|---|---|---|---|
| HORIZONTAL (fly right at 16 px/tick, stop 8 ticks inside) | **27** | **34** | **42** |
| VERTICAL (fly down at 16 px/tick, stop 8 ticks inside) | **27** | **34** | **42** |

**Derived, not measured separately:** 216 tiles / 8 tiles per chunk (256 B, `BG_OVERWRITE_CHUNK_BYTES`)
= 27 chunks = 27 ticks at one chunk a tick; the visible repaint is `ceil(29 / 4)` = 8 wipe ticks,
seen as 7 after the settle tick because the wipe arms on the settle tick; the full sweep is
`ceil(64 / 4)` = 16. A 320-tile blob (the act default's size, the static budget) would settle in
40 ticks and show its visible rows at about 47.

**Contended half: COULD NOT RUN.** The worst case the review asked for (a fall at 16 px/tick with
foreground streaming active) needs an act that streams its foreground. OJZ act 1 is fully resident,
and `build.sh` refuses the `STRESS_*` shapes that would evict. The chunk size is derived to drain on
the NTSC window's worst frame (`tools/test_bg_overwrite_chunk_budget.py`), so contention should not
stall a chunk, but act art page landings are not charged in that derivation (they take priority by
design), and no run confirms it. Booked with REGION-BG-COVER-WARNING.

## What the owner sees, and where (the accepted transient, rulings C7/C8 under R3)

- **From the crossing to +27 ticks:** Plane B still holds the OLD layout's nametable words while the
  arena's tiles are overwritten front first, 8 tiles a tick. Every background cell whose tile index
  has already been overwritten shows the NEW region's art in the OLD layout's arrangement. By +27
  the whole visible background is scrambled. This is the garbage the designer's foreground covers.
- **+27 to +34:** the sweep repaints the visible rows starting at the top visible row and walking
  down, 4 rows a tick. The new picture wipes in top to bottom.
- **+34 to +42:** the sweep finishes the rows off screen. Nothing visible changes.
- **The streamer is paused for the whole overwrite.** On this showcase it makes no difference (a
  one-plane layout never streams), but on a region whose layout is taller than the plane, a fall
  during the overwrite would also show wrong map rows at the top or bottom edge until the sweep.

**Cover this implies at the engine's camera caps** (`CAM_MAX_X_STEP` 16, `CAM_MAX_Y_STEP` 16 px a
tick): the visible background is wrong or mid-wipe for 34 ticks, so a player moving at the cap
travels 544 px while it happens. **Horizontal crossing: about 544 + 320 = 864 px of opaque
foreground. Vertical: about 544 + 224 = 768 px.** For a 320-tile blob, about 752 px of travel. These
are the inputs REGION-BG-COVER-WARNING needs.

## Recipe for a human look (DEBUG ROM, tagged for the controller)

1. Build `DEBUG=1 ./build.sh`. Boot with the boot-position mailbox at player (896, 3072) (128 px left
   of the showcase edge), or fly there in DEBUG free flight.
2. Hold RIGHT for about 8 ticks, then release. Watch the background for about 1.5 s (≈ 90 frames).
3. For the vertical case: start at player (1536, 1920) and hold DOWN.
4. Look for: the scramble from the crossing to about half a second in, the top-down wipe that
   follows, and whether the colonnade art under the Sec3 preset's palette reads at all (the look,
   and the choice of art, are the owner's).
