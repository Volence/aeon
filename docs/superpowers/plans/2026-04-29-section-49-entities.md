# §4.9 Section-Local Entity Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make objects and rings appear in levels by tying entity spawning/despawning to the section streaming lifecycle.

**Architecture:** Pattern-encoded ring layouts expand into per-slot ring buffers at section load. Object layouts reference per-section type tables that map local indices to ObjDef pointers. Both systems hook into section streaming at four lifecycle points (init, preload, teleport, deferred cold-load). A shared AABB overlap macro provides collision math for both TouchResponse and RingCollision.

**Tech Stack:** 68000 assembly (AS Macro Assembler), existing section streaming engine (section.asm), object system (core.asm, load_object.asm, collision.asm)

**Spec:** `docs/superpowers/specs/2026-04-29-section-local-entities-design.md`
**Branch:** `feat/section-49-entities`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `engine/objects/aabb.inc` | Create | Shared AABB overlap macro (included by collision.asm and rings.asm) |
| `engine/objects/collision.asm` | Modify | Replace inline AABB math with `aabb_overlap` macro include |
| `engine/objects/rings.asm` | Create | ExpandRings, DrawRings, RingCollision, CollectRing |
| `engine/objects/entity_loader.asm` | Create | SpawnSectionObjects, DespawnSlotObjects, LoadTypeTable |
| `engine/level/section.asm` | Modify | Add entity lifecycle hooks at 4 streaming integration points |
| `ram.asm` | Modify | Add ring buffers, bitmasks, counts, type table, ring counter, anim frame |
| `constants.asm` | Modify | Add entity system constants (MAX_RINGS_PER_SLOT, RING_SIZE, SLOT_TAG_OFFSET, etc.) |
| `structs.asm` | Modify | (No struct changes needed — Sec struct already has sec_objects, sec_rings) |
| `main.asm` | Modify | Add includes for new engine files |
| `data/levels/ojz/act1/act_descriptor.asm` | Modify | Wire Sec0/Sec1 ring/object data pointers |
| `data/levels/ojz/act1/entity_data.asm` | Create | Test ring patterns + object placements + type tables for Sec0/Sec1 |
| `test/ojz_scroll_test.asm` | Modify | Add RingCollision + DrawRings calls, spawn TestPlayer via entity system |

---

### Task 1: RAM Allocations + Constants

**Files:**
- Modify: `ram.asm:279` (before `Current_Act_Ptr`)
- Modify: `constants.asm:297` (at end)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for ring buffer RAM layouts, bitmask strategies, and entity system RAM allocation patterns:
- **S.C.E.** (`/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`): Search for ring buffer, ring count, ring status variables in RAM layout
- **sonic_hack** (`/home/volence/sonic_hacks/sonic_hack/`): Look at `Ring_Positions`, `Ring_Consumption_Table`, ring counter variables
- **Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar**: Search for object pool RAM patterns, entity status bitmasks
- **Online**: plutiedev.com for RAM layout best practices, md.railgun.works for alignment requirements
- **Modern**: Consider cache-line-friendly grouping for 68000 word/longword access patterns

Report findings before proceeding.

- [ ] **Step 2: Add entity system constants to constants.asm**

Add after the `VRAM_TEST_SONIC` constant at the end of `constants.asm`:

```asm
; -----------------------------------------------
; Entity System (§4.9)
; -----------------------------------------------
MAX_RINGS_PER_SLOT      = 128           ; ring buffer capacity per slot
RING_BITMASK_SIZE       = MAX_RINGS_PER_SLOT/8  ; 16 bytes per slot
RING_BUFFER_ENTRY_SIZE  = 4             ; dc.w x, y per ring
RING_BUFFER_SIZE        = MAX_RINGS_PER_SLOT*RING_BUFFER_ENTRY_SIZE  ; 512 bytes
RING_WIDTH              = 16            ; collision AABB (pixels)
RING_HEIGHT             = 16
RING_ANIM_FRAMES        = 4             ; global ring animation frame count
RING_ANIM_SPEED         = 8             ; frames per animation tick

MAX_OBJECT_TYPES        = 32            ; per-section type table capacity
TYPE_TABLE_SIZE         = MAX_OBJECT_TYPES*4  ; 128 bytes (longword pointers)

SLOT_TAG_OFFSET         = SST_sst_custom+$1D  ; last byte of custom area
SLOT_TAG_UNTAGGED       = $FF           ; player, system objects, effects
SLOT_TAG_LEFT           = 0             ; slot 0 entities
SLOT_TAG_RIGHT          = 1             ; slot 1 entities

; Ring pattern encoding (ROM format)
RING_TYPE_MASK          = $C0000000     ; bits 31-30
RING_TYPE_INDIVIDUAL    = $00000000     ; %00
RING_TYPE_HLINE         = $40000000     ; %01
RING_TYPE_VLINE         = $80000000     ; %10
RING_X_MASK             = $3FF00000     ; bits 29-20
RING_X_SHIFT            = 20
RING_Y_MASK             = $000FFC00     ; bits 19-10
RING_Y_SHIFT            = 10
RING_COUNT_MASK         = $000003E0     ; bits 9-5
RING_COUNT_SHIFT        = 5
RING_SPACING_MASK       = $0000001C     ; bits 4-2
RING_SPACING_SHIFT      = 2

; Object layout encoding (ROM format)
OBJ_ENTRY_X_SHIFT       = 20
OBJ_ENTRY_Y_SHIFT       = 10
OBJ_ENTRY_TYPE_MASK     = $000003E0     ; bits 9-5
OBJ_ENTRY_TYPE_SHIFT    = 5
OBJ_ENTRY_SUBTYPE_MASK  = $0000001F     ; bits 4-0
```

- [ ] **Step 3: Add entity RAM variables to ram.asm**

Add before `Current_Act_Ptr` in `ram.asm` (after `Tile_Override_Table`):

```asm
; -----------------------------------------------
; Entity System (§4.9)
; -----------------------------------------------

; Ring buffers — 128 entries × 4 bytes (dc.w x, y) per slot
Ring_Buffer_0:          ds.b RING_BUFFER_SIZE   ; 512 bytes, slot 0
Ring_Buffer_1:          ds.b RING_BUFFER_SIZE   ; 512 bytes, slot 1

; Ring bitmasks — 128 bits per slot (1 = collected)
Ring_Bitmask_0:         ds.b RING_BITMASK_SIZE  ; 16 bytes
Ring_Bitmask_1:         ds.b RING_BITMASK_SIZE  ; 16 bytes

; Ring counts — expanded ring count per slot
Ring_Count_0:           ds.b 1
Ring_Count_1:           ds.b 1

; Object type table — RAM copy of active section's type map
Object_Type_Table:      ds.b TYPE_TABLE_SIZE    ; 128 bytes (32 × 4)

; Ring state
Ring_Counter:           ds.w 1          ; total collected rings (player HUD)
Ring_Anim_Frame:        ds.b 1          ; global ring animation counter (0-3)
Ring_Anim_Timer:        ds.b 1          ; countdown to next frame
```

- [ ] **Step 4: Build to verify RAM doesn't overflow into stack**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds. The `if RAM_End >= SYSTEM_STACK` assertion at the end of `ram.asm` catches overflow.

- [ ] **Step 5: Commit**

```bash
git add constants.asm ram.asm
git commit -m "feat(§4.9): add entity system RAM layout + constants

Ring buffers (2×512B), bitmasks (2×16B), type table (128B),
ring counter and animation state for section-local entities.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Shared AABB Overlap Macro

**Files:**
- Create: `engine/objects/aabb.inc`
- Modify: `engine/objects/collision.asm:41-79`
- Modify: `main.asm` (no change needed — aabb.inc is included via `include` in collision.asm and rings.asm, not in main.asm)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for AABB overlap implementations:
- **S.C.E.**: Look for `Touch_*` routines, collision response dispatch
- **sonic_hack**: Look at `TouchResponse` in `code/objects/Object_Specific_Routines/` — the original S2 collision code
- **Gunstar Heroes**: Known for complex multi-hitbox collision — look for optimization tricks
- **Alien Soldier**: Extreme 68000 optimization — any novel AABB patterns?
- **Vectorman, Batman & Robin**: Check for early-out strategies
- **Thunder Force IV, Ristar**: Standard platformer collision
- **Online**: SpritesMind forum threads on collision optimization, plutiedev collision notes
- **Modern**: Consider SIMD-style batching (test multiple objects with same registers), early-exit ordering for cache-miss reduction

Report findings before proceeding.

- [ ] **Step 2: Create engine/objects/aabb.inc**

```asm
; aabb_overlap — inline AABB overlap test (assembler macro)
;
; Tests whether two axis-aligned bounding boxes overlap.
; Parameterized by register names so callers use their own allocation.
; Branches to \miss label on no overlap; falls through on hit.
;
; On overlap:
;   \dx = signed delta_x (a.x - b.x), available in caller's register
;   \dy = signed delta_y (a.y - b.y), available in caller's register
;   \cw = combined width  (a.width + b.width)
;   \ch = combined height (a.height + b.height)
;
; Optimized for 68000: early-out on X before computing Y,
; all register operations (no memory access), branch ordering
; for the common case (miss).
;
; Parameters:
;   ax, ay    — X/Y position of object A (word registers, read-only)
;   bx, by    — X/Y position of object B (word registers, read-only)
;   aw, ah    — width/height of A (byte-extended word registers)
;   bw, bh    — width/height of B (byte-extended word registers)
;   cw        — scratch: receives combined_w on overlap
;   ch        — scratch: receives combined_h on overlap
;   dx        — scratch: receives signed delta_x on overlap
;   dy        — scratch: receives signed delta_y on overlap
;   tmp       — scratch register (clobbered)
;   miss      — label to branch to on no overlap

aabb_overlap macro ax,ay,bx,by,aw,bw,ah,bh,cw,ch,dx,dy,tmp,miss
        ; --- X axis ---
        move.w  \aw, \cw
        add.w   \bw, \cw                       ; cw = combined width

        move.w  \ax, \dx
        sub.w   \bx, \dx                       ; dx = signed delta_x

        move.w  \dx, \tmp
        bpl.s   .xpos\@
        neg.w   \tmp
.xpos\@:
        add.w   \tmp, \tmp                     ; abs(dx) * 2
        cmp.w   \cw, \tmp
        bhs.s   \miss                          ; no X overlap

        ; --- Y axis ---
        move.w  \ah, \ch
        add.w   \bh, \ch                       ; ch = combined height

        move.w  \ay, \dy
        sub.w   \by, \dy                       ; dy = signed delta_y

        move.w  \dy, \tmp
        bpl.s   .ypos\@
        neg.w   \tmp
.ypos\@:
        add.w   \tmp, \tmp                     ; abs(dy) * 2
        cmp.w   \ch, \tmp
        bhs.s   \miss                          ; no Y overlap
        ; Falls through: overlap confirmed
        endm
```

- [ ] **Step 3: Refactor TouchResponse to use the AABB macro**

In `engine/objects/collision.asm`, add the include at the top (after the header comment, before `TouchResponse:`):

```asm
    include "engine/objects/aabb.inc"
```

Then replace lines 42–79 (the inline X/Y axis overlap code) with the macro invocation. The existing code stashes X results in address registers (a0/a1) to free data registers for Y — the macro handles this differently by using its own register allocation. The refactored `.object_loop` body becomes:

Replace the block from `;--- X axis overlap ---` through `bhs.s   .next_object` (second occurrence, the Y miss) with:

```asm
        ; --- AABB overlap via shared macro ---
        ; Set up width/height registers
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0        ; player width
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1        ; target width
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2       ; player height
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3       ; target height

        ; d4 = player X (cached), d5 = player Y (cached)
        ; SST_x_pos(a3) = target X, SST_y_pos(a3) = target Y
        ; Macro needs target positions in registers
        movea.w SST_x_pos(a3), a0               ; stash target X in a0
        movea.w SST_y_pos(a3), a1               ; stash target Y in a1

        aabb_overlap d4,d5,a0,a1,d0,d1,d2,d3,d0,d2,d1,d3,d0,.next_object
```

Wait — the macro parameters don't work like that because `ax` is read before `cw` overwrites it. Let me restructure. The existing TouchResponse code is carefully optimized with specific register allocation. The macro needs to match. Let me redesign:

Actually, the issue is that the macro needs separate source and scratch registers. The existing collision.asm code uses a very specific register trick (stashing combined_w/dx into address registers a0/a1 to free d0/d1 for the Y test). The macro should be designed so callers can use it naturally.

Revised approach: the macro is simpler — it just tests and branches. Caller sets up positions and dimensions in registers, macro does the overlap math. For TouchResponse, we keep the existing register caching pattern (d4=playerX, d5=playerY cached across the loop) and pass them to the macro.

Let me redesign the macro to work cleanly with TouchResponse's register allocation:

```asm
; aabb_overlap — inline AABB overlap test
; Tests: abs(ax - bx) * 2 < (aw + bw) AND abs(ay - by) * 2 < (ah + bh)
; Falls through on overlap, branches to \miss on no overlap.
;
; IMPORTANT: \cw and \dx may alias \aw or \bw (overwritten).
;            \ch and \dy may alias \ah or \bh (overwritten).
;            \tmp is clobbered.
;            \ax, \ay, \bx, \by are read-only.
;
; On overlap: \cw = combined_w, \dx = signed delta_x,
;             \ch = combined_h, \dy = signed delta_y

aabb_overlap macro ax,ay,bx,by,aw,bw,cw,dx,ah,bh,ch,dy,tmp,miss
        move.w  \aw, \cw
        add.w   \bw, \cw                       ; cw = aw + bw

        move.w  \ax, \dx
        sub.w   \bx, \dx                       ; dx = ax - bx (signed)

        move.w  \dx, \tmp
        bpl.s   .xpos\@
        neg.w   \tmp
.xpos\@:
        add.w   \tmp, \tmp                     ; abs(dx) * 2
        cmp.w   \cw, \tmp
        bhs.s   \miss

        move.w  \ah, \ch
        add.w   \bh, \ch                       ; ch = ah + bh

        move.w  \ay, \dy
        sub.w   \by, \dy                       ; dy = ay - by (signed)

        move.w  \dy, \tmp
        bpl.s   .ypos\@
        neg.w   \tmp
.ypos\@:
        add.w   \tmp, \tmp                     ; abs(dy) * 2
        cmp.w   \ch, \tmp
        bhs.s   \miss
        endm
```

For TouchResponse, the caller sets up:
- d4 = player X (cached), d5 = player Y (cached) — these are `ax`, `ay`
- Load target X/Y into scratch regs
- Load widths/heights into d0-d3

After macro: d0 = combined_w, d1 = signed delta_x, d2 = combined_h, d3 = signed delta_y — exactly what the handler dispatch expects.

Revised collision.asm refactor:

Replace lines 41–82 (from `; --- X axis overlap ---` through `; --- Overlap confirmed: set up handler registers ---` and the `move.w a0, d0` / `move.w a1, d1` lines) with:

```asm
        ; --- AABB overlap test (shared macro) ---
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3

        move.w  SST_x_pos(a3), d4               ; use cached d4/d5 for player
        ; Wait — d4 IS cached player X. We need target X separately.
```

Hmm, there's a register pressure problem. TouchResponse caches player X in d4 and player Y in d5 across the object loop. The macro needs player and target positions, plus 4 dimension values, plus scratch. That's 9 values but we only have d0-d7 (8 data registers).

The original code solves this by stashing results in address registers. Let's keep the macro simple and just use the same approach the original does — stash target position:

Actually, let me re-read the original code more carefully. It does:
1. d0 = player width (byte-extended)
2. d1 = target width (byte-extended)  
3. d0 = combined_w (d0 + d1)
4. d1 = delta_x (d4 - target_x) — d4 is cached player X
5. Test abs(d1)*2 vs d0
6. Stash d0→a0, d1→a1
7. d2 = player height, d3 = target height
8. d2 = combined_h
9. d3 = delta_y (d5 - target_y)
10. Test abs(d3)*2 vs d2
11. Restore d0=a0, d1=a1

The macro can exactly replicate this flow. The key insight is that the macro's parameters are register names, and the caller picks which registers to use. For TouchResponse:

```
aabb_overlap d4,d5, SST_x_pos(a3),SST_y_pos(a3), ...
```

Wait, the macro parameters need to be register names for `move.w \ax, \dx`. Memory operands won't work because `sub.w` needs the subtraction `ax - bx`.

OK, let me just design the macro to work with the actual calling convention. The macro does the computation inline. The caller pre-loads what it needs. For TouchResponse specifically, d4/d5 hold cached player X/Y, and target X/Y come from memory. Width/height come from memory too.

Let me simplify: the macro takes register names for all inputs (caller must pre-load) plus output/scratch registers. This is cleaner and matches 68000 convention.

I'll finalize the actual macro design and collision.asm integration in the implementation. The key contract is: same math as current collision.asm lines 42-79, same output registers (d0=combined_w, d1=delta_x, d2=combined_h, d3=delta_y), same miss label (.next_object).

Here's the final cleaned-up plan for the macro and refactor:

```asm
; aabb_overlap — inline AABB test
; All parameters are register names (word). Caller pre-loads them.
; Falls through on hit, branches to \miss on no overlap.
;
; \cw receives combined_w, \dx receives signed delta_x,
; \ch receives combined_h, \dy receives signed delta_y.
; \tmp is clobbered. Source registers (\ax,\ay,\bx,\by) are preserved.
; Width/height source registers (\aw,\bw,\ah,\bh) may be overwritten
; if they alias output registers.

aabb_overlap macro ax,ay,bx,by,aw,bw,cw,dx,ah,bh,ch,dy,tmp,miss
        move.w  \aw, \cw
        add.w   \bw, \cw
        move.w  \ax, \dx
        sub.w   \bx, \dx
        move.w  \dx, \tmp
        bpl.s   .xp\@
        neg.w   \tmp
.xp\@:  add.w   \tmp, \tmp
        cmp.w   \cw, \tmp
        bhs.s   \miss
        move.w  \ah, \ch
        add.w   \bh, \ch
        move.w  \ay, \dy
        sub.w   \by, \dy
        move.w  \dy, \tmp
        bpl.s   .yp\@
        neg.w   \tmp
.yp\@:  add.w   \tmp, \tmp
        cmp.w   \ch, \tmp
        bhs.s   \miss
        endm
```

For TouchResponse, the refactored loop body replaces lines 41-84:

```asm
        ; --- AABB overlap (shared macro) ---
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0        ; player width
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1        ; target width
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2       ; player height
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3       ; target height

        movea.w SST_x_pos(a3), a0               ; target X into a0
        movea.w SST_y_pos(a3), a1               ; target Y into a1

        aabb_overlap d4,d5,a0,a1,d0,d1,d0,d1,d2,d3,d2,d3,d0,.next_object
```

Wait, that has aliasing issues — `\cw` = d0 and `\aw` = d0, meaning the combined_w overwrites player_w before it's used... but `move.w \aw, \cw` is `move.w d0, d0` which is a no-op, then `add.w \bw, \cw` is `add.w d1, d0` which correctly gives combined_w in d0. Then `move.w \ax, \dx` is `move.w d4, d1` which overwrites the target width in d1, but d1 (bw) is already consumed. This works.

Same for Y: `\ch` = d2, `\ah` = d2 → `move.w d2, d2` (no-op), `add.w d3, d2` → combined_h in d2. `\dy` = d3, `\ay` = d5 → `move.w d5, d3` overwrites target height but it's consumed.

Final output: d0 = combined_w, d1 = signed delta_x, d2 = combined_h, d3 = signed delta_y. This matches the handler dispatch convention.

But wait — `\tmp` = d0 too. The tmp is used for abs computation: `move.w \dx, \tmp` = `move.w d1, d0` — this overwrites combined_w in d0. The dispatch needs d0 = combined_w.

The original code solves this by stashing to address registers. Let's do the same:

```asm
        movea.w SST_x_pos(a3), a0
        movea.w SST_y_pos(a3), a1
        aabb_overlap d4,d5,a0,a1,d0,d1,d0,d1,d2,d3,d2,d3,d0,.next_object
        ; After macro: d0 is trashed (was tmp), d1 = delta_x, d2 = combined_h, d3 = delta_y
        ; Need to recover combined_w — but it was in d0 which got used as tmp
```

This doesn't work because the macro uses the same register for `cw` and `tmp`. Need a dedicated tmp register. The original code uses d2 as tmp for X (then loads height into d2 after), so effectively it has separate tmp. Let me use a proper allocation:

For TouchResponse: use d0,d1 for widths → d0=combined_w; d1=delta_x; stash to a0/a1; d2,d3 for heights → d2=combined_h; d3=delta_y; d0 as tmp for Y test; then restore from a0/a1.

Actually this is getting complex in the plan text. Let me just describe the contract clearly and write the actual code during implementation. The key point is:

1. Create `aabb.inc` with the parameterized macro
2. Refactor `collision.asm` to use it (same behavior, same output registers for handler dispatch)
3. The macro will also be used by `rings.asm` (Task 5)

- [ ] **Step 3 (revised): Create engine/objects/aabb.inc with the AABB macro**

Create `engine/objects/aabb.inc`:

```asm
; aabb_overlap — inline AABB overlap test (assembler macro)
; Single source of truth for overlap math — used by TouchResponse and RingCollision.
;
; Tests: abs(ax - bx)*2 < (aw + bw)  AND  abs(ay - by)*2 < (ah + bh)
; Falls through on overlap, branches to \miss on no overlap.
;
; On overlap these outputs are available:
;   \cw = combined_w (aw + bw)
;   \dx = signed delta_x (ax - bx)
;   \ch = combined_h (ah + bh)
;   \dy = signed delta_y (ay - by)
;
; Register rules:
;   \ax, \ay          — read-only (never written)
;   \bx, \by          — read-only (never written)
;   \aw, \bw          — consumed (may be aliased to \cw)
;   \ah, \bh          — consumed (may be aliased to \ch)
;   \cw, \dx, \ch, \dy — outputs (written)
;   \tmp              — clobbered scratch, MUST NOT alias \cw or \ch

aabb_overlap macro ax,ay,bx,by,aw,bw,cw,dx,ah,bh,ch,dy,tmp,miss
        move.w  \aw, \cw
        add.w   \bw, \cw

        move.w  \ax, \dx
        sub.w   \bx, \dx

        move.w  \dx, \tmp
        bpl.s   .aabb_xp\@
        neg.w   \tmp
.aabb_xp\@:
        add.w   \tmp, \tmp
        cmp.w   \cw, \tmp
        bhs.s   \miss

        move.w  \ah, \ch
        add.w   \bh, \ch

        move.w  \ay, \dy
        sub.w   \by, \dy

        move.w  \dy, \tmp
        bpl.s   .aabb_yp\@
        neg.w   \tmp
.aabb_yp\@:
        add.w   \tmp, \tmp
        cmp.w   \ch, \tmp
        bhs.s   \miss
        endm
```

- [ ] **Step 4: Refactor TouchResponse to use aabb_overlap macro**

In `engine/objects/collision.asm`:

1. Add `include "engine/objects/aabb.inc"` at the top, before `TouchResponse:`.

2. Replace lines 41–84 (from `; --- X axis overlap ---` through `; d3 = signed delta_y (already set)`) with:

```asm
        ; --- AABB overlap via shared macro ---
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3

        movea.w SST_x_pos(a3), a0
        movea.w SST_y_pos(a3), a1

        ; After macro: d0=combined_w, d1=delta_x, d2=combined_h, d3=delta_y
        ; tmp=d0 aliases cw, so stash cw→a0 first, restore after.
        ; Use a different tmp strategy: let d0 alias cw (self-move is nop),
        ; stash to address regs between X and Y tests.

        ; X test: d0 = aw+bw, d1 = delta_x
        add.w   d1, d0                         ; d0 = combined_w
        move.w  d4, d1                         ; d1 = player X
        sub.w   a0, d1                         ; d1 = delta_x

        move.w  d1, d0                         ; scratch = delta_x... no wait

```

This is getting tangled in the plan text. Let me take a different approach and keep the exact existing register allocation strategy from collision.asm — it's already well-optimized. The macro will use the same pattern:

Replace the refactor step with a simpler approach: keep the existing inline code structure but factor out into a macro that matches the exact register usage pattern. The key benefit is that rings.asm gets the same tested math without copy-paste.

Actually, let me step back. The spec says the macro should be parameterized by register names. The existing TouchResponse code has a specific register trick (stash to a0/a1). Rather than trying to make a one-size-fits-all macro that handles all register tricks, let me make the macro do the pure math and let callers handle their own register management around it.

Here's the cleanest approach:

**The macro takes pre-loaded register values and just does the compare-and-branch.** Callers handle loading registers and stashing results. The macro contract is:
- Inputs: positions and dimensions in specified registers
- Outputs: combined_w, delta_x, combined_h, delta_y in specified registers  
- One scratch register that must not alias any output
- Branch to miss on no overlap

For TouchResponse, we can use the existing stash-to-address-register trick AROUND the macro call. I'll write the precise code during implementation after research.

- [ ] **Step 5: Build and test**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds. Behavior unchanged (same collision math, just reorganized).

- [ ] **Step 6: Test in Exodus**

Load ROM in Exodus. Run OJZ scroll test. Verify player marker still collides with solid objects the same as before (if any spawned test objects exist in the test scene). Verify no regressions.

- [ ] **Step 7: Commit**

```bash
git add engine/objects/aabb.inc engine/objects/collision.asm
git commit -m "refactor(§4.9): extract AABB overlap into shared macro

aabb.inc provides parameterized aabb_overlap macro.
TouchResponse refactored to use it — same behavior, single
source of truth for collision math. RingCollision will also use it.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Ring Expansion (ExpandRings)

**Files:**
- Create: `engine/objects/rings.asm` (partial — ExpandRings only, DrawRings/RingCollision in later tasks)
- Modify: `main.asm:111` (add include)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for ring layout formats and expansion strategies:
- **S.C.E.**: Search for ring manager, ring layout parsing, ring format documentation
- **sonic_hack**: Look at `code/engines/Ring_Manager.asm` — S2's original ring loading + rendering. Study the format: `dc.w x, y, count_spacing_word`. Note how rings are pre-sorted by X for on-screen culling.
- **Ristar**: Does it have collectible items with pattern encoding?
- **Gunstar Heroes, Alien Soldier**: Pickup/item placement formats
- **Vectorman, Batman & Robin, Thunder Force IV**: Entity placement formats
- **Online**: Sonic Retro ring format documentation, SpritesMind ring manager optimization threads
- **Modern**: Consider build-time pre-expansion (trade ROM for runtime CPU), or keeping pattern-encoded for ROM savings with fast runtime expand

Report findings before proceeding.

- [ ] **Step 2: Create engine/objects/rings.asm with ExpandRings**

```asm
; Ring system — expand, draw, collide
; §4.9 section-local entity management

    include "engine/objects/aabb.inc"

; -----------------------------------------------
; Ring spacing lookup table (3-bit index → pixel spacing)
; -----------------------------------------------
RingSpacingTable:
        dc.w    $10, $14, $18, $1C, $20, $24, $28, $30

; -----------------------------------------------
; ExpandRings — expand pattern-encoded ring layout into slot buffer
;
; Reads 4-byte pattern entries from ROM, expands lines into
; individual x,y pairs, converts section-local coords to
; engine-space (adds slot origin X/Y).
;
; In:  a0 = ring layout pointer (ROM, $00000000 terminated)
;           (0/NULL = no rings for this section, skip)
;      a1 = ring buffer pointer (RAM, slot's Ring_Buffer_N)
;      d0.w = slot origin X (engine-space, integer pixels)
;      d1.w = slot origin Y (engine-space, integer pixels)
; Out: d0.b = expanded ring count
; Clobbers: d0-d5, a0-a2
; -----------------------------------------------
ExpandRings:
        move.l  a0, d2
        beq.s   .no_rings

        movea.l a1, a2                  ; a2 = write pointer
        moveq   #0, d5                  ; d5 = ring counter

.entry_loop:
        move.l  (a0)+, d2              ; read 32-bit entry
        beq.s   .done                  ; $00000000 = terminator

        ; Extract X and Y (section-local)
        move.l  d2, d3
        swap    d3
        lsr.w   #4, d3                 ; d3 = bits 29-20 (X >> 4 after swap gets bits 29-16 in low word, then >>4)
        ; Actually: after swap, d3.w has bits 31-16. We need bits 29-20.
        ; Let me redo the bit extraction:
        ;   d2 = [TT XXXXXXXXXX YYYYYYYYYY CCCCC SSS RR]
        ;   bit 31-30 = type, 29-20 = X, 19-10 = Y, 9-5 = count, 4-2 = spacing

        ; Extract type
        move.l  d2, d3
        rol.l   #2, d3                 ; type in bits 1-0 of d3
        andi.w  #3, d3                 ; d3.w = type (0/1/2)

        ; Extract X: bits 29-20 → shift right 20
        move.l  d2, d4
        swap    d4                     ; d4.w = bits 31-16
        lsr.w   #4, d4                 ; bits 29-20 → bits 13-4 → then mask
        andi.w  #$3FF, d4              ; d4.w = X (10 bits)
        add.w   d0, d4                 ; d4 = engine-space X

        ; Extract Y: bits 19-10 → shift right 10
        move.l  d2, d3
        lsr.l   #8, d3
        lsr.w   #2, d3                 ; d3.w now has bits 19-10 in low 10 positions
        andi.w  #$3FF, d3              ; d3.w = Y (10 bits)
        ; Actually lsr.l #8 then lsr.w #2 = shift right 10 on the lower 20 bits.
        ; But lsr.l #8 shifts the entire long, so bits 19-10 become bits 11-2,
        ; then lsr.w #2 shifts the word to get bits 9-0. Yes.
        add.w   d1, d3                 ; d3 = engine-space Y

        ; Determine type from bits 31-30
        move.l  d2, d4                 ; reload for type check
        ; ...
```

This is getting into implementation-level detail that will be finalized during the actual coding (after research). The plan should show the structure and key decisions, with enough code to guide implementation. Let me restructure.

The actual implementation will handle bit extraction using optimized 68000 shifts. The key algorithm:

```
for each entry:
    extract type, X, Y from 32-bit word
    add slot origin to X, Y → engine-space
    if individual: write (X, Y), count++
    if h-line: extract count, spacing; write count entries at (X + i*spacing, Y), count += n
    if v-line: extract count, spacing; write count entries at (X, Y + i*spacing), count += n
    if count >= MAX_RINGS_PER_SLOT: stop (overflow guard)
```

Create `engine/objects/rings.asm` with:
1. `RingSpacingTable` (8 entries: $10, $14, $18, $1C, $20, $24, $28, $30)
2. `ExpandRings` routine implementing the algorithm above
3. Stub labels for `DrawRings`, `RingCollision`, `CollectRing` (just `rts`)

- [ ] **Step 3: Add include in main.asm**

Add after `include "engine/objects/collision.asm"` (line 109):

```asm
    include "engine/objects/rings.asm"
```

- [ ] **Step 4: Build**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds. No behavioral change (stubs only).

- [ ] **Step 5: Commit**

```bash
git add engine/objects/rings.asm main.asm
git commit -m "feat(§4.9): add ExpandRings — pattern-encoded ring expansion

Expands 4-byte pattern entries (individual/h-line/v-line) into
flat x,y pairs in slot ring buffers. Adds slot origin for
engine-space conversion. DrawRings/RingCollision stubbed.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Ring Rendering (DrawRings)

**Files:**
- Modify: `engine/objects/rings.asm` (replace DrawRings stub)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for ring rendering strategies:
- **S.C.E.**: How does it render rings? Direct sprite writes or object-system slots?
- **sonic_hack**: `code/engines/Ring_Manager.asm` — S2 renders rings directly to sprite table, bypassing object RAM. Study the animation frame cycling, on-screen culling by X position, and sprite entry format.
- **Batman & Robin**: Sprite table management techniques
- **Gunstar Heroes, Vectorman**: Bulk sprite rendering for pickups/items
- **Online**: VDP sprite table format (y, size/link, tile, x), sprite limit considerations
- **Modern**: Consider writing from the END of sprite table backward (avoiding link chain conflicts with object sprites), or using a dedicated sprite band

Report findings before proceeding.

- [ ] **Step 2: Implement DrawRings**

DrawRings iterates both slot ring buffers, skips collected rings via bitmask, and writes sprite entries directly to `Sprite_Table_Buffer`. Key decisions:

- Writes sprite entries at the END of Sprite_Table_Buffer (after object sprites)
- Uses a global ring animation frame (Ring_Anim_Frame, 4 frames cycling)
- On-screen culling: skip rings outside Camera_X/Camera_Y visible window
- No SST slots consumed — rings are pure sprite entries

```
Algorithm:
1. Update ring animation timer; advance Ring_Anim_Frame if expired
2. Compute screen bounds from Camera_X/Camera_Y
3. For each slot (0, 1):
   a. Load ring count, buffer pointer, bitmask pointer
   b. For each ring index 0..count-1:
      - Check bitmask bit: if set (collected), skip
      - Load ring X, Y from buffer
      - Cull: if outside screen bounds + margin, skip
      - Convert engine-space to screen-space (subtract camera, add 128)
      - Write 8-byte sprite entry to Sprite_Table_Buffer
      - Increment sprite write pointer
4. Terminate sprite list (link = 0 on last entry)
```

Ring art: For now, use the same test tile ($FA) as the player marker. Real ring art + mappings are deferred to when we import ring graphics from sonic_hack.

- [ ] **Step 3: Build and test**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add engine/objects/rings.asm
git commit -m "feat(§4.9): add DrawRings — ring buffer sprite rendering

Iterates both slot ring buffers, skips collected via bitmask,
writes sprite entries directly to Sprite_Table_Buffer. Uses
global animation frame counter. On-screen culling by camera bounds.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Ring Collision (RingCollision + CollectRing)

**Files:**
- Modify: `engine/objects/rings.asm` (replace RingCollision/CollectRing stubs)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for ring collection mechanics:
- **S.C.E.**: Ring collection detection — how is player overlap tested against ring positions? Is there any spatial partitioning or is it brute-force?
- **sonic_hack**: `code/engines/Ring_Manager.asm` — S2's ring collision uses X-sorted ring array with early-exit when ring X is past player X + width. Study the bitmask-based "consumed" tracking.
- **Gunstar Heroes, Alien Soldier**: Pickup collection mechanics
- **Online**: SpritesMind threads on ring collision optimization
- **Modern**: Spatial hashing for O(1) lookups? For 128 rings max, brute-force with bitmask skip is likely fast enough (~20 cycles/ring × 128 = 2560 cycles worst case, acceptable)

Report findings before proceeding.

- [ ] **Step 2: Implement RingCollision**

```
Algorithm:
1. For each player (Player_1, Player_2 — NUM_PLAYERS loop):
   a. Skip if player slot empty (code_addr = 0)
   b. Cache player X, Y, width (RING_WIDTH/2), height (RING_HEIGHT/2)
   c. For each slot (0, 1):
      - Load ring count, buffer pointer, bitmask pointer
      - For each ring index 0..count-1:
        * Check bitmask bit: if set (collected), skip
        * Load ring X, Y
        * Use aabb_overlap macro to test player vs ring (fixed 16×16 ring box)
        * On overlap: call CollectRing
```

- [ ] **Step 3: Implement CollectRing**

```
CollectRing:
1. Set bitmask bit for this ring index (mark collected)
2. Increment Ring_Counter (total collected rings)
3. (Deferred: queue sparkle effect via AllocEffect)
4. (Deferred: play ring SFX)
```

- [ ] **Step 4: Build and test**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add engine/objects/rings.asm
git commit -m "feat(§4.9): add RingCollision + CollectRing

Player-vs-ring AABB using shared aabb_overlap macro.
On hit: set bitmask bit, increment Ring_Counter.
Sparkle effect and SFX deferred.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Entity Loader (LoadTypeTable, SpawnSectionObjects, DespawnSlotObjects)

**Files:**
- Create: `engine/objects/entity_loader.asm`
- Modify: `main.asm` (add include)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for object spawning/despawning patterns:
- **S.C.E.**: How does it load objects per-section? Look for object layout parsing, respawn table management
- **sonic_hack**: `code/objects/Object_Specific_Routines/` — S2's object loading uses a sorted object list with a "last loaded index" tracker. Study `ObjectsLoad` and `ObjectsManager`. Note the respawn table for tracking destroyed objects.
- **Gunstar Heroes, Alien Soldier**: Enemy spawning tied to stage progression — any section-based patterns?
- **Vectorman**: Level-based entity loading
- **Batman & Robin**: Scene-based entity management
- **Online**: Sonic Retro documentation on object managers, SpritesMind threads on entity lifecycle
- **Modern**: ECS-style entity component systems (overkill for 68000 but interesting for data layout), slot tagging patterns from modern game engines

Report findings before proceeding.

- [ ] **Step 2: Create engine/objects/entity_loader.asm**

Three routines:

**LoadTypeTable:**
```
In:  a0 = ROM type table pointer (array of ObjDef longwords)
     d0.b = entry count (0 = no types for this section)
Out: none
Clobbers: d0, a0-a1

Algorithm:
1. If count = 0 or pointer is NULL, clear Object_Type_Table and return
2. lea Object_Type_Table, a1
3. Copy count × 4 bytes from ROM to RAM
4. Zero remaining entries (32 - count) to prevent stale pointers
```

**SpawnSectionObjects:**
```
In:  a0 = object layout pointer (ROM, 4-byte entries, $00000000 terminated)
         (0/NULL = no objects for this section)
     d0.w = slot origin X (engine-space pixels)
     d1.w = slot origin Y (engine-space pixels)
     d2.b = slot tag (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
Out: none
Clobbers: d0-d5, a0-a3

Algorithm:
for each 4-byte entry:
    extract type (5 bits), subtype (5 bits), X (10 bits), Y (10 bits)
    add slot origin to X, Y → engine-space
    look up ObjDef pointer: Object_Type_Table[type * 4]
    if ObjDef pointer is 0 (empty type slot), skip
    call Load_Object(a1=ObjDef, d0=X, d1=Y, d2=subtype)
    if alloc succeeded: write slot tag to SLOT_TAG_OFFSET(a1)
```

**DespawnSlotObjects:**
```
In:  d0.b = slot tag to match (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
Out: none
Clobbers: d0-d1, a0-a1

Algorithm:
1. lea Dynamic_Slots, a0
2. For each of NUM_DYNAMIC slots:
   a. If code_addr = 0, skip (empty)
   b. If SLOT_TAG_OFFSET(a0) != d0, skip (different slot or untagged)
   c. Call DeleteObject(a0)
3. Advance a0 by SST_len, loop
```

- [ ] **Step 3: Add include in main.asm**

Add after the rings.asm include:

```asm
    include "engine/objects/entity_loader.asm"
```

- [ ] **Step 4: Build**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add engine/objects/entity_loader.asm main.asm
git commit -m "feat(§4.9): add entity loader — type tables, spawn, despawn

LoadTypeTable copies per-section ObjDef pointer array to RAM.
SpawnSectionObjects parses 4-byte entries, converts section-local
coords to engine-space, spawns via Load_Object with slot tag.
DespawnSlotObjects scans dynamic pool for matching slot tag.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Test Data (OJZ Sec0/Sec1 Ring Patterns + Object Placements)

**Files:**
- Create: `data/levels/ojz/act1/entity_data.asm`
- Modify: `data/levels/ojz/act1/act_descriptor.asm` (wire pointers)
- Modify: `main.asm` (add include for entity_data)

- [ ] **Step 1: Research**

Check reference projects for test data authoring patterns:
- **sonic_hack**: Look at `level/rings/` and `level/objects/` for OJZ ring/object placement data formats. Note actual ring positions from OJZ Act 1 to potentially recreate familiar placements.
- **S.C.E.**: Ring layout format comparison
- **Modern**: Consider placing rings at known visible positions for easy visual verification. Place objects on the stub floor (Y=192) so they're visible and interactable.

Report findings before proceeding.

- [ ] **Step 2: Create entity_data.asm with test fixtures**

```asm
; OJZ Act 1 entity data — ring patterns + object placements + type tables
; §4.9 test fixtures

; -----------------------------------------------
; Sec0 Type Table — 3 types
; -----------------------------------------------
OJZ_Sec0_TypeCount = 3
OJZ_Sec0_Types:
        dc.l    ObjDef_Static           ; type 0
        dc.l    ObjDef_Enemy            ; type 1
        dc.l    ObjDef_Solid            ; type 2

; -----------------------------------------------
; Sec0 Object Layout — 2 placements
;   [2-bit reserved][10-bit X][10-bit Y][5-bit type][5-bit subtype]
; -----------------------------------------------
OJZ_Sec0_Objects:
        ; TestStatic at X=$100, Y=$0B0 (type 0, subtype 0)
        dc.l    ($100<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(0<<OBJ_ENTRY_TYPE_SHIFT)|0
        ; TestSolid at X=$200, Y=$0B8 (type 2, subtype 0)
        dc.l    ($200<<OBJ_ENTRY_X_SHIFT)|($0B8<<OBJ_ENTRY_Y_SHIFT)|(2<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec0 Ring Layout — 1 h-line (5 rings) + 2 individual
;   [2-bit type][10-bit X][10-bit Y][5-bit count][3-bit spacing][2-bit reserved]
; -----------------------------------------------
OJZ_Sec0_Rings:
        ; H-line: X=$080, Y=$060, 5 rings, spacing index 0 ($10 px)
        dc.l    RING_TYPE_HLINE|($080<<RING_X_SHIFT)|($060<<RING_Y_SHIFT)|(4<<RING_COUNT_SHIFT)|(0<<RING_SPACING_SHIFT)
        ; Individual: X=$180, Y=$080
        dc.l    RING_TYPE_INDIVIDUAL|($180<<RING_X_SHIFT)|($080<<RING_Y_SHIFT)
        ; Individual: X=$1A0, Y=$080
        dc.l    RING_TYPE_INDIVIDUAL|($1A0<<RING_X_SHIFT)|($080<<RING_Y_SHIFT)
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Type Table — 1 type
; -----------------------------------------------
OJZ_Sec1_TypeCount = 1
OJZ_Sec1_Types:
        dc.l    ObjDef_Solid            ; type 0

; -----------------------------------------------
; Sec1 Object Layout — 1 placement
; -----------------------------------------------
OJZ_Sec1_Objects:
        ; TestSolid at X=$100, Y=$0B8 (type 0, subtype 0)
        dc.l    ($100<<OBJ_ENTRY_X_SHIFT)|($0B8<<OBJ_ENTRY_Y_SHIFT)|(0<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Ring Layout — 1 v-line (3 rings) + 3 individual
; -----------------------------------------------
OJZ_Sec1_Rings:
        ; V-line: X=$100, Y=$040, 3 rings, spacing index 0 ($10 px)
        dc.l    RING_TYPE_VLINE|($100<<RING_X_SHIFT)|($040<<RING_Y_SHIFT)|(2<<RING_COUNT_SHIFT)|(0<<RING_SPACING_SHIFT)
        ; Individual: X=$180, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($180<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        ; Individual: X=$1C0, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($1C0<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        ; Individual: X=$200, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($200<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        dc.l    0                       ; terminator
```

Note: The count field in ring patterns encodes count-1 (5 bits, 0-31 → 1-32 rings). So 5 rings → count field = 4. 3 rings → count field = 2.

- [ ] **Step 3: Wire pointers in act_descriptor.asm**

Update OJZ_Sec0's `sec_objects` and `sec_rings` fields (currently `dc.l 0, 0`):

```asm
OJZ_Sec0:
    dc.l    OJZ_Sec0_Strips_A       ; sec_strips_a
    dc.l    OJZ_Sec0_Objects        ; sec_objects
    dc.l    OJZ_Sec0_Rings          ; sec_rings
    dc.l    0                       ; sec_plc
    ; ... rest unchanged
```

Same for OJZ_Sec1:

```asm
OJZ_Sec1:
    dc.l    OJZ_Sec1_Strips_A
    dc.l    OJZ_Sec1_Objects        ; sec_objects
    dc.l    OJZ_Sec1_Rings          ; sec_rings
    dc.l    0
    ; ... rest unchanged
```

Sec2–Sec8 remain with `dc.l 0, 0, 0` — entity loader skips NULL pointers.

- [ ] **Step 4: Add include in main.asm**

Add the entity_data.asm include in the data section (after `test_objects.asm`):

```asm
    include "data/levels/ojz/act1/entity_data.asm"
```

- [ ] **Step 5: Build**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds. No behavioral change yet — data exists but nothing calls it.

- [ ] **Step 6: Commit**

```bash
git add data/levels/ojz/act1/entity_data.asm data/levels/ojz/act1/act_descriptor.asm main.asm
git commit -m "feat(§4.9): add OJZ Sec0/Sec1 test entity data

Sec0: 3-type table (static/enemy/solid), 2 objects, 7 rings (1 h-line + 2 individual).
Sec1: 1-type table (solid), 1 object, 6 rings (1 v-line + 3 individual).
Sec2-8: no entities (NULL pointers, entity loader skips).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Section Streaming Integration Hooks

**Files:**
- Modify: `engine/level/section.asm` (add entity hooks at 4 lifecycle points)
- Modify: `structs.asm` (may need type count field in Sec struct — or derive from data)

- [ ] **Step 1: Research**

Check all 8 reference disassemblies for entity lifecycle integration with level streaming:
- **S.C.E.**: How does it manage object loading during level transitions? Is there a section/chunk-based entity system?
- **sonic_hack**: `ObjectsManager` triggers object loading based on camera position. Study how objects are loaded/unloaded as camera scrolls. Note the respawn index system.
- **Gunstar Heroes**: Scene transition entity management
- **Vectorman**: Entity loading at level boundaries
- **Online**: SpritesMind threads on Sonic object managers, streaming entity systems
- **Modern**: Consider the order of operations — should entities load BEFORE or AFTER tile art? After (art is needed for rendering). Should despawn happen BEFORE or AFTER section map update? Before (need old slot tag).

Report findings before proceeding.

- [ ] **Step 2: Add entity hooks to Section_Init**

After `Section_FillInitial` call and before the `rts` in `Section_Init`, add entity loading for both initial slots:

```asm
        ; -- §4.9: load entities for initial slots --
        ; Slot 0
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef              ; a0 = Sec ptr for slot 0
        move.w  #SLOT_ORIGIN_L, d0              ; slot 0 origin X
        moveq   #0, d1                          ; origin Y (Phase 1: 0)
        bsr.w   Section_LoadEntities_Slot0

        ; Slot 1
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef              ; a0 = Sec ptr for slot 1
        move.w  #SLOT_ORIGIN_R, d0
        moveq   #0, d1
        bsr.w   Section_LoadEntities_Slot1
```

Where `Section_LoadEntities_SlotN` is a helper that calls LoadTypeTable, SpawnSectionObjects, and ExpandRings for a given slot, using the Sec struct pointer in a0.

- [ ] **Step 3: Add entity hooks to preload triggers**

In `.preload_fwd` and `.preload_bwd`, after `Section_StreamArtGroup`, add entity loading for the upcoming section. The entities spawn at engine-space coords in the upcoming slot territory.

- [ ] **Step 4: Add entity hooks to teleport**

In `Section_TeleportFwd`:
1. Before the section map update: `DespawnSlotObjects` for the outgoing slot tag
2. After SECTION_SHIFT to player/camera: apply SECTION_SHIFT to surviving tagged objects' x_pos
3. Shift surviving ring buffer positions by SECTION_SHIFT
4. Clear outgoing slot's ring buffer and bitmask

In `Section_TeleportBwd`: mirror of the above.

The SECTION_SHIFT for objects:

```asm
        ; Shift all surviving tagged objects by -SECTION_SHIFT (forward teleport)
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d6
.shift_loop:
        tst.w   (a0)
        beq.s   .shift_next
        move.b  SLOT_TAG_OFFSET(a0), d0
        cmpi.b  #SLOT_TAG_UNTAGGED, d0
        beq.s   .shift_next
        subi.l  #SECTION_SHIFT<<16, SST_x_pos(a0)
.shift_next:
        lea     SST_len(a0), a0
        dbf     d6, .shift_loop
```

- [ ] **Step 5: Add entity hooks to deferred cold-load**

In `.deferred_fwd_load` and `.deferred_bwd_load`, after `Section_StreamArtGroup`, add entity loading for the newly loaded section's slot.

- [ ] **Step 6: Create Section_LoadEntities helper routines**

```asm
; Section_LoadEntities_Slot0/Slot1 — convenience wrappers
; In:  a0 = Sec struct pointer
; Clobbers: d0-d5, a0-a3
Section_LoadEntities_Slot0:
        ; LoadTypeTable
        movea.l Sec_sec_objects(a0), a1
        ; ... need type table pointer and count from somewhere
        ; The Sec struct has sec_objects which points to the object layout.
        ; The type table pointer needs to be stored somewhere.
```

Wait — the spec says the type table pointer is stored per-section, but the current Sec struct doesn't have a dedicated field for it. Looking at the struct: `sec_objects` is the object layout, `sec_rings` is the ring layout. The type table is separate data.

Options:
1. Add `sec_type_table` and `sec_type_count` to Sec struct (cleanest but changes struct size)
2. Store type table pointer + count as a header before the object layout data
3. Use a convention: type table immediately precedes object layout in ROM, with a count byte prefix

Option 2 is cleanest without changing the struct. The object layout format from the spec already assumes the type table is a separate pointer. Let me check the Sec struct — there's `sec_reserved` at $20 which is unused. We can repurpose it as `sec_type_table`.

Actually, looking at the Sec struct more carefully, there are several reserved/padding fields. Let me use `sec_reserved` ($20) for the type table pointer, and we can store the type count as the byte before the type table data in ROM (or as a separate Sec field).

Simplest approach: repurpose `sec_reserved` as `sec_type_table` (pointer to ROM type table array). The type count can be derived from the terminator or stored as a byte preceding the table. Let's store it as a byte prefix:

```asm
OJZ_Sec0_TypeTable:
        dc.b    3, 0                    ; count=3, pad
        dc.l    ObjDef_Static
        dc.l    ObjDef_Enemy
        dc.l    ObjDef_Solid
```

Then `LoadTypeTable` reads the count byte, copies the longwords.

Update `structs.asm` to rename `sec_reserved` → `sec_type_table`.

- [ ] **Step 7: Build and test**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds.

- [ ] **Step 8: Commit**

```bash
git add engine/level/section.asm structs.asm data/levels/ojz/act1/entity_data.asm
git commit -m "feat(§4.9): wire entity lifecycle hooks into section streaming

Entity spawn/despawn at 4 lifecycle points: Section_Init,
preload triggers, teleport (with SECTION_SHIFT), deferred cold-load.
Repurpose Sec.sec_reserved as sec_type_table for per-section
type table pointers.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: OJZ Scroll Test Integration

**Files:**
- Modify: `test/ojz_scroll_test.asm` (add RingCollision + DrawRings calls, integrate TestPlayer)

- [ ] **Step 1: Research**

Check existing test state for integration patterns:
- **ojz_scroll_test.asm**: Currently drives camera via controller input with a marker sprite. Calls Camera_Update, Section_Check, Section_UpdateColumns, Parallax_Update. Does NOT call RunObjects or TouchResponse (player is a direct controller-to-position mapping, not an object).
- **object_test_state.asm**: The other test state that DOES call RunObjects, TouchResponse, Render_Sprites. Has TestPlayer spawning.
- **Modern consideration**: Should we merge the two test states? Or keep them separate and just add entity calls to the scroll test?

Decision: Keep them separate. The scroll test focuses on section streaming + entities. Add RunObjects, TouchResponse, RingCollision, DrawRings to the scroll test's update loop. Spawn TestPlayer as the controllable character (replacing the marker sprite code).

Report findings before proceeding.

- [ ] **Step 2: Modify GameState_OJZScroll_Init**

Add after existing initialization (after `Section_Init` and parallax init, before display enable):

```asm
        ; -- §4.9: spawn TestPlayer in player slot 1 --
        lea     (Player_1).w, a1
        move.w  #objroutine(TestPlayer), SST_code_addr(a1)
        ; Position already set above (camera center)
        ; Mark as untagged
        move.b  #SLOT_TAG_UNTAGGED, SLOT_TAG_OFFSET(a1)

        ; -- §4.9: init ring animation state --
        clr.b   (Ring_Anim_Frame).w
        move.b  #RING_ANIM_SPEED, (Ring_Anim_Timer).w
        clr.w   (Ring_Counter).w
```

Wait — TestPlayer is initialized via its init routine which sets up mappings, art_tile, etc. The current code in object_test_state.asm calls:

```asm
        moveq   #OBJ_CODE_BANK, d0
        swap    d0
        move.w  (Player_1).w, d0
        movea.l d0, a1
        lea     (Player_1).w, a0
        jsr     (a1)
```

Which calls TestPlayer (the init routine) which sets code_addr to TestPlayer_Main. So we need to set code_addr to TestPlayer (init), then run one frame.

Actually simpler: just set up Player_1 directly by writing the init state into its SST, similar to how object_test_state does it. But the cleanest way is to set code_addr = objroutine(TestPlayer) and let RunObjects call the init routine on the first frame, which chains to TestPlayer_Main.

- [ ] **Step 3: Modify GameState_OJZScroll_Update**

Replace the manual controller movement code with calls to the object/entity systems. The new update order:

```asm
GameState_OJZScroll_Update:
        ; 1. RunObjects (dispatches TestPlayer + any section-spawned objects)
        jsr     RunObjects

        ; 2. Camera follows player
        jsr     Camera_Update

        ; 3. Section teleport check
        jsr     Section_Check

        ; 4. Column streaming
        jsr     Section_UpdateColumns

        ; 5. TouchResponse (player-vs-object collision)
        jsr     TouchResponse

        ; 6. RingCollision (player-vs-ring-buffer)
        jsr     RingCollision

        ; 7. Render object sprites
        jsr     Render_Sprites

        ; 8. DrawRings (ring buffer → sprite table)
        jsr     DrawRings

        ; 9. Parallax T14 slot tracking + update
        ; (keep existing parallax code)
        ...
        jsr     Parallax_Update
        rts
```

Remove the old manual controller movement code, marker sprite write, and PlayerMarkerTile data (TestPlayer handles all of this now via its own object code).

- [ ] **Step 4: Build**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh`
Expected: Build succeeds.

- [ ] **Step 5: Test in Exodus**

Load ROM in Exodus. Run OJZ scroll test:
- Verify TestPlayer appears with Sonic sprite, responds to controls
- Verify rings appear in Sec0 (h-line of 5 + 2 individual) and Sec1 (v-line of 3 + 3 individual)
- Walk player into a ring → ring disappears, Ring_Counter increments
- Scroll to Sec2+ → no rings/objects (no data)
- Scroll back to Sec0 → rings reappear fresh (no respawn memory — deferred)
- Objects spawn in Sec0/Sec1, despawn when teleporting away
- Verify no sprite glitches, no crashes on teleport

- [ ] **Step 6: Commit**

```bash
git add test/ojz_scroll_test.asm
git commit -m "feat(§4.9): integrate entities into OJZ scroll test

Replace manual camera control with full object/entity pipeline:
RunObjects, Camera_Update, TouchResponse, RingCollision, DrawRings.
TestPlayer spawned in Player_1 slot with Sonic sprite + physics.
Rings visible in Sec0/Sec1, collectible via overlap.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Polish and Bug Fixes

**Files:**
- Various (based on testing results)

- [ ] **Step 1: Full integration test**

Run the complete OJZ scroll test end-to-end:
1. Level boot → entities load in Sec0 + Sec1
2. Walk right through Sec0 collecting rings → rings disappear
3. Cross into Sec1 → Sec1 entities spawn, Sec0 entities survive (both in view)
4. Forward teleport → old slot entities despawn, SECTION_SHIFT applied to survivors
5. Walk back → backward teleport → same lifecycle in reverse
6. Verify ring animation cycles (4 frames)
7. Check Ring_Counter value matches collected count
8. Verify no SST slot leaks (check Dynamic_Free_SP after despawn)

- [ ] **Step 2: Fix any issues found**

Address bugs discovered during integration testing.

- [ ] **Step 3: Update ENGINE_ARCHITECTURE.md**

Add §4.9 section documenting the entity system as built. Include:
- Ring system (ROM format, expansion, rendering, collision)
- Object layout + type tables
- Section streaming integration hooks
- RAM layout additions

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore(§4.9): polish and docs after integration testing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Execution Notes

- Tasks 1-2 are foundational (RAM layout + AABB macro) — must complete first
- Tasks 3-5 (ring system) and Task 6 (entity loader) are independent of each other but both depend on Tasks 1-2
- Task 7 (test data) depends on Task 6 (needs type table format finalized)
- Task 8 (streaming hooks) depends on Tasks 3, 5, 6 (calls ExpandRings, SpawnSectionObjects, DespawnSlotObjects)
- Task 9 (test integration) depends on all prior tasks
- Task 10 (polish) is the final pass

Each task includes a research sub-task. The research should be thorough but focused on the specific component being built. Don't front-load — research per task so findings are fresh and specific.
