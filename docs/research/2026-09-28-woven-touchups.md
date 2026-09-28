# Woven act touch-ups: what the owner's two wishes cost, and whether either needs the freeze

**Date:** 2026-09-28. **Branch:** `research/woven-touchups`, base aeon `origin/master`
`a44c627700d15e411ae92839f520f446c0a24ef3`. **Status:** sizing research. No engine, tool or
act data was changed. Scratch variant manifests were baked and flown in this worktree, then the
committed tree was restored (`git status` clean apart from this note and its directory).
No emulator MCP was used; every emulator number comes from headless subprocess runs.

**Tags.** **MEASURED** (a command in §8 printed it), **READ** (file:line), **INFERRED**
(reasoning on read or measured facts; the sentence says which).

**The owner's words** (banked at empyrean `3a70b2c5`, `docs/OVERSEER-LOG.md`, "what he wants
from WOVEN-EDITABLE"):
1. "the only reason I want it edit is because there's some things I wanted done, should I share
   them instead?"
2. "so they layyouts are layouts from the map but they don't necessaryily connect to the other
   tunnels or maps and you can't get to them sometimes so I was thinking of that, and another
   thing was thinking of just getting rid of part of the tunnel with some more of the map
   (doesn't have to even extend the wholee sidde of the region, just add a new little rectangle
   where the tunnel is). Does that make sense?"

---

## 0. The answer for the owner, in plain words

- **Neither wish needs the freeze.** Both are about *where Sonic 2's own map pieces sit*,
  which the clip list already controls. The freeze is only for making a cell look or collide
  differently from Sonic 2 (§5).
- **Wish A, "pieces you can't get to": you are right, and it is worse than a few pieces.**
  Starting at the start and playing normally, you can reach Emerald Hill and fall into Hidden
  Palace's west half, and that is all. You cannot get into the first tunnel. Wing Fortress,
  Chemical Plant, both Metropolis halves, Oil Ocean and Hidden Palace's east strip are only
  reachable by flying there in debug. Our route test never noticed, because it puts the player
  at each tunnel's mouth instead of walking there (§1).
- **The main route can be fixed with the clip list alone. That fix is measured, not guessed**
  (§2): end Metropolis west just before its pit, drop the tunnel from Emerald Hill to a
  lower row, and move the lower part of the act down 320 px. In the real game, holding right
  and jumping from the start then carries you through Emerald Hill, the first tunnel, Metropolis
  and the second tunnel into Chemical Plant. It stops 262 px into Chemical Plant, at a loop
  wall that is already on the books (WOVEN-CPZ-POCKET-ROUTE).
  **Cost: small to medium.** The builder change is small. Most of the cost is re-running the
  checks and re-deriving two generated files.
- **Some pieces cannot be connected by moving pieces**, because Sonic 2 reaches them with
  objects (springs, moving platforms) and clips carry no objects: Wing Fortress (the whole top
  row), most of Metropolis east, and the climb back up out of Hidden Palace. Those wait for
  objects (S2CLIP-OBJECTS), or for the freeze if you want to hand-draw a ledge instead (§5).
- **Wish B, "swap part of a tunnel for more map": possible, but the tunnel cannot get
  shorter.** Each tunnel is exactly as long as the zone switch needs: palette, background and
  music change while only tunnel is on screen. So a new rectangle of map beside a tunnel pushes
  everything past it along by the same amount. The measured example (§3): 128 px more Oil
  Ocean at the Hidden Palace to Oil Ocean tunnel bakes clean and flies clean. Chemical Plant,
  Metropolis east and Oil Ocean move 128 px right, and the Metropolis to Chemical Plant tunnel
  grows by 128 px to pay for it. **Cost: small per rectangle**, plus the same re-checks.
  - The first tunnel (Emerald Hill to Metropolis) cannot take an Emerald Hill rectangle at its
    current height. Every width tried was refused, because Sonic 2's ground past that edge is
    not the same on its two collision layers.
- **One question back** is in §7. It asks you to point at the pieces and the tunnel you meant.
  Coordinates to fly to are there.

---

## 1. Wish A: which parts cannot be reached, and why

### 1.1 The repo's own tools cannot answer this, so two measurements were added

The brief asked for the answer from `tools/clip_reachability.py`, `tools/woven_route_witness.py`
and `tools/crossing_witness.py`. None of them can say whether one part of the act connects to
another:
- `clip_reachability` asks, per 8-px column, whether there is art and a landing surface and
  whether a fall can end (**READ** `tools/clip_reachability.py:18-40`). It is GREEN on this act
  (**MEASURED**, §8 c1). That is true, and it says nothing about connectivity.
- `woven_route_witness` **places** the player before every connector through the warp mailbox
  (**READ** `tools/woven_route_witness.py:17-19`, "The zone BETWEEN two corridors is not run").
  The landing record says so: "Not driven: going UP any shaft ... and running through the zones
  between connectors (the route PLACES the player)" (**READ** `docs/DEFERRED_WORK.md:37213`).
- `crossing_witness` drives one connector at a time.

So this note uses two instruments of its own. Both are committed beside it in
`docs/research/2026-09-28-woven-touchups/`:
- **`woven_flood.py`, a reachability flood over the baked act.** It reads the same strip bytes
  that `clip_reachability.StripGeometry` reads, plus the emitted solidity and heightmap tables.
  It refuses to run on a tree without this act's bake stamp. The model is **deliberately
  generous**, so an "unreachable" from it is a strong claim:
  - the two collision planes are merged: a cell is a floor if either plane says so, and a wall
    only if both do;
  - the player is a point, not a body;
  - a jump rises 96 px (JUMP_RISE_MAX is 99) and can drift 384 px sideways;
  - a fall passes through LRB-only interiors, as a Sonic 2 body does.

  **Its one known blind spot is momentum.** It does not model a spindash launch. In the real
  game, a spindash from Hidden Palace east got into rows the model marks unreached (§1.3). So
  the model's "unreached" is strong *except* where speed matters, and every claim the answer
  rests on was also flown on the real ROM.
- **`escape_probe.py` and `plateau_sweep.py`: headless runs on the real DEBUG ROM.** Each
  places the player (or starts at the act's own start), leaves debug flight with a B press, and
  plays scripted input:
  - `escape_probe` plays 7 patterns: hold right, hold left, each with a jump every 40 frames or
    none, a zigzag, and a spindash either way;
  - `plateau_sweep` is from the start, 3 injected speeds times 50 jump timings = 150 runs.

  Each run reports the box the player's centre covered. This is corroboration, not proof: a
  scripted pattern that fails does not prove that no pattern succeeds.

A map of the flood is at `docs/research/2026-09-28-woven-touchups/reach_map_base.png`, one pixel
per 8 x 8 px of the act:
- **green:** a standing spot reached from the start;
- **cyan:** reached from some connector but not from the start;
- **red:** reached from nowhere;
- **grey:** solid on both planes;
- **tan:** a floor.

### 1.2 From the start, only Emerald Hill and Hidden Palace west are reachable

**MEASURED** (flood, §8 c2). Standing spots reached from the start, per piece:

| Piece | From the start | From the start or any connector |
|---|---|---|
| ehz_double_loop | 1,995 / 2,033 (98%) | 98% |
| hpz_west | 1,292 / 1,924 (67%) | 67% |
| mtz_west | 154 / 382 (40%, model only, see 1.3 row 2) | 65% |
| cpz_loop_cluster, mtz_east, ooz_east, hpz_east, wfz_deck | **0** | 80%, **5%**, 93%, 86%, **20%** |

Connector graph (flood from each connector's own standing spots; **MEASURED** §8 c2):
- start reaches `ehz_to_hpz` (C4) and, in the model only, `ehz_to_mtz` (C5; see row 1 below);
- `ehz_to_mtz` reaches only `ehz_to_hpz`;
- `ehz_to_hpz` reaches only `ehz_to_mtz`;
- `mtz_to_ooz` (C9) reaches **nothing**.

### 1.3 The unreachable list, with coordinates and causes

All coordinates are act (world) px.

| # | Where | What cannot be reached, and why | Evidence |
|---|---|---|---|
| 1 | **The first tunnel C5's mouth**, on Emerald Hill's east plateau, x 1344..2559, standing y ~2420..2496; tunnel x 2560..3167, floor 2496 | The tunnel's floor was put on EHZ's high ground (the manifest note, item 4). From the start, nothing gets up there. In 150 swept runs (3 speeds x 50 jump timings) the highest the player got anywhere east of x 1344 was y 2581, about 160 px under the plateau. None of the 7 scripted patterns passed x 2560. The rightward runs all ended in EHZ's bottom-right pit (x 2230, feet on the fill at 2944) or against the fill at x 2550. The generous flood reaches it only by a 96-px-up, 384-px-across leap off the second loop's top, (992, 2544) to (1376, 2448). **INFERRED:** that needs about 12 px/frame at take-off, and no tested input produced it. | **MEASURED** §8 p1, p2, c3 |
| 2 | **Metropolis west past its walkway**, and C6's mouth (x 4688, floor 2880) | A player arriving through C5 drops onto MTZ's start walkway (y 2880, x 3177..4190) and is **trapped**. He cannot climb back up to C5 (min x 3177 in 7 of 7 patterns). He cannot reach C6: a 500-px pit spans x 4190..4580 on the walkway's row, and Sonic 2 crosses it with an object. He ends at the pit's bottom (4662, 4270). The manifest note already said "Metropolis's west half is cut by its pit" (item 11). | **MEASURED** §8 p3; **READ** manifest note item 11 |
| 3 | **Wing Fortress, the whole top row** (x 1536..7679, y 0..1407; 20% reachable even from its own shafts) | No shaft climbs into it. The distance from the highest reachable ground under each lane up to the lowest ledge: **C1 624 px** (EHZ ground 2480, lowest ledge 1856) and **C2 688 px** (MTZ walkway 2864, lowest ledge 2176). The jump is 99. C3 is a drop. So the ledges are in the shaft, but the ground is far below the shaft's bottom mouth. The top decks, y 304..671 (2,819 standing spots), are unreached even from the shafts. | **MEASURED** §8 c2 |
| 4 | **Hidden Palace west is a dead end** (x 0..2559, y 3504..5551) | C4 is **one-way down**: HPZ's ground under the lane is at 4320 and C4's lowest ledge at 3440, so the climb is 880 px (the woven report said "ledges back up"). From the C4 landing, 7 of 7 patterns stayed below y 4398 and west of x 2470. HPZ west's route climbs east to its edge at about (2400..2559, 4380..4540) and meets the fill: the east piece, `hpz_east`, is only rows 4800..5103 (the v2.1 recut, donor y 1296..1599). The upper-left pocket, x 0..303, y 3744..4143, is unreached from anywhere. | **MEASURED** §8 p4, c2 |
| 5 | **Metropolis east** (x 7696..9247, y 2240..3839; 5% reachable) | C7 lands you on a ledge, x 7700..7959, y ~2700, walled at x 7959. 7 of 7 patterns stayed at x ≤ 7959; the only way out is back left into Chemical Plant. Isolated rooms are at (8608..9247, 3088..3327), (7696..8351, 2368..2463), (8864..9247, 2448..2495) and the whole bottom row, 7840..9247 at 3760..3839. Sonic 2's Metropolis is driven by objects (lifts, platforms). | **MEASURED** §8 p5, c2 |
| 6 | **Shaft C9, mtz_to_ooz** (x 7712..7807, y 3840..4303) | Dead at both ends. Its top mouth is the floor of a sealed passage under C7's arrival slope. Its lowest ledge (4240) is 416 px above Oil Ocean's ground under the lane (4656). A flood from its own ledges reaches no other connector. | **MEASURED** §8 c2 |
| 7 | **The Chemical Plant pocket** (C6 to C7) | Not a run-through: a player on the middle track is stopped 262 px in by the plane-A back of a loop. The merged-plane flood cannot see this. The route-fix flight in §2 stops at exactly that x (4870 = 4608 + 262). | **READ** `docs/DEFERRED_WORK.md:38947`; **MEASURED** §8 p6 |
| 8 | Small isolated ledges | CPZ: 14 components of 16 to 48 spots, e.g. (6272..6751, 2384..2399), (5904..6127, 2544..2655). OOZ: 4 small ones, e.g. (5104..5343, 4912..4943). MTZ west: (4320..4639, 2576..2623) and (4448..4687, 2352..2399), above the pit. | **MEASURED** §8 c2 |

Oil Ocean (93%) and Hidden Palace east (86%) are well connected *once you are in them*. The
problem is getting there.

### 1.4 What connects each one on the generated side

**What the manifest allows today** (**READ** `tools/clip_manifest.py` header):
- **Clips.** Any number of rectangles, several per zone. Same-zone clips may touch (R10 forbids
  only overlap; `hpz_west`/`hpz_east` already butt).
- **Corridors.** Flat, one floor row, joining exactly two clips (K7). Each end must be flush or
  bridgeable by one ramp block, on both planes (K6, `clip_manifest.py:1714`). At least the Z2
  crossing length (`clip_rom_bake.py:1336`).
- **Shafts.** A vertical lane between one clip above and one below (K7), with both mouths open
  across the lane (K10). Optional ledges at a pitch under the jump reach (K9), **inside the
  shaft only**.
- **Also:** fill, `path_lines` (K11) and the start.

**What it does not allow:**
- a connector inside a clip (R10);
- ledges below a shaft's mouth, in the clip's own air;
- a tunnel whose two ends are at different heights;
- objects.

**How edits are made.** The manifest is written by
`docs/research/2026-09-27-mega-act-woven/build_woven_act.py` ("re-run it, never hand-edit this
file", **READ** manifest `note`), so placement edits are constants in that builder. Aurora can
only *append* clips today; it has no move, resize or delete (**READ**
`docs/research/2026-09-28-woven-editable.md` §0).

| # | Generated-side change | Allowed today? | Cost | Measured? |
|---|---|---|---|---|
| 1+2 | **Route fix**: end MTZ west at donor x 1024, drop C5 to EHZ's floor 960, move the non-WFZ act down 320 px, hold Oil Ocean, delete dead C9 | Yes: builder constants | **S** builder, **M** with re-verification | **Yes, §2** |
| 3 | Make Wing Fortress reachable from below | No clip-list change can: the lower zones' ground is 400+ px under their top edges, and the only ledges allowed live in the shaft. Needs springs (S2CLIP-OBJECTS, booked by name at `DEFERRED_WORK.md:37213`), a new "stair into the clip below" connector (new tooling), or a frozen hand-drawn ledge | **L** (objects) / **M-L** (new connector type) / freeze | No (INFERRED from row 3's gaps) |
| 4 | Connect HPZ west's route to HPZ east | A taller or re-cut `hpz_east` that includes HPZ's rows at donor y ~876..1040 where the west route exits. The collision budget is the wall: 250 of 255, and earlier recuts measured 259 (manifest note item 6). C4 back up needs springs, as row 3 | **M**, likely refused on collision | No |
| 5 | Metropolis east | Trim it to what is reachable (a small ledge), or pick a different MTZ window. Most of it is object content | **S** to trim / needs objects | No |
| 6 | C9 | Delete it (it is dead). Done inside the route fix | **S** | Yes (§2) |
| 7 | CPZ pocket | Already booked: another tunnel row pair, an authored layer line, or objects | as booked | READ |

**What re-verifies any of these:**
- **The bake's own refusals**, printed on every bake: K6/K10 seams, Z1/Z2 crossing lengths and
  the region plan, N1/N2 camera windows at 12 x 64-tile pages, and collision attr entries against
  the cap of 255.
- **Headless runs:**
  - `crossing_witness.py --corridor` on every connector touched;
  - `woven_route_witness.py --route ...`, whose route list changes when C9 goes;
  - `clip_reachability.py check`.
- **A walk from the start.** The fix has to be *walked*, and today nothing walks from the
  start: `escape_probe.py start` is the instrument that saw it. Promoting that to a witness
  would be new tooling, **S**.
- **Two re-derived generated files:**
  - `collision_baseline.json`, via `build_woven_act.py --baseline` (its entries are placed in
    act pixels, **READ** `build_woven_act.py` `baseline()` docstring, so any move stales it);
  - `anchors.toml`, via `clip_anchors.py --derive` after building both shapes, whenever the
    packed data crosses a bank boundary (§4).

---

## 2. The route fix, measured

The builder change is `docs/research/2026-09-28-woven-touchups/route_fix_builder.patch`
(knobs on `build_woven_act.py`, which is unchanged in the tree). The variant used:
`MTW_W=1024 OOZ_DX=496 DROP_C9=1 EHZ_FLOOR=960 MTZ_WEST_FLOOR=256 DROP_D=320`.

**How it was found** (**MEASURED**, §8 b3, b4):
- MTZ west ends at donor x 1024, where its walkway row (640) ends before the pit (the donor's
  plane-A rows, `woven.py` tree dump). C6 then starts at the walkway's end.
- Oil Ocean had to be held in place, because C9's lane only fits one coincidence of open spans.
  Moving Oil Ocean refused at K10 (C9 capped) or moved the Hidden Palace window and capped C4.
  C9 is dead anyway, so it was deleted.
- EHZ's C5 row. The flood and the probes show the player reaches EHZ's east edge only on its
  lowest ground (donor y 960). The builder's K6-accepted pairs were baked:

  | EHZ floor : MTZ floor | drop 0 | drop 160 | drop 320 |
  |---|---|---|---|
  | 576 : 256 (today's) | bakes (but row 1 of §1.3 still applies) | | |
  | 736 : 256 | bakes; **real runs still never enter C5** (§8 p7) | | |
  | 736 : 672, 736 : 384 | Z2 / region plan refuse | | |
  | 960 : 672 | region plan refuses | refuses | refuses |
  | 960 : 384 | C1 too short (Z2) | bakes; real runs need a jump at MTZ's edge (route witness COULD NOT RUN, stopped at x 3158) | bakes |
  | 960 : 256 | Z1 (660 centres show two zones) | C1 too short (Z2) | **bakes; chosen** |

**The chosen variant** (**MEASURED**, §8 b5, w3, p6):

| Check | Today | Route fix |
|---|---|---|
| Bake | rc 0 | rc 0 |
| Collision attr entries | 250 / 255 | 250 / 255 |
| Pool | 2,894 tiles, 49 pages | 2,846 tiles, 48 pages |
| Worst camera window | 12 of 12 (673 windows at 12) | 12 of 12 |
| SCREEN mixed / wrong / void | 0 / 0 / 0 over 419,120 centres | 0 / 0 / 0 over 412,676 |
| `clip_reachability` | OK | OK |
| crossing_witness C5, C6 | (landing record) | 0 glitch ticks, worst slack 1 frame each |
| woven_route_witness `ehz_to_mtz,mtz_to_cpz,cpz_to_mtz,cpz_to_ooz` | GREEN (with C9) | **GREEN** |
| **From the start, hold right + jump every 40 frames** | ends (2550, 2815), EHZ's east wall | **reaches x 4873, 262 px into Chemical Plant** (through C5, MTZ west, C6) |
| Anchors | fresh | **STALE**: packed end grew past the bank rule, re-derive both shapes and commit |

**What moves for the owner to see** (**MEASURED** builder print):
- the act is 8,752 x 6,464 px, from 9,248 x 6,144;
- C1 is 448, C2 1,152, C3 832 and C4 944 (the drops get longer);
- Chemical Plant, Metropolis east and Oil Ocean shift;
- Metropolis west loses its pit and the columns east of it (donor x 1024..1519);
- the start moves with Emerald Hill.

**Still not fixed by it:** rows 3, 4, 5 and 7 of §1.3.

---

## 3. Wish B: part of a tunnel replaced by a rectangle of the zone's own map

**How a tunnel is represented** (**READ** manifest `corridors`, `build_woven_act.py:179`
`tunnel()`):
- a `dst_rect` (608..416 px wide, 512 tall, or cut to the zone's bottom);
- a `floor_y`;
- a `tunnel` with `ceiling_y` 96 px above the floor and wall/back art from CPZ.

**Why the length is fixed.** The length is the Z2 crossing (`clip_rom_bake.py:1299-1360`):
- each side needs half a screen (160) plus 16 px times the frames the switch into that side
  takes;
- the blobs are A {EHZ, HPZ, WFZ} 302 tiles (9 frames), M {CPZ, MTZ} (9) and O {OOZ} (6); a
  switch inside a blob costs 3 frames.

The bake prints each crossing's need and what it has (**MEASURED**, §8 b1):

| Connector | Length | Need (before / after) | Slack |
|---|---|---|---|
| C5 ehz_to_mtz | 608 | 304 / 304 | **0** |
| C6, C7 (MTZ / CPZ) | 416 | 208 / 208 | **0** |
| C11 hpz_to_ooz | 560 | 304 / 256 | **0** |
| C1 wfz_to_ehz (shaft) | 512 | 160 / 160 | 192 |
| C2 wfz_to_mtz (shaft) | 832 | 256 / 256 | 320 |
| C4 ehz_to_hpz (shaft) | 560 | 160 / 160 | 240 |

**Every horizontal tunnel is at its minimum.** The owner's rectangle therefore cannot shorten
one. It can only **push the far side along** by its own width.

### 3.1 Tried literally: a shorter tunnel is refused every time

**MEASURED** (§8 b2): 26 scratch bakes, each a rectangle of the neighbouring zone's own map,
256 px tall (the tunnel's floor ±128), with the tunnel shortened by its width. Every one was
refused:

| Tunnel, rectangle from | Widths | Refusal |
|---|---|---|
| C5, EHZ past donor x 8704 | 16..192 (11 widths) | **K6 every time.** 16..48 and 96..112: EHZ's planes disagree on the floor row (plane B has no floor there, "heights 16 and 0"); 64..80 and 144..192: ground above the floor row |
| C6, CPZ west of donor 7040 / MTZ west past 1520 | 64, 128, 192 | K6 (ground above floor, or ground off the floor row) |
| C7, CPZ past donor 9216 | 64 / 128 / 192 | **Z2** (208 / 208 needed) / Z1 (72 centres show two zones) / K6 |
| C7, MTZ east west of donor 1520 | 64 / 128, 192 | **Z2** / K6 |
| C11, OOZ west of donor 8192 | 64, 128 / 192 | **Z2** (304 / 256 needed) / K6 |

### 3.2 The priced example: 128 px more Oil Ocean at C11, the far side moved

**MEASURED** (§8 b3, w1, w2). The scratch `variant.py hpz_to_ooz east 128 4688 256 1`:
- The new clip is OOZ donor (8064, 384, 128 x 256) at act (5104, 4688), the tunnel's floor
  ±128. The owner's "little rectangle": fill stays above and below it.
- C11 keeps its 560 px (x 4544..5103).
- Every clip and connector at x ≥ 5104 moves +128: Chemical Plant, Metropolis east, Oil Ocean,
  and C3, C7, C8, C9. **C6 grows from 416 to 544**, because its east end moved and its west end
  did not.

| Check | Result |
|---|---|
| Bake | rc 0 |
| Collision attr entries | 250 / 255 (**+0**) |
| Pool | 2,894 tiles in 49 pages (**+0**: OOZ's 128 columns reuse tiles already in the pool) |
| Worst camera window | 12 of 12 |
| SCREEN | 0 / 0 / 0 over 419,888 centres |
| crossing_witness `hpz_to_ooz` | 0 glitch ticks, worst slack 1 frame |
| crossing_witness `mtz_to_cpz` (now 544) | 0 glitch ticks, worst slack 6 frames |
| woven_route_witness (4 legs) | **GREEN** |
| clip_anchors | **STALE**: packed end 0xE3676 → 0xE51FA (+7,044 B), bank rule 0xF8000 → 0x100000 |

Cheaper-looking widths on C7 (64 px, either side, with the far side moved) also bake: 250 / 255,
12 / 12, SCREEN 0. At 128, C9's lane leaves Oil Ocean's open span (K10 capped at x 7920), or
MTZ's edge row fails K6.

**Cost per rectangle: S.** It is two constants in the builder, one re-run, and the re-checks
listed in §1.4.

### 3.3 The constraints that bite, in the order they fire

- **K6, the seam at the rectangle's outer edge.** The new edge must be flush with the tunnel's
  floor, or one ramp block off, **on both planes**, with nothing above the floor row. Sonic 2's
  ground rarely continues flat on both planes just past where a clip was cut. That is why the
  cut points are where they are. This refused most widths tried.
- **Z2, the crossing length.** It fixes the tunnel length, so the far side moves. The cascade is
  then the real cost: another tunnel grows, or a shaft lane leaves the open span below it (C9,
  K10), or a zone crossing drifts too close to another (the region plan's REGION_MIN_SPAN,
  which refused the original 960/672 pair).
- **Z1 (screen separation).** Refused one C7 variant.
- **Camera-window page budget: 12 of 12 with no slack** at camera (4648, 2352), beside C6
  (**MEASURED** N1). Anything that adds *new* tiles in view of that window refuses. All the
  variants above added none.
- **Collision attr entries: 250 of 255.** 5 spare. OOZ, CPZ, MTZ rectangles cost 0 here. A new
  zone window, or a taller HPZ, has measured 259.
- **Section grid.** The act is 5 x 4 sections of 2,048. Widening by a rectangle is free while
  the right edge stays under 10,240 (today 9,248). The fill row under the lowest clip must stay
  (FLOOR_BELOW).
- **Background arena, 376 tiles** (blobs 302 / 314 / 117, **READ** manifest note item 1). A
  rectangle of a zone already in the act adds no background tiles (INFERRED: backgrounds are
  per zone).
- **ROM bank placement** (§4). Almost any layout move re-packs all 20 sections.

---

## 4. The bank budget, measured

`anchors.toml` pins the clip's sound banks with
`dac_banks = align_up(packed_end + 0xC000 + 0x8000, 0x8000)` (**READ**
`games/sonic4/data/clips/s2_woven/anchors.toml`, `tools/bganim_room.py:248-266`). Its measured
packed ends are 0xE3676 (DEBUG) and 0xE2BBE (plain), both against 0xF8000.

**Headroom before the anchor moves by a bank** (**INFERRED**, arithmetic on those numbers):
- **2,442 B** in the DEBUG shape;
- **5,186 B** in the plain shape.

Both variants that moved content crossed it:
- the Oil Ocean example added 7,044 B (**MEASURED**);
- the route fix went STALE the same way (**MEASURED**).

This is not a refusal. It is a ritual:
1. build both S2CLIP shapes;
2. run `tools/clip_anchors.py --derive --clip s2_woven`;
3. commit `anchors.toml`.

The ROM grows by one 32-KB bank (**S**).

---

## 5. The freeze: does either wish need it?

**No.** The freeze (WOVEN-EDITABLE, `docs/decisions.jsonl` line 202) exists so that **cells
can differ from Sonic 2's own layout**: a tile repainted, or a collision block added, removed or
reshaped. That also means "collision matches Sonic 2" stops being guaranteed for those cells
(the card's own costs text).

**What does NOT need it** (both wishes as he described them):
- moving, resizing, splitting, adding or deleting clip rectangles of **Sonic 2's own map**;
  wish B is literally "some more of the map";
- moving, lengthening, adding or deleting tunnels and shafts, including the ledges inside a
  shaft, the tunnel art and the fill: the manifest generates all of these;
- the route fix in §2, which is every one of the above.

**What WOULD need it:**
- a ledge, step or bridge drawn inside a zone piece. The obvious cases:
  - a stair at C1/C2's foot so Wing Fortress can be climbed into;
  - a bridge over Metropolis west's pit instead of cutting it off;
  - a floor joining Hidden Palace west's route to its east strip;
  - steps back up out of Hidden Palace under C4;
- removing a Sonic 2 wall;
- repainting any tile.

**Did he describe any of that?** Not directly. His wish A is "connect them". Some connections
(rows 3, 4, 5 of §1.3) cannot be made by moving Sonic 2 pieces, so for those the choice is
**objects** (springs and platforms, S2CLIP-OBJECTS: no freeze, Sonic 2's own solution),
**the freeze** (draw the ledge yourself), or **leave them decorative**. That choice is his, and
it is the only place the freeze enters.

---

## 6. The hub's reading, tested

- **(A)** "some clip pieces don't connect to the neighbouring tunnels or pieces":
  **confirmed, and wider.** The first tunnel itself is not reachable from the start, and the
  main route is placement-only (§1.2). The reading was right that the fix for the route is a
  clip-list change (§2). It would be wrong for Wing Fortress, Metropolis east and the way back
  up from Hidden Palace, which need objects or the freeze.
- **(B)** "replace part of a tunnel with an extra small rectangle of that zone's real Sonic 2
  layout": **confirmed as a clip-list change with no freeze. Corrected on one point:** the
  tunnel does not get shorter. The rectangle pushes the far side along, and something else pays
  (§3).

---

## 7. The question for the owner

**"Can you fly to the pieces you couldn't reach and the tunnel you want to trim, and tell me
which of these they are (or read me the x, y if none)?"**

**Pieces:**
- **P1.** Wing Fortress, the whole top: around (4600, 700).
- **P2.** Emerald Hill's high east ground and the first tunnel's mouth: (2400, 2460).
- **P3.** Metropolis west past the pit: (4640, 2860). The walkway ends at x 4190.
- **P4.** Metropolis east past the ledge you arrive on: (8600, 3200).
- **P5.** Hidden Palace west's east end, where the big slope meets rock: (2480, 4400).
- **P6.** Somewhere else.

**Tunnels:**
- **T1.** Emerald Hill to Metropolis: x 2560..3167, floor 2496.
- **T2.** Metropolis to Chemical Plant: x 4688..5103, floor 2880.
- **T3.** Chemical Plant to Metropolis: x 7280..7695, floor 2880.
- **T4.** Hidden Palace to Oil Ocean: x 4544..5103, floor 4880.
- **Also:** is it the flat tunnels you mean, or the tall shafts too? The shafts are the only
  connectors with spare length: C1 192 px, C2 320 px, C4 240 px.

---

## 8. Commands and results

All from the worktree root. Build env:
`SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil`,
`SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob`.

**Setup.** Donor trees and `tools/bin/salvador` were copied in from the main checkout
(gitignored). `build_woven_act.py --out <scratch>` reproduces the committed manifest byte for
byte (`cmp` IDENTICAL).

**Bakes:**
- **b1.** `python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_woven/clips.json --allow-dirty --keep`
  printed:
  - rc 0, real 25 s;
  - Z2 lines per connector (the table in §3);
  - collision 250 / 255;
  - N1 worst window 12 of 12 at camera (4648, 2352), 673 windows at 12;
  - 2,894 pool tiles, 49 pages;
  - SCREEN 0 / 0 / 0 over 419,120.
- **b2.** 26 shortened-tunnel variants: `variant.py base.json <manifest> <corridor> <side> <E> <y0> 256 0`,
  then the bake. Refusals are in the table in §3.1.
- **b3.** Moved-far-side variants: `variant.py ... 1`.
  - `hpz_to_ooz east` 64 and 128: rc 0.
  - `cpz_to_mtz west 64` and `east 64`: rc 0.
  - `cpz_to_mtz west 128`: K10 on C9. `east 128`: K6.
  - Each rc-0 variant: collision 250, window 12, SCREEN 0/0/0, 2,894 tiles / 49 pages.
- **b4.** Route-fix sweep: the builder with `route_fix_builder.patch`. The outcomes are the table
  in §2.
- **b5.** The chosen variant was re-baked, then `clip_reachability.py check` gave OK.

**Flood:**
- **c1.** `python3 tools/clip_reachability.py check games/sonic4/data/clips/s2_woven/clips.json`:
  OK, planes A and B reachable.
- **c2.** `GRAPH=<out>.npy python3 docs/research/2026-09-28-woven-touchups/woven_flood.py games/sonic4/data/clips/s2_woven/clips.json`
  on the b1 bake. It printed §1.2's table, the connector graph, the isolated components and
  the shaft climb gaps.
- **c3.** `PATHTO=2480,2480 ... woven_flood.py ...`: the 7-move path, with the leap
  (992, 2544) to (1376, 2448).

**Real ROM** (`FAST=1 DEBUG=1 S2CLIP=s2_woven ./build.sh`, crc `d48933a5`, 1,195,134 B;
`escape_probe.py <rom> <lst> <manifest> <name> <x> <y> <frames> [patterns]`):
- **p1.** `start`, 1,500 frames, 7 patterns: max x 2550; y range 2242..2930; none past x 2560.
- **p2.** `plateau_sweep.py`, 150 runs: "plateau hits: 0". The highest point east of x 1344 was
  y 2581.
- **p3.** `mtzw_walkway 3700 2850`, 7 patterns: x 3177..4678. The rightward patterns end at
  the pit's bottom (y 4223..4271). The leftward ones stop at x 3177..3178.
- **p4.** `hpzw_c4_landing 832 4290`, 7 patterns: min y 4398, max x 2470.
- **p5.** `mtze_c7_ledge 7900 2690`, 7 patterns: max x 7959.
- `hpze_route 3500 4850`: spin-left reached (2521, 5389). This is the model's blind spot (§1.1).
- **p6.** Route-fix ROM (crc `a8d083b0`), `start`, right+jump: x 324..4873, end (4870, 3248).
  Right-run and spin-right fall into EHZ's pit at (2230, 2861). **The fix needs a jump over
  EHZ's own pit, as Sonic 2 does.**
- **p7.** The 736 : 256 variant ROM (crc `9703d31e`), `start`, 4 patterns: max x 2550.

**Witnesses:**
- **w1, w2.** Oil Ocean variant ROM (crc `95675ed9`):
  - `crossing_witness.py --corridor hpz_to_ooz` and `--corridor mtz_to_cpz`: both rc 0, 0 glitch
    ticks, worst slack 1 and 6 frames;
  - `woven_route_witness.py --route ehz_to_mtz,mtz_to_cpz,cpz_to_mtz,mtz_to_ooz`: VERDICT GREEN;
  - the build's `clip_anchors` lane reported STALE (the numbers are in §3.2).
- **w3.** Route-fix ROM (crc `a8d083b0`):
  - `crossing_witness` on `ehz_to_mtz` and `mtz_to_cpz`: 0 glitch ticks, worst slack 1 frame each;
  - `woven_route_witness --route ehz_to_mtz,mtz_to_cpz,cpz_to_mtz,cpz_to_ooz`: VERDICT GREEN.
- The 960 : 384 drop-160 ROM (crc `16140762`):
  - route witness COULD NOT RUN: the run stopped at x 3158 before MTZ's edge;
  - `crossing_witness ehz_to_mtz`: "never landed at x=3192; COULD NOT RUN".

**Restore.** After every scratch bake:
`git checkout -- games/sonic4/data/generated/ojz/act1 games/sonic4/data/collision games/sonic4/data/clips/s2_woven/clips.json && git clean -fdq -- games/sonic4/data/generated/ojz/act1`.
Scratch builder copies were deleted. The worktree's variant ROMs were deleted.
