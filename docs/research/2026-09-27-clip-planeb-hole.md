# The clip act's plane-B hole at x 1344..1407 (Emerald Hill): reachable, and why

Branch `research/clip-planeb-hole`, base `origin/master` 3423a219 (at or after ff7cbad5).
Question from LINES-EVERYWHERE open item 2 (`docs/DEFERRED_WORK.md`): the `s2_ehz_cpz` clip
declares 64 plane-B floorless columns, and the declaration said x 1344..1407 is reachable
"by walking LEFT past the layer line at x 1704" (derived from the table, not driven).

## Answer

1. **Reachable: yes, measured on both clip shapes.** A player can be on plane B at
   x 1344..1407 and fall through, and he falls forever (past y 1100, under the painted band).
2. **But not the way the booking said.** The x 1704 line does not put a walking player on B
   there. The real route is Emerald Hill's first loop, left to right of the pit.
3. **Sonic 2 puts the same player on path B at that spot too** (measured under GPGX). What
   saves him is the **Obj11 bridge**: the hole is exactly under it. The clip carries no
   objects, so the bridge is missing.
4. **Cause: missing Sonic 2 object (content), not a line, a converter or a collision bug.**
   Not fixed here (the brief: do not build objects). Content item for the owner below.
5. **The missing bridge is worse on plane A** than the plane-B hole: the pit is open on both
   planes, a plane-A player who walks in is trapped, and one who jumps in can be pushed out
   through the pit's right wall into a column with no floor (measured, both shapes).

## What was measured

Instruments (all in this directory, research only, no runner):

- `planeb_hole_drive.py`: the clip ROM headless (`tools/aether_instance`), the same boot and
  placement as `docs/research/2026-09-26-s2clip-loops-planes/loop_plane_probe.py`. DEBUG: B
  press out of free flight (the drive records the debug flag at boot: 255 on DEBUG, 0 on
  plain), then the `Warp_Req_*` mailbox; plain: a camera write. Per frame it records x, y,
  `Sst.layer` read from the ROM, the player state, ground speed, y_vel, and the **floor
  sensor**: the first landing surface at or below the feet in the player's column, on his
  CURRENT layer, read from the clip's own converted planes (`clip_manifest.collision_grids`,
  the words the clip bake writes into the ROM). Inputs are real buttons (hold, jump, a real
  spindash: DOWN + three A taps + release); the one non-button input is a single ground-speed
  write at the start (`--gsp`), standing in for "running at that speed".
- `s2_drive.py`: real Sonic 2 (s2disasm REV01 build, SHA-1
  `8bca5dcef1af3e00098666fd892dc1c2a76333f9`, header `GM 00001051-01`) under Genesis Plus GX
  through `tools/s2_music_balance.py`'s ctypes frontend. Placement is Sonic 2's own starpost
  restart (Saved_* block of `Obj79_SaveData`, s2.asm:44261; `Level_Inactive_flag` restarts
  the level, s2.asm:5092; `Obj79_LoadData` runs from LevelSizeLoad, s2.asm:14754), so the
  camera, object manager, every Obj03 and the bridge are initialised by the game. Path is
  `top_solid_bit` ($0C = A, $0E = B). `invulnerable_time` is held up so badniks cannot end a
  drive (the first try died to Coconuts at (1831, 480) with 0 rings).
- `s2_paths.py` / `aeon_paths.py`: per 8-px column, every solid cell of both paths, from the
  donor (chunk words + both collision indices + the height array) and from the clip's
  converted grids. The two agree cell for cell at every column printed here (x 1280..1760,
  1528..1576, 3840..4064).
- `sweep.sh`, `sweep2.sh`, `sweep3.sh` + `sweep_table.py`; tables in `sweep1.txt`..`sweep3.txt`
  (the per-drive sweep JSONs are not committed; the scripts regenerate them).

ROMs: `FAST=1 [DEBUG=1] S2CLIP=s2_ehz_cpz ./build.sh` at 3423a219, `s4.s2clip.bin` SHA-1
`c4c05cea598ef5fed1e29cad4c5babc6d9134325`, `s4.s2clip.debug.bin` SHA-1
`6a9d73797df9e250c38d5631ac24944c3a68af75`. FAST because the canonical clip build could not
run here: its pytest lane failed 10 `test_freeze_preflight` tests on `tee: /tmp/fp_repin.*:
Disk quota exceeded` (the machine's /tmp quota, not this tree). A FAST ROM is byte-identical to
the canonical one but nothing here checked that.

### 1. The booked mechanism is wrong: the x 1704 line fires only in a sealed corridor

The line at x 1704 (Obj03 at (1704, 712), subtype $11: back -> B, forward -> A, y 648..775)
covers only the band under the walkway. At x 1704 the collision is: walkway surface at
y ~597 (top-only cells y 592..655), a W (solid) row at y 656..671, a hollow y 672..735, and a
floor at y 736. A player walking the walkway has his centre at y ~578, outside the line.
The hollow is a lower corridor from x 1664 to 1912, closed at its left end by walls on both
paths at x 1656 (y 672..767) and on path B also at x 1672 and 1784..1800.

Measured (DEBUG, `dbg.loop1_run_left_4500.json`): a top-speed leftward run from x 4500
completes loop 1 (layer B at x 4364, back to A at x 4225 over the loop's top), runs off the
walkway at x 2046, drops into the dip, lands at the corridor mouth (x 1923, y 717) and runs
into the corridor on A. It crosses x 1704 at y 717 (f649) and becomes B, then stops at
x 1690 against path B's wall at x 1672 and stays there (frames 651..899). He can only leave
the corridor rightward, which fires the same line forward -> A. So this line cannot deliver a
plane-B player to x 1344.

### 2. The real route: loop 1, left of the pit

Loop 1's lines: x 4368 (subtype $11, y 512..639: back -> B) and x 4224 (subtype $91,
y 400..527: back -> B, forward -> A, **grounded only**). Every player crossing x 4368 leftward
at ground level becomes B; the only thing that makes him A again is crossing x 4224
rightward **on the ground**, which going round the loop does (at its top). A player who
leaves the loop leftward in the air keeps B, and no line between x 1704 and x 4224 changes it
(the table has none there). Then he runs the walkway on B to the bridge pit.

Measured, DEBUG and plain, no cap (`dbg.nocap_route.json`, `plain.nocap_route.json`):
start x 4500, ground speed $600 (top running speed) leftward, jump at frame 30 (inside the
loop), let go, spindash at frame 260 (real inputs) and jump 4 frames after the release,
second spindash at frame 540 to climb the hill at x ~3920, jump the dip at x 2106:

| shape | layer B from | exits loop leftward on | x 1344..1407 frames | on B | floor below | end |
|---|---|---|---|---|---|---|
| DEBUG | f23 x 4358 | B (only change in 1033 frames) | 54 | 54 | none on all 54 | x 1347 y 1109, fell |
| plain | f23 x 4358 | B (only change in 1025 frames) | 54 | 54 | none on all 54 | x 1351 y 1109, fell |

The same with a ground speed at the engine cap (`--gsp cap`, $1000) and position-triggered
jumps (`*.natural_route_pos.json`): both shapes, layer B from x 4344, fell at x 1349 / 1349.

How common: of 44 + 66 single-jump drives at speeds $300..$C00 plus the cap (sweeps 1 and 2),
**one** left the loop on B (cap speed, jump at frame 30); 41 left on A; the other 68 were
still right of x 3990 when the drive ended, most of them on B, rocking on the loop's inner
slope at x ~4200. From that stuck-on-B state, with a
real spindash, **1 of 20** jump timings (4 frames after the release) leaves on B (sweep 3).
So it takes a mistimed jump and a precise one, but no cheat: every input is a button a player
has, and the start speed is the top running speed.

Forced-layer control (`*.forcedB_walk_1800.json`): layer written to B on the walkway at
x 1800, walk left: both shapes fall through at x 1348 (48..51 frames in 1344..1407 on B, no
floor below any of them).

### 3. Sonic 2 at the same spot

- **Same lines, same state**: `s2.natural_route_pos2.json`, cap speed from x 4500, jump in the
  loop: path A -> B at x 4359 (f8), **no further path change in 1500 frames**, still path B at
  x 3203 (Sonic 2's own objects stop the drive there: an up-spring Obj41 at (3828, 440),
  then the terrain). Sonic 2's player leaves loop 1 on path B exactly as ours does.
- **The pit is bridged**: Sonic 2's object layout (s2disasm `level/objects/EHZ_1.bin`) has
  Obj11 (bridge) at (1448, 648), subtype $0C = 12 logs x 16 px = x 1352..1543, stakes Obj1C
  at (1336, 636) and (1544, 636), and Mashers (Obj5C) at (1400, 720) and (1480, 720).
- **On path B he walks across**: `s2.forcedB_walk_1800.json`, starpost-placed at (1800, 556)
  on path B, walk left: 10 frames at x 1344..1407, all on path B, all **grounded**, while the
  donor's path B has no floor below any of them; the bridge's log objects are loaded
  (`$11` at x 1408, 1448, 1504). He reaches x 1249 still grounded.
- **Sonic 2's collision under the bridge** (`s2_paths.py EHZ 1280 1760`): path A has the pit
  floor at y 864 from x 1344 to 1535; path B has it from x 1408 only. Sonic 2 never lets a
  player reach it (the bridge is always solid), so that difference is invisible in Sonic 2.

### 4. Plane A in the open pit (the same missing bridge)

- Walk left from x 1800 on A (`*.A_walk_1800_control.json`, both shapes): drops into the pit,
  lands on its floor (y 864), walks under the left bank to x 1290 and stays; five jumps did
  not get him out. The pit's walls rise to y 640; a jump rises about 97 px (derived from the
  jump force, not measured).
- Walk right from x 1150 on A and jump (`*.A_walk_right_1150_pit.json`, both shapes): the
  jump carries him over the pit; falling at x 1514, y 774..785 he overlaps plane A's solid
  (LRB-only) slab at y 784..799, which spans x 1344..1535, and the airborne wall push-out
  moves him right to the slab's far edge, x 1514 -> 1545 -> 1561 in two frames (DEBUG
  f470..472; plain the same shape), through the
  pit's right wall (x 1536..1551), into a column whose collision below y 672 is empty down to
  an LRB row at y 880: he falls forever (y 1109 at x 1584). The mechanism is read, not
  instrumented: `Air_WallProbeLeft` (games/sonic4/player/player_air.emp:747) subtracts the
  probe's negative distance, and a probe that starts inside a solid run returns the distance
  to that run's edge. Sonic 2 cannot be compared here (the bridge keeps everyone out).

## Conclusion and content item for the owner

It is a real hole the player can fall into in our build and not in Sonic 2, and the cause is
the missing **Obj11 bridge** (plus its stakes), not the layer lines, not the line converter
(`tools/s2_layer_lines.py` reads the x 1704 and loop lines exactly as Obj03 defines them:
subtype, half-length table `word_1FD68`, grounded bit), and not the collision conversion (the
converted planes equal the donor's cell for cell). Nothing here is ours to fix without building
objects, so nothing was fixed.

**Owner:** Emerald Hill's first bridge, Obj11 at act (1448, 648), 12 logs spanning x 1352..1543
(Sonic 2 also has stakes Obj1C at (1336, 636) and (1544, 636)). Until the clip has it (a
bridge object, or a collision stand-in on both planes, the owner's call), the pit is a
soft-lock on plane A and a bottomless fall on plane B at x 1344..1407. The same shape
repeats at x 8192..8255 on plane B, under a second bridge (Obj11 at (8168, 584), subtype $0C,
x 8072..8263); not driven.

`games/sonic4/data/clips/s2_ehz_cpz/clips.json`'s declaration now says this (reachable,
measured, the real route, the bridge), and `tools/clip_reachability.py`'s docstring no longer
calls the pit a "jump-the-pit seen from the path the player is not on".
