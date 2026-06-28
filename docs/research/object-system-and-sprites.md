# Object System & Sprite Rendering -- Cross-Engine Research

This document records findings from examining seven reference disassemblies plus
online sources. Each section follows the same A-E category structure so
comparisons across engines are straightforward.

---

## 1. S.C.E. (Sonic Clean Engine, S3K-based)

Source: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`

### A. Object State Table (SST)

**Size**: 80 bytes (`$50`) per object (line 330: `object_size = $50`).
S3K increased from Sonic 2's 64 bytes.

**Field layout** (`Engine/Constants.asm` lines 338-601):

| Offset | Size  | Name              | Category   |
|--------|-------|-------------------|------------|
| $00    | long  | code_addr         | Universal  |
| $04    | byte  | render_flags      | Universal  |
| $05    | byte  | routine           | Most objs  |
| $06    | byte  | height_pixels     | Universal  |
| $07    | byte  | width_pixels      | Universal  |
| $08    | word  | priority          | Universal  |
| $0A    | word  | art_tile          | Universal  |
| $0C    | long  | mappings          | Universal  |
| $10    | word+ | x_pos (long when subpixel used) | Universal |
| $12    | word  | x_sub             | Universal  |
| $14    | word+ | y_pos (long when subpixel used) | Universal |
| $16    | word  | y_sub             | Universal  |
| $18    | word  | x_vel             | Most objs  |
| $1A    | word  | y_vel             | Most objs  |
| $1C    | word  | ground_vel        | Player only |
| $1E    | byte  | y_radius          | Most objs  |
| $1F    | byte  | x_radius          | Most objs  |
| $20    | byte  | anim              | Most objs  |
| $21    | byte  | prev_anim         | Most objs  |
| $22    | byte  | mapping_frame     | Universal  |
| $23-$24| byte  | anim_frame, timer | Most objs  |
| $26    | byte  | angle             | Most objs  |
| $28    | byte  | collision_flags   | Non-player |
| $29    | byte  | collision_property| Non-player |
| $2A    | byte  | status            | Most objs  |
| $2B    | byte  | shield_reaction   | Non-player |
| $2C    | word  | subtype           | Non-player |
| $30    | long  | animations        | Non-player |
| $38    | byte  | state_flags       | Non-player |
| $39    | byte  | count             | Non-player |
| $3C    | byte  | routine_secondary | Some       |
| $48    | word  | parent            | Child objs |
| $4E    | word  | respawn_addr      | Most objs  |

Player-specific fields ($1C-$47 reimagined): ground_vel, double_jump_property,
flip_angle, status_secondary, air_left, object_control, move_lock,
invulnerability_timer, invincibility_timer, speed_shoes_timer, character_id,
top_solid_bit, lrb_solid_bit, etc.

**Standard vs Custom**: ~$22 bytes are truly universal ($00-$22). The remaining
$2E bytes are shared conventions that most objects follow but players override
entirely. That is ~43% fixed, 57% shared/custom.

**Code dispatch**: Full 32-bit code address in a longword at offset $00
(`code_addr`). `Process_Objects` loads it into a1 and does `jsr (a1)`.
No table lookup, no bank system -- raw pointer.

**Position format**: 16.16 fixed point via longword storage. `x_pos` at $10
is the integer part; `x_sub` at $12 is the fractional part. Code uses
`asl.l #8, d0; add.l d0, x_pos(a0)` which treats velocity as 8.8 and
position as 16.16 (velocity is shifted up 8 bits before adding to the 32-bit
position).

### B. Slot Allocation & Pools

**Total slots**: 110 objects (`Variables.asm` lines 11-30):
- Player_1: 1 slot
- Player_2: 1 slot (Tails in Sonic+Tails mode)
- Reserved_object_3: 1 slot (collision response list clearer)
- Dynamic_object_RAM: 90 slots
- 1 unused
- Breathing_bubbles: 2 slots (main + Tails)
- 1 unused
- Tails_tails: 1 slot
- Dust: 2 slots (main + Tails)
- Shield: 1 slot
- 1 unused
- Invincibility_stars: 4 slots
- 3 unused
- Wave_Splash: 1 slot

**Pool separation**: Implicit -- named slots exist at fixed RAM addresses for
player effects (dust, shield, tails' tails, stars, bubbles). Dynamic objects
share the 90-slot pool. No formal "system" or "effect" pool distinction.

**Allocation** (`Create Object.asm`): Linear scan starting from
Dynamic_object_RAM. Tests `code_addr` for zero using `tst.l code_addr(a1)`
in a `dbeq` loop. O(n) worst case where n = 90 slots.

**Deallocation** (`Delete Object.asm`): Zeros the entire $50-byte slot using
a `rept bytesTo2Lcnt(object_size)` macro that expands to 10 `move.l d0,(a1)+`
instructions (40 bytes cleared as 10 longs, plus 2-byte cleanup for $50 total).

**Slot ordering**: Position determines which objects freeze during death
sequences -- Dynamic_object_RAM slots get paused, reserved + level-only slots
continue running.

### C. Object Dispatch / RunObjects Loop

**Update order**: Linear scan, all slots, Player_1 first through Wave_Splash
last (`Process Objects.asm` lines 7-24):
```asm
Process_Objects:
    lea     (Object_RAM).w, a0
    ; ... death check ...
    moveq   #bytesToXcnt(Object_RAM_end-Object_RAM,object_size), d7
.loop:
    move.l  code_addr(a0), d0
    beq.s   .nextslot           ; zero = empty, skip
    movea.l d0, a1
    jsr     (a1)
.nextslot:
    lea     next_object(a0), a0
    dbf     d7, .loop
    rts
```

**Dispatch mechanism**: Indirect `jsr` through 32-bit code pointer. ~8 cycles
for the empty-slot skip (move.l + beq). No table lookup overhead.

**Register conventions**: a0 = current SST. Object code may clobber any
register except a0. d7 is the loop counter (preserved by dbf).

**Frozen behavior**: When player is dead/drowning, reserved slots (Player_1,
Player_2, reserved_3) execute normally. Dynamic objects get render-only pass:
`tst.l code_addr; bpl .skip; bsr Draw_Sprite`. Level-only objects execute
normally.

**Per-frame overhead**: ~12 cycles per empty slot (tst.l + beq + lea + dbf).
With 110 total slots and ~20 active, ~90 empties cost ~1080 cycles = ~0.16%
of a frame.

### D. Sprite Rendering & Priority

**Priority system**: 8 priority bands, each a list of .w SST addresses stored
in `Sprite_table_input` -- a $80-byte buffer per band (64 words = max 31
objects per band + count word). Priority stored at offset $08, in units of
$80 (so priority 0 = $0000, priority 3 = $0180, etc.).

**SAT building** (`Render Sprites.asm`): `Draw_Sprite` queues object .w
addresses into the appropriate priority band. `Render_Sprites` iterates
bands front-to-back, reads each object's mappings, and writes 8-byte VDP
SAT entries directly into `Sprite_table_buffer` (80 entries x 8 bytes = 640
bytes). This is a **two-phase system**: queue during object update, render in
a separate pass.

**Sprite overflow**: Hard limit check: `tst.w d7; bmi` -- d7 counts down
from 79. When it goes negative, no more sprites are written. The last
sprite's link byte is zeroed to terminate the chain.

**Multi-piece sprites**: Child sprite system via `render_flags.multi_sprite`
(bit 6). When set, `mainspr_childsprites` at $16 stores count, and
sub-sprites at offsets $18+ store individual x_pos, y_pos, mapframe for
up to 9 children. Each child gets its own mapping frame lookup.

**Flipping**: Four separate code paths in the SAT builder, selected by
testing render_flags bits 0-1:
- No flip: straight copy of y_offset, size, art_tile, x_offset
- X-flip: negate X offset, XOR flip_x on art_tile, apply width correction
  via lookup table at `byte_1AFD8` (8,16,24,32 per size class)
- Y-flip: negate Y offset, XOR flip_y, apply height correction via `byte_1B028`
- XY-flip: negate both, XOR both flip bits

**Screen-relative vs world**: `render_flags.level` (bit 2). When set,
subtract camera position; when clear, coordinates ARE screen coordinates
(used for HUD). The distinction is checked inside Render_Sprites per-object.

**Extra render slots**: `Render_sprite_first_RAM` and `Render_sprite_last_RAM`
allow injecting render callbacks before/after the main object render pass --
used for rings, water effects, special rendering that doesn't go through the
object system.

### E. Velocity / Movement

**Velocity application** (`Move Sprite.asm` lines 8-14):
```asm
MoveSprite:
    movem.w x_vel(a0), d0/d2     ; load x_vel and y_vel
    asl.l   #8, d0               ; shift 8.8 velocity to 16.16 position space
    asl.l   #8, d2
    add.l   d0, x_pos(a0)        ; add to 32-bit position
    add.l   d2, y_pos(a0)
    addi.w  #$38, y_vel(a0)      ; apply gravity
    rts
```
Velocity is 8.8 fixed-point (word). Position is 16.16 (longword). The `asl.l #8`
shifts vel left 8 bits to align with the position's fractional part. This gives
256 subpixels per pixel in position but only 256 velocity steps per pixel.

**Gravity**: Applied inline in `MoveSprite` (adds $38 to y_vel). Also available
via `MoveSprite_CustomGravity` with d1 parameter, and
`MoveSprite_LightGravity` (uses $20). Separate `MoveSprite2` variant omits
gravity entirely.

**Speed caps**: Not enforced in the move routines themselves -- handled per-
object (player has Max_speed, Acceleration, Deceleration globals checked
in movement code).

---

## 2. Batman & Robin (Clockwork Tortoise, 1995)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/`
Documented in: `disasm/OBJECT_SYSTEM.md`

### A. Object State Table

**Size**: ~90 bytes per object (used range $00-$58).

**Field layout** (from `OBJECT_SYSTEM.md`):

| Offset | Size  | Name              | Category   |
|--------|-------|-------------------|------------|
| $00    | long  | link_data         | Allocator  |
| $04    | word  | next_ptr          | List mgmt  |
| $06    | word  | prev_ptr          | List mgmt  |
| $08    | long  | script_ptr        | Universal  |
| $0A    | word  | init_a4           | Universal  |
| $0C    | word  | init_a5           | Universal  |
| $0E    | word  | flags_0E          | Universal  |
| $10    | word  | subtype           | Universal  |
| $18    | word  | sprite_link_count | Universal  |
| $1A    | word  | anim_accum        | Universal  |
| $1C-$20| word  | general purpose   | Custom     |
| $22    | word  | local_var_0       | Script     |
| $24    | word  | local_var_1       | Script     |
| $25    | byte  | active_flags      | Universal  |
| $26    | word  | state_flags       | Universal  |
| $28-$34| word  | anim/collision/timers | Custom |
| $36    | long  | velocity_x        | Universal  |
| $3A    | long  | velocity_y        | Universal  |
| $3C    | long  | callback_ptr      | Script     |
| $3E    | word  | x_pos             | Universal  |
| $40    | word  | x_pos_frac        | Universal  |
| $42    | word  | y_pos             | Universal  |
| $44    | word  | y_pos_frac        | Universal  |
| $4E    | word  | screen_x          | Computed   |
| $50    | word  | screen_y          | Computed   |
| $58    | word  | obj_type          | Universal  |

**Code dispatch**: Two-level **threaded bytecode interpreter** -- unique among
all references. Objects don't run native 68K directly; they execute word-sized
opcode streams. Level 1 (state script) uses a2/a5, Level 2 (action script)
uses a4/a6. Each opcode word is an address of a native handler; the handler
executes and reads the NEXT opcode inline (`movea.w (a2)+, a0; jmp (a0)`).
This is direct-threaded code, not indirect dispatch.

**Position format**: Word X/Y at $3E/$42 with fractional parts at $40/$44.
Effectively 16.16 but stored as two separate words rather than a longword.
Velocity is full 32-bit longword at $36/$3A.

**Standard vs Custom**: Only ~50% of the entry is well-defined. Fields $1C-
$20, $2C-$34 are general-purpose words reused differently per object type.

### B. Slot Allocation & Pools

**Allocation**: **Doubly-linked free list** -- O(1) allocation and deallocation.
This is the most advanced allocator among all references:
1. Free counter at `$F4B0` checked for underflow
2. Slot popped from free list head at `$AD52`
3. Inserted into active list at head `$DE94`
4. next/prev pointers set at $04/$06

**Deallocation**: O(1) linked-list removal (unlink from active, push to free).

**Pool separation**: Player objects at fixed addresses ($F650, $F690). All
other objects share the dynamic linked-list pool. No explicit type separation.

**Slot ordering**: Active list order determines update order. New objects
inserted at head, so newest objects update first.

### C. Object Dispatch

**Update order**: Walk the active linked list. No wasted iterations on empty
slots -- the list contains only active objects.

**Dispatch**: Threaded bytecode. The interpreter loop is:
```
movea.w (a2)+, a0    ; read next opcode (handler address)
jmp     (a0)         ; execute handler
```
Each handler ends by reading the next opcode the same way. Zero dispatch-loop
overhead between opcodes.

**Register conventions**: a6 = object SST (action level), a5 = saved copy of
a6 (state level), a2 = state script PC, a4 = action script PC.

**Frozen behavior**: Active flag at bit 0 of $25(a6). When clear, object
skipped entirely.

**Yield/Resume**: Script can yield mid-execution via opcode $0820 (saves a4
to $08(a6), restores stack from $DEC2, returns to main loop). Next frame
resumes from saved position. The script pointer itself IS the state machine --
no routine counter needed.

### D. Sprite Rendering

**Priority**: Sprite link counting via $18(a6) (sprite_link_count).
Objects compose their own sprite entries. Actual draw order managed through
the sprite table link field.

**SAT building**: VDP command buffer at $991C written directly during object
processing. The VDP_BurstTransfer routine at main_loop.asm line 24+ is an
unrolled copy loop that blasts pre-built VDP commands to the control port
(each DMA entry is 10 bytes: 4 move.l + 1 move.w).

**Screen-relative coordinates**: Computed per-object by subtracting camera
at $DFC4/$DFC8 and stored at $4E/$50 (screen_x/screen_y).

### E. Velocity / Movement

**Velocity**: Full 32-bit longwords at $36/$3A. This gives 16.16 fixed-point
velocity directly -- no shifting needed when adding to position (which is
also 16+16 across $3E+$40 / $42+$44).

**Gravity**: Applied through script opcodes that increment y_vel.

---

## 3. Vectorman (BlueSky Software, 1995)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/`
Documented in: `vectorman_disasm/ANALYSIS.md`

### A. Object State Table

**Size**: **12 bytes** per dispatch entry -- radically different from all
other engines.

| Offset | Size  | Name              |
|--------|-------|-------------------|
| $00    | word  | type/flags ($FFFF = empty/terminator) |
| $02    | word  | parameter         |
| $04    | long  | update routine pointer |
| $08    | long  | render routine pointer |

**Actual object data lives in separate, larger RAM blocks.** Player data at
$AF68 is ~1500 bytes. Each object type hardcodes the address of its data
block in its routines.

**Code dispatch**: Two raw 32-bit function pointers per object -- one for
update, one for render. State transitions are direct pointer writes:
`move.l #NewState, $4(a4)`.

**Position format**: Not in the dispatch entry -- lives in type-specific data
blocks. Player uses whatever format suits its 1500-byte data block.

### B. Slot Allocation & Pools

**Allocation**: Terminator-based compact table. The loop runs until $FFFF
marker. No empty-slot gaps -- objects must be compacted.

**Slot ordering**: Processing order = table order = implicit priority.

### C. Object Dispatch

**Update order**: Linear scan until $FFFF terminator. Each object gets TWO
calls: update (a1), then render (a0) if non-null.

**Dispatch mechanism**:
```asm
ObjectLoop:
    cmpi.w  #$ffff, (a4)    ; terminator?
    beq.b   .done
    movea.l $8(a4), a0       ; render routine
    movea.l $4(a4), a1       ; update routine
    jsr     (a1)             ; CALL UPDATE
    tst.l   a0               ; render null?
    beq.b   .skip
    jsr     $8EB4            ; CALL RENDER (via trampoline)
.skip:
    adda.w  #$C, a4          ; stride = 12
    bra.b   ObjectLoop
```

**Split update/render**: Vectorman's unique contribution. Invisible objects
skip render by having a null render pointer. The render trampoline at $8EB4
can apply global transforms.

### D. Sprite Rendering

**DMA pipeline**: The famous double-buffered pre-computed DMA queue.
- Main loop builds VDP command words into a buffer ($E49E)
- VBlank drains the buffer -- just copies 6 words per entry to $C00004
- Two-level budget enforcement: max 54 entries, max 2880 bytes per frame
- Objects provide (length, source_addr) pairs; queue builder handles VDP
  register encoding

### E. Velocity / Movement

Type-specific -- lives in each object's dedicated data block, not in the
dispatch table. No universal velocity system.

---

## 4. Gunstar Heroes (Treasure, 1993)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/`
Documented in: `gunstar_disasm/ANALYSIS.md`

### A. Object State Table

**Size**: **96 bytes ($60)** per object.

| Offset | Size  | Name              | Category   |
|--------|-------|-------------------|------------|
| $00    | word  | type/state        | Universal  |
| $02    | word  | mode/control flags| Universal  |
| $04    | word  | dispatch index    | Universal  |
| $08    | long  | sprite attrs ptr  | Universal  |
| $10    | word  | X position        | Universal  |
| $14    | word  | Y position        | Universal  |
| $18    | long  | X velocity (fixed-point) | Universal |
| $1C    | long  | Y velocity (fixed-point) | Universal |
| $24    | word  | art tile/priority | Universal  |
| $48    | long  | animation pointer | Universal  |
| $4C    | long  | data pointer      | Universal  |
| $50    | word  | timer/counter A   | Universal  |
| $56    | word  | timer/counter B   | Universal  |
| $58    | long  | **link pointer**  | Universal  |
| $5E    | word  | timer             | Custom     |

**Code dispatch**: Index-based jump table via word offset at $04:
```asm
move.w  $4(a5), d0       ; routine index
lea     JumpTable(pc, d0.w), a0
jmp     (a0)
```

**Position format**: Integer words at $10/$14. Velocity is full 32-bit
fixed-point longwords at $18/$1C.

**Link system**: The signature Treasure technique. Offset $58 stores a
pointer used for both parent/child links AND code callbacks, determined by
context. 52 writes + 19 reads in Gunstar.

### B. Slot Allocation & Pools

**Slot count**: 110 object loops confirmed in the code analysis. Linear
$60-stride iteration.

**Allocation**: Not detailed in analysis -- likely linear scan similar to
Sonic engines.

### C. Object Dispatch

**Register conventions**: a5 = current SST base pointer.

**Dispatch**: PC-relative jump table indexed by word offset at $04.

### E. Velocity / Movement

**Velocity**: 32-bit longwords at $18/$1C give 16.16 precision. Position
at $10/$14 are integer words -- integration must shift or use the fractional
part differently than Sonic.

---

## 5. Alien Soldier (Treasure, 1995)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/`
Documented in: `aliensoldier_disasm/ANALYSIS.md`

### A. Object State Table

**Size**: **96 bytes ($60)** -- same stride as Gunstar Heroes.

Same field layout as Gunstar with one critical addition:
- **$5C**: Second link pointer (104 references). Enables multi-part boss
  chains: Body->Head via $58, Body->LeftArm via $5C, etc.

**Dual-link system**: 380 references to $58 (vs Gunstar's 71). 104 references
to the new $5C field. Alien Soldier's bosses are built entirely around
linking.

### B. Slot Allocation & Pools

**Slot count**: 198 object processing loops -- nearly 2x Gunstar despite
same SST size, enabled by the larger 2MB ROM having more data and less code.

### C. Object Dispatch

**Two-stage dispatch**: First filter by type flags ($02), then routine index
via longword table. Simple objects skip the full dispatch. This avoids running
complex AI dispatch for objects that only need basic processing.

**Display list pre-building**: VDP command sequences pre-built in RAM during
main loop. VBlank just writes the pre-built blocks to VDP -- zero computation
at interrupt time.

---

## 6. Thunder Force IV (Technosoft, 1992)

Source: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/`
Documented in: `thunderforce4_disasm/ANALYSIS.md`

### A. Object State Table

**Size**: **32 bytes ($20)** per object. The smallest of all references.

Confirmed by 437 instances of `lsl.w #5` (multiply by 32) for index
calculations.

### B. Slot Allocation & Pools

**Type-segregated pools** -- the most granular pool system found:

| Pool         | Address     | Size  | Purpose        |
|--------------|-------------|-------|----------------|
| Main entities| $FFFF8198   | Variable | Player, weapons, FX |
| Bullet pool 1| $FFFF9000   | 1 KB  | Enemy bullets  |
| Bullet pool 2| $FFFF9400   | 1 KB  | More bullets   |
| Enemy pool 1 | $FFFFD000   | 1 KB  | Enemy objects  |
| Enemy pool 2 | $FFFFD400   | 1 KB  | More enemies   |

1KB / 32 bytes = 32 objects per pool.

**Why this matters**: Bullet processing gets a dedicated tight inner loop with
zero AI overhead. The loop just adds velocity, checks bounds, writes sprite
entry. Enemy processing runs separately with full AI. No type-checking in
the inner loop.

### C. Object Dispatch

**Update order**: Per-pool iteration. Bullets run in one pass, enemies in
another. Within each pool, linear scan.

### D. Sprite Rendering

**Sprite overflow handling**: Round-robin flicker using `add.w $F29A.w` to
rotate which sprites get priority each frame. Lower-priority sprites flicker
in/out across 4-frame windows. All objects remain visible -- none permanently
hidden.

**Priority**: Priority nibbles in sprite attributes control draw order.

---

## 7. sonic_hack (Sonic 2 mod -- baseline)

Source: `/home/volence/sonic_hacks/sonic_hack/`

### A. Object State Table

**Size**: 80 bytes (`$50`) per object.

**Field layout** (`S4.constants.asm` lines 50-168):

| Offset | Size  | Name              | Category   |
|--------|-------|-------------------|------------|
| $00    | word  | id (code offset)  | Universal  |
| $02    | word  | respawnentry      | Universal  |
| $04    | long  | mappings          | Universal  |
| $08    | word  | art_tile          | Universal  |
| $0A    | byte  | render_flags      | Universal  |
| $0B    | byte  | collision_response| Universal  |
| $0C    | word  | priority          | Universal  |
| $0E    | byte  | width_pixels      | Universal  |
| $0F    | byte  | height_pixels     | Universal  |
| $10    | word  | x_pos             | Universal  |
| $12    | word  | x_pixel (subpixel)| Universal  |
| $14    | word  | y_pos             | Universal  |
| $16    | word  | y_pixel (subpixel)| Universal  |
| $18    | word  | x_vel             | Universal  |
| $1A    | word  | y_vel             | Universal  |
| $1C    | byte  | next_anim         | Most objs  |
| $1D    | byte  | anim              | Most objs  |
| $1E    | byte  | anim_frame        | Most objs  |
| $1F    | byte  | anim_frame_duration| Most objs |
| $20    | byte  | mapping_frame     | Universal  |
| $21    | byte  | subtype           | Universal  |
| $22    | byte  | respawn_index     | Universal  |
| $23-$3F| -     | **per-type overlay** | Custom  |
| $40-$4F| -     | **expansion fields** | Universal/Custom |

**Per-type overlays** at $23-$3F:
- **Player** ($24-$3F): inertia, angle, flip_angle, status, status2, status3,
  air_left, move_lock, invulnerable/invincibility/speedshoes timers, shields,
  layer, etc.
- **Shield** ($24-$34): art pointer, DPLC pointer, prev frame, anim script
- **Generic**: free-form via objoff_XX constants

**Expansion fields** at $40-$4F (new in sonic_hack, not in stock S2):
obj_parent, obj_wait_timer, obj_wait_addr, obj_state_flags, obj_child_index,
obj_section_idx, obj_local_idx, obj_spawn_x, obj_spawn_y.

**Code dispatch** (`run_objects.asm` lines 60-72): Bank-offset system.
```asm
moveq   #1, d0          ; bank = $01
swap    d0               ; d0 = $00010000
move.w  (a0), d0         ; low word = offset within bank
beq.b   +               ; zero = empty slot
movea.l d0, a1
jsr     (a1)
```
The `id` field at offset $00 is NOT a raw code address -- it's a word offset.
Combined with the bank byte, it forms a 32-bit address: `$0001XXXX`.

**Position format**: 16.16 via longword at $10-$13 (x_pos + x_pixel). Same
as S.C.E.

**Standard vs Custom**: $23 bytes universal (45%), $1D bytes overlay (37%),
$10 bytes expansion (20%). More structured than S.C.E. due to explicit overlay
documentation.

### B. Slot Allocation & Pools

**Layout** (from S4.asm RAM):
- Reserved_Object_RAM: 16 slots (player, player2, HUD, title card, etc.)
- Dynamic_Object_RAM: 64 slots (badniks, platforms, monitors)
- LevelOnly_Object_RAM: 16 slots (effects, shields, invincibility stars)

Total: 96 slots (vs S.C.E.'s 110, Gunstar's 110, Alien Soldier's 198).

**Allocation**: Linear scan starting from Dynamic_Object_RAM, testing id word
for zero. O(n) where n = 64.

**Deallocation**: Zero all $50 bytes. No free list.

### C. Object Dispatch

**Update order** (`run_objects.asm` lines 22-33): Three-phase with execution
culling:
1. Reserved objects -- always execute
2. Dynamic objects -- **culled**: skips objects >768px from camera
3. LevelOnly objects -- always execute
4. Deferred deletion sweep

**Execution culling** (lines 88-108): Before dispatching a dynamic object,
check if its X position (coarse-aligned) is within $300 of the camera. If
not, skip the jsr entirely. This saves the full object execution cost for
far-off-screen objects.

**Deferred deletion** (lines 141-161): End-of-frame sweep checks
obj_state_flags bit 7 for each dynamic slot. Marked objects deleted after all
objects have run, preventing stale references mid-frame.

**Frozen behavior**: When player is dead, dynamic objects get render-only pass
(just DisplaySprite). Reserved and LevelOnly continue executing.

### D. Sprite Rendering

**Priority system** (`build_sprites.asm`): 8 priority bands (d7 = 7 down to
0). Each band is an $80-byte buffer in `Sprite_Table_Input`, holding a count
word followed by object .w addresses.

**SAT building**: Two-phase system identical to S.C.E.:
1. `DisplaySprite` queues object addresses into priority band (called by each
   object at the end of its routine)
2. `BuildSprites` walks bands in order, reads mappings, writes VDP SAT entries

**DisplaySprite** (from `run_objects.asm` line 688+): Adds object .w address
to the appropriate priority band's list. Uses the same `Sprite_Table_Input`
approach as S.C.E. (inherited from S3K).

**Mapping systems** (`build_sprites.asm` lines 95-149): Three render methods:
- **Classic**: Standard mapping frame lookup, piece loop
- **Static**: Single frame, no lookup
- **Compound**: Parent + child sub-sprites with per-child x/y/frame offsets

**DrawSprite** (line 167+): Reads 8-byte mapping pieces: {y_offset(1), padding,
size(1), padding, art_tile(2), unused(2), x_pos(2)}. Note: the mapping format
has 8 bytes per piece but the actual piece reads skip 2 bytes.

Four flip code paths identical to S.C.E., with the same width-correction
lookup tables.

**Sprite limit**: Hard check at 80 (line 88: `cmpi.b #80, d5`).

### E. Velocity / Movement

**Velocity application** (`run_objects.asm` lines 171-181):
```asm
ObjectMoveAndFall:
    move.w  x_vel(a0), d0
    ext.l   d0
    lsl.l   #8, d0
    add.l   d0, x_pos(a0)
    move.w  y_vel(a0), d0
    addi.w  #$38, y_vel(a0)  ; gravity
    ext.l   d0
    lsl.l   #8, d0
    add.l   d0, y_pos(a0)
    rts
```
Same as S.C.E.: `ext.l + lsl.l #8 + add.l` pattern. 8.8 velocity shifted
to align with 16.16 position.

**Rich behavior composition** (lines 211-600): sonic_hack adds a library of
composable behaviors: Obj_FacePlayer, Obj_ShootAtPlayer, Obj_FollowFloor,
Obj_BounceOffFloor, Obj_BounceOffLevelFloor, Obj_HomeInOnPlayer,
Obj_ApplyFriction, Obj_FloatBobbing, Obj_ApplyGravity, Obj_WavyFlight,
Obj_RicochetOffWalls. Each takes a0 + optional d0/d1 params and chains
via `bsr.w`.

---

## 8. Current aeon Implementation

Source: `/home/volence/sonic_hacks/aeon/`

### A. Object State Table

**Size**: 80 bytes (`$50`) (`structs.asm` line 90).

**Field layout** (`structs.asm` lines 65-88):

| Offset | Size  | Name              | Category   |
|--------|-------|-------------------|------------|
| $00    | word  | code_addr (bank offset) | Universal |
| $02    | long  | x_pos (16.16)     | Universal  |
| $06    | long  | y_pos (16.16)     | Universal  |
| $0A    | word  | x_vel             | Universal  |
| $0C    | word  | y_vel             | Universal  |
| $0E    | byte  | render_flags      | Universal  |
| $0F    | byte  | collision_resp    | Universal  |
| $10    | long  | mappings          | Universal  |
| $14    | word  | art_tile          | Universal  |
| $16    | word  | priority          | Universal  |
| $18    | byte  | width_pixels      | Universal  |
| $19    | byte  | height_pixels     | Universal  |
| $1A    | byte  | anim              | Universal  |
| $1B    | byte  | mapping_frame     | Universal  |
| $1C    | long  | anim_cursor       | Universal  |
| $20    | byte  | subtype           | Universal  |
| $21    | byte  | respawn_index     | Universal  |
| $22    | word  | parent_ptr        | Universal  |
| $24    | word  | sibling_ptr       | Universal  |
| $26    | long  | anim_table        | Universal  |
| $2A    | word  | wait_timer        | Universal  |
| $2C-$4F| 36 bytes | sst_custom    | Per-type   |

**Code dispatch**: Same bank system as sonic_hack (`objects.asm` line 177):
```asm
moveq   #OBJ_CODE_BANK, d0  ; d0 = 1
swap    d0                    ; d0 = $00010000
move.w  (a0), d0              ; d0 = $0001XXXX
beq.s   .next                 ; zero = empty
movea.l d0, a1
jsr     (a1)
```

**Position format**: 16.16 fixed point via longword. Position at $02/$06
(note: moved from sonic_hack's $10/$14 to $02/$06 for tighter packing).

**Standard vs Custom**: $2C bytes universal (55%), 36 bytes custom (45%).
Compared to sonic_hack, the universal section is larger because parent_ptr,
sibling_ptr, anim_table, and wait_timer are all promoted to universal.

### B. Slot Allocation & Pools

**Pool separation** (`constants.asm` lines 112-116):
- NUM_PLAYERS = 2
- NUM_DYNAMIC = 40
- NUM_EFFECTS = 16
- NUM_SYSTEM = 8
- Total = 66 slots

**Allocation** (`objects.asm`): **Free stack** -- O(1) allocation.
```asm
AllocDynamic:
    cmpi.w  #Dynamic_Free_Stack, (Dynamic_Free_SP).w
    beq.s   .full               ; stack empty?
    movea.w (Dynamic_Free_SP).w, a1
    subq.w  #2, (Dynamic_Free_SP).w
    movea.w -(a1), a1           ; pop address
    andi    #$FE, ccr           ; clear carry
    rts
```
Separate stacks for Dynamic and Effect pools. Player and System slots are
fixed -- no allocation/deallocation.

**Deallocation** (`objects.asm` lines 97-155): Determines pool by address
range comparison, pushes slot address back to the appropriate free stack,
then zeros all $50 bytes.

### C. Object Dispatch

**Update order**: Linear scan of ALL slots (`objects.asm` lines 165-186).
No execution culling yet. No separate passes for different pool types.

**Frozen behavior**: `RunObjects_Frozen` -- when Game_Paused is set, all
occupied slots get `Draw_Sprite` only, no object code execution.

**Register conventions**: a0 = self SST. Object code must preserve a0 and d7.

### D. Sprite Rendering

**Priority system** (`sprites.asm` lines 73-97): 8 priority bands, up to 16
objects per band (SPRITES_PER_BAND = 16). Object addresses stored in
`Sprite_Bands` array.

**SAT building** (`sprites.asm` lines 130-311): Two-phase:
1. `Draw_Sprite` performs on-screen check + queues to priority band
2. `Render_Sprites` walks bands 7 to 0 (front to back), reads mappings,
   writes 8-byte VDP SAT entries

**VDP-order mappings**: Mapping pieces are 8 bytes matching VDP SAT layout:
{y_offset(2), size_code(1), padding(1), tile_attrs(2), x_offset(2)}.
The padding byte gets overwritten with the link field. This eliminates
field reordering in the inner loop -- pieces are nearly memcpy'd.

**Flipping**: Two code paths (unflipped + X-flipped). X-flip negates X
offset, toggles flip bit ($0800), and applies width correction. No Y-flip
path yet.

**Sprite limit**: Hard cap at 80 (`cmpi.w #MAX_VDP_SPRITES, d5`).

**No sprite overflow handling**: When limit reached, remaining objects
are simply dropped.

### E. Velocity / Movement

**Velocity application** (`objects.asm` lines 213-220):
```asm
ObjectMove:
    move.w  SST_x_vel(a0), d0
    ext.l   d0
    add.l   d0, SST_x_pos(a0)
    move.w  SST_y_vel(a0), d0
    ext.l   d0
    add.l   d0, SST_y_pos(a0)
    rts
```
Note: **No `lsl.l #8` shift.** aeon uses `ext.l + add.l` directly,
treating velocity as a 16-bit signed integer added to the 16.16 position.
This means 1 velocity unit = 1/65536 pixel (vs sonic_hack where 1 velocity
unit = 1/256 pixel after the `lsl.l #8`). Velocity of $100 moves 1 pixel/frame
in sonic_hack but only 1/256 pixel in aeon.

**Gravity**: Not integrated into ObjectMove. Separate `Obj_ApplyGravity` call.

---

## 9. Online Findings

### plutiedev.com -- Sprite Table Reference

VDP SAT entry (8 bytes):
- +0 word: Y coordinate (add 128 for screen position, 9-bit wrapping)
- +2 byte: size code (bits 3-2: width-1 in cells, bits 1-0: height-1)
- +3 byte: link (index of next sprite, 7 bits, 0 = end)
- +4 word: tile + flags (bit 15: priority, bits 14-13: palette, bit 12:
  v-flip, bit 11: h-flip, bits 10-0: tile index)
- +6 word: X coordinate (add 128, 9-bit)

**Sprite masking**: Setting X position to 0 masks all remaining sprites on
that scanline. Used for scroll masking effects.

**Sprite cache**: VDP internally caches Y, size, and link fields. The cache
is write-through -- VRAM writes to the sprite table region update it
immediately. Changing the sprite table base address register does NOT
invalidate the cache, so you get half old data / half new data until VRAM
is rewritten.

**Per-scanline limits** (H40 mode):
- 80 sprites total, 20 per scanline, 320 sprite pixels per scanline
- Exceeding per-line limits: remaining sprites on that line are invisible
  (dot overflow)

### SpritesMind Forums -- Sprite Priority

The VDP draws sprites in **link order** -- first sprite in the chain is drawn
ON TOP of later sprites (opposite of many systems). To get correct Z-ordering,
objects that should appear in front must be earlier in the link chain.

One practical technique: maintain two sub-chains (high-priority and low-
priority), then concatenate them -- all high-priority sprites link together
first, then all low-priority sprites. This creates a two-layer depth sort
without full sorting.

The thread notes that sorting the sprite table by priority flag in byte 4
(bit 7) lets you use the VDP's own priority bit to separate sprites between
scroll planes while using link order for same-plane Z-ordering.

### SGDK Sprite Engine

SGDK (C SDK) implements:
- Object pooling via `POOL_create(MAX_SPRITE, sizeof(Sprite))`
- Automatic VRAM allocation for sprite tiles
- DPLC-like tile management to minimize wasted VRAM
- Software sprite composition (multi-hardware-sprite objects)
- Sprite visibility culling

### LUMINARY Engine (Matt Phillips / BigEvilCorporation)

A 68000 assembly engine for Mega Drive, successor to the Tanglewood engine:
- **Entity-component object system** with dynamic spawning and prefab support
- **Block-based dynamic memory allocator** for objects
- **Multi-sprite rendering** with timeline-track animation
- **Rigid body physics** with Sonic-like terrain collision
- **Fixed-point 16.16 math library**
- **Streaming plane maps** with block compression
- 86.3% assembly code

The entity-component approach is notable -- it's the only Genesis engine found
that uses composition over inheritance for objects, similar to modern game
engines.

### VDP Sprite Cache Implications for Engine Design

The VDP's sprite cache has important implications:
1. You must write the SAT to VRAM every frame (or at least the Y/size/link
   fields) even if nothing changed, because the cache is write-through
2. If you change the sprite table base address (VDP reg $85), you MUST also
   DMA the new table's contents -- the old cache persists otherwise
3. The Y coordinate cache means the VDP evaluates per-scanline sprite limits
   based on cached Y values, which is why you should DMA the SAT at the START
   of VBlank before the first line of the next frame begins rendering

---

## 10. Comparative Analysis

### SST Size Comparison

| Engine            | Size  | Reason |
|-------------------|-------|--------|
| Thunder Force IV  | 32    | Shmup -- simple objects, type-segregated pools handle complexity |
| Vectorman         | 12*   | Dispatch stub only -- data lives elsewhere |
| Sonic 2 (stock)   | 64    | Original baseline |
| sonic_hack        | 80    | Expanded from S2 for more per-type data + expansion fields |
| S.C.E. (S3K)      | 80    | Same as sonic_hack, S3K lineage |
| aeon         | 80    | Matches sonic_hack/S3K |
| Batman & Robin    | ~90   | Linked-list overhead + script variables + fractional pos |
| Gunstar/Alien Soldier | 96 | Complex boss state + link pointers |

### Allocation Strategy Comparison

| Engine           | Method               | Complexity | Waste |
|------------------|----------------------|------------|-------|
| S.C.E.           | Linear scan          | O(n)       | Cycles scanning empty slots |
| sonic_hack       | Linear scan          | O(n)       | Same |
| aeon        | **Free stack**       | **O(1)**   | 2 bytes per slot in stack array |
| Batman & Robin   | **Doubly-linked list**| **O(1)**   | 4 bytes per slot for next/prev |
| Vectorman        | Compact table        | O(1)†      | Must compact on delete |
| TF4              | Per-pool linear      | O(n/pool)  | Small n per pool |

†Vectorman's terminator approach is O(1) for append but requires compaction.

### Dispatch Mechanism Comparison

| Engine           | Method                  | Overhead per call |
|------------------|-------------------------|-------------------|
| S.C.E.           | jsr through longword ptr| ~20 cycles (move.l + movea.l + jsr) |
| sonic_hack       | Bank + word offset jsr  | ~24 cycles (moveq + swap + move.w + movea.l + jsr) |
| aeon        | Bank + word offset jsr  | ~24 cycles (same as sonic_hack) |
| Batman & Robin   | Threaded bytecode       | ~12 cycles per opcode (movea.w + jmp) |
| Vectorman        | Two function pointers   | ~40 cycles (2x jsr) |
| Gunstar          | Index into jump table   | ~22 cycles (move.w + lea + jmp) |

### Priority / SAT Building Comparison

| Engine           | Priority System            | SAT Building     |
|------------------|----------------------------|------------------|
| S.C.E.           | 8 bands, $80 bytes each    | Two-phase: queue then render |
| sonic_hack       | 8 bands, $80 bytes each    | Two-phase (same) |
| aeon        | 8 bands, 16 objs/band      | Two-phase (same concept, cleaner) |
| Batman & Robin   | Inline during processing   | Direct VDP write |
| Vectorman        | Implicit (table order)     | Separate render call |
| Gunstar          | Art tile bits              | Unknown |
| TF4              | Priority nibbles + flicker | Per-pool |

### Velocity Format Comparison

| Engine           | Position  | Velocity  | Integration |
|------------------|-----------|-----------|-------------|
| S.C.E.           | 16.16 (L) | 8.8 (W)  | ext.l + asl.l #8 + add.l |
| sonic_hack       | 16.16 (L) | 8.8 (W)  | ext.l + lsl.l #8 + add.l |
| aeon        | 16.16 (L) | 16.0 (W) | ext.l + add.l (no shift!) |
| Batman & Robin   | 16+16 (2W)| 16.16 (L)| Direct add (vel already aligned) |
| Gunstar          | 16.0 (W)  | 16.16 (L)| Unknown alignment |

**Note on aeon velocity**: The current implementation adds a sign-extended
word directly to a longword position. This gives extremely fine-grained velocity
(1 unit = 1/65536 pixel) but means the range of useful velocities is very
different from sonic_hack. A velocity of $100 in sonic_hack moves 1 pixel/frame;
in aeon it moves only 1/256 pixel/frame. To move 1 pixel/frame in
aeon, you need velocity = $10000 -- which overflows a word. This is likely
a design choice that needs verification: either the velocity interpretation is
intentionally different, or the `asl.l #8` shift was accidentally omitted.

---

## 11. Decision Points

### D1. SST Size: 64 / 80 / 96 bytes?

| Size | Used by | Pro | Con |
|------|---------|-----|-----|
| 64   | Stock S2 | Tightest RAM, most slots possible | Not enough custom space for complex bosses |
| 80   | S3K, sonic_hack, aeon, S.C.E. | Good balance -- 36 bytes custom + link fields | Wastes ~16 bytes for simple objects (rings, dust) |
| 96   | Gunstar, Alien Soldier | Room for dual link pointers + rich boss state | -25% slots vs 80-byte at same RAM budget |

**Current choice (80)**: Well-validated. Every Sonic-family engine uses 80.
Treasure's 96 adds dual links but we already have parent_ptr + sibling_ptr
at $22/$24. The 36-byte custom region at $2C-$4F provides adequate space.

### D2. Allocation: Linear Scan vs Free Stack vs Linked List?

| Method | Used by | Pro | Con |
|--------|---------|-----|-----|
| Linear scan | S.C.E., sonic_hack | Simple, no extra RAM | O(n) per allocation, ~90 iterations worst case |
| Free stack | aeon | O(1), simple, 2 bytes per slot overhead | Must match pool on deallocation |
| Linked list | Batman & Robin | O(1), no pool detection needed | 4+ bytes overhead per slot, complex code |

**Current choice (free stack)**: Good. O(1) with minimal complexity. Pool
detection in DeleteObject is a bit verbose but correct. Consider: could
store pool_id in one of the custom bytes to avoid address-range comparisons.

### D3. Dispatch: Code Pointer vs Bank+Offset vs Jump Table vs Bytecode?

| Method | Used by | Pro | Con |
|--------|---------|-----|-----|
| Full 32-bit pointer | S.C.E. | Simplest, fastest (1 fewer instruction) | 4 bytes in SST instead of 2 |
| Bank + word offset | sonic_hack, aeon | 2-byte SST field, 64KB code space | ~4 extra cycles (moveq+swap) |
| Index + jump table | Gunstar | Compact state encoding | State transitions need table updates |
| Threaded bytecode | Batman & Robin | Tiny script size, yield/resume for free | Complex runtime, hard to debug |

**Current choice (bank+offset)**: Reasonable. The 2-byte savings per slot
(2 * 66 = 132 bytes) is marginal. S.C.E.'s full-pointer approach is 4 cycles
faster per dispatch (no moveq+swap). Consider switching to full longword
pointer if the 132 bytes aren't critical -- it simplifies the dispatch loop
and removes the OBJ_CODE_BANK coupling.

### D4. Priority System: Bands vs Sort vs Linked-List Reorder?

| Method | Used by | Pro | Con |
|--------|---------|-----|-----|
| Priority bands (8 levels) | S.C.E., sonic_hack, aeon | Simple, O(1) insertion, proven | Only 8 priority levels; within-band order depends on insertion order |
| Sort sprite table by priority bit | SpritesMind approach | Uses VDP priority bit for plane separation | Only 2 priority levels without additional software sorting |
| Type-segregated pools | TF4 | Zero priority overhead | Inflexible; new types need new pools |

**Current choice (8 bands)**: Well-proven across all Sonic engines. The 16
objects per band limit (SPRITES_PER_BAND) may be tight for busy scenes --
S.C.E. uses 31 per band ($80/2 - 1). Consider increasing to 24 or 32.

### D5. Velocity Integration: ext.l+add.l vs ext.l+asl.l+add.l?

The aeon currently uses `ext.l + add.l` (no shift), while sonic_hack
and S.C.E. use `ext.l + lsl.l #8 + add.l` (shift velocity left 8 bits).

| Method | Vel meaning | 1 px/frame vel | Subpixel resolution |
|--------|-------------|----------------|---------------------|
| ext.l + add.l | 1 unit = 1/65536 px | $10000 (overflow!) | 16 bits |
| ext.l + asl.l #8 + add.l | 1 unit = 1/256 px | $100 | 8 bits |
| Batman & Robin (32-bit vel + 32-bit pos) | 1 unit = 1/65536 px | $10000 in vel longword | 16 bits |

The sonic_hack/S.C.E. approach is better for a Sonic game because:
- Velocity values fit in a word ($100 = 1 px/frame, $680 = jump velocity)
- 256 subpixels is sufficient for smooth movement
- All existing Sonic physics constants assume 8.8 velocity format
- The `lsl.l #8` costs only 24 extra cycles (8 + 2*n where n=8)

**Recommendation**: Add the `asl.l #8` shift to ObjectMove. Without it,
porting sonic_hack physics constants requires dividing every velocity value
by 256, which is error-prone and wastes precision in the wrong place.

### D6. Execution Culling

sonic_hack's `RunObject_Culled` skips objects >768px from camera. S.C.E.
does NOT cull -- all 110 slots execute every frame.

| Approach | Pro | Con |
|----------|-----|-----|
| No culling | Simplest, no edge cases | Wastes cycles on far objects |
| X-distance culling (sonic_hack) | Saves jsr overhead for distant objects | Objects must handle being "frozen" gracefully |
| Active-flag filtering (Batman & Robin) | Clean per-object control | Requires explicit activation management |
| Type-based split (Vectorman) | Render skipped via null pointer | Requires separate render pass |

**Current state**: aeon has no culling. Adding sonic_hack-style X-culling
for the dynamic pool is low-risk and high-reward. Alternatively, Vectorman's
split update/render approach could be adapted: objects set a "needs render"
flag; Draw_Sprite only queues objects with the flag.

### D7. Sprite Overflow Handling

| Approach | Used by | Behavior |
|----------|---------|----------|
| Drop excess | S.C.E., sonic_hack, aeon | Sprites beyond 80 are invisible |
| Round-robin flicker | TF4 | Rotate priority each frame; all sprites visible over 4 frames |
| Pre-sort by priority | SpritesMind | Ensure critical sprites (player, HUD) always render |

**Current state**: aeon drops excess sprites. For a Sonic game, round-
robin flicker is rarely needed (scenes with >80 VDP sprites are unusual).
But ensuring the player and HUD are always first in the link chain (and
thus always rendered) is important -- the current front-to-back band
ordering (band 7 first) already achieves this if player/HUD use band 7.

### D8. Multi-Piece Sprites

| Approach | Used by | How it works |
|----------|---------|--------------|
| Child sprite offsets in SST | S.C.E., sonic_hack | render_flags.multi_sprite flag; sub-sprite data at SST $18+ |
| Separate child objects | Treasure, aeon | Each piece is its own SST with parent_ptr link |
| VDP-order mapping pieces | aeon | Mapping pieces are 8 bytes matching SAT layout |

aeon's VDP-order mapping format eliminates field reordering in the piece
loop, which is a clear optimization over the 6-byte mapping format used by
Sonic engines (which requires separate writes to rearrange y, size, link,
tile, x into VDP order).

### D9. Deferred Deletion

| Approach | Used by | Pro | Con |
|----------|---------|-----|-----|
| Immediate delete | S.C.E., Sonic 2 | Simple | Can leave stale references if object A deletes object B while B is queued for processing |
| Deferred sweep | sonic_hack | Safe -- no stale references during frame | Extra sweep pass at frame end |
| Linked-list removal | Batman & Robin | O(1), safe by design | List management overhead |

sonic_hack's deferred deletion is a good pattern. aeon should adopt it
for the dynamic pool. The free-stack push can happen during the sweep.

---

## 12. Summary of Unique/Clever Techniques

1. **Batman & Robin's threaded bytecode** -- objects as scripts with
   yield/resume. Dramatically reduces code size for complex multi-phase
   behaviors. Not suitable for a Sonic engine (too much overhead for simple
   objects) but the yield/resume concept could inspire a coroutine-like system
   for cutscenes.

2. **Vectorman's split update/render** -- null render pointer skips sprite
   building entirely. Adaptable: use a flag bit in render_flags instead of a
   second pointer.

3. **Treasure's link pointers** -- parent/child coordination via fixed SST
   offset ($58). aeon already has parent_ptr + sibling_ptr, matching
   Alien Soldier's dual-link system.

4. **Thunder Force IV's type-segregated pools with fast bullet inner loop** --
   the bullet processing loop has zero type-checking overhead. Applicable if
   aeon ever needs high bullet counts (boss fights).

5. **TF4's round-robin sprite flicker** -- ensures all objects remain visible
   across 4-frame windows. Insurance for dense scenes.

6. **aeon's VDP-order mappings** -- pieces match SAT layout, eliminating
   field reordering. This is better than every reference engine's mapping
   format.

7. **sonic_hack's behavior composition library** -- Obj_FacePlayer,
   Obj_ShootAtPlayer, Obj_FollowFloor, etc. Provides building blocks that
   reduce object code size and encourage consistency.

8. **sonic_hack's execution culling** -- skipping far-off-screen objects saves
   the full jsr overhead. ~768px threshold is wide enough to not affect
   gameplay.

9. **Batman & Robin's O(1) linked-list allocator** -- eliminates the linear
   scan entirely. aeon's free stack achieves the same O(1) performance
   with less complexity.

10. **S.C.E.'s extra render slots** -- `Render_sprite_first_RAM` /
    `Render_sprite_last_RAM` allow injecting render callbacks for systems that
    don't use the object system (rings, water). Worth considering for aeon.
