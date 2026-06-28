# Player Physics in the Classics — S2 / S3K / sonic_hack

Research for §5 (player/character system). Documents BEHAVIOR and VALUES only — no code is
to be ported. All values are 8.8 fixed point (1.0 = $100 = 1 px/frame) unless noted.
Angles are 256-unit bytes ($100 = 360°, $40 = 90°); 0 = flat floor, angle increases as the
floor tilts (right wall ≈ $C0 quadrant, ceiling ≈ $80, left wall ≈ $40 per the quadrant
dispatch below).

Sources:
- **S2** — `/home/volence/sonic_hacks/s2disasm/s2.asm` (Obj01)
- **S3K** — `/home/volence/sonic_hacks/skdisasm/sonic3k.asm` (Obj_Sonic; Obj_Sonic2P at
  21420 is the competition-mode clone that kept several S2 behaviors — cited where relevant)
- **hack** — `/home/volence/sonic_hacks/sonic_hack/code/objects/Sonic.asm`,
  `Player_Common.asm`, `S4.constants.asm`

---

## 1. Ground movement core

### Constants (working-stat RAM, swapped wholesale per state)

| State | top_speed | acceleration | deceleration | Evidence |
|---|---|---|---|---|
| Normal | $600 | $C | $80 | s2.asm:35862, 35990–35992 |
| Underwater | $300 | $6 | $40 | s2.asm:36063–36065 |
| Speed shoes | $C00 | $18 | $80 | s2.asm:25747 (monitor), hack Speeds_Shoes Player_Common.asm:598 |
| Super | $A00 | $30 | $100 | s2.asm:35995–35997 |
| Super underwater | $500 | $18 | $80 | s2.asm:36068–36070 |
| Knuckles (S3K) | same $600/$C/$80; only jump differs | | | sonic3k.asm:32458 |

sonic_hack centralizes these as data rows selected by status flags (`ChooseSpeeds`,
Player_Common.asm:548–603), adding rows stock S2 lacks: `Speeds_ShoesW` $A00/$14/$60
(shoes+water), `Speeds_SuperTails` $800/$18/$C0, and water variants for Super. **Worth
keeping: the table+selector design** — stock S2 re-writes the three RAM words inline at
every transition point and notoriously misses combinations (shoes underwater).

S3K passes physics through **a4 = pointer to Max_speed/Acceleration/Deceleration RAM**
(sonic3k.asm:22433–22435); sonic_hack copies this convention (a4/a3 controller/a5 camera
bias, Sonic.asm:82–84, Player_Common.asm:4–10).

### Per-frame pipeline order

Mode dispatch: `status & (in_air|rolling)` → 4 handlers (S2 s2.asm:35914–35918, table
35946–35950; identical in S3K 22032 and hack Sonic.asm:85–119).

**S2 ground (Obj01_MdNormal, s2.asm:36145–36157):**
1. `Sonic_CheckSpindash` → 2. `Sonic_Jump` (can early-exit the whole frame via `addq.l #4,sp`,
s2.asm:37033) → 3. `Sonic_SlopeResist` (slope factor) → 4. `Sonic_Move` (input accel/decel/
friction, then project inertia → x_vel/y_vel, then ground wall check) → 5. `Sonic_Roll`
(roll start check) → 6. `Sonic_LevelBound` → 7. `ObjectMove` (position += velocity) →
8. `AnglePos` (floor sensors, angle update, snap-to-floor) → 9. `Sonic_SlopeRepel` (slip/
detach check).

**S2 air (Obj01_MdAir/MdJump, s2.asm:36163–36210):** `Sonic_JumpHeight` (release cap) →
`Sonic_ChgJumpDir` (air accel + drag) → `Sonic_LevelBound` → `ObjectMoveAndFall` (gravity)
→ underwater gravity adjust → `Sonic_JumpAngle` (angle → 0) → `Sonic_DoLevelCollision`.

**S2 roll (Obj01_MdRoll, s2.asm:36180–36191):** `Sonic_Jump` (unless pinball) →
`Sonic_RollRepel` (rolling slope factor) → `Sonic_RollSpeed` → `Sonic_LevelBound` →
`ObjectMove` → `AnglePos` → `Sonic_SlopeRepel`.

**S3K ground (Sonic_MdNormal, sonic3k.asm:22297–22307):** identical order
(Spindash → Jump → SlopeResist → Move → Roll → LevelBound → MoveSprite_TestGravity2 →
AnglePos → SlopeRepel), plus a reverse-gravity angle-mirroring wrapper around AnglePos
(`Call_Player_AnglePos`, 22333–22348) and an extra background-collision wall push-out
(22307–22315). **Order is unchanged S2→S3K**; the key consequence for a fresh engine:
slope factor is applied to inertia BEFORE input accel, and the angle used all frame is
LAST frame's angle — angle updates only at step 8.

### Acceleration / top speed handling

- Accel adds $C/frame toward held direction; on crossing top speed the frame's accel is
  *backed out* and only clamped if speed was below top before: S2 s2.asm:36610–36616
  (`add d5 / cmp d6 / blt / sub d5 / cmp d6 / bge / move d6,d0`). **Result: ground speed
  above top (downhill, spindash) is preserved while holding forward.** Same in S3K
  (22871–22877) and hack (Sonic.asm:718–724). (S1 lacked the back-out and hard-clamped.)
- Friction (no L/R held): subtract `acceleration` toward 0, clamp at 0
  (Obj01_UpdateSpeedOnGround, s2.asm:36447–36470). Friction value == acceleration ($C).
  Super Sonic forces friction d5=$C even though super accel is $30 (s2.asm:36443–36445;
  S3K 22678–22680) — friction intentionally does NOT scale with super accel.
- Deceleration (held direction opposes motion): subtract $80/frame; on crossing zero,
  speed is set to ∓$80 in the new direction ("turnaround kick", s2.asm:36563–36565,
  36624–36626). Same in S3K (22820–22822) and hack.
- After input: `x_vel = cos(angle)*inertia >> 8`, `y_vel = sin(angle)*inertia >> 8`
  (Obj01_Traction, s2.asm:36474–36482). Inertia (ground speed) is the single scalar source
  of truth on the ground.
- Ground wall check (end of Move/RollSpeed): probes ahead at `angle ± $40` (sign from
  inertia); on hit, velocity along the blocked axis is cancelled, inertia zeroed, pushing
  bit set (s2.asm:36486–36530). S3K adds two refinements (sonic3k.asm:22716–22776):
  skip the probe when angle isn't a multiple of $40 and is in the upper half (prevents
  false wall hits on steep curved terrain), and only set the pushing bit when facing the
  wall.

---

## 2. Slope physics

### Walking slope factor — Sonic_SlopeResist (s2.asm:37360–37384)

`inertia += ($20 * sin(angle)) >> 8` per frame. Applied only when `angle+$60 < $C0`
unsigned — i.e. skipped in the ceiling band (angle $60–$9F); applies on floor and both
wall quadrants.

**The standing-still exception:** S2 skips the factor entirely when `inertia == 0`
(s2.asm:37369–37370) — Sonic can stand on any walkable slope without sliding.
**S3K change** (Player_SlopeResist, sonic3k.asm:23825–23861): when `ground_vel == 0` the
factor is applied anyway **if |$20·sin| ≥ $D** (loc_11DDC, 23852–23860) — standing on
slopes steeper than ≈ asin($D/$20) ≈ 24° now starts a slide. Community consensus: the S3K
version is the better feel (prevents standing glued to steep walls) and is what SPG
documents as the "modern" rule.

### Rolling slope factor — Sonic_RollRepel (s2.asm:37393–37423)

Base factor $50·sin(angle)>>8, same ceiling-band skip. **Asymmetry:** if the factor's sign
opposes inertia (rolling uphill) it is quartered (`asr.l #2`) → effective **downhill $50,
uphill $14** (s2.asm:37402–37419). Identical in S3K (23871–23900) and hack
(Player_Common.asm:106–133). Walking $20 sits between the two.

### Landing: air velocity → ground speed (S2 Sonic_DoLevelCollision, s2.asm:37540–37733)

First the **movement direction quadrant** is taken from `CalcAngle(x_vel,y_vel)`, rotated
by −$20 and masked $C0 (s2.asm:37547–37557): four cases — moving down (default), left
($40), up ($80), right ($C0). Moving-down case after floor hit (37570–37613):

- Floor landing is *gated*: only land if the floor angle/eligibility check vs
  `-(y_vel.high + 8)` passes (37573–37579) — prevents snagging walls as floors at speed.
- Convert by **ground angle band** (d3 = floor angle):
  - `(d3+$20)&$40 == 0` and `(d3+$10)&$20 == 0` (within ±$0F of flat): `y_vel = 0`,
    `inertia = x_vel` (37596–37599).
  - `(d3+$10)&$20 != 0` (slope band ±$10–$1F): `y_vel >>= 1` (asr), `inertia = ±y_vel`
    with sign from the angle's sign bit (37592–37593, 37608–37612).
  - `(d3+$20)&$40 != 0` (steep band ±$20–$3F): `x_vel = 0`, y_vel capped at $FC0,
    `inertia = ±y_vel` (37602–37612).
- Moving mostly **horizontally** (HitLeftWall/HitRightWall paths) a floor hit always uses
  `inertia = x_vel` regardless of slope (Sonic_HitFloor, 37641–37654), and a wall hit sets
  `inertia = y_vel` (37618–37625) so wall-running engages.

This is **axis-select, not vector projection** — and, verified against real code, **S3K is
the same algorithm**, not a projection: SonicKnux_DoLevelCollision (sonic3k.asm:24039–24124)
has byte-identical band logic (24091–24121). The "S3K projects the velocity vector" claim
is FALSE for S3K; true vector projection (`gsp = xsp·cos + ysp·sin`) only appears in fan
engines/Mania-likes. The emergent SPG rule "use x_vel if moving mostly horizontally" comes
from the movement-direction quadrant dispatch, not from comparing magnitudes.

S3K's actual landing refinements: per-character radii restore via `default_y_radius`
with angle-aware y_pos fixup (Player_TouchFloor, 24339–24367), and reverse-gravity
support throughout.

### Angle update & quadrant snapping (AnglePos, s2.asm:42534–42674)

- On an object (`on_object` bit): angle forced to 0 (42541–42546).
- Quadrant for sensor axes chosen from current angle: `(angle+$20)&$C0` with a ±1 nudge
  for negative angles at the boundary (42551–42559) → 0 = floor sensors (down), $40 =
  left-wall walk, $80 = ceiling walk, $C0 = right-wall walk (42570–42576).
- Two sensors at x±x_radius, y+y_radius (rotated per quadrant); the **closer floor wins**
  and supplies the new angle (Sonic_Angle, 42649–42654).
- **Snap rule:** if the winning tile angle is odd (bit 0 set — the "flagged" $FF/$01 tile
  angles) OR differs from the current angle by ≥ $20, the angle snaps to the nearest
  cardinal `(angle+$20)&$C0` (42656–42674). This is what keeps loops stable across
  angle-less tiles.
- **Floor stick clamps:** push-up only if distance ≥ −$E; snap-down allowed up to
  `min(|x_vel|>>8 + 4, $E)` px — beyond that the player goes airborne unless
  `stick_to_convex` is set (42607–42639). The speed-scaled down-snap is why fast running
  follows convex hills instead of launching. S3K identical (sonic3k.asm:18810–18840, with
  stick_to_convex checked before the clamp).

---

## 3. Jumping

`Sonic_Jump` (S2 s2.asm:37002–37055; S3K 23292–23364 identical values):

- Trigger: A/B/C **pressed** this frame; requires ≥ 6 px headroom via `CalcRoomOverHead`
  at angle+$80 (37009–37011) — no jump in low tunnels.
- Jump force `d2`: **$680**; Super **$800**; underwater **$380** (37012–37019).
  Knuckles (S3K): **$600**, underwater **$300** (sonic3k.asm:32458–32461) — the entire
  Sonic/Knuckles jump difference is these two constants.
- **Perpendicular launch:** velocity is *added* along the surface normal:
  `x_vel += cos(angle−$40)·force>>8`, `y_vel += sin(angle−$40)·force>>8`
  (37021–37030). Running speed is preserved; jumping off a slope launches along the
  normal, which is the entire "ramp jump" feel.
- Sets in_air, clears pushing, sets `jumping=1`, clears `stick_to_convex`, switches to
  ball hitbox ($E/$7 from $13/$9) with +5 y_pos compensation (37031–37046). If already
  rolling, instead sets the **roll-jump flag** (37040–37041, 37052–37054 — see §5).
- The `addq.l #4,sp` (37033) aborts the rest of the ground frame — jump frame runs no
  Move/Roll/collision; air handler starts next frame.

`Sonic_JumpHeight` (S2 s2.asm:37067–37096; S3K 23369–23397):

- **Variable height:** while `jumping` flag set, if `y_vel < -$400` (−$200 underwater)
  and no jump button held → `y_vel = -$400` (release cap). Hold = full $680 arc, tap =
  short hop.
- **Up-velocity cap (non-jump airborne):** if not from a jump (`jumping==0`) and
  `y_vel < -$FC0` → clamp to **−$FC0** (37088–37093). Applies to slope launches/springs
  into MdAir; skipped in pinball/spindash mode. (This cap is widely disliked — it
  truncates big ramp launches; S3K kept it, many hacks remove it.)
- S3K appends the double-jump/shield-move dispatch here when the button is *pressed*
  mid-air (Sonic_ShieldMoves, sonic3k.asm:23401–23457): fire dash ±$800 horizontal,
  lightning bounce y_vel=−$580 (also clears `jumping` so the release cap can't kill it),
  bubble down-thrust y=+$800 with x zeroed; bubble floor bounce is a perpendicular
  $780 ($400 underwater) impulse on landing (BubbleShield_Bounce, 24400–24424).

Airborne angle decay: `Sonic_JumpAngle` steps angle toward 0 by 2/frame (s2.asm:37465–37486;
S3K Player_JumpAngle 23964–23983). So a player leaving a wall keeps a stale angle briefly —
landing code must tolerate it.

---

## 4. Air physics

- **Gravity: +$38/frame** (ObjectMoveAndFall, s2.asm:29942–29956; S3K MoveSprite
  sonic3k.asm:36035–36045). Applied AFTER the position add (old y_vel moves you, then
  gravity). Underwater: a flat **−$28 correction after gravity → net $10**
  (s2.asm:36168–36170; hack `GRAVITY_UNDERWATER_SUB` S4.constants.asm:281–282). Hurt
  state uses its own gravity $30 (net $10 water) (s2.asm:37798–37802).
- **Air acceleration = 2 × ground acceleration** ($18; $C underwater): Sonic_ChgJumpDir,
  s2.asm:36815–36818. No friction and no deceleration distinction in the air — the same
  $18 applies regardless of direction reversal, which is why air turning feels snappy.
- **Air top-speed handling differs S2 vs S3K (real, verified):**
  - S2 hard-clamps: holding into the direction of travel while `|x_vel| > top` snaps
    x_vel back to ±top (s2.asm:36826–36831, 36837–36840 — no back-out).
  - S3K adds the same back-out trick as ground (sonic3k.asm:23103–23111, 23118–23124):
    **air speed above top is preserved while holding forward.** Consensus: S3K version is
    correct; the S2 clamp visibly kills spindash-jump momentum.
  - sonic_hack kept the S2 hard clamp (Player_Common.asm:352–369).
- **Air drag — exact rule** (Sonic_JumpPeakDecelerate, s2.asm:36853–36879; S3K identical
  23138–23165): runs every air frame after air accel, **but returns unless
  `-$400 ≤ y_vel ≤ -1`** — the comparison is `cmpi.w #-$400,y_vel / blo` (unsigned), so
  all y_vel ≥ 0 and all y_vel < −$400 skip it. The "apex-only band" is real and is
  **moving upward slower than $400**, in S2 AND S3K (and S1) — it is not an S3K addition.
  Formula: `d1 = x_vel asr 5` (x_vel/32, truncating); if d1 == 0 nothing; else
  `x_vel -= d1`, clamped at 0 from the moving side. Note `asr` means leftward motion
  between −$1F and −$1 still gets −1 drag, while rightward below +$20 gets none.
  Drag applies regardless of input (unlike SPG's S1 description); it exists to soften
  apex float.

---

## 5. Rolling

- **Roll start** (S2 Sonic_Roll, s2.asm:36954–36991): requires `|inertia| ≥ $80`, down
  held, and **left/right NOT held** (36960–36962). On roll: ball hitbox, +5 y_pos, sound,
  and if inertia is 0 (possible via slope factor timing) force `inertia = $200` (36986–36988).
  - **S3K** (SonicKnux_Roll, sonic3k.asm:23227–23281): threshold raised to
    `|ground_vel| ≥ $100` (23240–23241); below that, down ducks instead. (The 2P
    competition object kept the S2 $80 rule — sonic3k.asm:21696.) S3K min-roll is the
    commonly preferred rule because it pairs with ducking.
- **Roll friction = acceleration / 2** ($6; $3 underwater): Sonic_RollSpeed,
  s2.asm:36666–36670. Applied when rolling regardless of input direction held forward —
  rolling never accelerates from input.
- **Controlled roll deceleration = $20 fixed** (holding the opposite direction,
  s2.asm:36671; S3K 22938) — NOT decel/4 of the live stat; Tails' S2 code derives it as
  `deceleration/4`, the comment at s2.asm:36671–36673 flags the inconsistency underwater.
  Crossing zero while braking sets ∓$80 like walking (36777–36780, 36799–36801).
- **Speed caps while rolling: x_vel clamped to ±$1000** after projection
  (s2.asm:36749–36755; hack `MAX_ROLL_SPEED` S4.constants.asm:286). d6 is set to
  2×top_speed (36667–36668) but the roll input path never uses it for accel — the $1000
  x clamp is the real limit.
- **Unroll:** S2 unrolls only when inertia reaches exactly 0 (Sonic_CheckRollStop,
  s2.asm:36709–36719): restore standing hitbox, −5 y_pos. **S3K unrolls when
  `|ground_vel| < $80`** (sonic3k.asm:22975–22997) using per-character default radii.
  If unrolling is forbidden (pinball/roll-tunnel flag), force `inertia = ±$400`
  (Sonic_KeepRolling, s2.asm:36724–36729; S3K 23001–23005).
- **Roll-jump lockout:** jumping from a roll sets the rolljumping status bit
  (s2.asm:37052–37054); `Sonic_ChgJumpDir` returns immediately when it's set
  (36819–36820) → **no air control, no air drag skip — the whole air-input block is
  skipped** (camera/drag section still runs). **S3K kept the lockout identically**
  (sonic3k.asm:23096–23097, 23361–23363); the S3K change is only that shield moves clear
  the bit when triggered (23407). Community consensus is split; Sonic 3 Complete and most
  modern engines make it optional/removed — S3K canonical behavior is still locked.
- The spindash flag doubles as "may not unroll" while already rolling (s2.asm:36712 note).

---

## 6. State flags & the mode/quadrant machinery

Status byte bits (usage-cited; same layout S2/S3K/hack):

| Bit | Meaning | Evidence |
|---|---|---|
| 0 | facing left (x_flip) | s2.asm:36542, 36605 |
| 1 | in air | s2.asm:37031 (set on jump), 37764 (cleared on land) |
| 2 | rolling / in ball | s2.asm:36972–36979 |
| 3 | standing on object | s2.asm:36246, 42541 |
| 4 | roll-jumping (air control lock) | s2.asm:37053, cleared 37766 |
| 5 | pushing | s2.asm:36512, 36544 |
| 6 | underwater | s2.asm:36055, 37017 |

Bits 1+2 ARE the movement mode: `status & %0110` indexes the 4-entry handler table
(s2.asm:35914–35918) — normal / air / roll / jump-ball. There is no separate enum; landing
(`Sonic_ResetOnFloor`, s2.asm:37744–37778) just clears bits 1,4,5 (+2 if unrolling on
land) plus `jumping`, flip vars, and look-delay. sonic_hack moved jumping/spindash/
stick_to_convex/flip_turned into a `status3` byte with named bits (Sonic.asm:938–939,
Player_Common.asm:59,140) — a cleaner split of "physics mode" vs "misc flags" worth keeping.

The angle quadrant system (one byte angle, `(angle+$20)&$C0` selects sensor axes) is
detailed in §2; the same masked add appears everywhere a "which way is down" decision is
needed: slope-skid check (s2.asm:36578–36580), slip check (37438–37440), wall probe
rotation (36487–36497), landing band select (37584–37590). **A fresh engine should treat
`quadrant = (angle+$20)>>6` as a first-class derived value computed once per frame.**

`obj_control` (s2.asm:35912; S3K `object_control` bit 6 also gates the ground wall probe,
sonic3k.asm:22717) suspends the whole movement dispatch while an external object drives
the player — keep an equivalent escape hatch.

---

## 7. Control specifics that define the feel

- **Decel-vs-skid threshold:** holding opposite direction always applies $80 decel; the
  skid *animation/sound* additionally requires flat-quadrant ground and `|inertia| ≥ $400`
  (s2.asm:36583–36584, 36644–36645; S3K 22841–22842). Famous bug: the angle test
  clobbers d0 (inertia) first, so the $400 compare actually tests garbage — left/right
  skid trigger speeds differ; both disassemblies carry a `fixBugs` correction using d1
  (s2.asm:36568–36581, sonic3k.asm:22826–22839). Implement the fixed version.
- **Direction change:** facing bit flips the moment accel is applied in the new direction
  (even at speed) — `bset/bclr` + pushing-bit clear + animation restart
  (s2.asm:36542–36545, 36605–36608). Skid completion flips facing too (36586, 36647).
- **Slope slip + control lock (S2 Sonic_SlopeRepel, s2.asm:37432–37456):** when grounded,
  not stick_to_convex, `(angle+$20)&$C0 != 0` (steeper than 45°) and `|inertia| < $280`:
  `inertia = 0`, **detach** (in_air set), and `move_lock = $1E` (30 frames). While
  move_lock > 0 it is decremented here and both Move and RollSpeed skip *input* (friction
  and slope factor still run — s2.asm:36226–36227, 36676–36677), so Sonic visibly slides
  under gravity without player interference.
- **S3K slip rework (Player_SlopeRepel, sonic3k.asm:23911–23953):** threshold widened to
  `(angle+$18) < $30` → slip when angle ≥ $18 (≈34°, vs S2's 45°); lock is still 30
  frames; **but detach only happens when `(angle+$30) ≥ $60`** (≈ angle ≥ $30/67°…
  ceiling-ish). For the moderate band Sonic stays grounded and gets `ground_vel ±= $80`
  shoved downhill (23939–23948) — he slides down the slope instead of popping off it, and
  ground_vel is NOT zeroed. Consensus: S3K's "slide, don't fall" is the better feel and
  is the SPG-recommended behavior.
- **Move lock is also the spring/landing lock channel** — anything writing move_lock gets
  the same input-freeze semantics for free.
- **stick_to_convex** (set by S-tunnels etc., cleared on jump s2.asm:37035) disables both
  the slip check and the snap-down distance limit (42633–42635) — full loop adherence.
- Camera Y bias (look up/down after $78-frame delay, s2.asm:36398–36423) lives inside the
  movement code in all three sources; keep it out of the §5 physics core.

---

## 8. sonic_hack deviations worth keeping (and avoiding)

Worth keeping:
- **Shared Player_Common layer** with a3/a4/a5 register conventions so Sonic/Tails/
  Knuckles share one copy of ChgJumpDir, RollSpeed, SlopeResist/Repel, wall check, water,
  display (Player_Common.asm:4–10; Sonic.asm:649, 783–792, 1246–1256). Character deltas
  are parameterized (RollSpeed takes d2=standing height, d3=unroll y-shift,
  Sonic.asm:762–773).
- **Named constants for every magic number**: GRAVITY_NORMAL $38, GRAVITY_UNDERWATER_SUB
  $28, MAX_ROLL_SPEED $1000, SPINDASH_INCREMENT $200 / SPINDASH_MAX $800, MOVE_LOCK_TIME
  $1E, LOOK_DELAY_MAX $78, PLAYER_HEIGHT_STANDING $26 / ROLLING $1C, widths 18/14
  (S4.constants.asm:272–298).
- **ChooseSpeeds data-table stat selection** incl. the missing shoes/super underwater
  rows (Player_Common.asm:548–603) — fixes a real S2 gap.
- **S3K-style status3 flag byte** (jumping/spindash/stick_convex/flip/lock bits) grafted
  onto S2 physics (Sonic.asm:938–939, 996, 1499).
- **Shield double-jump suite** (S3K-inspired, custom values): insta-shield with enlarged
  hitbox $2C/$22 (Sonic.asm:2087–2092), fire dash ±$800 (2098–2114), lightning jump
  −$600 + 4 sparks (2126–2150, vs S3K's −$580), bubble bounce +$780 down / $3C0
  underwater with a **BounceRecoil** that re-launches perpendicular at $780 on landing
  (2153–2214). Double-jump flag cleared centrally in ResetOnFloor (1471–1473).
- Spindash is the stock S2 table design: release speed `$800 + charge·$80` up to $C00
  (Super $B00–$F00), charge +$200/tap capped $800, decay `counter -= counter>>5`/frame
  (Sonic.asm:1179–1222; identical to s2.asm:37332–37335). Keep the table form.

Avoid / known quirks:
- Core physics is **unmodified stock S2** — S2 slip-detach (45°, Player_Common.asm:138–161),
  S2 air hard clamp (352–369), S2 $80 roll threshold (Sonic.asm:854), unfixed skid-check
  d0 bug (682–693). None of the S3K refinements in §§2,4,5,7 were adopted — adopt them in
  aeon from S3K behavior, not from sonic_hack.
- `Sonic_DoLevelCollision` calls `Sonic_ResetOnFloor` twice on shallow landings
  (Sonic.asm:1308 then 1324) — redundant double reset, don't replicate.
- Hurt-state physics unchanged: gravity $30, on landing zero all velocity + $78
  invulnerability (Sonic.asm:1528–1567).

---

## Quick reference card (canonical values for aeon)

| Quantity | Value | Notes |
|---|---|---|
| accel / decel / friction | $C / $80 / $C | ×½ water; super $30/$100/$C-friction |
| top speed | $600 | $300 water, $C00 shoes, $A00 super |
| gravity | $38 | net $10 underwater; hurt $30 |
| jump force | $680 | $380 water; Knuckles $600/$300; super $800 |
| jump release cap | −$400 | −$200 water; only while `jumping` |
| airborne up-cap | −$FC0 | non-jump airborne only; consider removing |
| air accel | 2×accel | S3K: don't clamp above top when already faster |
| air drag | x_vel −= x_vel>>5 | only when −$400 ≤ y_vel < 0 |
| slope factor walk | $20·sin | skip if standing (S3K: apply if ≥ $D) |
| slope factor roll | $50·sin down / $14·sin up | quartered uphill |
| roll friction / brake | accel/2 / $20 | roll x_vel cap ±$1000 |
| roll start / unroll | ≥$100 (S3K) / <$80 (S3K) | S2: ≥$80 / ==0 |
| skid anim threshold | ≥$400 on flat quadrant | implement the d1 fix |
| slip | <$280 inertia, angle ≥$18 (S3K) | ±$80 nudge, detach only ≥$30; lock 30 frames |
| landing | axis-select by motion quadrant + angle band | y_vel>>1 mid band; both games identical |
| angle snap | tile angle odd OR Δ≥$20 → nearest $40 | floor snap-down ≤ min(|x_vel|/256+4, $E) |
