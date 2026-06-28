# §3 Object System — Design Spec

**Date:** 2026-04-24
**Scope:** SST layout, free slot stack, RunObjects loop, object dispatch, sprite rendering (core → advanced), animation system (basic → events), collision system (object-vs-object), stub terrain, controller input, data-driven child creation, basic object loading, particle/effect pool, stress testing, advanced sprite optimizations.
**Baseline:** ENGINE_ARCHITECTURE.md §3
**Defers:** VRAM allocator integration (§2.2), section-local entity management (§4), ring system (§4), terrain collision with slopes/angles (§4), DPLC lookahead (needs real gameplay scenes)

---

## Overview

The object system is the backbone — every gameplay entity runs through it. This spec covers the full build from foundational research through stress-tested optimization, delivered in 8 phases.

All object code is written fresh for aeon conventions. Art data (sprites, palettes, DPLC tables) comes from sonic_hack; code never does. Test objects use existing Sonic/Tails sprites for the player-like object and synthetic art (colored rectangles) for enemies, solids, and collision test objects.

**Next brainstorming session after §3:** Deferred item catch-up. §3 unlocks several blocked items: Dynamic VRAM Allocator (§2.2), Refcount Art Caching (§2.2), Generic Perform_DPLC SST integration (§2.1/§3.9), DPLC Lookahead (§1.6), Adaptive DMA Byte Budget (§1.1). Review all, decide what to tackle before §4.

---

## Phase Structure

| Phase | Pattern | Deliverable | Test |
|-------|---------|-------------|------|
| 0 | Research | SST layout, dispatch, slot counts, particle pool, and novel design questions — all foundational decisions | Findings doc with validated decisions |
| 1 | Build | SST struct + free slot stack + RunObjects + basic sprite rendering | Objects on screen, allocated from stack, rendering through priority bands |
| 2 | Research → Build | Animation system (basic playback, speed scaling research) | Walk cycle playing via DPLC, frame changes driving DMA |
| 3 | Research → Build | Collision system + sprite rendering priority/overflow + stub terrain + controller input | Controllable object with gravity, touching enemies/solids |
| 4 | Research → Build | Child creation + object loading + particle pool + animation events | Multi-part objects, particle shower, animation-driven behavior |
| 5 | Build | Combined sandbox — full integration test | All systems exercising together in a playable test scene |
| 6 | Benchmark | Stress test — fill slots, heavy collision, particles at capacity | Baseline frame timing metrics (CPU per subsystem) |
| 7 | Research → Build | Advanced sprite rendering — LOD, link cycling, scanline budgeting, multiplexing | Re-run stress test, compare before/after metrics |

---

## Phase 0: Foundational Research

**Goal:** Resolve every decision that affects SST layout and core object system architecture before writing a single struct definition. These choices are permanent — changing field offsets after Phase 1 means rewriting every object routine.

### Research Questions

| # | Question | What to investigate | Why it matters |
|---|----------|-------------------|----------------|
| 1 | SST field layout | Access patterns across all 7 references — which fields are read together, written together, optimal ordering for 68000 instruction encoding (byte vs word offset thresholds at $80) | Fields at offsets $00-$7F use shorter instructions. Clustering hot fields saves cycles on every object every frame |
| 2 | SST size | Is $50 right? Could $48 or $58 be better? What do references actually use and why? | Affects total slot count, RAM usage, and iteration stride |
| 3 | Object dispatch | Word function pointer (sonic_hack dual approach), longword pointer, ID + jump table, or something else? sonic_hack uses word-sized function pointer for fast dispatch + separate ID+table for spawning/inspection — validate or improve | Called for every active object every frame — even small cycle differences compound |
| 4 | Slot counts and ranges | Peak object counts in demanding Sonic scenes (boss fights, ring scatter, badnik-heavy zones). How many player/dynamic/effect/system slots? | Too few = objects get dropped. Too many = wasted RAM + longer RunObjects loop |
| 5 | Particle/effect pool | How do references handle high-count simple entities (ring scatter, explosions, dust)? Separate pool with smaller struct, or same SST with wasted fields? What struct size? | Determines whether we need a second lightweight system alongside the main object loop |
| 6 | Animation speed scaling | Accumulator (add velocity to counter, advance on overflow) vs division vs table lookup vs other mechanisms across all references | Needs to be decided before animation fields go into the SST |
| 7 | Hot/cold SST split | Physically separate hot array (position, velocity, flags — touched every frame) from cold array (mappings, animation tables, child pointers — only during render/spawn). Data-oriented design adapted for 68000 bus | Could improve sequential access patterns, but adds indirection. Need to measure the tradeoff |
| 8 | Struct-of-arrays | All X positions contiguous, all Y positions contiguous. Enables batch collision checks, batch position updates. Radical departure from traditional Genesis layout. **Evaluate alongside #7** — SoA makes hot/cold split implicit | Potentially powerful for batch operations but 68000 has no cache — different tradeoffs than modern CPUs |
| 9 | Execution tiers / selective update | Capability flags (has_gravity, has_animation, has_collision) to skip subsystems an object doesn't need. Distance-based tiers — off-screen objects run at half rate or skip entirely | Could save significant CPU in dense scenes but adds branching overhead per object |
| 10 | Deferred deletion | Mark-for-delete + batch cleanup at end of frame vs immediate delete during iteration. What do references do? Any subtle bugs from mid-loop deletion? | Affects RunObjects loop design and whether deletion can corrupt iteration |
| 11 | Object communication | Beyond parent/child links — trigger arrays, event buffers, signal systems for switches/doors/boss phase triggers. How do references handle inter-object messaging? | Boss fights and puzzle mechanics need objects to coordinate |
| + | Open-ended | Anything novel found during research that we haven't anticipated | Keep an open eye — the best ideas may come from unexpected sources |

### Research Sources

**All 7 reference disassemblies (mandatory for each question):**
- S.C.E. (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`)
- Batman & Robin (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/`)
- Vectorman (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/vectorman_disasm/`)
- Gunstar Heroes (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/gunstar_disasm/`)
- Alien Soldier (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/aliensoldier_disasm/`)
- Thunder Force IV (`/home/volence/sonic_hacks/The Adventures of Batman and Robin/thunderforce4_disasm/`)
- sonic_hack (`/home/volence/sonic_hacks/sonic_hack/`)

**Online sources:**
- plutiedev.com — 68000 instruction timing, addressing modes
- SpritesMind forum — object system discussions, optimization techniques
- SGDK (Stephane-D) — modern Genesis object/sprite management
- GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD)
- Amiga demoscene — particle systems, data-oriented 68000 techniques
- Modern engine design literature — ECS patterns, data-oriented design adapted for 68000 constraints

### Deliverable

Research findings document (`docs/research/object-system-foundations.md`) with:
- Summary of each reference's approach to each question
- Comparison tables where applicable
- Validated decisions for SST layout, size, dispatch, slots, particles
- Novel findings section for anything unexpected
- Updated ENGINE_ARCHITECTURE.md §3 if any designs change

---

## Phase 1: SST + Free Slot Stack + RunObjects + Basic Sprite Rendering

**Goal:** Build the object system skeleton using Phase 0's validated decisions. Objects exist in RAM, can be allocated and freed, run their routines each frame, and display on screen.

### Deliverables

- **SST struct definition** — Using `struct`/`endstruct` per coding conventions. Field layout from Phase 0 research.
- **RAM layout** — Object RAM region using `phase`/`dephase`. Slot ranges (player, dynamic, effect, system) with clear boundaries.
- **Free slot stack** — Per-range stacks if research supports it, or single stack. O(1) alloc/free. Init routine that pushes all slot addresses at level start.
- **RunObjects loop** — Iterates active slots, dispatches to object routines via the mechanism chosen in Phase 0. Handles inactive (empty) slots efficiently.
- **Basic sprite rendering** — Two-phase: `Draw_Sprite` during object loop (stores pointer to priority band list), `Render_Sprites` after loop (converts to VDP sprite table entries). Priority bands implemented. Basic overflow protection (band overflow → next band).
- **DeleteObject** — Pushes slot back to free stack, clears SST entry.

### Test

Allocate a handful of test objects from the free slot stack. Each has a simple routine (static display). Objects appear on screen at different positions and priority levels. Verify: allocation works, RunObjects dispatches correctly, sprites render in priority order, DeleteObject frees slots for reuse.

### Success Criteria

- Objects allocate in O(1) from free slot stack
- RunObjects iterates and dispatches correctly
- Sprites display on screen through two-phase render
- Priority bands order sprites correctly
- DeleteObject returns slots to the stack
- Build succeeds, ROM runs in emulator

---

## Phase 2: Animation System (Research → Build)

**Goal:** Research animation approaches, then build basic animation playback wired into the §2 DPLC pipeline.

### Research

All 7 references + online sources, focused on:
- Animation script formats (bytecode, table-driven, hardcoded)
- Frame duration mechanisms (fixed, per-frame, speed-linked)
- How animation drives art loading (DPLC integration)
- Animation speed scaling mechanisms (accumulator, division, table — validate for §3 SST)
- Multi-sprite animation (parent drives children)
- Any novel animation techniques

### Deliverables

- **AnimateSprite routine** — Bytecode interpreter for basic control codes: $FF loop, $FE jump back N frames, $FB delete object, standard frame indices, per-frame delay ($F4).
- **Animation table pointer in SST** — Set once during object init, read by AnimateSprite internally (no `lea` before every call).
- **DPLC integration** — Frame changes detected by comparing current mapping_frame to previous. On change, Perform_DPLC queues DMA from uncompressed ROM art to VRAM via §2 pipeline.
- **Speed scaling** — Mechanism chosen by research. Implemented or noted for Phase 4 animation events if it's an event code.

### Test

Display Sonic's walk cycle: animation script plays through frames, each frame change triggers DPLC → DMA → VRAM update. Sprite on screen shows smooth animation. Verify frame timing, correct art per frame.

### Success Criteria

- Animation plays through frames with correct timing
- Frame changes trigger DPLC-driven art updates via §2 DMA pipeline
- Loop and jump-back control codes work correctly
- $FB delete code destroys object and frees slot
- Animation table pointer eliminates per-call `lea`

---

## Phase 3: Collision + Sprite Priority/Overflow + Stub Terrain + Controller (Research → Build)

**Goal:** Research collision approaches, then build object-vs-object collision with type dispatch, enhance sprite rendering with priority and overflow handling, add stub terrain and controller input for a controllable test player.

### Research

All 7 references + online sources, focused on:
- Collision detection algorithms (AABB, per-type handlers, registration lists, spatial partitioning)
- Collision response patterns (solid standing, push-out, bounce, damage)
- How references handle solid object interactions (which side was contacted?)
- Sprite overflow handling (round-robin, priority-based culling, degradation)
- Controller reading patterns (6-button protocol, debouncing, press/hold/release detection)

### Deliverables

- **TouchResponse** — Iterates dynamic slots, checks collision_response for non-zero, performs AABB overlap test using width_pixels/height_pixels from SST, dispatches to per-type handler.
- **Collision handlers** — At minimum: COLLISION_SOLID (AABB push-out with side detection), COLLISION_ENEMY (killable by spin/roll), COLLISION_HURT (damages on contact), COLLISION_SPRING (solid + bounce). More types added as research dictates.
- **Sprite rendering enhancements** — Priority band overflow to next band. Pre-initialized link chain.
- **Stub terrain** — Flat floor at a fixed Y coordinate. Objects with gravity fall until they hit the floor, then stand. No slopes, no angles, no collision map — pure placeholder for §4. Clearly marked as throwaway.
- **Controller input** — Read controller state, detect press/hold/release. Wire to test player for movement and jumping.

### Test

Controllable player object: walks left/right, jumps, has gravity, lands on flat floor. Test solid blocks the player can't walk through (side detection working). Test enemy that hurts the player on contact. Test spring that bounces the player upward. All rendering through priority bands with correct layering.

### Success Criteria

- Player moves with controller input, jumps, lands on stub floor
- Solid collision prevents walking through blocks (correct side detection)
- Enemy collision triggers hurt response
- Spring collision bounces player
- Sprite priority ordering correct under multiple overlapping objects
- No collision detection bugs (no tunneling, no stuck states)

---

## Phase 4: Child Creation + Object Loading + Particle Pool + Animation Events (Research → Build)

**Goal:** Research child creation, particle systems, and animation events, then build data-driven child creation, basic object loading, a lightweight particle pool, and animation event codes.

### Research

All 7 references + online sources, focused on:
- Child creation patterns (descriptor tables, linked lists, inheritance)
- Object initialization / loading (format bytes, data blocks, field setup)
- Particle / high-count entity systems (pools, ring scatter, explosions)
- Animation event systems (frame-triggered callbacks, sound cues, collision changes)
- Any novel approaches to any of the above

### Deliverables

- **Data-driven child creation** — Descriptor-table-driven child spawning. Strategies validated by research (architecture doc proposes 4: Normal, Complex, Linked, FlipAware — research confirms or adjusts). Auto-sets parent_ptr/child_ptr. Children inherit art from parent where appropriate. Cleanup chain on parent death.
- **Basic object loading** — `Load_Object` reads format byte from data block, initializes SST fields accordingly. Without VRAM allocator (deferred) — art_tile set directly for now.
- **Particle/effect pool** — Lightweight struct (size determined by Phase 0 research). Separate tight update loop and simple renderer. No collision, no animation state machine. Used for: visual effects, debris, dust, sparkles.
- **Animation events** — $F9 play sound, $F8 call routine, $F7 set collision, $F6 set field, $F5 speed-linked (mechanism from Phase 2 research). Extends the basic playback interpreter from Phase 2.

### Test

Multi-part test object: parent with 2-3 children, all rendering as a group. Destroy parent → children auto-delete. Particle shower: spawn 20+ particles from a point, each with velocity and lifespan, rendering through the particle pool. Animation events: test object whose animation script changes its collision type mid-animation and plays a sound cue.

### Success Criteria

- Child creation from descriptor table works for at least 2 strategies
- Parent death cascades to all children
- Children inherit parent art
- Load_Object initializes SST fields from format byte correctly
- Particle pool handles 20+ simultaneous particles without frame drops
- Particles have independent position/velocity/lifespan, render correctly
- Animation events fire at correct frames (collision change, sound, routine call)

---

## Phase 5: Combined Sandbox

**Goal:** Bring all systems together into a single test scene proving end-to-end integration.

### Scene Contents

- **Player** — Sonic sprites, animated walk/idle/jump cycle, DPLC-driven art, controller input, gravity + stub floor, collision with all object types
- **Badniks** — 2-3 test enemies with simple AI (walk back and forth), animated, hurtable by player
- **Solid platforms** — Static blocks at various positions, player stands on them and can't walk through them
- **Springs** — Bounce the player upward on contact
- **Multi-part object** — A "boss-like" test object with children, animation events changing collision state
- **Particle emitter** — Continuous particle shower demonstrating the particle pool
- **Mixed priority** — Objects at different priority levels rendering in correct order

### Success Criteria

- All systems work together without conflicts
- Player can navigate the scene, interact with all object types
- No crashes, no visual corruption, no stuck states
- Particle pool and main object system coexist through the DMA pipeline
- Frame runs within CPU budget (no lag frames under normal load)

---

## Phase 6: Stress Test + Baseline Benchmark

**Goal:** Push the object system to its limits and capture baseline performance metrics for before/after comparison with Phase 7 optimizations.

### Stress Tests

- **Slot saturation** — Fill all dynamic slots with active, animated, colliding objects
- **Collision pressure** — Cluster objects so every pair triggers an overlap check
- **Rapid alloc/free** — Spawn and destroy objects continuously (e.g., projectile stream)
- **Particle flood** — Particle pool at maximum capacity
- **Combined worst case** — All of the above simultaneously

### Metrics to Capture

- Total RunObjects CPU time (cycles or scanlines)
- TouchResponse CPU time separately
- Render_Sprites CPU time separately
- Particle pool update + render time
- DPLC/DMA queue utilization
- Frame timing (lag frame count under stress)
- Peak slot usage

### Deliverable

Benchmark results document. This is the "before" snapshot. Phase 7 optimizations will be measured against these numbers.

---

## Phase 7: Advanced Sprite Rendering (Research → Build + Benchmark)

**Goal:** Research and implement sprite rendering optimizations, then re-run the Phase 6 stress test to measure gains.

### Research

All 7 references + online sources, focused on:
- Link-order cycling (which games do it, how, measured fairness improvement)
- Sprite LOD for distant objects (simplified mappings, reduced piece count)
- Scanline-aware sprite budgeting (per-scanline pixel counters, proactive culling vs VDP silent dropout)
- Sprite multiplexing (HBlank SAT rewrites for virtual sprites beyond 80)
- Any other sprite rendering optimizations found in references

### Deliverables

- **Link-order cycling** — Rotate link chain start point each frame for overflow fairness (flicker instead of permanent dropout)
- **Scanline-aware budgeting** — Per-scanline sprite pixel counter during Render_Sprites. Proactive skip/shrink when budget exhausted
- **Sprite LOD** — Simplified mappings for objects far from camera center (if research validates the approach)
- **Sprite multiplexing** — HBlank SAT rewrites for particle/weather systems (if research validates the approach and particle pool benefits from it)

### Benchmark

Re-run exact Phase 6 stress test suite. Compare:
- Render_Sprites CPU time (before vs after)
- Visual quality under overflow (flickering vs permanent dropout)
- Effective sprite count on screen (with multiplexing if implemented)
- Any regressions in non-stressed scenarios

### Success Criteria

- Measurable improvement in at least one metric under stress
- No regressions under normal load
- Overflow behavior visually improved (fair flicker vs dropout)
- Before/after comparison documented

---

## Deferred Work (to add to DEFERRED_WORK.md after §3)

Items that §3 identifies but cannot complete:

- **VRAM allocator integration in Load_Object** — Blocked by §2.2 Dynamic VRAM Allocator (needs spawn/destroy lifecycle, which §3 now provides). When ready: deferred item catch-up session.
- **Section-local entity management** — Blocked by §4 Level/World. When ready: after §4 defines section format and entity tables.
- **Ring system** — Blocked by §4. Per-slot ring buffers with section-local coordinates.
- **Terrain collision (slopes, angles, sensors)** — Blocked by §4 collision map format. Stub terrain (Phase 3) replaced by real system in §4.
- **DPLC lookahead** — Needs real gameplay scenes to tune. Can be added after animation system exists (which §3 provides).

---

## Asset Strategy

- **Sonic/Tails sprites** — Already extracted in `art/uncompressed/characters/` and `art/optimized/characters/` with DPLC tables in `data/dplc/`. Used for the player-like test object.
- **Test object art** — Simple synthetic sprites (colored rectangles, basic shapes) created fresh. Small enough to define inline or as minimal binary files. Purpose: easy to debug visually, no extraction work, disposable.
- **All object code** — Written from scratch for aeon conventions. Reference sonic_hack only for behavioral understanding (what an object does), never for implementation (how it does it).
