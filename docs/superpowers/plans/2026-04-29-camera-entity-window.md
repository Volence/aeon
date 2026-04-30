# Camera-Driven Entity Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace teleport-triggered bulk entity loading with a camera-driven sliding window — entities load/despawn based on camera proximity.

**Architecture:** Pre-expanded X-sorted flat ring lists in ROM (build tool generates). Unified ring buffer in RAM (128 entries × 6 bytes). Per-section scan state tracks left/right load indices. EntityWindow_Scan runs once per frame after Camera_Update, spawning entities entering camera range and despawning those leaving it. Teleport shifts on-screen entities and resets scan state — no bitmask persistence needed.

**Tech Stack:** 68000 assembly (AS Macro Assembler), Python 3 build tool (`ojz_strip_gen.py`)

---

### Task 1: Research — Camera-Driven Entity Loading Patterns

**Files:**
- Read-only: all 8 reference disassemblies, online sources

- [ ] **Step 1: Research sonic_hack's entity loading**

Study sonic_hack's camera-driven ring/object loading:
- `sonic_hack/code/engines/Ring Manager/Ring_Manager.asm` — `BuildRings`, `CollectRing`
- `sonic_hack/code/objects/Object_Specific_Routines/single object loading/Object_Respawn_Loader.asm` — `ChkLoadObj`, sliding pointer
- Note X-sorted list format, sliding pointer mechanism, Y range gate, respawn table

- [ ] **Step 2: Research S.C.E. entity loading**

Check `/home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/`:
- Ring system: how rings are stored, loaded, despawned
- Object respawn system: sliding window or full-load approach
- Note any improvements over stock Sonic approach

- [ ] **Step 3: Research other disassemblies**

Quick scan of Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar for entity loading patterns:
- How do non-Sonic games handle entity spawn/despawn?
- Any O(1) removal techniques (swap-with-last, etc.)?
- Any per-section or per-screen entity management?

- [ ] **Step 4: Research online and modern approaches**

Search plutiedev, SpritesMind, segaretro, GitHub homebrew:
- Entity streaming in modern engines (spatial hashing, grid-based loading)
- Any Genesis-specific sliding window implementations beyond sonic_hack
- Hysteresis patterns (load vs despawn buffer sizes)

- [ ] **Step 5: Document findings**

Write a brief summary of key patterns found and how they inform our implementation. Note any adjustments to the spec design based on discoveries.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-29-camera-entity-window.md
git commit -m "docs: camera entity window implementation plan + research"
```

---

### Task 2: Build Tool — Flat X-Sorted Ring List Generation

**Files:**
- Modify: `tools/ojz_strip_gen.py`
- Modify: `data/levels/ojz/act1/entity_data.asm`
- Modify: `constants.asm` (remove pattern-encoding constants)

This task updates the build tool and entity data to emit pre-expanded, X-sorted flat ring lists.

- [ ] **Step 1: Research (per Task 1 pattern)**

Review how sonic_hack's ring layout format works. Check sonic_hack `level/rings/` format. Review our current entity_data.asm pattern-encoded format (RING_TYPE_HLINE, etc.) to understand what we're replacing.

- [ ] **Step 2: Add ring expansion to ojz_strip_gen.py**

Add a function to `tools/ojz_strip_gen.py` that reads the authoring-format ring definitions (H-line, V-line, individual) and outputs flat X-sorted 4-byte entries (`dc.w X, dc.w Y`). The function takes a list of ring definitions and returns expanded, X-sorted individual ring entries.

For the current OJZ test data, the authoring definitions are in `entity_data.asm`. Since these are currently assembled inline (not read by the build tool), the first version will hand-expand the test data directly in entity_data.asm. The build tool expansion function is for future use when ring data moves to the tool pipeline.

```python
def expand_rings(ring_defs):
    """Expand pattern ring definitions to flat X-sorted list.
    
    Each ring_def is (type, x, y, count, spacing) where:
      type: 'individual', 'hline', 'vline'
      x, y: section-local coords (0-$3FF)
      count: number of rings (1 for individual)
      spacing: pixel spacing between rings
    
    Returns: list of (x, y) tuples, sorted ascending by x, then y.
    """
    rings = []
    for rtype, x, y, count, spacing in ring_defs:
        if rtype == 'individual':
            rings.append((x, y))
        elif rtype == 'hline':
            for i in range(count):
                rings.append((x + i * spacing, y))
        elif rtype == 'vline':
            for i in range(count):
                rings.append((x, y + i * spacing))
    rings.sort(key=lambda r: (r[0], r[1]))
    return rings
```

- [ ] **Step 3: Add unit tests for ring expansion**

```python
def test_expand_rings():
    # H-line of 5 at spacing $10
    result = expand_rings([('hline', 0x80, 0x60, 5, 0x10)])
    assert result == [(0x80, 0x60), (0x90, 0x60), (0xA0, 0x60), (0xB0, 0x60), (0xC0, 0x60)]
    
    # V-line of 3 at spacing $10
    result = expand_rings([('vline', 0x100, 0x40, 3, 0x10)])
    assert result == [(0x100, 0x40), (0x100, 0x50), (0x100, 0x60)]
    
    # Mixed — sorted by X
    result = expand_rings([
        ('individual', 0x200, 0x80),
        ('individual', 0x100, 0x80),
    ])
    assert result == [(0x100, 0x80), (0x200, 0x80)]
```

Run: `python3 tools/ojz_strip_gen.py test`
Expected: tests pass

- [ ] **Step 4: Rewrite entity_data.asm ring lists as flat X-sorted**

Replace the pattern-encoded ring entries with pre-expanded flat lists. Each ring is `dc.w X` / `dc.w Y` (section-local coords, 10-bit values in low bits). Terminated by `dc.l 0`.

Sec0 rings (current: H-line 5@$080,$060 spacing $10; individual $180,$080; individual $1A0,$080):
```asm
OJZ_Sec0_Rings:
        dc.w    $080, $060      ; ring 0 (from H-line)
        dc.w    $090, $060      ; ring 1
        dc.w    $0A0, $060      ; ring 2
        dc.w    $0B0, $060      ; ring 3
        dc.w    $0C0, $060      ; ring 4
        dc.w    $180, $080      ; individual
        dc.w    $1A0, $080      ; individual
        dc.l    0               ; terminator
```

Sec1 rings (current: V-line 3@$100,$040 spacing $10; individual $180,$050; $1C0,$050; $200,$050):
```asm
OJZ_Sec1_Rings:
        dc.w    $100, $040      ; ring 0 (from V-line)
        dc.w    $100, $050      ; ring 1
        dc.w    $100, $060      ; ring 2
        dc.w    $180, $050      ; individual
        dc.w    $1C0, $050      ; individual
        dc.w    $200, $050      ; individual
        dc.l    0               ; terminator
```

Sec2 rings (current: H-line 4@$0C0,$050 spacing $14; V-line 3@$300,$030 spacing $10; individual $200,$070):
```asm
OJZ_Sec2_Rings:
        dc.w    $0C0, $050      ; ring 0 (from H-line)
        dc.w    $0D4, $050      ; ring 1 (spacing $14)
        dc.w    $0E8, $050      ; ring 2
        dc.w    $0FC, $050      ; ring 3
        dc.w    $200, $070      ; individual (X-sorted here)
        dc.w    $300, $030      ; ring 0 (from V-line)
        dc.w    $300, $040      ; ring 1
        dc.w    $300, $050      ; ring 2
        dc.l    0               ; terminator
```

Also update the entity_data.asm header comment to describe the new flat format.

- [ ] **Step 5: Remove pattern-encoding constants from constants.asm**

Remove from `constants.asm`:
```asm
; Ring pattern encoding (ROM format, 32-bit entries)
RING_TYPE_INDIVIDUAL    = $00000000     ; %00 << 30
RING_TYPE_HLINE         = $40000000     ; %01 << 30
RING_TYPE_VLINE         = $80000000     ; %10 << 30
RING_X_SHIFT            = 20            ; bits 29-20
RING_Y_SHIFT            = 10            ; bits 19-10
RING_COUNT_SHIFT        = 5             ; bits 9-5 (value 0-31 = 1-32 rings)
RING_SPACING_SHIFT      = 2             ; bits 4-2
```

Update existing ring-related constants for new format:
```asm
; Ring flat list format (ROM, 4 bytes per ring: dc.w X, dc.w Y)
RING_BUFFER_ENTRY_SIZE  = 6             ; unified buffer: dc.w x, y; dc.b section_id, list_index
```

- [ ] **Step 6: Build and verify**

Run: `./build.sh`
Expected: build succeeds (ring data is just dc.w values, no code reads them yet since ExpandRings hasn't been removed)

- [ ] **Step 7: Commit**

```bash
git add tools/ojz_strip_gen.py data/levels/ojz/act1/entity_data.asm constants.asm
git commit -m "feat(§4.9): flat X-sorted ring lists, remove pattern encoding"
```

---

### Task 3: RAM Layout — Unified Ring Buffer and Scan State

**Files:**
- Modify: `ram.asm`
- Modify: `constants.asm`
- Modify: `structs.asm` (add EntityScanState struct)

- [ ] **Step 1: Research**

Review how sonic_hack organizes ring RAM (Ring_Positions, Ring_Count, Object_Respawn_Table). Check S.C.E. for any improvements. Consider data-oriented layout (struct-of-arrays vs array-of-structs) for the 6-byte ring buffer entries.

- [ ] **Step 2: Add EntityScanState struct to structs.asm**

```asm
; -----------------------------------------------
; Per-section entity scan state (§4.9 camera-driven window)
; One per tracked section (4 max: 2 active + 2 preview neighbors)
; -----------------------------------------------
EntityScanState struct
ess_ring_right_idx   ds.w 1      ; $00 — next unloaded ring index (scanning right)
ess_ring_left_idx    ds.w 1      ; $02 — next unloaded ring index (scanning left)
ess_obj_right_idx    ds.w 1      ; $04 — next unloaded object index (scanning right)
ess_obj_left_idx     ds.w 1      ; $06 — next unloaded object index (scanning left)
ess_rom_ring_ptr     ds.l 1      ; $08 — pointer to section's ROM ring list
ess_rom_obj_ptr      ds.l 1      ; $0C — pointer to section's ROM object list
ess_rom_type_tbl_ptr ds.l 1      ; $10 — pointer to section's ROM type table
ess_origin_x         ds.w 1      ; $14 — section's engine-space X origin
ess_section_id       ds.b 1      ; $16 — section grid index (sec_y * grid_w + sec_x)
ess_pad              ds.b 1      ; $17 — pad to even
EntityScanState endstruct
```

- [ ] **Step 3: Update RAM layout in ram.asm**

Replace the old entity system block:
```asm
; -----------------------------------------------
; Entity System (§4.9 — camera-driven sliding window)
; -----------------------------------------------

; Unified ring buffer — 128 entries × 6 bytes (dc.w x, y; dc.b section_id, list_index)
Ring_Buffer:            ds.b MAX_RING_BUFFER * RING_BUFFER_ENTRY_SIZE  ; 768 bytes

; Ring count (unified)
Ring_Count:             ds.b 1
                        ds.b 1          ; pad

; Entity scan state — 4 tracked sections × EntityScanState_len bytes
Entity_Scan_State:      ds.b MAX_TRACKED_SECTIONS * EntityScanState_len

; Ring state
Ring_Counter:           ds.w 1          ; total collected rings (player HUD)
Ring_Anim_Frame:        ds.b 1          ; global ring animation counter (0-3)
Ring_Anim_Timer:        ds.b 1          ; countdown to next animation tick

; Entity window tracking
Entity_Window_Active:   ds.b 1          ; number of tracked sections (0-4)
                        ds.b 1          ; pad

; Active level pointer
Current_Act_Ptr:        ds.l 1
```

Remove: `Ring_Buffer_0`, `Ring_Buffer_1`, `Ring_Bitmask_0`, `Ring_Bitmask_1`, `Ring_Count_0`, `Ring_Count_1`, `Object_Type_Table`, `Ring_Persist_Bitmask`.

- [ ] **Step 4: Update constants.asm**

Add new constants, update old ones:
```asm
; Entity window (§4.9 camera-driven)
ENTITY_LOAD_BUFFER      = $180   ; pixels ahead/behind camera to load entities
ENTITY_DESPAWN_BUFFER   = $200   ; pixels beyond load buffer to despawn (hysteresis)
MAX_RING_BUFFER         = 128    ; max rings in unified buffer
RING_BUFFER_ENTRY_SIZE  = 6      ; bytes per unified ring buffer entry
MAX_TRACKED_SECTIONS    = 4      ; 2 active + 2 preview neighbors
SCREEN_WIDTH            = 320    ; visible screen width in pixels
```

Remove the old `RING_BUFFER_SIZE = MAX_RINGS_PER_SLOT*RING_BUFFER_ENTRY_SIZE` (512), `RING_BITMASK_SIZE`, `TYPE_TABLE_SIZE`, `MAX_RINGS_PER_SLOT` lines.

- [ ] **Step 5: Build and verify**

Run: `./build.sh`
Expected: build fails — code still references old RAM labels. That's expected; we'll fix references in subsequent tasks.

- [ ] **Step 6: Commit**

```bash
git add ram.asm constants.asm structs.asm
git commit -m "feat(§4.9): unified ring buffer + scan state RAM layout"
```

---

### Task 4: Ring Buffer Operations — Add, Remove, Clear

**Files:**
- Modify: `engine/objects/rings.asm`

- [ ] **Step 1: Research**

Study swap-with-last removal in sonic_hack (if any). Check S.C.E. ring buffer management. Review Gunstar Heroes / Alien Soldier for O(1) entity pool patterns. Verify our 6-byte entry layout is optimal for the hot paths (DrawRings iterates every entry every frame).

- [ ] **Step 2: Write RingBuffer_Add**

Add to `engine/objects/rings.asm`, replacing ExpandRings and RingSpacingTable:

```asm
; -----------------------------------------------
; RingBuffer_Add — append a ring to the unified buffer
;
; In:  d0.w = engine-space X
;      d1.w = engine-space Y
;      d2.b = section_id
;      d3.b = list_index (index in section's ROM ring list)
; Out: carry clear = success, carry set = buffer full
; Clobbers: d4, a0
; -----------------------------------------------
RingBuffer_Add:
        moveq   #0, d4
        move.b  (Ring_Count).w, d4
        cmpi.b  #MAX_RING_BUFFER, d4
        bhs.s   .full

        ; a0 = &Ring_Buffer[count * 6]
        move.w  d4, -(sp)
        add.w   d4, d4                  ; ×2
        add.w   (sp)+, d4               ; ×3 (count*2 + count = count*3)
        add.w   d4, d4                  ; ×6
        lea     (Ring_Buffer).w, a0
        adda.w  d4, a0

        move.w  d0, (a0)+              ; engine_X
        move.w  d1, (a0)+              ; engine_Y
        move.b  d2, (a0)+              ; section_id
        move.b  d3, (a0)+              ; list_index

        addq.b  #1, (Ring_Count).w
        andi.b  #$FE, ccr              ; clear carry
        rts

.full:
        ori.b   #1, ccr                ; set carry
        rts
```

- [ ] **Step 3: Write RingBuffer_Remove**

```asm
; -----------------------------------------------
; RingBuffer_Remove — remove ring at index by swapping with last
;
; In:  d0.w = index to remove (0-based)
; Out: none
; Clobbers: d1-d2, a0-a1
; -----------------------------------------------
RingBuffer_Remove:
        moveq   #0, d1
        move.b  (Ring_Count).w, d1
        subq.b  #1, d1
        bmi.s   .empty                  ; count was 0

        move.b  d1, (Ring_Count).w      ; decrement count

        cmp.w   d1, d0
        beq.s   .was_last               ; removing last entry, nothing to swap

        ; Compute source (last entry) and dest (removed entry) pointers
        ; index × 6: index × 2 + index = index × 3, then × 2
        move.w  d0, d2
        add.w   d2, d2
        add.w   d0, d2
        add.w   d2, d2                  ; d2 = remove_index × 6
        lea     (Ring_Buffer).w, a0
        lea     (a0, d2.w), a0          ; a0 = entry to overwrite

        move.w  d1, d2
        add.w   d2, d2
        add.w   d1, d2
        add.w   d2, d2                  ; d2 = last_index × 6
        lea     (Ring_Buffer).w, a1
        lea     (a1, d2.w), a1          ; a1 = last entry

        ; Copy 6 bytes: last → removed
        move.l  (a1)+, (a0)+           ; X + Y (4 bytes)
        move.w  (a1), (a0)             ; section_id + list_index (2 bytes)

.was_last:
.empty:
        rts
```

- [ ] **Step 4: Write RingBuffer_Clear**

```asm
; -----------------------------------------------
; RingBuffer_Clear — zero the ring count (buffer contents become garbage)
; -----------------------------------------------
RingBuffer_Clear:
        clr.b   (Ring_Count).w
        rts
```

- [ ] **Step 5: Remove ExpandRings and RingSpacingTable**

Delete the `RingSpacingTable` data and entire `ExpandRings` routine from `rings.asm`.

- [ ] **Step 6: Build**

Run: `./build.sh`
Expected: still fails (DrawRings/RingCollision/CollectRing reference old labels). We fix those next.

- [ ] **Step 7: Commit**

```bash
git add engine/objects/rings.asm
git commit -m "feat(§4.9): ring buffer add/remove/clear — swap-with-last O(1)"
```

---

### Task 5: Rewrite DrawRings — Single-Pass Unified Buffer

**Files:**
- Modify: `engine/objects/rings.asm`

- [ ] **Step 1: Research**

Study sonic_hack's ring drawing (DrawRings in Ring_Manager.asm). Check S.C.E. ring rendering. Note how they handle animation and on-screen culling. Our version must iterate the unified buffer with 6-byte stride instead of two 4-byte-stride slot buffers with bitmask checks.

- [ ] **Step 2: Rewrite DrawRings**

Replace the current two-slot-with-bitmask DrawRings with a single-pass over the unified buffer:

```asm
; -----------------------------------------------
; DrawRings — render rings from unified buffer to sprite table
;
; Single pass over Ring_Buffer. No bitmask — if it's in the buffer, it's alive.
; 6-byte stride: dc.w engine_X, engine_Y; dc.b section_id, list_index.
;
; In:  a4 = SAT buffer write pointer
;      d5.w = current VDP sprite count
; Out: a4 advanced, d5 incremented
; Clobbers: d0-d4, d6-d7, a0
; -----------------------------------------------
DrawRings:
        ; --- Animation timer ---
        move.b  (Ring_Anim_Timer).w, d0
        subq.b  #1, d0
        bpl.s   .no_anim_tick
        move.b  #RING_ANIM_SPEED-1, d0
        move.b  (Ring_Anim_Frame).w, d1
        addq.b  #1, d1
        cmpi.b  #RING_ANIM_FRAMES, d1
        blo.s   .frame_ok
        moveq   #0, d1
.frame_ok:
        move.b  d1, (Ring_Anim_Frame).w
.no_anim_tick:
        move.b  d0, (Ring_Anim_Timer).w

        ; Cache camera
        move.w  (Camera_X).w, d6
        move.w  (Camera_Y).w, d7

        ; Ring count
        moveq   #0, d1
        move.b  (Ring_Count).w, d1
        beq.s   .done
        subq.w  #1, d1                  ; dbf adjust

        lea     (Ring_Buffer).w, a0

.ring_loop:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bhs.s   .done

        ; On-screen culling — X
        move.w  (a0), d2                ; engine X
        sub.w   d6, d2                  ; screen X
        move.w  d2, d0
        addi.w  #16, d0
        cmpi.w  #336, d0               ; 320 + 16
        bhi.s   .skip_ring

        ; On-screen culling — Y
        move.w  2(a0), d3              ; engine Y
        sub.w   d7, d3                  ; screen Y
        move.w  d3, d0
        addi.w  #16, d0
        cmpi.w  #240, d0               ; 224 + 16
        bhi.s   .skip_ring

        ; --- Write SAT entry ---
        subi.w  #8, d3
        addi.w  #VDP_SPRITE_Y_OFFSET, d3
        move.w  d3, (a4)+              ; Y position
        move.b  #$05, (a4)+            ; size 2×2 (16×16)
        addq.b  #1, d5
        move.b  d5, (a4)+              ; link
        move.w  #VRAM_TEST_OBJ, (a4)+  ; tile attrs (placeholder)
        subi.w  #8, d2
        addi.w  #VDP_SPRITE_X_OFFSET, d2
        bne.s   .x_ok
        moveq   #1, d2
.x_ok:
        move.w  d2, (a4)+              ; X position

.skip_ring:
        addq.w  #6, a0                 ; 6-byte stride
        dbf     d1, .ring_loop

.done:
        rts
```

- [ ] **Step 3: Build**

Run: `./build.sh`
Expected: still fails (RingCollision/CollectRing). Next task.

- [ ] **Step 4: Commit**

```bash
git add engine/objects/rings.asm
git commit -m "feat(§4.9): single-pass DrawRings for unified ring buffer"
```

---

### Task 6: Rewrite RingCollision and CollectRing — Buffer Removal

**Files:**
- Modify: `engine/objects/rings.asm`

- [ ] **Step 1: Research**

Study sonic_hack's ring collision + collection (CollectRing in Ring_Manager.asm). Note how it handles removal. Key difference from old system: CollectRing now calls RingBuffer_Remove instead of setting a bitmask bit. The ring index used for removal is the iteration index, but since RingBuffer_Remove swaps with last, we need to be careful: after removing index N, the new entry at N (swapped from end) must be re-tested, and the loop count decrements.

- [ ] **Step 2: Rewrite RingCollision**

```asm
; -----------------------------------------------
; RingCollision — test player(s) vs rings in unified buffer
;
; Iterates unified Ring_Buffer (6-byte stride). No bitmask.
; On collection, calls RingBuffer_Remove which swaps-with-last,
; so we re-check the current index and decrement remaining count.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a2
; -----------------------------------------------
RingCollision:
        lea     (Player_1).w, a2
        move.w  #NUM_PLAYERS-1, d7

.player_loop:
        tst.w   SST_code_addr(a2)
        beq.w   .next_player

        move.w  SST_x_pos(a2), d4       ; cache player X
        move.w  SST_y_pos(a2), d5       ; cache player Y

        moveq   #0, d6
        move.b  (Ring_Count).w, d6
        beq.w   .next_player

        lea     (Ring_Buffer).w, a0
        moveq   #0, d3                  ; d3 = current index

.ring_loop:
        cmp.w   d6, d3
        bhs.w   .next_player

        ; X axis: player width vs ring 16px
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #RING_WIDTH, d1

        aabb_axis_test d4,(a0),d0,d1,d0,d1,d2,.skip_ring,rx

        ; Y axis: player height vs ring 16px
        moveq   #0, d0
        move.b  SST_height_pixels(a2), d0
        moveq   #RING_HEIGHT, d1

        aabb_axis_test d5,2(a0),d0,d1,d0,d1,d2,.skip_ring,ry

        ; Overlap — collect this ring
        addq.w  #1, (Ring_Counter).w

        ; Remove from buffer (swap-with-last)
        movem.l d3-d7/a0/a2, -(sp)
        move.w  d3, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d3-d7/a0/a2

        ; After remove: count decremented, entry at d3 is now the old last entry.
        ; Re-read count, DON'T advance d3 or a0 — re-check swapped entry.
        moveq   #0, d6
        move.b  (Ring_Count).w, d6
        bra.s   .ring_loop

.skip_ring:
        addq.w  #6, a0                 ; next entry (6-byte stride)
        addq.w  #1, d3
        bra.s   .ring_loop

.next_player:
        lea     SST_len(a2), a2
        dbf     d7, .player_loop
        rts
```

- [ ] **Step 3: Remove old CollectRing**

Delete the old `CollectRing` routine (bitmask-based). Ring collection is now inline in RingCollision (addq.w #1, Ring_Counter + RingBuffer_Remove call).

- [ ] **Step 4: Build**

Run: `./build.sh`
Expected: still fails — entity_loader.asm and section.asm reference old labels. Next tasks.

- [ ] **Step 5: Commit**

```bash
git add engine/objects/rings.asm
git commit -m "feat(§4.9): RingCollision rewrite — buffer removal on collect"
```

---

### Task 7: Remove Old Entity Loader Code

**Files:**
- Modify: `engine/objects/entity_loader.asm`

- [ ] **Step 1: Research**

Review what DespawnSlotObjects looks like and confirm it's still needed for teleport shift. Review all callers of the routines being removed to ensure nothing else depends on them.

- [ ] **Step 2: Remove LoadTypeTable**

Delete the entire `LoadTypeTable` routine. Type tables will be read directly from ROM at spawn time.

- [ ] **Step 3: Remove SpawnSectionObjects**

Delete the entire `SpawnSectionObjects` routine. Object spawning will be handled by EntityWindow_Scan.

- [ ] **Step 4: Remove Section_LoadSlotEntities**

Delete the entire `Section_LoadSlotEntities` routine. Entity loading is now camera-driven.

- [ ] **Step 5: Remove Save/RestoreRingBitmask routines**

Delete all four routines: `SaveRingBitmask_0`, `SaveRingBitmask_1`, `RestoreRingBitmask_0`, `RestoreRingBitmask_1`.

- [ ] **Step 6: Keep DespawnSlotObjects**

Verify `DespawnSlotObjects` is unchanged — it's still needed by EntityWindow_TeleportShift for despawning out-of-range objects.

- [ ] **Step 7: Update file header comment**

Update the file header from "Entity loader — type tables, section object spawn/despawn" to reflect the reduced scope.

- [ ] **Step 8: Build**

Run: `./build.sh`
Expected: still fails — section.asm calls removed routines. Next task fixes that.

- [ ] **Step 9: Commit**

```bash
git add engine/objects/entity_loader.asm
git commit -m "refactor(§4.9): remove bulk-load entity routines — camera window replaces"
```

---

### Task 8: EntityWindow Core — Init, Scan, TeleportShift

**Files:**
- Create: `engine/objects/entity_window.asm`

This is the core of the new system. EntityWindow_Init populates scan state at level start. EntityWindow_Scan runs per-frame. EntityWindow_TeleportShift handles teleport.

- [ ] **Step 1: Research**

Deep dive into sonic_hack's `ChkLoadObj` / `SingleObjectLoad` / `BuildRings` for the sliding pointer pattern. Study the Y range gate implementation. Note how sonic_hack's `Object_Load_Addr_Front` and `Object_Load_Addr_Back` track left/right edges. Study how the indices are reset on level transitions. Check S.C.E. for improvements.

- [ ] **Step 2: Write EntityWindow_InitSection helper**

A helper that populates one EntityScanState block from a section definition:

```asm
; -----------------------------------------------
; EntityWindow_InitSection — populate scan state for one section
;
; In:  a0 = Sec struct pointer (ROM)
;      a1 = EntityScanState pointer (RAM)
;      d0.w = section origin X (engine-space)
;      d1.b = section_id
; Out: none
; Clobbers: d2, a2
; -----------------------------------------------
EntityWindow_InitSection:
        ; Ring list pointer
        move.l  Sec_sec_rings(a0), ess_rom_ring_ptr(a1)
        ; Object list pointer
        move.l  Sec_sec_objects(a0), ess_rom_obj_ptr(a1)
        ; Type table pointer
        move.l  Sec_sec_type_table(a0), ess_rom_type_tbl_ptr(a1)
        ; Origin X
        move.w  d0, ess_origin_x(a1)
        ; Section ID
        move.b  d1, ess_section_id(a1)
        clr.b   ess_pad(a1)
        ; Reset load indices to 0 (scan from beginning)
        clr.w   ess_ring_right_idx(a1)
        clr.w   ess_ring_left_idx(a1)
        clr.w   ess_obj_right_idx(a1)
        clr.w   ess_obj_left_idx(a1)
        rts
```

- [ ] **Step 3: Write EntityWindow_Init**

Called from Section_Init. Populates scan state for initial 2 active sections + up to 2 preview neighbors, then runs one full scan pass.

```asm
; -----------------------------------------------
; EntityWindow_Init — set up entity window at level start
;
; Populates scan state for active sections and neighbors.
; Runs initial scan to load entities in camera range.
;
; In:  none (reads Slot_Section_Map, Current_Act_Ptr, Camera_X)
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
EntityWindow_Init:
        ; Clear ring buffer
        bsr.w   RingBuffer_Clear
        clr.b   (Entity_Window_Active).w

        ; Populate scan state for each tracked section
        lea     (Entity_Scan_State).w, a3   ; a3 = scan state array base
        moveq   #0, d7                      ; d7 = tracked section count

        ; --- BWD neighbor (slot 0 sec_x - 1) ---
        ; [code resolves BWD section, calls EntityWindow_InitSection if valid]
        ; ... (similar to Section_Init's neighbor resolution)

        ; --- Active slot 0 ---
        ; ... 

        ; --- Active slot 1 ---
        ; ...

        ; --- FWD neighbor (slot 1 sec_x + 1) ---
        ; ...

        move.b  d7, (Entity_Window_Active).w

        ; Run initial full scan (load everything in camera range)
        bsr.w   EntityWindow_Scan
        rts
```

The actual implementation will resolve each section via Section_GetSecPtrXY, determine its origin_x from slot position, and call EntityWindow_InitSection. For BWD/FWD neighbors, origin is computed as slot 0 origin - SECTION_SIZE or slot 1 origin + SECTION_SIZE.

- [ ] **Step 4: Write EntityWindow_ScanRingsRight helper**

For one section's scan state: scan forward from right_load_index, spawn rings that fall within the load window.

```asm
; -----------------------------------------------
; EntityWindow_ScanRingsRight — spawn rings entering right edge
;
; In:  a1 = EntityScanState pointer
;      d6.w = right edge threshold (Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER)
; Out: none
; Clobbers: d0-d3, a0, a2
; -----------------------------------------------
EntityWindow_ScanRingsRight:
        move.l  ess_rom_ring_ptr(a1), d0
        beq.s   .done                   ; NULL = no rings

        movea.l d0, a0                  ; a0 = ROM ring list base
        move.w  ess_ring_right_idx(a1), d0  ; d0 = current index
        move.w  ess_origin_x(a1), d3    ; d3 = section origin X

        ; Advance a0 to current index (index × 4 bytes per ROM entry)
        move.w  d0, d1
        lsl.w   #2, d1
        adda.w  d1, a0

.scan_loop:
        move.l  (a0), d1
        beq.s   .done                   ; terminator

        ; Extract section-local X from ROM entry
        move.w  (a0), d2                ; d2 = section_local_X (bits 9-0)
        andi.w  #$3FF, d2
        add.w   d3, d2                  ; d2 = engine_X

        ; Past right edge? Stop scanning (list is X-sorted)
        cmp.w   d6, d2
        bhi.s   .done

        ; Y range gate
        move.w  2(a0), d1              ; section_local_Y
        andi.w  #$3FF, d1
        ; (add origin_y when vertical sections exist — currently 0)
        
        move.w  (Camera_Y).w, d1
        ; ... Y gate check omitted for brevity (compare abs distance)

        ; Spawn this ring
        move.w  d2, d0                 ; d0 = engine_X
        ; d1 = engine_Y (computed above)
        move.b  ess_section_id(a1), d2 ; d2.b = section_id
        move.w  ess_ring_right_idx(a1), d3_temp
        move.b  d3_temp, d3            ; d3.b = list_index
        bsr.w   RingBuffer_Add

        ; Advance index
        addq.w  #1, ess_ring_right_idx(a1)
        addq.w  #4, a0                 ; next ROM entry
        move.w  ess_origin_x(a1), d3   ; restore origin_x
        bra.s   .scan_loop

.done:
        rts
```

(The actual implementation will flesh out Y gate, handle left-edge scanning, and object scanning analogously.)

- [ ] **Step 5: Write EntityWindow_Scan**

The per-frame main scan routine:

```asm
; -----------------------------------------------
; EntityWindow_Scan — per-frame camera-range entity scan
;
; Called once per frame after Camera_Update.
; For each tracked section: spawn entities entering range, despawn those leaving.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
EntityWindow_Scan:
        ; Compute window edges
        move.w  (Camera_X).w, d6
        ; d6 = left despawn edge = Camera_X - ENTITY_DESPAWN_BUFFER
        ; d7 = right load edge = Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER

        ; For each tracked section: scan right edge, scan left edge
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d5
        move.b  (Entity_Window_Active).w, d5
        beq.s   .despawn
        subq.w  #1, d5

.section_loop:
        lea     (a3), a1               ; a1 = current scan state
        ; ... call ScanRingsRight, ScanRingsLeft, ScanObjectsRight, ScanObjectsLeft
        lea     EntityScanState_len(a3), a3
        dbf     d5, .section_loop

.despawn:
        ; Despawn out-of-range rings
        bsr.w   EntityWindow_DespawnRings
        ; Despawn out-of-range objects
        bsr.w   EntityWindow_DespawnObjects
        rts
```

- [ ] **Step 6: Write EntityWindow_DespawnRings**

```asm
; -----------------------------------------------
; EntityWindow_DespawnRings — remove rings outside camera range
;
; Iterates Ring_Buffer. Any ring outside [Camera_X - despawn_buf,
; Camera_X + screen_w + despawn_buf] is removed via swap-with-last.
; Iterates backward to handle swap-with-last safely.
; -----------------------------------------------
EntityWindow_DespawnRings:
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .done

        move.w  (Camera_X).w, d6
        move.w  d6, d7
        subi.w  #ENTITY_DESPAWN_BUFFER, d6    ; d6 = left edge
        addi.w  #SCREEN_WIDTH+ENTITY_DESPAWN_BUFFER, d7  ; d7 = right edge

        ; Iterate backward (index = count-1 down to 0)
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0

.loop:
        ; Compute entry address: index × 6
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  ; d0 = index × 6
        move.w  (a0, d0.w), d1          ; engine_X

        cmp.w   d6, d1
        blt.s   .remove
        cmp.w   d7, d1
        bgt.s   .remove
        bra.s   .next

.remove:
        movem.l d5-d7/a0, -(sp)
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d5-d7/a0

.next:
        dbf     d5, .loop

.done:
        rts
```

- [ ] **Step 7: Write EntityWindow_DespawnObjects**

```asm
; -----------------------------------------------
; EntityWindow_DespawnObjects — delete dynamic objects outside range
;
; Iterates Dynamic_Slots. Objects with a slot tag whose SST_x_pos
; is outside despawn range get DeleteObject'd.
; -----------------------------------------------
EntityWindow_DespawnObjects:
        move.w  (Camera_X).w, d6
        subi.w  #ENTITY_DESPAWN_BUFFER, d6
        move.w  (Camera_X).w, d7
        addi.w  #SCREEN_WIDTH+ENTITY_DESPAWN_BUFFER, d7

        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5

.loop:
        tst.w   SST_code_addr(a0)
        beq.s   .next

        cmpi.b  #SLOT_TAG_UNTAGGED, SLOT_TAG_OFFSET(a0)
        beq.s   .next                   ; untagged = not entity-spawned

        move.w  SST_x_pos(a0), d0
        cmp.w   d6, d0
        blt.s   .despawn
        cmp.w   d7, d0
        ble.s   .next

.despawn:
        movem.l d5-d7/a0, -(sp)
        jsr     DeleteObject
        movem.l (sp)+, d5-d7/a0

.next:
        lea     SST_len(a0), a0
        dbf     d5, .loop
        rts
```

- [ ] **Step 8: Write EntityWindow_TeleportShift**

```asm
; -----------------------------------------------
; EntityWindow_TeleportShift — shift on-screen entities at teleport
;
; In:  d0.w = shift amount (+SECTION_SHIFT or -SECTION_SHIFT)
; Out: none
; Clobbers: d0-d5, a0-a1
; -----------------------------------------------
EntityWindow_TeleportShift:
        move.w  d0, d4                  ; d4 = shift

        ; Compute keep-range: Camera_X ± $180 (shifted by d4)
        move.w  (Camera_X).w, d2
        move.w  d2, d3
        subi.w  #ENTITY_LOAD_BUFFER, d2 ; d2 = left keep edge
        addi.w  #SCREEN_WIDTH+ENTITY_LOAD_BUFFER, d3 ; d3 = right keep edge

        ; --- Shift/despawn rings ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0

.ring_loop:
        ; Address of entry[d5]
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  ; d0 = index × 6

        move.w  (a0, d0.w), d1          ; engine_X
        cmp.w   d2, d1
        blt.s   .ring_remove
        cmp.w   d3, d1
        bgt.s   .ring_remove

        ; In range — shift position
        add.w   d4, (a0, d0.w)
        bra.s   .ring_next

.ring_remove:
        movem.l d2-d5/a0, -(sp)
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d2-d5/a0
        ; Don't decrement d5 — swap-with-last puts new entry here
        ; But since we iterate backward, we need to re-check this index
        ; Actually d5 stays same, count decremented, loop continues
        bra.s   .ring_check_bounds

.ring_next:
        dbf     d5, .ring_loop
        bra.s   .rings_done
.ring_check_bounds:
        dbf     d5, .ring_loop

.rings_done:
        ; --- Shift/despawn objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5

.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next

        cmpi.b  #SLOT_TAG_UNTAGGED, SLOT_TAG_OFFSET(a0)
        beq.s   .obj_next

        move.w  SST_x_pos(a0), d1
        cmp.w   d2, d1
        blt.s   .obj_despawn
        cmp.w   d3, d1
        bgt.s   .obj_despawn

        ; In range — shift
        add.w   d4, SST_x_pos(a0)
        bra.s   .obj_next

.obj_despawn:
        movem.l d2-d5/a0, -(sp)
        jsr     DeleteObject
        movem.l (sp)+, d2-d5/a0

.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

        ; --- Reset scan state ---
        ; Rebuild scan state for new section configuration
        ; (caller will update Slot_Section_Map before calling us,
        ;  and EntityWindow_RebuildScanState re-populates from current map)
        bsr.w   EntityWindow_RebuildScanState
        rts
```

- [ ] **Step 9: Write EntityWindow_RebuildScanState**

Re-populates the scan state array from current Slot_Section_Map (called after teleport updates the map).

```asm
; -----------------------------------------------
; EntityWindow_RebuildScanState — repopulate scan state from slot map
; Called after teleport updates Slot_Section_Map.
; -----------------------------------------------
EntityWindow_RebuildScanState:
        ; Same logic as EntityWindow_Init's section population,
        ; but doesn't clear ring buffer or run initial scan.
        ; Resolves 4 sections (BWD neighbor, slot 0, slot 1, FWD neighbor),
        ; populates Entity_Scan_State entries, sets Entity_Window_Active count.
        ; Sets load indices based on camera position within each section's
        ; coordinate range (binary search or linear scan to find the right index).
        ; ...
        rts
```

- [ ] **Step 10: Include entity_window.asm in the build**

Add `include "engine/objects/entity_window.asm"` to the appropriate location in `S4.asm` or the engine include chain.

- [ ] **Step 11: Build**

Run: `./build.sh`
Expected: still fails — section.asm entity blocks not updated yet.

- [ ] **Step 12: Commit**

```bash
git add engine/objects/entity_window.asm S4.asm
git commit -m "feat(§4.9): EntityWindow core — Init, Scan, TeleportShift"
```

---

### Task 9: Wire Section.asm — Replace Entity Lifecycle Blocks

**Files:**
- Modify: `engine/level/section.asm`

- [ ] **Step 1: Research**

Re-read Section_Init, Section_TeleportFwd, Section_TeleportBwd entity blocks. Map all references to removed routines (Section_LoadSlotEntities, SaveRingBitmask, RestoreRingBitmask, Ring_Bitmask_0/1, Ring_Count_0/1, Ring_Buffer_0/1).

- [ ] **Step 2: Update Section_Init**

Replace the entity loading block (~lines 75-105) with:
```asm
        ; -- §4.9: camera-driven entity window init --
        jsr     EntityWindow_Init
```

Remove:
- Ring bitmask clearing loop
- Two Section_GetSlotDef + Section_LoadSlotEntities blocks

- [ ] **Step 3: Update Section_TeleportFwd**

Replace the entity lifecycle block (~lines 386-458) with:
```asm
        ; -- §4.9: shift on-screen entities, despawn rest, reset scan state --
        move.w  #-SECTION_SHIFT, d0
        jsr     EntityWindow_TeleportShift
```

Remove:
- Save bitmask derivation + SaveRingBitmask_0/1 calls
- DespawnSlotObjects calls
- Ring buffer/bitmask clearing
- Section_GetSlotDef + Section_LoadSlotEntities pairs
- RestoreRingBitmask_0/1 calls

- [ ] **Step 4: Update Section_TeleportBwd**

Same pattern, with `+SECTION_SHIFT`:
```asm
        ; -- §4.9: shift on-screen entities, despawn rest, reset scan state --
        move.w  #SECTION_SHIFT, d0
        jsr     EntityWindow_TeleportShift
```

- [ ] **Step 5: Build**

Run: `./build.sh`
Expected: still fails — test code references old labels.

- [ ] **Step 6: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§4.9): wire EntityWindow into Section_Init/TeleportFwd/Bwd"
```

---

### Task 10: Wire Test — Update ojz_scroll_test.asm

**Files:**
- Modify: `test/ojz_scroll_test.asm`

- [ ] **Step 1: Research**

Read current test update loop. Identify where EntityWindow_Scan should be called (after Camera_Update, before RunObjects). Verify RingCollision call site is still correct.

- [ ] **Step 2: Add EntityWindow_Scan call**

In `GameState_OJZScroll_Update`, add after `jsr Camera_Update` and `jsr Section_Check`:
```asm
        ; -- §4.9: per-frame entity window scan --
        jsr     EntityWindow_Scan
```

The call order should be: Camera_Update → Section_Check → EntityWindow_Scan → Section_UpdateColumns → RunObjects → TouchResponse → RingCollision → Render_Sprites.

- [ ] **Step 3: Build and verify**

Run: `./build.sh`
Expected: build succeeds (all old references removed, all new code wired).

- [ ] **Step 4: Commit**

```bash
git add test/ojz_scroll_test.asm
git commit -m "feat(§4.9): wire EntityWindow_Scan into scroll test update loop"
```

---

### Task 11: Object Spawning via Window — ROM Type Table Reads

**Files:**
- Modify: `engine/objects/entity_window.asm`

- [ ] **Step 1: Research**

Review how SpawnSectionObjects extracted type/subtype/position from the 32-bit object entry and looked up the ObjDef pointer from Object_Type_Table. The new code does the same but reads the type table directly from ROM (via ess_rom_type_tbl_ptr).

- [ ] **Step 2: Write EntityWindow_SpawnObject helper**

```asm
; -----------------------------------------------
; EntityWindow_SpawnObject — spawn one object from ROM entry
;
; In:  d0.l = 32-bit object entry from ROM
;      a1 = EntityScanState pointer (for type table and origin)
; Out: none
; Clobbers: d0-d3, a0-a2
; -----------------------------------------------
EntityWindow_SpawnObject:
        ; Extract type index: bits 9-5
        move.w  d0, d1
        lsr.w   #5, d1
        andi.w  #$1F, d1                ; d1 = type index

        ; Extract subtype: bits 4-0
        move.w  d0, d2
        andi.w  #$1F, d2                ; d2.b = subtype

        ; Look up ObjDef from ROM type table
        move.l  ess_rom_type_tbl_ptr(a1), d3
        beq.s   .no_type_table
        movea.l d3, a2
        ; Type table format: dc.b count, pad; dc.l ObjDef × count
        moveq   #0, d3
        move.b  (a2), d3                ; d3 = entry count
        cmp.w   d3, d1
        bhs.s   .skip                   ; type index >= count
        addq.w  #2, a2                  ; skip count + pad
        lsl.w   #2, d1                  ; type × 4
        movea.l (a2, d1.w), a2          ; a2 = ObjDef pointer
        move.l  a2, d3
        beq.s   .skip                   ; NULL ObjDef

        ; Extract X: bits 29-20
        move.l  d0, d1
        swap    d1
        lsr.w   #4, d1
        andi.w  #$3FF, d1
        add.w   ess_origin_x(a1), d1    ; d1 = engine-space X
        move.w  d1, d0                  ; d0 = X for Load_Object

        ; Extract Y: bits 19-10
        ; ... (same extraction as SpawnSectionObjects)
        ; d1 = engine-space Y

        ; d0=X, d1=Y, a1=ObjDef (in a2), d2.b=subtype
        movea.l a2, a1                  ; a1 = ObjDef for Load_Object
        jsr     Load_Object
        rts

.no_type_table:
.skip:
        rts
```

- [ ] **Step 3: Integrate into ScanObjectsRight/Left**

Wire EntityWindow_SpawnObject into the object scanning loops (similar to ring scanning but calls SpawnObject instead of RingBuffer_Add).

- [ ] **Step 4: Build and test**

Run: `./build.sh`
Expected: builds. Load in emulator — objects should appear as camera scrolls into range.

- [ ] **Step 5: Commit**

```bash
git add engine/objects/entity_window.asm
git commit -m "feat(§4.9): ROM type table reads for object spawning via window"
```

---

### Task 12: Emulator Verification and Bug Fixes

**Files:**
- Potentially any of the above

- [ ] **Step 1: Build and load in Exodus**

Run: `./build.sh`
Load `s4.bin` in Exodus emulator.

- [ ] **Step 2: Test ring loading on scroll right**

Scroll right through sections 0, 1, 2. Verify:
- Rings appear as they scroll into view (not all at once)
- Ring count in Ring_Count matches expected visible rings
- Rings in Ring_Buffer have correct engine_X/Y values

Use Exodus MCP: `emulator_read_memory` to inspect Ring_Buffer and Ring_Count.

- [ ] **Step 3: Test ring collection**

Collect rings by walking through them. Verify:
- Ring_Counter increments
- Ring_Count decrements
- Collected ring disappears from buffer
- Other rings remain (swap-with-last preserves them)

- [ ] **Step 4: Test ring despawn on scroll**

Scroll past rings, then scroll back. Verify:
- Rings despawn when off-screen (Ring_Count decreases)
- Rings reload when scrolling back into range
- No instant respawn at teleport boundary

- [ ] **Step 5: Test teleport boundary**

Cross the teleport threshold going right. Verify:
- On-screen rings shift position correctly
- Off-screen rings are removed
- Scan state resets — new section's rings load on next frames
- No visual pop-in or glitches

- [ ] **Step 6: Test backward scroll + teleport**

Scroll left back across teleport. Verify same behavior in reverse.

- [ ] **Step 7: Test object loading**

Verify objects (TestSolid blocks) appear in correct positions per section. Verify they despawn when scrolling away and don't duplicate.

- [ ] **Step 8: Fix any bugs found**

Address issues discovered during testing. Common suspects:
- Off-by-one in load indices
- Wrong origin_x for neighbor sections
- Scan state not reset correctly on teleport
- Ring buffer overflow not handled

- [ ] **Step 9: Commit fixes**

```bash
git add -A
git commit -m "fix(§4.9): entity window bug fixes from emulator testing"
```

---

### Task 13: Documentation and Cleanup

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`
- Modify: `constants.asm` (final cleanup of any stale constants)

- [ ] **Step 1: Update ENGINE_ARCHITECTURE.md**

Update the §4.9 entity management section to describe the camera-driven sliding window system instead of the teleport-triggered bulk load. Key changes:
- Ring format: flat X-sorted instead of pattern-encoded
- Unified ring buffer instead of per-slot buffers
- No bitmask persistence
- EntityWindow_Scan per-frame instead of Section_LoadSlotEntities at teleport
- ROM type table reads instead of RAM copy

- [ ] **Step 2: Clean up any remaining stale constants**

Check `constants.asm` for any orphaned constants (MAX_RINGS_PER_SLOT, RING_BITMASK_SIZE, TYPE_TABLE_SIZE if not used elsewhere).

- [ ] **Step 3: Verify build is clean**

Run: `./build.sh`
Expected: builds without warnings.

- [ ] **Step 4: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md constants.asm
git commit -m "docs(§4.9): architecture update — camera-driven entity window"
```

- [ ] **Step 5: Final build + smoke test**

Build and load in emulator one final time. Quick scroll through all sections, collect some rings, cross teleport boundaries in both directions. Verify everything works.
