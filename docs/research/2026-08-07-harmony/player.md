# Harmony Framework — PLAYER research (design ideas only, no code transfer)

Source: `/home/volence/sonic_hacks/aeon/docs/research/external/harmony/`
(UltraRing "Harmony Framework", GameMaker Studio 2 / GML, MIT for original games).
Read: all `scripts/player_*`, `scripts/collision_util`, `scripts/game_init_collision`,
`scripts/game_enums`, `scripts/game_config`, `scripts/game_init_global_variables`,
`scripts/math_util` (relevant fns), `objects/obj_player/*.gml`. ~4.5 kLOC total.

Our side: `games/sonic4/player/*.emp` (3086 lines) + `data/animations/sonic_anims.emp`,
constants in `engine/system/constants.emp` and `games/sonic4/config/constants.emp`.

Baseline ruling for this report: **S3K is the behavioral baseline, target is
classic-faithful.** Every Mania/CD/modern-ism in Harmony is tagged as a CHOICE, not a win.

---

## PART 0 — Executive summary (read this if nothing else)

1. **Their physics constants are the classic 8.8 fixed-point values written as floats.**
   0.046875 = $C/256, 0.21875 = $38/256, 0.0234375 = $6/256, 0.078125 = $14/256,
   0.3125 = $50/256, 0.125 = $20/256. Every single physics constant in Harmony is
   n/256. **Their "floating point physics" is 8.8 in disguise — the port is exact.**
   Only three places need real division (peelout `/2.9`, spindash audio pitch `/28`,
   step count `/14`), and all three are approximable by shifts.
2. Their state machine is a **bare function pointer with no enter/exit hooks**. We
   have hooks and a transition-authority routine. **Ours is structurally better.**
   What they have that we don't is (a) a per-frame **capability-flag reset** model and
   (b) a **post-dispatch cross-cutting condition block**. Both are cheap on 68K and worth taking.
3. Their collision **derives the surface angle from the height map** (no angle table).
   Interesting, expensive, and we already solve the same failure mode with the
   odd-flag + divergence-snap policy.
4. Their shield abstraction is a **dispatch array of per-frame functions plus one
   shared `shield_state` byte** — serviceable but leaky (shield identity is enum-tested
   in `player_util`, `player_water`, `player_states`, `player_state_jump`).
5. Their character variation is **data tables for stats/art + inline `if (character ==)`
   branches for ability entry + dedicated states for ability bodies.** The inline
   branches are the weak part. **Our spec §3.1 rule ("characters contribute data +
   ability states, never fork inside shared routines") is the better design and this
   codebase is the evidence for why.**
6. Two concrete fidelity bugs found **on our side** by comparison (see §6):
   the **roll animation duration base** and the **grounded push-sensor Y offset**.

---

## PART A — Full state / ability inventory (feature checklist)

### A.1 Harmony's state machine architecture

`state` is a **script (function) reference** stored on the player instance
(`obj_player/Create_0.gml:36`). Dispatch is `script_execute(state)`
(`player_states.gml:49`). There is **no state id, no jump table, no enter hook, no
exit hook.** Transitions are bare assignments (`state = player_state_roll;`) scattered
across every state file, and every consequence of the transition is hand-written at
each assignment site.

Concretely, the roll transition has to manually do four things at each of its four
call sites: play the anim, set `state`, zero `idle_timer`, call `_player_hitbox(true)`
(`player_state_roll.gml:80-90`, `player_state_spindash.gml:74-79`).

The **hitbox is a function of the ANIMATION, not the state**
(`player_util.gml:436-483`: `if(animation_is_playing(animator, ANIM.ROLL) || ...
|| state == player_state_jump)`). That is a fragility we deliberately do not have —
our size lives only in the enter hooks (`PHook_EnsureBall` / `PHook_EnsureStanding`,
`player_common.emp:664-682`), keyed on the height byte and idempotent.

**What they have instead of exit hooks — the per-frame capability reset**
(`player_states.gml:5-15`):

```
if(flag_override) {
    direction_allow = true;  movement_allow = true;  collision_allow = true;
    attacking = false;       gravity_allow = true;   hitbox_allow  = true;
    speed_allow = true;
}
can_jump = false;  can_roll = false;
```

Every state then **re-asserts** what it needs each frame
(`player_state_glide.gml:4-7` sets movement/direction/gravity false + attacking true;
`player_state_transform.gml:11-27` flips the whole set on a timer). This is
immediate-mode: no stale flags are possible, so no exit hook is needed for cleanup.
`flag_override` is the opt-out for external systems that want to pin a flag.

**Cross-cutting transition block** — `player_state_conditions()`
(`player_states.gml:57-105`), run once after the state body, owns transitions that
are not any one state's business: air-roll (`:78-86`), look-down trigger (`:89-96`),
dropdash timer reset (`:72-75`), insta-shield flag reset (`:68-69`), state-scoped
sound stop (`:100-104`).

**Composable transition predicates** — `player_check_jump()`
(`player_state_jump.gml:103-133`) and `player_check_roll()`
(`player_state_roll.gml:74-93`) return true when they fired; callers `exit`.
Used by normal / roll / lookup / lookdown. Good idiom; we have the analogue
implicitly (`Player_Jump` reached from both `PState_Ground` and `PState_Roll`).

**Sub-state machines** encoded as plain integers, not states:
`shield_state` (0/1, per shield), `knockout_type` (K_HURT/K_DIE/K_DROWN/K_STUNNED,
`player_macros.gml:7-10`), `ceiling_landing`, `skid_timer` (a skid sub-state living
inside `player_state_normal`), `dropdash_timer`, `transform_timer`.

**Frame order** (`obj_player/Step_1.gml`):
```
character/hitbox-offset reset -> player_get_input -> player_handle_physics
-> super gate -> player_inv_speed -> compute `steps`
-> repeat(steps) { player_movement -> player_mode -> player_collision }
-> player_control -> animator_update -> player_states (shields -> state -> conditions -> tails)
-> player_direction -> player_visual_angle -> _player_hitbox -> player_misc
-> player_water -> recorder update
```
Note the ordering oddity: **`player_control` (input->speed) runs AFTER the movement
and collision loop**, so input applied this frame only moves you next frame. The
classics do input->move->collide in one pass. This is a deliberate structural choice
of theirs, not classic order.

### A.2 State inventory (= feature checklist)

Legend: **[HAVE]** we have it · **[PARTIAL]** mechanism exists, not wired
· **[MISSING]** · **[CHOICE]** non-S3K, adopting is a decision

| Harmony state | File | Ours | Notes |
|---|---|---|---|
| `player_state_normal` | `player_state_normal.gml` | **[HAVE]** `PState_Ground` | theirs also owns skid + push + teeter anim selection; ours splits that into `Player_Animate` |
| `player_state_roll` | `player_state_roll.gml` | **[HAVE]** `PState_Roll` | |
| `player_state_jump` | `player_state_jump.gml` | **[HAVE]** `PState_Jump` + `PState_RollJump` | theirs has no roll-jump lockout at all (see §B) |
| (airborne, uncurled) | — none; they reuse `normal` while `!ground` | **[HAVE]** `PState_Air` | they have **no dedicated air state**: `player_state_normal` runs airborne with `ground == false` |
| (airborne, curled, not from jump) | — none | **[HAVE]** `PState_AirBall` | rolled off a ledge stays `player_state_roll` in Harmony |
| `player_state_spindash` | `player_state_spindash.gml` | **[HAVE]** `PState_Spindash` | |
| `player_state_lookup` | `player_state_lookup.gml` | **[PARTIAL]** anim only (`ANIM_LOOKUP`) | theirs is a real state: locks movement/direction, decays gsp by friction, gates peel-out |
| `player_state_lookdown` (duck) | `player_state_lookdown.gml` | **[PARTIAL]** anim only (`ANIM_DUCK`) | theirs gates the spindash entry and applies a 0.125 slope influence while ducking |
| `player_state_spring` | `player_state_spring.gml` | **[MISSING]** | 10 lines: play SPRING anim, exit to normal/roll when `y_speed >= 0 \|\| ground` |
| `player_state_knockout` (hurt) | `player_state_knockout.gml:1-16` | **[MISSING]** | |
| `player_state_death` | `player_state_knockout.gml:18-86` | **[MISSING]** | `Player_Death_Pending` flag exists (`player_common.emp:840`), nothing consumes it |
| `player_state_drown` | `player_state_knockout.gml:88-161` | **[MISSING]** | |
| `player_state_transform` (super) | `player_state_transform.gml` | **[MISSING]** | |
| `player_state_dropdash` | `player_state_dropdash.gml` | **[MISSING]** | **[CHOICE]** Mania |
| `player_state_peelout` | `player_state_peelout.gml` | **[MISSING]** | **[CHOICE]** Sonic CD |
| `player_state_tailsfly` | `player_state_tailsfly.gml` | **[MISSING]** | Tails |
| `player_state_glide` | `player_state_glide.gml` | **[MISSING]** | Knuckles |
| `player_state_wallclimb` | `player_state_wallclimb.gml` | **[MISSING]** | Knuckles |
| `player_state_ledgeclimb` | `player_state_ledgeclimb.gml` | **[MISSING]** | Knuckles; frame-indexed position table |
| `player_state_knuxfall` | `player_state_knuxfall.gml` | **[MISSING]** | Knuckles |
| `player_state_knuxslide` | `player_state_knuxslide.gml` | **[MISSING]** | Knuckles |
| `player_state_null` | `player_state_null.gml` | **[MISSING]** | 3-line no-op state for cutscene/lock; we'd want this |
| debug fly | `player_debug.gml` (not a state — a `Step_1` early-out) | **[HAVE]** `Player_DebugMove` | ours is cleaner (runtime cheat gate, not a build gate) |

### A.3 Abilities / orthogonal mechanics inventory

| Feature | Harmony | Ours |
|---|---|---|
| Spindash | **[HAVE]** rev/decay/release, sound pitch ramp, dust | **[HAVE]** exact classic closed form |
| Roll | **[HAVE]** | **[HAVE]** |
| Jump + variable height | **[HAVE]** | **[HAVE]** |
| Jump **buffering** | **[MISSING]** in Harmony | **[HAVE]** `PHYS_JUMP_BUFFER = 2` — **[CHOICE]**, this is a modern-ism we already took; classics have no buffer |
| Skid + skid-turn | **[HAVE]** as a 24-frame timer sub-state w/ separate SKIDTURN anim | **[HAVE]** as an anim latch (`skid_latch`) — **ours is the Genesis approach** |
| Push detection | **[HAVE]** anim only, via a speed+wall-distance heuristic | **[HAVE]** `ST_PUSHING` from the wall probe — cleaner |
| Teeter / balance | **[HAVE]** 3 probes, LEDGE1/LEDGE2 chosen by side, on-object variant | **[HAVE]** `Player_AtLedgeEdge`, single ANIM_BALANCE (no side split) |
| Forced roll (S-tubes) | **[HAVE]** `force_roll` flag, first-class across roll/jump/spring/movement | **[MISSING]** (`PHYS_ROLL_FORCE_MIN` reserved) |
| Water running | **[HAVE]** `water_run` flag, orthogonal to state | **[MISSING]** |
| Layer/plane switching | **[HAVE]** `plane` (PLANE.A/B), separate tilemap layers | **[HAVE]** `layer` byte + `path_swap.emp` object |
| Solid-object riding | **[HAVE]** `on_object` / `on_object_count` / `ledge` | **[HAVE]** `ST_ON_OBJECT` + `SST_interact` owner |
| Semi-solids | **[PARTIAL]** — explicit TODO, see §B-14 | **[HAVE]** `SOLID_TOP` class mask |
| Shields x4 | **[HAVE]** | **[MISSING]** |
| Insta-shield | **[HAVE]** (off by default) | **[MISSING]** |
| Invincibility / speed shoes | **[HAVE]** | **[MISSING]** (`status_secondary` reserved) |
| Super form | **[HAVE]** + palette cycle + ring drain | **[MISSING]** |
| Underwater physics + drowning | **[HAVE]** | **[MISSING]** (`air_left` reserved) |
| Rings / ring loss | **[HAVE]** + Chaotix combine ring | **[MISSING]** |
| Visual (sprite) angle | **[HAVE]** 3 modes | **[PARTIAL]** `flip_angle` reserved, unimplemented |
| Look/duck camera pan | **[HAVE]** (via camera object) | **[PARTIAL]** `look_offset` reserved, pinned 0 |
| After-images (shoes/super) | **[HAVE]** generic recorder ring | **[HAVE]** `Player_Pos_Ring`/`Stat_Ring` (concrete) |
| Camera roll offset (curl comp.) | **[HAVE]** `camera_rolling_offset = [5,1,5]` | **CHECK** — we shift `y_pos` by `CURL_Y_SHIFT` on curl; verify the camera compensates |
| Air roll | **[HAVE]** (off by default) | **[MISSING]** — **[CHOICE]**, not classic |
| Dropdash / peelout | **[HAVE]** (both ON by default) | **[MISSING]** — **[CHOICE]**, Mania / CD |
| Get-up animation | (none) | **[PARTIAL]** `getup_timer` mechanism exists, never armed |
| Death / respawn | **[HAVE]** | **[MISSING]** |
| Null/cutscene state | **[HAVE]** | **[MISSING]** |

---

## PART B — Deviation & bugfix catalog

Harmony has **almost no explicit "the original did X, we do Y" comments** — the
README claims "a slew of additional content and bugfixes from the original games"
but the code does not annotate them. The catalog below is therefore derived by
comparing their code against S3K / the Sonic Physics Guide. Confidence is marked.

### B.1 Deviations they made deliberately (config-visible)

| # | What | Cite | Verdict for us |
|---|---|---|---|
| 1 | Dropdash ON by default | `game_init_global_variables.gml:67` | **[CHOICE]** Mania. Not S3K. |
| 2 | Peel-out ON by default | `game_init_global_variables.gml:66` | **[CHOICE]** Sonic CD. Not S3K. |
| 3 | Air-roll flag (off) | `:68`, used `player_states.gml:78-86` | **[CHOICE]** not classic |
| 4 | Insta-shield **OFF** by default | `:70` | odd — insta-shield *is* S3K. We'd default it ON. |
| 5 | Vertical camera default = "Mania" | `:74` (`global.camera_type = 1`) | **[CHOICE]** |
| 6 | Sprite rotation default = smooth interpolation | `:65` (`rotation_type = 0`) | **impossible on Genesis.** Their `rotation_type == 1` (45° snap w/ 34° deadzone) is the only hardware-representable mode. See §C-14. |
| 7 | `KNUCKLES_S3_GLIDE_TURN = false` | `game_config.gml:30` | i.e. their default glide-turn is *not* S3-accurate; the S3 behavior is opt-in |
| 8 | `PLAYER_ALT_COLLISION_MODE = true` | `game_config.gml:10-12` | mode changes driven by wall probes, sourced from the "Sonic Studio / improving classic Sonic physics" blog, not from any Sega game. See §C-5. |
| 9 | Sub-stepped movement (`steps` 1..4) | `game_config.gml:14-18`, `Step_1.gml:34,44-55` | modern anti-tunneling. Not classic. |
| 10 | `global.no_skid_state = true` — *"makes skidding work closer to the genesis games, instead of a separate state"* | `game_init_global_variables.gml:77` | **DEAD CONFIG.** Grepped the whole repo: the variable is **never read anywhere.** The skid *is* still a timer sub-state (`skid_timer = 24`, `player_state_normal.gml:104,144-192`) with a separate SKIDTURN animation and a deferred facing flip — that is Mania behavior, and the toggle that claims to disable it does nothing. |

### B.2 Numeric deviations from S3K (unannounced)

All values below are Harmony's, with the S3K/SPG value and our constant.

| # | Quantity | Harmony | S3K / SPG | Ours | Confidence |
|---|---|---|---|---|---|
| 11 | Roll speed cap | **18** (`Create_0.gml:33`, applied `player_state_roll.gml:71`) | 16 | `PHYS_GSP_CAP = $1000` = 16 | high |
| 12 | Global speed clamp | **24** (`Create_0.gml:27`, `player_movement.gml:3-5`) | no such global clamp | n/a | high |
| 13 | Unroll threshold | **exactly `ground_speed == 0`** *and* angle within ±40° (`player_state_roll.gml:37-50`) | \|gsp\| < 0.5 | `PHYS_UNROLL_MAX = $80` = 0.5 | high — visible: Harmony's Sonic stays curled all the way down to a dead stop |
| 14 | Roll **start** requires L/R released | **NO check** (`player_state_roll.gml:77`) | L/R must not be held | we veto on L/R (`player_ground.emp:150-154`) | high |
| 15 | Slip angle band | **≥ 45°** (`player_movement.gml:41`) | ±$18 = 33.75° | `PHYS_SLIP_ANGLE = $18` (and the exact S3K `addi.b #$18 / cmpi.b #$30` instruction form, `player_ground.emp:286-289`) | high |
| 16 | Slip **downhill nudge** | **absent** — Harmony only sets `control_lock = 30`, gsp untouched | gsp ± 0.5 shoved downhill | `PHYS_SLIP_NUDGE = $80` | high. Harmony implements S1/S2-style "lock + fall", not the S3K slide. |
| 17 | Detach angle | **≥ 90°** (`player_movement.gml:42`) | ±$30 = 67.5° | `PHYS_FALL_ANGLE = $30` | high |
| 18 | Grounded push-sensor Y offset at angle 0 | **+4** (`player_movement.gml:45-51`, `wall_h = 4`) | **+8** | we use **+8** (`player_ground.emp:690`) | high — **we are correct, they are not** |
| 19 | Spindash rev cap | **9** (`player_state_spindash.gml:42`) | 8 | `SPINDASH_CHARGE_MAX = $800` = 8 | high (max release speed still 12 either way, because `floor(9/2) == 4`) |
| 20 | Ceiling-landing (reattach) requires \|y_speed\| > 3.0 | **added gate** (`player_collision.gml:85`, `PLAYER_CEIL_LAND_SPD` `player_macros.gml:15`) | no speed gate; band test only | we use the classic band test `(angle+$20)&$40`, no speed gate (`player_air.emp:308-311`) | high |
| 21 | Ceiling reattach angle range | \|angle\| ≤ 140° (`PLAYER_CEIL_RANGE`, `player_macros.gml:16`) | flat-ceiling band $60-$9F bumps, everything else reattaches | ours = classic band | med |
| 22 | Landing conversion adds a magnitude guard `abs(x_speed) <= abs(y_speed/2)` / `<= abs(y_speed)` | `player_collision.gml:58,62` | classic bands are angle-only, no velocity-magnitude precondition | ours is angle-band-only (`player_air.emp:352-381`) | med — effect: fast-horizontal landings on slopes keep `x_vel` instead of converting |
| 23 | Underwater jump strength | `jump_strength *= 0.5` -> **3.25** (`player_handle_physics.gml:73`) | 3.5 | n/a (no water) | high |
| 24 | Underwater jump-release cap | `jump_release *= 0.5` -> **2.0** (`:72`) | stays 4 | n/a | med |
| 25 | Water exit boost | `y_speed *= 1.25` (`player_water.gml:111`) | commonly cited as ×2 | n/a | **low — verify against S3K before copying either number** |
| 26 | Total air timer | **32 s** (`player_water.gml:214`) | 30 s | n/a | med |
| 27 | Air drag has no truncation | `x_speed -= x_speed/32` (`player_control.gml:82`) — float, decays forever | classic is a truncating `div 0.125 / 256`, so it snaps | `asr.w #5 / beq / sub.w` (`player_air.emp:174-179`) — **we reproduce the truncation** | high — **we are more accurate than Harmony here** |
| 28 | Slope factor standing gate | speed-based: `abs(gsp) > 0.125 \|\| control_lock > 0` (`player_control.gml:15`) | S3K gates on slope steepness at rest | angle/factor-based: `PHYS_SLOPE_STAND_MIN = $D` (`player_ground.emp:130-138`) | med — different mechanism, same intent; **verify which matches S3K** |
| 29 | Roll-jump air-control lockout | **absent** — `player_state_jump` applies air input identically from a roll-jump | S3K/S2 lock air control on a roll-jump | `PSTATE_ROLLJUMP` + `AIRF_INPUT_LOCK` (`player_air.emp:64-67,131-133`) | high — **we have it, they don't** |
| 30 | Skid threshold 4.0, roll-start 1.0, spindash decay `rev/32`, walk anim `8-\|gsp\|`, roll/jump anim `4-\|gsp\|` | `player_state_normal.gml:102,41`; `player_state_roll.gml:7,77`; `player_state_spindash.gml:25` | matches S3K | see §6 — **our roll anim base is wrong** | high |

### B.3 Additions that reproduce a classic **quirk**

| # | What | Cite |
|---|---|---|
| 31 | **"Control lock quirk"** — while control-locked on a 45°-90° slope with \|gsp\| ≤ 2.5, pressing *against* the slide sets `gsp = ±deceleration` and flips facing. Explicitly commented `//Control lock quirk`. | `player_control.gml:47-68` |

We do the opposite: `Ground_Move` skips the whole input block while `move_lock != 0`
(`player_ground.emp:508-512`). **Verify against S3K before adopting** — I could not
confirm this quirk exists in S3K, and Harmony gives no source. If it is real, it is
a cheap ~20-byte addition; if not, it is an invention.

### B.4 Actual bugs in Harmony (do NOT copy)

| # | Bug | Cite |
|---|---|---|
| 32 | **Bubble-shield bounce takes the sine of a SPEED.** `x_speed = (dsin(ground_speed) * dcos(ground_angle) + -7.5/(1+underwater)) * dsin(ground_angle);` — `dsin(ground_speed)` is meaningless (a speed interpreted as degrees). | `player_shield_bubble.gml:42-43` |
| 33 | **`static glide_direction = facing`** — GML `static` in a script function initialises **once per program**, not per instance. Persists across level restarts and breaks with two players. | `player_state_glide.gml:9` |
| 34 | **Shield instance existence checked globally**: `if(!instance_exists(obj_shield) && shield != SHIELD.NONE)`. Single-player assumption baked into a framework. | `player_states.gml:43` |
| 35 | **Two admitted hack timers.** `floor_delay = 0; // hacky fix for jittery mode changes` — and it is **never read anywhere** (dead). `ceiling_lock = 0; // hacky fix for collision bugs` — ticked in `player_misc.gml:7`, only written by `player_state_glide.gml:129`, and read... nowhere. Both are dead scaffolds. | `Create_0.gml:16,18` |
| 36 | **Admitted incomplete semi-solid handling**, with the marker left in shipping code: `// If player is going up, disable semi solids [NOTE: THIS IS WHERE THE IMPROVEMENTS WILL HAPPEN FOR 1.1]`. Semi-solidity is decided purely by `sign(y_speed)`, so you cannot drop through by holding down, and a platform you are rising through re-solidifies mid-frame. | `player_collision.gml:36-40` |
| 37 | **Re-entrant state call as an admitted hack**: unrolling calls `script_execute(state)` on the *new* state from inside the *old* state's body, then patches the hitbox. `// A hack` | `player_state_roll.gml:41-48` |
| 38 | **Magic detach constant with a joke justification**: `if (wallCol >= 16) { // detach anyway because josh was like "thats bad"` | `player_state_wallclimb.gml:84-88` |
| 39 | **Player bounds are the CAMERA's limits.** `x = clamp(x, obj_camera.limit_left + 16, obj_camera.limit_right - 16)` inside the movement sub-step loop couples physics to the camera object. Ours reads the ACT descriptor (`Player_BoundsInit`, `player_common.emp:742-756`). | `player_movement.gml:33-38` |
| 40 | **Timer abused as a boolean**: `invincible_timer = 1` held constant while super. | `player_inv_speed.gml:53` |
| 41 | **Physics table rebuilt from a fresh struct literal EVERY FRAME** (9 arrays, 27 floats allocated per frame per player). Ours recomputes only on section change / status events (`Player_RefreshPhysics`, `player_common.emp:233-241`, explicitly documented "NEVER per-frame"). | `player_handle_physics.gml:6-18` called from `Step_1.gml:15` |
| 42 | Pervasive `=`-as-`==` style inside expressions (`if(mov = facing && ...)`, `anim = facing = 1 ? ANIM.LEDGE1 : ANIM.LEDGE2`). Legal GML, but it makes intent unreadable and hides real assignment bugs. | `player_state_normal.gml:119,122,132`; many others |

---

## PART C — Sensors & collision: their model vs classic S3K vs ours

### C.1 Sensor count and placement

| | Classic S3K | Harmony | Ours |
|---|---|---|---|
| Floor sensors | 2 (A, B) at x±x_rad, y+y_rad | **3** (L, M, R) — adds a **centre** sensor (`collision_util.gml:112-165`) | 2 (`Player_SensorSurface .probe_down`, `player_sensors.emp:337-345`) |
| Ceiling sensors | 2 (C, D) | 3 (same routine, `COLLISION_MODE.CEILING`) | 2 (`Player_SensorCeiling`) |
| Push sensors | 2 (E, F) at x±10 | 2 (`wall_w = 10`) | 2 (`PUSH_RADIUS = 10`) |
| Push Y at angle 0 | y + 8 | **y + 4** (`wall_h = 4`) | y + 8 |
| Air push sensors | at y (centre) | at y (`player_collision.gml:26-27`) | at y (`Air_WallProbeLeft/Right`) |
| Air sensors rotate with angle? | no | no (`player_collision.gml:19-23` forces FLOOR mode airborne) | no — `clr.b Player_Quadrant` before the whole air sensor block (`player_air.emp:220`) |

The **third (centre) floor sensor** is Harmony's main sensor-model deviation. Effect:
better behaviour on pointy terrain and narrow ledges where both outer sensors miss.
Cost: +50% floor probes, every frame, every sub-step. Their tie-break: L wins,
then M, then R (`collision_util.gml:140-155`).

### C.2 Angle handling — the big architectural difference

**Harmony has no angle table.** `collision_get_angle(px,py,mode,plane)`
(`collision_util.gml:61-102`) takes the two edges of the 16px cell the sensor is in,
runs a *full collision distance query at each edge*, and returns
`point_direction(ax,ay,bx,by)` — i.e. the angle is **atan2 of two height-map
samples**. Every angle query therefore costs **two extra full probes plus an atan2**,
and `collision_active_sensor` calls it up to 3 times per pair.

Consequences:
- The angle can never disagree with the height map (removes an entire authoring-error class).
- Angles are continuous floats, not 256-step binary — the visual-rotation code
  relies on that (`player_visual_angle.gml`).
- Flat-detection is a heuristic patch on top: *"Make angle flat if the results of the
  height are also flat"* — if two of the three sensor heights are equal, the angle is
  forced to the mode cardinal `90 * mode` (`collision_util.gml:157-162`).

**Ours** stores a per-attr angle byte (`AngleTable`) with an **odd flag** meaning "no
usable angle", plus a **divergence snap**: if `|new_angle - SST_angle| >= $20` the
quadrant cardinal is substituted (`player_sensors.emp:375-393`). That is the S.C.E.
model and it costs zero extra probes. Their approach solves the same problem from
the data side; ours solves it from the policy side, far cheaper on 68K.

### C.3 Ground collision modes / quadrants

Harmony's `mode = round(ground_angle / 90) % 4` (`player_util.gml:7`) with
`x_dir = sin(90*mode)`, `y_dir = cos(90*mode)` — algebraically identical to our
`(angle + $20) >> 6` quadrant (`player_common.emp:294-298`), but computed with
trig instead of a shift.

**`PLAYER_ALT_COLLISION_MODE`** (`player_collision.gml:194-234`) is the interesting
part: instead of deriving the mode purely from the angle byte, it fires two extra
probes at the player's *lower corners* in the adjacent wall directions, and switches
mode when a probe reports overlap **and** the angle delta is under
`PLAYER_SLOPE_TOLERANCE` (45°). This makes wall/loop transitions driven by actual
geometry rather than by whatever angle the last floor pair happened to return.
Cost: 2 extra probes + 2 extra angle queries (which are themselves 2 probes each) =
**6 extra probes per grounded frame.**

### C.4 The height-map data model (near-identical to ours)

`_tile_get_height` / `_tile_get_width` (`collision_util.gml:176-366`) implement the
**same two-cell model** we do: query the primary cell; if it is full (16) probe one
cell back, if it is empty probe one cell forward, and offset the result by ∓16.
Per-column signed byte, positive = solid from one edge, negative = hanging run from
the other, 16 = full. `_tiledata_get_height` resolves flip/mirror/rotate at query
time by index-flipping and negating (`:378-431`).

This is exactly the S.C.E. `FindFloor`/`FindWall` model our `probe_core` comptime fn
stamps (`player_sensors.emp:103-215`). **Independent convergence on the same design —
good confirmation.**

Difference: Harmony **bakes the height maps at runtime** by scanning the collision
tileset's pixels (`game_init_collision.gml:14-51`, with `show_debug_message(...
"height map baking took: {0} ms")`). We bake offline in `tools/collision_pipeline.py`.
Ours is obviously right for cartridge; theirs is right for an editor-driven workflow
where the artist edits the collision tileset image directly. Worth remembering if
Aurora ever wants a live-edit path.

### C.5 Layer / plane switching

Harmony uses **four separate tilemap layers**: `CollisionMain`, `CollisionSemi`,
`CollisionA`, `CollisionB` (`game_init_global_variables.gml:50`). Every probe
iterates all four and takes the **minimum** distance, skipping layers by the
`plane` (A/B) and `semi_solid` arguments (`collision_util.gml:16-49`).

So: solidity class is expressed as **layer membership**, decided per-probe.
Cost: 2-4 tile lookups per sensor.

**Ours** expresses it as a **solidity attr byte + class mask**
(`SOLID_TOP` / `SOLID_LRB`, gated by a single `and.b d6,d0` in
`player_sensors.emp:179-184`) — one lookup, one AND. **Ours is strictly cheaper and
equally expressive.** Their model does buy one thing: a semi-solid can have a full
height map independent of the main layer at the same cell. Ours can't (one attr per
cell per layer). Not worth 4× the probes.

---

## PART D — Shield architecture

### D.1 The mechanism

- `shield` is an int enum (`SHIELD.NONE = -1, NORMAL, FIRE, ELECTRIC, BUBBLE, END`,
  `game_enums.gml:93-102`).
- `shield_list` is an array of script references built in `Create_0.gml:111-116`.
- `player_states.gml:29-35` dispatches: `script_execute(shield_list[shield])` with a
  bounds check.
- `shield_state` (one int on the player) is the shield's private sub-state — used as
  idle(0)/active(1) by fire, electric and bubble.
- `shield_obj` is a **separate instance** carrying the graphic + its own animator;
  each shield script sets its own `depth` relative to the player *per frame*
  (in front / behind, cycling with the animation frame for fire and electric —
  `player_shield_fire.gml:14`, `player_shield_electric.gml:9-16`).
- `player_set_shield()` (`player_util.gml:220-236`) is the one entry point that resets
  the graphic transform + animator on change.

Bodies: `player_shield_normal.gml` (10 lines, anim + depth),
`_fire.gml` (56, air dash 8 px/frame + camera lag + destroyed underwater),
`_electric.gml` (48, double jump `y_speed = -5.5` + 64px ring magnet),
`_bubble.gml` (57, bounce down `y_speed = 8` then a ground bounce),
`_null.gml` (3, `exit;`).

### D.2 Is the abstraction boundary good?

**Partly.** The dispatch table itself is fine and would map to a 68K `offsets` table
directly. But the boundary **leaks in four directions**:

1. **Damage absorption is not in the shield** — `player_util.gml:59-63` hardcodes
   "if `shield != SHIELD.NONE`, drop the shield and eat the hit".
2. **Water interaction is not in the shield** — `player_water.gml:130-141` hardcodes
   "fire and electric die underwater, bubble suppresses drowning" by enum comparison,
   in the water module.
3. **The double-jump gate is not in the shield** — `player_states.gml:72` resets the
   dropdash timer with an inline expression enumerating which shields block it.
4. **Insta-shield is not a shield at all** — it lives in `player_state_jump.gml:29-42`
   with its own object, its own invincibility timer, and its own collision helper
   (`player_insta_shield_collide`, `player_util.gml:202-214`).

So `shield` identity is enum-tested in **at least five files**. Adding a fifth shield
means editing all of them. That is exactly the failure mode a dispatch table is
supposed to prevent.

Every shield's action is also **`character == CHAR_SONIC`-gated inline**
(`_fire.gml:20`, `_electric.gml:20`, `_bubble.gml:18`) — a second cross-cutting
condition duplicated three times.

### D.3 What we should do instead

A **shield descriptor** record per shield, one table, e.g.:

```
struct ShieldDef {
    per_frame:   ptr,   // animation/depth/passive (ring magnet)
    on_action:   ptr,   // action button pressed while airborne (0 = none)
    on_damage:   ptr,   // 0 = default "lose shield, no ring loss"
    flags:       u8,    // DESTROYED_BY_WATER | PREVENTS_DROWNING | SONIC_ONLY | MAGNETIC
}
```

`player_water` then tests `flags & DESTROYED_BY_WATER`, the hurt path calls
`on_damage`, and the insta-shield becomes just another row with `on_action` set and
`per_frame = 0`. Cost on 68K: one 8-byte record × 5, three indirect calls that are
mostly `PHook_Null`-style rts. This is the same shape as our
`PState_EnterHooks`/`ExitHooks` tables and would slot in cleanly.

---

## PART E — Water, and per-character variation

### E.1 Water (`player_water.gml`, 228 lines)

Structure — everything is in one per-frame function, driven by proximity to a
`par_water` instance (`:9-19`, including a `with(par_water) ... break` scan every
frame, `:12-19`):

- **Surface running** (`:32-58`): if the player's feet are within ±8px of the water
  line, grounded, `|gsp| > 6`, and `y_speed >= -0.1`, then snap `y = waterY -
  hitbox_h - 1`, force `ground_angle = 0`, and set the orthogonal flag `water_run`.
  The flag then suppresses skid (`player_state_normal.gml:102`), suppresses the
  detach check (`player_collision.gml:170`), and gates the ground-snap
  (`player_collision.gml:180`). **This is a good pattern: a surface-riding mode
  expressed as a flag that composes with the running state, not as a new state.**
- **Entry** (`:70-92`): `x_speed *= 0.5`, `y_speed *= 0.25`, splash, `underwater = true`.
- **Exit** (`:105-125`): `y_speed *= 1.25` (see B-25), `underwater = false`.
- **Physics multipliers** are applied in `player_handle_physics.gml:64-74`, not here —
  the water module only owns the flag. Good separation.
- **Aquaphobia + air timer** (`:127-228`): fire/electric shields destroyed, bubble
  shield suppresses the timer entirely (`air = 0`), bubble spawning with a randomised
  delay, warning SFX at 6/12/18 s, drowning music at 20 s, countdown bubbles 5..1 at
  22/24/26/28/30 s, drown at 32 s.
- **Water pools** (`obj_water_pool`) are handled as a bounded rectangle with separate
  vertical and horizontal entry/exit tests plus a neighbour check so two adjacent
  pools do not flicker the state (`:96-105`). Fiddly but a real problem solved.

Portability: every multiplier is a power-of-two fraction except the exit boost
(1.25 = 5/4, still shift-friendly). The air timer is frame counting. **All of this
ports to 68K without a single divide.**

### E.2 Per-character variation — how it's expressed

Four distinct mechanisms, in decreasing quality:

**(1) Stats as struct-of-arrays indexed by `character`** — good.
`player_handle_physics.gml:6-18`:
```
var physics_table = {
    accel : [0.046875, 0.046875, 0.046875],   // Sonic, Tails, Knux
    jump_strength : [6.5, 6.5, 6.0],
    ...
};
x_accel = physics_table.accel[character];
```
Only two values actually differ across the roster (`jump_strength` for Knuckles,
and the super-form row). **The super form is a whole-table replacement**
(`:20-31`) — a clean idea: super/water/speed-shoes are *alternate rows composed into
the effective table*, not scattered `if(super)` tests. This validates our
`Player_RefreshPhysics` design (`player_common.emp:233-241`) and tells us exactly how
to extend it: additional base rows + a compose step, still event-driven.

The bad part is only *when* it runs: **every frame** (§B-41).

**(2) Hitboxes / camera offsets as arrays** — good.
`Create_0.gml:133-149`: `hitbox_normal`, `hitbox_rolling`, `camera_rolling_offset`.
Note Tails' standing box is 9×15 vs Sonic/Knux 9×19, while all three roll at 7×14.

**(3) Animation registry rebuilt per character** — acceptable.
`player_animation_list.gml:50-159`: one big `switch(global.character)`. **The `ANIM.*`
ids are shared**; only the sprite bindings and durations differ. Super forms swap
their subset of the registry in place (`:53-74`), and `player_animation_list()` is
re-called on transform (`player_state_transform.gml:6`). This is structurally the
same as our `SST_anim_table` per-character pointer + shared `ANIM_*` ids
(`sonic.emp:27`, `sonic_anims.emp`) — **ours is better** because the table is ROM
data selected by pointer rather than a runtime rebuild.

**(4) Ability entry as inline `if (character == ...)` inside shared states** — bad.
`player_state_jump.gml`: line 29 (`CHAR_SONIC` insta-shield), line 59 (`CHAR_SONIC`
dropdash), line 78 (`CHAR_TAILS` fly), line 87 (`CHAR_KNUX` glide). Four character
branches in one shared state body, plus more in `player_state_lookup.gml:7`,
`player_state_roll.gml:5`, `player_state_normal.gml:54-98`, `player_states.gml`.
There is **no per-character "what does the action button do in the air" function
pointer.** Adding a fifth character means editing every shared state.

**This is the single strongest validation of our spec §3.1 inversion**
("characters contribute asset/physics data + ability states — never forks inside
shared routines", `player_common.emp:5-8`). Harmony is the counter-example: they
have the data tables right and the control flow wrong.

The right shape, which our `Player_States` table already almost supports, is a
**per-character dispatch table** — our closeout note already flags this
(`player_spindash.emp:35-40`: *"per-character dispatch-table indirection is future
work for the second character"*). Harmony confirms it is the correct call.

---

## PART F — Ranked structural ideas, with 68K verdicts

Ranked by (value to us) × (cheapness on 68K).

### 1. Immediate-mode capability flags — **[WORTH TAKING]**
`player_states.gml:5-15` + every state's opening lines.
Reset a flags byte to a default each frame; the state re-asserts what it needs;
downstream systems (`player_control`, `player_collision`, `player_movement`,
`player_direction`, hitbox, hazard response) just read the bits.
Kills the entire "state forgot to clean up on exit" bug class, and makes
"cutscene / spring / transform freezes X" trivially expressible.
**68K:** one `move.b #DEFAULTS, PlayerV.caps(a0)` at the top of dispatch, `bclr`/`bset`
in states. ~1 byte of SST (we have `status_secondary` reserved and `even_pad` free).
Cost is single-digit cycles. **Do it.** It composes with, and does not replace, our
enter/exit hooks — hooks own *persistent* state (radii, y-shift, ST_ROLLING), caps own
*per-frame* permissions. That split is cleaner than either codebase has today.

### 2. A post-dispatch cross-cutting condition block — **[WORTH TAKING]**
`player_state_conditions()` (`player_states.gml:57-105`).
One place for transitions that belong to no single state: forced-roll entry, look-down
trigger, spring override, death-pending, cutscene lock, timer resets.
**68K:** a plain `jbsr` right after the `jsr (a1,d1.w)` in `Player_Main`
(`player_common.emp:345`). Free. We currently scatter these (e.g. the look-down
condition lives implicitly in `Player_Animate`, which is supposed to be *read-only*
but already mutates `skid_latch`/`getup_timer` — a smell this would fix).

### 3. `force_roll` as a first-class flag — **[WORTH TAKING]**
`player_state_roll.gml:39,56,62-68`, `player_state_jump.gml:5`,
`player_state_spring.gml:9`, `player_movement.gml:42`.
S-tubes / roll-tunnels need "you are rolling and cannot stop, cannot jump, and get
pushed to 2.0 if you stall on flat ground". Harmony threads one boolean through five
sites and it works. We have `PHYS_ROLL_FORCE_MIN = $200` reserved with no flag.
**68K:** one status bit. Trivial.

### 4. `water_run` as an orthogonal flag, not a state — **[WORTH TAKING]** (design note)
`player_water.gml:32-58` + its three consumers. Surface-riding composes with running
rather than forking it. Same reasoning applies to any future "on a conveyor / on ice /
in a tube" modifier. Bank the pattern now so we don't reach for a state later.

### 5. Physics as composable **rows**, super/water as row replacement — **[WORTH TAKING]**
`player_handle_physics.gml:20-31`. Our `Player_RefreshPhysics` copies one ROM row;
Harmony shows the extension shape: alternate base rows (super), then multiplicative
modifiers (water ×0.5, shoes ×2) composed on top, all at event time.
**68K:** ×0.5 and ×2 are `asr`/`asl` on 8 words. Keep `Player_RefreshPhysics`
event-driven — do **not** copy their per-frame rebuild (§B-41).

### 6. Config flags as era/feature toggles — **[WORTH TAKING]**
`game_config.gml`, `game_init_global_variables.gml:64-78`.
`use_spindash / use_peelout / use_dropdash / use_airroll / use_insta_shield /
rotation_type / camera_type`. We already do this with build-time `if DEBUG == 1`;
extending it to *behavioral era* switches gives cheap A/B testing of "S3K-faithful vs
Mania" without forking code.
**68K:** comptime `const` + `if` — zero runtime cost, dead code not emitted.
**Caveat: their own example shows the failure mode** — `global.no_skid_state` is a
toggle that does nothing (§B-10). If we add a switch, add an `ensure` that it is read.

### 7. Visual angle decoupled from collision angle, with a deadzone — **[WORTH TAKING]**
`player_visual_angle.gml`. Their `rotation_type == 1` is the Genesis-representable
mode: `visual_angle = round(ground_angle/45)*45`, **forced to 0 when
`ground_angle < 34° or > 326°`** (`:41-44`), and **forced to 0 whenever the current
animation is not walk/run/maxrun** (`:62-65`). Both rules are worth copying verbatim
into whatever drives our reserved `flip_angle`.
The airborne decay (`visual_angle` walks back to 0 at 2.8125°/frame, `:50-58`) maps to
`±2` per frame on a binary angle — and we **already do exactly that** for the
collision angle (`player_air.emp:199-210`), so the same idiom applies.
Their smooth modes (0 and 2) use
`visual_angle += (((rot - visual_angle + 540) mod 360) - 180) / 4` — shortest-path
interpolation. In binary angles that is `(target - cur) as signed byte, asr #2`.
**Cheaper for us than for them.** But smooth rotation is not representable in sprite
mappings, so it stays theoretical.

### 8. Composable transition predicates — **[WORTH TAKING]** (partly have)
`player_check_jump()` / `player_check_roll()` returning "I fired, caller should exit".
We already share `Player_Jump` between Ground and Roll. Extend the idiom to the roll
start (currently duplicated in `PState_Ground` `player_ground.emp:150-158` and
`Air_LandState` `player_air.emp:475-485` with the same three-part gate written twice).

### 9. Attachment driven by the parent's animation id — **[WORTH TAKING]** (design)
`player_handle_tails.gml`: Tails' twin tail is a second animator whose sprite, offset
(x,y) and rotation are selected by a `switch` on the **parent's current animation id**,
with a `default:` that hides it. Clean, table-shaped, and directly relevant — Tails'
tail rendering is a named legacy bug in `sonic_hack` (root CLAUDE.md "Known Issues").
Convert the switch to a table indexed by `ANIM_*` and it is a ROM lookup.
**68K:** the rotation (`darctan2(y_speed*facing, -x_speed*facing)`, `:47`) is the only
expensive bit — needs a coarse atan2. Use an 8- or 16-step octant table.

### 10. Ledge/teeter side selection + on-object teetering — **[WORTH TAKING]** (small)
`player_state_normal.gml:112-123`: three probes (centre, left foot, right foot) at
`> 14px` choose between two *different* teeter animations by which side is hanging,
and the `on_object` case uses `ledge`/`on_object_count` instead of terrain.
We have the on-object case (`player_sensors.emp:488-516`) but a single `ANIM_BALANCE`.
Cheap upgrade when the art exists.

### 11. Camera roll offset compensating the curl y-shift — **[WORTH TAKING]** (verify)
`Create_0.gml:149` (`camera_rolling_offset = [5,1,5]`), applied in `player_util.gml:457`.
Sonic's 5px is exactly our `CURL_Y_SHIFT`. **Action: confirm our camera compensates
for the ±5px `y_pos` step in `PHook_EnsureBall`/`EnsureStanding`
(`player_common.emp:669,679`) — if it doesn't, the view jerks 5px on every curl/uncurl.**

### 12. A `null` state — **[WORTH TAKING]** (trivial)
`player_state_null.gml` — 3 lines. Needed for title cards, cutscenes, act transitions,
level-end. We will need it; a `PSTATE_NULL` row pointing at an `rts` costs 2 bytes.

### 13. Runtime-baked height maps from the collision tileset image — **[REJECT for the ROM, NOTE for Aurora]**
`game_init_collision.gml:14-51`. Right idea in the wrong place for a cartridge — we
bake in `tools/collision_pipeline.py`. Worth remembering if Aurora ever wants
live collision editing: the algorithm (scan the mask sprite column-wise, emit the
signed byte) is the same one our tool implements.

### 14. Angle derived from the height map instead of an angle table — **[INTERESTING BUT COSTLY ON 68K]**
`collision_util.gml:61-102`. Genuinely eliminates angle/height authoring
disagreement. But it costs **2 extra full probes + an atan2 per angle query**, and
`collision_active_sensor` queries up to 3 times per pair.
**68K feasibility:** the x-span is a fixed 15px, so atan2 collapses to a 1-D
`arctan(dy/15)` table indexed by the height delta — that part is cheap. The two extra
probes are not: our probe core is already the hot path.
**And we don't need it** — the odd-flag + `|Δangle| >= $20` divergence snap
(`player_sensors.emp:375-393`) covers the same failure mode at zero extra probes.
**Verdict: understand it, don't take it.**

### 15. Wall-probe-driven collision mode switching (`PLAYER_ALT_COLLISION_MODE`) — **[INTERESTING BUT COSTLY ON 68K]**
`player_collision.gml:194-234`. Mode changes decided by real geometry at the lower
corners rather than by the angle byte, gated on a 45° tolerance. This is their answer
to loop/wall-transition jitter (the same problem their dead `floor_delay` hack timer
was originally for, §B-35).
**68K:** +6 probes per grounded frame (2 wall probes, each needing an angle query =
2 more probes each). Too expensive as a default.
**Cheaper variant worth considering:** keep angle-driven mode selection, but add the
45°-tolerance *acceptance test* — which we effectively already have as the
divergence snap. **Verdict: our existing policy is the cheap 80% of this.**

### 16. Three floor sensors (L/M/R) with "two agree → force cardinal" — **[INTERESTING BUT COSTLY ON 68K]**
`collision_util.gml:112-165`. +50% floor probes for better pointy-terrain behaviour.
Their flat-forcing rule (`:157-162`) is a *heuristic replacement* for our odd-flag —
we get the same result from authored data for free.
**Verdict: revisit only if OJZ terrain shows a concrete 2-sensor failure.**

### 17. Sub-stepped movement + collision (`steps = 1 + |v|/14`, cap 4) — **[REJECT]**
`Step_1.gml:34,44-55`, `game_config.gml:14-18`.
Reason: our `PHYS_GSP_CAP = $1000` bounds motion to 16px/frame, which is exactly the
collision cell size, and our probe core already reads two cells. Tunneling is
structurally bounded. Sub-stepping would multiply our sensor cost by up to 4× to
solve a problem we do not have — and their own need for it comes from
`max_speed = 24` (§B-12), a cap we deliberately do not use.
(The `/14` would also need replacing with `>>4`, but that is moot.)

### 18. Input read once per frame into `hold_*` / `press_*` with a global disable — **[HAVE, equivalent]**
`player_get_input.gml`. We read `Ctrl_1_Press` once into d6 in `Player_Main`
(`player_common.emp:259`). Their `input_disable` blanket + the second blanket for the
shell menu (`:50-71`) is duplicated code; if we add an input-disable it should be one
mask applied once.

### 19. Generic per-instance value-history recorder — **[HAVE the concrete version]**
`Create_0.gml:178-197`, `player_util.gml:267-314`. A named-field ring used for
after-images (speed shoes / super), including Tails' tail fields. We already have
`Player_Pos_Ring` / `Player_Stat_Ring` (`player_common.emp:356-368`). Ours is fixed
to 4 fields; if after-images ever need sprite+frame we'd extend the stat ring rather
than build a registry. Their generality is a GML luxury.

### 20. Input applied AFTER movement/collision — **[REJECT]**
`Step_1.gml:44-58`: `player_control()` (input→speed) runs after the movement loop,
so input is one frame late. The classics do input→move→collide in one pass and so do
we (`PState_Ground`: spindash → jump → slope → `Ground_Move` → integrate → floor pair).
**Do not copy their frame order.**

---

## PART G — Honest assessment: what we have vs what we don't

### G.1 Where we are already ahead of Harmony

- **Enter/exit hook tables with a single transition writer** (`Player_SetState`,
  `player_common.emp:553-563`). Harmony has none; its hitbox is keyed off the
  *animation*, and every transition site hand-patches its consequences.
- **Roll-jump air-control lockout** (`PSTATE_ROLLJUMP` / `AIRF_INPUT_LOCK`).
  Harmony does not have it at all.
- **Uncurl ceiling-clearance guard** (`PState_Roll` `.unroll_check`,
  `player_ground.emp:458-487`, and `Air_LandState`'s A7 guard,
  `player_air.emp:486-499`). Harmony can uncurl into a ceiling.
- **Air drag truncation** matching the classic `div`/`asr` behaviour (§B-27).
- **S3K slip with the downhill nudge and the exact `addi.b #$18 / cmpi.b #$30`
  band form** (§B-15/16/17). Harmony's is S1/S2-shaped and missing the nudge.
- **Correct roll-start L/R veto** (§B-14) and **correct push-sensor +8** (§B-18).
- **Event-driven physics table** rather than a per-frame rebuild (§B-41).
- **Player bounds decoupled from the camera** (§B-39).
- **Single-lookup solidity classes** rather than 4-layer minimum scans (§C-5).
- **Comptime-stamped probe cores** — four directional probes from one `probe_core`
  fn (`player_sensors.emp:103-232`) with direction inversions resolved at assembly
  time. Harmony pays the mode dispatch at runtime on every probe.
- **Build-time invariants** — `ensure(Player_States.count == PSTATE_COUNT)`,
  the slope-constant shift-form asserts, the anim-ordinal guards in `sonic_anims.emp`.
  Harmony has zero build-time validation and, as a direct result, ships a dead config
  flag (§B-10) and two dead hack timers (§B-35).

### G.2 Two concrete fidelity fixes for us, found by this comparison

**(a) Roll animation duration base is wrong.**
Harmony: walk/run use `max(0, 8 - |gsp|)` (`player_state_normal.gml:41,63`);
**roll uses `max(0, 4 - |gsp|)`** (`player_state_roll.gml:7`) and the jump
animation latches `floor(max(0, 4 - |gsp|))` **once at jump time**
(`player_state_jump.gml:124`). That matches the classic (walk base 8, roll base 4).
Ours computes **one** hold for all three DUR_DYNAMIC scripts:
`Player_Animate`, `player_common.emp:403-411`:
```
d4 = max(0, ($800 - |gsp|) >> 8)     // == max(0, 8 - |gsp|)
```
and feeds it to Walk, Run **and Roll** (`sonic_anims.emp:37-39`).
**Effect: our roll/ball animation runs at half the classic speed at low speeds.**
Fix: derive a second hold `max(0, ($400 - |gsp|) >> 8)` for the ball path
(`Player_Animate` `.ball`, `player_common.emp:425-427`) — it is 4 instructions, and
the ball path currently doesn't touch d3 at all.

Secondary: they **latch** the jump anim speed at launch; we recompute from `gsp`
every frame, and `gsp` is stale in the air (nothing updates it airborne except
wall-run engage, `player_air.emp:249`). Latching at `Player_Jump` would be more
faithful and cheaper.

**(b) Verify camera compensation for `CURL_Y_SHIFT`** — see §F-11.

### G.3 Where we are genuinely behind (and it's fine — it's sequencing)

Everything in §A.2 marked **[MISSING]** that is not a `[CHOICE]`:
hurt/knockout, death, drown, water + underwater physics, rings, shields (all four),
insta-shield, invincibility, speed shoes, super form, spring state, null state,
Tails, Knuckles and the per-character dispatch indirection, forced roll, water
running, visual sprite angle, look/duck camera pan.

That is the correct order of business — we have the *physics core* and the *state
machine spine* and they are in better shape than Harmony's. What is absent is content
systems, and Harmony is a good checklist for them.

Two reserved fields to note as debt: `look_offset` and `flip_angle` are declared in
`PlayerV` (`player_common.emp:77,85`) and pinned to 0. `getup_timer` has a working
mechanism with no in-game trigger (`player_common.emp:486-492`). Harmony has real
implementations for the first two worth reading when we get there.

### G.4 One structural gap worth naming now

Our `Player_States` / `PState_EnterHooks` / `PState_ExitHooks` tables are **global,
not per-character** — `player_spindash.emp:35-40` already flags this. Harmony's
counter-example (§E.2 mechanism 4) shows the cost of deferring it: four `if(character
== ...)` branches accumulate inside one shared state before anyone notices.

Recommendation: when the second character lands, do the indirection **first**
(a per-character pointer to a state/hook table triple in the character's data block,
alongside `Ani_Sonic` / `PhysTable_Sonic` / `Map_Sonic`), *before* writing any Tails
code. That keeps spec §3.1 honest.

---

## PART H — 68K feasibility notes on their float dependence

| Harmony construct | Float-dependent? | 68K mapping |
|---|---|---|
| All physics constants | **No** — every one is n/256 | direct 8.8: 0.046875→$C, 0.5→$80, 0.21875→$38, 6.0→$600, 6.5→$680, 4.0→$400, 0.0234375→$6, 0.078125→$14, 0.3125→$50, 0.125→$20 |
| `dsin/dcos(ground_angle)` | degrees, float | our 256-step `GetSineCosine` + sine table |
| `math_uangle(a)` = `a<180 ? a : 360-a` | no | `abs` of the signed angle byte |
| `math_approach(v,t,step)` | no | `add`/`sub` + `bcc` cross-zero clamp — we already use this shape |
| `point_direction(ax,ay,bx,by)` (angle derivation) | **yes, atan2** | dx is a fixed 15 → 1-D arctan table indexed by dy. Feasible but see §F-14 |
| `darctan2(y_speed*f, -x_speed*f)` (Tails' tail) | **yes, atan2** | coarse octant table (8 or 16 steps); the tail art is low-res anyway |
| `distance_to_object(o) < 64` (electric magnet) | **yes, sqrt** | box test `|dx|<64 && |dy|<64`, or Manhattan `|dx|+|dy| < 90`. No mulu needed |
| `steps = min(1+|x/14|+|y/14|, 4)` | division by 14 | moot — we reject sub-stepping (§F-17) |
| Peelout release `2 + rev/2.9` | **division by 2.9** | `(rev * 88) >> 8` ≈ rev/2.909, or an 8-entry table. Only if we ever take peel-out |
| Spindash pitch `1 + pitch/13`, decay `pitch/28` | division | audio-only; our SFX has no pitch ramp today |
| Spindash rev decay `rev - rev/32` | no | `asr.w #5` + `sub.w` — **we already do exactly this** (`player_spindash.emp:71-73`) |
| Air drag `x - x/32` | no | `asr.w #5` — we do it, with the truncation they lack (§B-27) |
| `x*0.5, y*0.25, y*1.25` (water) | no | `asr #1`, `asr #2`, `(v + (v>>2))` |
| Glide accel 0.015625 / 0.046875, angle approach 2.8125 | no | 4/256, 12/256, 720/256 |
| Visual angle `(((t-c+540) mod 360)-180)/4` | shortest-path float | **cheaper in binary angles**: `(t - c)` as a signed byte, `asr #2`. No mod needed |
| Animation durations 0.2 / 0.4 / 0.6 | fractional frame advance | our integer `hold` + `DUR_DYNAMIC`; their `animation_set_duration(max(0, 8-|gsp|))` is **literally our formula** |
| `sign()` returning 0 | yes at 0 | classic 68K `tst`/`bpl` treats 0 as positive — note the divergence at gsp == 0 in their roll slope test (`player_state_roll.gml:20`) |

**Bottom line: Harmony's use of floats is almost entirely cosmetic.** The physics is
8.8 written in decimal, and the only genuinely float-dependent parts are the angle
derivation (§F-14, which we reject), Tails' tail rotation (needs a coarse atan2), and
the ring magnet's distance check (trivially replaced by a box test).

---

## Appendix — file map for follow-up

```
Core loop / dispatch    objects/obj_player/{Create_0,Step_1,Step_2,Draw_0}.gml
                        scripts/player_states/player_states.gml
Physics                 scripts/player_handle_physics, player_control, player_movement
Collision               scripts/player_collision, collision_util, game_init_collision
                        scripts/player_util/player_util.gml (player_mode, hitbox, solid reaction)
States                  scripts/player_state_*/
Shields                 scripts/player_shield_*/
Water                   scripts/player_water/player_water.gml
Presentation            scripts/player_direction, player_visual_angle,
                        player_animation_list, player_handle_tails
Config                  scripts/game_config/game_config.gml
                        scripts/game_init_global_variables/...:64-78
                        scripts/player_macros, game_enums, game_macros
Empty/dead              scripts/player_hitbox/player_hitbox.gml  (0 bytes — the real
                        _player_hitbox lives in player_util.gml:436)
```
