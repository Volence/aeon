# Child Creation, Particles, Animation Events, Object Loading — Research

**Sources:** S.C.E., sonic_hack, Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, SGDK, LUMINARY, nesdev, plutiedev, Amiga demoscene

---

## 1. Child Creation Patterns

### S.C.E. — 12 CreateChild Strategies (Most Comprehensive)

S.C.E. implements twelve distinct child creation routines, each for a different parent-child relationship:

**CreateChild1_Normal** — Single child with positional offsets. Inherits parent's mappings/art_tile. Data: `dc.l code_addr, dc.b x_off, y_off` (6 bytes per child). Use: shield objects, basic projectiles.

**CreateChild2_Complex** — Full init: code_addr, setup data, animations, wait callback, offsets, velocity. 30 bytes per child. Use: boss parts with independent AI.

**CreateChild3_NormalRepeated** — Same object spawned N times with different offsets. Saves template pointer in a3. Use: ring scatter, particle bursts.

**CreateChild4_LinkListRepeated** — Linked list chain. Previous→next via parent4, current→previous via parent3. Use: beam attacks, multi-segment bosses.

**CreateChild5_ComplexAdjusted** — Complex + mirrors x_offset and x_vel when parent is flipped. Use: asymmetrical boss parts.

**CreateChild6_Simple** — All children at parent position, minimal overhead. Use: burst effects, invincibility stars.

**CreateChild10_NormalAdjusted** — Normal + mirrors offset for parent x-flip, also sets child's x_flip. Use: directional weapons.

Remaining variants (7, 8, 9, 11, 12) combine the above with unrestricted allocation or tree-style linking.

**Linking fields:**
- `parent3` ($4C, word) — parent RAM address
- `parent4` ($4A, word) — sibling link (next in chain)
- `child_dx/dy` ($48-$49) — offset from parent
- `subtype` — sequential child index (0, 1, 2...)

**Deletion:** Sets "delete children" flag, transitions to Delete_Current_Object which walks the child chain one more frame before clearing slots. Avoids dangling pointers from mid-frame deletion.

### sonic_hack — Simpler Format

```
Create_Child_Object:
  dc.w  child_routine_id    ; 2 bytes
  dc.w  x_offset_signed     ; 2 bytes
  dc.w  y_offset_signed     ; 2 bytes
                            ; 6 bytes per child
```

Uses word-sized offsets (vs S.C.E.'s byte offsets). More range, less compact.

**Linking fields:** `obj_parent` (word) — parent address, `obj_child_index` (byte) — sequential index.

**Deletion:** Free slot stack — DeleteObject pushes slot address back onto stack, clears code_addr. O(1) deallocation.

### Batman & Robin — Doubly-Linked List + Cascade Delete

Object entry ~90 bytes. Doubly-linked active list with O(1) alloc/dealloc.

**Allocation (Object_Alloc at $8912):**
1. Decrement free counter at `$FFFFF4B0`
2. Pop slot from free list head at `$FFFFAD52`
3. Insert into doubly-linked active list at head `$FFFFDE94`
4. Update next/prev pointers at offsets $04/$06
5. Clear 22 longwords (88 bytes) of object data
6. Return pointer in a6

**Child pointer array** (offsets $08-$16): Parent stores up to 8 child pointers as consecutive words. NO parent pointer in children — relationships are one-way (parent→children only).

**Cascade delete ($8A5C):** When parent is deallocated:
1. Unlink parent from active list
2. Iterate child pointers at $8, $A, $C, $E, $10, $12, $14, $16
3. Chain each non-NULL child into free list
4. Bulk-update free counter: `add.b d1, $f4b0.w`

Children don't call destructors — just returned to free pool. Fast but no child cleanup logic.

**Effect system:** Separate 16-opcode bytecode interpreter ($03DCBE) with its own command stream. Effects use sine table rotation transforms ($0373A6, 512-entry table at $059B22) for spiral/ring patterns. Sprite Ring Rotator ($0373D0) positions N sprites in a rotating circle. Double rotation ($037926) creates Lissajous/spiral curves for boss attacks.

### Vectorman — No Parent-Child System

12-byte dispatch entries in a flat table at $BBD8:
```
+$00  word  Type/Flags ($FFFF = terminator)
+$02  word  Parameter (shifted << 4)
+$04  long  Update routine pointer
+$08  long  Render routine pointer
```

**No parent-child pointers.** Objects are fully independent. Player data lives in separate 1500-byte dedicated RAM blocks ($AF68, $B5A0), not in the dispatch table.

**Pool management:** Terminator-based — write active entries sequentially, $FFFF marks the end. Max 54 entries ($36). Compaction-based slot reuse (no free list).

**Separate update/render routines** per object — render pointer at +$08 called through trampoline at $8EB4, null render pointer skips rendering.

**DMA queue:** 54-entry queue with double-buffering and 2880-byte ($B40) per-frame budget. Graceful overflow: failed entries revert to backup pointers without corruption. Complete VDP commands pre-built during main loop.

### Gunstar Heroes — Single Link Field

96-byte ($60) SST per object.

**Single link field at $58** (long/4 bytes):
- 52 writes + 19 reads across codebase
- Stores either object address pointer OR code callback pointer (context-determined)
- Boss parts use $58 to reference other parts for relative positioning:
```asm
movea.w $58(a0), a0       ; follow link to parent
move.w  $10(a0), d0       ; read parent's X position
```

**No explicit spawn routine.** Multi-part bosses initialized via link field coordination. Data-driven init from ROM tables sets animation ($48) and data ($4C) pointers.

**Pool:** Static pre-allocation. Objects iterate with `lea $60(a5), a5` stride. No dynamic free-list observed.

### Alien Soldier — Dual Link Fields (Evolution from Gunstar)

96-byte ($60) SST — identical struct to Gunstar Heroes.

**Two link fields** (Treasure's refinement):
- **$58**: Primary link — 380 references (vs Gunstar's 52+19)
- **$5C**: Secondary link — 104 references (new in Alien Soldier)

Enables complex boss hierarchies:
```
Body ($58→Head, $5C→LeftArm)
  ├─ Head ($58→Body)
  ├─ LeftArm ($58→Body, $5C→RightArm)
  └─ RightArm ($58→Body)
```

**Spawn routine at $042C9A:** `jsr $2ab22.l` allocates child, sets velocity from parent, applies position offsets via byte reads.

**Pool:** Linear scan for free slots. `moveq #$ff, d7` loop counters suggesting 255-entry pools. Active flag checked via `tst.w`.

**Deletion:** Death via `jsr $2aa2a.l`. Children linked via $58/$5C cleaned up from parent destruction code.

### Thunder Force IV — Type-Segregated Pools

32-byte ($20) SST — confirmed by 437 instances of `lsl.w #5`.

**Separate pools by object type:**

| Pool | Address | Purpose |
|------|---------|---------|
| Main entities | $FFFF8198 | Player, weapons, FX |
| Bullet pool 1 | $FFFF9000 | Enemy bullets (32 slots) |
| Bullet pool 2 | $FFFF9400 | Enemy bullets (32 slots) |
| Enemy pool 1 | $FFFFD000 | Enemy objects (32 slots) |
| Enemy pool 2 | $FFFFD400 | Enemy objects (32 slots) |

**Bullet fast-path** — tight inner loop with no AI dispatch:
```asm
tst.w      (a0)         ; active?
beq.b      .next
move.w     $1E(a0), d0  ; velocity
add.w      d0, $10(a0)  ; integrate position
; bounds check, sprite write
.next:
adda.w     #$20, a0     ; stride = 32
dbra       d7, .loop
```

No collision response, animation state, or AI in bullet loop. Enemy processing runs separately with full AI.

**No link fields.** Type segregation replaces parent-child linking.

**Pool allocation:** Linear scan, first-fit. `moveq #$1f, d7` (31) loop counters for 32-slot pools.

**Sprite overflow: Round-robin flicker.** Counter at $F29A rotates which sprites get priority each frame. 80+ objects in bullet-hell scenes, only 80 VDP sprite slots. All objects remain visible across 4-frame windows — none permanently hidden.

### Online / Modern — Novel Patterns

**SGDK stack-based pool with swap-on-release:**
- Allocate: `--pool->free; return *pool->free;` — O(1)
- Release: `*pool->free = object; pool->free++;` — O(1)
- `maintainCoherency=true`: swaps released object with last allocated, keeping allocated region dense/contiguous
- Dense iteration via `POOL_getFirst()` — no null checks needed, just `dbra` over contiguous array

**LUMINARY ECS on 68000:**
- Full entity-component system with type descriptors (vtable-equivalent), component slot descriptors, coordinated multi-actor animation
- `EVisualEffect`: one-shot animation entity that auto-despawns when animation completes — `btst #ECSPRITE_STATE_FLAG_PLAYING` → `bsr ENT_DespawnEntity`
- Prefab spawning: `PrefabData` with `Prefab_ChildCount` + `Prefab_SpawnTable`, loops through spawn table with `dbra`, spawns children with position offsets relative to parent
- Entity allocation: `EntityManager_LastFreeBlock` caches last freed block for O(1) next alloc, falls back to linear scan

**nesdev union free-list pattern:**
- Same field serves double duty: when slot empty, stores pointer to next free slot; when occupied, stores gameplay data
- Zero overhead bookkeeping — the free chain lives inside the dead objects' memory

**SGDK frame-change callbacks:**
- `void (*onFrameChange)(struct Sprite* sprite)` — function pointer invoked on animation frame transitions
- `AnimationFrame` struct includes per-frame `Collision*` data for automatic hitbox changes

**Multiple traversal lists (nesdev):**
- Same object slots threaded through independent linked lists using different chain pointers
- `NextToExecute` for logic order, `NextToRender` for depth order
- Costs 2 bytes per entity per list, enables decoupled update/render ordering

## 2. Descriptor Table Format Comparison

| Engine | Per-child size | Offsets | Velocity | Link style | Extra |
|--------|---------------|---------|----------|------------|-------|
| S.C.E. Normal | 6 bytes | signed byte | no | parent3/parent4 words | — |
| S.C.E. Complex | 30 bytes | signed byte | long x,y | parent3/parent4 words | setup/anim/wait |
| sonic_hack | 6 bytes | signed word | no | parent word | — |
| Batman & Robin | inline | full word | inline | child array at $08-$16 | one-way parent→child |
| Gunstar Heroes | inline | full word | inline | single $58 link | context-determined |
| Alien Soldier | inline | full word | inline | dual $58/$5C links | bidirectional trees |
| Thunder Force IV | N/A | N/A | N/A | none (pool segregation) | — |
| Vectorman | N/A | N/A | N/A | none (flat table) | — |
| LUMINARY | spawn table | word offsets | per-component | entity list + component lists | prefab system |

## 3. Deletion Patterns

| Engine | Strategy | Complexity | Notes |
|--------|----------|------------|-------|
| S.C.E. | Walk child chain, delete each, one-frame delay | O(children) | Deferred to avoid dangling pointers |
| sonic_hack | Push slot to free stack | O(1) | Children check parent's code_addr each frame |
| Batman & Robin | Array scan + bulk free list push | O(children), max 8 | Cascade — no child destructors |
| Gunstar Heroes | Clear slot flags | O(1) per object | No explicit child cleanup observed |
| Alien Soldier | Death routine + link cleanup | O(links) | Children found via $58/$5C |
| Thunder Force IV | Clear active flag | O(1) | Pool segregation means no parent-child to clean up |
| LUMINARY | Unlink + destructor chain + component free | O(components) | Most structured cleanup |

**Orphan detection:** No game explicitly detects orphans. Instead:
- Parents ALWAYS delete children explicitly (S.C.E., Batman & Robin)
- Children check `parent_ptr` each frame — if parent's code_addr is 0, self-delete (sonic_hack)
- S.C.E. uses a "defeated" status bit that children can check

## 4. Particle & Effect Systems

### Ring Scatter (S2/sonic_hack canonical pattern)

1. Cap at 32 rings (prevent pool exhaustion)
2. Angle accumulator starts at $288, increments $10 per ring
3. Sine/cosine lookup for radial velocity distribution
4. All rings spawn at player position, velocity spreads them
5. Each ring gets gravity ($18/frame), bounce on floor contact
6. Shared animation counter for all scattered rings

### Batman & Robin — Bytecode Effect Scripting

Separate 16-opcode bytecode interpreter at $03DCBE:
- 0: Reset, 1: Start, 2: Continue, 3: Push return (4-deep call stack at $F4FC), 4: Pop return
- 5: Set repeat count, 6: Decrement and loop, 7: Computed jump
- 8-F: Load palette sets A-H

Effects use transform routines:
- Single rotation ($0373A6): radius + angle → sine/cosine → 16.16 X/Y
- Sprite ring rotator ($0373D0): N sprites in rotating circle
- Double rotation ($037926): two simultaneous rotations for Lissajous curves
- All use 512-entry sine table at $059B22 (word-sized)

### Vectorman — DMA-Budget-Aware Effects

54-entry DMA queue with 2880-byte per-frame budget. Effects that exceed the budget get deferred (backup pointer revert). Pre-computed VDP commands during main loop — VBlank just plays them back.

### Thunder Force IV — Bullet Pool Fast-Path

Bullets in dedicated pools skip AI dispatch entirely. 32-byte stride enables tight `dbra` loop. Round-robin sprite flicker ensures all 80+ objects remain visible across 4-frame rotation.

### LUMINARY — VFX as Auto-Despawn Entities

`EVisualEffect`: regular entity with single sprite component, loop disabled. On update, checks `ECSPRITE_STATE_FLAG_PLAYING` — when animation completes, calls `ENT_DespawnEntity`. No manual timer management.

### SGDK — Brute-Force Particles

Each particle is a full sprite entity managed by the standard pool. 40 particles at 60fps confirmed viable. No specialized particle system needed.

### Projectile Pools (Thunder Force IV / Shoot-em-ups)

- Type-segregated pools: bullets separate from enemies separate from FX
- 32-byte object stride (half of Sonic's 64) — more objects in same RAM
- Bullet fast-path: no AI dispatch, just `add velocity → check bounds → draw`
- Priority flicker rotation ensures all objects visible (4-frame cycle)

**For our engine:** Not needed unless boss fights spawn 20+ simultaneous projectiles. Our Effect_Slots pool (16 slots) handles typical Sonic-scale effects. Can add dedicated projectile pool later if needed.

## 5. Animation Events

### Standard Sonic Event Codes (S.C.E./S2)

| Code | Name | Action |
|------|------|--------|
| $00-$7F | Frame | Display mapping frame |
| $FC | Routine++ | Increment routine counter by 2 (state machine advance) |
| $FD | Chain | Switch to animation ID (next byte) |
| $FE | Jump back | Rewind N frames (next byte = count) |
| $FF | Loop | Restart from frame 0 |

### Batman & Robin — Script-Driven State Machine

No animation event callbacks. State transitions driven by bytecode script interpreter — script pointer IS the state. Opcodes at $000800+ include:
- $082E: Visibility check (screen bounds)
- $54B0: Countdown timer — `if --$19(a6) > 0, skip`
- $54CA: Frame accumulator — `$1A += $1B`, branch on carry

### Gunstar/Alien Soldier — Counter-Based Animation

Animation pointer at $48 controls frame sequencing. Timer/counter fields at $50, $56 drive timing. Sound effects triggered from animation event offsets (e.g., `subq.b #$1, $4b(a5)` in Alien Soldier at $42C5C).

### Thunder Force IV — RLE Animation Data

Animation frame data compressed with RLE:
- High bit: copy mode selection
- Bits 5-6: run type (1-byte, 2-byte, variable)
- Bits 0-4: count

Reduces DMA bandwidth for multi-frame sprites.

### SGDK — Frame-Change Callbacks

`void (*onFrameChange)(struct Sprite* sprite)` — invoked during sprite update when animation frame transitions. `AnimationFrame` struct includes per-frame `Collision*` for automatic hitbox changes per frame.

### No Animation Bytecode Systems Found in Homebrew

Despite extensive searching, no Genesis homebrew project documents an animation script bytecode system with embedded spawn/effect commands. The Sonic disassemblies use simple frame-list scripts. This is an area where our engine can innovate.

### Design for aeon

Our plan extends existing AF_ codes with $F4-$F9 event range:
- $F9 = play sound (next byte: sound ID)
- $F8 = call routine (next long: routine pointer)
- $F7 = set collision (next byte: collision_resp value)
- $F6 = set field (next 2 bytes: SST offset, value)
- $F5 = speed-linked duration

This goes beyond what any reference game does but is a clean extension of the existing negative-byte event system. The animation cursor skips past event parameters and continues reading — events are inline, not interrupting.

## 6. Object Initialization & Loading

### Data-Driven Load Routines (sonic_hack)

```asm
Load_Object2:           ; Standard object init from data table
  move.w  (a2)+, (a0)           ; code_addr
  move.l  (a2)+, mappings(a0)
  move.w  (a2)+, art_tile(a0)
  move.b  (a2)+, render_flags(a0)
  move.b  (a2)+, collision_response(a0)
  move.w  (a2)+, priority(a0)
  move.b  (a2)+, width_pixels(a0)
  move.b  (a2)+, height_pixels(a0)
  move.b  (a2)+, mapping_frame(a0)
  rts
```

Variants: Load_Object1 (adds velocity), Load_Object3 (minimal), Load_Object4 (broken monitors).

### Flip-Aware Loading (sonic_hack)

BadnikWeaponLoad applies post-copy transforms:
```asm
  btst #0, render_flags(a0)     ; parent flipped?
  beq.w +
  neg.w x_vel(a1)               ; mirror velocity
```

Post-copy transforms handle orientation without duplicating data tables.

### Batman & Robin — Template + Clear

Allocator clears 22 longwords (88 bytes), then copies init data template from ROM address stored in a0. Spawn routines set type ID at $58 and script pointer at $2A after allocation.

### Vectorman — Pointer-Based Init

Object entries in dispatch table store update/render routine pointers directly (as longs at +$04 and +$08). No intermediate lookup table — object type IS the routine pair.

### Gunstar/Alien Soldier — ROM Table-Driven

Animation pointers ($48) and data pointers ($4C) set from ROM tables. Dispatch index at $04 selects per-frame behavior routine. Data-driven but no single generic "Load_Object" routine.

### LUMINARY — Constructor Chain

Entity allocation → component allocation → component constructors → entity list insertion → entity constructor. Most structured init sequence found. Destructor runs in reverse order.

## 7. Recommendations for aeon

### Child Creation (4 strategies)

1. **CreateChild_Simple** — N copies at parent position (ring scatter, bursts). S.C.E.'s CreateChild6 pattern.
2. **CreateChild_Normal** — Different objects with byte offsets (multi-part objects). S.C.E.'s CreateChild1 pattern, 6 bytes per child.
3. **CreateChild_Complex** — Full init with velocity/animation (boss parts). S.C.E.'s CreateChild2 pattern.
4. **CreateChild_Linked** — Sibling chain with bidirectional links (segments). S.C.E.'s CreateChild4 pattern. Uses parent_ptr/sibling_ptr SST fields.

All use existing parent_ptr ($26) and sibling_ptr ($28) SST fields. No SST expansion needed.

### Deletion

S.C.E.'s pattern: walk child chain, delete each. One-frame deferred deletion to avoid dangling pointers. Children can also self-delete by checking parent's code_addr (sonic_hack pattern).

Batman & Robin's cascade-delete (bulk free list push) is faster but skips child cleanup. We should support both: fast cascade for simple effects, deferred walk for objects that need cleanup.

### Object Loading

Single `Load_Object` routine with data block format matching our SST layout. Objects define their properties in ROM tables, not code. Add flip-aware variant (sonic_hack's BadnikWeaponLoad pattern).

### Particle/Effects

Use Effect_Slots pool (16 slots) for explosions, ring scatter, debris. Cap spawns per event (e.g., max 16 rings). Fail silently on pool exhaustion.

VFX pattern from LUMINARY: one-shot objects that auto-despawn when animation completes. No manual timer needed — animation system drives lifetime.

### Animation Events

Extend existing AF_ codes with $F4-$F9 event range. Keep it simple — routine counter increment ($FC) is the primary state machine mechanism. SGDK's frame-change callback concept validates the approach.

### Patterns Deferred

- **SGDK swap-on-release pool**: Interesting for dense iteration but adds complexity. Our fixed-slot pools with `tst.w code_addr` checks are simpler and adequate for Sonic-scale object counts.
- **Type-segregated pools (TF4)**: Only needed if we have bullet-hell scenarios. Our 3-pool system (player/dynamic/effect) handles typical Sonic patterns.
- **Dual traversal lists (nesdev)**: Worth revisiting when sprite priority sorting becomes a concern.
- **Palette LRU cache**: Relevant for §2 VRAM management, not §3.
