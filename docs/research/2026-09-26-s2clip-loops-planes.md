# Loops and plane switching on the Sonic 2 clip act (`S2CLIP=s2_ehz_cpz`)

Research, 2026-09-26. Branch `research/s2clip-loops-planes`, cut from origin/master `91d4119c`.
Owner's ask: *"look into: 1. Loops/plane switching in this map."* Investigation only; nothing in
the engine, the bake or the canonical ROMs was changed.

Files beside this doc, in `docs/research/2026-09-26-s2clip-loops-planes/`:

| file | what it is |
|---|---|
| `loop_plane_probe.py` | headless drive (aether_instance, no MCP). Leaves debug free-flight with a real B press, places the player on plane-A ground, holds a direction, optionally injects a ground speed, logs x/y/layer/angle/gsp/state per frame. `--switchers s2` adds a host-side model of Sonic 2's Obj03 (see "Limits of the host model") |
| `run_all.sh` | every drive quoted below, each run twice (switchers `none` / `s2`); JSON per run in `out/` |
| `obj03.py` | lists every S2 Obj03 in EHZ1/CPZ1 from `s2disasm/level/objects/*_1.bin`, decoded per `s2.asm:45132-45369` |
| `render.py` | draws a zone's two collision paths (red = plane A only, blue = plane B only, grey = both, light = top-solid only) with the Obj03 lines in green |
| `diffscan.py` | census of 16x16 blocks where plane A and plane B differ |
| `ehz_loop1_planes.png`, `cpz_braid_planes.png`, `cpz_3000_planes.png` | the figures referred to below |

All runtime numbers are from `DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh` at `91d4119c` (build rc 0),
`s4.s2clip.debug.bin`. Coordinates are **act** coordinates unless marked CPZ/EHZ; EHZ is placed
1:1, CPZ at +11360 x, +256 y (`clips.json` dst_rect).

## Answer in one paragraph

Both of Sonic 2's collision paths are in the clip, faithfully: plane A is S2's primary path, plane B
its secondary. **Nothing in the clip ever moves the player onto plane B.** In Sonic 2 that job is
done by Obj03 (the plane switcher), and the clip carries no S2 objects at all. The engine's only
other layer writer, the painted loop crossover, is absent from S2 data and could not express S2's
switchers anyway. So the player runs the whole act on S2's primary path. Measured: in all 11 drives
of the ROM as built, the layer was 0 on every frame. The consequences are what you would predict.
None of EHZ's four loops can be completed: the player goes up the right arc, runs along the
ceiling and is thrown back out to the left. CPZ's braided track drops him to the level below. CPZ
has plane-A-only walls where Sonic 2's route is on plane B (at CPZ x 3206 and x 3591). The host
model then adds Sonic 2's own switcher lines, placed from S2's object layout, and changes nothing
else. With it, all four EHZ loops complete in both directions, the braid is ridden and the CPZ
3206 wall is passed. So the missing piece is exactly the switchers. The collision data is fine, and
so are the loop physics.

## What is there, and what is not (read)

1. **Both S2 paths are imported.** `tools/s2_zone_convert.py` `expand_collision_words` builds
   `section_N.collattr.bin` from S2's primary index (`Off_ColP`) with chunk bits 13:12, and
   `collattrb.bin` from the secondary index (`Off_ColS`) with bits 15:14. The bake emits both planes.
   The engine selects the plane from `Sst.layer` at every probe (`player_sensors.emp:344/455/548`,
   `player_climb.emp`, `player_glide.emp:438`).
2. **Nothing writes the layer in the clip.** `Sst.layer` has exactly three writers:
   - `Player_Init` (`clr.b layer`, `player_common.emp:828`);
   - `Player_LoopCrossover` (`player_common.emp:1420`), which fires only on a painted crossover
     mark. A converted S2 tree has XOVER_NONE in every cell: the donor chunk word has no crossover
     field (`clip_act_bake.check_severed_crossovers` docstring: "STRUCTURALLY VACUOUS ON TODAY'S DATA");
   - `PathSwap_Main` (`games/sonic4/objects/path_swap.emp:153`), which is placed in no level data and
     is parked for deletion (DEFERRED_WORK, `parcel/pathswap-placements` merged `af896648`).
3. **The clip carries no S2 objects.** `clip_rom_bake.py` header: "THE OBJECTS AND RINGS. Pass 8
   reads the shipped act's editor objects/rings ... Objects are out of scope for the whole first
   cut (owner's scope)." `s2_zone_convert.py`: "No objects, no rings". So S2's Obj03 lines never
   reach the ROM. Inside the clip rectangles S2 places **19 Obj03 in EHZ (19 of 19 in the zone)** and
   **25 in CPZ (of 60 in the zone)** (`obj03.py`).
4. **What the two paths hold.** `diffscan.py` counts 16x16 blocks where A and B differ: **849 in
   the EHZ rectangle and 749 in the CPZ rectangle.** The groups that matter:
   - every EHZ loop (4 of them, centres about x 4224, 6784, 7168, 8832): **right arc on A only, left
     arc on B only**, top cap and entry on both; the bottom-left entry slab is A top-solid, the
     bottom-right exit slab is B top-solid (`ehz_loop1_planes.png`);
   - CPZ braid, CPZ x 1024..2048 y 512..656: two interleaved sine tracks, one per plane
     (`cpz_braid_planes.png`);
   - CPZ x 3200..3344 y 704..1152: a vertical loop whose entry floor (x 3232..3328, y 896..960) is on
     B only. Its left side, and the quarter-pipe below it, are A only (`cpz_3000_planes.png`);
   - CPZ x 3584..3728 y 320..768: the wall booked as the S2CLIP-CPZ-LONGER limit (A wall, B open);
   - CPZ x 3840..4576 y 832..1168: a crossed diagonal/sine pair like the braid.

## Sonic 2's reference behaviour (read)

`s2.asm:45132-45369`, Obj03. A switcher is a **line** (vertical when subtype bit 2 is clear,
horizontal when set), of half-length `$20/$40/$80/$100` (subtype bits 1:0), with a per-player "which
side am I on" flag. When the player **crosses** the line within its extent, the object sets the path
for that crossing direction and nothing happens otherwise:

| subtype bit | meaning |
|---|---|
| 3 | crossing right (or down): 1 = path B (`$E/$F` solidity bits), 0 = path A (`$C/$D`) |
| 4 | crossing left (or up): same encoding |
| 5 / 6 | crossing right / left: draw the player at high priority (the bit is cleared first, always) |
| 7 | only while grounded |
| x-flip (layout word bit 13) | leave the path alone and change priority only |

It runs for both players. S3K's `Obj_PathSwap` (S.C.E. `Objects/Main/Path Swap/Path Swap.asm`) is
the same object with the same subtype layout, so S2 and our S3K baseline agree on what a switcher
is.

EHZ's loops use two lines each: a **grounded-only line at the apex** (e.g. (4224,464) `$91`:
crossing right gives A, crossing left gives B) and an **exit line** past the loop's right foot
((4368,576) `$11`, same directions). A rightward runner goes up the right arc on A, crosses the apex
line moving left (he is upside down), goes onto B and comes down the left arc. He then runs along
the bottom on B, crosses the exit line moving right and is back on A. EHZ never sets priority (bits
5/6 are clear in every EHZ switcher). CPZ does (21 of its 25 in-clip lines set priority), including 9
priority-only (x-flipped) lines, most of them on the braid.

## What happens on the act (measured)

`run_all.sh`, top speed (`PHYS_TOP_SPEED`, $600) injected once after landing unless noted, one
column per `--switchers` mode. "Inverted" is grounded frames with angle $60..$A0.

| drive | switchers none (the ROM as built) | switchers s2 (host model of Obj03) |
|---|---|---|
| EHZ loop 1, right, from 3950 | layer 0 on all 240 frames. Up the right arc, inverted along the ceiling to x 4082, airborne there (f110), lands on the approach slope at x 3966 moving **left** (f134, gsp -960). Furthest x 4298. | apex line fires to B (f85), exit line to A (f143). Full circuit, exits right to x 5118 |
| EHZ loop 1, right, walking from rest (no injection) | 600 frames, never gets past x 4298. Rocks between the slope and the loop, 115 inverted frames | clears the loop and runs on to x 6820 |
| EHZ loop 2, right, from 6600 | layer 0, max x 6858, ends back at 6648 | B at the apex (f77), A at the exit (f139). Exits and is already inside loop 3 (B, f198) when frames end, x 7276 |
| EHZ loop 3, right, from 7040 | layer 0, max x 7242, ends at 7209 | B (f69), A (f128), exits to 7696 |
| EHZ loop 4, right, from 8500 | layer 0, max x 8906, ends at 8658 | B (f101), A (f160), exits to 9564 |
| EHZ loop 1, **left**, from 4500 | layer 0, 0 inverted frames. Never enters the loop and drops to the lower route (y 860) | exit line to B (f22), apex line to A (f101), 26 inverted frames. Full circuit leftward, out at 3635 |
| CPZ braid, right, from 12160 (CPZ 800) | layer 0, 116 airborne frames, falls from y 815 to 1216 (the level below) | line (888,480) to B (f14). Rides the braid on B with 0 airborne frames to x 13954 |
| CPZ from the braid, 1500 frames | stops at 14566 (**CPZ 3206**), the A-only wall at the vertical loop | B from 888. Passes 3206, rides the vertical loop (15 inverted), line (3328,704) to A, stops at 14870 / y 1389 (CPZ 3510, 1133) |
| CPZ vertical-loop floor, from 14310 (CPZ 2950, y 896) | stops at 14566 (CPZ 3206) with gsp 0 | B at (3072,768), loop ridden (31 inverted), A at (3328,704), stops at CPZ (3510, 1133) as above |
| CPZ upper route, from 13700 (CPZ 2340) | stops at 14166 (CPZ 2806), y 749 | **identical**: no line in reach, stops at CPZ 2806 |
| CPZ at the booked wall, from 14700 (CPZ 3340) | stops at 14950 (CPZ 3590) | **identical**: no line fires. The S2 lines there ((3600,256), (3648,288), (3712,320)) span y 192..352 CPZ, above a player on the y 490 floor |

No drive faulted. Every `none` run shows layers `[0]` only.

**What each hypothesis forbade, and whether it happened.**
- *H1: nothing writes the layer in this act.* Forbids any frame with layer 1 in a `none` run. None
  seen, in 11 runs (5,300 frames).
- *H2: without switchers an EHZ loop cannot be completed rightward.* Forbids a `none` run exiting
  past the loop's right foot. Max x stayed at or below the loop's right arc (4298 / 6858 / 7242 /
  8906) in all four.
- *H3: placing S2's own switchers is enough, with no collision or physics change.* Forbids an `s2`
  run failing a loop that S2 completes. All four loops rightward and loop 1 leftward completed. The
  layer ended on A after every exit, and the lines fired in the order S2's layout implies.

**Limits of the host model.** It writes `Sst.layer` between frames, from the resolved position.
S2 does the same (Obj03 runs after the player in the object loop). It does **not** model priority,
the sidekick, or S2's object load window (a line is armed from the first frame, not when it scrolls
in). The two CPZ runs that end at CPZ (3510, 1133) stop against a low ceiling with gsp 0, holding
RIGHT without rolling. Whether S2 passes there in the same state was **not measured** against S2
itself. The two "identical" CPZ rows show the model is only as good as its start: a player placed
on plane A has no switcher history. In S2 he would reach CPZ 3340 already on B from an earlier line,
so those rows neither refute nor confirm anything about that wall.

## The owner's Chemical Plant stuck spot (coordinator's question)

*"Rolled down a quarter-pipe on the right face of a tall grey machinery block, stuck part-way down;
feet level with a row of white square blocks running right from the curve into a white open area."*
I identified a spot from that description alone, with no coordinate from the owner, so treat this
as a candidate, not a finding.

The best match in the reachable CPZ strip is the vertical loop at **CPZ x 3200..3344**
(`cpz_3000_planes.png`). The right face of the tall block at x 3200..3232 runs down to a quarter-pipe
(x 3216..3330, y 960..1150) that curves into the lower floor at y ~1150. That floor runs right into
open space, under a machinery block with white square cells. The quarter-pipe is **solid on plane A
only**.

- The layer does **not** explain getting stuck part-way down *that* curve. The engine collides only
  against plane A, and plane A is what S2 uses there too: S2 comes out of the vertical loop onto A
  (line (3328,704), and the model reproduces it: A at the exit, then down the curve).
- The layer does explain **how the route around it differs**. In S2 the player enters this
  structure on B, along the B-only floor at y 896..960, and the A-only wall at x 3200..3216 is not
  there for him. In aeon that wall stops a rightward runner at CPZ 3206 (measured above), and the
  B floor is a hole.

If the owner's spot is a different curve, this can be settled in two runs:
`loop_plane_probe.py --x <act x> --y-from <y>` with `--switchers none` against the same drive with
the layer forced to 1 (or `--switchers s2` from further back). If he still sticks on B, it is slope
physics, which is the `research/sonic-slope-collision` lane, not this one. I did not chase it.

## Why the existing crossover marks cannot stand in for S2's switchers (read)

`Player_LoopCrossover` (`player_common.emp:926-1440`) is the only in-engine layer writer that
reaches level data. Its semantics were built for OJZ's hand-painted loop:

- **The direction gate is fixed to OJZ's handedness.** A TO_B mark fires only while x_vel > 0 and a
  TO_A mark only while x_vel < 0 (`.dir_left` / `cmpi.b #LAYER_PATH_B`). OJZ puts its loop's right
  arc on B. **Sonic 2 puts the right arc on A.** EHZ's apex needs "to B while moving left" and its
  exit needs "to A while moving right": both are exactly the two cases the gate refuses. 15 of the
  19 EHZ lines (`$11/$12/$91`) are "to A going right, to B going left"; 2 (`$0A`) are the reverse and 2
  (`$02`) are A both ways.
- **A mark is a cell, not a line.** It fires on entering a cell on the plane you are on. It has no
  extent along the line, no side memory, no grounded-only flag, no horizontal form and no
  priority-only form. S2 uses all of these inside the clip: CPZ has 2 horizontal lines, 9 x-flipped
  (priority-only) lines and 21 lines that set priority; the grounded-only form is used 4 times in
  EHZ and once in CPZ.
- **Priority is derived from the layer** (B = high, `(5c)` in the routine's header). S2 sets priority
  per crossing, independently of the path. EHZ never raises it. A B-derived priority would draw Sonic
  in front of the loop art on the left arc, where S2 keeps him low.
- The routine's own header already records that a centre-placed mark is crossed twice by a full
  circuit, and that S2's arrangement (a return-to-default line past the exit foot) is the fix.

## Options to make it play like Sonic 2

In every option the collision data stays exactly as it is.

**A. Carry S2's Obj03 lines as a per-act line table, run by the player preamble** (recommended to
consider first). The clip bake reads `level/objects/<ZONE>_1.bin` and emits every Obj03 inside a
clip's src rect as a ROM row (x, y, half-length, flags), shifted by dst-src, per section. A new
routine next to `Player_LoopCrossover` evaluates S2's rule against the rows of the current section
for each player, and writes layer and priority the way Obj03 does. It keeps its own side flags, which
means one byte per line per player, or a per-player last-position compare, which needs no RAM per
line.
  - Size: bake emitter + tests ~150-250 lines of Python; routine ~80-120 lines `.emp`; one
    per-section table pointer in the section record, or a per-act table walked with an x-sorted
    cursor.
  - **Canonical bytes move** (the new routine and an empty table land in both canonical shapes).
    That is routine here, but the placement goldens move with them.
  - This is the S3K-floor *semantics* without an object slot per line. It is data-driven and
    build-time checkable (for example: refuse a line whose two sides lead to a plane that has no
    ground there). It does not depend on the clip ever carrying objects.
  - It is a design decision (a new engine mechanism beside the crossover marks), so it is not built
    here.

**B. Revive `PathSwap` as a faithful Obj03/`Obj_PathSwap` and teach the clip to carry objects.**
Closest to S2/S3K, and the object already exists in outline. But today's `path_swap.emp` supports
vertical lines only, "right side = B" (with an invert bit), no per-direction target, no priority and
the leader only. It is parked for deletion, and its `ObjDef_PathSwap` row is a placement boundary in
sigil's frozen tables (DEFERRED_WORK, pathswap-remove: `section_align.rs:176`). Rewriting it moves
canonical bytes that sigil pins, which is a cross-repo change and out of this lane (no sigil
changes). It also needs the clip to carry an object layer, which the owner scoped out of the first
cut. It costs 44 object slots' worth of spawn traffic for what is a pure data rule. **Larger**,
touches sigil, and needs an owner ruling on clip objects.

**C. Translate S2 lines into painted crossover marks at bake time.** Cheapest in data, but it only
works after an engine change to the direction gate: the mark would have to carry its crossing
direction, which widens the 2-value encoding and grows the attr set against `AttrSet.CAP` = 255. It
still cannot express horizontal, grounded-only or priority-only lines, or the extent of a line.
**Not recommended.** It would reproduce S2 approximately and with known holes.

In any option, **what "like Sonic 2" also needs beyond the layer:** priority per S2's bits, not
derived from the layer (EHZ keeps Sonic low; CPZ's braid toggles him in front and behind), and
the sidekick handled as well once there is one. Past the current CPZ end, the owner's
S2CLIP-CPZ-FURTHER card already lists the other missing mechanisms (spin tubes, boosters, pipe
springs).

## Open items (booked in DEFERRED_WORK as S2CLIP-PLANE-SWITCH)

1. Owner decision: option A / B / C, or leave the act on one plane. Until then the EHZ loops cannot
   be completed and the CPZ braid drops the player. Suggested decision card below.
2. Once switchers exist, re-measure the CPZ end at CPZ (3510, 1133) with a real S2-equivalent run
   (rolling). The model stops there holding RIGHT, unverified against S2.
3. CPZ upper route stops at CPZ 2806 (y 493) in both modes. Not plane-related; possibly
   slope/step physics (the other lane) or a jump S2 also needs. Not investigated.
4. The owner's stuck spot needs a coordinate to confirm which curve it is (see above).
5. `Player_LoopCrossover`'s direction rule is OJZ-handed. Any S2-derived content painted with marks
   inherits the inverted-handedness problem. This is worth a line in `docs/LOOP_CROSSOVER_ENCODING.md`
   when the mechanism is decided.

Suggested decision card (for the overseer to raise, not filed by this branch):
*"Sonic 2's loops and plane changes don't work in the test level, because Sonic 2 does them with an
object our level doesn't carry. Which way should we add it?"* The options are A, B and C above,
with A recommended because it keeps Sonic 2's rule exactly and does not need the level to carry
objects.
