# §3 Object System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete object system — SST, allocation, dispatch, sprite rendering, animation, collision, child creation, particles, and advanced sprite optimizations — with research before each subsystem.

**Architecture:** Word-offset dispatch via `objroutine` function (sonic_hack pattern), O(1) free slot stack allocation, priority-band sprite rendering, self-advancing animation cursor (Alien Soldier), type-dispatched collision, data-driven child creation. All code fresh for s4_engine — no ported routines.

**Tech Stack:** AS Macro Assembler, 68000 assembly, Sega Genesis VDP

**Conventions:** Read `CODING_CONVENTIONS.md` before writing ANY code. Key rules: `.s`/`.w`/`.l` on every branch/jump, `function` for compile-time math, `struct`/`endstruct` for data, PascalCase routines, ALL_CAPS constants, `.lowercase` locals.

**Testing:** Build with `./build.sh`, load ROM in Exodus emulator (user launches manually), verify with Exodus MCP tools. No unit test framework — verification is visual + memory inspection.

**Research Protocol:** Every research task must check ALL 7 reference disassemblies + online sources per CLAUDE.md. Reference paths:
- S.C.E.: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`
- Batman & Robin: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/`
- Vectorman: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/`
- Gunstar Heroes: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/`
- Alien Soldier: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/`
- Thunder Force IV: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/`
- sonic_hack: `/home/volence/sonic_hacks/sonic_hack/`
- Online: plutiedev, md.railgun.works, SpritesMind, SGDK, GitHub homebrew

---

## File Structure

### New files (create)

| File | Responsibility |
|------|---------------|
| `engine/objects.asm` | RunObjects loop, InitObjectRAM, AllocSlot, FreeSlot, DeleteObject, ObjectMove |
| `engine/sprites.asm` | Draw_Sprite (priority band insert), Render_Sprites (VDP SAT builder), InitSpriteSystem |
| `engine/animate.asm` | AnimateSprite bytecode interpreter, speed-linked timing (Phase 2) |
| `engine/collision.asm` | TouchResponse, per-type collision handlers, AABB math (Phase 3) |
| `engine/children.asm` | CreateChild_Normal, CreateChild_Complex, cleanup chains (Phase 4) |
| `engine/load_object.asm` | Load_Object format-byte reader, field initialization (Phase 4) |
| `objects/test_static.asm` | Phase 1 test: static display object |
| `objects/test_player.asm` | Phase 3 test: controllable player with gravity |
| `objects/test_enemy.asm` | Phase 3 test: simple enemy with collision |
| `objects/test_solid.asm` | Phase 3 test: solid block with side detection |

| `objects/test_parent.asm` | Phase 4 test: multi-part parent with children |
| `objects/test_particle.asm` | Phase 4 test: particle emitter |
| `data/mappings/test_mappings.asm` | Simple sprite mappings for test objects |
| `test/object_test_state.asm` | Game state: init objects, spawn test scene, run loop |

### Existing files (modify)

| File | Changes |
|------|---------|
| `structs.asm` | Add SST struct, SpriteMapping struct |
| `constants.asm` | Add object system constants (slot counts, bank number, collision types, priority bands) |
| `macros.asm` | Add `objroutine` function, `ObjCodeBase` reference |
| `ram.asm` | Add Object_RAM, free slot stacks, priority band lists, camera variables |
| `main.asm` | Include new engine files and object code, place ObjCodeBase alignment |
| `engine/game_loop.asm` | Wire test game states |
| `docs/ENGINE_ARCHITECTURE.md` | Fix anim_cursor alignment ($1B→$1C), keep in sync with implementation |

---

## Phase 1: SST + Free Slot Stack + RunObjects + Basic Sprite Rendering

### Task 1: SST struct + object constants + objroutine function

**Files:**
- Modify: `structs.asm`
- Modify: `constants.asm`
- Modify: `macros.asm`
- Modify: `docs/ENGINE_ARCHITECTURE.md` (fix alignment bug)

**IMPORTANT — alignment fix:** The documented SST layout has `anim_cursor` (longword) at offset $1B (odd). The 68000 requires word/longword accesses at even addresses — this would cause an Address Error. Fix: swap `mapping_frame` (byte, $1B) and `anim_cursor` (long, $1C) so the longword lands on an even offset.

- [ ] **Step 1: Add SST struct to `structs.asm`**

Append after the DMAEntry struct:

```asm
; -----------------------------------------------
; Sprite Status Table entry (§3.1)
; Object system per-slot data structure.
; Fields grouped logically; anim_cursor at $1C (even) for longword alignment.
; -----------------------------------------------

SST struct
code_addr       ds.w 1      ; $00 — object code offset from ObjCodeBase (0 = empty)
x_pos           ds.l 1      ; $02 — 16.16 subpixel X position
y_pos           ds.l 1      ; $06 — 16.16 subpixel Y position
x_vel           ds.w 1      ; $0A — horizontal velocity
y_vel           ds.w 1      ; $0C — vertical velocity
render_flags    ds.b 1      ; $0E — display flags (bit 0 = on-screen, bit 1 = x-flip, bit 2 = y-flip, bit 3 = coordinate mode)
collision_resp  ds.b 1      ; $0F — collision type dispatch (0 = none) [spec says collision_response — update spec in Task 23]
mappings        ds.l 1      ; $10 — sprite mapping pointer (ROM)
art_tile        ds.w 1      ; $14 — VRAM tile index + palette + priority
priority        ds.w 1      ; $16 — sprite priority band (0-7, 0 = back)
width_pixels    ds.b 1      ; $18 — collision width (full, not half)
height_pixels   ds.b 1      ; $19 — collision height (full, not half)
anim            ds.b 1      ; $1A — current animation ID
mapping_frame   ds.b 1      ; $1B — current mapping index
anim_cursor     ds.l 1      ; $1C — self-advancing animation ROM pointer
subtype         ds.b 1      ; $20 — object subtype
respawn_index   ds.b 1      ; $21 — respawn tracking
parent_ptr      ds.w 1      ; $22 — parent object RAM address
sibling_ptr     ds.w 1      ; $24 — sibling link (multi-part objects)
anim_table      ds.l 1      ; $26 — animation table pointer (ROM)
wait_timer      ds.w 1      ; $2A — Obj_Wait countdown
sst_custom      ds.b 36     ; $2C-$4F — per-object custom data overlay
SST endstruct

        if SST_len <> $50
          error "SST struct is \{SST_len} bytes, expected $50"
        endif
```

- [ ] **Step 2: Add object system constants to `constants.asm`**

Append after the Decompression section:

```asm
; -----------------------------------------------
; Object System (§3)
; -----------------------------------------------

; Slot counts per pool
NUM_PLAYERS             = 2
NUM_DYNAMIC             = 40
NUM_EFFECTS             = 16
NUM_SYSTEM              = 8
NUM_TOTAL_SLOTS         = NUM_PLAYERS+NUM_DYNAMIC+NUM_EFFECTS+NUM_SYSTEM

; Object code bank (ObjCodeBase aligned to $10000)
OBJ_CODE_BANK           = 1         ; moveq #1,d0; swap d0 → $00010000

; Sprite priority bands
PRIORITY_BANDS          = 8
SPRITES_PER_BAND        = 16

; Collision response types
COLLISION_NONE          = 0
COLLISION_ENEMY         = 1
COLLISION_BOSS          = 2
COLLISION_HURT          = 3
COLLISION_MONITOR       = 4
COLLISION_RING          = 5
COLLISION_BUBBLE        = 6
COLLISION_PROJECTILE    = 7
COLLISION_SOLID         = 8
COLLISION_SOLID_BREAK   = 9
COLLISION_SPRING        = 10
COLLISION_SOLID_HURT    = 11
COLLISION_TOUCH         = 12

; render_flags bits
RF_ONSCREEN             = 0         ; set by Draw_Sprite if visible
RF_XFLIP                = 1         ; horizontal flip
RF_YFLIP                = 2         ; vertical flip
RF_COORDMODE            = 3         ; 0 = world coords, 1 = screen coords

; Spawn guard
MAX_SPAWNS_PER_FRAME    = 8

; Game state IDs (extend existing)
GS_OBJECT_TEST          = 2
```

- [ ] **Step 3: Add `objroutine` function and helpers to `macros.asm`**

Add after the `dmaLength` function:

```asm
; Object code offset from ObjCodeBase (word — stored at SST $00)
; Usage: move.w #objroutine(MyObject), code_addr(a0)
; ObjCodeBase is defined in main.asm at align $10000
objroutine  function x, (x)-ObjCodeBase
```

- [ ] **Step 4: Fix SST alignment in `docs/ENGINE_ARCHITECTURE.md`**

Update the SST layout in §3.1 to swap `mapping_frame` and `anim_cursor`:
- `$1A  anim` (byte)
- `$1B  mapping_frame` (byte) — moved here for longword alignment
- `$1C  anim_cursor` (long) — now at even offset, was $1B (would cause Address Error)

- [ ] **Step 5: Build to verify struct compiles**

Run: `./build.sh`
Expected: Build succeeds. The struct definitions don't generate ROM data — they just establish offsets.

- [ ] **Step 6: Commit**

```bash
git add structs.asm constants.asm macros.asm docs/ENGINE_ARCHITECTURE.md
git commit -m "feat(§3): add SST struct, object constants, objroutine function

Fix alignment bug: anim_cursor (longword) was at odd offset \$1B,
swapped with mapping_frame (byte) so longword lands at \$1C."
```

---

### Task 2: Object RAM + sprite system RAM

**Files:**
- Modify: `ram.asm`

- [ ] **Step 1: Add Object RAM and sprite system variables to `ram.asm`**

Add after the Decompression buffer section, before `RAM_End`:

```asm
; -----------------------------------------------
; Object System (§3)
; -----------------------------------------------

; Object RAM — all slots contiguous, stride = SST_len ($50)
Object_RAM:
Player_1:               ds.b SST_len
Player_2:               ds.b SST_len
Dynamic_Slots:          ds.b SST_len * NUM_DYNAMIC
System_Slots:           ds.b SST_len * NUM_SYSTEM
Effect_Slots:           ds.b SST_len * NUM_EFFECTS
Object_RAM_End:

; Free slot stacks — word arrays of SST addresses, one per pool
Dynamic_Free_Stack:     ds.w NUM_DYNAMIC
Dynamic_Free_SP:        ds.w 1

Effect_Free_Stack:      ds.w NUM_EFFECTS
Effect_Free_SP:         ds.w 1

; Spawn guard counter (reset each frame)
Spawn_Count:            ds.w 1

; -----------------------------------------------
; Sprite Rendering (§3.5)
; -----------------------------------------------

; Priority band lists — each band holds up to SPRITES_PER_BAND object addresses
Sprite_Bands:           ds.w SPRITES_PER_BAND * PRIORITY_BANDS
Sprite_Band_Counts:     ds.b PRIORITY_BANDS
                        ds.b 1          ; pad to even

; Sprite link counter (next VDP sprite index to assign)
Sprite_Link_Next:       ds.w 1

; Total sprites rendered this frame
Sprites_Rendered:       ds.w 1

; -----------------------------------------------
; Camera (stub for §3, real implementation in §4)
; -----------------------------------------------
Camera_X:               ds.l 1          ; 16.16 camera X position
Camera_Y:               ds.l 1          ; 16.16 camera Y position

; Game pause / freeze flag
Game_Paused:            ds.b 1
                        ds.b 1          ; pad
```

- [ ] **Step 2: Build to verify RAM fits**

Run: `./build.sh`
Expected: Build succeeds. The `phase`/`dephase` overflow check catches any RAM overflow at build time.

- [ ] **Step 3: Commit**

```bash
git add ram.asm
git commit -m "feat(§3): add Object RAM, free slot stacks, sprite band lists, camera stub"
```

---

### Task 3: Object system core — InitObjectRAM, AllocSlot, FreeSlot, DeleteObject, RunObjects

**Files:**
- Create: `engine/objects.asm`
- Modify: `main.asm` (include it)

- [ ] **Step 1: Create `engine/objects.asm` with all core routines**

```asm
; Object system core — allocation, dispatch, deletion

; -----------------------------------------------
; InitObjectRAM — clear all slots, push addresses to free stacks
; Called at game state init (level start, etc.)
; In:  none
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
InitObjectRAM:
        ; Zero all Object RAM
        lea     (Object_RAM).w, a0
        move.w  #(Object_RAM_End-Object_RAM)/4-1, d0
        moveq   #0, d1
.clear:
        move.l  d1, (a0)+
        dbf     d0, .clear

        ; Init dynamic free stack — push addresses from last to first
        ; so first slot is popped first (LIFO order matches slot 2→41)
        lea     (Dynamic_Free_Stack).w, a0
        lea     (Dynamic_Slots).w, a1
        move.w  #NUM_DYNAMIC-1, d0
.push_dyn:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_dyn
        move.w  #Dynamic_Free_Stack+NUM_DYNAMIC*2, (Dynamic_Free_SP).w

        ; Init effect free stack
        lea     (Effect_Free_Stack).w, a0
        lea     (Effect_Slots).w, a1
        move.w  #NUM_EFFECTS-1, d0
.push_eff:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_eff
        move.w  #Effect_Free_Stack+NUM_EFFECTS*2, (Effect_Free_SP).w

        ; Reset spawn counter
        clr.w   (Spawn_Count).w
        rts

; -----------------------------------------------
; AllocDynamic — pop a free dynamic slot
; In:  none
; Out: a1 = SST address of allocated slot (or carry set if full)
; Clobbers: none
; -----------------------------------------------
AllocDynamic:
        cmpi.w  #Dynamic_Free_Stack, (Dynamic_Free_SP).w
        beq.s   .full
        movea.w (Dynamic_Free_SP).w, a1
        subq.w  #2, (Dynamic_Free_SP).w
        movea.w -(a1), a1
        ori     #0, ccr                 ; clear carry (success)
        rts
.full:
        ori     #1, ccr                 ; set carry (pool exhausted)
        rts

; -----------------------------------------------
; AllocEffect — pop a free effect slot
; In:  none
; Out: a1 = SST address (or carry set if full)
; Clobbers: none
; -----------------------------------------------
AllocEffect:
        cmpi.w  #Effect_Free_Stack, (Effect_Free_SP).w
        beq.s   .full
        movea.w (Effect_Free_SP).w, a1
        subq.w  #2, (Effect_Free_SP).w
        movea.w -(a1), a1
        ori     #0, ccr
        rts
.full:
        ori     #1, ccr
        rts

; -----------------------------------------------
; DeleteObject — push slot back to appropriate free stack, zero SST
; In:  a0 = SST address of object to delete
; Out: none
; Clobbers: d0-d1
; -----------------------------------------------
DeleteObject:
        ; Determine which pool this slot belongs to
        cmpa.w  #Effect_Slots, a0
        bhs.s   .effect_pool
        cmpa.w  #Dynamic_Slots, a0
        bhs.s   .dynamic_pool
        ; Player or system slot — just clear, don't push to any free stack
        bra.s   .clear_slot

.dynamic_pool:
        movea.w (Dynamic_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Dynamic_Free_SP).w
        bra.s   .clear_slot

.effect_pool:
        cmpa.w  #Effect_Slots+SST_len*NUM_EFFECTS, a0
        bhs.s   .clear_slot             ; system slot if past effect range
        movea.w (Effect_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Effect_Free_SP).w

.clear_slot:
        ; Zero all $50 bytes of the SST entry
        moveq   #0, d0
        moveq   #0, d1
        move.l  d0, (a0)+       ; $00
        move.l  d0, (a0)+       ; $04
        move.l  d0, (a0)+       ; $08
        move.l  d0, (a0)+       ; $0C
        move.l  d0, (a0)+       ; $10
        move.l  d0, (a0)+       ; $14
        move.l  d0, (a0)+       ; $18
        move.l  d0, (a0)+       ; $1C
        move.l  d0, (a0)+       ; $20
        move.l  d0, (a0)+       ; $24
        move.l  d0, (a0)+       ; $28
        move.l  d0, (a0)+       ; $2C
        move.l  d0, (a0)+       ; $30
        move.l  d0, (a0)+       ; $34
        move.l  d0, (a0)+       ; $38
        move.l  d0, (a0)+       ; $3C
        move.l  d0, (a0)+       ; $40
        move.l  d0, (a0)+       ; $44
        move.l  d0, (a0)+       ; $48
        move.l  d0, (a0)+       ; $4C
        lea     -SST_len(a0), a0 ; restore a0 to slot start
        rts

; -----------------------------------------------
; RunObjects — dispatch all active object slots
; Convention: object routines receive a0 = self SST pointer.
; Object routines MUST preserve a0 and d7.
; In:  none
; Out: none
; Clobbers: d0-d6, a0-a6 (object code may clobber freely except a0/d7)
; -----------------------------------------------
RunObjects:
        ; Reset spawn counter for this frame
        clr.w   (Spawn_Count).w

        ; Check global freeze
        tst.b   (Game_Paused).w
        bne.w   RunObjects_Frozen

        lea     (Object_RAM).w, a0
        move.w  #NUM_TOTAL_SLOTS-1, d7

.loop:
        moveq   #OBJ_CODE_BANK, d0
        swap    d0                      ; d0 = bank << 16
        move.w  (a0), d0                ; d0 = bank | offset
        beq.s   .next                   ; zero = empty slot
        movea.l d0, a1
        jsr     (a1)                    ; dispatch — a0 = self, d7 = loop counter
.next:
        lea     SST_len(a0), a0
        dbf     d7, .loop
        rts

; -----------------------------------------------
; RunObjects_Frozen — render-only pass (player death, pause)
; Calls Draw_Sprite for each occupied slot, skips object logic
; -----------------------------------------------
RunObjects_Frozen:
        lea     (Object_RAM).w, a0
        move.w  #NUM_TOTAL_SLOTS-1, d7
.loop:
        tst.w   (a0)
        beq.s   .next
        bsr.w   Draw_Sprite
.next:
        lea     SST_len(a0), a0
        dbf     d7, .loop
        rts

; -----------------------------------------------
; ObjectMove — apply velocity to position
; Standard movement: x_pos += x_vel, y_pos += y_vel (subpixel)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMove:
        move.w  x_vel(a0), d0
        ext.l   d0
        add.l   d0, x_pos(a0)
        move.w  y_vel(a0), d0
        ext.l   d0
        add.l   d0, y_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveX — apply X velocity only
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveX:
        move.w  x_vel(a0), d0
        ext.l   d0
        add.l   d0, x_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveY — apply Y velocity only (gravity, falling)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveY:
        move.w  y_vel(a0), d0
        ext.l   d0
        add.l   d0, y_pos(a0)
        rts
```

- [ ] **Step 2: Add include to `main.asm`**

After the `include "engine/dplc.asm"` line, add:

```asm
    include "engine/objects.asm"
```

- [ ] **Step 3: Build to verify**

Run: `./build.sh`
Expected: Build succeeds. All routines assemble without errors.

- [ ] **Step 4: Commit**

```bash
git add engine/objects.asm main.asm
git commit -m "feat(§3): add object system core — InitObjectRAM, AllocSlot, DeleteObject, RunObjects"
```

---

### Task 4: Sprite rendering — Draw_Sprite + Render_Sprites

**Files:**
- Create: `engine/sprites.asm`
- Modify: `main.asm` (include it)

**Sprite mapping format (VDP-order, zero reordering):**
Each mapping frame is:
- `dc.w piece_count` (number of sprite pieces)
- `piece_count` × 8 bytes per piece, matching VDP SAT entry layout:
  - `+0 word`: Y offset (signed, relative to object center)
  - `+2 byte`: VDP size code (bits 3-2 = width-1, bits 1-0 = height-1)
  - `+3 byte`: padding (overwritten with link by renderer)
  - `+4 word`: tile attributes (relative — added to object's art_tile)
  - `+6 word`: X offset (signed, relative to object center)

Mapping table: array of word offsets from table start, one per frame index.

- [ ] **Step 1: Create `engine/sprites.asm`**

```asm
; Sprite rendering — two-phase: Draw_Sprite (priority insert) + Render_Sprites (VDP SAT builder)

; -----------------------------------------------
; InitSpriteSystem — clear all priority bands
; Called at frame start before RunObjects
; In:  none
; Out: none
; Clobbers: d0, a0
; -----------------------------------------------
InitSpriteSystem:
        lea     (Sprite_Band_Counts).w, a0
        moveq   #0, d0
        move.l  d0, (a0)+              ; clear counts 0-3
        move.l  d0, (a0)+              ; clear counts 4-7
        clr.w   (Sprites_Rendered).w
        rts

; -----------------------------------------------
; Draw_Sprite — add object to its priority band's display list
; Called during object update (objects call this themselves).
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
Draw_Sprite:
        ; --- On-screen check ---
        ; Compare object world X against camera viewport
        move.w  x_pos(a0), d0                   ; integer X (high word of 16.16)
        sub.w   (Camera_X).w, d0                ; screen-relative X
        addi.w  #32, d0                          ; margin for partially visible sprites
        cmpi.w  #320+64, d0                      ; viewport width + margins
        bhi.s   .offscreen

        move.w  y_pos(a0), d0                   ; integer Y
        sub.w   (Camera_Y).w, d0                ; screen-relative Y
        addi.w  #32, d0
        cmpi.w  #224+64, d0
        bhi.s   .offscreen

        ; Mark as on-screen
        bset.b  #RF_ONSCREEN, render_flags(a0)

        ; --- Add to priority band ---
        moveq   #0, d0
        move.w  priority(a0), d0                ; d0 = band index (0-7)
        cmpi.w  #PRIORITY_BANDS, d0
        bhs.s   .offscreen                      ; invalid band → skip

        lea     (Sprite_Band_Counts).w, a1
        move.b  (a1,d0.w), d1                   ; d1 = current count
        cmpi.b  #SPRITES_PER_BAND, d1
        beq.s   .offscreen                      ; band full → overflow to next (Phase 7)

        addq.b  #1, (a1,d0.w)                   ; increment count

        ; Compute entry address: Sprite_Bands + band*SPRITES_PER_BAND*2 + count*2
        lsl.w   #5, d0                           ; band * 32 (SPRITES_PER_BAND * 2)
        ext.w   d1
        add.w   d1, d1                           ; count * 2
        add.w   d0, d1
        lea     (Sprite_Bands).w, a1
        move.w  a0, (a1,d1.w)                   ; store object SST address
        rts

.offscreen:
        bclr.b  #RF_ONSCREEN, render_flags(a0)
        rts

; -----------------------------------------------
; Render_Sprites — walk priority bands, build VDP SAT from mapping data
; Called after RunObjects. Reads each queued object's mappings and writes
; VDP-format sprite entries to Sprite_Table_Buffer.
; In:  none
; Out: Sprite_Table_Buffer updated, Sprite_Table_Dirty set
; Clobbers: d0-d6, a0-a4
; -----------------------------------------------
Render_Sprites:
        lea     (Sprite_Table_Buffer).w, a4     ; a4 = SAT write cursor
        moveq   #0, d5                           ; d5 = sprite index (for link chain)

        ; Process bands 7→0 (front first, so they're first in link chain = on top)
        moveq   #PRIORITY_BANDS-1, d6

.band_loop:
        lea     (Sprite_Band_Counts).w, a0
        move.b  (a0,d6.w), d4
        beq.s   .next_band                       ; empty band
        subq.b  #1, d4                           ; dbf count
        ext.w   d4

        ; Compute band list base
        move.w  d6, d0
        lsl.w   #5, d0                           ; band * 32
        lea     (Sprite_Bands).w, a3
        adda.w  d0, a3                           ; a3 = band list base

.obj_loop:
        movea.w (a3)+, a0                        ; a0 = object SST address

        ; Read mapping data
        movea.l mappings(a0), a1                 ; a1 = mapping table
        moveq   #0, d0
        move.b  mapping_frame(a0), d0            ; d0 = frame index
        add.w   d0, d0                           ; word offset
        adda.w  (a1,d0.w), a1                    ; a1 = frame data pointer

        move.w  (a1)+, d3                        ; d3 = piece count
        beq.s   .obj_done                        ; 0 pieces → skip
        subq.w  #1, d3                           ; dbf count

        ; Pre-compute screen position from world position
        move.w  x_pos(a0), d1                    ; object world X (integer part)
        sub.w   (Camera_X).w, d1
        addi.w  #128, d1                         ; VDP X offset
        move.w  y_pos(a0), d2                    ; object world Y
        sub.w   (Camera_Y).w, d2
        addi.w  #128, d2                         ; VDP Y offset

        ; Pre-load art_tile for adding to each piece
        move.w  art_tile(a0), d0                 ; d0 = base tile + palette + priority

        ; Check flip flags
        btst.b  #RF_XFLIP, render_flags(a0)
        bne.s   .flipped_pieces

        ; --- Normal (unflipped) piece loop ---
.piece_loop:
        cmpi.w  #80, d5                          ; VDP sprite limit
        bhs.s   .sat_full

        ; Read 8-byte VDP-order mapping piece
        move.w  (a1)+, d6                        ; Y offset (signed)
        add.w   d2, d6                           ; + screen Y
        move.w  d6, (a4)+                        ; SAT word 0: Y position

        move.b  (a1)+, (a4)+                     ; SAT byte 2: size code
        addq.l  #1, a1                           ; skip padding byte
        move.b  d5, -1(a4)                        ; SAT byte 3: link to NEXT sprite

        move.w  (a1)+, d6                        ; tile attributes (relative)
        add.w   d0, d6                           ; + base art_tile
        move.w  d6, (a4)+                        ; SAT word 2: tile + flags

        move.w  (a1)+, d6                        ; X offset (signed)
        add.w   d1, d6                           ; + screen X
        move.w  d6, (a4)+                        ; SAT word 3: X position

        addq.w  #1, d5                           ; next sprite index
        dbf     d3, .piece_loop

.obj_done:
        dbf     d4, .obj_loop
.next_band:
        move.w  d6, d0                           ; save d6
        moveq   #PRIORITY_BANDS-1, d6            ; would need separate counter
        ; Actually, we need a band counter that doesn't conflict with d6
        ; Fix: use stack or a different register for band iteration
        ; (this is corrected below in the full implementation)
        subq.w  #1, d0
        move.w  d0, d6
        bpl.s   .band_loop

        ; Terminate link chain
        tst.w   d5
        beq.s   .no_sprites
        ; Set last sprite's link to 0 (end chain)
        clr.b   -5(a4)                           ; link byte of last SAT entry
.no_sprites:
        move.w  d5, (Sprites_Rendered).w
        move.b  #1, (Sprite_Table_Dirty).w       ; trigger DMA in VBlank
        rts

.sat_full:
        ; VDP can only display 80 sprites — stop rendering
        bra.s   .no_sprites

        ; --- Flipped piece loop (X offsets negated) ---
.flipped_pieces:
        ; Same as .piece_loop but negate X offset and set xflip bit on tile
        ; (Full implementation during Phase 3 when player needs flipping)
        bra.s   .piece_loop                      ; placeholder: render unflipped for now
```

**Note to implementer:** The band loop counter management above has a register conflict with d6 being used for both band iteration and temporary values inside the piece loop. The implementer should use a different register (or the stack) for the outer band counter. One clean approach: use `move.w d6, -(sp)` before the obj loop and `move.w (sp)+, d6` after, or dedicate a5 as the band counter.

- [ ] **Step 2: Fix the band loop register conflict**

The Render_Sprites routine above uses d6 for both the outer band counter and temporary piece data. Fix by pushing/popping d6 around the inner loops, or by restructuring to use a separate register. The implementer should resolve this cleanly — the algorithm is correct, the register allocation needs adjustment.

- [ ] **Step 3: Add link chain management**

The link field in each SAT entry should point to the NEXT sprite index (d5+1), except the last sprite which links to 0. The current code writes `d5` (current index) as the link — this should be `d5+1` for the next sprite. The last entry gets link=0 written after the loop.

Actually, looking at VDP sprite behavior: the link field tells the VDP which sprite to process next. Sprite 0's link points to sprite 1, sprite 1's link to sprite 2, etc. The pre-initialized link chain from `Init_SpriteTable` (in buffers.asm) already sets up 0→1→2→...→79→0. Our renderer overwrites the entries it uses, so the link chain is implicitly correct as long as we write entries sequentially starting from index 0. We just need to terminate the chain at the last sprite we write.

Fix: After writing all pieces for all objects, find the last SAT entry written and set its link byte to 0. Already handled by `clr.b -5(a4)` in the code above.

But wait — the link byte in each entry should point to the next sprite index, and we're writing sequentially. If we write sprite 0, its link should be 1. Sprite 1's link should be 2. Etc. The `move.b d5, -1(a4)` line writes the CURRENT d5 as the link, but at that point d5 hasn't been incremented yet. So sprite 0 gets link=0, sprite 1 gets link=1... that's wrong. Fix: increment d5 BEFORE writing the link, or write d5+1.

Corrected approach:
```asm
        addq.w  #1, d5                  ; advance to next index FIRST
        move.b  d5, -1(a4)              ; link = next sprite index
```

Then after the loop, the last sprite's link needs to be 0:
```asm
        subq.b  #1, -5(a4)             ; wrong — just set to 0
        clr.b   -5(a4)                  ; link = 0 (end chain)
```

Wait, that's also wrong because we incremented d5 past the last used index. Let me reconsider.

The clean approach:
```asm
; Before piece loop, d5 = current sprite index (starts at 0)
; Write SAT entry at index d5:
;   link = d5 + 1 (next sprite)
; After writing, increment d5

        move.b  d5, d6                  ; save current index
        addq.b  #1, d6                  ; d6 = next sprite index
        move.b  d6, LINK_OFFSET(a4)     ; write link = next
        ; ... write rest of entry ...
        addq.w  #1, d5                  ; advance sprite index
```

The implementer should handle this carefully. The key is: each sprite's link byte points to the index of the NEXT sprite in the chain, and the last sprite's link is 0.

- [ ] **Step 4: Add include to `main.asm`**

After `include "engine/objects.asm"`:

```asm
    include "engine/sprites.asm"
```

- [ ] **Step 5: Build and fix any assembly errors**

Run: `./build.sh`
Expected: Build succeeds after resolving any register conflicts or forward reference issues.

- [ ] **Step 6: Commit**

```bash
git add engine/sprites.asm main.asm
git commit -m "feat(§3): add sprite rendering — Draw_Sprite priority bands + Render_Sprites SAT builder"
```

---

### Task 5: Test game state — spawn objects, display on screen

**Files:**
- Create: `test/object_test_state.asm`
- Create: `data/mappings/test_mappings.asm`
- Modify: `main.asm` (include test files, place ObjCodeBase)
- Modify: `engine/game_loop.asm` (add test game state)
- Modify: `constants.asm` (add test VRAM constants)

- [ ] **Step 1: Create test mapping data in `data/mappings/test_mappings.asm`**

Simple VDP-order mappings for a 16×16 test sprite (2×2 cells):

```asm
; Test sprite mappings — 16x16 colored square
; VDP-order: Y offset, size|link, tile attrs, X offset (8 bytes per piece)

Map_TestObj:
        dc.w Map_TestObj_F0 - Map_TestObj                ; frame 0
        dc.w Map_TestObj_F1 - Map_TestObj                ; frame 1

Map_TestObj_F0:
        dc.w 1                                            ; 1 piece
        dc.w -8                                           ; Y offset (centered)
        dc.b sprSize(2,2)>>8, 0                           ; 2x2 cells, link placeholder
        dc.w 0                                            ; tile 0 (relative to art_tile)
        dc.w -8                                           ; X offset (centered)

Map_TestObj_F1:
        dc.w 1                                            ; 1 piece
        dc.w -8
        dc.b sprSize(2,2)>>8, 0
        dc.w 4                                            ; tile 4 (different color)
        dc.w -8
```

- [ ] **Step 2: Create test art tiles**

Add inline test art data — 4 tiles (16×16 square) in two colors:

```asm
; Test art — two 16x16 colored squares (4 tiles each, 128 bytes each)
; These get DMA'd to VRAM at init time

TestArt:
; Square 1 — palette 0 color 1 (solid fill)
        rept 4
        dc.l $11111111, $11111111, $11111111, $11111111
        dc.l $11111111, $11111111, $11111111, $11111111
        endr
; Square 2 — palette 0 color 2
        rept 4
        dc.l $22222222, $22222222, $22222222, $22222222
        dc.l $22222222, $22222222, $22222222, $22222222
        endr
TestArt_End:
```

- [ ] **Step 3: Add VRAM constant for test art**

In `constants.asm`, add:
```asm
; Test object VRAM tile index (temporary — Phase 1 only)
VRAM_TEST_OBJ           = $0001         ; tile index 1 (after blank tile 0)
```

- [ ] **Step 4: Create test object code**

Create `objects/test_static.asm`:

```asm
; Test object — static display at fixed position
; Used for Phase 1 verification only

TestStatic:
        ; Object init (first call only — code_addr points here)
        move.l  #Map_TestObj, mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), art_tile(a0)
        move.b  #0, mapping_frame(a0)

        ; Change code_addr to main loop
        move.w  #objroutine(TestStatic_Main), (a0)

TestStatic_Main:
        bsr.w   Draw_Sprite
        rts
```

- [ ] **Step 5: Create test game state in `test/object_test_state.asm`**

```asm
; Object system test state
; Inits object RAM, loads test palette + art, spawns test objects, runs loop

GameState_ObjectTest_Init:
        ; Load sonic palette to palette line 0
        lea     TestPalette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #32/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w          ; mark all palette lines dirty

        ; DMA test art to VRAM
        move.l  #TestArt, d1                      ; source
        move.w  #vram_bytes(VRAM_TEST_OBJ), d2    ; VRAM dest
        move.w  #TestArt_End-TestArt, d3           ; length
        jsr     QueueDMA_Critical

        ; Init object system
        bsr.w   InitObjectRAM
        bsr.w   Init_SpriteTable

        ; Clear camera
        clr.l   (Camera_X).w
        clr.l   (Camera_Y).w

        ; Spawn test objects at various positions and priorities
        bsr.w   AllocDynamic
        bcs.s   .skip1
        move.w  #objroutine(TestStatic), (a1)
        move.l  #160<<16, x_pos(a1)               ; X = 160 (center)
        move.l  #112<<16, y_pos(a1)               ; Y = 112 (center)
        move.w  #4, priority(a1)                   ; mid priority
.skip1:

        bsr.w   AllocDynamic
        bcs.s   .skip2
        move.w  #objroutine(TestStatic), (a1)
        move.l  #80<<16, x_pos(a1)
        move.l  #80<<16, y_pos(a1)
        move.w  #2, priority(a1)
.skip2:

        bsr.w   AllocDynamic
        bcs.s   .skip3
        move.w  #objroutine(TestStatic), (a1)
        move.l  #240<<16, x_pos(a1)
        move.l  #144<<16, y_pos(a1)
        move.w  #6, priority(a1)
        move.b  #1, mapping_frame(a1)              ; different frame (color 2)
.skip3:

        ; Switch game state to the running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

; -----------------------------------------------
; GameState_ObjectTest — per-frame loop
; -----------------------------------------------
GameState_ObjectTest:
        bsr.w   InitSpriteSystem
        bsr.w   RunObjects
        bsr.w   Render_Sprites
        rts

; -----------------------------------------------
; Test palette — basic colors for visibility
; -----------------------------------------------
TestPalette:
        dc.w $0000              ; color 0: transparent (black)
        dc.w $000E              ; color 1: red
        dc.w $00E0              ; color 2: green
        dc.w $0E00              ; color 3: blue
        dc.w $0EEE              ; color 4: white
        dc.w $00EE              ; color 5: yellow
        dc.w $0E0E              ; color 6: cyan
        dc.w $0EE0              ; color 7: magenta
        dc.w $0444              ; color 8: dark gray
        dc.w $0888              ; color 9: gray
        dc.w $0CCC              ; color A: light gray
        dc.w $006E              ; color B: orange
        dc.w $060E              ; color C: purple
        dc.w $0060              ; color D: dark green
        dc.w $0006              ; color E: dark blue
        dc.w $0600              ; color F: dark red
```

- [ ] **Step 6: Place ObjCodeBase and wire includes in `main.asm`**

After all engine includes and before `NullInterrupt`, add:

```asm
; -----------------------------------------------
; Object code bank (§3)
; All object routines must live within this 64KB block.
; objroutine() computes offsets from ObjCodeBase.
; -----------------------------------------------
    align $10000
ObjCodeBase:
    rts                                 ; offset 0 = empty slot (rts is harmless safety net)

    include "objects/test_static.asm"

; -----------------------------------------------
; Data — mappings, art, test assets
; -----------------------------------------------
    include "data/mappings/test_mappings.asm"

; -----------------------------------------------
; Test game states
; -----------------------------------------------
    include "test/object_test_state.asm"
```

- [ ] **Step 7: Wire game state in `engine/game_loop.asm`**

Replace `GameState_Idle` or update boot sequence to start the object test:

In boot.asm or wherever Game_State is initially set, change:
```asm
move.l  #GameState_ObjectTest_Init, (Game_State).w
```

- [ ] **Step 8: Build and test**

Run: `./build.sh`
Expected: Build succeeds. ROM should display three colored squares at different screen positions. User loads ROM in Exodus emulator to verify.

Verify with Exodus MCP:
- Sprite table has 3 entries with correct positions
- Object RAM has 3 non-zero code_addr entries
- Priority bands have correct counts

- [ ] **Step 9: Commit**

```bash
git add objects/test_static.asm data/mappings/test_mappings.asm test/object_test_state.asm main.asm engine/game_loop.asm constants.asm
git commit -m "feat(§3): Phase 1 complete — objects allocate, dispatch, and render on screen"
```

---

## Phase 2: Animation System (Research → Build)

### Task 6: Animation system research

**Goal:** Investigate animation bytecode interpreters, speed scaling, and DPLC integration across all 7 references + online. Produce findings that inform AnimateSprite implementation.

**Files:**
- Create: `docs/research/animation-system.md` (research findings)

- [ ] **Step 1: Research all 7 references**

For each reference, investigate:

1. **Animation script format** — What bytecodes/data format? How are frames indexed? What control codes exist (loop, jump, delete, callback)?
2. **Frame duration mechanism** — Fixed per-animation? Per-frame? Speed-linked to velocity? Accumulator-based?
3. **DPLC integration** — How does a frame change trigger art loading? Is there a `prev_frame` comparison? Where does the DPLC call happen — in the animation routine or separately?
4. **Self-advancing pointer** (Alien Soldier) — Exactly how does `anim_cursor` walk through ROM? How are control codes (loop, branch) handled as pointer rewrites?
5. **Multi-sprite animation** — How does a parent animate its children? Does each child read the parent's frame, or does the parent directly set child frames?
6. **Speed scaling** — S.C.E.'s velocity-linked formula, sonic_hack's `($800-|inertia|)>>8`, any accumulator approaches?

**Specific files to examine per reference:**

| Reference | Files to check |
|-----------|---------------|
| S.C.E. | `Animation.asm`, `Animate_*` routines, look for `Animate_RawGetFaster` |
| Batman & Robin | Search for animation/bytecode interpreter, look for fractional accumulator |
| Vectorman | Search for animation/frame update, callback patterns |
| Gunstar Heroes | Timer at $4C, animation tables, search for `$4C` references |
| Alien Soldier | $48(a5) pointer, search for `move.l a0, $48` pattern, control code handling |
| Thunder Force IV | Frame counter at +$10, dual-use (animation + lifetime), animation tables |
| sonic_hack | `code/engines/animate.asm` or equivalent, `AnimateSprite` routine |

**Online:** Search plutiedev for sprite animation patterns, SGDK `SPR_setAnim`/`onFrameChange`, SpritesMind animation threads.

- [ ] **Step 2: Write findings document**

Save to `docs/research/animation-system.md`. Format: per-question analysis with source citations, then validated decisions for our implementation.

Key decisions to resolve:
- Self-advancing cursor vs frame index + timer: which do we implement? (Research leaned toward cursor — validate with detailed analysis)
- Speed scaling formula: which one?
- DPLC trigger: inside AnimateSprite or separate call?
- Control code set: which codes do we need for Phase 2 (basic) vs Phase 4 (events)?

- [ ] **Step 3: Commit research**

```bash
git add docs/research/animation-system.md
git commit -m "docs(§3): animation system research — 7 references + online"
```

---

### Task 7: AnimateSprite routine

**Files:**
- Create: `engine/animate.asm`
- Modify: `main.asm` (include it)

**Depends on:** Task 6 research findings. The exact implementation will be informed by the research. Below is the expected structure based on Phase 0 findings (self-advancing cursor).

- [ ] **Step 1: Implement AnimateSprite**

Create `engine/animate.asm` with:

```asm
; AnimateSprite — bytecode animation interpreter using self-advancing cursor
;
; Animation script format:
;   Byte 0: default frame duration (ticks)
;   Byte 1+: sequence of frame indices and control codes
;
; Control codes (negative bytes):
;   $FF = loop (restart from byte 1)
;   $FE = jump back N bytes (next byte = N)
;   $FD = branch to animation (next byte = animation ID)
;   $FC = increment object routine counter (custom field)
;   $FB = delete object
;
; In:  a0 = SST pointer
;      anim_table(a0) must be set (pointer to animation table in ROM)
;      anim(a0) = desired animation ID
; Out: mapping_frame updated if frame changed
; Clobbers: d0-d2, a1
```

The routine should:
1. Check if animation changed (`anim` vs a previous value — use a byte in custom data or compare cursor against table)
2. If new animation: look up `anim_table + anim*2` for script offset, set `anim_cursor` to script start + 1 (skip duration byte), read duration into a timer
3. If same animation: decrement timer. When timer reaches 0, advance cursor to next frame byte
4. Read byte at cursor: if positive, set `mapping_frame` to that value. If negative, handle control code
5. On frame change, trigger DPLC if needed (or set a flag for the caller to check)

- [ ] **Step 2: Add DPLC trigger on frame change**

When `mapping_frame` changes, call `Perform_DPLC` (from `engine/dplc.asm`) if the object has DPLC data. Use a flag or SST field to indicate whether this object uses DPLCs.

For Phase 2, the simplest approach: if `anim_table` is non-null AND the frame changed, call Perform_DPLC with the new frame index. The object's init code sets up the DPLC pointer in a custom data field.

- [ ] **Step 3: Include in `main.asm`**

After `include "engine/sprites.asm"`:
```asm
    include "engine/animate.asm"
```

- [ ] **Step 4: Build and verify**

Run: `./build.sh`

- [ ] **Step 5: Commit**

```bash
git add engine/animate.asm main.asm
git commit -m "feat(§3): add AnimateSprite — self-advancing cursor + basic control codes"
```

---

### Task 8: Animation test — Sonic walk cycle with DPLC

**Files:**
- Modify: `test/object_test_state.asm` (add animated test object)
- Create: `objects/test_animated.asm`
- Create: `data/animations/test_anims.asm` (animation scripts)

- [ ] **Step 1: Create animation script data**

Create walk cycle animation using Sonic's existing frame indices. The animation script references Sonic's mapping frames. Sonic's optimized art is in `art/optimized/characters/sonic.bin` and DPLC data in `data/dplc/optimized/sonic.bin`.

```asm
; Animation scripts for test objects
Ani_TestWalk:
        dc.w Ani_TestWalk_Walk - Ani_TestWalk
Ani_TestWalk_Walk:
        dc.b 8                  ; frame duration: 8 ticks
        dc.b 0, 1, 2, 3, 4, 5  ; walk frames (Sonic walk cycle indices)
        dc.b $FF                ; loop
        even
```

Note: The exact frame indices depend on Sonic's mapping data. The implementer should check `mappings/sprite/Sonic.asm` in sonic_hack for the walk cycle frame numbers.

- [ ] **Step 2: Create animated test object**

`objects/test_animated.asm`:
- Init: set mappings to Sonic's mappings, set anim_table, set DPLC pointer, set art_tile
- Main: call AnimateSprite, call Draw_Sprite
- On frame change (detected by AnimateSprite), trigger DPLC → DMA

- [ ] **Step 3: Update test game state to spawn animated object**

Modify `GameState_ObjectTest_Init` to allocate an animated test object alongside the static ones. Load Sonic's art via DPLC for the initial frame.

- [ ] **Step 4: Build and test in emulator**

Run: `./build.sh`
Expected: Sonic's walk animation plays on screen. Art updates correctly via DPLC → DMA. Frame timing matches the duration byte.

Verify with Exodus MCP:
- VRAM shows Sonic art tiles updating each frame change
- DMA queue shows Important-priority entries for DPLC transfers
- Animation loops smoothly

- [ ] **Step 5: Commit**

```bash
git add objects/test_animated.asm data/animations/test_anims.asm test/object_test_state.asm
git commit -m "feat(§3): Phase 2 complete — animated Sonic walk cycle with DPLC art streaming"
```

---

## Phase 3: Collision + Stub Terrain + Controller Input (Research → Build)

### Task 9: Collision system research

**Goal:** Research collision detection, response patterns, solid object interactions, and controller input across all 7 references.

**Files:**
- Create: `docs/research/collision-system.md`

- [ ] **Step 1: Research all 7 references**

For each reference, investigate:

1. **Collision detection algorithm** — AABB? Pixel-perfect? How is the overlap test done? What's the cost per pair?
2. **Collision iteration pattern** — Does one object (player) check against all others? Or all-pairs? Registration list? Spatial bucketing?
3. **Collision response dispatch** — How does the engine decide what happens on contact? Type byte? Callback? Jump table?
4. **Solid object interactions** — How is "which side was contacted?" determined? Push-out distance? Standing detection? How does the player ride moving platforms?
5. **Sprite overflow handling** — How do references handle >20 sprites per scanline? Round-robin? Priority culling? Link cycling? (Relevant to Phase 7 but research now)
6. **Controller reading** — 3-button vs 6-button protocol. Press/hold/release detection. Existing `engine/controllers.asm` handles 3-button; research 6-button if needed.

**Specific files to examine:**

| Reference | Files to check |
|-----------|---------------|
| S.C.E. | `Touch_Response.asm`, `Touch_SolidObject.asm`, collision type handling |
| Batman & Robin | Collision system, spatial bucket implementation |
| Vectorman | Collision detection, bbox system |
| Gunstar Heroes | $40/$42 attacker/target pointers, hit communication |
| Alien Soldier | Two-pass collision, hit detection |
| Thunder Force IV | Simple collision (projectile pool), priority cycling |
| sonic_hack | `code/objects/Object_Specific_Routines/object_touch_response.asm`, SolidObject routines |

**Online:** plutiedev collision patterns, SGDK collision API, SpritesMind collision threads.

- [ ] **Step 2: Write findings and commit**

Save to `docs/research/collision-system.md`.

Key decisions: AABB math formula, iteration pattern (player-vs-all or all-pairs), solid side detection algorithm, controller protocol (3 vs 6 button).

```bash
git add docs/research/collision-system.md
git commit -m "docs(§3): collision system research — 7 references + online"
```

---

### Task 10: TouchResponse + collision handlers

**Files:**
- Create: `engine/collision.asm`
- Modify: `main.asm`

- [ ] **Step 1: Implement TouchResponse**

```asm
; TouchResponse — check player(s) against all collidable objects
;
; Iterates dynamic + effect slots. For each with collision_resp != 0,
; performs AABB overlap test against each player. On overlap, dispatches
; to per-type handler.
;
; In:  none (reads Object_RAM directly)
; Out: none
; Clobbers: d0-d6, a0-a3
```

Algorithm:
1. For each player slot (a2 = player SST):
2. For each dynamic/effect slot (a3 = target SST):
3. If target `collision_resp` == 0, skip
4. AABB overlap test using `width_pixels`/`height_pixels`
5. If overlap: read `collision_resp`, use as index into handler jump table
6. Call handler with a2 = player, a3 = target

AABB test (doubled-delta, full dimensions):
```asm
; Combined width = (player.width + target.width) / 2 — but our widths are FULL
; So half each: overlap if |px - tx| < (pw + tw) / 2 AND |py - ty| < (ph + th) / 2
        move.w  x_pos(a2), d0          ; player X (integer)
        sub.w   x_pos(a3), d0          ; delta X
        bpl.s   .pos_x
        neg.w   d0
.pos_x:
        moveq   #0, d1
        move.b  width_pixels(a2), d1
        moveq   #0, d2
        move.b  width_pixels(a3), d2
        add.w   d2, d1
        lsr.w   #1, d1                 ; combined half-width
        cmp.w   d1, d0
        bge.s   .no_overlap            ; |dx| >= combined half-width

        ; Y axis
        move.w  y_pos(a2), d0
        sub.w   y_pos(a3), d0
        bpl.s   .pos_y
        neg.w   d0
.pos_y:
        moveq   #0, d1
        move.b  height_pixels(a2), d1
        moveq   #0, d2
        move.b  height_pixels(a3), d2
        add.w   d2, d1
        lsr.w   #1, d1                 ; combined half-height
        cmp.w   d1, d0
        bge.s   .no_overlap            ; |dy| >= combined half-height
        ; Overlap confirmed — dispatch to handler
```

- [ ] **Step 2: Implement core collision handlers (infrastructure only)**

Only implement handlers needed for Phase 3 testing. All other collision types get `rts` stubs in the jump table — they'll be built alongside the actual objects that use them (springs with the spring object, monitors with the monitor object, etc.).

Phase 3 handlers:
- `Touch_Solid` — AABB push-out with side detection (top/bottom/left/right). The foundation — needed for any platform gameplay.
- `Touch_Hurt` — player takes damage. Simplest damage response for testing enemy contact.

Stub entries (implemented later alongside their objects):
- `Touch_Enemy` → `rts` (implemented with badnik objects)
- `Touch_Boss` → `rts` (implemented with boss objects)
- `Touch_Monitor` → `rts` (implemented with monitor object)
- `Touch_Ring` → `rts` (implemented with ring system)
- `Touch_Bubble` → `rts` (implemented with bubble object)
- `Touch_Projectile` → `rts` (implemented with projectile objects)
- `Touch_SolidBreak` → `rts` (implemented with breakable terrain)
- `Touch_Spring` → `rts` (implemented with spring object)
- `Touch_SolidHurt` → `rts` (implemented with spike/hazard objects)
- `Touch_Generic` → `rts` (implemented as needed)

Each handler is a subroutine called with a2 = player, a3 = target.

- [ ] **Step 3: Implement side detection for solids**

Determine which side the player contacted the solid object. Compare overlap distances on each axis to find the minimum penetration. Push player out along that axis.

```asm
; Side detection: compare X and Y overlap to find contact face
; If X overlap < Y overlap → side contact (left/right)
; If Y overlap < X overlap → top/bottom contact
; If top contact AND player moving down → player stands on object
```

- [ ] **Step 4: Include in `main.asm` and build**

```bash
git add engine/collision.asm main.asm
git commit -m "feat(§3): add TouchResponse + Touch_Solid/Hurt, stub table for remaining types"
```

---

### Task 11: Stub terrain + gravity + controller input

**Files:**
- Create: `objects/test_player.asm`
- Modify: `test/object_test_state.asm`

- [ ] **Step 1: Create controllable test player**

`objects/test_player.asm`:
- Reads `Ctrl_1_Held` / `Ctrl_1_Press` for movement
- Left/right sets x_vel based on held direction
- Button press (B/C) sets negative y_vel (jump) if on ground
- Gravity: add to y_vel each frame
- Stub floor: if y_pos > FLOOR_Y, clamp and set on-ground flag
- Calls AnimateSprite (walk cycle when moving, idle when still)
- Calls Draw_Sprite

```asm
; Floor Y position for stub terrain (replaced by real collision in §4)
STUB_FLOOR_Y            = 192
GRAVITY                 = $38           ; gravity acceleration per frame
JUMP_VELOCITY           = -$680         ; initial jump velocity
WALK_SPEED              = $200          ; horizontal speed
```

- [ ] **Step 2: Create test enemy and solid block objects**

`objects/test_enemy.asm`:
- Simple patrol: walk left/right, reverse at boundaries
- collision_resp = COLLISION_HURT (uses the core handler — Touch_Enemy is stubbed until badniks exist)
- On death: delete (no explosion yet — particles come in Phase 4)

`objects/test_solid.asm`:
- Static position, no movement
- collision_resp = COLLISION_SOLID
- width_pixels/height_pixels set to block dimensions

- [ ] **Step 3: Update test game state**

Modify `GameState_ObjectTest_Init` to spawn: 1 player, 2 enemies, 3 solid blocks. Set up positions for a testable scene.

Wire collision: call `TouchResponse` from `GameState_ObjectTest` between `RunObjects` and `Render_Sprites`.

- [ ] **Step 4: Build and test**

Expected: Player walks, jumps, lands on stub floor and solid blocks. Enemies hurt player on contact. Player can stand on solid blocks. Collision response works correctly.

- [ ] **Step 5: Commit**

```bash
git add objects/test_player.asm objects/test_enemy.asm objects/test_solid.asm test/object_test_state.asm
git commit -m "feat(§3): Phase 3 complete — controllable player, collision, stub terrain"
```

---

## Phase 4: Child Creation + Object Loading + Particles + Animation Events (Research → Build)

### Task 12: Child creation and particle system research

**Files:**
- Create: `docs/research/children-particles.md`

- [ ] **Step 1: Research all 7 references**

Focus areas:
1. **Child creation patterns** — Descriptor tables (S.C.E.'s 12 strategies), inheritance (art, mappings, position), linked vs unlinked children
2. **Parent-child lifecycle** — Cleanup chains, orphan detection, what happens when parent dies mid-frame
3. **Particle/effect systems** — Thunder Force IV projectile pool, ring scatter (sonic_hack), explosion patterns, debris
4. **Animation events** — SGDK onFrameChange, any engine that triggers behavior from animation frames
5. **Object loading / init patterns** — Format bytes, data blocks, bulk field initialization

- [ ] **Step 2: Write findings and commit**

```bash
git add docs/research/children-particles.md
git commit -m "docs(§3): child creation + particle system research"
```

---

### Task 13: Data-driven child creation

**Files:**
- Create: `engine/children.asm`
- Modify: `main.asm`

- [ ] **Step 1: Implement CreateChild_Normal**

```asm
; CreateChild_Normal — spawn a child from a descriptor table entry
; In:  a0 = parent SST, a1 = descriptor table pointer
;      Descriptor: dc.w objroutine(ChildCode), dc.b x_off, y_off
; Out: a1 = child SST (or carry set if pool full)
; Sets child's parent_ptr, inherits mappings + art_tile from parent
```

1. Call AllocDynamic (or AllocEffect based on a parameter)
2. Set child's code_addr from descriptor
3. Set child's x_pos = parent.x_pos + x_offset, same for y_pos
4. Copy parent's mappings and art_tile to child
5. Set child's parent_ptr = parent address
6. Set parent's sibling_ptr = child address (or chain if multiple children)

- [ ] **Step 2: Implement CreateChild_Complex**

Same as Normal but also sets: animation, velocity, callback pointer from the descriptor.

- [ ] **Step 3: Implement CreateChild_Linked and CreateChild_FlipAware**

From §3.3 spec — two additional strategies:

`CreateChild_Linked` — spawns a chain of children (snake segments, train cars). Descriptor includes a repeat count; each child's `sibling_ptr` links to the next. Used for multi-segment objects.

`CreateChild_FlipAware` — same as Complex but negates X offsets and X velocity when parent's `render_flags` has RF_XFLIP set. Used for directional boss weapons that mirror when the boss faces left.

Both use the same AllocDynamic + parent_ptr/sibling_ptr wiring as Normal/Complex.

- [ ] **Step 4: Implement cleanup chain**

`DeleteChildren` — walk sibling_ptr chain from parent, delete each child, free slots.

Called when parent dies (before DeleteObject on parent).

- [ ] **Step 5: Build and commit**

```bash
git add engine/children.asm main.asm
git commit -m "feat(§3): add data-driven child creation + cleanup chains"
```

---

### Task 14: Basic object loading (Load_Object)

**Files:**
- Create: `engine/load_object.asm`
- Modify: `main.asm`

- [ ] **Step 1: Implement Load_Object**

```asm
; Load_Object — initialize an SST from a data block
; In:  a0 = SST pointer (already allocated)
;      a1 = object data block pointer
;
; Data block format:
;   dc.w objroutine(ObjectCode)     ; code_addr
;   dc.l MappingPointer             ; mappings
;   dc.w vram_art(tile,pal,pri)     ; art_tile
;   dc.b collision_type             ; collision_resp
;   dc.b subtype                    ; subtype
;   dc.b width, height              ; collision dimensions
;   dc.w priority                   ; sprite priority band
```

Reads fields from the data block and writes them to the SST. Fields not present in the block retain their zeroed state (from slot clear).

- [ ] **Step 2: Build and commit**

```bash
git add engine/load_object.asm main.asm
git commit -m "feat(§3): add Load_Object — data-block-driven SST initialization"
```

---

### Task 15: Animation events ($F9-$F4)

**Files:**
- Modify: `engine/animate.asm`

- [ ] **Step 1: Extend AnimateSprite with event code handling**

Add handlers for negative bytes in the animation script that are event codes:

```asm
; Event codes (interleaved in animation data):
;   $F9 = play sound     (next byte: sound ID)
;   $F8 = call routine   (next long: routine pointer)
;   $F7 = set collision   (next byte: collision_resp value)
;   $F6 = set field       (next 2 bytes: SST offset, value)
;   $F5 = speed-linked    (frame duration = max(1, top_speed - |vel|))
```

When the cursor reads a byte in the $F4-$F9 range:
1. Execute the event (play sound, modify SST field, etc.)
2. Advance cursor past the event's parameters
3. Continue reading the next byte (could be another event or a frame index)

- [ ] **Step 2: Build and commit**

```bash
git add engine/animate.asm
git commit -m "feat(§3): add animation event codes (\$F9-\$F4) to AnimateSprite"
```

---

### Task 16: Particle/effect pool test

**Files:**
- Create: `objects/test_particle.asm`
- Create: `objects/test_parent.asm`
- Modify: `test/object_test_state.asm`

- [ ] **Step 1: Create particle emitter test object**

`objects/test_particle.asm`:
- Emitter object spawns particles via AllocEffect at a configurable rate
- Each particle: random velocity, gravity, fixed lifespan (countdown timer in custom data)
- Particle deletes itself when timer expires
- Uses simple 8×8 dot mapping

- [ ] **Step 2: Create multi-part parent test object**

`objects/test_parent.asm`:
- Uses CreateChild_Normal to spawn 2-3 children at init
- Children orbit or follow parent
- Parent death → children auto-delete via cleanup chain
- Test: player kills parent (collision), verify children die too

- [ ] **Step 3: Update test scene**

Add particle emitter and multi-part object to the test scene. Verify 20+ simultaneous particles, correct parent-child lifecycle.

- [ ] **Step 4: Build and test**

```bash
git add objects/test_particle.asm objects/test_parent.asm test/object_test_state.asm
git commit -m "feat(§3): Phase 4 complete — child creation, particles, animation events"
```

---

## Phase 5: Combined Sandbox

### Task 17: Full integration test scene

**Files:**
- Modify: `test/object_test_state.asm`

- [ ] **Step 1: Build combined test scene**

Modify `GameState_ObjectTest_Init` to create a comprehensive test scene:

- **Player** (Sonic sprites, animated, controllable, DPLC art streaming)
- **3 enemies** (patrol AI, hurtable, death explosions via particle emitter)
- **5 solid blocks** (various positions, player stands on them)
- **1 multi-part boss-like object** (parent + 2 children, animation events change collision)
- **1 particle emitter** (continuous shower)

Scene layout: arrange objects to create a mini platforming playground. Player starts on the left, enemies and platforms create a navigable space.

- [ ] **Step 2: Verify all systems interact correctly**

Test checklist:
- Player moves, jumps, lands on floor and solid blocks
- Player kills enemies by jumping on them (spin) — if Touch_Enemy is implemented by Phase 5
- Enemy contact hurts player (when not spinning)
- Boss parent death cascades to children
- Particles render without corruption
- Animation events fire correctly (collision changes, sounds)
- No crashes, stuck states, or visual corruption
- Frame runs within CPU budget (no lag frames under normal load)

- [ ] **Step 3: Commit**

```bash
git add test/object_test_state.asm
git commit -m "feat(§3): Phase 5 complete — combined sandbox, all systems integrated"
```

---

## Phase 6: Stress Test + Baseline Benchmark

### Task 18: Stress test and metrics capture

**Files:**
- Create: `test/stress_test_state.asm`
- Modify: `main.asm` (include it)
- Create: `docs/benchmarks/phase6-baseline.md`

- [ ] **Step 1: Create stress test game state**

`test/stress_test_state.asm`:

- **Slot saturation** — fill all 40 dynamic slots with animated, colliding objects
- **Collision pressure** — cluster objects so every pair triggers overlap check
- **Rapid alloc/free** — projectile stream: spawn every frame, delete after 30 frames
- **Particle flood** — fill all 16 effect slots
- **Combined worst case** — all of the above simultaneously

Each scenario runs for a fixed number of frames (e.g., 300 = 5 seconds at 60fps).

- [ ] **Step 2: Add profiling instrumentation**

Use Exodus MCP or `ifdef __DEBUG__` instrumentation to capture:
- Total RunObjects scanlines (read VDP HV counter before/after)
- TouchResponse scanlines
- Render_Sprites scanlines
- DMA queue utilization (slots used per frame)
- Frame timing (lag frame count)
- Peak slot usage

- [ ] **Step 3: Run benchmarks and document**

Save results to `docs/benchmarks/phase6-baseline.md`. This is the "before" snapshot for Phase 7 comparison.

- [ ] **Step 4: Commit**

```bash
git add test/stress_test_state.asm docs/benchmarks/phase6-baseline.md main.asm
git commit -m "perf(§3): Phase 6 complete — stress test baseline benchmark"
```

---

## Phase 7: Advanced Sprite Rendering (Research → Build + Benchmark)

**Scope note:** §3.5 specifies several advanced sprite features. Task 19 research evaluates ALL of them: link-order cycling, scanline-aware budgeting, sprite X=0 masking, sprite multiplexing, sprite LOD, and BuildSprites_Compound. Tasks 20-21 implement the two most impactful (link cycling + scanline budgeting). If research shows X=0 masking or multiplexing are high-value, add implementation tasks. Features not implemented here should be added to DEFERRED_WORK.md during Task 23.

### Task 19: Advanced sprite rendering research

**Files:**
- Create: `docs/research/sprite-rendering-advanced.md`

- [ ] **Step 1: Research all 7 references**

Focus areas:
1. **Link-order cycling** — Which games rotate the sprite link chain start? How? Measured improvement?
2. **Sprite LOD** — Simplified mappings for distant objects? Reduced piece count?
3. **Scanline-aware budgeting** — Per-scanline sprite pixel counters? Proactive culling vs VDP dropout?
4. **Sprite multiplexing** — HBlank SAT rewrites for virtual sprites? Cost per rewrite? Which games use it?
5. **Sprite X=0 masking** — Per-scanline clipping. Which games use it? (Galaxy Force II, Alien Soldier)
6. **Pre-formatted SAT entries** — Thunder Force IV's approach of storing VDP-ready data in the SST

- [ ] **Step 2: Write findings and commit**

```bash
git add docs/research/sprite-rendering-advanced.md
git commit -m "docs(§3): advanced sprite rendering research"
```

---

### Task 20: Link-order cycling

**Files:**
- Modify: `engine/sprites.asm`

- [ ] **Step 1: Implement link chain rotation**

Add a frame counter that rotates the starting link index:

```asm
; Each frame, advance the starting sprite index by 1 (mod active_count)
; This distributes VDP scanline overflow as flicker instead of permanent dropout
Sprite_Cycle_Offset:    ; RAM variable (add to ram.asm)

; In Render_Sprites, start writing SAT entries at Sprite_Cycle_Offset
; instead of always starting at index 0
```

The rotation ensures that if scanline X has >20 sprites, different sprites are dropped each frame, creating flicker rather than permanent disappearance.

- [ ] **Step 2: Build and commit**

---

### Task 21: Scanline-aware sprite budgeting

**Files:**
- Modify: `engine/sprites.asm`

- [ ] **Step 1: Add per-scanline pixel counter**

During Render_Sprites, maintain a counter of sprite pixels per scanline. When a scanline's budget is exhausted (>20 sprites covering it), skip or deprioritize remaining sprites for that scanline.

This is the most complex sprite optimization. Implementation details depend on Phase 7 research findings.

- [ ] **Step 2: Build and commit**

---

### Task 22: Benchmark comparison

**Files:**
- Modify: `docs/benchmarks/phase6-baseline.md` (add Phase 7 results)

- [ ] **Step 1: Re-run Phase 6 stress tests**

Run the exact same stress test scenarios from Task 18 with Phase 7 optimizations enabled.

- [ ] **Step 2: Compare before/after metrics**

Document:
- Render_Sprites CPU time (before vs after)
- Visual quality under overflow (flicker vs permanent dropout)
- Any regressions under normal load

- [ ] **Step 3: Commit**

```bash
git add docs/benchmarks/phase6-baseline.md engine/sprites.asm
git commit -m "perf(§3): Phase 7 complete — link cycling + scanline budgeting, benchmark comparison"
```

---

## Post-Implementation: ENGINE_ARCHITECTURE.md Sync

### Task 23: Final architecture sync

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Update §3 to reflect implemented reality**

Walk through every §3 subsection in ENGINE_ARCHITECTURE.md and verify it matches the actual implementation. Update any designs that changed during implementation. Add implementation notes where the research informed a different approach than originally planned.

Specific known fixes:
- §3.1: Rename `collision_response` → `collision_resp` (matches code)
- §3.8: Fix stale `child_ptr ($22)` → `parent_ptr ($22)` and `sibling_ptr ($24)`
- §3.10: Fix stale `child_ptr` references → `sibling_ptr`
- §3.5: Add any advanced sprite features NOT implemented (move to DEFERRED_WORK.md)

- [ ] **Step 2: Review DEFERRED_WORK.md**

Check if any deferred items are now unblocked by §3 completion:
- Generic Perform_DPLC SST integration (§2.1/§3.9) → NOW UNBLOCKED
- Dynamic VRAM Allocator (§2.2) → NOW UNBLOCKED
- Refcount Art Caching (§2.2) → NOW UNBLOCKED
- Sprite Rendering Pipeline (§1.2) → NOW COMPLETE (was part of §3)
- DPLC Lookahead (§1.6) → NOW UNBLOCKED

Update DEFERRED_WORK.md accordingly.

- [ ] **Step 3: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§3): sync ENGINE_ARCHITECTURE.md and DEFERRED_WORK.md with implementation"
```

---

## Appendix: Conventions for Object Code

**Object routine contract:**
- Receives `a0` = SST pointer (self)
- MUST preserve `a0` and `d7`
- All other registers (`d0-d6`, `a1-a6`) are freely clobberable
- Called from RunObjects via `jsr (a1)` where a1 is reconstructed from `objroutine` offset

**State machine pattern:**
```asm
MyObject:
    ; Init state — runs once, sets up fields
    move.l  #Map_MyObj, mappings(a0)
    move.w  #vram_art(VRAM_MyObj,0,0), art_tile(a0)
    ; ... set other fields ...
    move.w  #objroutine(MyObject_Main), (a0)    ; transition to main loop
MyObject_Main:
    bsr.w   ObjectMove
    bsr.w   AnimateSprite
    bsr.w   Draw_Sprite
    rts
```

**Deletion pattern:**
```asm
    bsr.w   DeleteObject    ; pushes slot to free stack, zeros SST, restores a0
    rts                     ; return to RunObjects — slot is now empty
```

**Child spawn pattern:**
```asm
    lea     MyChildDescriptor(pc), a1
    bsr.w   CreateChild_Normal
    bcs.s   .no_child       ; pool full
    ; a1 = child SST, ready for additional setup
.no_child:
```
