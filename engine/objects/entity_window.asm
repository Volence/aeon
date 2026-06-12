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
        beq.w   .markdone               ; .w — DEBUG assert expansions exceed short range
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
; entry's section changes (EntityWindow_InitSection). Window slides
; migrate surviving sections' masks to their new entries by identity
; (EntityWindow_MigrateMasks); teleport rebases keep the tracked
; section set invariant, so their masks survive slot-to-same-slot.
; Spawn paths test the bit first, which makes the X scan, the slide
; populate, and the vertical re-scan (EntityWindow_RescanY) mutually
; idempotent.
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
        ; this entry's section changes. Same-section re-init preserves the
        ; bits — the path teleport rebuilds take (the visibility-derived
        ; window keeps the section set invariant across a rebase); slides
        ; clear here, then EntityWindow_MigrateMasks copies survivors in.
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
; EntityWindow_DeriveWindow — absolute window anchor from the camera envelope
;
; The tracked 2×2 = the sections overlapped by the camera's DESPAWN envelope
; (the widest band), so any live windowed entity's section is always tracked.
; Envelope spans < SECTION_SIZE on both axes → always exactly 2 cols × 2 rows
; (screen+2×buffer < SECTION_SIZE on both axes — see constants.asm).
;
; Out: d2.b = sec_x0 (slot0 sec_x + col0 — may be "negative"/past-grid; the
;             grid range check voids such cells downstream)
;      d3.b = sec_y0
;      d4.w = col0 (signed — entry origin derivation needs it)
;      d5.w = row0 (signed)
; Clobbers: d0
; -----------------------------------------------
EntityWindow_DeriveWindow:
        move.w  (Camera_X).w, d4
        subi.w  #SLOT_ORIGIN_L+ENTITY_DESPAWN_BUFFER, d4
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d4                  ; d4 = col0 (floor — asr is negative-safe)
        move.w  (Camera_Y).w, d5
        subi.w  #SLOT_ORIGIN_U+ENTITY_DESPAWN_BUFFER_Y, d5
        asr.w   d0, d5                  ; d5 = row0
        move.b  (Slot_Section_Map).w, d2        ; slot0 sec_x
        add.b   d4, d2                  ; d2 = sec_x0 (byte wrap OK — range check voids)
        move.b  (Slot_Section_Map+1).w, d3      ; slot0 sec_y
        add.b   d5, d3                  ; d3 = sec_y0
        rts

; -----------------------------------------------
; EntityWindow_BuildEntries — (re)configure the 4 entries from the camera
; envelope (visibility-derived window — see spec 2026-06-11).
;
; Quadrants: entry 0 = (sec_x0, sec_y0) … entry 3 = (sec_x0+1, sec_y0+1).
; Stores the absolute anchor in Entity_Window_Anchor (slide trigger +
; teleport-invariance checks read it) and the signed column-0/row-0 origin
; bases in Entity_Window_OriginX/Y. Void quadrants ("negative"/past-grid
; coordinates via Section_GetSecPtrXY's unsigned range check) get
; SEC_VOID-stamped entries and a clear validity bit.
;
; In:  none (reads Camera_X/Y, Slot_Section_Map, Current_Act_Ptr)
; Out: Entity_Window_Active = validity mask; Entity_Window_Anchor +
;      Entity_Window_OriginX/Y updated
; Clobbers: d0-d7, a0-a3
; -----------------------------------------------
EntityWindow_BuildEntries:
        bsr.w   EntityWindow_DeriveWindow       ; d2/d3 = anchor, d4/d5 = col0/row0
        move.b  d2, (Entity_Window_Anchor).w
        move.b  d3, (Entity_Window_Anchor+1).w
        ; origin bases: SLOT_ORIGIN + col0/row0 × SECTION_SIZE (signed words —
        ; may be −$600, $200, $A00, $1200)
        moveq   #SECTION_SIZE_SHIFT, d0
        asl.w   d0, d4
        addi.w  #SLOT_ORIGIN_L, d4
        move.w  d4, (Entity_Window_OriginX).w   ; origin_x of column 0
        asl.w   d0, d5
        addi.w  #SLOT_ORIGIN_U, d5
        move.w  d5, (Entity_Window_OriginY).w   ; origin_y of row 0

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d7                  ; d7 = validity mask
        moveq   #0, d6                  ; d6 = entry index 0-3

.entry_loop:
        ; entry geometry from the stored anchor — d2/d3 don't survive the
        ; loop body (d2 reused for origin_y, InitSection clobbers d3), so
        ; reload each iteration
        move.b  (Entity_Window_Anchor).w, d2    ; d2 = sec_x0
        move.b  (Entity_Window_Anchor+1).w, d3  ; d3 = sec_y0
        move.w  d6, d0
        andi.w  #1, d0                  ; d0 = column offset (entry & 1)
        add.b   d0, d2                  ; d2 = sec_x0 + (entry & 1)
        move.w  d6, d1
        lsr.w   #1, d1                  ; d1 = row offset (entry >> 1)
        add.b   d1, d3                  ; d3 = sec_y0 + (entry >> 1)
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY     ; a0 = Sec ptr, Z set = out of grid
        beq.s   .void_entry             ; (unsigned check voids "negative" bytes too)

        bsr.w   Section_FlatIDXY        ; d0.w = flat id (d2/d3/a2 preserved)
        move.w  d0, d1                  ; d1.b = section_id

        ; origins: column/row base + (entry bit) × SECTION_SIZE
        move.w  (Entity_Window_OriginX).w, d0
        btst    #0, d6                  ; right column?
        beq.s   .x_done
        addi.w  #SECTION_SIZE, d0
.x_done:
        move.w  (Entity_Window_OriginY).w, d2
        btst    #1, d6                  ; lower row?
        beq.s   .y_done
        addi.w  #SECTION_SIZE, d2
.y_done:

        lea     (a3), a1
        bsr.w   EntityWindow_InitSection

        ; claim a collected/killed bitmask slot for this section
        movem.l d6-d7/a3, -(sp)
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        movem.l (sp)+, d6-d7/a3

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
; In:  none (reads Camera_X/Y, Slot_Section_Map, Current_Act_Ptr —
;      camera must be positioned before this runs)
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
        ; anchor + origin bases: first BuildEntries overwrites them, but an
        ; explicit clear documents that no pre-derivation state survives boot
        clr.w   (Entity_Window_Anchor).w
        clr.w   (Entity_Window_OriginX).w
        clr.w   (Entity_Window_OriginY).w

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
        andi.w  #ENTITY_RESCAN_COARSE_MASK, d0
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

        ; Vertical re-scan: fires when camY crosses a 128px coarse row.
        ; ENTITY_LOAD_BUFFER_Y (256px) > row size, so band motion between
        ; crossings can never skip past an entity unseen.
        move.w  (Camera_Y).w, d0
        andi.w  #ENTITY_RESCAN_COARSE_MASK, d0
        cmp.w   (Camera_Y_Coarse_Prev).w, d0
        beq.s   .no_rescan
        move.w  d0, (Camera_Y_Coarse_Prev).w
        movem.l d5/d7, -(sp)
        bsr.w   EntityWindow_RescanY
        movem.l (sp)+, d5/d7
.no_rescan:

        ; window slide: fires when the camera envelope crosses a section
        ; boundary (≤ once per ~2048px of travel; one axis per frame at the
        ; 16px/f camera clamp). DeriveWindow clobbers d5 — the validity mask
        ; is reloaded below on both paths.
        bsr.w   EntityWindow_DeriveWindow       ; d2/d3 = anchor candidate
        cmp.b   (Entity_Window_Anchor).w, d2
        bne.s   .slide
        cmp.b   (Entity_Window_Anchor+1).w, d3
        beq.s   .no_slide
.slide:
        move.w  d7, -(sp)                       ; right load edge (camera unchanged by slide)
        bsr.w   EntityWindow_Slide
        move.w  (sp)+, d7
.no_slide:
        move.b  (Entity_Window_Active).w, d5    ; reload — DeriveWindow/Slide clobbered it

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6                  ; d6.b = entry index (0-3)

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
; EntityWindow_TrySpawnRing — gate one ROM ring entry, add if it passes
;
; Gates (cheapest first): Y load band → collected bit → loaded bit.
; On RingBuffer_Add success, sets the loaded bit. Buffer-full leaves
; the bit clear — the X ratchet has already passed this ring, so only
; a later re-scan or teleport populate retries it.
; X-edge filtering is the WALKERS' job — this helper never reads
; Camera_X, so the teleport populate can add off-screen-X rings.
;
; In:  a0 = ROM ring entry (dc.w local X, dc.w local Y)
;      a1 = EntityScanState pointer
;      d4.w = list index
; Out: none
; Clobbers: d0-d2 (d3-d7/a0-a6 preserved; d3/d4/a0 saved internally)
; -----------------------------------------------
EntityWindow_TrySpawnRing:
        ; Y load band: camY-LOAD_Y .. camY+SCREEN_HEIGHT+LOAD_Y
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; engine Y
        move.w  (Camera_Y).w, d2
        subi.w  #ENTITY_LOAD_BUFFER_Y, d2
        cmp.w   d2, d1
        blt.w   .out_of_band            ; above band (.w — DEBUG assert expansion exceeds short range)
        addi.w  #SCREEN_HEIGHT+2*ENTITY_LOAD_BUFFER_Y, d2
        cmp.w   d2, d1
        bgt.w   .out_of_band            ; below band (.w — see above)

        ; one save window for both checks + the add (subcalls clobber a0)
        movem.l d3-d4/a0, -(sp)

        ; collected on a previous visit?
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        bsr.w   Collected_CheckRing     ; clobbers d2, a0
        bne.w   .gated                  ; Z clear = collected (.w — DEBUG assert expansion exceeds short range)

        ; already in the buffer? (loaded bit — set on add, cleared on remove)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Test       ; clobbers d0, d2, a0
        bne.w   .gated                  ; loaded → skip (.w — see above)

        ; spawn ring into buffer
        movea.l 8(sp), a0               ; ROM entry (a0 slot of movem frame)
        move.w  (a0), d0
        add.w   EntityScanState_ess_origin_x(a1), d0    ; engine X
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; engine Y
        move.b  EntityScanState_ess_section_id(a1), d2  ; section_id
        move.b  d4, d3                  ; list_index

    ifdef __DEBUG__
        ; No-dup invariant (spec §3): teleports never populate and slides
        ; populate only genuinely-new sections, so a (section_id, list_index)
        ; pair offered here must never already sit in the live buffer — the
        ; loaded bit would have gated it. This is the shared add site for the
        ; X scan, the vertical re-scan AND PopulateSectionRings, so it guards
        ; every spawn path. d4/a0 are clobberable (RingBuffer_Add clobbers
        ; both); d5 must survive — push it.
        move.w  d5, -(sp)
        moveq   #0, d4
        move.b  d2, d4
        lsl.w   #8, d4
        move.b  d3, d4                  ; d4 = (section_id<<8)|list_index
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .nodup_ok
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0
.nodup_scan:
        cmp.w   4(a0), d4               ; entry key word: sec.b, idx.b at +4
        beq.s   .nodup_hit
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
        dbf     d5, .nodup_scan
        bra.s   .nodup_ok
.nodup_hit:
        move.w  4(a0), d5               ; register comparand for the assert
        assert.w d5, ne, d4             ; always fails: duplicate (sec,idx)
.nodup_ok:
        move.w  (sp)+, d5
    endif

        bsr.w   RingBuffer_Add          ; clobbers d4, a0
        bcs.s   .gated                  ; full — no bit; re-scan/populate retries
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.b  d3, d1                  ; list_index (RingBuffer_Add's d3 input)
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Set
.gated:
        movem.l (sp)+, d3-d4/a0
.out_of_band:
        rts

; -----------------------------------------------
; EntityWindow_ScanRingsRight — load rings entering right edge
;
; Y-skipped entries still advance the X ratchet (S3K semantics) —
; the vertical re-scan catches them when the band reaches them.
;
; In:  a1 = EntityScanState pointer
;      d7.w = right edge (Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER)
; Out: none
; Clobbers: d0-d4, a0
; -----------------------------------------------
EntityWindow_ScanRingsRight:
        move.l  EntityScanState_ess_rom_ring_ptr(a1), d0
        beq.s   .done
        movea.l d0, a0

        move.w  EntityScanState_ess_ring_right_idx(a1), d4
        move.w  EntityScanState_ess_origin_x(a1), d3

        ; Advance a0 to current index (4 bytes per ROM entry: dc.w X, dc.w Y)
        move.w  d4, d0
        lsl.w   #2, d0
        adda.w  d0, a0

.loop:
        move.l  (a0), d0                ; terminator: dc.l 0
        beq.s   .update_idx
        move.w  (a0), d0
        add.w   d3, d0                  ; engine X

        ; Past right edge? List is X-sorted, stop
        cmp.w   d7, d0
        bhi.s   .update_idx

        bsr.w   EntityWindow_TrySpawnRing
        addq.w  #1, d4
        addq.w  #4, a0
        bra.s   .loop

.update_idx:
        move.w  d4, EntityScanState_ess_ring_right_idx(a1)
    ifdef __DEBUG__
        ; Negative-origin inertness (shared note — ScanObjectsRight asserts the
        ; same; see spec §6): after a FWD teleport the kept left column
        ; re-expresses to a negative origin (e.g. -$600), so its entities'
        ; engine X is negative — huge UNSIGNED, always past the right load
        ; edge — and the bhi above exits at the first entry. Such an entry is
        ; intentionally inert for NEW spawns (nothing in it can reach the
        ; screen without a BWD teleport making the origin positive first), so
        ; its ratchet must stay 0. d3 = origin_x, d4 = ratchet just written.
        tst.w   d3
        bpl.s   .org_ok
        assert.w d4, eq
.org_ok:
    endif
.done:
        rts

; -----------------------------------------------
; EntityWindow_PopulateSectionRings — full ring populate for one entry
;
; Offers EVERY listed ring to TrySpawnRing (no X edge filter), so
; in-band, uncollected, not-yet-loaded rings load across the whole
; section width; sets ring_right_idx to the camera-relative position
; (first ring past right load edge). Called by the slide path for
; newly tracked sections only — surviving sections' loaded bits
; migrate with them, so a re-offer couldn't double-add anyway (the
; no-dup invariant is DEBUG-asserted at the shared add site inside
; EntityWindow_TrySpawnRing).
; Out-of-band rings are NOT added — the vertical re-scan picks them
; up when camY reaches them.
;
; In:  a1 = EntityScanState pointer (fully initialized)
; Out: ring_right_idx set
; Clobbers: d0-d4, a0, a2
; -----------------------------------------------
EntityWindow_PopulateSectionRings:
        move.l  EntityScanState_ess_rom_ring_ptr(a1), d0
        beq.s   .pdone
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

        ; Pass 2: offer every listed ring (band/collected/loaded gates inside)
        movea.l a2, a0
        moveq   #0, d4
.ploop:
        move.l  (a0), d0                ; terminator: dc.l 0
        beq.s   .pdone
        bsr.w   EntityWindow_TrySpawnRing
        addq.w  #1, d4
        addq.w  #4, a0
        bra.s   .ploop

.pdone:
        rts

; -----------------------------------------------
; EntityWindow_TrySpawnObject — gate one ROM object entry, spawn if it passes
;
; Entry format (v2): 6 bytes — dc.w x, y, flags|type|subtype
;   +0 dc.w  section-local X
;   +2 dc.w  section-local Y   (ess_origin_y added here)
;   +4 dc.w  flags|type|subtype  (OEF_* bits; flows to Load_Object in d2)
; Gates: ANY_Y/Y load band → killed bit → loaded bit. On Load_Object
; success: SST_slot_tag = entry index | ANY_Y<<7 (never collides with
; SLOT_TAG_UNTAGGED=$FF), section id + list index stored, loaded bit set.
; Alloc failure leaves the bit clear — a later re-scan retries.
; X-edge filtering is the WALKERS' job — no Camera_X reads here.
;
; In:  a0 = ROM object entry
;      a1 = EntityScanState pointer
;      d4.w = list index
; Out: none
; Clobbers: d0-d2, a2 (d3-d7/a0-a1/a3 preserved; d3/d5/a0-a1/a3 saved internally)
; -----------------------------------------------
EntityWindow_TrySpawnObject:
        ; ANY_Y (placement bit 15) skips the Y band check
        move.w  4(a0), d2               ; placement word
        bmi.s   .y_ok

        ; Y load band: camY-LOAD_Y .. camY+SCREEN_HEIGHT+LOAD_Y
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; engine Y
        move.w  (Camera_Y).w, d0
        subi.w  #ENTITY_LOAD_BUFFER_Y, d0
        cmp.w   d0, d1
        blt.w   .out_of_band            ; above band
        addi.w  #SCREEN_HEIGHT+2*ENTITY_LOAD_BUFFER_Y, d0
        cmp.w   d0, d1
        bgt.w   .out_of_band            ; below band
.y_ok:
        ; one save window for both checks + the spawn
        ; (frame: d3=0, d5=4, a0=8, a1=12, a3=16; Load_Object clobbers a1-a3)
        movem.l d3/d5/a0-a1/a3, -(sp)

        ; killed on a previous visit?
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        bsr.w   Killed_CheckObject      ; clobbers d2, a0
        bne.s   .gated                  ; Z clear = killed

        ; already spawned? (loaded bit — set on spawn, cleared on despawn/kill)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a1), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Test       ; clobbers d0, d2, a0
        bne.s   .gated                  ; loaded → skip

        ; spawn (d5 stashes section_id — Load_Object preserves d4-d7)
        movea.l 8(sp), a0               ; ROM entry (a0 slot of movem frame)
        moveq   #0, d5
        move.b  EntityScanState_ess_section_id(a1), d5

        move.w  (a0), d0
        add.w   EntityScanState_ess_origin_x(a1), d0    ; engine X
        move.w  2(a0), d1
        add.w   EntityScanState_ess_origin_y(a1), d1    ; engine Y
        move.w  4(a0), d2               ; full placement word — Load_Object reads flips from bits 13-14

        ; Type extraction: bits 12-8 → d3, then type-table lookup
        move.w  d2, d3
        lsr.w   #OEF_TYPE_SHIFT, d3
        andi.w  #OEF_TYPE_MASK, d3
        movea.l EntityScanState_ess_rom_type_tbl_ptr(a1), a2
        lsl.w   #2, d3                  ; type × 4 (longword)
        addq.w  #2, d3                  ; skip count+pad header
        movea.l (a2, d3.w), a1          ; a1 = ObjDef pointer

        jsr     Load_Object             ; clobbers d0-d3/a1-a3, preserves d4-d7/a0
        bne.s   .gated                  ; alloc failed — no bit, re-scan retries

        ; Tag spawned object (a1 = new SST from Load_Object)
        ; slot_tag = entry index; bit 7 = ANY_Y (placement bit 15)
        movea.l 12(sp), a2              ; scan state (a1 slot of movem frame)
        move.b  EntityScanState_ess_entry_idx(a2), d0
        move.w  4(a0), d3               ; placement word (a0 survived Load_Object)
        bpl.s   .tag_plain
        bset    #7, d0
.tag_plain:
        move.b  d0, SST_slot_tag(a1)
        move.b  d5, SST_entity_section_id(a1)
        move.b  d4, SST_entity_list_index(a1)

        ; mark loaded (entry index WITHOUT the ANY_Y bit — it's a mask base)
        moveq   #0, d0
        move.b  EntityScanState_ess_entry_idx(a2), d0
        moveq   #0, d1
        move.w  d4, d1                  ; list_index
        moveq   #ENTITY_LOADED_OBJ_OFFSET, d2
        bsr.w   EntityLoaded_Set
.gated:
        movem.l (sp)+, d3/d5/a0-a1/a3
.out_of_band:
        rts

; -----------------------------------------------
; EntityWindow_ScanObjectsRight — load objects entering right edge
;
; List is X-sorted; bhi exits as soon as X exceeds load edge. Terminated
; by dc.w -1 (X is section-local, always >= 0 → bmi fires on sentinel).
; Y-skipped entries still advance the X ratchet (S3K semantics) —
; the vertical re-scan catches them when the band reaches them.
;
; In:  a1 = EntityScanState pointer
;      d7.w = right edge (Camera_X + SCREEN_WIDTH + ENTITY_LOAD_BUFFER)
; Out: none
; Clobbers: d0-d4, a0, a2
; -----------------------------------------------
EntityWindow_ScanObjectsRight:
        move.l  EntityScanState_ess_rom_obj_ptr(a1), d0
        beq.s   .obj_done
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
        bmi.s   .obj_update_idx         ; bmi fires on -1 terminator

        add.w   d3, d0                  ; engine X

        ; Past right edge? List is X-sorted, stop
        cmp.w   d7, d0
        bhi.s   .obj_update_idx

        bsr.w   EntityWindow_TrySpawnObject
        addq.w  #1, d4
        addq.w  #OBJ_ENTRY_SIZE, a0
        bra.s   .obj_loop

.obj_update_idx:
        move.w  d4, EntityScanState_ess_obj_right_idx(a1)
    ifdef __DEBUG__
        ; negative-origin entries must stay inert — see the shared note at
        ; EntityWindow_ScanRingsRight's ratchet update
        tst.w   d3
        bpl.s   .org_ok
        assert.w d4, eq
.org_ok:
    endif
.obj_done:
        rts

; -----------------------------------------------
; EntityWindow_RescanY — vertical re-scan after a coarse camY change
;
; Walks each valid entry's ROM lists from index 0 to the X ratchet
; (right_idx) — only entities already passed by the X scan — and
; spawns anything now in band whose loaded bit is clear. Loaded bits
; make this idempotent; collected/killed still filter.
; Cost: O(entities in X range) per 128px of vertical travel.
;
; In:  none
; Out: none
; Clobbers: d0-d6, a0-a3
; -----------------------------------------------
EntityWindow_RescanY:
        move.b  (Entity_Window_Active).w, d5
        beq.s   .done
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6
.entry_loop:
        btst    d6, d5
        beq.s   .entry_next
        lea     (a3), a1
        bsr.w   EntityWindow_RescanRings
        lea     (a3), a1
        bsr.w   EntityWindow_RescanObjects
.entry_next:
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d6
        cmpi.w  #MAX_TRACKED_SECTIONS, d6
        blo.s   .entry_loop
.done:
        rts

; -----------------------------------------------
; EntityWindow_RescanRings — re-offer rings 0..ring_right_idx-1
;
; No X edge test: everything below the ratchet already passed it.
; Defensive terminator stop guards a ratchet beyond list end.
;
; In:  a1 = EntityScanState pointer
; Out: none
; Clobbers: d0-d4, a0
; -----------------------------------------------
EntityWindow_RescanRings:
        move.l  EntityScanState_ess_rom_ring_ptr(a1), d0
        beq.s   .done
        movea.l d0, a0
        move.w  EntityScanState_ess_ring_right_idx(a1), d3      ; X ratchet bound
        beq.s   .done
        moveq   #0, d4
.loop:
        move.l  (a0), d0                ; terminator: dc.l 0
        beq.s   .done
        bsr.w   EntityWindow_TrySpawnRing
        addq.w  #1, d4
        addq.w  #4, a0
        cmp.w   d3, d4
        blo.s   .loop
.done:
        rts

; -----------------------------------------------
; EntityWindow_RescanObjects — re-offer objects 0..obj_right_idx-1
;
; In:  a1 = EntityScanState pointer
; Out: none
; Clobbers: d0-d4, a0, a2
; -----------------------------------------------
EntityWindow_RescanObjects:
        move.l  EntityScanState_ess_rom_obj_ptr(a1), d0
        beq.s   .done
        movea.l d0, a0
        move.w  EntityScanState_ess_obj_right_idx(a1), d3       ; X ratchet bound
        beq.s   .done
        moveq   #0, d4
.loop:
        tst.w   (a0)                    ; defensive: -1 sentinel below the ratchet
        bmi.s   .done
        bsr.w   EntityWindow_TrySpawnObject
        addq.w  #1, d4
        addq.w  #OBJ_ENTRY_SIZE, a0
        cmp.w   d3, d4
        blo.s   .loop
.done:
        rts

; -----------------------------------------------
; EntityWindow_DespawnRings — remove rings outside camera range
;
; X rule (unchanged): out-of-X rings despawn UNLESS their section is
; an active window entry. Y rule (Task 5): EVERY ring — active section
; or not — must sit inside the Y despawn band or it goes. The Y band
; uses ENTITY_DESPAWN_BUFFER_Y (wider than load = hysteresis: a ring
; between the bands neither loads nor despawns, so no churn).
; Iterates backward for safe swap-with-last removal.
; -----------------------------------------------
EntityWindow_DespawnRings:
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.w   .done
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
        ble.s   .check_y                ; X in window → still Y-gated

.check_active:
        move.b  4(a0, d0.w), d1
        cmp.b   (Entity_Scan_State+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, d1
        bne.s   .remove                 ; X straggler in a dead section

.check_y:
        ; Y despawn band: camY-DESPAWN_Y .. camY+SCREEN_HEIGHT+DESPAWN_Y
        move.w  2(a0, d0.w), d1         ; engine_Y
        move.w  (Camera_Y).w, d2
        subi.w  #ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        blt.s   .remove                 ; far above
        addi.w  #SCREEN_HEIGHT+2*ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        ble.s   .next                   ; in band → keep
                                        ; far below → fall into .remove

.remove:
        ; clear the loaded bit before removal (no-op when section
        ; untracked; Y despawn makes this live for active sections too)
        clearLoadedRing a0,d0
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
;
; Same X/Y rules as DespawnRings, plus: ANY_Y objects (slot_tag bit 7)
; are exempt from the Y band — they live as long as X allows.
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
        ble.s   .check_y                ; X in window → still Y-gated

.check_active:
        move.b  SST_entity_section_id(a0), d1
        cmp.b   (Entity_Scan_State+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, d1
        beq.s   .check_y
        cmp.b   (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, d1
        bne.s   .despawn                ; X straggler in a dead section

.check_y:
        move.b  SST_slot_tag(a0), d1
        bmi.s   .next                   ; bit 7 = ANY_Y → never Y-despawned
        move.w  SST_y_pos(a0), d1
        move.w  (Camera_Y).w, d2
        subi.w  #ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        blt.s   .despawn                ; far above
        addi.w  #SCREEN_HEIGHT+2*ENTITY_DESPAWN_BUFFER_Y, d2
        cmp.w   d2, d1
        ble.s   .next                   ; in band → keep
                                        ; far below → fall into .despawn

.despawn:
        movem.l d5-d7/a0, -(sp)
        ; clear the loaded bit before the SST vanishes (Y despawn makes
        ; this live for active sections too)
        clearLoadedObj a0
        movea.l 12(sp), a0              ; SST ptr (a0 slot of the movem frame)
        jsr     DeleteObject
        movem.l (sp)+, d5-d7/a0

.next:
        lea     SST_len(a0), a0
        dbf     d5, .loop
        rts

; -----------------------------------------------
; EntityWindow_TeleportShift — re-express entities after an X teleport rebase
;
; A teleport rebase does not change what is visible, and the window is
; visibility-derived, so the tracked SECTIONS are invariant across the
; rebase: the slot-map sec_x advance (±2) cancels the camera delta's
; col0 shift (∓2), leaving the anchor unchanged — DEBUG-asserted below.
; Entity work therefore reduces to: shift EVERY buffered ring's and
; slot-tagged object's X by the rebase delta, then rebuild the scan
; entries (same sections, re-expressed origins; loaded masks survive via
; InitSection's same-section path + slot-to-same-slot migration). No
; keep-window, no despawn, no populate — nothing spawns or dies at a seam.
;
; In:  d0.w = shift amount (+SECTION_SHIFT or -SECTION_SHIFT)
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_TeleportShift:
        move.w  d0, d4                  ; d4 = shift

        ; --- shift all buffered rings ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0
.ring_loop:
        add.w   d4, (a0)                ; engine_X += delta
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
        dbf     d5, .ring_loop
.rings_done:

        ; --- shift all slot-tagged objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5
.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next
        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .obj_next
        add.w   d4, SST_x_pos(a0)       ; integer word of the 16.16 X
.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

    ifdef __DEBUG__
        ; anchor stash: RebuildScanState clobbers d0-d7/a0-a4 and
        ; Entity_Mask_Scratch is FULL inside Slide (4 ids + 128 mask bytes),
        ; so the stack is the stash — balanced across the bsr.
        move.w  (Entity_Window_Anchor).w, -(sp)
    endif
        bsr.w   EntityWindow_RebuildScanState
    ifdef __DEBUG__
        ; teleport invariance: the rebase must not move the anchor
        move.w  (sp)+, d0               ; pre-rebase anchor
        move.w  (Entity_Window_Anchor).w, d1
        assert.w d1, eq, d0
    endif
        rts

; -----------------------------------------------
; EntityWindow_TeleportShiftY — re-express entities after a Y teleport rebase
;
; Vertical mirror of EntityWindow_TeleportShift (see its header for the
; invariance argument): slot-map sec_y advance (±2) cancels the camera
; delta's row0 shift (∓2) — same sections, re-expressed origins. Shifts
; ring Y (buffer entry +2) and SST_y_pos. RebuildScanState also rebases
; Camera_Y_Coarse_Prev, so the vertical re-scan trigger doesn't
; false-fire off the rebased camY.
;
; In:  d0.w = shift amount (+SECTION_SHIFT or -SECTION_SHIFT)
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_TeleportShiftY:
        move.w  d0, d4                  ; d4 = shift

        ; --- shift all buffered rings ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0
.ring_loop:
        add.w   d4, 2(a0)               ; engine_Y += delta
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
        dbf     d5, .ring_loop
.rings_done:

        ; --- shift all slot-tagged objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5
.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next
        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .obj_next
        add.w   d4, SST_y_pos(a0)       ; integer word of the 16.16 Y
.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

    ifdef __DEBUG__
        ; anchor stash on the stack — see EntityWindow_TeleportShift
        move.w  (Entity_Window_Anchor).w, -(sp)
    endif
        bsr.w   EntityWindow_RebuildScanState
    ifdef __DEBUG__
        move.w  (sp)+, d0               ; pre-rebase anchor
        move.w  (Entity_Window_Anchor).w, d1
        assert.w d1, eq, d0
    endif
        rts

; -----------------------------------------------
; EntityWindow_MigrateMasks — move loaded masks to sections' new entries
;
; Generic identity match: for each NEW entry, find its section id in the
; old snapshot; on match copy the old 32-byte mask into the entry's live
; slot. Sections new to the window keep the compare-clear's zeroed mask.
; Handles any slide direction — including the (DEBUG-asserted-impossible)
; diagonal — and the teleport case, where every copy is slot-to-same-slot.
; Old SEC_VOID snapshot ids can't false-match: new valid ids are real.
; Cold path (slides/teleports only) — clarity over cycles.
;
; In:  a4 = snapshot: 4 bytes old section ids + 4×32 bytes old masks
; Out: none
; Clobbers: d0-d3, a0-a1
; -----------------------------------------------
EntityWindow_MigrateMasks:
        moveq   #0, d3                  ; d3 = new entry index
.new_loop:
        ; d2.b = new entry d3's section id (entry stride $1A: ×26 = ×16+×8+×2)
        move.w  d3, d0
        lsl.w   #4, d0
        move.w  d3, d1
        lsl.w   #3, d1
        add.w   d1, d0
        move.w  d3, d1
        add.w   d1, d1
        add.w   d1, d0
        lea     (Entity_Scan_State+EntityScanState_ess_section_id).w, a0
        move.b  (a0, d0.w), d2
        cmpi.b  #SEC_VOID, d2
        beq.s   .new_next               ; void entry — nothing to receive

        lea     (a4), a0                ; snapshot section ids
        moveq   #0, d0                  ; d0 = old entry index
.old_loop:
        cmp.b   (a0)+, d2
        beq.s   .match
        addq.w  #1, d0
        cmpi.w  #MAX_TRACKED_SECTIONS, d0
        blo.s   .old_loop
        bra.s   .new_next               ; not previously tracked — mask stays zeroed

.match:
        lea     4(a4), a0               ; snapshot mask block
        lsl.w   #5, d0                  ; old entry × ENTITY_LOADED_SLOT_SIZE
        adda.w  d0, a0
        lea     (Entity_Loaded_Masks).w, a1
        move.w  d3, d1
        lsl.w   #5, d1                  ; new entry × ENTITY_LOADED_SLOT_SIZE
        adda.w  d1, a1
        moveq   #ENTITY_LOADED_SLOT_SIZE/4-1, d1
.copy:
        move.l  (a0)+, (a1)+
        dbf     d1, .copy

.new_next:
        addq.w  #1, d3
        cmpi.w  #MAX_TRACKED_SECTIONS, d3
        blo.s   .new_loop
        rts

; -----------------------------------------------
; EntityWindow_Slide — re-derive the window after the envelope crossed a
; section boundary (also the teleport rebuild body — see RebuildScanState)
;
; Snapshot old ids+masks → recenter collected 3×3 (evict BEFORE BuildEntries
; claims — claim-before-evict failed silently at 9/9 occupancy, see the bug
; note carried from the old RebuildScanState) → BuildEntries (compare-clear
; zeroes genuinely-new sections' masks) → migrate surviving masks by section
; identity → populate sections that weren't tracked before. Teleport rebases
; keep the section set invariant: every id is in the snapshot, masks migrate
; slot-to-same-slot, populate never fires — teleports are populate-free.
; Cold path (≤ once per ~2048px of travel) — clarity over cycles.
;
; In:  none (reads Camera_X/Y, Slot_Section_Map, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_Slide:
        ; snapshot the old window: 4 section-id bytes + the 128-byte mask block
        lea     (Entity_Mask_Scratch).w, a0
        move.b  (Entity_Scan_State+EntityScanState_ess_section_id).w, (a0)+
        move.b  (Entity_Scan_State+(EntityScanState_len*1)+EntityScanState_ess_section_id).w, (a0)+
        move.b  (Entity_Scan_State+(EntityScanState_len*2)+EntityScanState_ess_section_id).w, (a0)+
        move.b  (Entity_Scan_State+(EntityScanState_len*3)+EntityScanState_ess_section_id).w, (a0)+
        lea     (Entity_Loaded_Masks).w, a1
        moveq   #(MAX_TRACKED_SECTIONS*ENTITY_LOADED_SLOT_SIZE)/4-1, d0
.snapshot:
        move.l  (a1)+, (a0)+
        dbf     d0, .snapshot

        ; recenter the collected/killed 3×3 on the section containing the
        ; camera CENTER (DeriveWindow-style math on camX+160 / camY+112 —
        ; always in-grid, so FlatIDXY needs no range check)
        move.w  (Camera_X).w, d4
        subi.w  #SLOT_ORIGIN_L-(SCREEN_WIDTH/2), d4
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d4                  ; column of the camera center
        move.w  (Camera_Y).w, d5
        subi.w  #SLOT_ORIGIN_U-(SCREEN_HEIGHT/2), d5
        asr.w   d0, d5                  ; row of the camera center
        move.b  (Slot_Section_Map).w, d2
        add.b   d4, d2                  ; sec_x
        move.b  (Slot_Section_Map+1).w, d3
        add.b   d5, d3                  ; sec_y
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_FlatIDXY        ; d0.w = camera-center flat id
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        bsr.w   Collected_UpdateCenter

    ifdef __DEBUG__
        move.w  (Entity_Window_Anchor).w, -(sp) ; old anchor (snapshot holds ids, not the anchor)
    endif
        bsr.w   EntityWindow_BuildEntries

    ifdef __DEBUG__
        ; single-axis invariant: at most one anchor byte changes per slide
        ; (16px/f camera clamp); teleport rebuilds change neither
        move.w  (sp)+, d0               ; old anchor
        move.w  (Entity_Window_Anchor).w, d1
        eor.w   d0, d1                  ; nonzero byte = that axis moved
        tst.b   d1
        beq.s   .axis_ok                ; sec_y0 unchanged → at most X slid
        andi.w  #$FF00, d1              ; sec_y0 slid → sec_x0 must not have
        assert.w d1, eq
.axis_ok:
    endif

        ; migrate surviving sections' loaded masks to their new entries
        lea     (Entity_Mask_Scratch).w, a4
        bsr.w   EntityWindow_MigrateMasks

        ; populate entries whose section was NOT tracked before (band-gated;
        ; survivors' ids are in the snapshot — incl. every teleport entry)
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6
.populate_loop:
        move.b  (Entity_Window_Active).w, d0
        btst    d6, d0
        beq.s   .populate_next
        move.b  EntityScanState_ess_section_id(a3), d0
        lea     (Entity_Mask_Scratch).w, a0
        moveq   #MAX_TRACKED_SECTIONS-1, d1
.old_id_scan:
        cmp.b   (a0)+, d0
        dbeq    d1, .old_id_scan
        beq.s   .populate_next          ; id survived the slide — nothing new
        lea     (a3), a1
        bsr.w   EntityWindow_PopulateSectionRings       ; clobbers d0-d4/a0/a2 — d6/a3 safe
.populate_next:
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d6
        cmpi.w  #MAX_TRACKED_SECTIONS, d6
        blo.s   .populate_loop
        rts

; -----------------------------------------------
; EntityWindow_RebuildScanState — teleport-path window re-derivation
;
; Called after a teleport rebase updates Camera + Slot_Section_Map. The
; window is visibility-derived, so the rebase leaves the tracked section
; set invariant — the shared slide body re-expresses origins, migrates
; every mask slot-to-same-slot, and (all ids in the snapshot) populates
; nothing. Only extra work vs a slide: rebase the vertical re-scan
; trigger so the next coarse crossing is real.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a4
; -----------------------------------------------
EntityWindow_RebuildScanState:
        move.w  (Camera_Y).w, d0
        andi.w  #ENTITY_RESCAN_COARSE_MASK, d0
        move.w  d0, (Camera_Y_Coarse_Prev).w
        bra.w   EntityWindow_Slide
