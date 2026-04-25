# Child Creation, Particles, Animation Events, Object Loading — Research

## 1. Child Creation Patterns

### S.C.E.'s 12 CreateChild Strategies

S.C.E. implements twelve distinct child creation routines. Key ones:

**CreateChild1_Normal** — Single child with positional offsets. Inherits parent's mappings/art_tile. Data: `dc.l code_addr, dc.b x_off, y_off` (6 bytes per child). Use: shield objects, basic projectiles.

**CreateChild2_Complex** — Full init: code_addr, setup data, animations, wait callback, offsets, velocity. 30 bytes per child. Use: boss parts with independent AI.

**CreateChild3_NormalRepeated** — Same object spawned N times with different offsets. Saves template pointer in a3. Use: ring scatter, particle bursts.

**CreateChild4_LinkListRepeated** — Linked list chain. Previous→next via parent4, current→previous via parent3. Use: beam attacks, multi-segment bosses.

**CreateChild5_ComplexAdjusted** — Complex + mirrors x_offset and x_vel when parent is flipped. Use: asymmetrical boss parts.

**CreateChild6_Simple** — All children at parent position, minimal overhead. Use: burst effects, invincibility stars.

**CreateChild10_NormalAdjusted** — Normal + mirrors offset for parent x-flip, also sets child's x_flip. Use: directional weapons.

Remaining variants (7, 8, 9, 11, 12) combine the above with unrestricted allocation or tree-style linking.

### sonic_hack Format (Simpler)

```
Create_Child_Object:
  dc.w  child_routine_id    ; 2 bytes
  dc.w  x_offset_signed     ; 2 bytes
  dc.w  y_offset_signed     ; 2 bytes
                            ; 6 bytes per child
```

Uses word-sized offsets (vs S.C.E.'s byte offsets). More range, less compact.

### Treasure Games (Gunstar Heroes / Alien Soldier)

- 96-byte SST (Gunstar), with link fields at $58 (primary) and $5C (secondary, Alien Soldier only)
- Bidirectional linking enables full tree navigation
- Alien Soldier has 380+ link field references — child/parent tracking is core architecture
- No formal "CreateChild" API; parent writes directly to allocated child slots

### Descriptor Table Format Comparison

| Engine | Per-child size | Offsets | Velocity | Extra |
|--------|---------------|---------|----------|-------|
| S.C.E. Normal | 6 bytes | signed byte | no | — |
| S.C.E. Complex | 30 bytes | signed byte | long x,y | setup/anim/wait |
| sonic_hack | 6 bytes | signed word | no | — |
| Treasure | inline | full word | inline | custom per-object |

**Recommendation:** Start with S.C.E.-style byte offsets (6 bytes per child). Add Complex variant (with velocity) for boss parts. Use word offsets only if children need >128px distance.

## 2. Parent-Child Lifecycle

### Linking Fields

**S.C.E.:**
- `parent3` ($4C, word) — parent RAM address
- `parent4` ($4A, word) — sibling link (next in chain)
- `child_dx/dy` ($48-$49) — offset from parent
- `subtype` — sequential child index (0, 1, 2...)

**sonic_hack:**
- `obj_parent` (word) — parent address
- `obj_child_index` (byte) — sequential index

**Our SST already has:** parent_ptr ($26), sibling_ptr ($28). These map directly.

### Deletion Patterns

**S.C.E.:** Sets "delete children" flag, transitions to Delete_Current_Object which walks the child chain one more frame before clearing slots.

**sonic_hack:** Free slot stack — DeleteObject pushes slot address back onto stack, clears code_addr. O(1) deallocation.

**Pattern:** Parent doesn't delete children immediately. Sets a flag, runs one more frame, then walks child chain and deletes each. This avoids dangling pointers from mid-frame deletion.

### Orphan Detection

No game explicitly detects orphaned children. Instead:
- Parents ALWAYS delete their children explicitly
- Children check `parent_ptr` each frame — if parent's code_addr is 0, self-delete
- S.C.E. uses a "defeated" status bit that children can check

## 3. Particle & Effect Systems

### Ring Scatter (S2/sonic_hack canonical pattern)

1. Cap at 32 rings (prevent pool exhaustion)
2. Angle accumulator starts at $288, increments $10 per ring
3. Sine/cosine lookup for radial velocity distribution
4. All rings spawn at player position, velocity spreads them
5. Each ring gets gravity ($18/frame), bounce on floor contact
6. Shared animation counter for all scattered rings (saves per-ring overhead)

```
for each ring:
  allocate from free stack
  set position = player position
  set x_vel = cos(angle) << scale
  set y_vel = sin(angle) << scale
  angle += $10
  set collision = CT_RING (can be recollected)
```

### Explosion + Animal Spawning

Multiple child types spawned sequentially:
1. Animal object (inherits position, gets parent backlink)
2. Points text (mapping_frame encodes point value: 100/200/500)
3. Explosion sprite (short animation, self-deletes via $FC event)

Each allocation check fails silently if pool is full — graceful degradation.

### Projectile Pools (Thunder Force IV / Shoot-em-ups)

- Type-segregated pools: bullets separate from enemies separate from FX
- 32-byte object stride (half of Sonic's 64) — more objects in same RAM
- Bullet fast-path: no AI dispatch, just `add velocity → check bounds → draw`
- Priority flicker rotation ensures all objects visible (4-frame cycle)

**For our engine:** Not needed unless boss fights spawn 20+ simultaneous projectiles. Our Effect_Slots pool (16 slots) handles typical Sonic-scale effects. Can add dedicated projectile pool later if needed.

## 4. Animation Events

### Standard Sonic Event Codes (S.C.E./S2)

| Code | Name | Action |
|------|------|--------|
| $00-$7F | Frame | Display mapping frame |
| $FC | Routine++ | Increment routine counter by 2 (state machine advance) |
| $FD | Chain | Switch to animation ID (next byte) |
| $FE | Jump back | Rewind N frames (next byte = count) |
| $FF | Loop | Restart from frame 0 |

### No Explicit Event System Found

None of the 7 references have animation-triggered events (play sound, set collision, etc.). Instead:
- **Sound cues:** Object routine checks `mapping_frame` and plays sound at specific frames
- **Hitbox windows:** Routine checks `anim_frame` and enables collision during attack frames
- **State transitions:** $FC code increments routine counter → next behavior state

### Design for s4_engine

Our plan adds event codes $F4-$F9:
- $F9 = play sound (next byte: sound ID)
- $F8 = call routine (next long: routine pointer)
- $F7 = set collision (next byte: collision_resp value)
- $F6 = set field (next 2 bytes: SST offset, value)
- $F5 = speed-linked duration

This goes beyond what any reference game does but is a clean extension of the existing negative-byte event system. The animation cursor skips past event parameters and continues reading — events are inline, not interrupting.

## 5. Object Initialization & Loading

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

### Data Table Format

```
MyObject__Data:
  dc.w  objroutine(MyRoutine)
  dc.l  MyMappings
  dc.w  vram_art(VRAM_MyArt, 0, 0)
  dc.b  render_flags_byte
  dc.b  collision_type
  dc.w  priority
  dc.b  width, height
  dc.b  mapping_frame
  even
```

**Key principle:** Define object properties as ROM data tables, not inline code. One Load_Object routine serves all object types.

### Flip-Aware Loading

sonic_hack's BadnikWeaponLoad applies transformations after bulk copy:
```asm
  btst #0, render_flags(a0)     ; parent flipped?
  beq.w +
  neg.w x_vel(a1)               ; mirror velocity
```

Post-copy transforms handle orientation without duplicating data tables.

## 6. Recommendations for s4_engine

### Child Creation (4 strategies)

1. **CreateChild_Simple** — N copies at parent position (ring scatter, bursts)
2. **CreateChild_Normal** — Different objects with byte offsets (multi-part objects)
3. **CreateChild_Complex** — Full init with velocity/animation (boss parts)
4. **CreateChild_Linked** — Sibling chain with bidirectional links (segments)

All use existing parent_ptr/sibling_ptr SST fields. No SST expansion needed.

### Object Loading

Single `Load_Object` routine with data block format matching our SST layout. Objects define their properties in ROM tables, not code.

### Particle/Effects

Use Effect_Slots pool (16 slots) for explosions, ring scatter, debris. Cap spawns per event (e.g., max 16 rings). Fail silently on pool exhaustion.

### Animation Events

Extend existing AF_ codes with $F4-$F9 event range. Keep it simple — routine counter increment ($FC) is the primary state machine mechanism.
