# CHAR-4 / CHAR-6 reproduction recipe and firsthand S3K check (2026-09-13)

Research note for the ledger rows `CHAR-4` and `CHAR-6` (`docs/lens-findings.jsonl`). This
note changes no engine code. The research agent could not use the emulator. Every runtime
number here is either **MEASURED BY THE CONTROLLER** (labelled) or **PREDICTED** from
source and level data (labelled, "controller to confirm").

## 0. Provenance

- Source read: worktree `research/char46-repro` at `96a98abd`. The ROM tree
  `/home/volence/sonic_hacks/.aeon-land-0913` is also at `96a98abd`, and its
  `git status --short` printed 0 lines, so source and ROM agree.
- ROM: `.aeon-land-0913/s4.debug.bin`, md5 `6211829d4b067b0130e4c693f6528589`. I computed
  it with md5sum and it equals the controller's. Listing: `.aeon-land-0913/s4.debug.lst`,
  sigil revision `1532b72f`, `debug=1`.
- The `.lst` carries labels only, with no instruction bytes. So every address below a
  label was decoded from the ROM bytes and is marked `(ROM-decoded)`. The rest are
  listing symbols.

## 1. Headline

1. **Neither bug is blocked.** Nothing in the glide family, or in the per-frame code around
   it, clamps or ejects a head that is inside terrain. CHAR-6 has already been reproduced
   at runtime by the controller (section 5).
2. **The lift is 9 px of the centre, but the head rises 18 px.** EnsureStanding keeps the
   feet planted while the box grows from 21 to 39 high. After the lift, the head sensor
   sits 18 rows above where the glide head sensor was. S3K grows the radius with y_pos
   unchanged, so its head rises 9 and its feet drop 9. Measured as the ceiling distance
   the glide head had before release, our exposure window is 0..17 (18 values) and S3K's
   is 0..8 (9 values). S3K also pushes the head back out on the next frame. The
   controller's "twice S3K" hypothesis is **CONFIRMED** (section 6 (ii)).
3. **There are four mid-air sites, not three.** `Climb_LetGo` (player_climb.emp) also
   enters PSTATE_GLIDEFALL straight from the 21x21 ability box and takes the same 9 px
   lift. S3K has the same fourth site, `Knuckles_LetGoOfWall`, and like the other three it
   leaves y_pos alone.
4. **"S3K lifts only on the two grounded landings" is PARTLY right.** S3K has exactly one
   glide-family lift that does anything: the slide get-up. The formula on the
   GlideFall landing always evaluates to 0. Our engine lifts on two grounded paths where
   S3K does not: the glide slope landing and Climb_ReachFloor. See section 6 (iii).
5. **Scope of CHAR-4 is wider than the glide.** S3K runs its ceiling-probing collision
   (`Knux_DoLevelCollision_CheckRet`) for the glide, the glide-fall and the slide. Ours
   runs no ceiling probe in any of them. The controller has measured the missing probe in
   GlideFall.

## 2. Getting Knuckles into the level

- `CHAR_KNUCKLES = 2` (games/sonic4/config/constants.emp, after `CHAR_SONIC = 0` and
  `CHAR_TAILS = 1`). Confirmed. `CharacterDefs[2] = CharDef_Knuckles` (characters.emp), and
  its `cd_ability` is `Ability_KnuxGlide`. The file header of knuckles.emp still says
  "his ability is not wired yet"; that sentence is stale.
- **`Character_ID`** is at `$FFFFEC4C` and is a **word** (u16). Next to it:
  `Player_Chardef` `$FFFFEC4E` (a longword cache of the resolved record) and
  `Cheat_Flags` `$FFFFEC4A`.
- **Who reads it, and when.** There are exactly three readers:
  1. `Player_Init` (`$10002`), once, at level init. It is called from
     `GameState_OJZScroll_Init` (`$BDF30`).
  2. `Debug_CharacterHotkey` (`$BE3AC`, DEBUG only), polled every frame. It acts only on
     an A press while in debug-fly.
  3. The DEBUG desync guard in `Player_Ability` (`$1231C`), on each airborne ability
     press.

  Nothing reads it per frame otherwise.

**Option A, presses only (the controller has used it).** The DEBUG boot arms
`CHEAT_DEBUG_FLY` at the top of `GameState_OJZScroll_Init`, and `Player_Init` then tail-calls
`Player_DebugEnter`, so the player boots in debug-fly.

1. Press A, release it for at least one frame, then press A again. The controller measured
   that the press latch is edge-triggered and that back-to-back presses count once.
   Afterwards `Character_ID` reads `$0002`.
2. Press **B** to leave debug-fly. `Player_DebugExit` (`$109CC`) re-runs
   `Player_InitAssets` from the new record, sets the standing box, zeroes the velocities
   and calls `Player_SetState(PSTATE_AIR)`.

The hotkey's gates: `Input_Source` (`$FFFF8036`) must be 0; no B press on the same frame;
C not held.

**Option B, breakpoint.** Break on `GameState_OJZScroll_Init` (`$0BDF30`). This is after
the boot RAM clear and before `Player_Init`. Write the word `$0002` to `$FFFFEC4C` and
resume. `Player_Init` then resolves Knuckles completely: Player_Chardef, box, art,
physics row and palette. At the same stop you may also write `Boot_At_X` (`$FFFFF008`,
word), `Boot_At_Y` (`$FFFFF00A`, word) and then `Boot_At_Flag` (`$FFFFF00C`, byte,
nonzero) to boot at a chosen point.

**Unsafe: poking `Character_ID` alone mid-level.** `Player_Chardef` keeps Sonic's record,
so nothing changes. On the first airborne jump press, the DEBUG guard in `Player_Ability`
(`assert.l d1, eq, d0`) raises. Poking both cells still leaves the physics row, palette,
art and box stale until the next `Player_DebugExit`.

## 3. Player RAM

Player_1 is at `$FFFF8FFE`. Offsets come from `engine/objects/sst.emp` (struct `Sst`) and
the `PlayerV` overlay at `Sst+$30` (player_common.emp). The ROM bytes of `Player_SetState`
(`move.b $32(a0),d1`) confirm `player_state` at +$32.

| field | address | width / format |
|---|---|---|
| x_pos | `$FFFF9000` | long, 16.16. The high word `$FFFF9000` is integer px |
| y_pos | `$FFFF9004` | long, 16.16. The high word `$FFFF9004` is integer px; +y is down |
| x_vel | `$FFFF9008` | word, signed 8.8 |
| y_vel | `$FFFF900A` | word, signed 8.8 (positive = falling) |
| width_pixels / height_pixels | `$FFFF9014` / `$FFFF9015` | bytes, FULL size 2r+1 |
| status | `$FFFF901C` | byte: bit1 facing left, bit3 IN_AIR, bit4 ROLLING, bit5 ON_OBJECT, bit6 PUSHING |
| angle / layer | `$FFFF901D` / `$FFFF902B` | bytes (layer 0 = path A) |
| ground_speed | `$FFFF902E` | word 8.8 (PlayerV+0) |
| player_state | `$FFFF9030` | byte, a PSTATE_* value (PlayerV+2, ROM-confirmed) |
| debug_flag | `$FFFF903A` | byte, nonzero = debug-fly (PlayerV+12) |
| glide_angle | `$FFFF9042` | byte: 0 = gliding right, $80 = gliding left (PlayerV+20) |

The three PlayerV offsets other than player_state were derived from the field order under
the `PLAYERV_SPEND = 29` pin. The ROM bytes now confirm all three:
- `Ability_KnuxGlide` has `317C 0400 0030` (`move.w #$400,$30(a0)`), so ground_speed is
  at +$30;
- `Ability_KnuxGlide` has `1141 0044` (`move.b d1,$44(a0)`), so glide_angle is at +$44;
- `Player_DebugExit`'s first word is `51E8 003C` (`sf $3C(a0)`), so debug_flag is at +$3C.

The release-cap gate is `B26C 000E` (`cmp.w $E(a4),d1`). The jump buffer
(`PlayerBlock.jump_buffer`, PBLK_JUMPBUF = 17, ensure-bound) for slot 0 is
`Player_Blocks` (`$FFFFEC52`) + 17 = `$FFFFEC63`. That address is derived and
not byte-checked.

**Boxes.** Every sensor uses r = size >> 1 (`lsr`) and the **integer** y_pos word. The
subpixel is dropped, so a 39-high box has r = 19, not 19.5. Cited: `Player_SensorSurface`
(`move.b height_pixels(a0),d1 / lsr.w #1,d1`, `move.w y_pos(a0),d5`), and
`Glide_Collide`'s floor probe (`lsr.w #1,d1` / `add.w y_pos(a0),d1`).

| box | bytes $16/$17 | radii used by the probes |
|---|---|---|
| standing (Knuckles = Sonic's box) | `$13/$27` (19x39) | 9 / 19 |
| glide / slide / climb ability box | `$15/$15` (21x21) | 10 / 10 |
| ball | `$0F/$1D` (15x29) | 7 / 14 |

**State values** (`player_state`, config/constants.emp):

| state | value | state | value |
|---|---|---|---|
| GROUND | 0 | FLY | $0E |
| ROLL | 2 | GLIDE | **$10** |
| SPINDASH | 4 | GLIDEFALL | **$12** |
| AIR | **6** | SLIDE | **$14** |
| JUMP | 8 | CLIMB | $16 |
| ROLLJUMP | $0A | LEDGE | $18 |
| AIRBALL | $0C | | |

All four GLIDEFALL entries compile to `moveq #$12,d0 / bra.w Player_SetState` (ROM-decoded):

| entry | address |
|---|---|
| `PState_Glide.release` | `$1143A` (two `asr.w x_vel` first, then `$11442`) |
| `Slide_Terrain.ledge_drop` | `$1166C` |
| `Knuckles_Gliding_WallCatch.fall` | `$11998` |
| `Climb_LetGo` | `$11888`, the moveq at `$11892` |

**The lift instruction** is `PHook_EnsureStanding` (`$10818`), decoded from the ROM:

```
$10818 bclr #4,$1E(a0)          ; ST_ROLLING
$1081E movea.l ($EC4E).w,a1     ; Player_Chardef
$10822 move.w $16(a0),d1        ; current box word
$10826 cmp.w $1A(a1),d1         ; cd_stand_wh
$1082A beq.s $10842             ; .keep (already standing: no lift)
$1082C moveq #0,d2
$1082E move.b $1B(a1),d2        ; stand_h = $27
$10832 sub.b d1,d2              ; - current_h
$10834 lsr.b #1,d2              ; (39-21)>>1 = 9
$10836 move.w $1A(a1),$16(a0)   ; box := standing
$1083C swap d2
$1083E sub.l d2,6(a0)           ; y_pos -= $00090000   <-- the lift
$10842 rts                      ; .keep
```

A breakpoint at `$1083E` while `player_state` (`$FFFF9030`) is `$12` isolates the
GLIDEFALL-entry lifts. At that point d2.l = `$00090000`. The hook's callers are
`PHook_AirEnter` (`$107AC`, `bsr.s` at its first word) and, through the enter-hook table,
the Air, Fly and GlideFall rows.

## 4. Glide input

- **In the DEBUG shape B is not a glide button.** `CHEAT_DEBUG_FLY` is armed, so the glide
  masks exclude B (`BUTTON_JUMP_MASK_NO_B = A|C`) and B toggles debug-fly. Use **A or C**.
- **Start.** Knuckles must be in AIR, JUMP, ROLLJUMP or AIRBALL (`PState_AirShared`), and
  a fresh A or C press (`Ctrl_1_Press`, `$FFFF8029`) must arrive while
  `PlayerBlock.jump_buffer` is nonzero. It always is on a genuine airborne press:
  `Player_Main` (`$1021A`) latches `PHYS_JUMP_BUFFER` = 2 on every press edge before the
  dispatch. The buffer is 0 only on a jump's launch frame, so the press that jumped can
  never also glide. The gate is at `PState_AirShared.press_ok` (`$10F34`).
  `Player_Ability` (`$1231C`) then calls `Ability_KnuxGlide` (`$11672`), which refuses
  while `y_vel < release_cap` (−$400).
  - From a standing jump: Knuckles' jump force is $600 and gravity $38/frame, so y_vel
    reaches −$400 about 10 frames after launch. Letting go of the button while rising cuts
    y_vel to −$400 at once, so tap, release, tap works.
  - After a warp or a B exit from fly (AIR, y_vel ≥ 0), any later press glides.
- **Entry.** `gsp = $400`; `x_vel = ±$400` by facing (status bit1); `y_vel += $200`
  (clamped ≥ 0); box 21x21 with NO y shift (`PHook_GlideEnter`). The rest of the press
  frame runs under AIR rules; the glide body starts the next frame.
- **Direction** is the facing at the press. A warp clears status, so Knuckles faces
  right. Hold LEFT or RIGHT to turn (2 units/frame, 64 frames per half turn). Hold
  nothing to go straight.
- **Hold.** Keep A or C held (`Ctrl_1_Held`, `$FFFF8028`). `PState_Glide` tests it after
  `Glide_Collide` each frame.
- **Release.** Let go of every one of A and C. On that same frame, `.release` quarters
  x_vel and calls SetState(GLIDEFALL), which runs the lift.
- **Steady glide.** y_vel settles into alternating $60/$80 (~0.44 px/frame down). gsp
  grows +4/frame from $400, so ~4.1..4.5 px/frame horizontally.

## 5. Runtime measurements (MEASURED BY THE CONTROLLER)

Same ROM, md5 `6211829d`. Knuckles was selected with the debug-fly A cycle
(`Character_ID = $0002`).

**Witness 1, release "in open air"** (frame 752 → 753):

| frame | y_pos | y_vel | x_vel | box |
|---|---|---|---|---|
| 752 (gliding) | `$020A6000` (522.375) | `$0098` | `$0434` | 21x21 |
| 753 | `$0201D800` (513.844) | `$0078` | `$010E` | 19x39 |

Δy = −8.531 = −9 + $78/256. The glide frame's own move happens first, then the 9 px lift.
The controller then reported x_pos: `$031DC800` (797.78) at frame 752 and `$03220000`
(802.0) at frame 753. Both lie outside the box's x 896..1023, so this was an open-air
release with nothing above the head. **Witness 1 is therefore a pure mechanism witness:
it shows the lift fires. Witness 2 below is the harm witness.**

**Witness 2, the brown overhang at x ≈ 880..1010:**

- **Ceiling check.** Knuckles stood at x 926.3, y 557.3 and did a full jump with A held.
  At frame 814 y_vel went from `$FB50` to 0 and y read 525.94, where free motion gave
  525.16. In engine terms: integer y 525 minus ball r 14 is 511, the last solid row.
  That is dist 0, exactly where `Air_CeilingBump` leaves a snapped head.
- **Release.** Knuckles glided under the lip at x 903..908, and A was released between
  frames 776 and 777. y went from 535.125 to 526.59 and the box from 21 to 39 high.
- **No push-out.** At frame 778, y = 527.06 and y_vel = `$00B0`: he moved by exactly the
  previous y_vel.
- **Exit timing.** Head tops as the controller computed them (y − 19.5):

  | frame | 777 | 778 | 779 | 780 | 781 | 782 | 783 |
  |---|---|---|---|---|---|---|---|
  | head top | 507.1 | 507.6 | 508.3 | 509.2 | 510.3 | 511.6 | 513.2 |

  At f783, y = `$0214B0` (532.6875) and y_vel = `$01C8`. Every frame matches free fall
  under gravity $38 exactly.

**Which half-height applies: the engine's own criterion.** The probes use integer y and
r = 19 (section 3). The ceiling sensor row is p = y_int − 19. The engine's distance is
dist = p − 511 (511 is the last solid row), and it counts as embedded only when dist < 0.
The engine's snaps fire only on `dist < 0`; 0 is "touching".

| frame | 777 | 778 | 779 | 780 | 781 | 782 | 783 |
|---|---|---|---|---|---|---|---|
| y_int | 526 | 527 | 527 | 528 | 529 | 531 | 532 |
| dist | −4 | −3 | −3 | −2 | −1 | +1 | +2 |

So the head was embedded for **5 frames (777..781)**. At f782 it is clear. The controller's
"511.1 at f782" is an arithmetic slip: 511.6 + 0.5 = 512.1, which is clear. My offline
probe reproduces −4 at the release for x 905..930, and −4 at x 903, where only the right
sensor (x+9) is under the lip (section 7).

## 6. Deliverable 2: the S3K claims, firsthand (skdisasm `sonic3k.asm`)

### (i) S3K's glide collision probes the ceiling. CONFIRMED, with two nuances.

`Knux_DoLevelCollision_CheckRet` (:32629) splits motion into four classes using
`GetArcTan(x_vel, y_vel) − $20 & $C0` (:32637-32647):

- **$C0, mostly right** (`loc_17AB0`, :32774). Right wall (:32775), then **ceiling**
  `sub_11FEE` (:32783). If embedded, `sub.w d1,y_pos(a0)` (:32791) pushes Knuckles down
  and clears upward y_vel. Otherwise the floor, but only when y_vel ≥ 0 (:32801-32802).
- **$40, mostly left** (`loc_179DA`, :32681). Left wall, then **ceiling** (:32690). A
  penetration under $14 is pushed out (`cmpi.w #$14,d1 / bhs.s loc_17A1C`,
  :32693-32695, then `add.w d1,y_pos` :32701). **Asymmetry:** a penetration of $14 or
  more is NOT pushed out. It branches to a right-wall check and returns with no floor
  check (:32710-32719). The right class has no such cut-off.
- **$80, mostly up** (`loc_17A62`, :32742). Both walls, then **ceiling** (:32759),
  pushed out (:32767).
- **$00, mostly down** (:32648-32678). Both walls and the floor, **no ceiling probe**.

`sub_11FEE` (:24143) is `Sonic_CheckCeiling` under normal gravity (:20246): a pair at
x ± x_radius, y − y_radius. The walls (`CheckRightWallDist`, :20192) probe at centre
height: `move.w y_pos(a0),d2` / `addi.w #$A,d3`. That is the same geometry as our
`Air_WallProbeRight` (x + PUSH_RADIUS, y).

Call sites: the glide (`Knuckles_Glide`, :30704), the fall (`Knuckles_Fall_From_Glide`,
:30912) and the slide (`Knuckles_Sliding`, :30997). All three probe the ceiling in three
of the four classes.

**Does a glide sit in a horizontal class? Nearly always.** Steady y_vel is $60..$80 while
|x_vel| = |cos|·gsp with gsp ≥ $400. It falls into the down class only when
|x_vel| < y_vel, which happens in two cases:
- about 5 frames around the vertical point of each turn (|cos| < 1/8);
- the first frames after an entry from a fast fall, when y_vel + $200 exceeds |x_vel|.

In both cases Knuckles is moving down, away from any ceiling. The fall after a
straight-glide release is also horizontal on its first frame: x_vel $434/4 = $10D against
y_vel $78+$38 = $B0.

### (ii) At the mid-air restore sites S3K leaves y_pos alone. CONFIRMED, at four sites.

| site | radius restore | y_pos written? |
|---|---|---|
| glide release | :30730-30731 `move.b default_y_radius(a0),y_radius(a0) / move.b default_x_radius(a0),x_radius(a0)` | no |
| wall-catch `.fail` | :30893-30894 (same two instructions) | no |
| slide ledge-drop `.fail` | :31031-31032 (same) | no |
| `Knuckles_LetGoOfWall` | :31461-31462 (same) | no (the fourth site; ours is `Climb_LetGo`) |

**The controller's hypothesis is CONFIRMED.** On restore, S3K's radius goes 10 → 19 about
a fixed centre: the head (y − y_radius) rises 9 and the feet (y + y_radius) drop 9. Ours
keeps the feet and raises the head 18. The measured exposure window, as the ceiling
distance the glide head had before release, is **0..17 for us against 0..8 for S3K**:
exactly twice.

Two more differences:
- **S3K ejects on the next frame.** The fall runs `Knux_DoLevelCollision_CheckRet`, and in
  the horizontal and up classes its ceiling probe pushes a 1..9 px embed back out. We run
  nothing.
- **S3K's feet can land below a floor.** No collision runs later in the same frame: the
  restore follows the collision pass in `Knuckles_Glide`, and follows `sub_11FD6` in
  `Knuckles_Sliding`. So for one frame the feet can sit up to 9 px inside a floor that was
  within 9 px under the glide feet. On the next frame, `Knuckles_Fall_From_Glide` →
  `Knux_DoLevelCollision_CheckRet` takes its floor branch (`sub_11FD6` → `Sonic_CheckFloor`,
  a pair at y + y_radius, :19843). That branch gives `add.w d1,y_pos(a0)` (a snap up) and
  `bclr #Status_InAir`, and the fall then dead-stops (:30918-30920).
  - In the horizontal classes that floor branch needs y_vel ≥ 0 (:32723-32724,
    :32801-32802). The fall's y_vel is always ≥ 0, because gravity is added before the
    collision (:30903) and the glide never rises.
  - For the ledge-drop, the feet drop into air by definition (floor distance ≥ 14).

In short, S3K's 9 px floor exposure is corrected next frame. We trade it for 9 more pixels
of ceiling exposure, which nothing corrects.

### (iii) S3K lifts y_pos only on the two grounded landings. PARTLY right.

- **Slide get-up: a real 9 px lift.** :30978-30986 `move.b y_radius(a0),d0 /
  sub.b default_y_radius(a0),d0 / ext.w d0 / ... / add.w d0,y_pos(a0)`, which is
  10 − 19 = −9 (9 px up). Ours matches: `.get_up` → GROUND → EnsureStanding.
- **GlideFall landing: the same formula, but it is always 0.** :30922-30930. All four
  entries to `double_jump_flag = 2` (:30718, :30891, :31028, :31454) restored default
  radii first, so y_radius − default_y_radius is 0. Ours matches: the dead stop reaches
  EnsureStanding with the box already standing, so it takes `.keep`.
- **Other grounded Knuckles restores in S3K have no lift.**
  - The glide slope landing (`Knux_Gliding_HitFloor` → `Knux_TouchFloor`, :32833-32838):
    radii are restored, and y is adjusted only under `Status_Roll`, which the glide entry
    cleared (:32565).
  - Climb reaching the floor (`.reachedFloor`, :31244-31253 → `Knux_TouchFloor`).

  **Ours lifts 9 on both.** The glide `.hit_floor` non-flat branch goes → GROUND →
  EnsureStanding, and so does `Climb_ReachFloor`. In S3K the feet sit 9 px in the floor
  until the next grounded floor snap, so the end state matches one frame later. This is a
  timing divergence on the grounded path, outside CHAR-6. It is worth knowing because the
  ledger says the grounded path "is correct and must stay".
- **Ledge finish.** Ours pre-sets the standing box (`PState_Ledge`), so there is no lift,
  consistent with S3K.

## 7. The place: OJZ act 1, section 0, the "brown overhang"

**Collision exists only in section 0.** Plane A (`section_N.collattr.bin`) is all air in
sections 1..8, so world coordinates equal section-0 local coordinates.

**The reader is faithful to the shipped tables.** The offline reader (appendix A) bakes the
editor words through `collision_pipeline.bake_plane_cell` against
`data/collision/base`, the same way `apply_editor_collision_overlay` does. All 35 baked
non-air (heights, solidity) tuples are present in the shipped
`data/collision/heightmaps.bin` + `solidity.bin`.

ASCII map, plane A, 16 px cells (`#` = LRB-solid present, `=` = top-only, `.` = air). The
ruler `|` marks every 128 px from x = 0, so the box's left wall sits at column 56
(x = 896):

```
       |       |       |       |       |       |       |       |       |       |       |
  240  ........................................................................................
  256  ........................................................########........########........
  272  ........................................................#......#........#......#........
  320  ........................................................#......#....#####......#........
  368  ........................................................#########......#########........
  384  ........................................................#########...####................
  400  ........................................................#......#....####................
  432  ........................................................#......#..##....................
  448  ........................................................#......####.....................
  480  ........................................................#......####.....................
  496  ........................................................##########=.....................
  512  .................................................................##.....................
  528  ..................................................................##....................
  544  .............................#======..==####......................==....................
  560  .............................=..........====####...................=====................
  576  .............................=..............============================================
  592  ==============================..........................................................
```

**Geometry of the box.** It is hollow, x 896..1023, y 256..511. Its walls are the full
height at x 896..911 and x 1008..1023, and it has a cross-member at y 368..399. The bottom
is a **16 px slab**, y 496..511, spanning x 896..1055. Open air lies below it and to its
left.

**The collision cells under it are flat.**
- Section 0, plane A, collision row 31 (y 496..511), cells col 112..127 (x 896..1023):
  every one is word `$30FF`. That is shape `$0FF`, all 16 heights = 16 (a full block),
  no flip, solidity 3 (TOP|LRB).
- The last solid row is **511** at every x from 896 to 1023, i.e. flat. In the controller's
  terms the underside is at 512. At x 912..1007 the solid run is 16 px thick; at the two
  walls it runs 256 px up.
- Right corner: col 128 (x 1024..1031) is word `$3481`, shape `$081` x-flipped, hanging
  heights −5/−11/−15 at x 1024..1026. So the last solid row is 500 at x 1024, 510 at 1026,
  and 511 at 1028..1039.
- From x 1040 the underside **descends diagonally**: row 32 is full at col 130, so the last
  solid row is 527 at x 1040. It continues down-right to about (1100, 580).

**No objects can interfere.** None of the 8 entries in `section_0.objects.json` lies within
x 600..1400, y 300..720.

**Caveat: the thin slab.** At x 912..1007, a lift large enough to carry the head sensor
past the 16 px slab (glide y ≤ 523) puts the sensor in the hollow above the slab. The
ceiling probe then reads +32 ("clear") while the box straddles the slab. Use the bands
below, which keep the sensor inside the slab.

### CHAR-4 (a): the head enters the slab while gliding. PREDICTED, controller to confirm.

**Geometry.** Glide RIGHT with integer centre y in **512..520**. When x reaches **886**, the
head pair (x ± 10, y − 10) enters the slab: ceiling dist = y − 521, so −9..−1. On the same
frame the right wall probe at (896, y) reads +32 (it is below the slab) and the centre floor
probe reads +32. So nothing in `Glide_Collide` notices.

**Recipe:**
1. Get Knuckles gliding right in the open air left of the box. For example, warp with
   `Warp_Req_X` (`$FFFFF002`) = `$02F8` (760), `Warp_Req_Y` (`$FFFFF004`) = `$01E0` (480),
   and `Warp_Req_Flag` (`$FFFFF006`) = 1, written in that order. Wait for the flag to read
   0, then press and hold A.
   - The warp (`Debug_Warp_Consume`, `$BE480`) zeroes the velocities, clears status (facing
     right), enters AIR with the standing box, places the player verbatim and reseeds
     streaming.
   - The glide then drops about 20 px while the parachute settles.
2. Pause when the integer x_pos is in 850..870. Write y_pos (long `$FFFF9004`) =
   `$02020000` (514.0). Resume with A still held.

**Predicted trajectory** (offline sim: gsp $400, straight glide, the exact probe_core
emulation):

| x | y | ceiling dist |
|---|---|---|
| 884 | 516.A | +32 (clear) |
| **888** | 517.0 | **−4** |
| 896 | 517.E | −4 |
| 905 | 518.C | −3 |
| 913 | 519.A | −2 |
| 921 | 520.8 | −1 |
| 926 | 521.0 | 0 (touching) |

So about 8 frames embedded, with the wall and floor probes at +32 throughout.

**A second, natural instance.** At the descending corner the head enters the diagonal
underside at x ≈ 1032..1046, y ≈ 531..533 (ceiling −6, −6, −5, −21). That lasts 4 frames,
before the right wall probe fires at x ≈ 1051 and the wall-catch path takes over. This is
the "rising overhang" shape the ledger describes.

A leftward twin exists: glide LEFT at y 496..504 from x ≥ 1180. The head enters the
diagonal at x 1073 (ceiling −9..−1).

### CHAR-6 (b): the release puts the head in the slab

**Discriminating band.** Glide right under the slab at integer y **530..537**, then release
A with x in **905..1014**, so both standing head sensors (x ± 9) are under the flat
underside. Offline, at x = 960:

| glide y | glide head dist | ours after the lift (y − 9, box 19x39) | S3K model (same y, box 19x39) |
|---|---|---|---|
| 530 | +9 | −9 | 0 |
| 533 | +12 | −6 | +3 |
| 537 | +16 | −2 | +7 |

In this band our head is embedded while S3K's is clear. The controller's natural run
(y 535 → 526 at x 903..908, dist −4; S3K model +5) sits in this band and is measured.

**Deterministic variant.** While gliding right under the slab, pause when x_pos is in
925..960. Write y_pos = `$02140000` (532.0), then release A on the next frame.

| frame | ours y | ours dist | S3K model dist |
|---|---|---|---|
| release | 523 | −7 | +2 |
| fall 1 | 524 | −6 | |
| fall 2 | 525 | −5 | |
| fall 3 | 526 | −4 | |
| fall 4 | 527 | −3 | |
| fall 5 | 528 | −2 | |
| fall 6 | 530 | 0 | |

So 6 frames embedded (the release frame plus five). PREDICTED; controller to confirm.

## 8. The discriminating measurement, and what each hypothesis forbids

**Embedded, by the engine's own criterion.** The ceiling sensor pair sits at
(x_int ± (width >> 1), y_int − (height >> 1)). Its dist is p − u, where u is the last
solid LRB row (511 for this slab). The engine treats dist < 0 as embedded;
`Air_CeilingBump` and the mostly-up class snap only then. For this slab:

- standing box: embedded if and only if y_int ≤ 529;
- glide box: embedded if and only if y_int ≤ 520.

**The integrator check.** This shows whether ANY code corrected the position:

- **GLIDE frames.** `Glide_Move` writes y_vel before `ObjectMove`, so
  Δy_pos (long) = y_vel_end × 256 exactly. The one exception is a floor landing, where
  y_vel reads 0 and the state leaves $10.
- **GLIDEFALL frames.** `ObjectMove` runs before gravity, so
  Δy_pos = y_vel_prev_end × 256, and y_vel_end = y_vel_prev_end + $38 (capped at
  PHYS_FALL_CAP).
- **Release frame.** Δy_pos = y_vel_end × 256 − `$00090000`; box `$15/$15` → `$13/$27`.
  The controller's `−$88800` = `−$90000 + $7800` matches.

**CHAR-4 forbids:**
- a GLIDE frame with the head dist < 0 and Δy_pos ≠ y_vel × 256 (that would be an
  ejection);
- the glide ending at the x = 886 entry for y 512..520 (a wall, floor or state change
  there means some probe saw the slab);
- a downward y correction over the embedded run.

**CHAR-6 forbids:**
- a release Δy that is not −9 px + y_vel;
- a lift that is skipped or reduced when a ceiling is near (that would reveal a clearance
  check);
- a GLIDEFALL frame, while embedded, where Δy_pos ≠ the previous y_vel × 256.

The controller's frames 777..783 violate none of these.

**Could the bugs fail to happen? Checked; no.** Every per-frame path in GLIDE and GLIDEFALL
that writes y_pos:

- `Glide_Move`. Its level-top cut halves only x_vel and gsp, at y < $10.
- `ObjectMove`.
- `Glide_Collide`'s floor snap: +dist only when the feet are embedded and y_vel ≥ 0.
- The hooks via `Player_SetState`: the lift itself.

After the dispatch, `Player_Main` runs `Player_LevelBound` (`$108E4`; I did not read it,
and it clamps to act edges far from this site) and object touch. No object is nearby.
Nothing else writes y.

## 9. What else runs while the head is embedded (the controller's question)

**In GLIDEFALL (`PState_GlideFall`, `$1159A`).** Only `Glide_Collide` (`$11530`) probes:
- walls at (x ∓ 10, y_int) (`Air_WallProbeLeft` / `Air_WallProbeRight`);
- the centre floor at (x, y_int + 19), only while y_vel ≥ 0.

After the lift the centre line is always below a flat underside. Proof: the glide head was
clear, so p ≥ u. The new sensor is p − 18, so the new centre is (p − 18) + 19 ≥ u + 1.
The wall probes therefore cannot see a flat ceiling. The feet are planted, so the floor
probe is unaffected.

- **A sloped or stepped ceiling** whose face lies within 10 px of the centre line CAN
  register as a wall. That snaps x out, zeroes x_vel and sets `GLF_PUSH`, which
  `PState_GlideFall` ignores; the result is only a horizontal stop.
- **The slide** (`Slide_Terrain`) has the same wall probes at the slide centre and the
  quadrant-rotated floor pair. It has no ceiling probe either.

**If he lands while still embedded.** This needs a floor within the remaining embed depth
below: the short-drop cases of the ledge-drop or a failed wall catch. The ceiling-reading
code in other states then sees the embedded head:

- `PState_Ground` (player_ground.emp, jump gate) calls `Player_SensorCeiling` and jumps
  only if dist ≥ `PHYS_JUMP_HEADROOM` (6). **While embedded, every jump press is refused.**
  The jump buffer retries for its 2 frames. `PState_Roll` has the same gate, and its
  unroll guard compares against `curl_head_rise`.
- `Air_Collide` (`$10F6A`), in AIR, JUMP, ROLLJUMP or AIRBALL:
  - the horizontal classes run `Air_CeilingBump`, which snaps DOWN by −dist. This is the
    only code that would eject the head, and it never runs in the glide family;
  - the mostly-up class snaps and then either bumps or **re-attaches to the ceiling** as
    GROUND when the ceiling angle is steep (`.reattach`);
  - `Air_LandState` has the curled-landing headroom guard.

## Appendix A: how the level numbers were produced (reproducible)

The reader is a Python module that imports `tools/collision_pipeline.py` from this tree.

**Cell lookup** (mirrors `Collision_GetType` and `apply_editor_collision_overlay`):
- Section = (x >> 11, y >> 11) on the 3x3 grid.
- The editor word for world (x, y) in section 0 is
  `collattr[((y >> 4) * 2) * 256 + (x >> 3)]`, big-endian. A 16 px collision row samples
  the top tile row; columns are 8 px.
- Bake: shape = word & $3FF and solidity = (word >> 12) & 3. Solidity 0 or shape 0 is
  air. Heights come from `base/heightmaps.bin[shape*16 : +16]`, then `flip_profile_x` if
  bit 10 is set, then `flip_profile_y` if bit 11 is set. The height column is x & 15.

**Probe cores** (mirrors `probe_core` in player_sensors.emp):
- `.cell`: a class-masked solidity gate; the height is negated for Up and Right; a hanging
  run returns 16 when sub + h < 0, else 0.
- Empty primary cell: one cell forward, dist = 32 − (h + sub), or 32 when nothing is found.
- Full primary cell: one cell back, dist = −(h_back + sub).
- Partial primary cell: dist = 16 − (h + sub).
- sub = (axis & 15) ^ (15 if the direction is Up or Left). HeightMapsRot =
  `collision_pipeline.rotate_profile`.

**Sensors used:**
- glide walls: (x ± 10, y), LRB;
- glide floor: (x, y + (h >> 1)), TOP;
- ceiling pair: (x ± (w >> 1), y − (h >> 1)), LRB.
