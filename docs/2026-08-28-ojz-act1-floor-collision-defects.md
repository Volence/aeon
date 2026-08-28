# Knuckles falls through the OJZ act-1 ground — diagnosis

**Date:** 2026-08-28 · **Branch:** `diag/knux-falls-through` · **Evidence:** static only, no emulator

## Verdict

**(a) — the level's collision data.** The engine reads the collision it is given,
correctly, at every point checked. The data it is given is wrong in three
distinct ways, all of them in the authored editor tree, none of them in code.

The single most load-bearing piece of evidence is that the owner's save state
independently predicted the mechanism before it was looked up: at his exact
saved position and facing, the ledge probe lands exactly on a 1-pixel hole in
the floor's height profile — and the save's own `anim` byte reads
`$06 = ANIM_BALANCE`, the teeter animation, in the middle of flat ground.

## What the save state says

`s4.debug.state0`, decoded with no emulator via the new `tools/state_ram.py`
(ROM fingerprint matched `s4.debug.bin`, payload checksum verified, RAM length
verified 64 KiB):

```
position   x=954.62464   y=557.31744   (16.16)
camera     x=810  y=432
velocity   x_vel=+0.000  y_vel=+0.000    ground_speed +0.000
state      GROUND   angle=$00   layer=0
status     $02 [xflip]                   -> facing LEFT, not in air, not rolling
hitbox     19 x 39 px full -> radii 9 x 19
anim       $06 BALANCE
```

Three corrections to the numbers this investigation was handed:

* `Camera_Y` is at `$FFFFA608`, **not** `$FFFFA606`. `Camera_X` is a longword, so
  `$A606` is its *fractional* word — which is why the camera looked like `y = 0`.
  It is actually `y = 432`, consistent with `Cache_Top_Row = 38`.
* `anim` was not decoded before. It is the key field: `$06` is `ANIM_BALANCE`.
* The state is **not** ambiguous about *when*. At this position the engine finds
  solid ground with distance 0. The frame is a stable stand — with the wrong
  animation playing.

## Defect 1 — the whole main floor is painted with a 15-pixel-wide block

Every cell of OJZ act 1's main ground carries the editor cell word **`$1472`**:

| field | value | meaning |
|---|---|---|
| bits 9:0 | 114 | base-bank shape index |
| bit 10 | 1 | X-flip |
| bits 13:12 | 1 | solidity = `SOL_TOP` |

S&K base shape 114 (verified byte-identical to the donor at
`skdisasm/Levels/Misc/Height Maps.bin` — the import is faithful, not buggy) is:

```
h = [0, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16]   angle $FF
```

a full block **missing its leftmost 1-pixel column**. X-flipped, that becomes

```
h = [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 0]   angle $01
```

which interns as runtime attr **`$01`** — confirmed byte-identical in the ROM at
`HeightMaps+$10` (`s4.debug.bin` `$6E350`). It is the **only** entry in the
act's 32-entry runtime attr table with a zeroed height column; every other full
block (`$02`, `$04`, `$0F`, `$19`) is all-16.

**Effect:** a 1-pixel-wide column of air at every world X ≡ 15 (mod 16), the full
length of the floor. Measured directly:

```
x=958 (x&15=14): dist= +0 attr=$01
x=959 (x&15=15): dist=+32 attr=$00      <- nothing found
x=960 (x&15= 0): dist= +0 attr=$01
```

**Count:** 300 authored cells, all in section 0.

### Why this produces the reported symptom

`Player_AtLedgeEdge` (`games/sonic4/player/player_sensors.emp`) probes a *single*
point at `x ± LEDGE_PROBE_REACH`, where `LEDGE_PROBE_REACH = PLAYER_X_RADIUS + 2 = 11`,
and calls it a ledge when the floor distance exceeds `LEDGE_NO_GROUND = 8`.

At the saved position, facing left: `954 − 11 = 943`, and `943 & 15 = 15` — the
hole. The probe returns 32, so the engine reports "at a ledge edge", and
`Player_Animate` selects `ANIM_BALANCE`. That is exactly the `anim = $06` in the
save state.

This fires at **2 of every 16 X positions** on the entire floor: `x & 15 == 10`
facing left, `x & 15 == 4` facing right. Knuckles stops on flat ground and
teeters on nothing.

### Where it actually drops him

The *floor pair* uses two sensors 18 px apart, so both can never sit in the same
1-pixel hole — the hole alone does not detach a player mid-floor, and a
left-to-right and right-to-left walk simulation over all nine sections detaches
only at genuine platform ends. But within 9 px of a ground edge, one sensor is
already past the edge and the other can land in the hole. **12 (x, surface) pairs
across the act** lose both sensors, e.g.:

```
x 568   surface y=544  | x=559: attr=$01 h[15]=0 | x=577: AIR
x 614   surface y=544  | x=605: AIR             | x=623: attr=$01 h[15]=0
x 1060..1063, 1111..1112, x 6  (same shape, at other edges)
```

**Correction:** repaint the floor with base shape **255** (or **251**), both of
which are all-16 and are already in the owner's palette (used 232 and 832 times
respectively elsewhere in the same section). Shape 114 has no business under a
walkable surface.

## Defect 2 — the main floor is a jump-through platform

`$1472` sets solidity `SOL_TOP` (1), not `SOL_ALL` (3). Over the 63 tile columns
of the main ground at y=576, 62 are `SOL_TOP` and 1 is `SOL_ALL`. `SOL_TOP`
passes the floor-sensor class mask so standing works, but the surface is not a
wall and not a ceiling: nothing can push against it and nothing collides with it
from below. For an act's primary ground that is almost certainly not the intent.

## Defect 3 — the ground is drawn far below where it is solid

At x = 954 the art draws solid ground continuously from y = 576 down past
y = 728; the collision exists for exactly **one 16-pixel cell** (y = 576..591)
and is air everywhere below.

```
 row   y   | art (tile cols 118..126) | collision cell
  72  576  | #########                | attr=$01 sol=1
  73  584  | #########                | attr=$01 sol=1
  74  592  | #########                | attr=$00 sol=0   <- drawn, not solid
  ...  ...   (continues to row 91+)
```

**Count across the act: 1260 drawn-but-air 8-pixel tiles in 56 columns**, deepest
run 32 tiles (256 px) at x = 768. Anything that gets a player's feet below
y = 592 there is inside visible ground with no collision at all, and falls
forever — section 0 has nothing below.

This does not currently tunnel on its own: `PHYS_FALL_CAP` is
`((1 << COLLISION_CELL_SHIFT) - 1) << 8` = **15 px/frame**, deliberately one less
than the 16 px cell, and a sweep of every (start height, initial y-velocity)
trajectory onto this floor at x = 954 found **0** that skip the landing window.
The engine is defending the thin floor exactly as designed. It is one pixel of
margin, though, and it is spent.

## What was checked and found correct (the engine's exoneration)

| Check | Result |
|---|---|
| Save-state RAM tile cache vs the baked section-0 strips, over the whole cache window, both planes | **4800 cells compared, 0 differ** |
| ROM `HeightMaps` / `HeightMapsRot` / `AngleTable` / `SolidityTable` vs `data/collision/*.bin` | byte-identical at `$6E340`/`$6F340`/`$70340`/`$70440` |
| `Cache_Top_Row` parity (collision cells are world-16px-aligned; an odd top row would shift every cell 8 px) | invariant held — `tile_cache.emp` masks `#$FFFE`; observed 38 |
| `SOLID_TOP`/`SOLID_LRB`/`SOLID_ALL` (engine) vs `SOL_TOP`/`SOL_LRB`/`SOL_ALL` (pipeline) | 1/2/3 both sides, no seam mismatch |
| Odd-angle flag (attr `$01` carries angle `$01`) | handled — `Player_SensorSurface` substitutes the quadrant cardinal on `btst #0` |
| S&K collision import faithfulness | `import_sk_collision.py` is a straight byte copy; shape 114 matches the donor exactly |
| Editor even-row sampling (`apply_editor_collision_overlay` reads only even tile rows) | no loss — every authored row appears as an even/odd pair with identical counts |
| Fall-through by tunnelling at the real fall cap | 0 trajectories |
| Objects near the spot | one, at (808, 210); `ST_ON_OBJECT` clear |

## Honest limits

* A *fall* at exactly (954, 557) is **not** reproducible statically: there the
  floor pair returns distance 0. What is reproducible there, exactly, is the
  false ledge teeter. If the owner saw Knuckles physically drop, it was at one of
  the 12 edge positions above or after moving; the save captures the teeter.
* Everything here is read from `s4.debug.bin` (2026-08-27 18:11) and the editor /
  generated trees that share its timestamp. The working tree in the shared
  checkout is the ROM's own inputs; this worktree's committed copies differ and
  were **not** used.

## Recommended fixes (data — for the owner, not applied here)

1. Repaint the 300 floor cells from base shape **114** to **255**, dropping the
   X-flip. Removes the 1-px holes, the false teeter, and all 12 fall-through spots.
2. Reconsider `SOL_TOP` on the primary ground; `SOL_ALL` is the classic choice.
3. Paint collision into the drawn ground body below y = 592, or accept a
   one-pixel-of-margin floor and never let anything exceed `PHYS_FALL_CAP`.

## Reproducing

```bash
python3 tools/state_ram.py s4.debug.state0 --rom s4.debug.bin --lst s4.debug.lst
python3 tools/state_ram.py test          # decoder self-tests
python3 -m pytest tools/test_state_ram.py -q
```
