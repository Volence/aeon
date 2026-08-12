# Knuckles C4 — glide/slide/climb/ledge research (Tasks 10-11)

Banked 2026-08-12, after task 9 landed (`a4626d94` + sigil chain 102). Two
independent research legs, one per task, both grounded in skdisasm and in the
live tree. **Read this before writing a line of `player_glide.emp` or
`player_climb.emp`** — between them they found one blocking mechanism gap and
about a dozen places the plan's Task 10/11 text is wrong or under-specified.

The plan (`plans/2026-08-08-character-dispatch-v2.md`) has been annotated with
pointers back here; this file is the detail.

**One source could not be reached:** `info.sonicretro.org` returns HTTP 403 to
the fetch tooling, so the Sonic Physics Guide's Knuckles pages are unread and no
SPG cross-check was possible. Everything below is from the disassembly, which is
the stronger source. If SPG ever becomes reachable, the numbers worth
re-checking are the glide accel/turn pair and the slide friction.

Line references are `skdisasm/sonic3k.asm` unless stated. Tree references are
this worktree at `a4626d94`.

---

## 0. THE BLOCKING FINDING — the ability box does not compose with the hooks

Both legs found this independently, from opposite ends. It is the single thing
most likely to produce a subtly broken Knuckles, and it must be settled BEFORE
the glide is coded.

Glide, slide and climb all run at **10 x 10** radii (`:32566-32569`) — a third
collision box, alongside standing and ball. Our box machinery only knows two:

- `PHook_EnsureStanding` (`player_common.emp:1014`) restores the standing box
  **only when the current box equals `cd_roll_wh`**. Coming from a 21x21 ability
  box the `cmp.w` misses and it takes `.keep` — **the standing box is never
  restored, and Knuckles keeps a 21x21 hitbox for the rest of the act.** This
  fires on every glide-detach and every climb-detach into an air state.
- `PHook_EnsureBall` (`player_common.emp:1027`) does the opposite: from the
  ability box it sets the ball box *and* applies the full stand-to-ball
  `curl_y_shift`, a drop S3K's wall jump-off does not have (`:31430-31431`
  writes the radii and never touches `y_pos`). This fires on the climb jump-off.

The plan's Task 10 Step 1 hand-waves this as "add a `set_ability_size`-style
splice". A splice alone does not fix it — the *guards* are what is wrong.

### The fix (recommended, and it is what S3K actually computes)

1. **A third box in the record.** Append to `CharacterDef` AFTER `cd_palette`,
   at `$24` (the note at `engine/structs.emp:222` requires `$00-$1E` stay
   byte-stable; `cd_palette` already took `$20`):
   ```
   cd_ability_wh: u16,   // $24 — the ability-state box (glide/slide/climb),
                         //       W<<8|H full dims. 0 = no ability box.
   ```
   Knuckles gets `((10*2+1) << 8) | (10*2+1)` off a named
   `KNUX_ABILITY_RADIUS = 10`; Sonic and Tails get 0. **Do not reach for
   `PUSH_RADIUS`** (`engine/system/constants.emp:132`) — it is also 10 and it is
   a different fact.

2. **`set_ability_size`**, the exact peer of the two splices at
   `player_common.emp:254-266`.

3. **`PHook_EnsureAbility`**, the exact peer of the two Ensure hooks: `bclr
   ST_ROLLING` (glide is attacking but NOT curled), compare the box word against
   `cd_ability_wh`, set it if different, **no y shift** — S3K applies none on
   glide entry (`:32565-32572`). Idempotent, so glide-to-slide is a no-op on the
   box exactly as S3K leaves it.

4. **Generalise `PHook_EnsureStanding`'s guard** from "am I the ball box" to "am
   I not the standing box", with the y shift computed from the *current* height
   rather than the fixed curl pair:
   ```
   cmp.w  CharacterDef.cd_stand_wh(a1), d1
   beq    .keep
   ...    shift = (cd_stand_h - current_h) >> 1
   ```
   This is literally S3K's `y_radius - default_y_radius` (`:32834`, `:30978`),
   and it **reproduces the existing two-box case exactly**: ball to standing is
   `(39-29)>>1 = 5`, ability to standing is `(39-21)>>1 = 9` — and 9 is the
   number S3K's slide get-up uses (`:30978-30986`). So the generalisation is not
   a new behaviour, it is the closed form of the one we already have.

   **Sonic and Tails come out behaviour-identical** (same shift, same paths);
   only the instruction encoding moves, so this is ROM-changing but
   RAM-identical and the replay fixtures should hold. Gate it that way.

   **The debug-fly 16-height box is safe** — verified, not assumed:
   `Player_DebugExit` calls `set_standing_size` explicitly
   (`player_common.emp:1229`) before any hook runs, so the generalised guard
   never meets the 16 box. The current comment "not curled (incl. debug 16)"
   describes a path that no longer reaches it.

5. Task 11 needs the same generalisation on `PHook_EnsureBall` (the climb
   jump-off goes ability box to ball box).

This is a shared-player-code change with its own gate, and it is a prerequisite
for BOTH tasks. Land it as the opening step of Task 10, WITH its first consumer
(a `cd_ability_wh` that nothing reads would be exactly the dormant scaffold the
house style forbids).

---

## 1. Task 10 — glide + slide

### 1.1 The S3K constants

| # | Rule | Value | S3K | Plan agrees? |
|---|---|---|---|---|
| 1 | Entry: `y_vel >= -$400` (release cap) | `-$400` | :32515-32522 | **missing.** It is `PBLK_RELEASE_CAP(a4)` here — `Ability_TailsFlight` (player_fly.emp:315-317) already implements exactly this gate; copy it |
| 2 | Entry: uncurl + radii 10/10, **no y correction** | `$A` | :32565-32567 | yes |
| 3 | `y_vel += $200`, clamp >= 0 | `$200` | :32570-32572 | yes |
| 4 | `gsp = $400`; `x_vel = ±$400` by facing; glide angle `0`/`$80`; `angle = 0` | `$400` | :32576-32586 | yes (the `angle = 0` is unstated but needed) |
| 5 | Accel **+8/frame** while `gsp < $400` | `8` | :31607-31612 | yes |
| 6 | Accel **+4/frame** while `$400 <= gsp < $1800` | `4` | :31618-31627 | yes |
| 7 | Accel suppressed while turning — **the +4 branch only** | — | :31622-31624 | ambiguous in the plan; the +8 branch has NO turn gate |
| 8 | Speed cap | `$1800` | :31618 | yes |
| 9 | Turn step | `+2/frame` | :31650-31674 | yes (64 frames for a half turn) |
| 10 | **The turn CONTINUES with no direction held** | — | :31670-31674 | **missing, and it changes the feel.** Releasing L/R mid-turn does not stop the turn; it completes to the next rest position |
| 11 | Reversal mid-turn = `neg.b` the angle, then `+2` | — | :31645-31666 | missing. The mirror preserves `cos` (facing) while flipping rotation — it is the whole trick |
| 12 | `x_vel = cos(glide_angle) * gsp >> 8` | — | :31679-31683 | yes — see 1.2 |
| 13 | Parachute: `y_vel -= $20` when `y_vel >= $80`, else `+= $20` | `$20`, terminal `$80` | :31687-31695 | yes |
| 14 | Level top: `y_pos < $10` → **halve** `x_vel` and `gsp` (`asr`) | `$10` | :31700-31709 | missing. Our camera minimum is a structural 0, the same reduction `player_fly.emp:66-69` already documents |
| 15 | Per-frame order: move-with-NO-gravity, gravity lives in the parachute term BEFORE the move | — | :30679-30683, :36091 | missing. This is `PState_Fly`'s ordering, NOT `PState_Air`'s, and the difference is a frame of lag on every glide |
| 16 | Release → fall sub-state, `x_vel` **asr twice (/4)**, radii restored | `/4` | :30712-30733 | yes |
| 17 | Fall-from-glide: normal air control, then `y_vel += $38` | `$38` | :30900-30903 | missing (== our `PHYS_GRAVITY`) |
| 18 | **Fall-from-glide landing is a DEAD STOP** — `gsp = x_vel = y_vel = 0` | — | :30918-30933 | **missing, and it is not a normal landing** (no `gsp = x_vel` conversion) |
| 19 | Land with quadrant `(angle+$20)&$C0 != 0` → normal land, `x_vel = gsp` | — | :30747-30755 | yes in spirit; it is the QUADRANT test, not a slope band |
| 20 | Land flat → SLIDE, radii stay 10x10 | — | :30758-30762 | yes |
| 21 | Slide friction `$20`/frame on `x_vel`, sign crossing → get-up | `$20` | :30959-30970 | yes |
| 22 | Slide button-release → **full get-up**, not just a velocity zero | `move_lock $F` | :30951-30993 | **plan says "zeroes x_vel". It does far more** — it IS the get-up |
| 23 | Slide get-up y-correction **-9** | `-9` | :30978-30986 | missing; without it Knuckles sinks 9 px. Falls out free from §0 step 4 |
| 24 | Slide ledge-drop: floor dist `>= 14` → fall | `14` | :31005-31034 | yes |
| 25 | Slide floor follow: `y_pos += d1`, `angle = d3` every frame | — | :31013-31014 | missing; required |
| 26 | Slide **SFX** cadence | **8 frames** | :31017-31022 | — |
| 27 | Slide **DUST** cadence | **4 frames** | :34102-34104 | **THE PLAN IS WRONG.** Task 10 Step 3 says "dust cadence 8". 8 is the SFX cadence; the dust is 4, identical to skid dust and to our own `DUST_CADENCE_RELOAD = 3` |
| 28 | Slide dust Y offset | `+6` px (skid is `+$10`) | :34086-34122 | our `Dust_Tick` derives `y_radius - 3`; with the ability box `y_radius` is 10, so use rise 4 to hit 6 exactly |
| 29 | Glide pose from the TURN TABLE `$C0 $C1 $C2 $C3 $C4 $C3 $C2 $C1`, index `(angle+$10)>>5`; index 4 flips facing and uses `$C0` | — | :31564-31596 | **missing. Facing is derived from the glide angle every frame**, not from `x_vel` — otherwise `Air_XInput` fights it |

Two S3K details that are **dead code — do not port them**: the fall-landing
y-correction (`:30922-30930`, always 0 because every path in already restored
the radii) and, for Task 11, the `Knuckles_Gliding_HitWall` "adds the Y radius to
the X coordinate" bug that S3K's own comment calls harmless (`:30835-30837`).

### 1.2 The multiply — `muls.w`, with the established pragma

There is **no fixed-point multiply helper in the tree** (`engine/system/math.emp`
has only `GetSineCosine` and `GetArcTan`). `CODING_CONVENTIONS.md:247` bans
per-frame `mulu`/`muls`, but there is an established, documented exception and
glide is the same shape as it:

```
player_ground.emp:630-641   (Ground_Move_Cap .project_slope)
        move.w  d0, d2
        moveq   #0, d0
        move.b  angle(a0), d0 as Angle
        jbsr    GetSineCosine
        muls.w  d2, d1                  // lint: disable=E002
        asr.l   #8, d1
        move.w  d1, x_vel(a0)
```

**Use that idiom verbatim**, with the `lint: disable=E002` pragma and a
justification comment: cos and gsp are both full-range variables, so no
shift-add decomposition exists (the conventions' technique table only covers
*constant* fractions); one player, one product per glide frame; and S3K spends
literally the same `muls.w`/`asr.l #8` (`:31681-31682`), so matching it is the
only way to be bit-exact. Rejected alternatives worth recording: a 2-D
`cos x gsp` table (kilobytes of ROM for one state) and a CORDIC shift-add
rotation (more cycles AND it drifts from S3K's rounding).

Glide needs only the **cos** output (`d1`); S3K discards sin. One `muls`.

`GetSineCosine` (`engine/system/math.emp:21`) is
`(d0: Angle) clobbers() out(d0,d1: fixed<8,8>)` — it **clobbers nothing else**,
which is what lets `.project_slope` keep a speed in `d2` across it.

`GetArcTan` is **not** needed: `Air_Collide` already does the equivalent
quadrant classification with a signed `|x_vel|` vs `|y_vel|` compare and
documents the equivalence (`player_air.emp:299-307`).

### 1.3 A third state, not a sub-state

The plan creates PSTATE_GLIDE + PSTATE_SLIDE and calls the fall a "fall
sub-state". S3K's `Knuckles_Fall_From_Glide` (`:30899-30947`) is a genuinely
different body: normal gravity `$38` *after* the move, normal air control, and a
landing that zeroes all three velocities instead of converting `x_vel` to `gsp`.
It cannot be `PSTATE_AIR` and it does not share glide's per-frame shape. Every
other S3K `double_jump_flag` value is promoted to a PSTATE by this plan; 2 should
be too.

**Recommended numbering** (`config/constants.emp:108-119`, `PSTATE_FLY = 14`,
`PSTATE_COUNT = 8` today):

```
PSTATE_GLIDE     = 16
PSTATE_GLIDEFALL = 18
PSTATE_SLIDE     = 20
PSTATE_COUNT     = 11
```
leaving Task 11 `PSTATE_CLIMB = 22`, `PSTATE_LEDGE = 24`, `PSTATE_COUNT = 13`.

All even, all `< COUNT*2`, coverage sum `(1<<COUNT)-1` — `pstate_values_ok()`
(`constants.emp:130`) passes. Registration is four coordinated edits plus the
value list; the three `.count == PSTATE_COUNT` ensures (`player_common.emp:852`,
`:893`, `:913`) catch a forgotten row, and the value list itself catches a
forgotten name.

### 1.4 The unscoped piece: glide's own terrain pass

`Air_Collide` **tail-jumps into `Player_SetState`** on landing
(`player_air.emp:578-579`, `:600-601`), so glide cannot call it and then inspect
the outcome — the state would already be GROUND/ROLL with a normal `gsp = x_vel`
conversion, which is precisely what glide must not do. S3K has a dedicated
`Knux_DoLevelCollision_CheckRet` (`:32629`) that reports into
`Gliding_collision_flags` instead of transitioning.

Glide needs the same: a glide-owned collide built from `Player_SensorFloor` /
`Air_WallProbeRight` / `Air_WallProbeLeft` that returns a flags byte. **This is
the largest single piece of work in Task 10 and the plan does not mention it in
any of its four steps.**

### 1.5 Animations and sound

**None of the glide/slide poses exist.** `ANIM_COUNT = 13`
(`constants.emp:179`), and `knuckles_anims.emp:39-44` says so explicitly.
S3K's poses: glide is a direct `mapping_frame` write from the 8-entry turn table
(`$C0..$C4`), glide-fall is `AniKnuckles21` (`$CA $CB`), slide is a direct `$CC`,
slide get-up `AniKnuckles22` (`$CD`), glide-land get-up `AniKnuckles23` (`$9C`).

Our `AnimateSprite` owns `mapping_frame` and `Player_Animate` re-classifies every
frame, so the direct-write trick does not carry over. Suggested id set — 9 new,
`ANIM_COUNT 13 -> 22`, with `ANIM_GLIDE_0..4` contiguous so the classifier can
`add.b idx` and an `ensure` pinning the span. Sonic's and Tails' tables each need
9 fallback rows or their `.count == ANIM_COUNT` ensures fail — the precedent is
the `Fly`/`FlyTired` fallbacks at `knuckles_anims.emp:121-124`.

`Player_Animate` gains a glide/slide branch beside the FLY branch
(`player_common.emp:684-698`) — without it glide is airborne-and-uncurled and
falls through to `.walk_or_run`. That branch is also where **facing** is set from
the turn index (§1.1 row 29).

**SFX: none of the three ids exist.** S3K uses `sfx_GlideLand $4C`,
`sfx_GroundSlide $7E`, `sfx_Grab $4A`; our bank has 11 blobs and none of them are
these. Either scope a sound-side parcel (bank entry + priority ladder row) or
ship glide/slide silent — the plan is silent about being silent.

### 1.6 PlayerV budget

`PlayerV` is **20 bytes of 30 usable** (`$30..$43`), 10 free (`$44..$4D`). The
header comment at `player_common.emp:78` says "22 of 30" and is **stale** — fix
it in whichever task gets there first. (Task 12 Step 1 already lists a different
stale figure, "18 of 34"; that text no longer exists but this one does.)

Glide needs one byte, `glide_angle` (S3K's `double_jump_property`, `:31677`).
Slide needs **nothing new** — friction runs on `Sst.x_vel`, `move_lock` exists,
the dust cadence rides `PBLK_DUSTTIMER` in the player block, the SFX cadence
rides `Frame_Counter+1`.

The replay-hash contract on these bytes is the one already written at
`player_common.emp:104-122`: address-free AND Sonic-unreachable, seeded at the
ability entry, **never cleared at init** (a clear is a write).

---

## 2. Task 11 — climb + ledge

### 2.1 The headline: our sensor layer already expresses every S3K query

Task 11 Step 1 is described in the plan as "the hard part — map S3K's wall
detection onto OUR sensor layer". **It is done, and the answer is that no
extension is needed.** `player_sensors.emp` supports fully arbitrary probe
points (X and Y, not just Y) at two levels:

- `Player_SensorWallDir` (`:438`) — `a0` for the layer, `d0/d1` = the probe
  point, `d2` = direction 0/1/2/3 (down/up/right/left). Class is **pinned to
  `SOLID_LRB`** for all four arms, which is exactly S3K's `lrb_solid_bit`.
- The four `pub` probe cores `Collision_Probe{Down,Up,Right,Left}` (`:235-244`)
  — arbitrary point, caller-chosen class in `d6`.

Only the `Player_Sensor{Floor,Ceiling,Surface}` family hardcodes the player's
centre, and climb never uses it.

**Distance semantics:** positive = gap; negative = embedded that many px; `+32`
with `d1=d2=0` = the "nothing found" sentinel. Same sign convention as S3K's
`FindWall`/`FindFloor`. **`d3` (layer) is clobbered by every call** and must be
reloaded before each probe; `d6` survives.

### 2.2 The equivalence table

Radii during climb are 10 x 10, so the box word is `$1515`.

| S3K query | S3K | Ours | Probe point | Mapping |
|---|---|---|---|---|
| `GetDistanceFromWall` — wall distance in the facing direction | :31518-31532 | `Player_SensorWallDir`, `d2 = 2` (right) / `3` (left) | right: `(x+10, probeY)`; left: `(x-10-1, probeY)` — **keep the `-1`**, it is S3K's asymmetry and it is what makes the flush test land at `== 0` on the left | 1:1, our `d0.w` IS S3K's `d1`. Ignore the angle |
| ...at `y-11`, climbing UP | :31076-31083 | as above | `probeY = y_pos - 11` | `>= 4` → ledge; `== 0` → keep climbing; **1..3 or negative → freeze in place, do NOT detach** |
| ...at `y+11`, climbing DOWN | :31224-31230 | as above | `probeY = y_pos + 11` | `!= 0` → **detach.** Note the asymmetry with the up case — it is deliberate and it is why climbing up a bumpy wall feels different from climbing down one |
| ceiling probe | :31091-31105 | `Collision_ProbeUp` direct, `d6 = SOLID_LRB` | `(x, y-18)` | `< 0` → embedded: `sub.w d0` pushes DOWN, skip the move. `>= 0` → `y_pos -= 1` |
| floor probe | :31235-31246 | `Collision_ProbeDown` direct, `d6 = SOLID_TOP` | `(x, y+19)` — write it as `PLAYER_Y_RADIUS`, not as `9 + KNUX_ABILITY_RADIUS` | `< 0` → **landed**: `y_pos += d0`, zero the three velocities, `PSTATE_GROUND` |
| glide wall-catch pair | :30781-30800 | **two direct `Collision_ProbeRight`/`Left` calls** — see the gap below | `(x±10, y-10)` and `(x±10, y+10)` | both `== 0` → catch |
| glide catch fallback, the 12 px floor window | :30836-30858 | `Collision_ProbeDown` direct, `d6 = SOLID_TOP` | `(x±11, y-11)` | `0 <= d0 < 12` → `y_pos += d0`, catch |

### 2.3 The one real gap, and the cheap correct answer

`Player_SensorPair` (`:255`) keeps the **nearer** hit. S3K's glide catch needs
"both flush", i.e. the **max** must be 0. With min-only, gliding into a wall
*corner* (one sensor flush, one in open air) reads as flush and skips the 12 px
ledge-lip branch entirely.

**Recommended: call the cores twice.** The file already states this is the right
idiom for point probes — `Player_AtLedgeEdge` at `player_sensors.emp:549-553`
says so in as many words. Two `Collision_ProbeRight` calls with `d6` held across
them and `d3` reloaded before each IS S3K's two `FindWall`s, and it is cheaper
than the pair wrapper.

Recorded alternative if a named pair is ever wanted: in `Player_SensorPair`,
replace `move.w d5, d0` with `exg d0, d5` — same two bytes, and `d5` then carries
the loser's distance on both paths. `d5` is already in the clobber set and the
one existing caller does not read it after `.pair`, so it is behaviour-identical.
Still a byte-changing parcel.

**Non-gaps, stated so nobody invents an extension:** arbitrary probe Y (and X) is
supported; floor-class at an arbitrary point is `Collision_ProbeDown` +
`SOLID_TOP` (do **not** use `Player_SensorWallDir` with `d2 = 0` — it pins
`SOLID_LRB` and would reject jump-through platforms as floors); layer select is
free via `d3 = layer(a0)`.

### 2.4 Climb behaviour, corrected against the plan

Three detach conditions, not two: latch-X drift (`:31046-31048`),
**`ST_ON_OBJECT`** (`:31052-31053`, **omitted by the plan**), and wall-loss —
which fires **only on the climb-DOWN path**.

Other plan corrections:
- "wall distance >= 4 at head sensor" — there is no head sensor. Same
  `GetDistanceFromWall` at `y-11`, which is mid-body (the head at the 10x10 box
  is `y-10`).
- "floor within ~19px below → land" misreads the probe: `y+19` is the probe
  ORIGIN; the landing test is `dist < 0`.
- "top camera clamp" is a **level-top** clamp — structurally `y_pos >= 16` here,
  the same reduction `player_fly.emp:66-69` documents. Calling it a camera clamp
  invites someone to reach for `Camera_Y`.
- The 12 px window belongs to the glide wall-CATCH and is the **fallback**
  branch, not an extra gate on every catch.
- Climb writes `y_pos` directly at 1px/frame — no `ObjectMove`, no gravity.
- Jump-off: `y_vel = -$380`, `x_vel = $400`, `bchg ST_XFLIP`, negate if the OLD
  bit was clear, so it always launches AWAY from the wall.
- Animation pacing: 1 frame every 4, cycling `$B7..$BC`, **backward** when
  climbing down.
- S3K's `Disable_wall_grab` (`:30777`, `:31039`) has no counterpart here — some
  walls are meant to be non-grabbable. Register the object-side hook in
  DEFERRED_WORK rather than losing it silently.
- skdisasm gates a real fix behind `FixBugs` (`:31355-31379`, Knuckles snapping
  to his first climb frame when idle). Our structure gets the fixed behaviour for
  free; **say so**, the way `player_fly.emp:211-228` does for the ceiling bug.

### 2.5 The clamber script — S3K's actual bytes

```
; mapping_frame, dx, dy, duration
dc.b  $BD,   3,   -3,   6
dc.b  $BE,   8,  -10,   6
dc.b  $BF,  -8,  -12,   6
dc.b  $D2,   8,   -5,   6
```
`dx` negates when facing left; `dy` never does (reverse gravity is N/A). Cursor
steps 0/4/8/12/16. **Step 0 runs at ENTRY**, not on the first LEDGE frame
(`:31447-31448`), so the state is ~18 frames, not 24. The finish subtracts 1 from
`x_pos` when facing left (`:31551-31553`) — that 1px asymmetry is inherited from
`GetDistanceFromWall`'s left-branch `subq.w #1`; keep it and comment it. S3K's
own comment notes frame `$D2` is never actually seen.

### 2.6 Frame ids are S3K's ordinals verbatim

`characters_staging/README.md` records 251 frames converted in order, and
`knuckles_anims.emp` already uses raw S3K frame bytes directly. So the clamber
frames are `$BD $BE $BF $D2`, the climb cycle is `$B7..$BC`, the catch pose is
`$B7` and the let-go pose is `$CB` — 1:1, no lookup table, **do not author a
`KnuxFrame_*` indirection.**

Getting them on screen (the mechanism the plan does not mention): add
`ANIM_CLIMB` / `ANIM_LEDGE` as 1-frame scripts so the anim-changed path lands the
right frame once; then every frame the state body writes `Sst.anim_timer = $20`
so `AnimateSprite` decrements and takes `.done` without touching
`mapping_frame` (this is S3K's `:31411` pin exactly); and any manual
`mapping_frame` write must call **`RefreshSpritePieceCount`** because the engine
caches `frame_off` and the piece count (`Player_DebugEnter` is the precedent).

### 2.7 PlayerV for climb + ledge

`knux_latch_x: i16` (world X at the catch), `knux_step: u8` (climb anim
countdown AND ledge cursor — one byte for both because the states are disjoint
and S3K's `double_jump_property` is the same byte doing the same double duty),
`knux_timer: u8` (ledge step frames; we need our own because `AnimateSprite` owns
`Sst.anim_timer`), plus a named pad. With glide's byte that is 26 of 30.

**A union with `fly_fuel`/`fly_thrust` is the design intent** (the comment at
`player_common.emp:104-110` says so) **but the language cannot express it**: every
`vars X: Sst.sst_custom` overlay in the tree starts at `$30`, none uses
offset-anchored placement, and both characters share the single `PlayerV`
overlay. Declare in place, amend that comment so the union reads as a *budget*
principle rather than a byte-sharing one, and raise it with the sigil session if
the 2 bytes ever matter.

**Floating-origin hazard, put the note AT the field:** `knux_latch_x` is a world
coordinate. When the floating-origin rebase lands it must join the shift-list, or
every rebase during a climb trips the drift guard and drops Knuckles off the
wall. Same class as the `Player_Pos_Ring` note in Task 8.

---

## 3. Sequencing

1. **The §0 box mechanism**, landed with the glide as its first consumer.
2. Glide + glide-fall + slide (§1), including §1.4's glide-owned terrain pass.
   Interim wall-contact behaviour: take S3K's own `.fail` path (`:30890-30896` —
   enter the fall, restore radii), so Task 11 replaces one branch rather than
   rewriting.
3. Climb + ledge (§2). Hard-blocked on 2: Task 11 Step 2 modifies
   `player_glide.emp`, which does not exist until then.

Every one of these is a byte-changing parcel and owes the full ritual
(`SIGIL_BLOB_LEN_DRIFT=warn`, both sigil binaries rebuilt, repin, refreeze with
emulator evidence, three gates), plus a `map.toml` `order` entry and a sigil
`ModuleSpec` with a REAL pin landed in the same change as any new module.
Growing `ANIM_COUNT` touches three data sections and their ordinal ensures.
