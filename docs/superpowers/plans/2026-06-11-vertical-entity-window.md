# Vertical Entity Window (§4.9 Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Y dimension to the camera-driven entity window — entities in lower section rows load/despawn correctly, with S3K-style Y banding for rings and objects.

**Architecture:** `Entity_Scan_State` grows 2 → 4 entries (slot L/R × section rows r/r+1), spawn paths gain a per-entry Y origin and a camY band check (`OEF_ANY_Y` opt-out), a per-entry loaded bitmask makes Y re-scans and teleport populates idempotent, and Y teleports migrate bitmasks between row entries. Spec: `docs/superpowers/specs/2026-06-11-vertical-entity-window-design.md`.

**Tech Stack:** AS Macro Assembler (68000), Exodus MCP for verification. Build: `./build.sh` (errors in s4.log). NO emulator auto-launch — Exodus is already running; use `emulator_reload_rom` + `emulator_load_symbols`.

**Branch:** create `vertical-entity-window` from master before Task 1; merge back in Task 8.

**Conventions reminders (CODING_CONVENTIONS.md is law):** `.s`/`.w` on every branch; `function` for compile-time math; no `mulu`/`divu`; struct guards (`if X_len <> ...`) must be updated when structs change.

**Verification pattern used throughout** (every task): build, then
```
mcp: emulator_reload_rom path=/home/volence/sonic_hacks/s4_engine/s4.bin
mcp: emulator_load_symbols path=/home/volence/sonic_hacks/s4_engine/s4.lst
```
Drive the camera by writing Player_1 position (x_pos longword at Player_1+2, y_pos at Player_1+6; camera follows at ≤16px/frame, world coords are $200-based on both axes):
```
mcp: emulator_write_memory addr=<Player_1+2> bytes=XXXXXXXXYYYYYYYY   ; 16.16 x, then 16.16 y
```

---

## Current-state facts the implementer needs (verified 2026-06-11)

- `engine/objects/entity_window.asm` (953 lines): all routines named below live here.
- `EntityScanState` struct at `structs.asm:228-243`: $18 bytes, guard asserts $18. `ess_pad` byte at $17 is free.
- `ram.asm:341`: `Entity_Scan_State: ds.b MAX_TRACKED_SECTIONS * EntityScanState_len` — `MAX_TRACKED_SECTIONS = 4` already (constants.asm:366), so 2 entries of headroom already allocated.
- `Entity_Window_Active` (ram.asm:349) is today a **count** (0-2). Becomes a 4-bit validity mask.
- Spawn paths hardcode `addi.w #SLOT_ORIGIN_U, d1` in THREE places: `EntityWindow_ScanRingsRight` (~line 447), `EntityWindow_PopulateSectionRings` (~line 520), `EntityWindow_ScanObjectsRight` (~line 593).
- The X scan is a **right-edge ratchet**: `ScanRingsRight`/`ScanObjectsRight` walk from index 0 (or last stop) to `Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER`; there is no left edge. Active-section entities never X-despawn (`.check_active` in both Despawn routines keeps them). The Y re-scan therefore walks `0..right_idx`.
- **Pre-existing bug this plan fixes:** `RingBuffer_Add` (engine/objects/rings.asm:16) has no dedupe; `EntityWindow_TeleportShift` keeps in-range rings, then `RebuildScanState` → `PopulateSectionRings` re-adds the same `(section_id, list_index)` rings → duplicate buffer entries. The loaded bitmask (Task 4) fixes this.
- Y teleports exist: `Section_TeleportDown/Up` (engine/level/section.asm:506+) advance both slots' sec_y, call `EntityWindow_TeleportShiftY` (section.asm:523, 582).
- `Section_GetSecPtrXY` (section.asm:~125): in d2.b=sec_x, d3.b=sec_y, a2=Act ptr; out a0=Sec ptr, **Z set if out of range (a0=0)** — handles row ≥ grid_h for free.
- `SLOT_ORIGIN_U = $0200`, `SLOT_ORIGIN_D = $0A00` (constants.asm:211-212) — lower-row Y origin constant already exists.
- `SLOT_TAG_LEFT/RIGHT/UP/DOWN = 0/1/2/3`, `SLOT_TAG_UNTAGGED = $FF` (constants.asm:388-392). slot_tag becomes "entry index 0-3"; bit 7 of slot_tag becomes the per-SST ANY_Y flag (an ANY_Y object's tag is $80+idx, never $FF, so the exact `cmpi.b #SLOT_TAG_UNTAGGED` checks stay valid).
- Object placement word bit 15 = `OEF_ANY_Y` (constants.asm:396); `tst.w`/`bmi` tests it for free. `objentry x,y,type[,sub][,flags]` macro (macros.asm:172) takes pre-shifted flag masks: `(1<<OEF_ANY_Y)`.
- Ring ROM entries: `dc.w x, y`, terminator `dc.l 0`. Object ROM entries: 6 bytes `dc.w x, y, flags|type|sub`, terminator `dc.w -1`.
- Test data lives in `data/levels/ojz/act1/entity_data.asm`; Sec3-8 (rows 1-2) are empty stubs at lines 104-144. Sections are 2048×2048; OJZ act1 grid is 3×3.
- `EntityWindow_Scan` is called per frame from `test/ojz_scroll_test.asm:157`. `EntityWindow_Init` from `section.asm:41`.

---

### Task 1: Groundwork — struct fields, constants, RAM

**Files:**
- Modify: `structs.asm` (EntityScanState, ~line 228)
- Modify: `constants.asm` (after ENTITY_DESPAWN_BUFFER, ~line 368)
- Modify: `ram.asm` (after Entity_Window_Active, ~line 349)

- [ ] **Step 1: Extend EntityScanState**

In `structs.asm`, replace the `ess_pad` line and the guard:

```asm
ess_origin_x         ds.w 1      ; $14 — section's engine-space X origin
ess_section_id       ds.b 1      ; $16 — section grid index (sec_y * grid_w + sec_x)
ess_entry_idx        ds.b 1      ; $17 — this entry's index (0-3) — loaded-mask base derives from it
ess_origin_y         ds.w 1      ; $18 — section's engine-space Y origin (§4.9 phase 2)
EntityScanState endstruct

    if EntityScanState_len <> $1A
      error "EntityScanState struct is \{EntityScanState_len} bytes, expected $1A"
```

- [ ] **Step 2: Add constants**

In `constants.asm` directly under `ENTITY_DESPAWN_BUFFER` (line 368):

```asm
ENTITY_LOAD_BUFFER_Y    = $100          ; pixels above/below camera to load entities (§4.9 ph2)
ENTITY_DESPAWN_BUFFER_Y = $180          ; Y despawn distance (> load = hysteresis)
ENTITY_LOADED_SLOT_SIZE = 32            ; per-entry loaded bitmask: 16B rings + 16B objects
ENTITY_LOADED_OBJ_OFFSET = 16           ; object bits start mid-slot
```

- [ ] **Step 3: Add RAM**

In `ram.asm` directly after `Entity_Window_Active`:

```asm
Entity_Loaded_Masks:    ds.b MAX_TRACKED_SECTIONS * ENTITY_LOADED_SLOT_SIZE ; 128B — per-entry ring/obj loaded bits (§4.9 ph2)
Camera_Y_Coarse_Prev:   ds.w 1          ; camY & $FF80 at last vertical re-scan
```

- [ ] **Step 4: Build**

Run: `./build.sh` — expect `Build complete`. The struct guard catches a mis-sized struct at build time. Nothing reads the new fields yet.

- [ ] **Step 5: Commit**

```bash
git add structs.asm constants.asm ram.asm
git commit -m "feat(entity-window): groundwork — ess_origin_y/entry_idx, Y-band constants, loaded-mask RAM"
```

---

### Task 2: Quadrant window — 4 entries, validity mask, Y origins

**Files:**
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_InitSection`, `EntityWindow_Init`, `EntityWindow_RebuildScanState`, `EntityWindow_Scan`, `EntityWindow_DespawnRings`, `EntityWindow_DespawnObjects`, the three `SLOT_ORIGIN_U` spawn sites)
- Modify: `engine/level/section.asm` (new helper `Section_FlatIDXY` next to `Section_SlotFlatID`)

- [ ] **Step 1 (research):** Re-read `EntityWindow_Init` (line 296), `EntityWindow_RebuildScanState` (line 891), and `Section_GetSecPtrXY`/`Section_SlotFlatID` (section.asm 99-150) end to end. Confirm: Init does NOT populate rings (initial X scan does); Rebuild DOES populate per entry. Confirm `Collected_UpdateCenter` args (d0 = center flat id, d1 = grid_w).

- [ ] **Step 2: Add `Section_FlatIDXY` helper** in `engine/level/section.asm` directly after `Section_SlotFlatID`:

```asm
; -----------------------------------------------
; Section_FlatIDXY — flat section id from grid coordinates.
; In:  d2.b = sec_x, d3.b = sec_y, a2 = Act ptr
; Out: d0.w = sec_y * grid_w + sec_x
; Clobbers: d1
; -----------------------------------------------
Section_FlatIDXY:
        moveq   #0, d0
        moveq   #0, d1
        move.b  d3, d1
        subq.w  #1, d1
        bmi.s   .fxy_add_x
.fxy_mul:
        add.w   Act_grid_w(a2), d0
        dbf     d1, .fxy_mul
.fxy_add_x:
        moveq   #0, d1
        move.b  d2, d1
        add.w   d1, d0
        rts
```

- [ ] **Step 3: Rewrite `EntityWindow_InitSection`** — takes origins for both axes, entry index, and compare-clears the loaded mask when the section changes (the mask clear is inert until Task 4 sets bits, but landing it now keeps Task 4 small):

```asm
; -----------------------------------------------
; EntityWindow_InitSection — populate one EntityScanState entry
;
; In:  a0 = Sec struct pointer (ROM)
;      a1 = EntityScanState pointer (RAM)
;      d0.w = section origin X (engine-space)
;      d1.b = section_id
;      d2.w = section origin Y (engine-space)
;      d6.b = entry index (0-3)
; Out: none
; Clobbers: d3, a2 (mask clear)
; -----------------------------------------------
EntityWindow_InitSection:
        ifdebug assert.l a0, ne, #0     ; NULL Sec ptr = caller passed a void/out-of-grid slot

        ; Loaded mask is per-entry state about ONE section — clear it when
        ; this entry's section changes. Same-section re-init (teleport
        ; migration target) keeps its bits (Task 6 copies them in first).
        cmp.b   EntityScanState_ess_section_id(a1), d1
        beq.s   .same_section
        moveq   #0, d3
        move.b  d6, d3
        lsl.w   #5, d3                  ; entry × ENTITY_LOADED_SLOT_SIZE (32)
        lea     (Entity_Loaded_Masks).w, a2
        adda.w  d3, a2
        moveq   #ENTITY_LOADED_SLOT_SIZE/4-1, d3
.clear_mask:
        clr.l   (a2)+
        dbf     d3, .clear_mask
.same_section:

        move.l  Sec_sec_rings(a0), EntityScanState_ess_rom_ring_ptr(a1)
        move.l  Sec_sec_objects(a0), EntityScanState_ess_rom_obj_ptr(a1)
        move.l  Sec_sec_type_table(a0), EntityScanState_ess_rom_type_tbl_ptr(a1)
        move.w  d0, EntityScanState_ess_origin_x(a1)
        move.w  d2, EntityScanState_ess_origin_y(a1)
        move.b  d1, EntityScanState_ess_section_id(a1)
        move.b  d6, EntityScanState_ess_entry_idx(a1)
        clr.w   EntityScanState_ess_ring_right_idx(a1)
        clr.w   EntityScanState_ess_ring_left_idx(a1)
        clr.w   EntityScanState_ess_obj_right_idx(a1)
        clr.w   EntityScanState_ess_obj_left_idx(a1)
        rts
```

- [ ] **Step 4: Add the shared quadrant builder** replacing the duplicated slot-0/slot-1 blocks. Insert after `EntityWindow_InitSection`:

```asm
; -----------------------------------------------
; EntityWindow_BuildEntries — (re)configure all 4 quadrant entries
;
; Quadrants: entry 0 = slot L row r, 1 = slot R row r,
;            entry 2 = slot L row r+1, 3 = slot R row r+1.
; Void quadrants (sec_x = SEC_VOID, or row ≥ grid_h via
; Section_GetSecPtrXY) get SEC_VOID-stamped entries and a clear
; validity bit. Entity_Window_Active = 4-bit validity mask.
;
; In:  none (reads Slot_Section_Map, Current_Act_Ptr)
; Out: Entity_Window_Active set
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
EntityWindow_BuildEntries:
        lea     (Entity_Scan_State).w, a3
        lea     (Slot_Section_Map).w, a5
        moveq   #0, d7                  ; d7 = validity mask
        moveq   #0, d6                  ; d6 = entry index 0-3

.entry_loop:
        ; slot = entry & 1, row offset = entry >> 1
        move.w  d6, d0
        andi.w  #1, d0                  ; d0 = slot (0/1)
        add.w   d0, d0                  ; slot × 2 (map stride)
        move.b  (a5, d0.w), d2          ; d2 = sec_x
        cmpi.b  #SEC_VOID, d2
        beq.s   .void_entry
        move.b  1(a5, d0.w), d3         ; d3 = sec_y
        move.w  d6, d1
        lsr.w   #1, d1                  ; row offset (0/1)
        add.b   d1, d3                  ; d3 = sec_y + row offset
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY     ; a0 = Sec ptr, Z set = out of grid
        beq.s   .void_entry

        bsr.w   Section_FlatIDXY        ; d0.w = flat id (d2/d3/a2 preserved)
        move.w  d0, d1                  ; d1.b = section_id

        ; origins from entry geometry
        move.w  d6, d0
        andi.w  #1, d0
        beq.s   .x_left
        move.w  #SLOT_ORIGIN_R, d0
        bra.s   .x_done
.x_left:
        move.w  #SLOT_ORIGIN_L, d0
.x_done:
        moveq   #0, d2
        move.w  #SLOT_ORIGIN_U, d2
        btst    #1, d6                  ; lower row?
        beq.s   .y_done
        move.w  #SLOT_ORIGIN_D, d2
.y_done:

        lea     (a3), a1
        bsr.w   EntityWindow_InitSection

        ; claim a collected/killed bitmask slot for this section
        movem.l d6-d7/a3/a5, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        movem.l (sp)+, d6-d7/a3/a5

        bset    d6, d7                  ; mark entry valid
        bra.s   .next_entry

.void_entry:
        ; stamp SEC_VOID — despawn paths read entry ids unconditionally;
        ; a stale id would keep dead-section survivors alive forever
        move.b  #SEC_VOID, EntityScanState_ess_section_id(a3)
        move.b  d6, EntityScanState_ess_entry_idx(a3)

.next_entry:
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d6
        cmpi.w  #MAX_TRACKED_SECTIONS, d6
        blo.s   .entry_loop

        move.b  d7, (Entity_Window_Active).w
        rts
```

- [ ] **Step 5: Rewrite `EntityWindow_Init`** (replace lines 296-362 wholesale):

```asm
EntityWindow_Init:
        bsr.w   RingBuffer_Clear
        bsr.w   Collected_Init
        clr.b   (Entity_Window_Active).w

        ; cold boot: loaded masks + scan-state section ids are garbage —
        ; clear everything so InitSection's compare-clear starts clean
        lea     (Entity_Loaded_Masks).w, a0
        moveq   #(MAX_TRACKED_SECTIONS*ENTITY_LOADED_SLOT_SIZE)/4-1, d0
.clear_loaded:
        clr.l   (a0)+
        dbf     d0, .clear_loaded
        lea     (Entity_Scan_State).w, a0
        move.w  #(MAX_TRACKED_SECTIONS*EntityScanState_len)-1, d0
.clear_scan:
        clr.b   (a0)+
        dbf     d0, .clear_scan

        ; center the 3×3 collected window on slot 0 BEFORE claiming slots
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        bsr.w   Collected_UpdateCenter

        bsr.w   EntityWindow_BuildEntries

        ; vertical re-scan trigger baseline
        move.w  (Camera_Y).w, d0
        andi.w  #$FF80, d0
        move.w  d0, (Camera_Y_Coarse_Prev).w

        ; Run initial scan to load entities in camera range
        bra.w   EntityWindow_Scan
```

(Note: the scan-state clear means InitSection's compare-clear sees section_id 0 — that matches a real section id, but the loaded masks were just cleared anyway, so no stale bits can survive a cold init.)

- [ ] **Step 6: Rewrite `EntityWindow_RebuildScanState`** (replace lines 891-953):

```asm
EntityWindow_RebuildScanState:
        ; Evict stale bitmask slots FIRST (claim-before-evict broke at
        ; exactly 9/9 occupancy — see git history)
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        bsr.w   Collected_UpdateCenter

        bsr.w   EntityWindow_BuildEntries

        ; teleport moved the world under the camera — rebase the
        ; vertical re-scan trigger so the next crossing is real
        move.w  (Camera_Y).w, d0
        andi.w  #$FF80, d0
        move.w  d0, (Camera_Y_Coarse_Prev).w

        ; full ring populate for every valid entry (teleport path)
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6
.populate_loop:
        move.b  (Entity_Window_Active).w, d0
        btst    d6, d0
        beq.s   .populate_next
        lea     (a3), a1
        movem.l d6/a3, -(sp)
        bsr.w   EntityWindow_PopulateSectionRings
        movem.l (sp)+, d6/a3
.populate_next:
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d6
        cmpi.w  #MAX_TRACKED_SECTIONS, d6
        blo.s   .populate_loop
        rts
```

- [ ] **Step 7: Update `EntityWindow_Scan`** loop to iterate 4 entries by validity mask (replace lines 371-396):

```asm
EntityWindow_Scan:
        move.b  (Entity_Window_Active).w, d5
        beq.s   .scan_done

        ; Compute window edges
        move.w  (Camera_X).w, d7
        addi.w  #SCREEN_WIDTH+ENTITY_LOAD_BUFFER, d7   ; d7 = right load edge

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6                  ; d6.b = entry index (0-3) → SST_slot_tag

.section_loop:
        btst    d6, d5
        beq.s   .section_next
        lea     (a3), a1
        bsr.w   EntityWindow_ScanRingsRight
        bsr.w   EntityWindow_ScanObjectsRight
.section_next:
        lea     EntityScanState_len(a3), a3
        addq.b  #1, d6
        cmpi.b  #MAX_TRACKED_SECTIONS, d6
        blo.s   .section_loop

.scan_done:
        bsr.w   EntityWindow_DespawnRings
        bra.w   EntityWindow_DespawnObjects
```

(Note `d5` now holds the validity mask across the loop — `ScanRingsRight`/`ScanObjectsRight` clobber only d0-d4/a0/a2 per their headers; verify and preserve d5 around them if the Task 4/5 refactors change that.)

- [ ] **Step 8: Y origins at the three spawn sites.** Replace each `addi.w #SLOT_ORIGIN_U, d1` (ScanRingsRight ~447, PopulateSectionRings ~520, ScanObjectsRight ~593) with:

```asm
        add.w   EntityScanState_ess_origin_y(a1), d1    ; section-local Y -> engine Y
```

and delete the now-stale `; §4.9 vertical window replaces this constant` comments.

- [ ] **Step 9: Despawn exemption covers 4 entries.** In BOTH `EntityWindow_DespawnRings` (.check_active, lines 657-662) and `EntityWindow_DespawnObjects` (.check_active, lines 701-706), replace the two-compare block with four:

```asm
.check_active:
        ; d1.b = entity's section_id (already loaded by caller code above)
        cmp.b   (Entity_Scan_State+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
```

(SEC_VOID stamps make the unconditional reads safe for invalid entries.)

- [ ] **Step 10: Build + regression-verify in Exodus.**

Run `./build.sh`, reload ROM + symbols. Checks:
1. `emulator_read_memory symbol=Entity_Window_Active len=1` → expect $0F (all 4 valid: 3×3 grid, start pair (0,1), rows 0-1).
2. Read `Entity_Scan_State` (4 × $1A = 104 bytes): entry ids 0,1,3,4 (flat: row0 = 0,1; row1 = 3,4); origins (X $200/$A00/$200/$A00, Y $200/$200/$A00/$A00).
3. Row-0 entities regress clean: write Player_1 x to put camera over Sec0 rings ($080-$1A0 section-local) → `Ring_Count` ≥ 7, screenshot shows rings.
4. Walk right across the FWD teleport: no asserts, `Entity_Window_Active` reflects voids at the grid edge (pair (2,VOID) → mask $05: entries 0 and 2 only).

- [ ] **Step 11: Commit**

```bash
git add engine/objects/entity_window.asm engine/level/section.asm
git commit -m "feat(entity-window): 2x2 quadrant scan state — validity mask, per-entry Y origins, 4-way despawn exemption"
```

---

### Task 3: Row-1 test entity data

**Files:**
- Modify: `data/levels/ojz/act1/entity_data.asm` (Sec3/Sec4 stubs, lines 104-117)

- [ ] **Step 1: Author test data.** Replace the Sec3 and Sec4 stubs:

```asm
OJZ_Sec3_TypeTable:
        dc.b    2, 0
        dc.l    ObjDef_Static           ; type 0
        dc.l    ObjDef_Solid            ; type 1

OJZ_Sec3_Objects:
        ; Solid block low in the section — only reachable by descending
        objentry $180, $300, 1
        ; ANY_Y static marker: must spawn whenever X is in range,
        ; regardless of camera Y (full-height test object)
        objentry $400, $700, 0, 0, (1<<OEF_ANY_Y)
        objend

OJZ_Sec3_Rings:
        ; Vertical ladder from near the row-0/row-1 boundary downward —
        ; exercises band entry/exit during descent
        dc.w    $100, $020
        dc.w    $100, $120
        dc.w    $100, $220
        dc.w    $100, $320
        dc.w    $100, $420
        ; horizontal line deep in the section
        dc.w    $200, $500
        dc.w    $220, $500
        dc.w    $240, $500
        dc.l    0

OJZ_Sec4_TypeTable:
        dc.b    1, 0
        dc.l    ObjDef_Enemy            ; type 0

OJZ_Sec4_Objects:
        objentry $200, $400, 0
        objend

OJZ_Sec4_Rings:
        dc.w    $080, $100
        dc.w    $0A0, $100
        dc.w    $0C0, $100
        dc.l    0
```

- [ ] **Step 2: Build + verify spawn-on-descent.**

Build, reload. With the camera at the level start (camY=$200), `Ring_Count` should NOT include Sec3 rings yet under Task 2 semantics... **it will** — Y banding doesn't exist until Task 5; Sec3 is a tracked quadrant, so its X-in-range rings all load. That's correct for this task. Verify instead:
1. Write Player_1 to x=$04F0, y=$0BA0 (over Sec0/Sec3 boundary area, descended) → screenshot: Sec3 ring ladder visible at correct world positions (world Y = $200 + SECTION_SIZE + section-local Y... i.e. ladder at engine Y $A20-$E20, x=$300 engine).
2. `Ring_Count` includes both Sec0 and Sec3 rings when camera X covers x_local $100.
3. The Sec3 solid block and ANY_Y marker objects appear in the object list (`emulator_object_list` or screenshot).

- [ ] **Step 3: Commit**

```bash
git add data/levels/ojz/act1/entity_data.asm
git commit -m "test(entity-window): row-1 entity fixtures — Sec3 ring ladder + ANY_Y marker, Sec4 enemy"
```

---

### Task 4: Loaded bitmasks + spawn helpers (fixes teleport double-populate)

**Files:**
- Modify: `engine/objects/entity_window.asm`

- [ ] **Step 1 (research):** Confirm the duplicate-ring repro on the Task 3 build before fixing: position camera mid-pair, note `Ring_Count`; drive a FWD then BWD teleport cycle returning to the same spot; `Ring_Count` higher than baseline = duplicates confirmed (record numbers for the commit message).

- [ ] **Step 2: Add bitmask primitives** (after `Killed_MarkObject`, before the Entity Window Core banner):

```asm
; =====================================================
; Loaded bitmasks — §4.9 phase 2
; One 32-byte slot per scan entry: bytes 0-15 ring bits,
; bytes 16-31 object bits, indexed by list_index (0-127).
; Set at spawn, cleared at despawn, cleared wholesale when an
; entry's section changes (InitSection), migrated on teleports.
; =====================================================

; -----------------------------------------------
; EntityLoaded_Test — test a loaded bit
; In:  d0.b = entry index (0-3)
;      d1.w = list_index
;      d2.w = 0 (rings) or ENTITY_LOADED_OBJ_OFFSET (objects)
; Out: Z clear = loaded, Z set = not loaded
; Clobbers: d0, d2, a0
; -----------------------------------------------
EntityLoaded_Test:
        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        lsl.w   #5, d0                  ; entry × 32
        add.w   d0, d2
        lea     (Entity_Loaded_Masks).w, a0
        adda.w  d2, a0
        move.w  d1, d0
        lsr.w   #3, d0
        btst    d1, (a0, d0.w)
        rts

; -----------------------------------------------
; EntityLoaded_Set / EntityLoaded_Clear — same inputs as Test
; Clobbers: d0, d2, a0
; -----------------------------------------------
EntityLoaded_Set:
        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        lsl.w   #5, d0
        add.w   d0, d2
        lea     (Entity_Loaded_Masks).w, a0
        adda.w  d2, a0
        move.w  d1, d0
        lsr.w   #3, d0
        bset    d1, (a0, d0.w)
        rts

EntityLoaded_Clear:
        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        lsl.w   #5, d0
        add.w   d0, d2
        lea     (Entity_Loaded_Masks).w, a0
        adda.w  d2, a0
        move.w  d1, d0
        lsr.w   #3, d0
        bclr    d1, (a0, d0.w)
        rts

; -----------------------------------------------
; EntityWindow_EntryForSection — map section_id → entry index
; In:  d0.b = section_id
; Out: d0.w = entry index 0-3, or -1 if untracked
; Clobbers: d1, a0
; -----------------------------------------------
EntityWindow_EntryForSection:
        lea     (Entity_Scan_State+EntityScanState_ess_section_id).w, a0
        moveq   #0, d1
.efs_loop:
        cmp.b   (a0), d0
        beq.s   .efs_found
        lea     EntityScanState_len(a0), a0
        addq.w  #1, d1
        cmpi.w  #MAX_TRACKED_SECTIONS, d1
        blo.s   .efs_loop
        moveq   #-1, d0
        rts
.efs_found:
        move.w  d1, d0
        rts
```

(Note `EntryForSection` can false-match a SEC_VOID query against a void entry — callers only pass real section ids taken from live entities, never $FF, and despawn's 4-way exemption already filtered SEC_VOID. No guard needed; say so in a comment if the reviewer asks.)

- [ ] **Step 3: Wire spawn sites.** In `EntityWindow_ScanRingsRight`, after the `Collected_CheckRing` block (`bne.s .skip`), add a loaded check, and set the bit after a successful `RingBuffer_Add`:

```asm
        ; Already in the buffer? (loaded bit — set on add, cleared on remove)
        movem.l d3-d4/d7/a0-a1, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Test
        movem.l (sp)+, d3-d4/d7/a0-a1
        bne.s   .skip                   ; loaded → skip
```

and immediately after the `bsr.w RingBuffer_Add` (still inside the saved-register window — re-order so the add's carry is tested BEFORE restoring):

```asm
        bsr.w   RingBuffer_Add
        bcs.s   .add_failed             ; buffer full — no bit, retry next frame
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.b  d3, d1                  ; d3.b = list_index in this window
        moveq   #0, d2
        bsr.w   EntityLoaded_Set
.add_failed:
```

Apply the same pair (Test before add / Set after successful add) to `EntityWindow_PopulateSectionRings` — this is the dedupe that fixes the teleport double-populate bug.

- [ ] **Step 4: Wire object spawn site.** In `EntityWindow_ScanObjectsRight` after the `Killed_CheckObject` skip, add the same `EntityLoaded_Test` with `d2 = ENTITY_LOADED_OBJ_OFFSET`; after a successful `Load_Object` (the `bne.s .obj_spawn_fail` path means failure), set the bit:

```asm
        ; after: move.b d4, SST_entity_list_index(a1)
        moveq   #0, d0
        move.b  d6, d0                  ; d6.b = entry index (scan loop counter)
        moveq   #0, d1
        move.w  d4, d1
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Set
```

(d6 is the entry index inside the scan loop; `EntityWindow_ScanObjectsRight` already receives it. Confirm the movem save-set around the spawn includes everything `EntityLoaded_Set` clobbers — d0/d2/a0 are already inside the saved window.)

- [ ] **Step 5: Clear bits at despawn.** In `EntityWindow_DespawnRings` `.remove` block, before `RingBuffer_Remove`, the ring entry's section_id (byte 4) and list_index (byte 5) are at hand:

```asm
.remove:
        movem.l d5-d7/a0, -(sp)
        ; clear loaded bit (entity may be re-entered later)
        moveq   #0, d1
        move.b  5(a0, d0.w), d1         ; list_index
        move.b  4(a0, d0.w), d0         ; section_id (overwrites index offset — save first)
        ; NOTE: d0 held index×6 — recompute removal index from d5 below
        bsr.w   EntityWindow_EntryForSection
        bmi.s   .no_bit                 ; untracked section — no mask
        moveq   #0, d2
        bsr.w   EntityLoaded_Clear
.no_bit:
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d5-d7/a0
```

Mirror in `EntityWindow_DespawnObjects` `.despawn` (section/list from `SST_entity_section_id`/`SST_entity_list_index`, `d2 = ENTITY_LOADED_OBJ_OFFSET`), and in `EntityWindow_TeleportShift`/`TeleportShiftY` `.ring_remove`/`.obj_despawn` blocks — every removal path clears its bit. Also clear in `DeleteObject`-initiated paths? No — entity-window despawn is the only windowing path; objects deleted by gameplay (kill) go through `Killed_MarkObject` and must ALSO clear the loaded bit: add the same clear inside `Killed_MarkObject` (it has d2=section_id, d3=list_index — note its register convention differs; adapt with the same EntryForSection call).

- [ ] **Step 6: Build + verify.**

1. Repro from Step 1 again: FWD+BWD teleport cycle → `Ring_Count` returns to baseline (duplicates fixed).
2. Read `Entity_Loaded_Masks` (128 bytes): bits set only for in-buffer rings/live objects; counts match `Ring_Count` + object census.
3. Collect a ring (drive player through it if collision is wired; otherwise skip), kill nothing, descend/ascend: no double rings.

- [ ] **Step 7: Commit**

```bash
git add engine/objects/entity_window.asm
git commit -m "feat(entity-window): loaded bitmasks — idempotent spawns; fixes teleport double-populate ring duplicates"
```

---

### Task 5: Y band at spawn, vertical re-scan, Y despawn

**Files:**
- Modify: `engine/objects/entity_window.asm`

- [ ] **Step 1: Shared band-check code.** The band test is 6 instructions; inline it (no jsr overhead in spawn hot path) at each of the three spawn sites plus the re-scan. Canonical shape (d1 = entity engine-Y, computed right after the origin add):

```asm
        ; Y band: camY - LOAD_Y .. camY + SCREEN_HEIGHT + LOAD_Y
        move.w  (Camera_Y).w, d2
        subi.w  #ENTITY_LOAD_BUFFER_Y, d2
        cmp.w   d2, d1
        blt.s   .skip                   ; above band
        addi.w  #SCREEN_HEIGHT+2*ENTITY_LOAD_BUFFER_Y, d2
        cmp.w   d2, d1
        bgt.s   .skip                   ; below band
```

Register pressure note: in `ScanRingsRight` d2 is free at that point (it held the terminator test); in `ScanObjectsRight` d2 holds the placement word — test ANY_Y FIRST (`tst.w d2` / `bmi.s .y_ok` since OEF_ANY_Y = bit 15), then use a scratch register that IS free there (d1 after relocating the Y computation; the implementer adjusts locals, keeping the documented clobber lists truthful).

- [ ] **Step 2: Apply band check to ring sites.** `ScanRingsRight` and `PopulateSectionRings`: after computing engine Y (origin add), run the band check before the Collected/loaded checks (cheapest test first). The skipped entity's X index still advances — S3K semantics; the re-scan catches it later.

- [ ] **Step 3: Apply to object site with ANY_Y.** In `ScanObjectsRight`, compute engine Y early (move the `move.w 2(a0), d1 / add.w ess_origin_y` up, before Killed check), then:

```asm
        move.w  4(a0), d2               ; placement word
        bmi.s   .y_ok                   ; bit 15 = OEF_ANY_Y → skip band
        ; (band check on d1 here, branching to .obj_skip)
.y_ok:
```

On successful spawn, tag the SST with the ANY_Y flag so Y-despawn can exempt it:

```asm
        ; slot_tag = entry index; bit 7 = ANY_Y (placement bit 15)
        move.b  d6, d0
        tst.w   d2                      ; d2 = placement word (saved across Load_Object — keep in saved set)
        bpl.s   .tag_plain
        bset    #7, d0
.tag_plain:
        move.b  d0, SST_slot_tag(a1)
```

(Replaces the existing `move.b d6, SST_slot_tag(a1)`. Every existing reader compares against `SLOT_TAG_UNTAGGED` = $FF exactly — $80+idx can never equal $FF, so they stay correct. Grep `SST_slot_tag` across the repo and confirm: only exact-$FF compares and the despawn flows touched here.)

- [ ] **Step 4: Y despawn.** In `EntityWindow_DespawnRings`, after the X window check falls through to `.check_active` and the section IS active (currently → keep), add the Y test — restructure so active-section entities still get Y-despawned:

```asm
.loop:
        ; ... existing X check:
        ;   in X window  → .check_y
        ;   out of X     → .check_active (despawn unless active section)
.check_y:
        move.w  2(a0, d0.w), d1         ; engine_Y
        move.w  (Camera_Y).w, d2
        subi.w  #ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        blt.s   .remove                 ; far above
        addi.w  #SCREEN_HEIGHT+2*ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        bgt.s   .remove                 ; far below
        bra.s   .next
```

(The X-in-window path now flows to `.check_y` instead of `.next`; the out-of-X active-section-keep path ALSO flows to `.check_y` — net rule: X-straggler despawn unchanged, plus everyone in the buffer must be Y-near or out it goes.) Mirror in `EntityWindow_DespawnObjects` using `SST_y_pos`, with the ANY_Y exemption first:

```asm
.check_y:
        move.b  SST_slot_tag(a0), d1
        bmi.s   .next                   ; bit 7 = ANY_Y → exempt from Y despawn
        move.w  SST_y_pos(a0), d1
        ; (same band test → .despawn / .next)
```

- [ ] **Step 5: Vertical re-scan.** New routine + trigger. In `EntityWindow_Scan`, after the edges are computed and before `.section_loop`, insert:

```asm
        ; vertical re-scan: fires when camY crosses a 128px coarse row
        move.w  (Camera_Y).w, d0
        andi.w  #$FF80, d0
        cmp.w   (Camera_Y_Coarse_Prev).w, d0
        beq.s   .no_rescan
        move.w  d0, (Camera_Y_Coarse_Prev).w
        movem.l d5/d7/a3, -(sp)
        bsr.w   EntityWindow_RescanY
        movem.l (sp)+, d5/d7/a3
.no_rescan:
```

New routine (after `EntityWindow_ScanObjectsRight`):

```asm
; -----------------------------------------------
; EntityWindow_RescanY — vertical re-scan after a coarse camY change
;
; Walks each valid entry's ROM lists from index 0 to the X ratchet
; (right_idx) — i.e. only entities already passed by the X scan —
; and spawns any whose Y is now in band and whose loaded bit is clear.
; Loaded bits make this idempotent; collected/killed still filter.
; Cost: O(entities in X range) per 128px of vertical travel.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_RescanY:
        move.b  (Entity_Window_Active).w, d5
        beq.s   .rescan_done
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6
.rs_entry:
        btst    d6, d5
        beq.s   .rs_next
        lea     (a3), a1
        bsr.w   EntityWindow_RescanRings
        lea     (a3), a1
        bsr.w   EntityWindow_RescanObjects
.rs_next:
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d6
        cmpi.w  #MAX_TRACKED_SECTIONS, d6
        blo.s   .rs_entry
.rescan_done:
        rts
```

`EntityWindow_RescanRings` is structurally `ScanRingsRight` with two changes: the loop bound is `d4 < ring_right_idx` (read it into a register up front) instead of the X edge compare, and the X edge compare is dropped (everything below right_idx already passed it). The band + loaded + collected checks are identical to the (post-Task-5) ScanRingsRight body. `EntityWindow_RescanObjects` likewise mirrors `ScanObjectsRight` (bound = obj_right_idx, killed + loaded + band + ANY_Y + spawn + tag + set-bit identical). **Implementation note:** to avoid three diverging copies of the spawn body, factor the per-entry "check + spawn ring" body into `EntityWindow_TrySpawnRing` (in: a0 = ROM entry, a1 = scan state, d4 = list index, d6 = entry index; out: none) and the object equivalent `EntityWindow_TrySpawnObject`, and have all four walkers (X scan ×2, re-scan ×2) call them. The walkers differ only in loop bounds.

- [ ] **Step 6: Build + verify banding + idempotency.**

1. Reload; park camera at start (camY=$200). `Ring_Count` must now EXCLUDE Sec3's deep rings (engine Y $A20+ — far below band top $200−$100..$200+224+$100). Compare against Task 3's count (which included them).
2. The ANY_Y marker object IS spawned (check object list) despite Y=$700+$A00 engine.
3. Descend slowly (write Player y in steps): ladder rings appear as the band reaches them; `Ring_Count` rises stepwise.
4. Oscillate up/down across the same boundary 10×: `Ring_Count` returns to identical values at each end (idempotent; no leak, no dupes).
5. Ascend fully: deep rings despawn (Y despawn band).

- [ ] **Step 7: Commit**

```bash
git add engine/objects/entity_window.asm
git commit -m "feat(entity-window): Y band spawn + vertical re-scan + Y despawn — OEF_ANY_Y honored, S3K-style"
```

---

### Task 6: Teleport integration — mask migration

**Files:**
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_TeleportShift`, `EntityWindow_TeleportShiftY`)

- [ ] **Step 1 (research):** Read `Section_TeleportFwd/Bwd/Down/Up` in `engine/level/section.asm` (around lines 350-600) and write down, for each direction, the slot-map before→after mapping (e.g. BWD: new slot1 sec = old slot0 sec). Confirm against the grid-edge SEC_VOID behavior (FWD to edge → (2,$FF)). This determines which mask copies are valid.

- [ ] **Step 2: Mask migration in `EntityWindow_TeleportShift`.** After the ring/object shift loops, BEFORE `bsr.w EntityWindow_RebuildScanState`, add (d4 still holds the shift):

```asm
        ; Mask migration: BWD heals the pair (new slot1 = old slot0), so
        ; entries 0/2's masks become entries 1/3's. FWD advances both
        ; slots to new sections — InitSection's compare-clear wipes all.
        tst.w   d4
        bmi.s   .no_migrate             ; FWD (negative shift = camera rebased down... verify sign in Step 1!)
        lea     (Entity_Loaded_Masks).w, a0
        lea     (Entity_Loaded_Masks+ENTITY_LOADED_SLOT_SIZE).w, a1
        moveq   #ENTITY_LOADED_SLOT_SIZE/4-1, d0
.mig01: move.l  (a0)+, (a1)+
        dbf     d0, .mig01
        lea     (Entity_Loaded_Masks+2*ENTITY_LOADED_SLOT_SIZE).w, a0
        lea     (Entity_Loaded_Masks+3*ENTITY_LOADED_SLOT_SIZE).w, a1
        moveq   #ENTITY_LOADED_SLOT_SIZE/4-1, d0
.mig23: move.l  (a0)+, (a1)+
        dbf     d0, .mig23
.no_migrate:
```

**The `tst.w d4` polarity is a Step 1 deliverable** — d0 passed in is `+SECTION_SHIFT` or `−SECTION_SHIFT`; map which sign is BWD from the section.asm call sites (lines 387/471) and fix the branch accordingly. The copy direction must also run before InitSection's compare-clear, which `RebuildScanState` triggers — it does (call is after).

- [ ] **Step 3: Mask migration in `EntityWindow_TeleportShiftY`.** Same pattern: Down (rows advance) copies entry 2→0 and 3→1; Up copies 0→2 and 1→3. Insert before its `RebuildScanState` call, with the same sign-verification note (call sites section.asm:523/582):

```asm
        tst.w   d4
        bmi.s   .migrate_down           ; verify sign in Step 1
        ; UP: rows retreat — old upper row becomes lower row
        lea     (Entity_Loaded_Masks).w, a0
        lea     (Entity_Loaded_Masks+2*ENTITY_LOADED_SLOT_SIZE).w, a1
        moveq   #(2*ENTITY_LOADED_SLOT_SIZE)/4-1, d0
.migu:  move.l  (a0)+, (a1)+
        dbf     d0, .migu
        bra.s   .migrate_done
.migrate_down:
        ; DOWN: rows advance — old lower row becomes upper row
        lea     (Entity_Loaded_Masks+2*ENTITY_LOADED_SLOT_SIZE).w, a0
        lea     (Entity_Loaded_Masks).w, a1
        moveq   #(2*ENTITY_LOADED_SLOT_SIZE)/4-1, d0
.migd:  move.l  (a0)+, (a1)+
        dbf     d0, .migd
.migrate_done:
```

(Entries 0,1 and 2,3 are contiguous 32-byte slots, so each direction is one 64-byte block copy.)

- [ ] **Step 4: Switch `TeleportShiftY` keep-range to Y constants.** Its keep-window currently uses `ENTITY_LOAD_BUFFER` (X constant) — replace both with `ENTITY_LOAD_BUFFER_Y` for consistency with the new band.

- [ ] **Step 5: Also clear stale loaded bits for migrated-away survivors.** After migration + rebuild, entities whose sections dropped out keep no masks (cleared by compare-clear) — already handled. Shifted SURVIVORS' SST coordinates moved but their `(section_id, list_index)` identity didn't — bits stay valid. State this in a comment above the migration block.

- [ ] **Step 6: Build + verify the teleport matrix.** For each of: FWD, BWD, DOWN, UP (drive player position past each threshold):
1. `Ring_Count` before vs after settling back at an equivalent position: stable (no dupes, no losses).
2. Survivor entities visibly continuous across the seam (screenshot pair).
3. `Entity_Loaded_Masks` bits consistent with the buffer census after each teleport.
4. DOWN at the bottom grid row (row 2 → rows (2,3)): entries 2/3 void (`Entity_Window_Active` = $03), no asserts. UP back heals.

- [ ] **Step 7: Commit**

```bash
git add engine/objects/entity_window.asm
git commit -m "feat(entity-window): teleport mask migration — X-BWD pair heal + Y row advance/retreat block copies"
```

---

### Task 7: Instrumentation — ring buffer high-water + drop counter

**Files:**
- Modify: `ram.asm` (after Camera_Y_Coarse_Prev)
- Modify: `engine/objects/rings.asm` (`RingBuffer_Add`)

- [ ] **Step 1: RAM**

```asm
Ring_HighWater:         ds.b 1          ; max Ring_Count observed (diagnostics)
Ring_Add_Dropped:       ds.b 1          ; RingBuffer_Add failures (buffer full)
```

(Also zero both in `RingBuffer_Clear` — it currently just clears `Ring_Count`.)

- [ ] **Step 2: Wire `RingBuffer_Add`.** In the success path after `addq.b #1, (Ring_Count).w`:

```asm
        move.b  (Ring_Count).w, d4
        cmp.b   (Ring_HighWater).w, d4
        bls.s   .not_record
        move.b  d4, (Ring_HighWater).w
.not_record:
```

and in `.full`:

```asm
.full:
        addq.b  #1, (Ring_Add_Dropped).w
        ifdebug assert.b (Ring_Add_Dropped).w, eq, #0   ; DEBUG: a drop is a level-design/budget bug — fail loud
        ori.b   #1, ccr                ; set carry
        rts
```

(If the existing `assert` macro can't express "always fail with message", use the project's debug-print/illegal pattern — check `ifdebug` usages in `engine/objects/core.asm` (`Debug_AssertObjLoop`) for the house style and copy it.)

- [ ] **Step 3: Build + verify.** Reload, play across all sections + teleports: `emulator_read_memory symbol=Ring_HighWater len=1` — record the value (expected well under 128 with current fixtures; note it in the commit). `Ring_Add_Dropped` = 0.

- [ ] **Step 4: Commit**

```bash
git add ram.asm engine/objects/rings.asm
git commit -m "feat(rings): buffer high-water mark + DEBUG-fatal drop counter"
```

---

### Task 8: Full verification matrix, docs, merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§4.9 section)
- Modify: `docs/DEFERRED_WORK.md`
- Merge: `vertical-entity-window` → `master`

- [ ] **Step 1: Run the spec §8 matrix end-to-end on a fresh build** (all seven items: row-1 spawn positions, band culling, re-scan approach from above AND below, 10× oscillation ring-count stability, all-four-teleport survivor continuity, bottom-edge voids, ANY_Y). Screenshot evidence for each. Any failure → stop, root-cause (systematic-debugging), fix, re-run.

- [ ] **Step 2: Update `docs/ENGINE_ARCHITECTURE.md` §4.9** — rewrite the entity-window subsection: 2×2 quadrant scan state, Y band constants, loaded bitmasks (and that they also dedupe teleport populates), OEF_ANY_Y semantics (slot_tag bit 7 mirror), vertical re-scan cost shape, mask migration table per teleport direction.

- [ ] **Step 3: Update `docs/DEFERRED_WORK.md`:**
- Strike "§4.9 entity window is X-only" with resolution note + date.
- Update "Real ring/object art at safe VRAM slots" — its "when ready: after §4.9 phase 2" blocker is now satisfied.
- Add any follow-ups discovered during implementation (e.g. §4.9.4 respawn memory remains open and now has a stable substrate; ring count census tooling if it proved useful).

- [ ] **Step 4: Commit docs, merge, update memory.**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§4.9): vertical entity window — architecture + deferred-work closeout"
git checkout master && git merge --no-ff vertical-entity-window -m "merge: vertical entity window (§4.9 phase 2)"
```

Save a project memory: quadrant window shipped, key numbers (high-water mark, RAM cost), the teleport-duplicate bug fixed by loaded masks, and the mask-migration sign conventions.

---

## Self-review notes (already applied)

- **Spec coverage:** §1 quadrants → Task 2; §2 structures → Tasks 1/4; §3 spawn band + ANY_Y → Task 5; §4 re-scan → Task 5; §5 despawn → Task 5; §6 teleports + mask migration → Task 6 (+ recenter already in rebuild); §7 edge cases → Tasks 2 (voids) / 6 (bottom row); §8 instrumentation + matrix → Tasks 7/8. Non-goals untouched.
- **Known judgment calls for the implementer:** register allocation inside the modified scan loops (documented clobber headers MUST be kept truthful — update them); the `tst.w d4` sign polarity in Task 6 is deliberately flagged as a research deliverable, not assumed.
- **Type consistency:** `EntityLoaded_Test/Set/Clear` share one signature (d0 entry, d1 index, d2 type offset); `ess_entry_idx` is the only new way entry indices flow into helpers; `SLOT_TAG_*` values 0-3 coincide with entry indices by design.
