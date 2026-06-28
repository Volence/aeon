# Player Movement, Gravity, Controller Input, and Ground Detection Research

Research across all 7 reference disassemblies plus online sources. Focus: what we need for Task 11 (test player object with movement, jump, gravity, stub floor).

---

## 1. sonic_hack (Sonic 2 modified disassembly)

**Source**: `/home/volence/sonic_hacks/sonic_hack/code/objects/Sonic.asm`, `Player_Common.asm`, `Object_Specific_Routines/object_movement.asm`, `S4.constants.asm`

### Controller Reading

3-button only. TH pin toggle protocol, called from VBlank handler:
- Write $40 to port (TH=1), read CBRLDU (bits 5-0)
- Write $00 to port (TH=0), read SA00DU (bits 5-0), shift SA to bits 7-6
- Combine and invert: result byte is SACBRLDU, 1 = pressed
- **Held vs Press detection**: `Ctrl_1_Held` stores current state. `Ctrl_1_Press` = `(new EOR old) AND new` -- bits that are held now but were NOT held last frame.
- **Logical layer**: `Ctrl_1_Logical` copies from physical `Ctrl_1` unless `Control_Locked` is set. This allows cutscenes/demos to inject fake input.

Button bit assignments (bit position for btst):
```
button_up=0, button_down=1, button_left=2, button_right=3
button_B=4, button_C=5, button_A=6, button_start=7
```

### Player State Machine

Top-level routine byte (`routine` offset) selects major state via jump table:
```
Sonic_Init       = 0    ; one-shot setup
Sonic_Control    = 2    ; normal gameplay (has sub-states)
Sonic_Hurt       = 4    ; recoil from damage
Sonic_Dead       = 6    ; death animation
Sonic_Gone       = 8    ; off-screen after death
Sonic_Respawning = $A   ; respawn sequence
```

Within `Sonic_Control`, a secondary 2-bit dispatch selects movement mode from status bits (in_air | rolling):
```
Sonic_MdNormal = %00   ; on ground, not rolling
Sonic_MdAir    = %01   ; airborne, not rolling
Sonic_MdRoll   = %10   ; on ground, rolling
Sonic_MdJump   = %11   ; airborne + rolling (jumping/bouncing)
```

This is NOT a state byte -- it's two status bits combined into a 4-entry jump table. Bit 1 = in_air, bit 2 = rolling. The actual "state" is emergent from these flags.

### Horizontal Movement

**Ground movement uses `inertia` (also called `ground_vel`)**. This is a single signed 8.8 value representing speed along the ground surface. At the end of movement calculation, it is decomposed to x_vel and y_vel using the surface angle:
```
x_vel = (inertia * cos(angle)) >> 8
y_vel = (inertia * sin(angle)) >> 8
```

Physics RAM (loaded into registers at start of movement):
- `Sonic_top_speed` (a4+0) = $600 = 6.0 px/frame
- `Sonic_acceleration` (a4+2) = $C = 0.046875 px/frame^2
- `Sonic_deceleration` (a4+4) = $80 = 0.5 px/frame^2

**Acceleration**: When pressing left/right in movement direction, add `acceleration` to inertia per frame. Cap at `top_speed`.

**Deceleration (braking)**: When pressing opposite direction, subtract `deceleration` from inertia. If speed crosses zero during braking, clamp to $-80 or $80 (a small push in the new direction). Triggers skid animation and sound at speeds >= $400.

**Friction (no input)**: When no left/right is pressed AND on ground, subtract `acceleration` from absolute inertia each frame. This makes friction = acceleration by design (Sonic stops in the same time it takes to reach speed).

### Gravity and Vertical Movement

**Gravity constant**: $38 = 0.21875 px/frame^2, applied every frame while airborne via `ObjectMoveAndFall`:
```
y_vel += $38    ; add gravity
```

**Underwater gravity**: Subtract $28 from y_vel after gravity is added. Net underwater gravity = $38 - $28 = $10 = 0.0625 px/frame^2.

**Terminal velocity**: y_vel is capped at $FC0 upward (via Sonic_UpVelCap). No explicit downward terminal velocity -- the physics naturally limit it through collision.

**Air resistance / air drag**: At the peak of a jump (when y_vel > -$400), horizontal speed is divided by 32 each frame and subtracted. This creates a "floaty peak" feel where horizontal momentum decays slightly near the top of a jump.

### Jumping

**Initiation**: Any of A/B/C pressed (Ctrl_1_Press_Logical). Must have >= 6px headroom above (CalcRoomOverHead).

**Jump velocity**: $680 = 6.5 px/frame upward. Applied relative to ground angle:
```
x_vel += ($680 * cos(angle - $40)) >> 8
y_vel += ($680 * sin(angle - $40)) >> 8
```
On flat ground, angle=0, so this is purely vertical. On slopes, you jump perpendicular to the surface.

**Super Sonic jump**: $800 = 8.0 px/frame.
**Underwater jump**: $380 = 3.5 px/frame.

**Variable height**: While `jumping` flag is set AND y_vel < -$400 (still rising), if jump button is RELEASED, y_vel is immediately set to -$400. This truncates the jump arc. If button is still held, gravity continues normally allowing full height.

**Air control**: Uses `Player_ChgJumpDir`. Acceleration in air = 2x ground acceleration. Same top speed cap applies. If player rolled into the jump (btst #4,status), air control is disabled.

### Ground Detection

Full collision system uses `AnglePos` / `DoLevelCollision` with height map sensors. Not relevant to stub terrain for Task 11.

**On-ground flag**: `status` bit 1 (in_air). When 0 = on ground, 1 = airborne. Set when jumping, cleared when `AnglePos` finds floor contact. The ground angle is stored in `angle` offset.

### Speed-to-Position

`ObjectMove` (no gravity) and `ObjectMoveAndFall` (with gravity):
```
; vel is 8.8 fixed, pos is 16.16 fixed
; Shift vel left 8 to align with position fractional bits:
ext.l   d0          ; sign-extend 16-bit vel to 32-bit
lsl.l   #8, d0      ; shift into 16.16 position space
add.l   d0, x_pos   ; add to 32-bit position
```
This gives subpixel accuracy. The integer part of x_pos is the pixel coordinate; the lower 16 bits are subpixel.

### Animation Integration

Animation ID (`anim` field) is set by movement code based on state:
- `anim = 0` = walking/running (speed-based frame rate set by Sonic_Animate)
- `anim = 2` = rolling/jumping
- `anim = 5` = standing idle
- `anim = 6` = balancing on edge
- `anim = 7` = looking up
- `anim = 8` = ducking
- `anim = 9` = spindash charge
- `anim = $D` = skidding/braking

Walk/run is a single animation with variable frame duration based on abs(inertia):
- faster inertia = shorter frame duration = faster animation
- Thresholds determine visual walk vs jog vs run vs dash

---

## 2. S.C.E. (Sonic Clean Engine, S3K-based)

**Source**: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Objects/Players/Sonic/Sonic.asm`, `Engine/Core/Controllers.asm`, `Engine/Objects/Move Sprite.asm`

### Controller Reading

Same 3-button TH toggle protocol as Sonic 2. Key difference:
- TH=0 read comes FIRST, then TH=1. The SA bits are shifted by `lsl.b #2` instead of `lsl.b #2` on d1 (same math, different order).
- Includes `Detect_Controller` routine that pulses TH 4 times to detect if a pad is connected. Checks if response is $0D (connected).

### Player State Machine

Identical structure to Sonic 2: routine byte dispatch for major states (Init/Control/Hurt/Death/Restart/Drown), then 2-bit status dispatch for movement modes (Normal/Air/Roll/Jump).

One notable improvement: S.C.E. saves/restores a4-a6 around the movement mode dispatch:
```
movem.l a4-a6,-(sp)
jsr     Sonic_Modes(pc,d0.w)
movem.l (sp)+,a4-a6
```
This protects the physics pointers from being clobbered by subroutines within the mode.

### Horizontal Movement

Same system as Sonic 2: `ground_vel` (equivalent to `inertia`) decomposed via angle to x_vel/y_vel. Same constants:
```
Max_speed    = $600
Acceleration = $C
Deceleration = $80
```

Underwater values: $300 / $6 / $40 (half speed, half accel, half decel).

### Gravity

Same $38 gravity in `MoveSprite` (applies gravity) vs `MoveSprite2` (no gravity).

**Notable additions**: S.C.E. includes `MoveSprite_LightGravity` ($20), `MoveSprite_CustomGravity` (d1 parameter), and `MoveSprite_ReverseGravity` (negates y_vel direction for flip-gravity mode). These are cleaner abstractions than sonic_hack.

**Terminal velocity**: Explicit cap at $1000 (16.0 px/frame) checked after gravity is applied in MdAir/MdJump.

### Jumping

Same $680 jump velocity, $380 underwater. Same variable height mechanism (cap at -$400 when button released). Same CalcRoomOverHead headroom check.

**Shield double jumps**: Implemented in `Sonic_InstaAndShieldMoves` -- fire shield dash ($800 horizontal), lightning shield double jump (y_vel = -$580), bubble shield bounce (y_vel = $800 downward, x_vel = 0).

### Speed-to-Position

Identical to Sonic 2 but uses `asl.l #8` with `movem.w` for loading both velocities:
```
movem.w x_vel(a0),d0/d2     ; load x_vel into d0, y_vel into d2
asl.l   #8,d0
asl.l   #8,d2
add.l   d0,x_pos(a0)
add.l   d2,y_pos(a0)
```
The `movem.w` trick is more elegant -- loads both velocities in one instruction.

---

## 3. Batman & Robin

**Source**: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/main_loop.asm`

### Controller Reading

Standard 3-button TH toggle protocol at $A10003. Same approach:
- TH=0, read SA bits
- TH=1, read CBRLDU
- Combine, invert
- Press detection via EOR/AND:
```
move.b  (a1), d1        ; old held
move.b  d1, d2
eor.b   d0, d2          ; changed bits
move.b  d0, (a1)        ; store new held
and.b   d2, d1          ; d1 = released this frame
and.b   d2, d0          ; d0 = pressed this frame
```
Notable: Batman stores BOTH "just pressed" AND "just released" -- useful for charge attacks.

### Player State Machine

Batman uses a pointer-based state machine stored in the object's RAM. Level-specific scripts drive behavior. The game is a beat-em-up/platformer hybrid, so player states include combat moves, grapple, batarang throw, etc.

State transitions are script-driven rather than flag-based. Objects have a script pointer ($2A field) that the engine follows.

### Movement

Batman uses simpler movement than Sonic -- no inertia system. Direct velocity from input. However, the object system has a standard ObjectMove-style velocity-to-position pipeline.

---

## 4. Vectorman

**Source**: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/code/disasm.asm`

### Controller Reading

**6-button controller support confirmed**. The code performs the full 7-cycle TH toggle sequence:
```
; 8 alternating TH writes with reads between them
move.b  #$40, (a0)     ; TH=1
nop / nop
move.b  (a0), d1
move.b  #$00, (a0)     ; TH=0
nop / nop
move.b  (a0), d1
; ... repeats 4 more times (total 8 TH toggles)
```

Detection logic checks lower nibble of the 6th read:
- If bits 3-0 == $0, $1, $2, or $3 --> 6-button pad detected
- Otherwise --> 3-button pad

The 12-bit result is stored: low 8 bits = standard SACBRLDU, bits 8-11 = MXYZ.

### Player Movement

Vectorman uses a platformer physics model with:
- Gravity applied each frame
- Variable jump (implied by the multi-state jump handling)
- 8-directional aiming (separate from movement) for shooting
- Object position stored as 16.16 fixed point

The player object has a large state machine for different transformations (ball form, drill form, etc.).

---

## 5. Gunstar Heroes

**Source**: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/code/disasm.asm`

### Controller Reading

3-button protocol with 6-button detection. Same TH toggle approach. The detection routine (sub_00311E) checks a flag at $f705 bit 6 to determine if the pad is 6-button, then remaps X/Y/Z buttons into the standard button byte at specific bit positions.

**Configurable button mapping**: Gunstar stores button mapping in RAM ($ff20 area) and applies it during the read. This allows the options screen to remap buttons -- a technique worth noting for aeon's eventual options menu.

### Player Movement

Gunstar Heroes is a run-and-gun with:
- 8-way movement (up/down/left/right + diagonals)
- Fixed-speed running (not acceleration-based like Sonic)
- Jump with fixed height (not variable)
- Slide move (fixed velocity burst)
- Grabbing/throwing enemies (separate state machine)

The player state machine is index-based with separate routines for each state.

---

## 6. Alien Soldier

**Source**: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/code/disasm.asm`

### Controller Reading

Identical controller reading code to Gunstar Heroes (same developer, Treasure). Same 3-button + 6-button detection. Same EOR/AND press/release detection with stored results at $f706/$f707.

### Player Movement

Alien Soldier has the most complex player state machine of the non-Sonic references:
- Walk, run, dash (instant speed boost), jump, double jump
- Hover (hold jump in air for limited time)
- Teleport dash (invincible rush move, costs health)
- Counter (absorb projectile, convert to health)
- Multiple weapon states

The dash move is interesting: it sets a high fixed velocity and a timer, ignoring normal acceleration. The player is invincible during dash. This is similar to Sonic's spindash in concept but implemented as a state rather than physics.

**Gravity**: Standard per-frame addition to y_vel. The game has high gravity for snappy jumps (boss-rush design demands responsive movement).

---

## 7. Thunder Force IV

**Source**: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/code/disasm.asm`

### Controller Reading

The disassembly uses fully numeric addresses, making controller code harder to locate. The game uses standard 3-button input (it predates the 6-button pad, released 1992).

### Ship Movement (Shmup)

Thunder Force IV is a horizontal scrolling shooter, so "player movement" is fundamentally different:
- **No gravity** -- the ship moves freely in 2D
- **4/8-directional input** mapped directly to velocity
- **Acceleration/deceleration model**: The ship smoothly accelerates to top speed and decelerates when input is released, using a simple add/subtract per frame -- conceptually similar to Sonic's ground movement but in two axes
- **Speed selection**: Player can choose between 4 speed settings, stored as the top speed value. This is equivalent to Sonic's `top_speed` being configurable.

**Relevant takeaway**: The 2-axis acceleration model (accel toward input direction, decel when no input) is the simplest possible physics model that still feels smooth. Good for a test player that doesn't need terrain collision.

---

## 8. Online Sources

### plutiedev.com -- Controller Protocol

**3-Button Protocol**:
- Write $40 to port control register during init
- Two TH cycles per read: TH=1 then TH=0
- Result byte: SACBRLDU (1 = pressed after NOT inversion)
- Need `nop` delays between write and read for bus synchronization (2+ nops)

**6-Button Protocol**:
- Seven TH cycles total (alternating $40/$00)
- Cycles 1-2: standard 3-button data
- Cycles 3-5: repeated/ignored data
- Cycle 6 (TH=0): detection -- if bits 3-0 are $0000, it's a 6-button pad
- Cycle 7 (TH=1): read X/Y/Z/Mode in bits 3-0

**Critical rule**: Read controllers ONLY ONCE per frame. Multiple reads per frame break 6-button timing.

**Press vs Held**: `held = current_state`, `pressed = (current XOR previous) AND current`, `released = (current XOR previous) AND previous`. Store in RAM; game logic reads cached values.

### huguesjohnson.com -- 6-Button Implementation

Complete 68000 assembly implementation of 6-button reading. Key details:
- Detection flag stored in memory, checked before attempting 6-button cycles
- Extra buttons stored in separate RAM location (word-sized for alignment)
- Hardware quirk: reading during init vs during VBlank produces different results on 6-button pads

### Sonic Physics Guide (info.sonicretro.org, values verified from disassemblies)

The definitive Sonic physics reference. While the wiki itself blocked automated access, the exact values are confirmed from the sonic_hack and S.C.E. disassemblies:

**Ground Movement Constants (Sonic 2)**:
| Parameter | Value | Decimal (px/frame or px/frame^2) |
|-----------|-------|----------------------------------|
| Acceleration | $000C | 0.046875 |
| Deceleration | $0080 | 0.500000 |
| Friction | $000C | 0.046875 (same as accel) |
| Top Speed | $0600 | 6.000000 |
| Slope Factor | $0020 | 0.125000 |
| Roll Decel (natural) | $0006 | 0.023438 (accel/2) |
| Roll Decel (braking) | $0020 | 0.125000 |
| Roll Top Speed | $1000 | 16.000000 |
| Min Roll Speed | $0080 | 0.500000 |

**Air Movement**:
| Parameter | Value | Decimal |
|-----------|-------|---------|
| Air Acceleration | $0018 | 0.09375 (2x ground accel) |
| Gravity | $0038 | 0.218750 |
| Underwater Gravity | $0010 | 0.062500 ($38 - $28) |
| Jump Velocity | $0680 | 6.500000 |
| Underwater Jump | $0380 | 3.500000 |
| Variable Jump Cap | $0400 | 4.000000 |
| Upward Speed Cap | $0FC0 | 15.750000 |
| Terminal Vel (S.C.E.) | $1000 | 16.000000 |

**Ground Speed System**:
1. Player has a single `inertia` (ground_vel) value representing speed along the ground surface
2. Input acceleration/deceleration modifies inertia directly
3. At end of movement phase, inertia is decomposed to x_vel and y_vel using the ground angle:
   - `x_vel = (inertia * cos(angle)) >> 8`
   - `y_vel = (inertia * sin(angle)) >> 8`
4. On flat ground (angle=0), x_vel = inertia, y_vel = 0
5. When airborne, x_vel and y_vel are modified directly (no inertia)

**Variable Jump Height Algorithm**:
1. On jump button PRESS: set y_vel = -$680, set `jumping` flag, set in_air status
2. Each frame while airborne: add $38 to y_vel (gravity)
3. If `jumping` flag set AND y_vel < -$400 (still rising fast) AND jump button NOT HELD:
   - Set y_vel = -$400 (truncate jump)
4. Result: tapping jump = short hop, holding jump = full arc

**Slope Factor on Ground**:
- `slope_force = sin(angle) * $20`
- Added to inertia each frame while on ground
- Going uphill: decelerates. Going downhill: accelerates.
- While rolling, slope force = `sin(angle) * $50` (stronger)

**Air Drag at Jump Peak**:
- When y_vel > -$400 (near peak or descending), and x_vel != 0:
  - `x_vel -= x_vel / 32` (gradual horizontal deceleration near peak)
- This creates the subtle "floaty" feel at the top of a jump

**Ground Detection (Sensors)**:
- Two floor sensors: one at player's left foot, one at right foot, both extending downward from player center
- Sensor positions shift based on ground angle (rotate at 45/135/225/315 degree thresholds)
- Floor found: set on-ground, store angle, adjust y_pos to sit on surface
- Floor NOT found (both sensors return nothing): set airborne

### SGDK and GitHub Homebrew

- SGDK's JOY system abstracts controller reading with `JOY_readJoypad()` returning a 16-bit mask. Handles 3-button and 6-button transparently. Uses `JOY_setEventHandler()` for press/release callbacks.
- Xeno Crisis uses SGDK's input system. Its player movement is 8-directional with fixed speed (twin-stick shooter).
- Tanglewood uses custom assembly input reading, similar to the Sonic approach.

---

## 9. Synthesis and Recommendations for aeon Test Player

### Controller Reading

**Current state**: aeon already has `Read_Controllers` in `engine/controllers.asm` implementing 3-button protocol. Stores `Ctrl_1_Held` and `Ctrl_1_Press`.

**6-button extension needed?** Not for Task 11. The test player only needs d-pad + one jump button. However, the eventual game will want 6-button support. **Recommendation**: defer 6-button to a later task. The existing 3-button code is correct and sufficient.

**One concern**: The current controller read does NOT pause the Z80. All references show Z80 being stopped before IO access. The aeon code accesses `HW_PORT_1_DATA` directly without stopZ80. This works on most emulators but can cause glitches on hardware. **Note for later**: add Z80 stop/start around controller reading, or move controller reading inside VBlank where Z80 is already stopped.

### State Machine Approach

For the test player (Task 11), a full Sonic state machine is overkill. Recommended approach:

**Simple flag-based state** using status bits, exactly like sonic_hack/S.C.E.:
- Bit 0: facing direction (0=right, 1=left)
- Bit 1: in_air (0=ground, 1=airborne)

Two code paths based on in_air flag:
1. **On ground**: apply acceleration/deceleration from input, check for jump initiation
2. **In air**: apply air control (weaker), apply gravity, check for landing

This avoids a complex state byte dispatch while still separating ground/air behavior. A state byte + jump table can be added later when we need rolling, spindash, hurt states.

### Physics Values for Test Player

Use the standard Sonic 2 values. They are proven and well-understood:

```
TEST_PLAYER_ACC     = $000C     ; ground acceleration
TEST_PLAYER_DEC     = $0080     ; ground deceleration (braking)
TEST_PLAYER_TOP     = $0600     ; top speed
TEST_PLAYER_GRAVITY = $0038     ; gravity per frame
TEST_PLAYER_JUMP    = $0680     ; initial jump velocity (negative)
TEST_PLAYER_JUMP_CAP = $0400    ; variable jump truncation cap
TEST_PLAYER_AIR_ACC = $0018     ; air acceleration (2x ground)
```

**Simplified for test player** (no slopes, no rolling):
- Skip `inertia` decomposition -- on flat ground, inertia = x_vel directly
- No slope factor, no rolling physics, no spindash
- Friction when no input = same as acceleration (standard Sonic behavior)

### Variable Jump Height

Implement the proven Sonic technique:
1. On jump press: `y_vel = -JUMP_VEL`, set in_air flag, set jumping flag
2. Each frame in air: `y_vel += GRAVITY`
3. If jumping AND y_vel < -JUMP_CAP AND jump button NOT held: `y_vel = -JUMP_CAP`

This is 5 instructions of code and gives perfect variable jump feel.

### Stub Floor

The test player needs a simple floor, not real terrain collision:
```
STUB_FLOOR_Y = 192      ; fixed Y position of floor (pixels from top)

; After applying velocity to position:
; If y_pos >= STUB_FLOOR_Y AND y_vel >= 0:
;   y_pos = STUB_FLOOR_Y
;   y_vel = 0
;   clear in_air flag
;   clear jumping flag
```

This is a pure Y clamp. No angle, no sensors, no height maps. Just "if below floor and moving down, put on floor." Real terrain collision comes in section 4.

### Speed-to-Position

Already implemented in `engine/objects.asm` as `ObjectMove`. Uses the standard pattern:
```
ext.l   d0
asl.l   #8, d0
add.l   d0, SST_x_pos(a0)
```

For the test player, we need an `ObjectMoveAndFall` equivalent that also applies gravity:
```
ObjectMoveAndFall:
    bsr.s   ObjectMove
    addi.w  #TEST_PLAYER_GRAVITY, SST_y_vel(a0)
    rts
```

Or inline the gravity add into the player's air update code, which is cleaner since gravity value may vary (underwater, etc).

### Animation Integration

For the test player, minimal animation states:
- `ANIM_IDLE = 0` -- standing still (inertia = 0, on ground)
- `ANIM_WALK = 1` -- moving on ground (inertia != 0)
- `ANIM_JUMP = 2` -- airborne

Set `anim` based on state each frame. The existing `AnimateSprite` system handles frame advancement and timer. Walk animation speed can be tied to abs(x_vel) later; for now, fixed frame rate is fine.

### Summary of What to Build (Task 11)

1. **Player object code** (~150 lines):
   - Read controller (already cached in RAM by VBlank)
   - If on ground: accelerate/decelerate from d-pad, check jump button
   - If in air: air control from d-pad, apply gravity, check variable jump cap
   - Apply velocity to position (ObjectMove)
   - Stub floor collision (Y clamp)
   - Set animation ID based on state
   - Call AnimateSprite + Draw_Sprite

2. **No new engine code needed** -- ObjectMove, AnimateSprite, controller reading, and Draw_Sprite all exist.

3. **New constants needed**: physics values (ACC, DEC, TOP, GRAVITY, JUMP, etc.) and stub floor Y.

4. **New RAM needed**: none beyond the player's SST slot (Player_1 already allocated). Custom fields in sst_custom can store the jumping flag.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State machine | Flag-based (in_air bit) | Simplest for test player, matches Sonic 2 pattern |
| Ground speed model | Direct x_vel (no inertia) | No slopes yet; inertia decomposition is pointless on flat ground |
| Physics values | Sonic 2 defaults | Proven, well-documented, easy to tune later |
| Variable jump | Truncation cap method | 5 instructions, universal Sonic technique |
| Floor collision | Y clamp at fixed line | Stub only; real collision is section 4 |
| Air control | 2x acceleration, same top speed | Standard Sonic air control |
| Animation | 3 states (idle/walk/jump) | Minimum viable for visual feedback |
| 6-button controller | Deferred | Not needed for test player |
