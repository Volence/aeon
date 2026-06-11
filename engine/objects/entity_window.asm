; Entity window — camera-driven sliding entity loader
; §4.9: rings and objects load/despawn based on camera proximity

; =====================================================
; Rolling Collected/Killed Bitmask
; =====================================================

; -----------------------------------------------
; Collected_Init — fill all 9 slots with COLLECTED_EMPTY_TAG
; -----------------------------------------------
Collected_Init:
        lea     (Ring_Collected_Window).w, a0
        moveq   #COLLECTED_WINDOW_SLOTS-1, d1
.loop:
        move.b  #COLLECTED_EMPTY_TAG, (a0)
        clr.b   1(a0)
        clr.l   COLLECTED_BITMASK_OFFSET(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+4(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+8(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+12(a0)
        clr.l   KILLED_BITMASK_OFFSET(a0)
        clr.l   KILLED_BITMASK_OFFSET+4(a0)
        clr.l   KILLED_BITMASK_OFFSET+8(a0)
        clr.l   KILLED_BITMASK_OFFSET+12(a0)
        lea     COLLECTED_SLOT_SIZE(a0), a0
        dbf     d1, .loop
        rts

; -----------------------------------------------
; Collected_FindSlot — find bitmask slot for a section
;
; In:  d0.b = section_id
; Out: a0 = slot pointer, Z clear = found; Z set = not found
; Clobbers: d1
; -----------------------------------------------
Collected_FindSlot:
        lea     (Ring_Collected_Window).w, a0
        moveq   #COLLECTED_WINDOW_SLOTS-1, d1
.scan:
        cmp.b   (a0), d0
        beq.s   .found
        lea     COLLECTED_SLOT_SIZE(a0), a0
        dbf     d1, .scan
        moveq   #0, d1                  ; Z set = not found
        rts
.found:
        moveq   #1, d1                  ; Z clear = found
        rts

; -----------------------------------------------
; Collected_CheckRing — test if ring was previously collected
;
; In:  d0.b = section_id
;      d1.w = list_index (0-based)
; Out: Z clear = collected (skip), Z set = uncollected (spawn)
; Clobbers: d2, a0
; -----------------------------------------------
Collected_CheckRing:
        movem.l d0-d1, -(sp)
        bsr.w   Collected_FindSlot
        movem.l (sp)+, d0-d1
        beq.s   .uncollected

        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        move.w  d1, d2
        lsr.w   #3, d2
        btst    d1, COLLECTED_BITMASK_OFFSET(a0, d2.w)
        rts

.uncollected:
        moveq   #0, d2                  ; Z set
        rts

; -----------------------------------------------
; Collected_MarkRing — mark ring as collected in bitmask
;
; In:  d2.b = section_id (from ring buffer entry)
;      d3.b = list_index (from ring buffer entry)
; Out: none
; Clobbers: d0-d1, a0
; -----------------------------------------------
Collected_MarkRing:
        move.b  d2, d0
        bsr.w   Collected_FindSlot
        beq.s   .done
        moveq   #0, d1
        move.b  d3, d1
        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        move.w  d1, d0
        lsr.w   #3, d0
        bset    d1, COLLECTED_BITMASK_OFFSET(a0, d0.w)
.done:
        rts

; -----------------------------------------------
; Killed_CheckObject — test if object was previously killed
;
; In:  d0.b = section_id
;      d1.w = list_index (0-based)
; Out: Z clear = killed (skip), Z set = alive (spawn)
; Clobbers: d2, a0
; -----------------------------------------------
Killed_CheckObject:
        movem.l d0-d1, -(sp)
        bsr.w   Collected_FindSlot
        movem.l (sp)+, d0-d1
        beq.s   .alive

        ifdebug assert.w d1, lo, #MAX_LIST_ENTRIES
        move.w  d1, d2
        lsr.w   #3, d2
        btst    d1, KILLED_BITMASK_OFFSET(a0, d2.w)
        rts

.alive:
        moveq   #0, d2
        rts

; -----------------------------------------------
; Killed_MarkObject — mark object as killed in bitmask
; Also clears the loaded bit — a killed object's SST is gone, so the
; loaded mask must agree or respawn paths skip the (dead) slot forever.
;
; In:  d0.b = section_id
;      d1.b = list_index
; Out: none
; Clobbers: d0-d3, a0
; -----------------------------------------------
Killed_MarkObject:
        move.b  d0, d3                  ; section_id survives FindSlot for the loaded-bit clear
        move.w  d1, -(sp)
        bsr.w   Collected_FindSlot
        move.w  (sp)+, d1
        beq.s   .markdone
        moveq   #0, d2
        move.b  d1, d2
        ifdebug assert.w d2, lo, #MAX_LIST_ENTRIES
        move.w  d2, d0
        lsr.w   #3, d0
        bset    d2, KILLED_BITMASK_OFFSET(a0, d0.w)

        move.b  d3, d0                  ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .markdone               ; section untracked — no loaded bits
        move.w  d2, d1                  ; list_index (d2 untouched by EntryForSection)
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Clear
.markdone:
        rts

; -----------------------------------------------
; Collected_ClaimSlot — claim an empty slot for a section
;
; In:  d0.b = section_id
; Out: a0 = slot pointer
;      Z clear = success, Z set = no empty slots
; Clobbers: d1, a0
; -----------------------------------------------
Collected_ClaimSlot:
        bsr.w   Collected_FindSlot
        bne.s   .already_owned

        lea     (Ring_Collected_Window).w, a0
        moveq   #COLLECTED_WINDOW_SLOTS-1, d1
.find:
        cmpi.b  #COLLECTED_EMPTY_TAG, (a0)
        beq.s   .claim
        lea     COLLECTED_SLOT_SIZE(a0), a0
        dbf     d1, .find
        moveq   #0, d1                 ; Z set = no slot
        rts

.claim:
        move.b  d0, (a0)
        clr.b   1(a0)
        clr.l   COLLECTED_BITMASK_OFFSET(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+4(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+8(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+12(a0)
        clr.l   KILLED_BITMASK_OFFSET(a0)
        clr.l   KILLED_BITMASK_OFFSET+4(a0)
        clr.l   KILLED_BITMASK_OFFSET+8(a0)
        clr.l   KILLED_BITMASK_OFFSET+12(a0)
.already_owned:
        moveq   #1, d1                 ; Z clear = ok
        rts

; -----------------------------------------------
; Collected_UpdateCenter — evict slots outside new 3×3 range (±1 in each axis)
; Radius ±1 gives a 3×3 = 9-section keep-neighborhood, matching COLLECTED_WINDOW_SLOTS.
; Increasing the radius beyond ±1 would overflow the 9 available slots.
;
; In:  d0.b = new center section_id
;      d1.b = grid_w
; Out: none
; Clobbers: d0-d5, a0-a1
; -----------------------------------------------
Collected_UpdateCenter:
        move.b  d0, (Entity_Window_Center_ID).w

        ; Compute center_x, center_y via repeated subtraction
        ; center_y = id / grid_w, center_x = id % grid_w
        moveq   #0, d2
        move.b  d0, d2                  ; center_id
        moveq   #0, d3
        move.b  d1, d3                  ; grid_w
        moveq   #0, d4                  ; center_y
.div_center:
        cmp.w   d3, d2
        blo.s   .div_center_done
        sub.w   d3, d2
        addq.w  #1, d4
        bra.s   .div_center
.div_center_done:
        ; d2 = center_x, d4 = center_y, d3 = grid_w (preserved)

        lea     (Ring_Collected_Window).w, a0
        moveq   #COLLECTED_WINDOW_SLOTS-1, d5

.slot_loop:
        move.b  (a0), d0
        cmpi.b  #COLLECTED_EMPTY_TAG, d0
        beq.s   .slot_next

        ; Compute slot's grid coords
        moveq   #0, d1
        move.b  d0, d1                  ; slot section_id
        moveq   #0, d0                  ; slot_y
.div_slot:
        cmp.w   d3, d1
        blo.s   .div_slot_done
        sub.w   d3, d1
        addq.w  #1, d0
        bra.s   .div_slot
.div_slot_done:
        ; d1 = slot_x, d0 = slot_y

        ; Check |slot_x - center_x| <= 1
        sub.w   d2, d1
        bpl.s   .sx_pos
        neg.w   d1
.sx_pos:
        cmpi.w  #1, d1
        bhi.s   .evict

        ; Check |slot_y - center_y| <= 1
        sub.w   d4, d0
        bpl.s   .sy_pos
        neg.w   d0
.sy_pos:
        cmpi.w  #1, d0
        bls.s   .slot_next

.evict:
        move.b  #COLLECTED_EMPTY_TAG, (a0)
        clr.b   1(a0)
        clr.l   COLLECTED_BITMASK_OFFSET(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+4(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+8(a0)
        clr.l   COLLECTED_BITMASK_OFFSET+12(a0)
        clr.l   KILLED_BITMASK_OFFSET(a0)
        clr.l   KILLED_BITMASK_OFFSET+4(a0)
        clr.l   KILLED_BITMASK_OFFSET+8(a0)
        clr.l   KILLED_BITMASK_OFFSET+12(a0)

.slot_next:
        lea     COLLECTED_SLOT_SIZE(a0), a0
        dbf     d5, .slot_loop
        rts

; =====================================================
; Loaded bitmasks — §4.9 phase 2
; One ENTITY_LOADED_SLOT_SIZE (32-byte) slot per scan entry:
; bytes 0-15 ring bits, 16-31 object bits, bit = list_index (0-127).
; Set at spawn, cleared at despawn/removal, cleared wholesale when an
; entry's section changes (EntityWindow_InitSection), migrated between
; entries on teleports (Task 6). Spawn paths test the bit first, which
; makes the X scan, the teleport populate, and the Task-5 vertical
; re-scan mutually idempotent.
; =====================================================

    if ENTITY_LOADED_SLOT_SIZE <> 32
      error "EntityLoaded primitives assume 32-byte slots (lsl #5)"
    endif
    if ENTITY_LOADED_OBJ_OFFSET*8 <> MAX_LIST_ENTRIES
      error "Loaded-mask half-slot does not cover MAX_LIST_ENTRIES bits"
    endif

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
        lsl.w   #5, d0                  ; entry × ENTITY_LOADED_SLOT_SIZE
        add.w   d0, d2
        lea     (Entity_Loaded_Masks).w, a0
        adda.w  d2, a0
        move.w  d1, d0
        lsr.w   #3, d0                  ; byte offset; btst Dn,mem uses bit# mod 8
        btst    d1, (a0, d0.w)
        rts

; -----------------------------------------------
; EntityLoaded_Set — set a loaded bit (same inputs as Test)
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

; -----------------------------------------------
; EntityLoaded_Clear — clear a loaded bit (same inputs as Test)
; Clobbers: d0, d2, a0
; -----------------------------------------------
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
; In:  d0.b = section_id (a real id from a live entity — never SEC_VOID,
;      so void entries can't false-match)
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

; =====================================================
; Entity Window Core
; =====================================================

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

; -----------------------------------------------
; EntityWindow_Init — set up entity window at level start
;
; In:  none (reads Slot_Section_Map, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
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

; -----------------------------------------------
; EntityWindow_Scan — per-frame camera-range entity scan
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
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

; -----------------------------------------------
; EntityWindow_ScanRingsRight — load rings entering right edge
;
; In:  a1 = EntityScanState pointer
;      d7.w = right edge (Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER)
; Out: none
; Clobbers: d0-d4, a0
; -----------------------------------------------
EntityWindow_ScanRingsRight:
        move.l  EntityScanState_ess_rom_ring_ptr(a1), d0
        beq.w   .done
        movea.l d0, a0

        move.w  EntityScanState_ess_ring_right_idx(a1), d4
        move.w  EntityScanState_ess_origin_x(a1), d3

        ; Advance a0 to current index (4 bytes per ROM entry: dc.w X, dc.w Y)
        move.w  d4, d0
        lsl.w   #2, d0
        adda.w  d0, a0

.loop:
        move.w  (a0), d0                ; section-local X (or terminator high word)
        move.w  2(a0), d1               ; section-local Y (or terminator low word)
        ; Check terminator: dc.l 0 means both words are 0
        move.l  (a0), d2
        beq.s   .update_idx             ; terminator

        ; Engine-space X
        add.w   d3, d0                  ; d0 = engine X

        ; Past right edge? List is X-sorted, stop
        cmp.w   d7, d0
        bhi.s   .update_idx

        ; Check if already collected
        movem.l d3-d4/d7/a0-a1, -(sp)
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        bsr.w   Collected_CheckRing
        movem.l (sp)+, d3-d4/d7/a0-a1
        bne.s   .skip                   ; Z clear = collected, skip

        ; Already in the buffer? (loaded bit — set on add, cleared on remove)
        movem.l d3-d4/d7/a0-a1, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Test
        movem.l (sp)+, d3-d4/d7/a0-a1
        bne.s   .skip                   ; loaded → skip

        ; Spawn ring into buffer
        movem.l d3-d4/d7/a0-a1, -(sp)
        move.w  (a0), d0
        add.w   d3, d0                  ; engine X
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; section-local Y -> engine Y
        move.b  EntityScanState_ess_section_id(a1), d2  ; section_id
        move.b  d4, d3                  ; list_index
        bsr.w   RingBuffer_Add
        bcs.s   .add_failed             ; buffer full — no bit, ring retries later
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0   ; a1 = scan state (inside saved window)
        moveq   #0, d1
        move.b  d3, d1                  ; list_index (RingBuffer_Add's d3 input)
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Set
.add_failed:
        movem.l (sp)+, d3-d4/d7/a0-a1

.skip:
        addq.w  #1, d4
        addq.w  #4, a0
        bra.w   .loop

.update_idx:
        move.w  d4, EntityScanState_ess_ring_right_idx(a1)
.done:
        rts

; -----------------------------------------------
; EntityWindow_PopulateSectionRings — full ring populate for teleport
;
; Adds ALL uncollected rings from a section to the buffer and sets
; ring_right_idx to the camera-relative position (first ring past
; right load edge). DespawnRings skips active-section rings, so
; off-screen rings persist until the section becomes inactive.
;
; In:  a1 = EntityScanState pointer (fully initialized)
; Out: ring_right_idx set
; Clobbers: d0-d4, a0, a2
; -----------------------------------------------
EntityWindow_PopulateSectionRings:
        move.l  EntityScanState_ess_rom_ring_ptr(a1), d0
        beq.w   .pdone
        movea.l d0, a2
        move.w  EntityScanState_ess_origin_x(a1), d3

        ; Pass 1: find ring_right_idx (first ring past right load edge)
        move.w  (Camera_X).w, d0
        addi.w  #SCREEN_WIDTH+ENTITY_LOAD_BUFFER, d0
        movea.l a2, a0
        moveq   #0, d4
.pfind:
        move.l  (a0), d1
        beq.s   .pfound
        move.w  (a0), d1
        add.w   d3, d1
        cmp.w   d0, d1
        bhi.s   .pfound
        addq.w  #1, d4
        addq.w  #4, a0
        bra.s   .pfind
.pfound:
        move.w  d4, EntityScanState_ess_ring_right_idx(a1)

        ; Pass 2: add all uncollected rings to buffer
        movea.l a2, a0
        moveq   #0, d4
.ploop:
        move.l  (a0), d1
        beq.w   .pdone

        movem.l d3-d4/a0-a1, -(sp)
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1
        bsr.w   Collected_CheckRing
        movem.l (sp)+, d3-d4/a0-a1
        bne.s   .pskip

        ; Already in the buffer? (loaded bit — teleport-kept rings stay set)
        movem.l d3-d4/a0-a1, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Test
        movem.l (sp)+, d3-d4/a0-a1
        bne.s   .pskip                  ; loaded → skip

        movem.l d3-d4/a0-a1, -(sp)
        move.w  (a0), d0
        add.w   d3, d0
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; section-local Y -> engine Y
        move.b  EntityScanState_ess_section_id(a1), d2
        move.b  d4, d3
        bsr.w   RingBuffer_Add
        bcs.s   .padd_failed            ; buffer full — no bit, ring retries later
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0   ; a1 = scan state (inside saved window)
        moveq   #0, d1
        move.b  d3, d1                  ; list_index (RingBuffer_Add's d3 input)
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Set
.padd_failed:
        movem.l (sp)+, d3-d4/a0-a1

.pskip:
        addq.w  #1, d4
        addq.w  #4, a0
        bra.w   .ploop

.pdone:
        rts

; -----------------------------------------------
; EntityWindow_ScanObjectsRight — load objects entering right edge
;
; Entry format (v2): 6 bytes — dc.w x, y, flags|type|subtype
;   +0 dc.w  section-local X
;   +2 dc.w  section-local Y   (spawner adds the entry's ess_origin_y)
;   +4 dc.w  flags|type|subtype  (OEF_* bits; flows to Load_Object in d2)
; Terminated by dc.w -1 (X is section-local, always >= 0 → bmi fires on sentinel).
; List is X-sorted; bhi exits as soon as X exceeds load edge.
;
; In:  a1 = EntityScanState pointer
;      d6.b = entry index 0-3 (stored to SST_slot_tag on spawn)
;      d7.w = right edge (Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER)
; Out: none
; Clobbers: d0-d4, a0, a2
; -----------------------------------------------
EntityWindow_ScanObjectsRight:
        move.l  EntityScanState_ess_rom_obj_ptr(a1), d0
        beq.w   .obj_done
        movea.l d0, a0

        move.w  EntityScanState_ess_obj_right_idx(a1), d4
        move.w  EntityScanState_ess_origin_x(a1), d3

        ; Advance a0 to current index: d4 × 6 via ×2, ×3, ×6
        move.w  d4, d0
        add.w   d0, d0                  ; d0 = d4 × 2
        add.w   d4, d0                  ; d0 = d4 × 3
        add.w   d0, d0                  ; d0 = d4 × 6
        adda.w  d0, a0

.obj_loop:
        move.w  (a0), d0                ; section-local X (or $FFFF sentinel)
        bmi.w   .obj_update_idx         ; bmi fires on -1 terminator

        ; Engine-space X
        add.w   d3, d0

        ; Past right edge? List is X-sorted, stop
        cmp.w   d7, d0
        bhi.w   .obj_update_idx

        ; Check if object was killed in previous visit
        movem.l d0/a0, -(sp)
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1
        bsr.w   Killed_CheckObject
        movem.l (sp)+, d0/a0
        bne.w   .obj_skip

        ; Already spawned? (loaded bit — set on spawn, cleared on despawn/kill)
        movem.l d0/a0, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Test
        movem.l (sp)+, d0/a0
        bne.w   .obj_skip               ; loaded → skip

        ; Spawn this object (d5 stashes section_id; a3 saved: Load_Object clobbers it; d4-d7 preserved by Load_Object)
        movem.l d3-d7/a0-a1/a3, -(sp)

        moveq   #0, d5
        move.b  EntityScanState_ess_section_id(a1), d5

        ; d0.w = engine X (already computed above)
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; section-local Y -> engine Y
        move.w  4(a0), d2               ; full placement word — Load_Object reads flips from bits 13-14

        ; Type extraction: bits 12-8 → d3, then type-table lookup
        move.w  d2, d3                  ; placement word already in d2
        lsr.w   #OEF_TYPE_SHIFT, d3
        andi.w  #OEF_TYPE_MASK, d3
        movea.l EntityScanState_ess_rom_type_tbl_ptr(a1), a2
        lsl.w   #2, d3                  ; type × 4 (longword)
        addq.w  #2, d3                  ; skip count+pad header
        movea.l (a2, d3.w), a1          ; a1 = ObjDef pointer

        jsr     Load_Object
        bne.s   .obj_spawn_fail

        ; Tag spawned object with slot + entity metadata
        ; a1 = new SST pointer from Load_Object
        move.b  d6, SST_slot_tag(a1)
        move.b  d5, SST_entity_section_id(a1)
        move.b  d4, SST_entity_list_index(a1)

        ; Mark loaded (d0-d2 dead here; d4/d6 preserved by Load_Object)
        moveq   #0, d0
        move.b  d6, d0                  ; entry index
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Set

.obj_spawn_fail:
        movem.l (sp)+, d3-d7/a0-a1/a3

.obj_skip:
        addq.w  #1, d4
        addq.w  #OBJ_ENTRY_SIZE, a0
        bra.w   .obj_loop

.obj_update_idx:
        move.w  d4, EntityScanState_ess_obj_right_idx(a1)
.obj_done:
        rts

; -----------------------------------------------
; EntityWindow_DespawnRings — remove rings outside camera range
;
; Iterates backward for safe swap-with-last removal.
; -----------------------------------------------
EntityWindow_DespawnRings:
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .done
        subq.w  #1, d5

        move.w  (Camera_X).w, d6
        move.w  d6, d7
        subi.w  #ENTITY_DESPAWN_BUFFER, d6
        addi.w  #SCREEN_WIDTH+ENTITY_DESPAWN_BUFFER, d7

.loop:
        ; Compute entry address
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  ; d0 = index × 6
        lea     (Ring_Buffer).w, a0
        move.w  (a0, d0.w), d1          ; engine_X

        cmp.w   d6, d1
        blt.s   .check_active
        cmp.w   d7, d1
        ble.s   .next

.check_active:
        move.b  4(a0, d0.w), d1
        cmp.b   (Entity_Scan_State+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, d1
        beq.s   .next

.remove:
        ; clear the loaded bit before removal (no-op when section untracked)
        moveq   #0, d3
        move.b  5(a0, d0.w), d3         ; list_index
        move.b  4(a0, d0.w), d0         ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .bit_done
        move.w  d3, d1
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Clear
.bit_done:
        movem.l d5-d7, -(sp)
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d5-d7

.next:
        dbf     d5, .loop

.done:
        rts

; -----------------------------------------------
; EntityWindow_DespawnObjects — delete dynamic objects outside range
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

        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .next

        move.w  SST_x_pos(a0), d0
        cmp.w   d6, d0
        blt.s   .check_active
        cmp.w   d7, d0
        ble.s   .next

.check_active:
        move.b  SST_entity_section_id(a0), d1
        cmp.b   (Entity_Scan_State+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, d1
        beq.s   .next
        cmp.b   (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, d1
        beq.s   .next

.despawn:
        movem.l d5-d7/a0, -(sp)
        ; clear the loaded bit before the SST vanishes
        moveq   #0, d3
        move.b  SST_entity_list_index(a0), d3
        move.b  SST_entity_section_id(a0), d0
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .bit_done
        move.w  d3, d1
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Clear
.bit_done:
        movea.l 12(sp), a0              ; SST ptr (a0 slot of the movem frame)
        jsr     DeleteObject
        movem.l (sp)+, d5-d7/a0

.next:
        lea     SST_len(a0), a0
        dbf     d5, .loop
        rts

; -----------------------------------------------
; EntityWindow_TeleportShift — shift nearby entities, despawn rest
;
; In:  d0.w = shift amount (+SECTION_SHIFT or -SECTION_SHIFT)
; Out: none
; Clobbers: d0-d7, a0-a1
; -----------------------------------------------
EntityWindow_TeleportShift:
        move.w  d0, d4                  ; d4 = shift

        ; Keep-range: entities within Camera_X ± load buffer survive and shift
        move.w  (Camera_X).w, d2
        move.w  d2, d3
        subi.w  #ENTITY_LOAD_BUFFER, d2
        addi.w  #SCREEN_WIDTH+ENTITY_LOAD_BUFFER, d3

        ; --- Shift/despawn rings (backward iteration) ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5

.ring_loop:
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  ; d0 = index × 6
        lea     (Ring_Buffer).w, a0
        move.w  (a0, d0.w), d1          ; engine_X

        cmp.w   d2, d1
        blt.s   .ring_remove
        cmp.w   d3, d1
        bgt.s   .ring_remove

        ; In range — shift
        add.w   d4, (a0, d0.w)
        bra.s   .ring_next

.ring_remove:
        movem.l d2-d5/a0, -(sp)
        ; clear the loaded bit so the post-teleport populate can re-add
        moveq   #0, d3
        move.b  5(a0, d0.w), d3         ; list_index
        move.b  4(a0, d0.w), d0         ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .ring_bit_done
        move.w  d3, d1
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Clear
.ring_bit_done:
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d2-d5/a0

.ring_next:
        dbf     d5, .ring_loop

.rings_done:
        ; --- Shift/despawn objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5

.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next

        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .obj_next

        move.w  SST_x_pos(a0), d1
        cmp.w   d2, d1
        blt.s   .obj_despawn
        cmp.w   d3, d1
        bgt.s   .obj_despawn

        add.w   d4, SST_x_pos(a0)
        bra.s   .obj_next

.obj_despawn:
        movem.l d2-d5/a0, -(sp)
        ; clear the loaded bit before the SST vanishes
        moveq   #0, d3
        move.b  SST_entity_list_index(a0), d3
        move.b  SST_entity_section_id(a0), d0
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .obj_bit_done
        move.w  d3, d1
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Clear
.obj_bit_done:
        movea.l 16(sp), a0              ; SST ptr (a0 slot of the movem frame)
        jsr     DeleteObject
        movem.l (sp)+, d2-d5/a0

.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

        ; Rebuild scan state for new section configuration
        bsr.w   EntityWindow_RebuildScanState
        rts

; -----------------------------------------------
; EntityWindow_TeleportShiftY — vertical-teleport mirror of TeleportShift.
; Shifts nearby entities' Y by the teleport amount, despawns the rest.
; Camera_Y/Player_Y just jumped SECTION_SHIFT; entity engine-Y must move
; with them or every loaded ring/object ends up SECTION_SHIFT pixels off.
;
; In:  d0.w = shift amount (+SECTION_SHIFT or -SECTION_SHIFT)
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_TeleportShiftY:
        move.w  d0, d4                  ; d4 = shift

        ; Keep-range: entities within Camera_Y ± load buffer survive and shift
        move.w  (Camera_Y).w, d2
        move.w  d2, d3
        subi.w  #ENTITY_LOAD_BUFFER, d2
        addi.w  #SCREEN_HEIGHT+ENTITY_LOAD_BUFFER, d3

        ; --- Shift/despawn rings (backward iteration) ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5

.ring_loop:
        move.w  d5, d0
        add.w   d0, d0
        add.w   d5, d0
        add.w   d0, d0                  ; d0 = index × 6
        lea     (Ring_Buffer).w, a0
        move.w  2(a0, d0.w), d1         ; engine_Y

        cmp.w   d2, d1
        blt.s   .ring_remove
        cmp.w   d3, d1
        bgt.s   .ring_remove

        ; In range — shift Y
        add.w   d4, 2(a0, d0.w)
        bra.s   .ring_next

.ring_remove:
        movem.l d2-d5/a0, -(sp)
        ; clear the loaded bit so the post-teleport populate can re-add
        moveq   #0, d3
        move.b  5(a0, d0.w), d3         ; list_index
        move.b  4(a0, d0.w), d0         ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .ring_bit_done
        move.w  d3, d1
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Clear
.ring_bit_done:
        move.w  d5, d0
        bsr.w   RingBuffer_Remove
        movem.l (sp)+, d2-d5/a0

.ring_next:
        dbf     d5, .ring_loop

.rings_done:
        ; --- Shift/despawn objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5

.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next

        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .obj_next

        move.w  SST_y_pos(a0), d1
        cmp.w   d2, d1
        blt.s   .obj_despawn
        cmp.w   d3, d1
        bgt.s   .obj_despawn

        add.w   d4, SST_y_pos(a0)
        bra.s   .obj_next

.obj_despawn:
        movem.l d2-d5/a0, -(sp)
        ; clear the loaded bit before the SST vanishes
        moveq   #0, d3
        move.b  SST_entity_list_index(a0), d3
        move.b  SST_entity_section_id(a0), d0
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .obj_bit_done
        move.w  d3, d1
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Clear
.obj_bit_done:
        movea.l 16(sp), a0              ; SST ptr (a0 slot of the movem frame)
        jsr     DeleteObject
        movem.l (sp)+, d2-d5/a0

.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

        ; Rebuild scan state for new section configuration (sec_y changed)
        bsr.w   EntityWindow_RebuildScanState
        rts

; -----------------------------------------------
; EntityWindow_RebuildScanState — repopulate scan state from slot map
;
; Called after teleport updates Slot_Section_Map.
; Resets load indices and reconfigures tracked sections.
; -----------------------------------------------
EntityWindow_RebuildScanState:
        ; Evict stale bitmask slots FIRST (claim-before-evict broke at
        ; exactly 9/9 occupancy: ClaimSlot calls failed silently when a
        ; full 3x3 neighborhood preceded a teleport, leaving the active
        ; sections untracked until the next one)
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
