# Player Feel Research — Classic Constants + Modern Techniques (§5)

Research for the §5 player system. Sources: the Sonic Physics Guide (SPG) on Sonic Retro
(canonical community reverse-engineering of the Genesis originals — fetched via Wayback
Machine mirrors of `info.sonicretro.org`), SDA mechanics docs, Sonic 3 A.I.R., Sonic 3
Complete, fangame engine ecosystem, plutiedev.

All speed values below are signed 8.8 fixed point (1 pixel = 256 subpixels), per-frame at
60fps — the native format of the originals and what §5 should use. Angles are 256-step hex
angles (degrees given for reference).

---

## 1. Authoritative physics constants (SPG)

### Ground movement (Sonic/Tails/Knuckles — identical)

| Constant | Hex (8.8) | Decimal | Notes |
|---|---|---|---|
| `ACC_GROUND` | `$0C` | 0.046875 px/f² | Added to ground speed when holding direction of motion |
| `DEC_GROUND` | `$80` | 0.5 px/f² | When holding opposite direction (turnaround) |
| `FRC_GROUND` | `$0C` | 0.046875 px/f² | No horizontal input; applied toward 0, clamped at 0 |
| `TOP_SPEED` | `$600` | 6.0 px/f | Caps input acceleration ONLY — see §4 bug 1 |
| Turnaround quirk | `$80` | ±0.5 | When DEC crosses 0, GSp is set to ∓0.5, not 0 (authentic) |

### Air

| Constant | Hex | Decimal | Notes |
|---|---|---|---|
| `ACC_AIR` | `$18` | 0.09375 | 2× ground acc; no decel distinction, no friction in air |
| `GRAVITY` | `$38` | 0.21875 px/f² | Added AFTER position update (order matters for jump height) |
| `TOP_Y_SPEED` | `$1000` | 16.0 | Added in Sonic CD; absent in S1 (see §4 bug 3) |
| Air drag | — | `xsp -= (xsp div 0.125)/256` | i.e. `xsp -= (xsp >> 5) >> 3` floor-div; only while `-4 < ysp < 0`, before gravity |
| Air rotation | `$02`/frame | 2.8125°/f | Ground Angle eases back to 0 while airborne (sprite only — air sensors never rotate) |

### Jump

| Constant | Hex | Decimal | Notes |
|---|---|---|---|
| `JUMP_FORCE` (Sonic/Tails) | `$680` | 6.5 | Applied perpendicular to ground: `xsp -= jmp*sin(ang)`, `ysp -= jmp*cos(ang)` — ground speed is preserved (slope launch) |
| `JUMP_FORCE` (Knuckles) | `$600` | 6.0 | Knuckles jumps lower. (SPG: 6.0 exactly, not $650) |
| `JUMP_RELEASE_CAP` | `-$400` | -4.0 | Variable jump: while jumping and button not held, if `ysp < -4` set `ysp = -4`. Checked before movement+gravity |
| Low-ceiling jump check | dist < 6 | — | C/D sensors fire for 1 frame on jump press; jump suppressed if ceiling closer than 6px |

### Rolling

| Constant | Hex | Decimal | Notes |
|---|---|---|---|
| `FRC_ROLL` | `$06` | 0.0234375 | Half ground friction; no acceleration while rolling |
| `DEC_ROLL` | `$20` | 0.125 | Friction stacks with decel: effective `$26`/frame when braking |
| `ROLL_TOP_X` | `$1000` | 16.0 | Hard cap on X SPEED (not GSp!) while rolling — SPG recommends capping GSp instead |
| Roll start min | `$80` (S1/2/3) / `$100` (S&K) | 0.5 / 1.0 | S&K raised it so crouch→spindash works while creeping |
| Unroll threshold | `$80` (S&K only) | 0.5 | S&K unrolls below this |
| Forced-roll GSp | `$200` | 2.0 | If forced to roll at GSp 0 (S-tunnels), GSp set to 2 |
| Roll-jump | — | — | S1/2/3K: no air control after jumping from a roll. CD/Mania: full control |

### Slopes

| Constant | Hex | Decimal | Notes |
|---|---|---|---|
| `SLOPE_NORMAL` | `$20` | 0.125 | `GSp -= slope*sin(ang)` at start of step; skipped in Ceiling mode |
| `SLOPE_ROLL_UP` | `$14` | 0.078125 | Rolling, sign(GSp) == sign(sin(ang)) |
| `SLOPE_ROLL_DOWN` | `$50` | 0.3125 | Rolling downhill |
| Standing exception | `$0D` | 0.05078125 | S1/2: no slope factor at GSp==0. S3K: still applied if factor ≥ $0D (can't stand on steep slopes). Rolling slope factor never checks GSp==0 |
| Slip threshold | `$280` | 2.5 | abs(GSp) below this on steep ground → slip |
| Control lock | 30 frames | ~0.5s | Ticks only while grounded; friction still input-gated during lock |
| S1/2/CD slip range | hex 223–32 | 46°–315° | Detach, GSp = 0, lock = 30 |
| S3K slip range | hex 231–24 | 35°–326° | GSp ±= 0.5 (`$80`) toward downhill instead of zeroing |
| S3K fall range | hex 207–48 | 69°–293° | Detach only at these steeper angles |

Movement on ground every frame: `xsp = GSp*cos(ang)`, `ysp = GSp*-sin(ang)` → add to
position → ground sensors re-align. GSp is the single source of truth while grounded.

### Landing conversion (air → ground speed), by winning sensor angle

Floor landing (moving down; ranges inclusive, smaller overrides larger):
| Range | Hex angle | GSp result |
|---|---|---|
| Flat | 0–23° (255–240, 15–0) | `GSp = xsp` |
| Slope | 0–45° (255–224, 31–0) | mostly-horizontal motion: `GSp = xsp`; else `GSp = ysp * 0.5 * -sign(sin(ang))` |
| Steep | outside Slope | mostly-horizontal: `GSp = xsp`; else `GSp = ysp * -sign(sin(ang))` |

Ceiling contact (moving up): flat ceiling range 91°–225° (191–66) → bump head, `ysp = 0`;
steeper → if moving mostly up, reattach grounded with `GSp = ysp * -sign(sin(ang))`.

### Underwater (apply on entry, restore on exit)

acc `$06`, dec `$40`, frc `$06`, top `$300`, air acc `$0C`, roll frc `$03`, roll dec `$20`
(unchanged), gravity `$10`, jump `$380` (`$300` Knuckles), jump release cap `-$200`.
Entry: `xsp *= 0.5`, `ysp *= 0.25` (after gravity). Exit: `ysp *= 2`, clamped to `-$1000`.
Air timer: 30s, event cadence 60 frames.

Sources:
- https://info.sonicretro.org/SPG:Running
- https://info.sonicretro.org/SPG:Air_State
- https://info.sonicretro.org/SPG:Jumping
- https://info.sonicretro.org/SPG:Rolling
- https://info.sonicretro.org/SPG:Slope_Physics
- https://info.sonicretro.org/SPG:Underwater
- https://info.sonicretro.org/SPG:Characters

---

## 2. Sensor geometry specification (SPG)

### Radii (sizes are 2r+1 px — always odd)

| State | Width Radius | Height Radius |
|---|---|---|
| Sonic / Knuckles standing | 9 | 19 (19×39 px) |
| Tails standing / flying | 9 | 15 (19×31 px) |
| Any character jumping/rolling | 7 | 14 (15×29 px) |
| Knuckles glide/climb/slide | 10 | 10 |
| **Push Radius (all, always)** | **10** | — |

On radius change (curl/uncurl) the player Y shifts 5px to keep the bottom pixel fixed.
Hitbox (object interaction, separate from solidity): width radius 8, height radius =
HeightRadius − 3. (S2 Sonic crouch: hitbox y+12, hr=10; S3+ crouch doesn't change it.)

### Sensors (Floor mode positions; whole arrangement rotates 90° per mode)

| Sensor | Position | Purpose |
|---|---|---|
| A (ground L) | (x − WR, y + HR), points down | Floor |
| B (ground R) | (x + WR, y + HR), points down | Floor |
| C, D (ceiling) | exact mirror of A/B, point up | Ceiling |
| E (push L) | (x − 10, y), points left | Wall |
| F (push R) | (x + 10, y), points right | Wall |

E/F drop to `y + 8` when Ground Angle == 0 exactly (so low steps push instead of snap-up).
Pushing width (21px) is 2px wider than ground footing (19px). Grounded push sensors test at
`position + (xsp,ysp)` (cast where the player WILL be, before movement), and on hit add the
distance into the speed rather than position. Airborne push: at y, after movement, sets
`xsp = 0` and adds distance to position.

### Sensor mechanics

- A sensor reads the 16-entry height (or width) array of the 16×16 block it's in;
  regression (full 16 → check 1 block back) / extension (empty/0 → check 1 block out)
  gives an effective 2-block, 32px range.
- Returns: distance to surface (−32..31), tile angle, tile id. Distances 16..32 ⇒ treat
  as "nothing found".
- Grounded floor acceptance: S1: reject if dist < −14 or > 14. S2+: positive limit is
  `min(abs(xsp) + 4, 14)` (Y-axis modes use ysp) — faster = stickier; −14 fixed.
- Tile angle `$FF` = flagged: snap Ground Angle to nearest 90°. S2+ also snaps when
  |tile angle − Ground Angle| > 45° (hex 32).
- A vs B: smaller distance wins (tie → A); winner supplies distance AND angle.

### Mode tables (derived from Ground Angle each collision, never stored)

| Mode | Ground sensors (hex) | Push sensors (hex) |
|---|---|---|
| Floor | 0°–45°, 315°–360° (255–224, 32–0) | 0°–44°, 316°–360° (255–225, 31–0) |
| Right Wall | 46°–134° (223–161) | 45°–135° (224–160) |
| Ceiling | 135°–225° (160–96) | 136°–224° (159–97) |
| Left Wall | 226°–314° (95–33) | 225°–315° (96–32) |

Push sensors are disabled outside −90°..90° ground angle (no pushing on loop tops);
S3K re-enables them at exact multiples of 90°. Mode effectively updates one frame late
(uses last frame's angle) — original behavior.

### Airborne activation (by motion quadrant, from atan2(ysp,xsp))

- Mostly right: A, B, C, D + F. Mostly left: A, B, C, D + E.
- Mostly up: C, D, E, F. Mostly down: A, B, E, F.
- Air sensors never rotate with angle.
- Airborne floor collide rules: only if winning dist < 0; moving mostly down additionally
  requires a sensor dist ≥ −(ysp + 8); moving mostly left/right requires ysp ≥ 0.
- Jump-through (top-solid) tiles: only A/B detect them — the upward "pop onto platform"
  when falling begins is a consequence, not a special case.

### Misc grounded behaviors

- Both ground sensors find nothing → airborne (run off ledge).
- Balancing: GSp==0 and only one sensor active and a center probe (x, y+HR) finds no
  floor → balance anim; origin can be up to edge+10 before falling (~10px of built-in
  spatial "coyote" forgiveness). Second-stage balance anim at ~edge+7 (S2+).

Sources:
- https://info.sonicretro.org/SPG:Solid_Tiles
- https://info.sonicretro.org/SPG:Slope_Collision
- https://info.sonicretro.org/SPG:Characters
- https://info.sonicretro.org/SPG:Hitboxes
- https://info.sonicretro.org/SPG:Main_Game_Loop (per-state order of operations)

---

## 3. Modern technique verdicts

Calibration point: Sonic Mania (Tax/Stealth) is the community-accepted ceiling for "modern
but still classic". Its documented deviations from the Genesis games are small and
deliberate: jump-delay fix (move on the press frame), slightly taller jump (gravity
cancelled on the launch frame, ≈ +8px apex, +2 frames), CD-style roll-jump air control,
and the drop dash. It did NOT add coyote time, visible input buffering, corner correction,
or a speed camera (SPG documents each Mania difference inline). Sonic 3 A.I.R. is the
other reference: it ships feel changes (extended camera, smooth rotation, glitch fixes)
strictly as opt-in settings — the community norm is "fixes on, deviations optional".

| Technique | Verdict | Rationale |
|---|---|---|
| Coyote time (grace frames after leaving ledge) | **User-decision** (default off, ≤4 frames if on) | Classic already grants ~10px spatial forgiveness (origin can overhang the ledge before both sensors clear); Mania/Origins didn't add temporal grace; harmless at 2–4f but not canon. |
| Jump input buffering (press N frames before landing still jumps) | **Adopt, 2 frames** | Invisible, pure anti-frustration; consistent with Mania's responsiveness goals; zero physics-visible change. Trivial on 68000 (decrement a buffer counter latched on press edge). |
| Jump-delay fix (player moves on the jump press frame) | **Adopt** | The original skips the rest of the player step on the press frame — SPG documents it as a bug (you can even get a −4 release jump without ever moving at jump force). Mania fixed it; nobody defends it. |
| Variable jump: early-release velocity cap (−$400) | **Adopt (this IS classic)** | The cap is the authentic mechanism. Reject early-release-gravity-multiplier schemes — they change the arc shape and feel floatier. |
| Mania's taller jump (cancel gravity on launch frame) | **User-decision** (default off) | Deliberate Mania deviation, not Genesis; ±8px apex changes level-design tuning. Keep a build flag, decide after §5 playtesting. |
| Corner correction (nudge sideways when clipping a ceiling edge) | **Reject for terrain** | Classic already has the answer: steep-ceiling reattach + flat-ceiling head bump, plus the 15px-wide curled hitbox; 360° collision makes "nudge direction" ambiguous on slopes. Revisit only for solid OBJECTS if §5 testing shows head-catch frustration. |
| Speed-dependent camera lead (CD extended camera: focal point shifts back 64px at GSp ≥ 6, 2px/step) | **User-decision** (engine support, default off) | Divisive since 1993; Mania rejected it for the main games, S3AIR ships it as an option. SPG notes CD's version misbehaves in air (GSp doesn't update) — if implemented, drive it from xsp. |
| Roll-jump air control (CD/Mania behavior) | **Adopt** | The S1/2/3K lockout is the single most-complained-about classic control rule; CD and Mania both allow control; cost is deleting a restriction, not adding code. |
| Drop dash | **Adopt when §5 moveset lands** | Mania's celebrated addition, designed by Whitehead for flow on replays; fits classic feel by community consensus. |
| S3K slip/fall method (±$80 nudge, split 35°/69° ranges) | **Adopt over S1 method** | The most refined original implementation; prevents standing on steep slopes and feels less punitive than S1's hard GSp=0. |

Sources:
- https://info.sonicretro.org/SPG:Jumping (Mania jump differences, jump-delay bug)
- https://info.sonicretro.org/SPG:Rolling (roll-jump control per game)
- https://info.sonicretro.org/SPG:Camera (borders, lag caps, CD extended camera, spindash lag)
- https://sonic3air.boards.net/thread/1015/enhanced-extended-camera-v1-1 (S3AIR opt-in camera)
- https://sonic.fandom.com/wiki/Drop_Dash (design intent, behavior differences in Origins back-ports)
- https://www.ketra-games.com/2021/08/coyote-time-and-jump-buffering.html (generic technique reference)

Camera numbers worth keeping (SPG:Camera): H border 144/160 (consider 152/168 to center
both directions), V focal point 96, air V border ±32, scroll caps 16px/f (S1/2/CD) or
24px/f (S3K), ground V catch-up 6 (slow) / 16–24 (GSp ≥ 8), look up/down shift 104/88 at
2px/step with 120-frame delay (S2+), spindash launch lag via 32-frame position-history
replay (blank the history at launch to avoid backward scroll, or just freeze camera 16
frames).

---

## 4. Known classic bugs — fix or keep

| # | Bug | Recommendation |
|---|---|---|
| 1 | **S1 ground speed-cap curtail**: holding forward while above top speed (spring, slope) clamps GSp to $600 — pressing your run direction KILLS momentum. | **Fix** (S2 already did): only add ACC and clamp when GSp was below top beforehand. Critically, this preserves the legitimate behavior that slope factor / springs / downhill rolling can exceed $600 — the cap gates input acceleration only. |
| 2 | **Air speed cap** (S2/CD): the S2 fix wasn't applied to the airborne branch, so running off a ledge above top speed and holding forward clamps xsp — the famous "lose your speed jumping off a hill" quirk. | **Fix** (apply the same already-above-top check in air). S3K fixed it; an S3AIR mod exists solely to re-add the S2 cap for speedrun parity — make our fix a constant, not a hardcode. |
| 3 | **Tunneling / jump-through-floor at high speed**: sensors reach 32px, so >16px/frame can skip terrain; S1 has no Y speed cap at all. | **Fix**: adopt CD's `TOP_Y_SPEED = $1000` and cap rolling speed at $1000 — on GROUND SPEED, not X speed (SPG explicitly recommends this over the original X-speed cap, which misbehaves in wall modes). With both caps ≤16px/f the 32px sensor range is mathematically sufficient; no swept collision needed. |
| 4 | **1-frame jump delay** (press frame does nothing). | **Fix** per Mania (see §3). |
| 5 | **Roll-jump size bug**: jumping from a roll keeps STANDING radii; landing then "uncurls" anyway, popping the player 5px above the floor (S2). S3's fix introduced a 5px ground sink used for Marble Garden clips. | **Fix properly**: always use rolling radii (7/14) while curled, symmetric ±5px shift on curl/uncurl. Closes both the pop and the clip. |
| 6 | **Two-sensor ledge quirks**: running off a slanted ledge pops the player up–down–up; abutting opposite ramps dip 1px and report the WRONG angle (jumping launches backward). | **Fix, low priority / optional**: prefer the sensor nearer the direction of motion when distances tie within tolerance. Visible in only a few spots (GHZ/MZ-style hills); pure parity builds may keep it. |
| 7 | **Wall ejection zips / level wrap**: getting embedded in a wall ejects at high speed; X underflow wraps to end-of-level (S3K: x=32767 loopback). | **Fix**: clamp eject distance per frame, never invert speed sign on ejection, clamp position to section bounds (our section streaming makes wraps fatal anyway). Speedrunners are the only constituency for keeping zips — S3AIR's answer is optional "glitch fixes", ours is a build flag at most. |
| 8 | **MoDule's S3 fixes** (shipped in Sonic 3 Complete): jumping out of shallow water gravity error, roll-jump hitbox error, stale midair physics when a pillar/object is smashed from beneath the player. | **Fix** — community-canon-positive (Sonic 3 Complete is the reference "fixed S3"). |
| 9 | **Slope glitch**: ground angle persists after the object stood on is destroyed → walking on air at the old angle. | **Fix**: force airborne re-evaluation whenever the standing surface (object) disappears. |
| 10 | **Left+Right simultaneously** runs both input branches in one step. | **Fix**: mask opposing directions (worn pads can produce this on real hardware). |
| 11 | **S3K landing/ceiling angle asymmetries** (ranges like 46°–315° not perfectly symmetric). | **Keep** — SPG notes the asymmetry is an artifact of cheap calculation, but it's also what every reference value was tuned against; symmetrize only if our angle math makes it free. |

Sources:
- https://kb.speeddemosarchive.com/Sonic_the_Hedgehog/Game_Mechanics_and_Glitches (speed caps per game, zips, wraps, tunneling, slope glitch, roll-jump 5px)
- https://info.sonicretro.org/SPG:Running (S1 cap quirk + S2 fix description)
- https://info.sonicretro.org/SPG:Jumping (jump delay, roll-jump size bug)
- https://www.romhacking.net/hacks/1056/ + https://sonichacks.fandom.com/wiki/Sonic_3_Complete (MoDule bugfix list)
- https://gamebanana.com/mods/54146 (S2 air speed cap as an opt-in S3AIR mod — evidence the fix is default-canon)
- https://github.com/Eukaryot/sonic3air/releases (glitch-fix options split for speedrunning)

---

## 5. Genesis pad input handling for feel

- **Poll exactly once per frame, at a fixed point** — in the VBlank handler, before game
  logic. The 6-button pad sequences its extra buttons off TH toggles with an internal step
  counter that resets after ~1.5ms idle; polling twice per frame or at drifting times
  corrupts reads (plutiedev). The Sonic originals poll in V-int, which is the right call.
- **Poll during lag frames too** (V-int still fires) and latch EDGES, not just levels:
  maintain `held` + `pressed` (rising edge) bytes, and let `pressed` accumulate (OR, not
  overwrite) until game logic consumes it. Then a button tapped during a dropped frame
  still jumps on the next logic tick — this is the single cheapest "modern feel" win and
  pairs with the 2-frame jump buffer in §3.
- **6-button read**: 7 TH toggles ($40/$00 alternating) with `nop` settling delays; step 6
  low nibble == 0 identifies a 6-button pad; step 7 yields X/Y/Z/Mode. Detect once per
  frame as part of the normal read (it IS the normal read). Holding Mode at power-on
  forces 3-button compat — honor it.
- **Design rule**: core moveset must be complete on 3 buttons (every classic shipped
  that way); X/Y/Z only for convenience remaps (e.g., dedicated ability/super button as
  Mania added) — never required.
- Active-low data: bit 0 = pressed; mask opposing D-pad directions after read (§4 bug 10).

Source: https://www.plutiedev.com/controllers

---

## Decisions needed from user (flagged for §5 planning)

1. Coyote time toggle (default off) — yes/no, and frame count if yes.
2. Mania taller-jump flag — adopt, or strict Genesis arc.
3. Extended-camera support — build it now as an option, or defer.
4. S3AIR-style "keep classic glitches" build flag for bug fixes 2/7 — worth the asm
   complexity, or fix unconditionally.
