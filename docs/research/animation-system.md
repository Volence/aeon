# Animation System Research

Research into sprite animation systems across 7 reference projects and online sources, to inform the Sonic 4 Engine animation implementation.

## 1. Per-Reference Findings

### 1.1 S.C.E. (Sonic Clean Engine)

**Files**: `Engine/Objects/Animate Sprite.asm`, `Engine/Objects/Animate Raw.asm`

S.C.E. provides the most comprehensive animation framework of any reference, with multiple variants for different use cases. It is essentially a cleaned-up Sonic 3K animation system.

**Animation script format (Animate_Sprite variant)**:
```
AnimTable:  dc.w  Anim0-AnimTable, Anim1-AnimTable, ...   ; offset table
Anim0:      dc.b  duration, frame0, frame1, ..., control_code [, arg]
```
- First byte = per-animation frame duration (countdown timer reload value)
- Subsequent bytes = mapping frame indices
- Terminated by control code ($FF-$FB)

**Control codes** (Animate_Sprite):
| Code | Name | Effect |
|------|------|--------|
| $FF (afEnd) | Loop | Restart animation from first frame |
| $FE (afBack) | Jump back | Next byte = count; rewind N frames in script |
| $FD (afChange) | Switch anim | Next byte = new animation ID |
| $FC (afRoutine) | Advance routine | Increment `routine(a0)` by 2, continue |
| $FB | Delete | Move object offscreen (`x_pos = $7F00`) |

**Frame duration mechanism**: Per-animation constant. `anim_frame_timer` decrements by 1 each tick; when it goes negative, the next frame is read and the timer reloads from byte 0 of the animation script.

**Animate_SpriteMultiDelay variant**: Per-frame timing. Data format becomes pairs:
```
Anim0:  dc.b  frame0, timer0, frame1, timer1, ..., control_code
```
Each frame carries its own duration byte. Frame index advances by 2 per step.

**Animate_Raw variant**: Simpler system used for raw animation sequences (shields, effects). No animation table indirection -- uses a direct ROM pointer stored in `animations(a0)`. Format:
```
RawAnim:  dc.b  duration, frame0, frame1, ..., $FF, control_byte [, arg]
```
Control codes: $FE = restart, $FC = jump (signed byte offset to new script), $FA = custom callback via `wait_addr(a0)`.

**Animate_RawGetFaster**: Speed-up accumulator for spindash-like effects. Starts at full duration and decrements `aniraw_frame_timer` each loop completion until it reaches 0, at which point it calls a custom callback. This is the closest S.C.E. gets to velocity-linked animation.

**Multi-sprite animation (Animate_MultiSprite)**: Packed nybble format for boss sub-sprites. Each child stores two bytes in a buffer:
- Byte 1: high nybble = prev anim ID, low nybble = current anim ID
- Byte 2: high nybble = frame index, low nybble = timer

Parent iterates through child sprite mapping frames at `sub2_mapframe`, `sub3_mapframe`, etc. Each child reads from the same animation table but maintains independent anim/frame/timer state packed into 2 bytes per child.

**DPLC integration**: Completely separate from animation. `Sonic_Load_PLC` (line 2960 of `Sonic.asm`) is called AFTER `Animate_Sonic`. It compares `mapping_frame(a0)` against `Player_prev_frame` in RAM. If changed, it walks the DPLC table and queues DMA entries. Non-player objects use `Perform_DPLC` (in `Engine/Objects/Misc.asm`) which stores prev_frame at `ros_prev_frame(a0)` ($3A in the SST).

**Speed scaling** (walk/run): `Animate_Sonic` (line 2427) detects walk/run animations by checking if the first byte of the animation script is negative (`bmi.s SAnim_WalkRun`). The speed formula:
```
d2 = abs(ground_vel)           ; player ground speed
duration = ($800 - d2) >> 8    ; frame duration = (2048 - speed) / 256
; Clamped: if result < 0, duration = 0 (fastest)
```
This maps speed range $000-$800 to duration range 8-0 frames. At full speed ($800+), every frame advances the animation. At standstill, each frame lasts 8 ticks.

The walk animation also adds an angle-derived offset to the mapping frame to select the correct rotation frame set (0, 2, 4, or 6 added to base frame).

### 1.2 Batman & Robin (Clockwork Tortoise)

**Files**: `disasm/code/engine/objects.asm`

Batman & Robin uses a fundamentally different architecture: a **two-level bytecode interpreter**. Objects have no traditional animation routine.

**Level 1 (State Script)**: A bytecode stream with `a2` as the program counter. Each opcode is a 16-bit code word that indexes directly into handler addresses. The `movea.w (a2)+, a0; jmp (a0)` pattern is a threaded-code interpreter. Opcodes manipulate four local variables at `a5+$22/$24/$26/$28` (set, OR, AND, XOR, increment, decrement, dec-branch-if-zero, compare-skip, etc.).

**Level 2 (Action Script)**: Loaded from `$8(a6)` into `a4`. Contains frame data, collision box definitions, and positioning. Action script entries have per-frame timers at `$1(a4)` that count down via `subq.b #1, $1(a4)`.

**Frame duration**: Per-frame, embedded in the action script bytecode. When the timer at `$1(a3)` or `$1(a4)` expires, the next action script entry is read.

**DPLC integration**: Not applicable in the traditional sense. Batman & Robin pre-loads art tiles and uses the VDP shadow table approach for sprite management. The bytecode system handles art switching as part of the state transitions.

**Multi-sprite**: The action script system naturally supports multi-sprite objects. Child sprites are spawned and managed through the bytecode commands, with parent position offsets applied via the script.

**Key takeaway**: This is a data-driven scripting engine, not a simple animation system. Far more powerful than Sonic's approach but vastly more complex. The self-advancing `a2` bytecode PC is essentially the cursor pattern taken to its logical extreme.

### 1.3 Vectorman (BlueSky Software)

**Files**: `vectorman_disasm/code/disasm.asm` (66963 lines, raw disassembly)

Vectorman uses pre-rendered 3D sprites -- each "animation frame" is a complete pre-rendered sprite sheet. The disassembly is unsymbolized, making specific routine identification difficult.

**Animation approach**: Based on code patterns at typical object field offsets, Vectorman appears to use:
- `$1a(a0)` / `$22(a0)` as frame-related fields
- `$16(a0)` / `$18(a0)` as position/velocity
- No traditional animation script system found -- likely hardcoded frame sequences per object state

**Key takeaway**: Vectorman's pre-rendered ball-sprite system is architecturally unique and not directly applicable to our tile-based sprite animation. The game's animation is tightly coupled to its 3D rendering pipeline.

### 1.4 Gunstar Heroes (Treasure)

**Files**: `gunstar_disasm/code/disasm.asm` (59453 lines)

Gunstar Heroes uses the **self-advancing cursor pattern** (same developer as Alien Soldier). Key evidence at lines 51540-51553:

```asm
        subq.w     #$1, $4c(a5)           ; decrement frame timer
        bne.w      $5611e                  ; if timer > 0, skip
        movea.l    $48(a5), a0             ; load cursor from SST
        move.w     (a0)+, $4c(a5)          ; read new timer (word)
        bmi.w      $56120                  ; negative = end marker
        move.w     (a0)+, d0              ; read display flags
        move.w     (a0)+, $8(a5)          ; read mapping hi
        move.w     (a0)+, $a(a5)          ; read mapping lo
        move.l     a0, $48(a5)            ; save advanced cursor
        or.w       $808a.w, d0            ; merge global flags
        move.w     d0, $e(a5)             ; set sprite attributes
```

**Animation record format** (8 bytes per frame):
```
dc.w  timer           ; frame duration (negative = end)
dc.w  display_flags   ; palette, priority, flip
dc.w  mapping_hi      ; sprite pattern name table entry
dc.w  mapping_lo      ; additional mapping data
```

**Frame duration**: Per-frame, stored as a word in the animation data. Timer at `$4c(a5)` counts down each tick.

**DPLC**: Not used. Gunstar Heroes pre-loads all sprite art into VRAM. The `$8(a5)/$a(a5)` fields directly set VDP sprite pattern attributes.

**Object slot layout**:
- `$48(a5)` = animation cursor (ROM pointer, self-advancing)
- `$4c(a5)` = frame timer (word countdown)
- `$8(a5)` / `$a(a5)` = current sprite attributes
- `$e(a5)` = display/priority flags

**End-of-animation handling**: When timer word is negative ($8000+), the routine either:
- Sets object to delete state (`$2(a5) |= $7FFF` clear)
- Loops by resetting cursor to start (seen in some variants)

### 1.5 Alien Soldier (Treasure)

**Files**: `aliensoldier_disasm/code/disasm.asm`

Alien Soldier uses the same self-advancing cursor as Gunstar Heroes (same engine lineage). The core animation routine is at line 19473 (`sub_02AE5E`):

```asm
sub_02AE5E:
        subq.w     #$1, $4c(a5)           ; decrement frame timer
        bne.b      $2ae86                  ; if timer > 0, return
        movea.l    $48(a5), a0             ; load cursor
        move.w     (a0)+, $4c(a5)          ; read new timer
        bmi.b      $2ae88                  ; negative = animation end
        move.w     (a0)+, $e(a5)           ; read display flags
        move.w     (a0)+, $8(a5)           ; read mapping hi
        move.w     (a0)+, $a(a5)           ; read mapping lo
        move.l     a0, $48(a5)            ; save advanced cursor
        or.w       $808a.w, d0            ; merge global palette
        move.w     d0, $e(a5)
```

**Identical to Gunstar Heroes** in structure. Same 8-byte animation record, same `$48(a5)` cursor / `$4c(a5)` timer layout.

**Additional variant** at line 19528: Includes a **loop control code**. When timer is negative, instead of ending, it reads a longword pointer and resets the cursor:
```asm
loc_02AF1C:
        move.l     (a0)+, $48(a5)         ; read loop target pointer
        bra.b      $2aefa                 ; restart from new cursor position
```
This enables non-looping sequences that jump to a different animation, or infinite loops that reset to the start.

**Setup routine** at line 19415 (`sub_02AD9C`):
```asm
sub_02AD9C:
        move.w     #$38, (a0)             ; set object type
        move.w     #$8d40, $2(a0)         ; set state
        move.w     (a1)+, $4c(a0)         ; initial timer from data
        move.w     (a1)+, $e(a0)          ; initial display flags
        move.w     (a1)+, $8(a0)          ; initial mapping hi
        move.w     (a1)+, $a(a0)          ; initial mapping lo
        move.l     a1, $48(a0)            ; save cursor (points past first frame)
```

**Key insight**: The initialization reads the first frame inline and then saves the cursor pointing to frame 2. This means frame 0 is never "re-read" -- the cursor always points to the *next* frame to load.

### 1.6 Thunder Force IV (Technosoft)

**Files**: `thunderforce4_disasm/code/disasm.asm` (64257 lines, contains null bytes)

Thunder Force IV's disassembly has embedded null bytes making analysis difficult. Based on patterns found:

- `$e(a0)` appears to be a **dual-purpose timer/lifetime counter**. It is decremented by `subq.w #1, $e(a0)` in many contexts, sometimes by 2, 3, 6, 7, or 8 -- suggesting it serves as both an animation frame counter and a general-purpose countdown.
- Object positions at `$10(a0)/$12(a0)`, velocities at `$14(a0)/$16(a0)`, with fractional positions at `$30(a0)/$32(a0)` and velocity deltas at `$2a(a0)/$2c(a0)`.

**Key takeaway**: TF4 appears to use inline/hardcoded animation rather than a generic animation script system. Frame changes are driven by the object's state machine directly, with the timer at `$e` serving as the tempo control. This is appropriate for a shmup where most objects have simple, short animations.

### 1.7 sonic_hack (Sonic 2 mod)

**Files**: `code/engines/display_animate.asm`, `code/objects/Sonic.asm`

This is the original Sonic 2 animation system with minor modifications.

**AnimateSprite** (line 64, `display_animate.asm`):
```asm
AnimateSprite:
    moveq   #0, d0
    move.b  anim(a0), d0           ; current animation ID
    cmp.b   next_anim(a0), d0      ; changed?
    beq.s   Anim_Run               ; no: continue
    move.b  d0, next_anim(a0)      ; yes: store and reset
    move.b  #0, anim_frame(a0)
    move.b  #0, anim_frame_duration(a0)
Anim_Run:
    subq.b  #1, anim_frame_duration(a0)  ; decrement timer
    bpl.s   Anim_Wait              ; still counting: return
    add.w   d0, d0
    adda.w  (a1,d0.w), a1          ; resolve animation pointer
    move.b  (a1), anim_frame_duration(a0) ; reload timer
    moveq   #0, d1
    move.b  anim_frame(a0), d1     ; current frame index
    move.b  1(a1,d1.w), d0        ; read mapping frame
    bmi.s   Anim_End_FF            ; control code check
```

**Identical structure to S.C.E.** (expected, as S.C.E. is derived from S3K which shares lineage with S2).

**Control codes**: $FF through $F9:
| Code | Effect |
|------|--------|
| $FF | Loop to start |
| $FE | Jump back N bytes |
| $FD | Switch to animation N |
| $FC | Set touched flag, continue |
| $FB | Reset animation frame |
| $FA | No-op return |
| $F9 | Increment `objoff_2A` by 2 |

**Sonic_Animate speed scaling** (line 1786):
```asm
SAnim_WalkRun:
    mvabs.w inertia(a0), d2        ; d2 = abs(ground speed)
    ; ...
    neg.w   d2
    addi.w  #$800, d2              ; d2 = $800 - speed
    bpl.s   +
    moveq   #0, d2                 ; clamp to 0
+   lsr.w   #8, d2                 ; d2 = ($800 - speed) >> 8
    move.b  d2, anim_frame_duration(a0)
    addq.b  #1, anim_frame(a0)
```
Duration = `max(0, ($800 - abs_speed)) >> 8`. Range: 0 (max speed) to 8 (standstill).

**Walk animation frame offset**: Walk uses 6 frames per rotation angle, with 4 angle sets (0, 2, 4, 6 added to base). The angle offset is doubled twice and added to `mapping_frame`, giving access to frames 0-47 from a single 8-frame animation script.

**DPLC**: Handled separately. For the player, `Sonic_Load_PLC` is a standalone call after `Sonic_Animate`. For other objects, S3K-style `Perform_DPLC` compares `mapping_frame` vs `$3A(a0)` (prev_frame).

**Shield DPLC** (`LoadShieldsDynPLC`, line 183 of `Shields.asm`):
```asm
LoadShieldsDynPLC:
    moveq   #0, d0
    move.b  mapping_frame(a0), d0
    cmp.b   shield_prev_frame(a0), d0   ; frame changed?
    beq.s   LSDPLC_Return               ; no: skip
    move.b  d0, shield_prev_frame(a0)   ; yes: update prev
    ; ... walk DPLC table, queue DMA entries
```

---

## 2. Online Findings

### 2.1 SGDK Sprite Engine

SGDK (C-based Genesis SDK) provides a high-level animation API:

**Animation state per sprite**:
- `animInd` (s16): current animation index
- `frameInd` (s16): current frame within animation
- `timer` (s16): countdown to next frame

**AnimationFrame struct**:
```c
typedef struct {
    s8 numSprite;       // VDP sprites composing this frame
    u8 timer;           // duration in 1/60s ticks
    TileSet* tileset;   // tile data for this frame
    Collision* collision;
    FrameVDPSprite frameVDPSprites[];
} AnimationFrame;
```

**Key design**: Per-frame duration (`timer` field per AnimationFrame). VRAM tile upload is triggered by the `onFrameChange` callback mechanism:
```c
typedef void FrameChangeCallback(Sprite* sprite);
```
This callback fires during `SPR_update()` when a frame changes, allowing the caller to update VRAM tile indices, trigger sound effects, or perform custom logic.

**Relevance to our engine**: The callback-on-frame-change pattern is interesting but heavy for 68000 assembly. However, the concept of separating "frame changed" notification from the animation tick is sound. Our prev_frame comparison approach achieves the same result more efficiently.

### 2.2 LUMINARY Engine (Big Evil Corporation / Tanglewood)

LUMINARY uses a "timeline track" animation system with entity components:
- `framewk/entities/eanim.asm` -- standard animation entity
- `framewk/entities/estampanim.asm` -- stamp-based animation
- `framewk/entities/esprite.asm` -- sprite integration

The blog tutorial describes a simple approach for beginners:
- Animation data is an array of frame IDs, one per game tick: `dc.b 0,0,0,0, 1,1,1,1, 2,2,2,2, 3,3,3,3`
- Frame counter increments each tick, wraps at end
- On frame change, compare current vs previous frame ID; only upload tiles if different
- Upload directly from ROM to VRAM during VBlank

This "expanded timeline" approach is simple but wasteful of ROM space for slow animations. The per-frame timer approach used by Sonic games is far more compact.

### 2.3 General Patterns from Community

**prev_frame comparison for DPLC**: Universal across all Sonic engines. The pattern is:
1. Animation routine sets `mapping_frame`
2. Separate DPLC routine compares `mapping_frame` vs `prev_frame`
3. If different: walk DPLC table, queue DMA, update `prev_frame`
4. If same: return immediately

This separation keeps the animation routine generic (no DPLC knowledge) and makes DPLC optional per object.

**Speed-to-duration formula**: The Sonic formula `duration = ($800 - speed) >> 8` is standard across S1, S2, S3K, and S.C.E. It provides smooth animation speed scaling with only 3 instructions (neg, add, shift).

---

## 3. Analysis and Validated Decisions

### 3.1 Self-Advancing Cursor vs Frame Index + Timer

**Frame index + timer** (Sonic/S.C.E. approach):
- Animation state = {anim_id, frame_index, timer} (3 bytes)
- Random access to any frame (useful for walk angle offsets)
- Animation data is compact (1 byte per frame)
- Animation change = just set `anim_id`; system detects via prev_anim comparison
- Timer reload requires re-reading the animation header each frame
- Requires animation table indirection (offset table lookup)

**Self-advancing cursor** (Treasure approach):
- Animation state = {cursor_ptr, timer} (6 bytes)
- Sequential-only access (no random frame access without reset)
- Animation data is larger (8 bytes per frame in Treasure's case)
- Animation change = set new cursor pointer
- Timer is inline with frame data (read once, advance past)
- No table indirection needed; cursor points directly to next frame
- Natural for scripted sequences with embedded per-frame data

**Decision: Hybrid approach.** Use the frame-index + timer approach as the primary system (matching our SST layout with `SST_anim`, `SST_mapping_frame`, `SST_anim_cursor`, `SST_anim_table`). The `SST_anim_cursor` field exists in our SST but should be used as a **resolved pointer to the current animation script** (set once when anim ID changes), not a Treasure-style self-advancing cursor. This gives us:
- Compact animation data (Sonic format)
- Random frame access (essential for walk angle offsets)
- Fast animation change detection via prev_anim comparison
- The cursor field caches the resolved animation pointer, avoiding re-computing `table + offset[anim_id]` every tick

**Rationale**: The Treasure cursor approach is elegant for objects with simple linear animations and per-frame metadata (display flags, mapping pointers). But Sonic's walk animation requires random frame access (angle offset + base frame), which is incompatible with a purely sequential cursor. The Sonic approach is proven across 6 games and well-understood.

### 3.2 Speed Scaling Formula

**Sonic standard**: `duration = max(0, ($800 - abs_speed)) >> 8`
- Range: 0 (fastest, at speed >= $800) to 8 (slowest, at speed 0)
- 3 instructions: `neg.w d2 / addi.w #$800, d2 / lsr.w #8, d2`
- No multiply, no divide
- Smooth, well-tested across all Sonic games

**Decision: Use the Sonic formula unchanged.** It maps the expected speed range ($000-$800) to a reasonable duration range (8-0). The `>> 8` shift effectively divides into 8 speed bands. For our engine, the constant $800 should be a named constant (`ANIM_SPEED_MAX`) so it can be tuned per character.

```
; Speed-linked duration: faster movement = shorter frame hold
; d2.w = abs(ground_vel)
    neg.w   d2
    addi.w  #ANIM_SPEED_MAX, d2    ; $800 default
    bpl.s   .clamp
    moveq   #0, d2                 ; clamp to 0 (max animation speed)
.clamp:
    lsr.w   #8, d2                 ; divide into bands
    move.b  d2, SST_anim_timer(a0) ; set frame duration
```

### 3.3 DPLC Trigger Location

All references agree: **DPLC is separate from animation.**

- S.C.E.: `Animate_Sonic` then `Sonic_Load_PLC` as separate calls
- sonic_hack: Same pattern
- S3K: `Perform_DPLC` called independently, checks `mapping_frame` vs `$3A(a0)`
- Gunstar/Alien Soldier: No DPLC (all art pre-loaded)
- SGDK: `onFrameChange` callback (separate from animation tick)

**Decision: DPLC call stays separate.** The object's main loop calls:
1. `AnimateSprite` -- updates `SST_mapping_frame`
2. `Perform_DPLC` -- compares frame, queues DMA if changed

This keeps AnimateSprite generic (usable for objects with and without DPLC) and lets objects that pre-load all art skip the DPLC call entirely.

We already have `Perform_DPLC` and `Perform_DPLC_Deferrable` in `engine/dplc.asm`. The animation routine only needs to set `SST_mapping_frame`. A `prev_frame` field should be added to the SST (or use a byte in `SST_custom`) for the comparison.

### 3.4 Control Code Set

**Phase 2 (basic animation)**:
| Code | Byte | Meaning |
|------|------|---------|
| AF_END | $FF | Loop: restart from first frame |
| AF_BACK | $FE | Jump back: next byte = rewind count |
| AF_CHANGE | $FD | Switch animation: next byte = new anim ID |
| AF_ROUTINE | $FC | Advance routine counter by 2 |

These four codes cover all standard Sonic object animation needs and match the proven S.C.E./S2/S3K set.

**Phase 4 (advanced, added later if needed)**:
| Code | Byte | Meaning |
|------|------|---------|
| AF_DELETE | $FB | Mark object for deletion |
| AF_CALLBACK | $FA | Call custom function pointer |
| AF_SFX | $F9 | Play sound effect (next byte = SFX ID) |

The $FA callback is inspired by S.C.E.'s `Animate_Raw` which uses `wait_addr(a0)` for custom code jumps. The $F9 SFX trigger is new but useful for tying sound to specific animation frames.

### 3.5 Per-Frame vs Per-Animation Duration

**Per-animation** (Sonic standard / `Animate_Sprite`):
- Compact: 1 byte overhead per animation
- Sufficient for 90% of objects (explosions, rings, monitors, badniks)
- Walk/run speed-linking overrides the duration anyway

**Per-frame** (S.C.E. `Animate_SpriteMultiDelay`):
- 1 extra byte per frame
- Needed for: shield animations, idle sequences with varying timing, cutscene animations
- Example: Sonic's idle (fast tapping, then slow stretch) uses 50+ frames at duration 5 but could benefit from per-frame timing

**Decision: Support both.** Implement two entry points:
1. `AnimateSprite` -- per-animation duration (byte 0 = duration, bytes 1+ = frames)
2. `AnimateSprite_PerFrame` -- per-frame duration (pairs of frame, duration)

The per-animation variant is the default. Per-frame is opt-in for objects that need it. Both share the same control code handling. The animation script's duration byte value can serve as a discriminator: negative values ($80+) signal special behavior (walk/run), non-negative values are the per-animation timer.

### 3.6 Proposed Animation Script Formats

**Standard format** (per-animation duration):
```
AnimTable:  dc.w  Anim0-AnimTable, Anim1-AnimTable, ...
Anim0:      dc.b  duration          ; timer reload value (0-$7F)
            dc.b  frame0, frame1, frame2, ...
            dc.b  AF_END            ; or other control code
            even
```

**Per-frame format**:
```
AnimTable:  dc.w  Anim0-AnimTable, ...
Anim0:      dc.b  frame0, dur0, frame1, dur1, ...
            dc.b  AF_END, 0         ; control code + padding
            even
```

**Speed-linked marker**: When byte 0 of an animation is $FF, the animation routine enters speed-linked mode (walk/run). The second byte provides the base frame set size for angle offset calculation.

### 3.7 SST Fields Summary

Current SST fields are sufficient. The one addition needed is a `prev_frame` field for DPLC comparison. Options:
- Add `SST_prev_frame` as a dedicated byte (requires SST restructure)
- Use first byte of `SST_custom` ($2C) as prev_frame for DPLC-using objects
- Use `SST_anim_cursor` high byte (since cursor is only used as resolved pointer, not Treasure-style advancing)

**Recommendation**: Add `SST_prev_frame` (byte) and `SST_anim_timer` (byte) as dedicated fields. This may require adjusting the SST layout. The `SST_anim_cursor` field should be repurposed or renamed to `SST_anim_ptr` to clarify it caches the resolved animation script pointer rather than acting as a Treasure-style self-advancing cursor.

Proposed animation-related SST fields:
```
SST_anim           ds.b 1   ; $1A - desired animation ID
SST_mapping_frame  ds.b 1   ; $1B - current mapping frame index
SST_anim_ptr       ds.l 1   ; $1C - cached pointer to current animation script (ROM)
SST_prev_anim      ds.b 1   ; $20 - previous animation ID (for change detection)
SST_anim_frame     ds.b 1   ; $21 - current byte offset within animation script
SST_anim_timer     ds.b 1   ; $22 - frame duration countdown
SST_prev_frame     ds.b 1   ; $23 - previous mapping_frame (for DPLC comparison)
```

Note: These field assignments would need to be reconciled with existing SST layout. The current `SST_subtype` at $20 and `SST_respawn_index` at $21 may need relocation.

---

## Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Animation model | Frame index + timer | Random access for walk angles, compact data, proven across all Sonic games |
| Speed scaling | `($800 - speed) >> 8` | Standard Sonic formula, no multiply, well-tested |
| DPLC trigger | Separate call after animate | Keeps animation generic, matches all references |
| Control codes (Phase 2) | $FF-$FC (4 codes) | Covers loop, jump-back, switch-anim, advance-routine |
| Control codes (Phase 4) | $FB-$F9 (3 codes) | Delete, callback, SFX -- added when needed |
| Frame duration | Both per-anim and per-frame | Per-anim default, per-frame opt-in for complex sequences |
| Cursor field usage | Cache resolved anim pointer | Not Treasure-style self-advancing; avoids re-computing table offset each tick |

## Online Sources

- [SGDK sprite_eng.h](https://github.com/Stephane-D/SGDK/blob/master/inc/sprite_eng.h) -- AnimationFrame struct, callback mechanism
- [SGDK sprite_eng.c](https://github.com/Stephane-D/SGDK/blob/master/src/sprite_eng.c) -- Implementation
- [LUMINARY engine](https://github.com/BigEvilCorporation/LUMINARY) -- Timeline track animation, entity components
- [Big Evil Corp: Animated Sprites](https://blog.bigevilcorporation.co.uk/2012/05/05/sega-megadrive-8-animated-sprites/) -- Simple frame array approach, prev_frame comparison for VRAM upload
- [Sonic 3 Unlocked: DPLC part 2](https://s3unlocked.blogspot.com/2017/11/dynamic-pattern-load-cues-part-2.html) -- Sonic 3 prev_frame comparison pattern
- [Hugues Johnson: Genesis Sprite Animation](https://huguesjohnson.com/programming/genesis/animated-sprites/) -- Step counter approach
- [SpritesMind: Animation speed](http://gendev.spritesmind.net/forum/viewtopic.php?t=2154) -- SGDK timer configuration
- [plutiedev.com](https://plutiedev.com/sprites) -- Sprite hardware reference
