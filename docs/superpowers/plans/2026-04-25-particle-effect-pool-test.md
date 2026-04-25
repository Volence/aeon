# Particle & Effect Pool Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `CreateEffect_*` routines that allocate from the effect pool (mirroring `CreateChild_*`), build a test particle object with auto-despawn, a test emitter that spawns particles periodically, and a test multi-part parent that verifies parent-death-kills-children lifecycle.

**Architecture:** Effect creation routines mirror the existing `CreateChild_Normal`/`CreateChild_Simple` API but call `AllocEffect` instead of `AllocDynamic`. A test particle object moves with velocity and auto-despawns via `AF_DELETE` when its animation ends. A test emitter spawns particles on a timer using `CreateEffect_Normal`. A test multi-part parent uses `CreateChild_Normal` to spawn children, then self-destructs after a timer to verify `DeleteChildren` cascade.

**Tech Stack:** 68000 assembly, AS Macro Assembler, existing s4_engine object/animation/DPLC systems.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `engine/objects/children.asm` | Add `CreateEffect_Normal` and `CreateEffect_Simple` (effect-pool variants of child creation) |
| `objects/test_particle.asm` | Test particle — moves with velocity, plays short animation, auto-despawns via `AF_DELETE` |
| `objects/test_emitter.asm` | Test emitter — spawns particles periodically using `CreateEffect_Normal` |
| `objects/test_parent.asm` | Test multi-part parent — spawns children, self-destructs after timer, verifies cascade delete |
| `data/animations/particle_anims.asm` | Animation script for particles: 3-frame flash → `AF_DELETE` |
| `data/mappings/test_mappings.asm` | Add particle mapping frame (frame 2 — 8x8 single tile for small particle) |
| `test/object_test_state.asm` | Add emitter and parent to test scene spawn list |
| `main.asm` | Include new object files and animation data |

### Existing files (modify)

| File | Changes |
|------|---------|
| `engine/objects/children.asm` | Add `CreateEffect_Normal`, `CreateEffect_Simple` |
| `data/mappings/test_mappings.asm` | Add frame 2 (8x8 particle) |
| `test/object_test_state.asm` | Add emitter + parent to `TestObjectList` |
| `main.asm` | Include `objects/test_particle.asm`, `objects/test_emitter.asm`, `objects/test_parent.asm`, `data/animations/particle_anims.asm` |

### New files (create)

| File | Purpose |
|------|---------|
| `objects/test_particle.asm` | Particle object code |
| `objects/test_emitter.asm` | Emitter object code |
| `objects/test_parent.asm` | Multi-part parent object code |
| `data/animations/particle_anims.asm` | Particle animation scripts |

---

## Conventions Reference

All code must follow `CODING_CONVENTIONS.md`. Key rules for this plan:
- `.s`/`.w`/`.l` on every branch and jump
- `function` for compile-time math, never runtime
- PascalCase for routines, ALL_CAPS for constants, `.lowercase` for locals
- `_lowercase_underscored` for SST custom field overlays (with `ifndef` guards when shared)
- Tail calls: `jsr X / rts` → `jmp X`
- No `clr` on RAM — use `moveq #0,dn` + `move`
- Routine headers with In/Out/Clobbers on every public routine

---

## Task 1: Particle animation data + mapping frame

**Files:**
- Modify: `data/mappings/test_mappings.asm`
- Create: `data/animations/particle_anims.asm`

The particle needs a small visual (8x8 single tile) and a short animation that ends with `AF_DELETE` for auto-despawn.

- [ ] **Step 1: Add frame 2 to `Map_TestObj`**

In `data/mappings/test_mappings.asm`, add a third frame offset to the table header and a new frame definition for a small 8x8 particle (1x1 cell, single tile):

```asm
; Test sprite mappings — 16x16 colored square + 8x8 particle
; VDP-order format: Y offset, size|pad, tile attrs, X offset (8 bytes per piece)
; Mapping table: word offsets from table start

Map_TestObj:
        dc.w    Map_TestObj_F0 - Map_TestObj    ; frame 0
        dc.w    Map_TestObj_F1 - Map_TestObj    ; frame 1
        dc.w    Map_TestObj_F2 - Map_TestObj    ; frame 2 — 8x8 particle

Map_TestObj_F0:
        dc.w    1                               ; 1 piece
        dc.w    -8                              ; Y offset (centered)
        dc.b    sprSize(2,2)>>8, 0              ; 2x2 cells (16x16), link placeholder
        dc.w    0                               ; tile 0 (relative to art_tile)
        dc.w    -8                              ; X offset (centered)

Map_TestObj_F1:
        dc.w    1                               ; 1 piece
        dc.w    -8
        dc.b    sprSize(2,2)>>8, 0
        dc.w    4                               ; tile 4 (second color)
        dc.w    -8

Map_TestObj_F2:
        dc.w    1                               ; 1 piece
        dc.w    -4                              ; Y offset (centered 8x8)
        dc.b    sprSize(1,1)>>8, 0              ; 1x1 cell (8x8), link placeholder
        dc.w    0                               ; tile 0 (color index 1)
        dc.w    -4                              ; X offset (centered 8x8)
```

- [ ] **Step 2: Create particle animation scripts**

Create `data/animations/particle_anims.asm`:

```asm
; Particle animation scripts — short flash → auto-despawn

Ani_Particle:
        dc.w Ani_Particle_Flash-Ani_Particle    ; anim 0: flash then die

Ani_Particle_Flash:
        dc.b 4                                  ; duration: 4 frames per frame
        dc.b 2, 2, 2                            ; frame 2 (8x8 particle) × 3 cycles
        dc.b AF_DELETE                          ; auto-despawn
        align 2
```

- [ ] **Step 3: Build test**

Run: `./build.sh`
Expected: Build succeeds. Animation data and mapping frame included but not yet referenced by any object.

- [ ] **Step 4: Commit**

```bash
git add data/mappings/test_mappings.asm data/animations/particle_anims.asm
git commit -m "feat: add particle mapping frame + flash animation with AF_DELETE"
```

---

## Task 2: CreateEffect_Normal + CreateEffect_Simple

**Files:**
- Modify: `engine/objects/children.asm`

These routines mirror `CreateChild_Normal` and a new simple variant, but call `AllocEffect` instead of `AllocDynamic`. `CreateEffect_Normal` uses the same 4-byte descriptor format (code_addr, x_off, y_off). `CreateEffect_Simple` spawns N copies of the same effect at the parent's position (ring scatter, burst patterns).

- [ ] **Step 1: Add `CreateEffect_Normal` to `engine/objects/children.asm`**

Append after `DeleteChildren` at the end of the file:

```asm
; -----------------------------------------------
; CreateEffect_Normal — spawn effect children from a descriptor table
; Allocates from Effect pool (not Dynamic). Children are NOT linked
; into the parent's sibling chain — effects are fire-and-forget.
;
; Descriptor format (4 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(EffectCode)   ; child code_addr (0 = end)
;   dc.b x_offset_signed          ; signed byte, relative to parent X
;   dc.b y_offset_signed          ; signed byte, relative to parent Y
;
; In:  a0 = parent SST pointer
;      a1 = descriptor table pointer (ROM)
; Out: none (effects allocated, or silently skipped if pool full)
; Clobbers: d0-d2, a1-a2
; -----------------------------------------------
CreateEffect_Normal:
.effect_loop:
        move.w  (a1)+, d2               ; d2 = effect code_addr
        beq.s   .done                   ; 0 = end of table

        movem.l a0-a1, -(sp)
        jsr     AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST
        movem.l (sp)+, a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position = parent + signed byte offset (16.16)
        move.b  (a1)+, d0               ; x_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0               ; y_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Inherit mappings, art_tile from parent
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Set parent_ptr so effect can reference parent if needed
        move.w  a0, SST_parent_ptr(a2)

        bra.s   .effect_loop

.alloc_fail:
        movem.l (sp)+, a0-a1
        addq.w  #2, a1                  ; skip x_off, y_off of failed entry
.skip_rest:
        tst.w   (a1)                    ; check next entry
        beq.s   .done
        addq.w  #4, a1                  ; skip full 4-byte entry
        bra.s   .skip_rest
.done:
        rts

; -----------------------------------------------
; CreateEffect_Simple — spawn N copies of the same effect at parent position
; Allocates from Effect pool. Fire-and-forget (no sibling chain).
;
; In:  a0 = parent SST pointer
;      d0.w = effect code_addr (objroutine value)
;      d1.w = number of copies to spawn
; Out: none (silently stops if pool exhausted)
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateEffect_Simple:
        subq.w  #1, d1                  ; adjust for dbf
        bmi.s   .done
        move.w  d0, d2                  ; d2 = code_addr (preserved)
        move.w  d1, d3                  ; d3 = counter (preserved)

.spawn_loop:
        movem.l d2-d3/a0, -(sp)
        jsr     AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST
        movem.l (sp)+, d2-d3/a0

        move.w  d2, SST_code_addr(a2)

        ; Position = parent position
        move.l  SST_x_pos(a0), SST_x_pos(a2)
        move.l  SST_y_pos(a0), SST_y_pos(a2)

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        move.w  a0, SST_parent_ptr(a2)

        dbf     d3, .spawn_loop
.done:
        rts

.alloc_fail:
        movem.l (sp)+, d2-d3/a0
        rts
```

- [ ] **Step 2: Build test**

Run: `./build.sh`
Expected: Build succeeds. New routines assembled but not yet called.

- [ ] **Step 3: Commit**

```bash
git add engine/objects/children.asm
git commit -m "feat: add CreateEffect_Normal + CreateEffect_Simple — effect pool allocation"
```

---

## Task 3: Test particle object

**Files:**
- Create: `objects/test_particle.asm`
- Modify: `main.asm` (add include)

A minimal effect object: sets its own upward velocity on init, applies gravity each frame, plays the flash animation, and auto-despawns via `AF_DELETE`. Uses the test art already in VRAM.

- [ ] **Step 1: Create `objects/test_particle.asm`**

```asm
; Test particle — short-lived effect with velocity + gravity + auto-despawn
; Allocated from effect pool by emitters via CreateEffect_Normal/Simple.
; Sets its own velocity on init — emitter only controls spawn position.

PARTICLE_GRAVITY        = $20           ; lighter than player gravity ($38)
PARTICLE_X_VEL          = -$100         ; initial horizontal velocity (leftward)
PARTICLE_Y_VEL          = -$300         ; initial vertical velocity (upward)

; -----------------------------------------------
; TestParticle — init routine (called as first-frame code_addr)
; In:  a0 = SST pointer (position, mappings, art_tile set by CreateEffect)
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestParticle:
        move.l  #Ani_Particle, SST_anim_table(a0)
        moveq   #0, d0
        move.b  d0, SST_anim(a0)                ; anim 0: flash
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        move.w  #6, SST_priority(a0)            ; high priority (in front)
        move.b  #8, SST_width_pixels(a0)
        move.b  #8, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0) ; screen coords (no camera)
        move.w  #PARTICLE_X_VEL, SST_x_vel(a0)
        move.w  #PARTICLE_Y_VEL, SST_y_vel(a0)
        move.w  #objroutine(TestParticle_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestParticle_Main — per-frame update
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestParticle_Main:
        ; Apply gravity
        move.w  SST_y_vel(a0), d0
        addi.w  #PARTICLE_GRAVITY, d0
        move.w  d0, SST_y_vel(a0)

        ; Move
        jsr     ObjectMove

        ; Animate (AF_DELETE handles despawn)
        jsr     AnimateSprite

        ; Draw
        jmp     Draw_Sprite
```

- [ ] **Step 2: Add include to `main.asm`**

After the `include "objects/test_solid.asm"` line, add:

```asm
    include "objects/test_particle.asm"
```

Also, after `include "data/animations/sonic_anims.asm"`, add:

```asm
    include "data/animations/particle_anims.asm"
```

- [ ] **Step 3: Build test**

Run: `./build.sh`
Expected: Build succeeds. Particle object assembled but not yet spawned by anything.

- [ ] **Step 4: Commit**

```bash
git add objects/test_particle.asm main.asm
git commit -m "feat: add TestParticle — effect object with gravity + AF_DELETE auto-despawn"
```

---

## Task 4: Test emitter object

**Files:**
- Create: `objects/test_emitter.asm`
- Modify: `main.asm` (add include)
- Modify: `test/object_test_state.asm` (add to spawn list)

A stationary object that spawns a particle every N frames using `CreateEffect_Normal`. Demonstrates the effect pool lifecycle: allocate → run → auto-despawn → slot returns to pool → reuse.

- [ ] **Step 1: Create `objects/test_emitter.asm`**

```asm
; Test emitter — spawns particles at a fixed interval
; Placed in the test scene to demonstrate effect pool lifecycle.

_emitter_timer          = SST_sst_custom        ; word — countdown to next spawn
EMITTER_INTERVAL        = 30                    ; frames between spawns

; -----------------------------------------------
; TestEmitter_Init — set up emitter (called as first-frame code_addr)
; In:  a0 = SST pointer (position set by spawn list)
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestEmitter:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #1, SST_mapping_frame(a0)       ; frame 1 (color 2 square)
        move.w  #5, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #EMITTER_INTERVAL, _emitter_timer(a0)
        move.w  #objroutine(TestEmitter_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestEmitter_Main — per-frame: countdown, spawn particle, draw self
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestEmitter_Main:
        subq.w  #1, _emitter_timer(a0)
        bne.s   .draw

        ; Timer expired — spawn particle (particle sets its own velocity)
        move.w  #EMITTER_INTERVAL, _emitter_timer(a0)
        lea     .ParticleDesc(pc), a1
        jsr     CreateEffect_Normal

.draw:
        jmp     Draw_Sprite

; Descriptor: one particle at emitter position (0,0 offset)
.ParticleDesc:
        dc.w    objroutine(TestParticle)
        dc.b    0, 0                            ; x_off, y_off = centered
        dc.w    0                               ; terminator
```

- [ ] **Step 2: Add include to `main.asm`**

After `include "objects/test_particle.asm"`, add:

```asm
    include "objects/test_emitter.asm"
```

- [ ] **Step 3: Add emitter to test scene spawn list**

In `test/object_test_state.asm`, spawn the emitter manually in `GameState_ObjectTest_Init` (no ObjDef needed for a test object). Add after `jsr Load_ObjectList`:

```asm
        ; --- Spawn test emitter (effect pool demo) ---
        jsr     AllocDynamic
        bne.s   .no_emitter
        move.w  #objroutine(TestEmitter), SST_code_addr(a1)
        move.l  #60<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
.no_emitter:
```

`AllocDynamic` returns the slot in `a1`, so write fields to `a1` directly.

- [ ] **Step 4: Build and test in emulator**

Run: `./build.sh`
Expected: Build succeeds. Load ROM in Exodus. The emitter (color-2 square at 60,80) should appear and spawn small particles that rise upward-left with gravity pulling them down, then vanish after the flash animation completes (~12 frames).

Verify:
- Particles appear at the emitter's position every 30 frames
- Particles move upward-left and curve downward (gravity)
- Particles auto-despawn (disappear) after 3 animation cycles
- No crash or visual glitch over 10+ seconds of running

- [ ] **Step 5: Commit**

```bash
git add objects/test_emitter.asm main.asm test/object_test_state.asm
git commit -m "feat: add TestEmitter — spawns particles from effect pool on timer"
```

---

## Task 5: Test multi-part parent object

**Files:**
- Create: `objects/test_parent.asm`
- Modify: `main.asm` (add include)
- Modify: `test/object_test_state.asm` (spawn parent)

A parent object that spawns 3 children via `CreateChild_Normal` on init, then self-destructs after a timer. When the parent calls `DeleteChildren` + `DeleteObject`, all children should vanish simultaneously. This verifies the parent-child lifecycle.

Children use `TestChildPart` as their code_addr — a tiny init routine defined in this file that sets width_pixels/height_pixels/priority (needed for Draw_Sprite on-screen culling), then transitions to a draw-only loop.

- [ ] **Step 1: Create `objects/test_parent.asm`**

```asm
; Test parent — multi-part object that spawns children, then self-destructs
; Demonstrates CreateChild_Normal lifecycle + DeleteChildren cascade.

_parent_life_timer      = SST_sst_custom        ; word — countdown to self-destruct

PARENT_LIFETIME         = 180                   ; frames before self-destruct (3 seconds)

; -----------------------------------------------
; TestChildPart — child init (sets display fields, transitions to draw-only)
; In:  a0 = SST pointer (position, mappings, art_tile set by CreateChild_Normal)
; Out: none
; Clobbers: none
; -----------------------------------------------
TestChildPart:
        move.w  #3, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #objroutine(TestChildPart_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestChildPart_Main — display-only
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
TestChildPart_Main:
        jmp     Draw_Sprite

; -----------------------------------------------
; TestParent — init routine
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        moveq   #0, d0
        move.b  d0, SST_mapping_frame(a0)       ; frame 0 (color 1 square)
        move.w  #3, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #PARENT_LIFETIME, _parent_life_timer(a0)

        ; Spawn 3 children around parent
        lea     .ChildDesc(pc), a1
        jsr     CreateChild_Normal

        move.w  #objroutine(TestParent_Main), SST_code_addr(a0)

        ; Fall through to main for first frame

; -----------------------------------------------
; TestParent_Main — per-frame: countdown, then self-destruct with children
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent_Main:
        subq.w  #1, _parent_life_timer(a0)
        bne.s   .draw

        ; Timer expired — kill children then self
        jsr     DeleteChildren
        jmp     DeleteObject

.draw:
        jmp     Draw_Sprite

; Child descriptor: 3 children at offsets around parent
.ChildDesc:
        dc.w    objroutine(TestChildPart)
        dc.b    -24, 0                          ; left of parent
        dc.w    objroutine(TestChildPart)
        dc.b    24, 0                           ; right of parent
        dc.w    objroutine(TestChildPart)
        dc.b    0, -24                          ; above parent
        dc.w    0                               ; terminator
```

- [ ] **Step 2: Add include to `main.asm`**

After `include "objects/test_emitter.asm"`, add:

```asm
    include "objects/test_parent.asm"
```

- [ ] **Step 3: Add parent to test scene**

In `test/object_test_state.asm`, after the emitter spawn block (added in Task 4), add:

```asm
        ; --- Spawn test parent (child lifecycle demo) ---
        jsr     AllocDynamic
        bne.s   .no_parent
        move.w  #objroutine(TestParent), SST_code_addr(a1)
        move.l  #260<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
.no_parent:
```

- [ ] **Step 4: Build and test in emulator**

Run: `./build.sh`
Expected: Build succeeds. Load ROM in Exodus.

Verify:
- Parent (color-1 square at 260,80) appears with 3 children (same color, offset left/right/above)
- After ~3 seconds (180 frames), ALL FOUR objects (parent + 3 children) vanish simultaneously
- After they vanish, the slots are freed — emitter's particles continue working (effect pool not corrupted)
- After a few more seconds, parent + children should NOT reappear (they're gone, not respawning)

Wait — the parent is a one-shot demo. To make it continuously testable, let's make the parent respawn itself after deletion. Actually, that overcomplicates things. The 3-second lifecycle is enough to verify the cascade. If the user wants to see it again they reload the ROM.

- [ ] **Step 5: Commit**

```bash
git add objects/test_parent.asm main.asm test/object_test_state.asm
git commit -m "feat: add TestParent — multi-part object with DeleteChildren lifecycle demo"
```

---

## Task 6: Verify effect pool recycling

**Files:**
- No new code — emulator verification only

This task verifies that the effect pool actually recycles slots. The emitter spawns 1 particle every 30 frames. Each particle lives ~12 frames (3 animation cycles × 4 frames). So at steady state, only ~1 particle is alive at a time. Over 60 seconds (3600 frames), the emitter will have spawned 120 particles — far exceeding the 16-slot effect pool. If recycling works, this runs forever without exhaustion.

- [ ] **Step 1: Run ROM for 60+ seconds**

Load ROM in Exodus. Let it run for at least 60 seconds.

Verify:
- Particles keep spawning the entire time (no point where emitter stops producing)
- No visual corruption or missing sprites
- The emitter square stays visible

- [ ] **Step 2: Inspect effect pool via Exodus MCP**

Use Exodus MCP `emulator_read_memory` to check Effect_Free_SP. At steady state with only ~1 effect alive, the free stack pointer should be close to its initial value (most slots free).

Check: `Effect_Free_SP` address (from `ram.asm` — find the absolute address via symbols).

- [ ] **Step 3: Verify parent cleanup**

After the parent + children vanish (~3 seconds in):
- Use Exodus MCP `emulator_object_list` to confirm those slots are empty (code_addr = 0)
- Verify the Dynamic_Free_SP moved back (slots returned to dynamic pool)

- [ ] **Step 4: Commit** (no code changes — just a verification task)

No commit needed. If issues are found, fix them and commit the fix.

---

## Task 7: Update ENGINE_ARCHITECTURE.md

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`

Document the `CreateEffect_Normal` and `CreateEffect_Simple` routines in the object system section, alongside the existing `CreateChild_*` documentation.

- [ ] **Step 1: Find the child creation section in ENGINE_ARCHITECTURE.md**

Search for the section that documents `CreateChild_Normal` / child creation patterns.

- [ ] **Step 2: Add effect creation documentation**

Add a subsection describing the effect creation API:

```markdown
#### Effect Creation (Effect Pool)

`CreateEffect_Normal` and `CreateEffect_Simple` mirror the child creation API but allocate from the 16-slot effect pool instead of the dynamic pool. Effects are fire-and-forget — they are NOT linked into the parent's sibling chain and will NOT be cascade-deleted when the parent dies.

**CreateEffect_Normal** — descriptor-driven, same 4-byte format as `CreateChild_Normal`:
- In: a0 = parent SST, a1 = descriptor table (ROM)
- Inherits mappings + art_tile from parent
- Sets parent_ptr but does NOT chain siblings

**CreateEffect_Simple** — spawn N copies of the same effect at parent position:
- In: a0 = parent SST, d0.w = effect code_addr, d1.w = count
- All copies at parent's exact position (caller sets velocity after)

Effects typically auto-despawn via `AF_DELETE` animation event when their animation ends. No manual timer management needed — the animation system drives lifetime.
```

- [ ] **Step 3: Build test**

Run: `./build.sh`
Expected: Build succeeds (doc changes don't affect build, but confirms no accidental edits).

- [ ] **Step 4: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs: add CreateEffect_Normal/Simple to ENGINE_ARCHITECTURE.md"
```
