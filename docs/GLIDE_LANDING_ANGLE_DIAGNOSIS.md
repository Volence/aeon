# Knuckles "keeps speed after a glide" — diagnosis

> **CORRECTION (2026-11-17, review before landing).** This doc's forensics hold: the F1 data fault, the arithmetic that reproduces the saved frame, and the `Glide_Collide` site. Its framing does not. It treats the grounded divergence rule (`|Δ| >= $20` → cardinal) as the policy every floor consumer should apply, and the glide as the outlier. S3K applies that rule only on the ground (`Player_Angle`, sonic3k.asm:18854). Every airborne landing, the glide included, takes the angle raw with only the odd flag resolved (`Sonic_CheckFloor` :19888-19893; `loc_11F6E` :24082). Our ordinary air landings using the grounded rule was itself a bug, fixed in `f136c486` (2026-09-26, `Player_SensorLand`). Three consequences. The "jump/fall onto the tile is immune" discriminator (§2) no longer holds on master. The "divergence half" fix (§7 option 3) was ruled out by the owner and is not S3K-faithful. The defect was the data (F1), now fixed by the RULE A gate plus `fde35b2f`/`ccc356c7`, plus the odd-flag gap, now CHAR-9 (`docs/2026-09-09-BUGS-archived.md`). §6's predicted byte `$01` is stale: the shipped tables carry `$FF`, and CHAR-9's TAG-A/B/C supersede TAG-3.

**Reported (owner, 2026-08-28):** *"When you glide as Knuckles, stop gliding, then hold down the
glide button, sometimes Knuckles keeps speed going in that direction."* Owner saved the stuck
state as `s4.debug.state1` (2026-08-28 14:38).

**Status: DIAGNOSED, NOT FIXED.** The mechanism is identified, the trigger condition is named,
and every byte of the saved frame is reproduced from it arithmetically. The fix is a behaviour
ruling the owner has to make — see "Why this was not fixed" at the end. No engine bytes were
changed by this lane.

**Branch:** `diag/glide-momentum`. No emulator was used (subagent invariant); all evidence is
static decode of the save state's RAM + ROM and of the source.

---

## 1. The defect, in one paragraph

`Glide_Collide` (`games/sonic4/player/player_glide.emp:380`) is the **only** floor consumer in the
engine that writes `angle(a0)` from a **raw** `Collision_ProbeDown` result. Every other consumer
takes its angle from `Player_SensorFloor`, which applies an *angle-resolution policy*
(`games/sonic4/player/player_sensors.emp:400-421`): an odd angle byte is the "no usable angle"
sentinel and is replaced by the quadrant cardinal, and so is any angle that differs from the
player's current `angle` by `>= $20`. The OJZ act contains collision cells whose **heightmap is a
completely full 16x16 block but whose angle byte is `$E0`** (a 45-degree slope). Walking, jumping
or falling onto such a cell is harmless — the resolution policy rejects `$E0` and substitutes the
flat cardinal `$00`. **Landing on it from a glide installs the raw `$E0` into `angle(a0)`**, and
from that frame on the same divergence guard *protects* the bad value (`|delta| == 0` every
frame), so it never washes out. With `angle = $E0` on flat ground, `PState_Ground` applies a
`-23`/frame slope factor forever and `Player_SlopeRepel` re-arms `move_lock = 30` forever:
Knuckles is pushed steadily left with his input frozen 29 frames in every 30, until he is pinned
against the left act boundary at `x = 16` and can never walk out again.

Two faults compose. Neither alone is visible:

| | fault | owner |
|---|---|---|
| **F1** | a collision attr whose heightmap is uniformly full (`10` x16) carries a non-flat even angle (`$E0`) | collision **data** (donor-derived attr-set) |
| **F2** | `Glide_Collide` writes `angle(a0)` from a raw probe, bypassing the odd-flag + divergence resolution every other floor consumer applies | **code**, `player_glide.emp:380` |

Without F2 the bad angle can never reach `angle(a0)`. Without F1 the bypass has nothing bad to
install.

---

## 2. The "sometimes" — the exact discriminator

Three conditions, all necessary:

1. **The landing must come through the glide family's own terrain pass** (`Glide_Collide`, reached
   from `PState_Glide` and `PState_GlideFall`). A jump landing, a fall landing, a walk-on or a
   spindash all go through `Player_SensorFloor` and are immune on the *same tile, same pixel*.
2. **The tile must carry an even angle byte that differs from the player's current angle by
   `>= $20`.** During a glide `angle(a0)` is `0` (`Ability_KnuxGlide` clears it,
   `player_glide.emp:623`), so any tile angle in `$20..$E0` qualifies. In this act the offending
   tile is the full-solid slab with angle `$E0`; the *other* floor in the same area (attr `$01`,
   angle `$01`) is odd-flagged and therefore safe. **That is why it happens in some places and
   not others.**
3. **Whether the jump button is still held at touchdown selects how visible it is:**
   - **held** -> `PState_Glide.hit_floor`. With `angle = $E0` the quadrant test
     `(angle + $20) & $C0` evaluates to **0**, so the glide calls this ground *flat* and enters
     **`PSTATE_SLIDE` with `x_vel` preserved**. `PState_Slide` reads **no directional input at
     all** — the only exits are releasing the button, friction (`$20`/frame), a wall, or a ledge.
     That is the "keeps speed going in that direction" the owner sees, and holding the button is
     literally its continuation condition.
   - **released before touchdown** -> `PSTATE_GLIDEFALL` -> `.dead_stop`, which zeroes `x_vel`,
     `y_vel` and `ground_speed`. No initial momentum — **but `Glide_Collide` still installed the
     bad angle**, so the slow leftward ground drift follows either way.

   Note the two states disagree about the same byte: **the glide reads `$E0` as flat, the ground
   state reads it as a 45-degree slope.**

---

## 3. Reproduction path through the state machine

Every step is a named branch in the source; nothing here is inferred behaviour.

| # | state | what runs | result |
|---|---|---|---|
| 1 | `PSTATE_AIR`/`JUMP` | fresh jump press + `PBLK_JUMPBUF != 0` -> `Player_Ability` -> `Ability_KnuxGlide` (`player_glide.emp:607`) | `ground_speed = $400`, `glide_angle = -$80` (facing left), **`angle(a0) = 0`** |
| 2 | `PSTATE_GLIDE` | `Glide_Move`: `gsp += 4`/frame (cap `$1800`), `x_vel = cos(glide_angle)*gsp >> 8` = `-gsp` | travelling left |
| 3 | `PSTATE_GLIDE` | `Glide_Collide` (`:314`): single centre `Collision_ProbeDown` while `y_vel >= 0` finds the slab, `d1` = **raw** angle `$E0` | `angle(a0) := $E0` (`:380`) — **the bypass** |
| 4 | `PSTATE_GLIDE` | `.hit_floor` (`:159`): `($E0 + $20) & $C0 == 0` -> `.flat_slide` | -> `PSTATE_SLIDE`, `x_vel` preserved |
| 5 | `PSTATE_SLIDE` | `ObjectMove` -> button-held test -> friction `$20`/frame -> `Slide_Terrain`. **No L/R input is read.** `Slide_Terrain` uses `Player_SensorFloor`, but `|$E0 - $E0| = 0` so the resolution policy now **keeps** the bad angle | coasts left, uncontrollable, for `x_vel^2 / (2*$20)` px |
| 6 | `PSTATE_SLIDE` -> `PSTATE_GROUND` | button released, or `x_vel` crosses zero, or `Player_LevelBound` zeroes `x_vel` at the boundary -> `.get_up` (`:520`): velocities zeroed, `move_lock = $F` | grounded with **`angle = $E0` still installed** |
| 7 | `PSTATE_GROUND`, every frame | slope factor (`player_ground.emp:296-345`): `sin($E0) asr 3` = **`-23`** added to `ground_speed`; `Ground_Move` friction `+$C`; net **`-11`/frame** | pushed left, permanently |
| 8 | `PSTATE_GROUND`, every 30 frames | `Player_SlopeRepel` (`:482`): `(angle + $18) & $FF = $F8 >= $30` and `|gsp| < $280` -> `gsp -= $80`, **`move_lock = 30`** | input frozen 29 frames in 30 |
| 9 | steady state | at `x = 16` `Player_LevelBound` (`player_common.emp:1426-1443`) clamps and zeroes `x_vel` + `ground_speed` every frame, so `|gsp|` can never reach `$280` and step 8 re-arms forever | **pinned; only a jump escapes** |

Step 9 is a genuine trap and it is **S3K-identical code** — `Player_SlopeRepel` (sonic3k.asm:23911)
and `Player_LevelBound` (:23176) both behave the same way in stock S3K. It only becomes reachable
because F1+F2 put a 45-degree angle on flat ground next to a level boundary.

---

## 4. Evidence — the saved frame reproduced arithmetically

Decoded from `s4.debug.state1` (RAM offsets **derived** from `PlayerV` in
`games/sonic4/player/player_common.emp:88+`, `Sst` stride `$50` confirmed by
`Player_1 = $FFFF8ED6`, `Player_2 = $FFFF8F26` in `s4.debug.lst`):

```
x = 16.$0000   y = 829.$C200      x_vel = 0    y_vel = +7 (= +0.027 px/f)
ground_speed = 0                  move_lock = $0013 (19)
player_state = PSTATE_GROUND      angle = $E0     layer 0
status = $02 (ST_XFLIP only)      glide_angle = $80  <-- FULLY LEFT
box 19 x 39 (standing)            anim $05 = ANIM_IDLE   mapping_frame $56
Cheat_Flags = $01 (CHEAT_DEBUG_FLY ARMED)   debug_flag = 0
Player_Chardef = $00011F76 = CharDef_Knuckles
camera = (0, 685)
```

**The runtime collision the engine actually saw**, read out of `Tile_Cache_Collision`
(`$FFFF2580`) with the cache window registers (`Cache_Left_Col`/`Head_Col`/`Top_Row`/`Bottom_Row`/
`Origin_Col`/`Origin_Row` at `$FFFFAD26..$FFFFAD30`), indexed exactly as
`engine/level/collision_lookup.emp` `Collision_GetType` does:

```
cache window: cols 0..79, rows 68..127  =>  world X 0..639, Y 544..1023
y  592  attr $01 x80   (sol $01 TOP-only, angle $01 = ODD -> resolved flat)
y  848  attr $02 x80   <-- the player's feet (829 + 19 = 848)
y  864  attr $02 x80
        attr $02: solidity $03 (SOLID_ALL), angle $E0,
                  heightmap = 10 10 10 10 10 10 10 10 10 10 10 10 10 10 10 10
```

A **uniformly full 16x16 solid cell carrying a 45-degree angle.** 640 px of it, the whole visible
floor of that area.

**The arithmetic closes exactly.** With `angle = $E0`, `sin($E0) = -181`, `cos($E0) = +181`
(`engine/data/sine.bin`), `PHYS_FRICTION = $C`:

| step | value |
|---|---|
| slope factor `sin asr 3` | `-181 >> 3` = **-23** |
| `Ground_Move` friction (`move_lock != 0` -> friction only) | `-23 + 12` = **-11** |
| projection `y_vel = gsp*sin >> 8` | `(-11 * -181) >> 8` = **+7** — **matches the saved `y_vel` exactly** |
| projection `x_vel = gsp*cos >> 8` | `(-11 * 181) >> 8` = **-8** |
| `ObjectMove` | `16.00000 - 8/65536*256` -> integer X = 15 |
| `Player_LevelBound` | `15 < 16` -> clamp X=16, sub=0, **`x_vel = 0`, `ground_speed = 0`** (`y_vel` untouched) |

That is why the frame shows `x = 16.00000`, `x_vel = 0`, `gsp = 0` and a nonzero `y_vel = +7`:
**`y_vel` is the one field the boundary clamp does not touch, and its value is the exact product
the model predicts.** `move_lock = 19` is `30 - 11`, i.e. 11 frames after the last slip re-arm.

**The 64-frame history rings** (`Player_Pos_Ring` `$FFFFE400`, `Player_Stat_Ring` `$FFFFE500`,
`Player_Ring_Index` `$FFFFE600`) show `x = 16, y = 829, status $02` and **zero buttons held for
all 64 frames** — he had stopped trying and was standing still when he saved. `Replay_Record_Buf`
is all zero (no recording was running), so there is no longer input history to recover.

---

## 5. Corrections to the brief

Three decoding points in the dispatch were wrong; two changed nothing, one is material.

1. **`camera x = 0, y = 0` is wrong.** `Camera_X` is 16.16 at `$FFFFA604`, so `$A606` is its
   *subpixel* word; `Camera_Y` is at `$FFFFA608`. The real camera is **(0, 685)** — Knuckles is
   on screen at screen-Y 144, not off the bottom of the world.
2. **`glide_angle $00` is wrong — it is `$80`.** `glide_angle` sits at `Player_1 + $44`, not
   `+$3E` (`+$3E` is `getup_timer`); the `Sst` is `$50` bytes, not `$40`. `$80` = *fully left*,
   which is direct independent confirmation that the last glide was leftward.
3. **`Cheat_Flags = $01` — the debug-fly cheat is ARMED in this session**, so `B` is stolen from
   the jump family everywhere (`Player_Main`'s jump-buffer latch, the ability gate, the glide's
   release test, the slide's hold test). It is not implicated in this bug (`debug_flag = 0`, and
   `Player_DebugEnter`/`Exit` both zero all three velocities), but it means **the owner's glide
   button must be A or C, not B** — worth knowing before trying to reproduce.

Also confirmed, contradicting the brief's lead: **`move_lock` is not the slip/spring channel
misfiring, and the standing box / `PHook_GlideEnter` are innocent.** `move_lock = 19` is the
ordinary slope slip doing exactly what it is written to do, on an angle that should never have
been installed.

One more correction, to the *source tree* rather than the brief: `games/sonic4/data/collision/*.bin`
in the working tree no longer matches the ROM the owner ran (the attr-set is content-addressed and
re-derived every build, and the editor tree is dirty). In the ROM the offending attr is index
**`$02`**; in the current tree the same pathological pair — full `10 x16` heightmap, angle `$E0`,
solidity `$03` — survives at index **`$0E`**. **The fault is still present in the tree**, just
placed elsewhere (a subagent's independent static decode puts it at `x 896..1151, y 256..383` in
section 0).

---

## 6. A second, independent consequence of the same bypass (latent, not yet observed)

`Glide_Collide` also passes through **odd** angle bytes, which are the "no usable angle" sentinel.
The upper floor in this very act is attr `$01` with angle **`$01`**. Gliding onto it installs
`angle(a0) = $01`. `Air_Collide`'s airborne angle decay (`player_air.emp:298-311`) states its
assumption in a comment — *"Angles here are always even (the odd-flag sensors substitute
cardinals), so +/-2 lands exactly on 0"* — and steps by 2:

```
$01 -> bpl -> subq #2 -> $FF      (next frame)
$FF -> bmi -> addq #2 -> $01      (and back)
```

**An odd angle oscillates forever and never decays to 0.** `Glide_Collide` is the one site that
can break that invariant. Not observed in the save state (it holds `$E0`, an even value), so this
is a derived prediction, not a measurement — see TAG-3.

---

## 7. Why this was NOT fixed

The obvious fix — make `Glide_Collide` apply `Player_SensorFloor`'s resolution policy — splits
into two halves with very different risk:

* **The odd-flag half is unambiguously correct** (an odd byte is a sentinel, never a real angle)
  and would close section 6. **But it does not fix the reported bug**: `$E0` is even. Shipping it
  alone would look like a fix and not be one.
* **The divergence half (`|delta| >= $20` -> substitute the cardinal) is what actually closes the
  reported bug**, and it is a real behaviour change: during a glide `angle(a0)` is always `0`, so
  it would reject **every** glide landing on a genuine slope of 45 degrees or steeper and route it
  to `PSTATE_SLIDE` instead of `PSTATE_GROUND`. That is arguably *consistent* — every ordinary air
  landing in this engine already gets the cardinal substituted, because `Air_Collide` decays the
  airborne angle to 0 before `Air_TouchFloor` runs — but it changes how Knuckles lands on real
  terrain, and that is an owner ruling, not a lane decision.

The third option, **fixing the data**, is the one this diagnosis actually points at: a collision
attr whose heightmap is uniformly full cannot be a slope, and nothing checks that today. That fix
lands in `tools/collision_pipeline.py`'s `emit_tables`/`AttrSet.intern` and changes the generated
collision for the whole act, whose inputs are the owner's live editor tree — off limits to this
lane, and it needs sign-off on the resulting collision change.

So: three candidate fixes, one ruling needed. Booked in `docs/DEFERRED_WORK.md`.

### Recommended order

1. **Data gate (highest value, no physics change).** In `tools/collision_pipeline.py`, refuse or
   normalise any attr-set entry whose heightmap is uniformly `$10` (or uniformly `$00`) and whose
   angle is a non-flat even byte. Expectation is **derived from the geometry**, not from a sample:
   a surface with zero rise across all 16 columns has angle 0 by definition. Wire it into
   `tools/gen_collision_data.py`, which `build.sh` already runs before `ojz_strip_gen.py generate`
   (see that file's docstring), so a bad tile fails the build rather than shipping.
2. **`Glide_Collide` odd-flag resolution** (closes section 6; small, no ruling needed).
3. **`Glide_Collide` divergence resolution** — only after the owner rules on 45-degree glide
   landings.

---

## 8. Also found, not fixed (all booked in DEFERRED_WORK)

* **`PState_GlideFall.dead_stop` omits S3K's `move_lock = $F`.** S3K's
  `Knuckles_Fall_From_Glide` sets `move_lock = $F` and `anim = $23` on the *flat* dead-stop landing
  (sonic3k.asm:30941-30944); ours sets neither. Our glide-fall landing is instantly controllable.
* **`ANIM_GLIDE_LAND` and `ANIM_SLIDE_GETUP` are dead data.** The animation scripts exist and are
  `ensure`-pinned in all three character tables, but **no code ever writes either id** — grep for
  the constants finds only the declarations and the ordinal guards. S3K plays both.
* **`Player_SlopeRepel` nudges `ground_speed` by `+/-$80` on the *detach* path; S3K does not.**
  S3K (`sonic3k.asm:23928-23934`) sets `move_lock`, then on the steep branch sets `Status_InAir`
  and returns **without** the nudge; only the shallow branch nudges. Ours always nudges, then
  detaches.
* **`Player_SlopeRepel` tests `move_lock` before `stick_convex`; S3K tests `stick_convex` first**,
  so in S3K a convex-stuck player's `move_lock` never decrements. Inert today (`stick_convex` has
  no writer).
* **`Player_DebugExit` does not clear `move_lock`.** A slip lock survives a free-flight excursion.
* **Stale comment:** `games/sonic4/player/knuckles.emp:11` still says *"HIS ABILITY IS NOT WIRED
  YET. cd_ability points at Ability_None"*. It points at `Ability_KnuxGlide` (`:90`).
* **Inherited S3K quirk, recorded not fixed:** the *slope* glide landing does
  `move.w ground_speed, x_vel` (`player_glide.emp:182`), and `ground_speed` is a **positive
  magnitude** throughout a glide (direction lives in `glide_angle`). So a leftward glide that lands
  on a slope launches Knuckles **rightward** at full glide speed. S3K does exactly the same
  (`Knux_Gliding_HitFloor`, sonic3k.asm:30741, with `Knux_TouchFloor` never recomputing
  `ground_vel`), so this is parity, not a port error — but it is a bug in both.

---

## 9. Runtime TAGs — checks that need the emulator (I could not run one)

**TAG-1 — confirm the trigger, and confirm the immunity, on the same pixel.**
Load `s4.debug.state1`. Jump straight up (A or C — **not B**, the debug-fly cheat is armed) and let
Knuckles land back on the same floor **without gliding**. Read `Player_1 + $1F` (`angle`).
*Expect `$00`* (the resolution policy substituted the cardinal) and *expect the leftward drift to
stop and `move_lock` at `$FFFF8ED6 + $34` to reach 0 and stay 0.* Then glide (jump, then a second
A/C press while airborne) and land on the same floor: *expect `angle` to read `$E0` again and the
drift + `move_lock = 30` cycle to resume.* **That single A/B pair proves or kills the whole
diagnosis.**

**TAG-2 — watch the install.** Breakpoint on `Glide_Collide`'s `move.b d3, angle(a0)`
(`player_glide.emp:380`). On a glide landing, read `d3` at the breakpoint. *Expect `$E0`.* Compare
with `Player_SensorFloor`'s output at the same position (`d1` after `player_sensors.emp:421`),
*expect `$00`.* Same pixel, two answers — that is the bypass, visible directly.

**TAG-3 — the odd-angle oscillation (section 6, predicted not measured).** Glide onto the **upper**
floor (attr `$01`, angle `$01` — the long slab at world `y = 592`), then jump. Watch
`Player_1 + $1F` frame by frame while airborne. *Expect it to alternate `$01`/`$FF` forever instead
of decaying to `$00`.* If it decays, section 6 is wrong and should be struck.

**TAG-4 — the escape.** From the saved state, confirm the only escape is a jump: hold RIGHT for
120 frames and read `x_pos` (`+$02`). *Expect it to stay at 16.* Then press A/C. *Expect him to
leave.*

**TAG-5 — sanity on the slide's zero input.** During a `PSTATE_SLIDE` (state byte at `+$32` reads
`20`), hold LEFT and RIGHT alternately and watch `x_vel` (`+$0A`). *Expect input to have no effect
whatsoever* — `PState_Slide` reads the D-pad nowhere. If it does respond, my reading of
`player_glide.emp:450-530` is wrong.

---

## 10. Tooling used (not committed; another lane owns the extractor)

* the controller's `state_ram.py` (being committed under `tools/` by another lane — deliberately
  not committed here)
* three throwaway readers in the session scratchpad: the history-ring dump, the replay-buffer /
  globals dump, and `runtime_coll.py` — which is the one worth re-creating if this is revisited:
  it reads the **runtime** collision out of `Tile_Cache_Collision` + the cache window registers,
  so it answers "what did the engine actually see" rather than "what does the source say", and the
  two disagreed here.
