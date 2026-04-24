# Object System Foundations — Research Synthesis

Research synthesis across 7 reference disassemblies and online sources, providing the evidential foundation for all Section 3 (Object System) implementation decisions in the Sonic 4 Engine.

Sources examined: S.C.E. (Sonic Clean Engine), Batman & Robin (Clockwork Tortoise), Vectorman (BlueSky), Gunstar Heroes (Treasure), Alien Soldier (Treasure), Thunder Force IV (Technosoft), sonic_hack (modified Sonic 2), and online research (plutiedev, SpritesMind, SGDK, homebrew projects, Amiga demoscene).

---

## 1. Executive Summary

The object system is the most heavily iterated subsystem across Genesis games, and the seven reference disassemblies reveal a surprisingly wide design space. SST sizes range from 32 bytes (Thunder Force IV projectiles) to 224 bytes (Gunstar Heroes player singleton). Dispatch methods split cleanly into two schools: Sonic-derived engines (S.C.E., sonic_hack) use function pointers at offset $00 for maximum flexibility, while Treasure engines (Gunstar Heroes, Alien Soldier) use word-offset jump tables with self-advancing routine counters for minimal per-dispatch overhead. Both approaches work; the deciding factor is whether objects need to change their update routine dynamically (function pointer wins) or follow a predictable linear state progression (jump table wins). Our engine needs both patterns across different object types, so the function pointer approach at $00 is correct as the primary dispatch — objects that want linear state progression can implement it internally via routine counter fields in their custom data area.

Allocation strategy is where our engine makes its most significant departure from all references. Every commercial Genesis game and every community engine uses linear scan (O(n)) for slot allocation. S.C.E.'s `tst.l code_addr(a0); dbeq d0,.find` is the cleanest implementation but still worst-cases at 90 iterations. Batman & Robin's doubly-linked active list is the most sophisticated alternative but adds 4 bytes of pointer overhead per slot. Our free slot stack is genuinely novel — O(1) allocate, O(1) free, zero per-slot overhead — and no counter-evidence has emerged from any source. This is the single biggest algorithmic win in the object system.

Deletion strategy is the question where reference engines diverge most dramatically. Five of the seven use immediate deletion (zero the slot, it falls out of the system). Alien Soldier alone uses true mark-and-sweep — `bset.b #$4, $2(a5)` at 80+ call sites, with a sweep pass at $1CA16 cleaning up at end-of-frame. Batman & Robin uses an unusual stack-restoration technique where an object deleting itself mid-update restores SP to jump back to the main loop, skipping the rest of its update code. The evidence overwhelmingly favors immediate deletion for our engine: it is simpler, it pairs naturally with the free slot stack (delete = push address back), and Alien Soldier's deferred approach exists to solve a problem (mid-iteration mutation of a flat pointer list) that our architecture avoids by design.

The animation system findings validate and extend our planned behavior sequencer. Alien Soldier's self-advancing pointer technique (the ROM pointer IS the animation state — no frame index bookkeeping) is the most elegant animation implementation found in any reference. Thunder Force IV's dual-use frame counter (driving both animation AND object lifetime) demonstrates how animation timing can subsume general-purpose timers. SGDK's `onFrameChange` callback pattern independently validates our animation-events-as-behavior-sequencer design. The synthesis of these three approaches — self-advancing ROM pointers, animation-as-lifetime, and frame-change callbacks — produces a system more powerful than any single reference.

The "hot/cold field split" question, which motivated our SST reordering, received a definitive answer from online research: the 68000 has no data cache, so there is zero hardware benefit to field ordering for sequential-access optimization. However, there IS a software benefit: keeping all high-frequency fields within the first 16 bytes of the SST means the most common field accesses use the smallest displacements in `d(An)` addressing, saving 0 bytes per access (since all displacements within $50 are 16-bit anyway) but improving code readability and maintenance. The real optimization is keeping `code_addr` at offset $00 for zero-offset `(a0)` addressing — this saves 2 bytes and 4 cycles per dispatch versus any other offset. Every reference engine that uses function pointer dispatch puts the dispatch field at $00.

---

## 2. Reference Summary Table

| Reference | SST Size | Slot Count | Dispatch | Allocation | Deletion | Animation | Key Innovation |
|-----------|----------|------------|----------|------------|----------|-----------|----------------|
| **S.C.E.** | $50 (80B) | 109 (3+90+16) | Function ptr at $00 | Linear scan (dbf) | Immediate (clr code_addr) | Timer-based + velocity scaling | Priority-as-bucket-offset; 12 child creation strategies |
| **Batman & Robin** | $5A (90B) | 140 | Doubly-linked active list | Multi-slot atomic alloc | SP restore (mid-update exit) | Two-level threaded bytecode + fractional accumulator | Dual active lists with semaphore; spatial collision buckets |
| **Vectorman** | 12B dispatch + heap | Variable | Update/render split passes | Heap allocator (variable-size) | Kill-flag-then-free | N/A (callback-driven) | Implicit hot/cold split; callback-based communication |
| **Gunstar Heroes** | $60 (96B) | ~27 enemy + pools | Word-offset jump table | Linear scan, Z-flag return | Immediate (clr.w $2) | Timer countdown at $4C | Tri-state mode word; adjacent-slot children; SWAP tricks |
| **Alien Soldier** | $60 (96B) | 61 main + bullet pool + 5 boss | Two-stage (activity check + jump table) | Sequential scan ($02 test) | Mark-and-sweep (bset then sweep) | Self-advancing ROM pointer | Dual link fields ($58+$5C); deferred deletion; VDP command pre-build |
| **Thunder Force IV** | $20/$40/$60 | 73 (1+20+12+40) | Type index * 4 + jump table; projectiles have NO dispatch | Per-frame free-list rebuild | Immediate (clr.w) | Frame counter drives both animation AND lifetime | Per-type pool sizing; pre-formatted SAT; priority cycling; multi-sprite per slot |
| **sonic_hack** | $50 (80B) | 121 (3 partitions) | Dual (word fn ptr + Obj_Index table) | Free slot stack (O(1)) | Deferred mark+sweep | Speed scaling via ($800 - \|inertia\|) >> 8 | Dual dispatch separating per-frame vs spawn-time routing |

---

## 3. Per-Question Analysis

### Q1: SST Field Layout — What Fields, What Order, What at Offset $00?

**Our original plan:** Hot/cold reorder with `id/objroutine` (word) at $00, positions at $02/$06, velocities at $0A/$0C, render/collision at $0E/$0F. Fields ordered by access frequency.

**What the research says:**

Every reference engine that uses function pointer dispatch puts the dispatch field at offset $00. The zero-offset `(a0)` or `(a5)` addressing mode saves 2 bytes and 4 cycles over `d(a0)` with any non-zero displacement. This is universally agreed upon:

- S.C.E.: `code_addr` at $00 (longword function pointer)
- Gunstar Heroes: mode word at $02, but dispatch index at $04 (uses a5-relative; $00 reserved for object type ID)
- Alien Soldier: same as Gunstar ($02 activity flags, $04 dispatch offset)
- sonic_hack: `code_addr` at $00 (word function pointer)
- Batman & Robin: code pointer at $00

Treasure's approach of putting a type/mode word at $02 and the dispatch offset at $04 is interesting but serves their jump-table dispatch model. For function pointer dispatch, the pointer must be at $00.

**Online research confirms:** `move.l (a0),d0` (zero offset) saves 2 bytes + 4 cycles over `move.l 0(a0),d0`. The `d(An)` displacement is always 16-bit for simple indexed mode — there is NO threshold penalty at $7F (that only applies to `d(An,Xn)` indexed mode). So within a $50 SST, all field offsets cost the same number of cycles in `d(An)` mode. The only special case is offset $00.

**Gunstar's tri-state mode word at $02 is worth noting:** zero = free (testable with `tst.w`), positive = simple update, negative (bit 7 set) = full update + sprite chain. This enables three-way dispatch with `beq.s`/`bmi.s`/`bpl.s` — elegant. But it serves a different dispatch model than ours.

**Recommendation: ADOPT current plan with one refinement.** Keep `code_addr` (longword) at $00 for zero-offset dispatch. Keep positions at $02/$06 and velocities at $0A/$0C. The hot/cold ordering is not a hardware optimization (no cache) but a convention that clusters related fields for maintainability. The key structural benefit is that the most common field patterns (position check, velocity apply, collision test) access contiguous offset ranges, which makes code easier to audit and object headers self-documenting.

One refinement: consider making offset $00 a longword `code_addr` that doubles as slot-empty detection. `tst.l (a0)` tests both "is this slot occupied?" and "what routine does it run?" in one instruction. S.C.E. already does this — zero code_addr = empty slot. This is cleaner than a separate empty-flag field.

### Q2: SST Size — $40, $50, $60, $80?

**Our original plan:** $50 (80 bytes).

**What the research says:**

| Engine | SST Size | Rationale |
|--------|----------|-----------|
| S.C.E. | $50 | Expanded from S2's $40; `object_size_bits = 6` (uses shift for stride) |
| Batman & Robin | $5A | Exact-fit for their field set (not power-of-two) |
| Vectorman | 12 + variable | Dispatch header is tiny; data is heap-allocated |
| Gunstar Heroes | $60 (enemies), ~$E0 (players) | Fixed addresses for players, uniform $60 stride for enemies |
| Alien Soldier | $60 | Same as Gunstar |
| Thunder Force IV | $20/$40/$60 | Three different sizes for three pool types |
| sonic_hack | $50 | Expanded from S2's $40 |

The power-of-two question matters because it determines how you compute slot addresses from indices. With $40 or $80, you use a shift: `lsl.w #6, d0` or `lsl.w #7, d0`. With $50 or $60, you need `mulu` or a shift-add sequence:

- $50 = $40 + $10: `move.w d0,d1; lsl.w #6,d0; lsr.w #2,d1; lsl.w #4,d1; add.w d1,d0` — this is wrong, simpler: `lsl.w #4,d0; move.w d0,d1; lsl.w #2,d0; add.w d1,d0` (d0 * 16, d1 = d0 * 16, d0 = d0 * 64 + d0 * 16 = d0 * 80). 3 instructions.
- $60 = $40 + $20: `move.w d0,d1; lsl.w #6,d0; lsl.w #5,d1; add.w d1,d0`. 3 instructions.
- $40: `lsl.w #6,d0`. 1 instruction.
- $80: `lsl.w #7,d0`. 1 instruction.

However, with a free slot stack, index-to-address conversion almost never happens. The stack stores actual addresses, not indices. The only time you'd need the conversion is debug inspection or respawn table indexing. S.C.E. stores `object_size_bits = 6` but then uses `tst.l code_addr(a0); lea next_object(a0),a0` where `next_object = $50`. The stride constant is used for linear iteration, not index multiplication.

**Thunder Force IV's per-type sizing is the most RAM-efficient:** 32-byte projectiles, 64-byte main entities, 96-byte large enemies. Total ~5.7KB for 73 objects. But it requires separate pools, separate iteration loops, and separate allocation routines — significant code complexity.

**Recommendation: ADOPT $50.** The 80-byte SST is the sweet spot. It provides 34 bytes of free custom data ($2E-$4F), which is sufficient for even complex boss objects (Gunstar's player at ~224 bytes is a fixed-address singleton, not a pooled object). The non-power-of-two stride is irrelevant with a free slot stack — we never compute slot-from-index. For linear iteration (RunObjects), the stride is a constant `lea $50(a0),a0` — 12 cycles regardless of value. Going to $40 would sacrifice 16 bytes of custom data and constrain boss/player objects. Going to $60 wastes 16 bytes per slot across 55 objects = 880 bytes of RAM for no benefit. $50 is what S.C.E. and sonic_hack converged on independently.

### Q3: Object Dispatch — Function Pointer, Jump Table, Routine Counter?

**Our original plan:** Function pointer (longword) at offset $00.

**What the research says:**

Three dispatch families exist across the references:

**Function pointer (S.C.E., sonic_hack, Batman):**
```
; S.C.E.:
move.l  code_addr(a0), d0      ; 12 cycles
beq.s   .nextslot              ; 8/10 cycles (empty slot check)
movea.l d0, a1                 ; 4 cycles
jsr     (a1)                   ; 16 cycles = 40 cycles total
```
Pros: Objects can change their update routine to ANY address at any time. Maximum flexibility. Zero = empty slot.
Cons: 4-byte field, 40-cycle dispatch.

**Word-offset jump table (Gunstar, Alien Soldier):**
```
; Gunstar:
move.w  $04(a5), d0            ; 8 cycles
jmp     JumpTable(pc, d0.w)    ; 14 cycles = 22 cycles total
; Self-advancing: addq.w #4, $4(a5) at each routine end
```
Pros: 18 cycles faster per dispatch. Self-advancing routine counter automates linear state machines. 2-byte field.
Cons: All routines must be within one jump table (PC-relative). State transitions are linear by default — non-linear requires explicit writes to the routine counter.

**Alien Soldier's two-stage dispatch adds an early-out:**
```
; Stage 1: check activity flags at $02
tst.w   $02(a5)                ; 4 cycles
beq.s   .skip                  ; 8 cycles (inactive → skip entirely)
; Stage 2: dispatch via $04
move.w  $04(a5), d0
jmp     JumpTable(pc, d0.w)
```
This prevents inactive-but-allocated objects from costing full dispatch overhead. Relevant for boss parts that are "reserved" but not yet active.

**Gunstar's tri-state at $02 is the most cycle-efficient:**
```
tst.w   $02(a5)
beq.s   .free                  ; slot empty
bmi.s   .full_update           ; bit 15 set = needs sprite chain
; fall through = simple update (no sprite work)
```
Three outcomes from one `tst.w` — zero, negative, positive — each routes differently. 4+8=12 cycles to the common path.

**Recommendation: ADOPT function pointer at $00, with lessons from Treasure.** The function pointer approach is correct for our engine because:
1. Objects frequently change behavior non-linearly (monitors change when broken, badniks change when hurt, bosses have complex phase graphs).
2. Zero code_addr = empty slot eliminates a separate "is occupied" check.
3. Section-local entity management (Section 4.9) needs to set arbitrary routine pointers at spawn time from per-section type tables.

However, Treasure's self-advancing routine counter is worth providing as a utility pattern for objects that DO have linear state progressions. Objects can store a routine counter in their custom data area ($2E+) and use a helper macro:

```
; Objects wanting linear state progression:
AdvanceRoutine macro
    addq.w  #4, objoff_2E(a0)     ; advance to next state
    endm
```

This gives us both patterns without architectural compromise.

### Q4: Slot Allocation — Linear Scan, Free Stack, Pointer List, Heap?

**Our original plan:** Free slot stack with O(1) pop/push.

**What the research says:**

| Engine | Method | Complexity | Per-Slot Overhead |
|--------|--------|------------|-------------------|
| S.C.E. | Linear scan (`tst.l; dbeq`) | O(n) worst case | 0 bytes |
| Batman & Robin | Doubly-linked free list | O(1) amortized | 4 bytes (prev/next ptrs) |
| Vectorman | Heap allocator | O(n) (fragmentation) | Variable |
| Gunstar Heroes | Linear scan, Z-flag return | O(n) | 0 bytes |
| Alien Soldier | Sequential scan (`tst.w $02`) | O(n) | 0 bytes |
| Thunder Force IV | Per-frame free-list rebuild + O(1) pop | O(1) alloc, O(n) rebuild | 0 bytes per-slot, separate array |
| sonic_hack | Free slot stack | O(1) | 0 bytes per-slot, separate array |

Online research confirms: **no commercial Genesis game uses a free slot stack.** All use linear scan. The stack is a genuine algorithmic improvement. S.C.E.'s 90-slot scan worst-cases at `90 * (12+10) = 1,980 cycles` for a single failed allocation attempt. Our stack pop is `movea.w -(a1),a0` — 10 cycles regardless of pool size.

Thunder Force IV's approach is the most interesting comparison: it rebuilds a free pointer array every frame (O(n) scan once), then pops from the array for O(1) allocation. This is O(n) amortized per frame (always pays the scan cost) versus our O(1) amortized (scan never happens). Thunder Force pays ~880 cycles per frame for the rebuild (40 slots * 22 cycles). We pay zero.

Thunder Force IV also implements **spawn guards**: `cmpi.w #$8, $f208.w; bhi skip` prevents more than 8 objects spawning per frame. This is worth adopting regardless of allocation method — it prevents pathological pool exhaustion from spawn cascades.

Batman's doubly-linked free list achieves O(1) but costs 4 bytes per slot (prev/next pointers within the SST). That is 220 bytes of wasted SST space across 55 objects. Our separate stack array costs `55 * 2 = 110 bytes` of RAM outside the SST — less than half the cost, with no per-slot pollution.

**Recommendation: ADOPT free slot stack.** It is the fastest allocation method found in any reference, with the lowest overhead. Add Thunder Force IV's spawn guard as a safety mechanism: limit spawns-per-frame to prevent cascade exhaustion.

### Q5: Slot Counts and Pool Partitioning — How Many, Separate Pools?

**Our original plan:** 55 total — Slots 0-1 players, 2-41 dynamic (40 slots), 42-46 effects (5 slots), 47-54 system (8 slots).

**What the research says:**

| Engine | Total | Partitioning |
|--------|-------|--------------|
| S.C.E. | 109 | 3 fixed + 90 dynamic + 16 special-purpose |
| Batman & Robin | 140 | Flat pool with multi-slot atomic allocation |
| Gunstar Heroes | ~35+ | ~27 enemy pool + 4 mini-boss + player singletons at fixed addresses |
| Alien Soldier | 61+ | 61 main + separate bullet pool + 5 fixed boss slots |
| Thunder Force IV | 73 | 1 player + 20 main + 12 projectile + 40 large enemy |
| sonic_hack | 121 | 3-partition (player, level, dynamic) |

Thunder Force IV's per-type pools are the most granular. The key insight: **projectiles and effects are fundamentally different from gameplay entities.** They spawn in bursts, live briefly, and need minimal state. Giving them their own pool prevents a ring scatter or explosion cascade from starving the enemy pool.

Alien Soldier validates this with its separate bullet pool — bullets cannot displace enemies, enemies cannot displace bullets.

S.C.E.'s 90 dynamic slots seem excessive, but it serves a level streaming model where many objects exist simultaneously. Our section-local entity management (Section 4.9) means objects are per-section, reducing the simultaneous active count.

**Recommendation: ADAPT current plan, increase effects pool.** The 5-effect-slot allocation is too small — a single ring scatter creates up to 32 ring objects. Options:

1. **Dedicated ring scatter pool** (16 slots, 32 bytes each — rings need minimal state). Thunder Force IV validates per-type sizing.
2. **Expand effects pool to 16 slots** with a separate free stack. This handles ring scatters (capped at 16 visible scattered rings), explosions, score popups, and dust simultaneously.
3. **Keep 40 dynamic + 16 effect + 8 system = 64 dynamic slots + 2 players = 66 total.** At $50 per slot, that is $50 * 66 = 5,280 bytes = ~5.2KB for Object RAM. Comfortable within 64KB.

Slot ranges with separate free stacks per pool:
- Slots 0-1: Players (fixed, no allocation needed)
- Slots 2-41: Dynamic level objects (40 slots, own free stack)
- Slots 42-57: Effects/particles (16 slots, own free stack)
- Slots 58-65: System objects (8 slots — HUD, shields, title cards, fixed assignment)

### Q6: Particle/Effect Pool — Separate Lightweight Pool or Shared?

**Our original plan:** Effects in slots 42-46 (5 slots), shared SST size.

**What the research says:**

Thunder Force IV is the strongest reference here. Its projectile pool uses **32-byte structs** — half the size of main entities. Fields: position (8 bytes), velocity (4 bytes), SAT data (8 bytes), frame counter (2 bytes), type/misc (10 bytes). The SAT data is pre-formatted at VDP offsets — `Render_Projectile` is two `move.l` instructions.

Vectorman's heap allocator implicitly supports variable-size objects, but introduces fragmentation.

Alien Soldier's bullet pool is separate from the main pool but uses the same $60 stride. The pool boundary prevents bullets from consuming enemy slots.

**The separate-size-pool question (Thunder Force IV style) vs. shared-size-pool (Alien Soldier style):**

Separate sizes save RAM but require separate iteration loops, separate allocation routines, and separate struct definitions. Shared sizes waste RAM per lightweight object but unify all iteration and allocation code.

At 16 effect slots * $50 bytes = 1,280 bytes for shared-size effects. At 16 effect slots * $20 bytes = 512 bytes for half-size effects. Savings: 768 bytes. The 768-byte savings is significant (1.2% of total RAM) but comes at the cost of a second RunEffects loop, a second free stack, and a second SST struct.

**Recommendation: ADOPT shared SST size with separate pool.** Use the same $50 SST for effects but give them their own free stack (as recommended in Q5). The RAM cost is acceptable, and the code simplification is substantial:
- Effects use the same `Draw_Sprite`, `AnimateSprite`, and field offsets as all other objects.
- `RunObjects` iterates one contiguous SST range with one stride.
- Effects that need to be promoted to full gameplay objects (e.g., a scattered ring that becomes collectible) require zero migration — they already have all the fields.

The 768-byte savings from Thunder Force IV's approach is not worth the code duplication. Our section-local entity management already keeps active object counts low, reducing pressure on effect slots.

### Q7: Animation System — Timer-Based, Velocity-Linked, Self-Advancing Pointer?

**Our original plan:** Behavior sequencer with bytecode scripts, event codes ($F9-$F4), and animation-as-behavior.

**What the research says:**

Three distinct animation paradigms exist across the references:

**Timer-based countdown (S.C.E., Gunstar Heroes):**
Standard approach. Frame duration in animation data, countdown timer in SST. When timer hits zero, advance to next frame, reload timer. S.C.E. adds velocity-linked variants: `Animate_RawGetFaster` / `Animate_RawGetSlower`, and the character code computes `timer = max(1, top_speed - abs(inertia))` — higher speed = lower timer = faster animation.

**Self-advancing ROM pointer (Alien Soldier):**
The most elegant approach found. The ROM pointer at $48(a5) IS the animation state. After reading a `(frame_index, timer_value)` tuple, the routine writes the incremented pointer back: `move.l a0, $48(a5)`. No frame index bookkeeping, no "current frame" field, no table-base + offset calculation. The pointer walks forward through ROM data. Loop/branch control codes simply rewrite the pointer to a different ROM address.

Cost: 4 bytes in SST (pointer), ~20 cycles per frame advance. This is cheaper than timer-based (which needs pointer + index + timer = 6 bytes, ~30 cycles per advance).

**Threaded bytecode (Batman & Robin):**
Two-level system — animation scripts contain opcodes that reference sub-scripts. Plus a fractional animation accumulator for sub-frame precision (useful for smoothing at variable framerates, less relevant for our fixed-60fps target).

**SGDK's onFrameChange callback:**
When the animation frame advances, call a function pointer if non-null. This validates our "animation events as behavior sequencer" concept independently — a modern engine framework arrived at the same pattern.

**Velocity-linked animation (S3K via S.C.E.):**
`anim_frame_timer = top_speed - abs(inertia)`. Lower inertia = higher timer = slower animation. Higher inertia = lower timer = faster animation. Continuous, not discrete — no "walk vs. run" animation switch needed.

sonic_hack's variant: `($800 - |inertia|) >> 8` — same principle, different scale.

**Thunder Force IV's dual-use frame counter:**
The frame counter at +$10 drives BOTH animation (table lookup indexed by `counter & ~1`) AND object lifetime (destroy when counter reaches N). Eliminates a separate lifetime timer field. Novel and space-efficient, but couples animation rate to lifetime in ways that may be undesirable for objects with variable-duration animations.

**Recommendation: ADOPT behavior sequencer, ADAPT self-advancing pointer technique.**

Our bytecode animation format (Section 3.6 of ENGINE_ARCHITECTURE.md) is validated by all references — every engine uses some form of bytecode animation tables. Our event codes ($F9-$F4) are validated by SGDK's `onFrameChange` callback pattern.

Incorporate Alien Soldier's self-advancing pointer as the implementation mechanism. Instead of maintaining separate `anim_frame` and `anim_frame_duration` fields alongside a `mapping_frame` field, store a single ROM pointer (`anim_cursor`) that walks through the animation script. This:
- Eliminates `anim_frame` (1 byte saved)
- Eliminates `anim_frame_duration` (1 byte saved)  
- Makes event code processing trivial (the cursor naturally walks over event bytes)
- Simplifies loop/branch (just rewrite the cursor to the target address)

The `anim` field (current animation ID) is still needed for animation-change detection: `cmp.b anim(a0),d0; bne.s .restart_anim`.

Velocity-linked duration ($F5 event code) uses the S3K formula: `timer = max(1, top_speed - abs(inertia))`, validated by S.C.E.

### Q8: Hot/Cold Field Split — Worth It on Cacheless 68000?

**Our original plan:** Reorder SST fields by access frequency (hot fields first, cold fields last). Described as "NOVEL" in ENGINE_ARCHITECTURE.md.

**What the research says:**

**Online research is definitive: the 68000 has no data cache. There is zero hardware benefit to field ordering for sequential access optimization.** The "hot/cold split" terminology from modern CPU architecture does not apply. Every `move.w offset(a0),d0` costs the same number of cycles regardless of whether `offset` is $02 or $4E (both are 16-bit displacements in `d(An)` mode, both cost 12 cycles for .w).

The ONLY offset that matters is $00: `move.l (a0),d0` (zero-offset) saves 2 bytes + 4 cycles over `move.l $XX(a0),d0`. This is why `code_addr` belongs at $00 — it is accessed on EVERY dispatch.

**However,** field grouping still has software engineering value:
- Related fields (x_pos, y_pos, x_vel, y_vel) adjacent means routines that access all four can use `movem.l` for batch loads.
- Collision fields clustered means TouchResponse accesses sequential offsets, improving code locality (easier to read, not faster to execute).
- Custom data at the end ($2E-$4F) means overlays for different object types don't collide with engine fields.

**Vectorman's approach is the one genuine hot/cold split found:** A 12-byte dispatch entry (code pointer, flags, status) paired with a variable-size heap block for object-specific data. This is a true architectural split — the dispatch loop only touches the 12-byte entries, and objects that don't need much data get tiny heap blocks. But the heap allocator adds complexity and fragmentation risk.

**Recommendation: REJECT the "hot/cold" framing, ADOPT the field layout for software engineering reasons.** Stop calling it a "hot/cold split" — that implies a cache benefit that doesn't exist. Instead, call it "logical field grouping": dispatch at $00, physics at $02-$0D, render/collision at $0E-$1F, links at $20-$23, engine at $24-$2D, custom at $2E-$4F. The layout is good; the rationale needs correcting.

Update ENGINE_ARCHITECTURE.md Section 3.1 to remove "NOVEL" tag and reframe the ordering as a code-maintenance and `movem` optimization, not a cache optimization.

### Q9: Execution Tiers / Selective Update — How to Skip Offscreen Objects?

**Our original plan:** 4-tier execution (Reserved/Dynamic/LevelOnly/Deferred) mentioned in Section 3.8.

**What the research says:**

**S.C.E. freeze tier:** On player death, dynamic objects get render-only processing (Draw_Sprite only, no logic). Simple and effective — one flag check at the top of RunObjects gates all object logic.

**Alien Soldier's two-stage dispatch:** `tst.w $02(a5)` as a fast first check. Inactive objects (allocated but not running — e.g., pre-spawned boss parts) cost only 12 cycles per frame instead of full dispatch overhead. This is valuable for boss fights where parts are pre-allocated but activate sequentially.

**Tanglewood's world grid culling:** Objects only enter the update linked list while within viewport-adjacent grid cells. Zero CPU cost for offscreen objects. This is the most aggressive culling but requires a spatial data structure that our section-local entity management already provides at the macro level — objects only exist in active sections.

**Thunder Force IV's projectile pool has NO dispatch:** The 12 projectile slots are processed by a single hard-coded physics loop, not by per-object dispatch. This eliminates dispatch overhead (22 cycles * 12 = 264 cycles saved per frame) for objects with uniform behavior.

**Key insight from all references:** Offscreen culling at the individual-object level is rarely done. Most engines load/unload objects at the section/zone level and run ALL loaded objects every frame. The exceptions are:
1. S.C.E.'s render-only freeze tier (applies to ALL objects, not per-object)
2. Tanglewood's spatial grid (most aggressive but requires spatial indexing)
3. Section-local management (our approach — objects only exist in loaded sections)

**Recommendation: ADAPT to three tiers with section-local management as the primary culling mechanism.**

1. **Always-run** (players, HUD, shields, system objects) — slots 0-1 and 58-65. Run every frame regardless of game state.
2. **Section-active** (level objects, enemies, platforms) — slots 2-41. Only exist while their section is in one of the 4 layout slots. Section unload = bulk delete. This IS the offscreen culling — objects that aren't in an active section simply don't exist in RAM.
3. **Freeze-capable** (all dynamic objects) — on player death or pause, skip logic, run Draw_Sprite only. One flag check at RunObjects top.

Individual offscreen checks (per-object `is this on screen?`) are unnecessary given section-local management. A 2048x2048 section is at most ~3 screens wide — everything in the section is "near screen." The only per-object screen check needed is in Draw_Sprite (don't render objects outside the viewport), which is already standard.

### Q10: Deletion Strategy — Immediate, Deferred Mark-and-Sweep, or Hybrid?

**Our original plan:** TBD — research was supposed to decide.

**What the research says:**

| Engine | Strategy | Implementation | Motivation |
|--------|----------|----------------|------------|
| S.C.E. | Immediate | Zero code_addr; `respawn_addr` bookkeeping first | Simple, sufficient |
| Batman & Robin | Immediate (SP restore) | Object restores SP to main-loop frame, exiting mid-update | Avoids running remaining code after deletion |
| Vectorman | Kill-flag-then-free | Set flag, freed during next allocation pass | Heap allocator needs safe-point freeing |
| Gunstar Heroes | Immediate | `clr.w $2(a5)` clears mode word; display list rebuilt each frame, cleared objects fall out | Display list is rebuilt anyway |
| Alien Soldier | Mark-and-sweep | `bset.b #$4, $2(a5)` marks; sweep at $1CA16 cleans up end-of-frame | 80+ call sites use bset; prevents mid-iteration mutation of active list |
| Thunder Force IV | Immediate | `clr.w (a6)`; slot available after next free-list rebuild | Free-list rebuild handles bookkeeping |
| sonic_hack | Deferred mark+sweep | Custom implementation | Unclear original motivation |

**Alien Soldier's mark-and-sweep exists to solve a specific problem:** its active list at $ed00 is a flat array of object pointers. Removing an entry mid-iteration would corrupt the iteration. Marking for deletion and sweeping after iteration is complete avoids this. Our architecture doesn't have this problem — RunObjects iterates SST slots by stride, not by pointer list. A deleted slot (zero code_addr) is simply skipped on the next iteration.

**Batman & Robin's SP restore is clever but risky:** `move.l (sp)+,a0; jmp (a0)` — restoring a saved return address to jump back to RunObjects. If the stack is in an unexpected state, this corrupts execution. It saves cycles (avoids running the rest of a deleted object's update) but adds a fragile implicit contract between deletion and the main loop.

**S.C.E.'s approach is the cleanest and most compatible with our free slot stack:** zero code_addr = slot is empty. RunObjects checks `tst.l (a0); beq.s .skip` and skips empty slots. DeleteObject pushes the slot address back to the free stack, then zeros the SST. No deferred phase, no mark bits, no sweep pass.

The only concern with immediate deletion is parent-child cascades: deleting a parent while iterating children could cause issues if children are processed after the parent in the same frame. S.C.E. handles this by having children check `tst.l code_addr(parent)` — if parent is zero, child self-deletes. This works because the parent is fully zeroed (including code_addr) immediately, so the child's check is reliable.

**Recommendation: ADOPT immediate deletion.**

```
DeleteObject:
    move.w  a0, (Free_Stack_SP)+    ; push slot address back (10 cycles)
    ; Zero all $50 bytes (movem.l with 12 regs + moveq = ~100 cycles)
    movem.l d0-d7/a1-a4, -(sp)     ; save
    moveq   #0, d0
    ; ... bulk zero via movem ...
    movem.l (sp)+, d0-d7/a1-a4     ; restore
    rts
```

Actually, the zeroing can be done more efficiently. Pre-load registers with zero and use `movem.l` to write:

```
; Assuming d0-d6 and a1-a4 are zero (11 registers * 4 bytes = 44 bytes)
; Two movem.l writes: 44 + 36 = 80 bytes, with final 0 bytes = $50 total
```

The exact clearing sequence will be finalized during implementation. The key architectural decision is: immediate deletion, free stack push, and full slot zeroing. No marks, no sweep, no deferred phase.

### Q11: Object Communication — Parent/Child Links, Trigger Arrays, Global State Words?

**Our original plan:** Three mechanisms — parent/child links (Treasure), level trigger array (S.C.E.), boss event buffer.

**What the research says:**

**Parent-child links (Treasure, validated at scale):**
Gunstar Heroes: one link field at $58 with 71 references. Alien Soldier: two link fields ($58 + $5C) with 484 total references. The second link field enables both parent and sibling tracking simultaneously. Alien Soldier uses stride arithmetic (`addi.l #$60, $58(a5)`) to walk consecutive boss parts without pointer indirection.

S.C.E. has 12 child creation strategies spanning the full range of parent-child patterns: simple spawn, complex multi-field init, repeated spawns, doubly-linked sibling chains, flip-aware mirroring, and tree lists.

**Gunstar Heroes' adjacent-slot child technique:** `lea $60(a5), a0` — the child is statically positioned one stride ahead. No allocation needed. This only works with predictable multi-part objects (boss with known part count) but eliminates allocation overhead entirely.

**Level trigger array (S.C.E.):** `Level_trigger_array` at $FFD822, 16 bytes. Flat boolean array indexed by subtype. Button objects write, platform/door objects poll. Simple, fast (one byte read), fully decoupled.

**Global state word (Thunder Force IV):** `$f308.w` — 0 = normal, 3 = boss dead. All objects can read this to coordinate level-wide behavior changes. Minimal, effective for simple global state.

**Vectorman's callbacks:** Register function pointers for inter-object communication rather than polling. More elegant but adds 4 bytes per callback pointer.

**Recommendation: ADOPT all three mechanisms from our original plan, with Alien Soldier's dual link field.**

1. **Parent/child links:** `parent_ptr` ($20) and `sibling_ptr` ($22). Use Alien Soldier's dual-link approach rather than S.C.E.'s single-child-pointer chain. Parent_ptr points to the creating object. Sibling_ptr links to the next child of the same parent, forming a singly-linked sibling ring. This enables:
   - Parent death cascade: walk sibling_ptr from first child, delete all.
   - Sibling communication: boss arms can read each other's state.
   - No tree traversal needed — parent reads child via stored pointer, children read parent via parent_ptr.

2. **Level trigger array:** 16 bytes, indexed by trigger ID from object subtype. Identical to S.C.E. implementation. Covers all button/switch/door/platform interactions.

3. **Boss event buffer:** 32 bytes of shared state at a fixed RAM address. Boss phase, attack pattern index, health threshold flags, defeat conditions. All boss parts read/write this buffer. More structured than Thunder Force IV's single word, covers the same use case.

4. **Global game state word** (from Thunder Force IV): Add a single word `Game_State_Flags` for level-wide state (boss defeated, water rising, section collapsing). Objects check this for global behavior changes. Cheaper than a full event system, sufficient for known use cases.

---

## 4. Novel Techniques Catalog

### 4.1 Allocation and Memory

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| Free slot stack | sonic_hack / our design | O(1) allocate/free via word-addressed stack | **Core architecture** — primary allocation method |
| Adjacent-slot children | Gunstar Heroes | `lea $60(a5),a0` — child at known offset, no alloc | Useful for fixed-layout multi-part objects (bosses with known part count) |
| Multi-slot atomic allocation | Batman & Robin | Allocate N contiguous slots in one operation | Unnecessary with our free stack — allocate N slots individually |
| Per-frame free-list rebuild | Thunder Force IV | Scan once, allocate many | Superseded by free stack |
| Spawn guard | Thunder Force IV | `cmp.w #MAX, spawn_count; bhi skip` | **Adopt** — prevents cascade exhaustion |

### 4.2 Dispatch and Execution

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| Tri-state mode word | Gunstar Heroes | `tst.w $02` → beq/bmi/bpl for three-way dispatch | Elegant but serves jump-table model, not function-pointer model |
| Two-stage dispatch | Alien Soldier | Activity-flag check before full dispatch | **Adopt** for pre-allocated boss parts: check code_addr, skip if zero |
| Self-advancing routine counter | Gunstar/Alien Soldier | `addq.w #4, $4(a5)` at each routine end | **Provide as utility** — objects with linear state progression use it voluntarily |
| No-dispatch projectile loop | Thunder Force IV | Hard-coded physics for all projectiles, no dispatch | **Consider** for ring scatter — uniform behavior, no per-object dispatch needed |
| Update/render split | Vectorman | Separate passes for logic and drawing | Already in our architecture (RunObjects + Render_Sprites) |

### 4.3 Animation

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| Self-advancing ROM pointer | Alien Soldier | ROM pointer IS animation state; reads and increments | **Adopt** as AnimateSprite implementation |
| Fractional animation accumulator | Batman & Robin | Sub-frame animation precision | Unnecessary at fixed 60fps |
| Velocity-linked timer | S.C.E. / S3K | `timer = max(1, top_speed - abs(inertia))` | **Adopt** as $F5 event code |
| Dual-use frame counter | Thunder Force IV | Counter drives animation AND lifetime | **Consider** for short-lived effects (explosions, score popups) |
| onFrameChange callback | SGDK | Call function pointer when animation frame changes | **Already planned** as animation event system |

### 4.4 Rendering

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| Priority-as-bucket-offset | S.C.E. | 8 priority levels via separate pointer buffers | **Adopt** — already in architecture (Section 3.5) |
| Pre-formatted SAT entries | Thunder Force IV | Struct stores sprite data at exact VDP offsets; 2x move.l to copy | **Adopt for effects/particles** — pre-format during spawn, blast-copy during render |
| Multi-sprite per slot | Thunder Force IV | One pool slot drives 3 SAT entries (linked list within slot) | **Adopt for multi-piece objects** — compound sprite rendering |
| Priority cycling | Thunder Force IV | Frame counter indexes priority table; all sprites get screen time | **Already in architecture** as link-order cycling |
| Sprite X=0 masking | Alien Soldier / Galaxy Force II | Hardware stops link scan at X=0 | **Already in architecture** (Section 3.5) |

### 4.5 Communication

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| Dual link fields | Alien Soldier | $58 parent + $5C sibling | **Adopt** as parent_ptr + sibling_ptr |
| Stride arithmetic | Alien Soldier | `addi.l #$60, $58(a5)` walks consecutive parts | **Adopt** for fixed-layout boss parts |
| Trigger array | S.C.E. | 16-byte boolean array, button writes / door reads | **Already in architecture** (Section 9.2) |
| Global state word | Thunder Force IV | Single word for level-wide state | **Adopt** as Game_State_Flags |
| Hit communication | Gunstar Heroes | Bidirectional: attacker stores target ptr, target stores attacker ptr | **Adopt** — collision response stores attacker address for knockback direction |
| Callback registration | Vectorman | Objects register function pointers for communication | Overhead not justified at 7.67 MHz |

### 4.6 Deletion and Lifecycle

| Technique | Source | Description | Applicability |
|-----------|--------|-------------|---------------|
| SP restore deletion | Batman & Robin | Restore SP to exit mid-update | Fragile, implicit contract — **reject** |
| Mark-and-sweep | Alien Soldier | bset mark bit, sweep at end-of-frame | Solves pointer-list iteration problem we don't have — **reject** |
| Respawn bookkeeping | S.C.E. | Clear respawn-table bit before zeroing code_addr | **Adopt** — respawn_index field supports this |
| Reserved/transitioning state | Gunstar Heroes | `move.w #$1000, $2(a0)` prevents double-allocation | **Adopt** for boss pre-allocation: non-zero code_addr prevents stack-pop allocation |

### 4.7 68000 Optimization Tricks

| Technique | Source | Cycles Saved | Description |
|-----------|--------|--------------|-------------|
| SWAP as free register | Gunstar Heroes | 12 cycles/use | `swap d2` stashes loop counter in upper word; 4 cycles vs 16 for push/pop |
| SWAP 16.16 fixed-point | Gunstar Heroes | ~10 cycles/op | `add.l d0,d1; swap d0; swap d1; sub.w d0,d1` — integer pixel delta without divide |
| Pre-built VDP command blocks | Gunstar/Alien Soldier | VBlank savings | 112 entries at $f000, built during main loop, blind replay in VBlank |
| Terminator-based iteration | Vectorman | ~4 cycles/iter | `tst.w (a0)+; bmi.s .done` vs dbf counter management |
| `moveq` bulk zero + movem write | All | ~60 cycles | `moveq #0,d0-d7; movem.l d0-d7,$00(a0)` clears 32 bytes in 2 instructions |
| Unrolled 32-iteration walker | Batman & Robin | Branch overhead | Inner loop unrolled 32x for active-list traversal |

---

## 5. Validated Design Decisions

### Summary Verdicts

| Decision | Original Plan | Verdict | Rationale |
|----------|---------------|---------|-----------|
| SST at $50 | $50 (80 bytes) | **ADOPT** | Sweet spot. S.C.E. and sonic_hack converged here independently. 34 bytes custom data sufficient for all object types. Non-power-of-two irrelevant with free stack. |
| code_addr at $00 | Longword at $00 | **ADOPT** | Universal across all function-pointer engines. 2 bytes + 4 cycles saved per dispatch. Zero = empty slot. |
| Hot/cold field ordering | Reorder by access frequency | **ADAPT** | Rename to "logical field grouping." No cache benefit exists. Keep layout for code-maintenance and movem optimization. Remove "NOVEL" tag. |
| Free slot stack | O(1) push/pop | **ADOPT** | Fastest allocation in any reference. No counter-evidence. Add TF4 spawn guard. |
| Slot count / pools | 55 total (40 dynamic + 5 effect + 8 system + 2 player) | **ADAPT** | Increase effects to 16 slots. Total: 66 (2 player + 40 dynamic + 16 effect + 8 system). Separate free stacks per pool. |
| Function pointer dispatch | Longword fn ptr | **ADOPT** | Correct for our object model. Provide Treasure-style routine counter as opt-in utility. |
| Immediate deletion | TBD | **ADOPT** | 5 of 7 references use immediate. Mark-and-sweep solves a problem we don't have. Pairs naturally with free stack push. |
| Animation sequencer | Bytecode with event codes | **ADOPT** | Validated by SGDK onFrameChange, enhanced by Alien Soldier self-advancing pointer. |
| Parent/child links | parent_ptr + child_ptr | **ADAPT** | Rename child_ptr to sibling_ptr. Adopt Alien Soldier dual-link model for parent + sibling ring. |
| Trigger array | 16-byte flag array | **ADOPT** | Identical to S.C.E. Proven simple, fast, decoupled. |
| Boss event buffer | 32 bytes shared state | **ADOPT** | No counter-evidence. Add TF4-style global state word alongside. |
| Collision type dispatch | Type byte + direct dimensions | **ADOPT** | No reference uses this exact approach — genuinely novel and more modular. |
| Priority-band rendering | 8-level bucket sort | **ADOPT** | S.C.E. proves it works at scale. Zero-cost ordering. |

### Required ENGINE_ARCHITECTURE.md Updates

Based on this research, the following changes should be made to Section 3 of ENGINE_ARCHITECTURE.md:

1. **Section 3.1:** Remove "NOVEL" from the hot/cold reordering claim. Reframe as "logical field grouping for code maintenance and movem optimization." The 68000 has no data cache; there is no hardware-level hot/cold benefit.

2. **Section 3.1:** Rename `child_ptr` to `sibling_ptr`. Adopt Alien Soldier's dual-link model: `parent_ptr` points up to the creating object, `sibling_ptr` links laterally to the next child of the same parent.

3. **Section 3.1 slot ranges:** Increase effect pool from 5 to 16 slots. Update total from 55 to 66. Document separate free stacks per pool.

4. **Section 3.2:** Add Thunder Force IV spawn guard: `cmp.w #MAX_SPAWNS_PER_FRAME, Spawn_Count; bhi.s .reject`.

5. **Section 3.6:** Document self-advancing ROM pointer as the AnimateSprite implementation mechanism (from Alien Soldier). Replace `anim_frame` + `anim_frame_duration` with `anim_cursor` (longword ROM pointer).

6. **Section 3.8:** Document Gunstar Heroes' bidirectional hit communication ($40/$42 attacker/target pointers) as the TouchResponse output mechanism.

7. **Section 9.2:** Add Game_State_Flags word (from Thunder Force IV) alongside the trigger array and boss event buffer.

8. **New subsection:** Add Alien Soldier's "reserved/transitioning" state pattern: objects can be pre-allocated with a non-zero code_addr that points to a no-op or minimal routine, preventing the free stack from re-issuing that slot.

---

## Appendix A: Cycle Cost Comparison — Allocation Methods

| Method | Best Case | Worst Case | Average (50% full) | Per-Slot Overhead |
|--------|-----------|------------|---------------------|-------------------|
| Free slot stack (ours) | 10 cycles | 10 cycles | 10 cycles | 0 (2 bytes in separate array) |
| Linear scan (S.C.E.) | 22 cycles (first slot free) | 1,980 cycles (90 slots, last free) | ~990 cycles | 0 bytes |
| Linear scan (Gunstar) | 22 cycles | 594 cycles (27 slots) | ~297 cycles | 0 bytes |
| Doubly-linked list (Batman) | 24 cycles | 24 cycles | 24 cycles | 4 bytes per slot |
| Per-frame rebuild + pop (TF4) | 10 cycles (pop) | 10 cycles (pop) | 10 cycles (pop) + 880 cycles/frame (rebuild) | 0 per-slot, 80-byte array |

## Appendix B: SST Size vs. RAM Cost

| SST Size | 40 Dynamic | 16 Effect | 8 System | 2 Player | Total Slots | Total RAM |
|----------|------------|-----------|----------|----------|-------------|-----------|
| $40 (64B) | 2,560 | 1,024 | 512 | 128 | 66 | 4,224 |
| $50 (80B) | 3,200 | 1,280 | 640 | 160 | 66 | 5,280 |
| $60 (96B) | 3,840 | 1,536 | 768 | 192 | 66 | 6,336 |
| $80 (128B) | 5,120 | 2,048 | 1,024 | 256 | 66 | 8,448 |
| TF4 mixed ($20/$40/$60) | 2,560 ($40) | 512 ($20) | 512 ($40) | 96 ($60) | 73 | 3,680 |

$50 at 66 slots = 5,280 bytes = 8.1% of 64KB RAM. Acceptable. Free stack arrays add 2 * (40+16) = 112 bytes. Grand total: 5,392 bytes.

## Appendix C: Dispatch Cost Comparison

| Method | Per-Object Cost | 66-Object Frame Cost | Notes |
|--------|----------------|----------------------|-------|
| Function pointer (S.C.E.) | 40 cycles | 2,640 cycles | Flexible, zero = empty |
| Jump table (Gunstar) | 22 cycles | 1,452 cycles | Requires single table |
| Two-stage (Alien Soldier) | 12 cycles (inactive) / 26 cycles (active) | ~1,200 cycles (30 active) | Best for mixed active/inactive |
| No dispatch (TF4 projectiles) | 0 cycles | 0 cycles | Only for uniform-behavior pools |

Our 66-slot RunObjects with function pointer dispatch: ~2,640 cycles worst case (all slots full). This is 2.2% of the ~120,000 cycle NTSC frame budget. Acceptable. The empty-slot fast path (`tst.l (a0); beq.s .next; ... lea $50(a0),a0`) costs only ~24 cycles per empty slot, so a half-full pool costs ~1,500 cycles for iteration.
