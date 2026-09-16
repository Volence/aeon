# M-A: the measured cost of a region background switch

> Region bg switch, task 7 (plan `docs/superpowers/plans/2026-09-16-region-bg-switch.md`). Named
> outside the `08-*` series on purpose: that series belongs to another agent's foreground budget work.

**What was measured:** the DEBUG ROM's showcase region (x 1024..2047, y 2048..4095; its own
216-tile blob and a one-plane layout), crossed from an act-default neighbour on two routes, in the
headless emulator. **Instrument:** `python3 tools/bg_switch_gate.py --legs measure` (measurement
only, excluded from the default gate run). **Tree:** `parcel/region-bg-switch` at `278e435b` with the
liveness-sized chunk, built `FAST=1 DEBUG=1` (the canonical `DEBUG=1` build of the same source was
green through all 13 gate legs).

**Unit:** a *tick* is one pass of `GameState_OJZScroll_Update`. VBlanks were counted over the same
span from `Frame_Counter`: equal to the ticks on both routes, so **no lag frames occurred** and ticks
equal frames here.

## Results (chunk = 1824 B = 57 tiles, the shipped value)

| route | crossing -> arena settled (`BG_Tiles_Current` names the blob) | crossing -> all 29 visible Plane B rows show the new layout | crossing -> sweep retired (all 64 rows) |
|---|---|---|---|
| HORIZONTAL (fly right at 16 px/tick, stop 8 ticks inside) | **4** | **11** | **19** |
| VERTICAL (fly down at 16 px/tick, stop 8 ticks inside) | **4** | **12** | **19** |

**Why 1824 B (controller ruling, 2026-09-16):** the chunk must fit on any frame where it is the only
Deferrable entry (liveness): NTSC 6144 - foreground plane drain 536 - Critical 1664 - full-CRAM raster
ship 128 - the Important queue's player-art peak 1984 = 1832 B, rounded down to whole tiles.
Insta-shield, spindash-dust and waterline entries are not charged: they may slip behind a chunk at
the queue head, which is the Deferrable contract. Derivation and red test:
`tools/test_bg_overwrite_chunk_budget.py`.

**Derived, not measured separately:** 216 tiles / 57 per chunk = 4 chunks = 4 ticks; the visible
repaint is `ceil(29 / 4)` = 8 wipe ticks after the wipe arms, and the full sweep `ceil(64 / 4)` = 16
(the vertical route's one extra tick is the window catching up). A 320-tile blob (the static budget)
would settle in 6 ticks and show its visible rows at about 13.

**Peer slip (GATE BG-SWITCH leg TRAFFIC):** a synthetic 32 B Deferrable entry appended every frame
across the crossing waited at most **1 frame** from enqueue to send (sent in its own frame's VBlank);
no chunk was ever left over at the queue head (H = 0), so the derived bound H + 1 = 1 held. **Measured,
not proven red:** on the calm free-flight route no chunk is ever held, even with the chunk mutated to
3808 B, so the H + 1 assertion has not been seen to fail; violating it would need a non-FIFO drain.

## The rejected alternative: 256 B chunks

The first derivation charged every Deferrable producer's peak on the same frame (insta-shield 928,
dust 384, waterline 256), leaving 264 B, so the chunk was 256 B (8 tiles). Measured on the same
routes: arena settled **+27** ticks, visible rows repainted **+34**, sweep retired **+42**; a 320-tile
blob would settle in 40. Rejected by the controller: a chunk at the head only DELAYS the Deferrable
peers behind it, which their contract allows; what it must guarantee is that it can itself drain.

## Contended half: COULD NOT RUN

The worst case the review asked for (a fall at 16 px/tick with foreground streaming active) needs an
act that streams its foreground. OJZ act 1 is fully resident, and `build.sh` refuses the `STRESS_*`
shapes that would evict. Act art page landings on the Important queue are not charged in the chunk
derivation (they take priority by design), so a heavy streaming frame delays a chunk; no run measures
by how much. Booked with REGION-BG-COVER-WARNING.

## What the owner sees, and where (the accepted transient, rulings C7/C8 under R3)

- **From the crossing to +4 ticks:** Plane B still holds the OLD layout's nametable words while the
  arena's tiles are overwritten front first, 57 tiles a tick. Background cells whose tile index has
  been overwritten show the NEW region's art in the OLD arrangement: scrambled, and covered by design.
- **+4 to about +11:** the sweep repaints the visible rows starting at the top visible row and walking
  down, 4 rows a tick. The new picture wipes in top to bottom.
- **To +19:** the sweep finishes the rows off screen. Nothing visible changes.
- **The streamer is paused for the whole overwrite.** On this showcase it makes no difference (a
  one-plane layout never streams); on a region whose layout is taller than the plane, a fall during
  the overwrite would also show wrong map rows at the top or bottom edge until the sweep.

**Cover this implies at the engine's camera caps** (`CAM_MAX_X_STEP` 16, `CAM_MAX_Y_STEP` 16 px a
tick): the visible background is wrong or mid-wipe for 11 ticks horizontally (176 px of travel) and
12 vertically (192 px). **Horizontal crossing: about 176 + 320 = 496 px of opaque foreground.
Vertical: about 192 + 224 = 416 px.** (At 256 B chunks it was about 864 and 768 px.) These are the
inputs REGION-BG-COVER-WARNING needs.

## Recipe for a human look (DEBUG ROM, tagged for the controller)

1. Build `DEBUG=1 ./build.sh`. Boot with the boot-position mailbox at player (896, 3072) (128 px left
   of the showcase edge), or fly there in DEBUG free flight.
2. Hold RIGHT for about 8 ticks, then release. Watch the background for about half a second.
3. For the vertical case: start at player (1536, 1920) and hold DOWN.
4. Look for: the brief scramble in the first few frames, the top-down wipe that follows, and whether
   the colonnade art under the Sec3 preset's palette reads at all (the look, and the art, are the
   owner's).
