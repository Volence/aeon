# §3 Object System — Phase 0 Foundational Research

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Research object system design across all 7 reference disassemblies and online sources, producing validated decisions for SST layout, dispatch mechanism, slot counts, particle pools, and novel design patterns — before writing any implementation code.

**Architecture:** Single research phase producing one findings document (`docs/research/object-system-foundations.md`) plus updates to `docs/ENGINE_ARCHITECTURE.md` §3 for any design changes. Each task surveys one reference or source category, extracting answers to all 11 research questions. The final task synthesizes findings into decisions.

**Tech Stack:** grep/search across 68000 assembly disassemblies, web research, document writing.

---

## File Structure

**New files to create:**

| File | Purpose |
|------|---------|
| `docs/research/object-system-foundations.md` | Research findings — all 7 references + online, validated decisions |

**Files to modify:**

| File | Changes |
|------|---------|
| `docs/ENGINE_ARCHITECTURE.md` | Update §3 if any research findings change the design |
| `docs/DEFERRED_WORK.md` | Update with any newly identified deferred items |

---

## Reference Paths

| Reference | Path | Key Files |
|-----------|------|-----------|
| S.C.E. | `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/` | `Engine/Objects/*.asm`, `Engine/Constants.asm`, `Engine/Variables.asm` |
| Batman & Robin | `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/` | `code/engine/objects.asm`, `code/engine/core.asm`, `OBJECT_SYSTEM.md`, `MEMORY_MAP.md` |
| Vectorman | `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/` | `code/disasm.asm`, `ANALYSIS.md`, `MEMORY_MAP.md` |
| Gunstar Heroes | `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/` | `code/disasm.asm`, `ANALYSIS.md`, `MEMORY_MAP.md` |
| Alien Soldier | `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/` | `code/disasm.asm`, `MEMORY_MAP.md` |
| Thunder Force IV | `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/` | `code/disasm.asm`, `ANALYSIS.md`, `MEMORY_MAP.md` |
| sonic_hack | `/home/volence/sonic_hacks/sonic_hack/` | `S4.constants.asm`, `code/objects/Object_Specific_Routines/*.asm`, `code/objects/Sonic.asm` |

## Research Questions (for reference — answer ALL of these for each source)

1. **SST field layout** — what fields, what offsets, what ordering rationale?
2. **SST size** — bytes per object slot?
3. **Object dispatch** — function pointer, jump table, ID + table, or hybrid?
4. **Slot counts and ranges** — how many slots, how partitioned?
5. **Particle/effect pool** — separate system for simple entities, or same object pool?
6. **Animation speed scaling** — how does animation rate link to movement speed?
7. **Hot/cold SST split** — any separation of frequently/rarely accessed fields?
8. **Struct-of-arrays** — any SoA patterns (positions contiguous, etc.)?
9. **Execution tiers / selective update** — do inactive/offscreen objects skip processing?
10. **Deferred deletion** — immediate vs mark-and-sweep?
11. **Object communication** — how do objects signal each other beyond parent/child?
+  **Open-ended** — anything novel or surprising worth noting?

---

## Task 1: Research S.C.E. Object System

**Files:**
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Constants.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Variables.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Process Objects.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Create Object.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Create Child Object.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Delete Object.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Animate Sprite.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Draw Sprite.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Render Sprites.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Touch Response.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Solid Object.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Move Sprite.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Check Range.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Check Wait.asm`
- Read: `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Misc.asm`

S.C.E. is our cleanest Sonic reference and the architecture doc's primary influence. This is the deepest dive.

- [ ] **Step 1: Extract SST layout from Constants.asm**

Search for object field offset definitions:

```bash
grep -n "equ\|EQU\|=\|set\|SET" "/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Constants.asm" | grep -i "obj\|sst\|status\|sprite\|render\|anim\|map\|art\|vel\|pos\|col\|pri\|sub\|rout\|flag\|width\|height\|child\|parent"
```

Read the full SST definition section. Document: every field, its offset, its size, and the ordering rationale (if comments explain it). Note the total SST size.

- [ ] **Step 2: Extract slot counts and ranges from Variables.asm**

```bash
grep -n "Object_RAM\|Player\|Dynamic\|Reserved\|Slot\|slot\|Object_Size\|next_object\|prev_object" "/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Variables.asm"
```

Read the Object RAM region definition. Document: how many slots, how they're partitioned (player/dynamic/effect/system), slot size, total RAM consumed.

- [ ] **Step 3: Read Process Objects (RunObjects equivalent)**

Read `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Process Objects.asm` in full.

Document:
- How does it iterate slots? (fixed stride, pointer chain, other)
- How does it dispatch to object routines? (what field, what mechanism)
- Does it skip empty/inactive slots? How?
- Are there execution tiers or categories?
- How does it handle deletion during iteration?

- [ ] **Step 4: Read Create Object and Create Child Object**

Read both files in full.

Document:
- How are free slots found? (linear scan, free list, stack, other)
- What fields are initialized during creation?
- Child creation: how many strategies? Descriptor format? What's inherited from parent?
- parent_ptr/child_ptr mechanics — how are chains built and walked?
- Cycle cost of allocation (count instructions on the common path)

- [ ] **Step 5: Read Delete Object**

Read `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Delete Object.asm` in full.

Document:
- Immediate or deferred deletion?
- How is the slot cleared? (`moveq #0` loop, `movem`, single clear?)
- Does it handle child cleanup? How?
- Does it return the slot to a free list/stack?

- [ ] **Step 6: Read Animate Sprite**

Read `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Animate Sprite.asm` in full.

Document:
- Animation script format (bytecode? table?)
- Control codes and their functions
- How frame duration works (fixed, per-frame, speed-linked?)
- Any animation events or callbacks?
- How does it integrate with art loading / DPLC?
- Is there a multi-sprite animation variant?

- [ ] **Step 7: Read Draw Sprite and Render Sprites**

Read both files in full.

Document:
- Two-phase render? How does Draw_Sprite store data for Render_Sprites?
- Priority band system — how many levels? How implemented?
- How is the VDP sprite table built? (link chain, direct write, buffer?)
- Overflow handling — what happens when too many sprites?
- Any compound/multi-sprite rendering?
- Sprite table dirty flag / conditional DMA?

- [ ] **Step 8: Read Touch Response and Solid Object**

Read both files in full.

Document:
- How does collision detection work? (AABB, registration list, spatial hash?)
- What determines collision type? (field in SST, separate table, bit flags?)
- How are collision dimensions determined? (from SST directly, lookup table, mapping-derived?)
- Solid object: how does side detection work? (which face was contacted)
- How many collision types / handlers?

- [ ] **Step 9: Read Move Sprite, Check Range, Check Wait, Misc**

Read all four files.

Document:
- ObjectMove: velocity → position update. Any gravity handling?
- Check Range: off-screen deletion / activation check?
- Check Wait: timer-based waiting / callback mechanism?
- Misc: any object communication, signal, or trigger mechanisms?
- Any selective update patterns (skip processing based on flags/distance)?

- [ ] **Step 10: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — S.C.E. object system research notes"
```

**No checkpoint here — continue to next reference.**

---

## Task 2: Research Batman & Robin Object System

**Files:**
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/OBJECT_SYSTEM.md`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/MEMORY_MAP.md`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/objects.asm`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/core.asm`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/main_loop.asm`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/objects/objects_1.asm`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/objects/objects_2.asm`

Batman & Robin (Clockwork Tortoise) is known for its VDP shadow table and sophisticated object system. The existing `OBJECT_SYSTEM.md` doc may already have analysis — start there.

- [ ] **Step 1: Read OBJECT_SYSTEM.md and MEMORY_MAP.md**

These are existing analysis documents. Read them in full and extract answers to all 11 research questions where available.

- [ ] **Step 2: Read objects.asm — core object routines**

Read `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/objects.asm` in full.

Document for all 11 questions:
- SST layout and size
- Object loop / dispatch mechanism
- Allocation (Batman uses doubly-linked free list per the architecture doc — verify and document the full mechanism)
- Deletion pattern (immediate vs deferred)
- Any execution tiers or selective update
- Object communication / signaling
- Anything novel or surprising

- [ ] **Step 3: Read core.asm and main_loop.asm for integration context**

How does the object system fit into the frame? What runs before/after objects? Any relevant patterns for our design.

- [ ] **Step 4: Scan objects_1.asm and objects_2.asm for patterns**

These are actual game objects. Scan (don't read every line) for:
- Common field access patterns (which SST offsets used most)
- Child creation patterns
- Animation patterns
- Any inter-object communication

```bash
grep -n "parent\|child\|signal\|trigger\|event\|message\|notify" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/objects.asm" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/objects/objects_1.asm"
```

- [ ] **Step 5: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — Batman & Robin object system research notes"
```

---

## Task 3: Research Vectorman Object System

**Files:**
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/ANALYSIS.md`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/MEMORY_MAP.md`
- Search: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/code/disasm.asm`

Vectorman (BlueSky) is relevant for its 64×64 plane setup (same as ours) and advanced sprite work.

- [ ] **Step 1: Read ANALYSIS.md and MEMORY_MAP.md**

Extract existing analysis. Focus on object system details, SST layout, slot counts, sprite rendering.

- [ ] **Step 2: Search disasm.asm for object system patterns**

Vectorman is a single-file disassembly. Search for object-related routines:

```bash
grep -n "Object\|object\|Sprite\|sprite\|Slot\|slot\|Alloc\|alloc\|Delete\|delete\|Create\|create\|Anim\|anim\|Collisi\|collisi\|Touch\|touch\|Process\|process\|particle\|Particle\|effect\|Effect" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/code/disasm.asm" | head -60
```

Read the routines found. Document for all 11 questions. Special attention to:
- How Vectorman handles its multi-joint character (3D-projected sprites — relevant to our multi-sprite rendering)
- Particle effects (Vectorman has heavy particle use — explosions, morphball particles)
- Any novel object system patterns

- [ ] **Step 3: Search for RAM layout / object RAM region**

```bash
grep -n "RAM\|ram\|Object_RAM\|Obj_RAM\|FF[0-9A-F]\{4\}" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/MEMORY_MAP.md"
```

Document slot counts, size per slot, total RAM usage.

- [ ] **Step 4: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — Vectorman object system research notes"
```

---

## Task 4: Research Gunstar Heroes Object System

**Files:**
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/ANALYSIS.md`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/MEMORY_MAP.md`
- Search: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/code/disasm.asm`

Gunstar Heroes (Treasure) is critical for parent-child links, multi-sprite objects, and handling extreme sprite counts.

- [ ] **Step 1: Read ANALYSIS.md and MEMORY_MAP.md**

Extract existing analysis. Treasure's object system is the reference for parent-child architecture.

- [ ] **Step 2: Search disasm.asm for object system patterns**

```bash
grep -n "Object\|object\|Sprite\|sprite\|Slot\|slot\|Alloc\|alloc\|Delete\|delete\|Create\|create\|parent\|child\|chain\|link\|Anim\|anim\|Collisi\|collisi" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/code/disasm.asm" | head -60
```

Read the routines found. Document for all 11 questions. Special attention to:
- Parent/child pointer mechanics (architecture doc says 380+ references in Alien Soldier)
- How multi-part bosses coordinate (object communication)
- How Treasure handles heavy sprite counts (20+ enemies on screen)
- The SWAP-based 16.16 fixed point (§5 mentions this — note if visible here)

- [ ] **Step 3: Search for object communication patterns**

```bash
grep -n "parent\|child\|sibling\|signal\|trigger\|boss\|phase\|state.*change\|notify\|broadcast" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/code/disasm.asm" | head -40
```

Document any patterns beyond simple parent/child pointers.

- [ ] **Step 4: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — Gunstar Heroes object system research notes"
```

---

## Task 5: Research Alien Soldier Object System

**Files:**
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/MEMORY_MAP.md`
- Search: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/code/disasm.asm`

Alien Soldier (Treasure) represents extreme 68000 optimization and the most mature version of Treasure's object system.

- [ ] **Step 1: Read MEMORY_MAP.md**

Note: `ANALYSIS.md` is a symlink to Gunstar's — check if it contains Alien Soldier-specific info or is Gunstar-only.

```bash
ls -la "/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/ANALYSIS.md"
```

Read `MEMORY_MAP.md` for SST layout, slot counts, RAM structure.

- [ ] **Step 2: Search disasm.asm for object system patterns**

```bash
grep -n "Object\|object\|Sprite\|sprite\|Slot\|slot\|Alloc\|alloc\|Delete\|delete\|Create\|create\|parent\|child\|Anim\|anim\|Collisi\|collisi" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/code/disasm.asm" | head -60
```

Document for all 11 questions. Special attention to:
- Differences from Gunstar Heroes (same engine, evolved)
- Any optimization techniques not seen in Gunstar
- Boss object coordination (Alien Soldier has complex multi-phase bosses)
- parent_ptr/child_ptr usage frequency and patterns

- [ ] **Step 3: Search for optimization patterns**

```bash
grep -n "movem\|swap\|moveq\|dbf\|addq\|subq" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/code/disasm.asm" | head -40
```

Look for tight inner loops in the object system — RunObjects, collision, rendering. Note cycle-saving techniques.

- [ ] **Step 4: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — Alien Soldier object system research notes"
```

---

## Task 6: Research Thunder Force IV Object System

**Files:**
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/ANALYSIS.md`
- Read: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/MEMORY_MAP.md`
- Search: `/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/code/disasm.asm`

Thunder Force IV (Technosoft) is a shmup with very different object requirements — many projectiles, bullet patterns, enemy waves. Relevant for particle pool design and high-count entity management.

- [ ] **Step 1: Read ANALYSIS.md and MEMORY_MAP.md**

Extract existing analysis. Focus on how a shmup handles dozens of bullets and enemies simultaneously.

- [ ] **Step 2: Search disasm.asm for object and projectile patterns**

```bash
grep -n "Object\|object\|Bullet\|bullet\|Shot\|shot\|Proj\|proj\|Enemy\|enemy\|Sprite\|sprite\|Alloc\|alloc\|Delete\|delete\|Pool\|pool\|Particle\|particle" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/code/disasm.asm" | head -60
```

Document for all 11 questions. Special attention to:
- How TF4 manages bullet pools (separate from main objects?)
- Projectile struct size (smaller than full object?)
- Execution patterns for many simultaneous entities
- Any round-robin or priority-based sprite rendering for overflow

- [ ] **Step 3: Search for sprite rendering under pressure**

```bash
grep -n "Render\|render\|Draw\|draw\|Sprite_Table\|SAT\|sprite_link\|overflow\|flicker\|priority" "/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/code/disasm.asm" | head -40
```

TF4 is known for sprite-heavy scenes. How does it handle overflow? Any cycling or multiplexing?

- [ ] **Step 4: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — Thunder Force IV object system research notes"
```

---

## Task 7: Research sonic_hack Object System

**Files:**
- Read: `/home/volence/sonic_hacks/sonic_hack/S4.constants.asm`
- Read: `/home/volence/sonic_hacks/sonic_hack/code/objects/Object_Specific_Routines/object_index.asm`
- Read: `/home/volence/sonic_hacks/sonic_hack/code/objects/Sonic.asm` (scan, not full read)
- Search: `/home/volence/sonic_hacks/sonic_hack/code/objects/Object_Specific_Routines/`

sonic_hack is our data source and the user's prior work. The dual dispatch approach (word function pointer + separate ID table) is a noted preference to validate.

- [ ] **Step 1: Extract SST layout from S4.constants.asm**

```bash
grep -n "equ\|EQU\|=\|set\|SET" /home/volence/sonic_hacks/sonic_hack/S4.constants.asm | grep -i "obj\|sst\|status\|sprite\|render\|anim\|map\|art\|vel\|pos\|col\|pri\|sub\|rout\|flag\|width\|height\|child\|parent\|id\|code"
```

Read the full SST definition. Document field layout, size, ordering. Note the word function pointer mechanism.

- [ ] **Step 2: Read object_index.asm for dispatch mechanism**

Read `/home/volence/sonic_hacks/sonic_hack/code/objects/Object_Specific_Routines/object_index.asm` in full.

Document:
- How object IDs map to routines
- Is this the "separate ID + jump table" part of the dual approach?
- How does this interact with the word function pointer in the SST?

- [ ] **Step 3: Search Object_Specific_Routines for shared patterns**

```bash
grep -rn "DeleteObject\|SingleObjLoad\|ObjectMove\|SpeedToPos\|RememberState\|MarkObj\|DisplaySprite\|DrawSprite" /home/volence/sonic_hacks/sonic_hack/code/objects/Object_Specific_Routines/ --include="*.asm" | head -30
```

```bash
ls /home/volence/sonic_hacks/sonic_hack/code/objects/Object_Specific_Routines/
```

Document:
- All shared routines available to objects
- How DeleteObject works (immediate? slot clearing?)
- How SingleObjLoad works (linear scan? how many variants?)
- Object communication patterns across routines

- [ ] **Step 4: Scan Sonic.asm for player object patterns**

```bash
grep -n "routine\|state\|anim\|collision\|velocity\|speed\|inertia\|angle\|shield" /home/volence/sonic_hacks/sonic_hack/code/objects/Sonic.asm | head -40
```

Don't read every line — scan for structural patterns:
- How does the player state machine work?
- Animation speed scaling (walk→run transition)
- Collision integration

- [ ] **Step 5: Check for particle/effect patterns**

```bash
grep -rn "scatter\|explosion\|debris\|particle\|effect\|dust\|splash\|star\|sparkle\|ring.*scatter\|ring.*loss" /home/volence/sonic_hacks/sonic_hack/code/objects/ --include="*.asm" | head -20
```

How does sonic_hack handle ring scatter, explosions, and other high-count transient effects? Same SST slots or special handling?

- [ ] **Step 6: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — sonic_hack object system research notes"
```

---

## Task 8: Online Research

**Files:**
- Web searches for each source category

This task searches online sources for object system design patterns, 68000 optimization techniques, and modern approaches adaptable to Genesis hardware.

- [ ] **Step 1: Search plutiedev for 68000 addressing and optimization**

Search for:
- 68000 instruction timing reference (which addressing modes cost what)
- Offset thresholds for short vs long displacement ($00-$7F vs $80+)
- Any object system or game loop design guidance

```bash
# Web search
```

Document: instruction cycle costs for common SST access patterns, optimal offset ranges.

- [ ] **Step 2: Search SpritesMind for object system discussions**

Search for:
- "object system" Genesis/Mega Drive discussions
- "sprite table" optimization threads
- "particle system" 68000 threads
- "struct of arrays" or "data oriented" 68000 discussions
- Any debates about SST layout or object allocation

```bash
# Web search: site:gendev.spritesmind.net object system
# Web search: site:gendev.spritesmind.net sprite table optimization
# Web search: site:gendev.spritesmind.net particle effect genesis
```

- [ ] **Step 3: Search SGDK for modern Genesis object management**

Search SGDK (github.com/Stephane-D/SGDK) for:
- Object/entity management system
- Sprite engine implementation
- Pool allocation patterns
- Collision detection approach

```bash
# Web search: SGDK sprite engine object management site:github.com
```

- [ ] **Step 4: Search GitHub homebrew for novel object systems**

Search for Genesis/Mega Drive homebrew projects with interesting object systems:
- Xeno Crisis — modern commercial Genesis game
- Tanglewood — puzzle platformer
- Demons of Asteborg — action platformer
- Project MD — Mega Drive framework
- Any other Genesis homebrew with documented object systems

```bash
# Web search: genesis mega drive homebrew object system 68000
# Web search: "xeno crisis" genesis object system
# Web search: project-md mega drive entity
```

- [ ] **Step 5: Search for data-oriented design on 68000 / retro hardware**

Search for:
- Struct-of-arrays on 68000 or similar 16-bit CPUs
- Data-oriented design adapted for hardware without caches
- Amiga demoscene particle systems (68000, similar bus architecture)
- Any analysis of AoS vs SoA performance on 68000

```bash
# Web search: "struct of arrays" 68000 performance
# Web search: amiga demoscene particle system 68000
# Web search: data oriented design retro 16-bit
```

- [ ] **Step 6: Search for deferred deletion and entity lifecycle patterns**

Search for:
- Deferred deletion in game engines (mark-and-sweep vs immediate)
- Entity lifecycle patterns in retro games
- Double-buffered object lists
- Any 68000-specific considerations for deletion during iteration

```bash
# Web search: deferred deletion game engine entity
# Web search: entity lifecycle retro game 68000
```

- [ ] **Step 7: Search for object communication / event systems in retro games**

Search for:
- Signal/event systems in Genesis games
- Object messaging in retro game engines
- Trigger arrays, event buffers
- Boss phase coordination patterns

```bash
# Web search: object communication retro game engine event system
# Web search: genesis mega drive boss object coordination
```

- [ ] **Step 8: Commit progress notes**

```bash
git add -A
git commit -m "docs(§3): Phase 0 — online research notes"
```

---

## Task 9: Synthesize Findings and Write Research Document

**Files:**
- Create: `docs/research/object-system-foundations.md`

- [ ] **Step 1: Compile raw notes from Tasks 1-8**

Gather all findings from the 7 reference disassemblies and online research. Organize by research question.

- [ ] **Step 2: Write research document — reference summaries**

Create `docs/research/object-system-foundations.md`. Start with a summary of each reference's object system:

```markdown
# §3 Object System — Foundational Research

## Reference Summaries

### S.C.E.
[Summary of SST layout, dispatch, allocation, rendering, collision, animation, etc.]

### Batman & Robin
[Summary]

### Vectorman
[Summary]

### Gunstar Heroes
[Summary]

### Alien Soldier
[Summary]

### Thunder Force IV
[Summary]

### sonic_hack
[Summary]

### Online Sources
[Key findings from plutiedev, SpritesMind, SGDK, homebrew, Amiga demoscene]
```

- [ ] **Step 3: Write research document — comparison tables**

Add comparison tables for each major research question:

```markdown
## Comparison Tables

### SST Layout Comparison
| Reference | Size | Position Offset | Velocity Offset | Dispatch Offset | Notable Fields |
|-----------|------|-----------------|-----------------|-----------------|----------------|
| S.C.E.    | $XX  | $XX             | $XX             | $XX             | ...            |
| ...       |      |                 |                 |                 |                |

### Object Dispatch Comparison
| Reference | Mechanism | Cycle Cost | Notes |
|-----------|-----------|------------|-------|
| ...       |           |            |       |

### Slot Count Comparison
| Reference | Total Slots | Player | Dynamic | Effect | System | Total RAM |
|-----------|-------------|--------|---------|--------|--------|-----------|
| ...       |             |        |         |        |        |           |

### Allocation Mechanism Comparison
| Reference | Method | Alloc Cost | Free Cost | Notes |
|-----------|--------|------------|-----------|-------|
| ...       |        |            |           |       |

### Particle/Effect Handling Comparison
| Reference | Approach | Struct Size | Max Count | Separate Pool? |
|-----------|----------|-------------|-----------|----------------|
| ...       |          |             |           |                |
```

- [ ] **Step 4: Write research document — validated decisions**

For each of the 11 research questions, write a decision section:

```markdown
## Validated Decisions

### 1. SST Field Layout
**Decision:** [What we're going with]
**Rationale:** [Why, citing evidence from references]
**Changed from architecture doc:** [Yes/no, what changed and why]

### 2. SST Size
...

### 3. Object Dispatch
**Note:** sonic_hack's dual approach (word function pointer for dispatch + separate ID table for spawning/inspection) is a preference to validate.
...

[Continue for all 11 questions]

### 12. Novel Findings
[Anything unexpected discovered during research]
```

- [ ] **Step 5: Add deferred items section**

```markdown
## Deferred for Later Phases
[Any design questions that can't be resolved until implementation reveals real constraints]
```

- [ ] **Step 6: Commit research document**

```bash
git add docs/research/object-system-foundations.md
git commit -m "docs(§3): Phase 0 — object system foundational research complete"
```

**CHECKPOINT: Review research findings and validated decisions before proceeding.**

---

## Task 10: Update ENGINE_ARCHITECTURE.md

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§3 section, lines ~1419-1731)

- [ ] **Step 1: Compare validated decisions against current §3 design**

Read current `docs/ENGINE_ARCHITECTURE.md` §3 (lines 1419-1731). For each of the 11 research questions, check if the validated decision differs from what's currently documented.

- [ ] **Step 2: Update §3 with changes**

For each decision that changed, update the relevant subsection in ENGINE_ARCHITECTURE.md. Add implementation notes where research provided new detail. Preserve existing content that wasn't invalidated.

If no decisions changed, add a brief note: "§3 design validated by Phase 0 research — no changes."

- [ ] **Step 3: Update DEFERRED_WORK.md if new deferred items identified**

If research identified any new deferred items not already tracked, add them to `docs/DEFERRED_WORK.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§3): update architecture doc with Phase 0 research findings"
```

**CHECKPOINT: Phase 0 complete. Research validated, architecture updated. Ready for Phase 1-7 implementation plan.**

---

## After Phase 0

When Phase 0 is complete and validated, write the Phase 1-7 implementation plan as a separate document (`docs/superpowers/plans/2026-04-24-object-system-implementation.md`). That plan will use the validated SST layout, dispatch mechanism, slot counts, and other decisions from the research findings — details that can't be written until Phase 0 produces them.
