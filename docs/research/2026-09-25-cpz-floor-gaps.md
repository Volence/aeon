# What Sonic 2 puts at the 34 Chemical Plant floor "pinholes" (S2CLIP-CPZ-LONGER)

2026-09-25. Research only: no source, data or gate changes. Question from the hub: widening the Sonic 2 clip's
Chemical Plant (CPZ act 1) from 2528 px to 6624 px (past the second checkpoint at CPZ x 6143) is refused by
`tools/collision_consistency.py` RULE B, which finds 34 floor pinholes (16-px gaps) in Sonic 2's own CPZ collision.
The site list is in `docs/DEFERRED_WORK.md` on `parcel/s2clip-cpz-longer` at 47c43013 (the S2CLIP-CPZ-LONGER row).
**What does Sonic 2 put at each site?**

Reproduce with `python3 docs/research/2026-09-25-cpz-floor-gaps/cpz_gap_probe.py`. Run
`python3 tools/s2_zone_convert.py convert s2disasm@CPZ` first so the probe can also check the converted-tree path.
The probe is research only: no gate, build or test calls it.

## Answer in one paragraph

**No object fills any of them, and none is a conversion artifact.** The 34 are 20 distinct (x, y) positions, 14 of
them on both planes. **None of them can make a standing player's ledge probe report a ledge**, in Sonic 2 or in aeon. 29 are
the floors of small **air pockets sealed inside solid rock**: chunk entries whose solidity bits are all clear, set inside solid
ground (often the same block is solid next door), or blocks with no collision shape. 1 is **not a hole at all**: a 16x16 air cell at the foot of a wall, beside a ramp only 1-2 px thick,
with solid floor directly under it, so the real surface dips by 1 px there. It lies on the plane-A side of a Sonic 2
loop, in a region that is sealed on plane A. 4 are **16-px notches in
the underside of a slab**, covered from above. RULE B fires because it checks one collision row at a time. It does not
ask whether anyone can stand beside the gap, or whether there is ground just under it. Its own derivation says the harm is a false teeter, and none of these
can cause one. They are false positives of the gate on donor content, not defects in Sonic 2's level.

The brief's hypothesis was "objects fill them", read from the 4-row stacks at CPZ x 4320 and 5408. **That hypothesis
is refuted.** Those stacks are sealed 32x80-px air pockets inside walls. The nearest object is 92 to 156 px away (Manhattan distance), and
it is a monitor or an invisible plane-switch line, not anything solid.

## Method: three derivations that agree

1. **Stock data, Sonic 2's own reading.** This path reads `level/layout/CPZ_1.kos` (s2.asm:89709),
   `mappings/128x128/CPZ_DEZ.kos` (s2.asm:90311), the primary and secondary collision indexes (s2.asm:89601, :89603)
   and `Collision array - Vertical.bin` (s2.asm:89576). It then applies `FindFloor`'s tests (s2.asm:42941-42990): block
   id non-zero, the plane's top-solid bit (`btst d5,d4`, bit 12 for the primary plane and bit 14 for the secondary),
   collision id non-zero, and the height at `(x, NOT-ed when X-flipped) & 15` non-zero. The result is a floor line per
   pixel for each 16-px row. It is scanned in the two act sections of the 6624-px variant (CPZ x 2528..4575 and
   4576..6623) for gaps under 18 px that have floor on both sides.
2. **The converted donor tree through aeon's own code.** This path reads `section_N.collattr(b).bin` and runs
   `collision_pipeline.bake_plane_cell` against `data/collision/base_s2`, which is byte-identical to the stock arrays
   (checked with `cmp`). It then calls the gate's own `find_pinhole_violations` with `min_gap_px` = 18.
3. **The site list in the DEFERRED_WORK row**, which came from the real clip build.

Paths 1 and 2 give **the same 34 (plane, x, y) triples**. They also equal the row's list once act coordinates are
converted (act = CPZ + (11808, 256)). Paths 1 and 2 share only the Kosinski decoder. The converter
(`tools/s2_zone_convert.py`) is therefore faithful at these cells, and a converter fix has nothing to fix.

Two predicates classify each site. Both are in the probe.
- **Sealed:** a 4-connected flood over 16x16 blocks in the site's plane. Only fully solid blocks count as walls:
  partial and sloped blocks count as open, which is the cautious choice for a "sealed" claim. A flood that grows past
  600 blocks counts as open.
- **Standable:** is there any standing position where the player's body fits in air, a foot sensor is on floor in the
  gap's row, and aeon's single ledge probe lands in the gap? The body is (2 x 9 + 1) x 38 px, from `PLAYER_X_RADIUS` 9
  and `PLAYER_Y_RADIUS` 19 (engine/system/constants.emp:179-180). The ledge probe is at x ± `LEDGE_PROBE_REACH`,
  which is 11 (games/sonic4/player/player_sensors.emp:503).

  The predicate is not blind. It found a standing position at one site in this list, inside a sealed cavity. Beyond
  x 6624 it found 3 on plane B in open space (see "Beyond the checkpoint"). It has a known blind spot: it requires a
  foot on the gap row's TOP pixel. It therefore answers "none" at CPZ (4864,1648), where the neighbouring floor is a
  ramp 1-2 px thick at the bottom of its block. That site was checked by hand instead (class L): a player CAN stand
  there, and the probe finds ground 1-2 px down.

## Per-site table

CPZ coordinates are Sonic 2's own. Act coordinates are the clip's. The block word is the chunk entry: bits 9:0 block
id, 10 X-flip, 11 Y-flip, 13:12 primary solidity, 15:14 secondary solidity. "Nearest object" is from
`level/objects/CPZ_1.bin` (s2.asm:90685). Each record is 6 bytes: x, then y (bits 0-11) with x-flip in bit 13, y-flip
in bit 14 and respawn in bit 15 (ChkLoadObj, s2.asm:33376-33404). The record number is its index in the file.
Object names come from `Obj_Index` (s2.asm:29686ff). Distances are Manhattan, from the centre of the 16x16 gap block
to the object's position.

| # | CPZ x | CPZ y | act x | act y | plane | chunk / block word | what the geometry is | nearest object (none covers the site) | class |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2672 | 1632 | 14480 | 1888 | B | $D8 / $309A (secondary solidity 0) | notch into the underside of solid ground that is solid at this x from y 1536 down to 1631. The only standing position whose probe sees it is inside a **sealed 64x48 cavity** (x 2608..2671, y 1584..1631, 12 blocks), which touches the notch only at a corner | #29 Obj26 monitor st $04 at (2669,1521), on the slab's top, 130 px | U |
| 2 | 2672 | 1648 | 14480 | 1904 | B | $D8 / $30A4 | the same notch's lower row, open to the air below, no standing position | #29, 146 px | U |
| 3-4 | 2848 | 320 | 14656 | 576 | A+B | $27 / $F05E (solid, but block $05E has collision id 0) | sealed 16x32 pocket (2 blocks) | #30 ObjA7 Grabber st $36 at (2870,400), 86 px | S |
| 5-6 | 2848 | 336 | 14656 | 592 | A+B | $27 / $F05E | same pocket | #30, 70 px | S |
| 7-8 | 3024 | 1456 | 14832 | 1712 | A+B | $1B / $00DE (the neighbours are $F0DE) | sealed pocket, 15 blocks, x 2976..3055, y 1440..1519 | #32 Obj26 monitor st $06 at (2991,1425), 80 px | S |
| 9 | 3328 | 928 | 15136 | 1184 | B | $39 / $F0E2 (secondary collision id 0) | sealed 1-2 block pocket on plane B. On plane A the cell is part of an open room with no floor in this row | #40 Obj03 st $41 at (3448,960), 136 px | S |
| 10 | 3712 | 544 | 15520 | 800 | B | $39 / $F0E2 | the same chunk ($39) again, the same sealed plane-B pocket | #46 Obj03 st $A8 at (3712,320), 240 px | S |
| 11-12 | 4320 | 416 | 16128 | 672 | A+B | $AC / $0055 (the neighbours are $F054 / $F0CB) | **sealed 32x80 pocket** (6 blocks, x 4304..4335, y 416..495): a column of blocks $0055/$0035/$0038/$0418, all with solidity clear on both planes; two of them ($0035, $0418) are the solidity-cleared twins of the solid $F035 / $F018 beside them | #58 Obj03 st $65 at (4264,392), 96 px | S |
| 13-14 | 4320 | 432 | 16128 | 688 | A+B | $AC / $0035 | same pocket | #58, 112 px | S |
| 15-16 | 4320 | 448 | 16128 | 704 | A+B | $AC / $0038 | same pocket | #58, 128 px | S |
| 17-18 | 4320 | 480 | 16128 | 736 | A+B | $AC / $0418 | same pocket, bottom row | #60 Obj2D one-way barrier st $00 at (4296,608), 152 px | S |
| 19 | 4864 | 1648 | 16672 | 1904 | A | $3D / $005E | the corner between a ramp 1-2 px thick (block $074, X-flipped, heights 2..1) and a wall. The block **under** the gap (y 1664) is solid, so the surface steps down 1 px. It is the floor of the **plane-A interior of a loop plus a shaft**, a 260-block region (x 4768..4959, y 1184..1663) that is sealed on plane A | #68 Obj03 st $79 at (4848,1600), 80 px: see class L | L |
| 20 | 4896 | 1616 | 16704 | 1872 | A | $3D / $00A3 | sealed 3-block pocket in the wall beside that shaft | #68, 80 px | S |
| 21-22 | 4976 | 1440 | 16784 | 1696 | A+B | $83 / $0C74 (X+Y-flipped, solidity 0; the neighbours are the solid $FC73 / $F874) | a 16-px break in a slab's underside, which is a hanging ceiling 1-6 px deep. Solid above, open below, no standing position | #70 Obj03 st $A8 at (4992,1472), 32 px (an invisible line, not solid) | U |
| 23-24 | 5408 | 1312 | 17216 | 1568 | A+B | $BD / $0055 | **sealed 32x80 pocket** (x 5392..5423, y 1312..1391). The same four blocks as CPZ x 4320, in a different chunk | #80 Obj26 monitor st $04 at (5379,1265), 92 px | S |
| 25-26 | 5408 | 1328 | 17216 | 1584 | A+B | $BD / $0035 | same pocket | #80, 108 px | S |
| 27-28 | 5408 | 1344 | 17216 | 1600 | A+B | $BD / $0038 | same pocket | #80, 124 px | S |
| 29-30 | 5408 | 1376 | 17216 | 1632 | A+B | $BD / $0418 | same pocket | #80, 156 px | S |
| 31-32 | 6304 | 1600 | 18112 | 1856 | A+B | $CC / $0055 | sealed pocket (6 blocks, x 6304..6367, y 1600..1647). The same block family again, in a third chunk | #109 Obj1D blue balls st $05 at (6416,1608), 104 px | S |
| 33-34 | 6304 | 1616 | 18112 | 1872 | A+B | $CC / $0035 | same pocket | #109, 120 px | S |

Objects near the sites that could in principle carry collision are these: Obj74 invisible solid block (#82 at
(5488,1088), #89 at (5648,960)), Obj6B platform (#86/#87 at (5568,1040)), Obj78 stairs (#90 at (5648,1552)), Obj19
platform (#93 at (5720,1320)) and Obj0B tipping pipe (#103-#106 at x 6288..6384, y 1424). **Every one of them is at
least 184 px from every site**, measured in a straight line. Of all the gameplay objects, the closest to any site is
the Obj2D one-way barrier #60 at (4296,608), 124 px below the CPZ x 4320 pocket. The spin-tube main paths (`misc/obj1E_b.asm`, included at s2.asm:48402, all 14 polylines)
pass within a player's box of none of the sites.

## The classes

| class | count (plane cells) | sites | what it is | can a player ever stand beside it? |
|---|---|---|---|---|
| **S: sealed pocket** | **29** (A 14, B 15) | 2848 x4, 3024 x2, 3328 B, 3712 B, 4320 x8, 4896 A, 5408 x8, 6304 x4 | air sealed inside rock on that plane. Mostly chunk entries with both solidity bits clear, set inside solid ground (the $0055/$0035/$0038/$0418 column appears in three chunks, $AC, $BD and $CC; $00DE sits among solid $F0DE), plus blocks $05E and $0E2, which have collision id 0 in the index | no. The flood is sealed even when slopes count as open |
| **L: 1-px dip in the plane-A loop shaft** | **1** (A) | 4864 A | the floor of the shaft under the plane-A shell of the loop at x 4736..4991, y 1168..1407. On plane A a 32-px wall stands at x 4736..4767 from y 1216 to 1407, where plane B is open. The flagged cell is air, but the block under it is solid and the ramp beside it is only 1-2 px thick, so a player standing there has ground 1-2 px under the probe point. That is below `LEDGE_NO_GROUND` 8 in aeon and below Sonic 2's balance threshold of 12 (s2.asm:36323-36324), so it is no ledge. Rule B misses this because it looks only inside one 16-px row. Plane context: Obj03 #68 at (4848,1600), subtype $79, is a vertical line 128 px tall (y 1536..1663) that sets plane B whichever way it is crossed, in the air too (bits 3 and 4 set, bit 7 clear; s2.asm:45205-45281). The loop-top line #69 at (4864,1200), subtype $A8, sets plane A when crossed leftward on the ground (bit 4 clear, bit 7 set). **So Sonic 2 can put a player in this shaft on plane A** (for example, running the loop backwards), and this cell cannot be called unreachable in Sonic 2 | **yes in Sonic 2, possibly. It is still no ledge** (floor 1 px below). In the clip it is sealed on plane A (260 blocks) |
| **U: underside notch** | **4** (A 1, B 3) | 2672 B x2, 4976 A+B | a 16-px notch in the underside of a slab, covered from above | no. The only body-sized air beside 2672 is a sealed cavity. At 4976 the row above is solid |

Total: 29 + 1 + 4 = 34. A 16/B 18 by plane.

**In the clip only plane A is ever read.** The clip act carries no Chemical Plant objects: its objects are still the
shipped act's (tools/clip_rom_bake.py:41-43). The converted tree has `crossover_marks` 0 (the donor's `zone.json`).
The player's `layer` is cleared at spawn (games/sonic4/player/player_common.emp:828), and apart from that it is written
only by a crossover mark (player_common.emp:1420). So the clip's player stays on plane A, and the 18 plane-B cells are
never probed in the clip at all. That is read from source. It was not run.

## What Sonic 2 itself does beside a gap like this

Sonic 2's balance check is a single probe at the player's centre x: `ChkFloorEdge`, with a distance of 12 or more
meaning "balance" (s2.asm:36322-36325, 43674-43697). **Sonic 2 would therefore teeter over an exposed 16-px floor gap
too**, over a slightly different window of positions from aeon's probe at x ± 11. That matters for later work, not for
these 34. For an exposed gap, filling it would take away a teeter Sonic 2 has. None of the 34 makes Sonic 2 balance: 33 cannot
be stood beside, and at CPZ 4864 the ground is 1-2 px under the probe point, well inside the 12-px threshold.

## Options per class, costed

The same options apply to all three classes, because all three fail the same test: no standing player's probe can
report a ledge. For S and U nobody can stand beside the gap. For L the ground is 1-2 px under it.

| option | S (29) | L (1) | U (4) | changes what the player experiences vs Sonic 2? | cost |
|---|---|---|---|---|---|
| **G. Refine RULE B**: a gap counts only if a standing player can reach a position where the ledge probe sees it (body box in air, a foot on the surface, the region not sealed) AND the probe then finds no ground within `LEDGE_NO_GROUND` (8 px) below the surface. The second part looks into the next row down, and it is what clears L | clears all 29 | clears | clears | **No.** The ROM is unchanged and the collision stays byte-faithful to Sonic 2 | `tools/collision_consistency.py`: a per-candidate body-box check using `collision_pipeline.covers` semantics on the attr heights, plus a cell flood inside the section (a flood that reaches the section edge counts as OPEN, so the gate stays red in that case). About 100 lines. 4 new tests: sealed pocket exempt, underside notch exempt, corner-touching cavity exempt, exposed flat-floor pinhole still red. The existing rule-B fixtures keep firing if off-grid rows count as air. Update the gate docstring's "what green rules out". About half a day. **Weakens the owner's teeter guard in a precise way, so it needs the hub or owner to say yes.** A rule-A-style "buried" exemption (solid cell directly above) is not enough: it clears only 14 of the 34, because the stacked rows have pocket air above them |
| **F. Clip-bake fill**: paint each flagged cell as a full block in that plane, only in clip acts, reported per cell (the gate's own FIX) | clears | clears, **but only with the right shape** | clears | **S and U: none predicted.** Nobody can stand beside those cells, and a 16-px ceiling notch is narrower than the 18-px head-sensor pair. Not measured. **L: a full-block fill CHANGES play.** It turns Sonic 2's 1-px dip at the wall's foot into a 16-px step. Sonic 2 can reach that spot on plane A (see class L); the clip cannot, because it is sealed on plane A there. The faithful fill at L is a 1-px-high flat shape, or nothing | About 40 lines in `tools/clip_act_bake.py` or `tools/clip_rom_bake.py` (which the DEFERRED row warns a parallel parcel may be editing), plus a per-cell report in the clip manifest. Attr-set growth: likely 0, since full solid blocks are already interned. It is a Sonic 2 geometry edit made to satisfy a gate, and every later Sonic 2 clip will need it too (21 more flagged cells in the rest of CPZ act 1, below) |
| **O. An aeon object equivalent** | n/a | n/a | n/a | n/a | Sonic 2 puts no object at any site, so there is nothing to port for these cells. Aeon has no spin tube, booster, platform or staircase objects today (`games/sonic4/objects/`); see the owner items |
| **X. Stop the clip before the class** | impossible | impossible | impossible | would cut the owner's request | The first site is at CPZ x 2672, 144 px past today's 2528 end. No end past it avoids them, and no section-aligned end past act x 14336 exists without the void (DEFERRED row) |
| **C. Converter fix** | n/a | n/a | n/a | n/a | Nothing to fix: the stock and tree derivations agree cell for cell |
| **B. Baseline entries** | forbidden | forbidden | forbidden | no | `tools/collision_baseline.json` says not to add entries to get a build green |

**Recommendation, every class: G, refine RULE B.** Why:
1. It keeps the collision byte-faithful to Sonic 2, which is what the owner asked for ("plays like the original").
2. It makes the gate's check match its own stated derivation. Rule B's docstring names one harm: a false ledge, a
   teeter seen by the single-point ledge probe (tools/collision_consistency.py:93-113). None of these 34 can produce
   one, so flagging them serves nothing.
3. It stops every later Sonic 2 clip from paying for the same false positive.

**Fallback: F**, if the hub prefers not to touch the gate. It is invisible in play for the 33 S and U cells. At L it
must use a 1-px-high shape, not the gate's all-16 FIX. Its costs are touching the clip bakers and hiding the question
the next time a cell is flagged.

Neither option is needed for the plane-B cells if the clip stays plane-A-only. The gate checks both planes, though, so
both options must cover both planes.

## Owner and hub items

1. **Gate policy (G vs F).** This is a change to the owner's teeter guard. G is recommended. G leaves play identical to
   Sonic 2 at these cells. F does too, provided L gets a 1-px shape.
2. **This matters more than the 34 cells: the widened strip will not play like Sonic 2 without Chemical Plant's
   objects, and pinholes are not the reason.** CPZ x 2528..6623 has 28 Obj03 plane-switch lines, 4 Obj1E spin tubes,
   3 Obj7B pipe-exit springs, 5 Obj1B speed boosters, 2 Obj74 invisible solid blocks, 2 Obj6B platforms, an Obj78
   staircase, an Obj19 platform, an Obj2D one-way barrier, 4 Obj0B tipping pipes and 5 Obj41 springs, plus badniks,
   monitors and 2 starposts. The clip carries none of them and never leaves plane A. At the loop at x 4736..4991,
   plane A has a 32-px wall where Sonic 2's plane-B route is open. A plane-A player running right along the y 1408
   floor meets it. **Whether the second checkpoint can be reached on plane A at all has not been measured.** No
   traversal was run, per the no-emulator rule. The next step would be a headless `tunnel_run_witness`-style run over
   the widened FAST ROM.

   For comparison, the stretch already shipped (CPZ x 0..2527) holds 12 Obj03 lines, 4 Obj19 platforms, 1 spin tube
   and 1 breakable block that the clip also lacks.

   Aeon's layer model is the directional crossover mark: TO_B fires only when moving right and TO_A only when moving
   left (player_common.emp:1400-1420). That cannot express an Obj03 like #68, which sets plane B from both sides.
   `games/sonic4/objects/path_swap.emp` can express it, but its header says it is placed in no level data and parked
   for deletion.
3. **The DEFERRED row's option (b), "look at what Sonic 2 puts on those cells", is answered: nothing.** Its reading
   that the 4-row stacks look like a pipe or platform gap is refuted: they are sealed pockets.

## Beyond the checkpoint (out of scope, measured once)

Running the same stock scan over the rest of CPZ act 1 (x 6624..10111, in two 2048-px windows that are not the act's
real sections) finds **21 more** flagged cells. 12 are sealed. 4 have a standing position, and 3 of those are in open
space on plane B: CPZ (9328,864), (9456,1376) and (8688,1408). Those 3 would be real exposed gaps where Sonic 2 itself
teeters. Option F there would change Sonic 2's behaviour and option G would keep it. That argues again for G.

## Caveats

- Nothing here ran on hardware or in an emulator. "Sealed" and "standable" are geometric predicates written from
  `FindFloor` and aeon's player constants. The standability model ignores slopes under the body and rolling height,
  and it requires a foot on the gap row's top pixel. That does not weaken a "no" at the S and U sites, where the
  enclosing blocks are full and solid. At the one site with a thin ramp beside it (L, CPZ 4864) the model's "none" was
  wrong, and the site was re-read by hand (see its row).
- Plane semantics: plane A is the primary index with top bit 12, plane B the secondary with top bit 14. The Obj03
  subtype reading is from s2.asm:45149-45281: bit 2 chooses a horizontal or vertical line, bits 0-1 the size ($20 <<
  n), bit 3 the plane when crossing right or down, bit 4 the plane when crossing left or up, and bit 7 means grounded
  only. An X-flipped Obj03 changes no plane (s2.asm:45234-45237).
