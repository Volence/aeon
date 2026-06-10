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
        bsr.s   Collected_FindSlot
        movem.l (sp)+, d0-d1
        beq.s   .uncollected

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
        bsr.s   Collected_FindSlot
        beq.s   .done
        moveq   #0, d1
        move.b  d3, d1
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

        move.w  d1, d2
        lsr.w   #3, d2
        btst    d1, KILLED_BITMASK_OFFSET(a0, d2.w)
        rts

.alive:
        moveq   #0, d2
        rts

; -----------------------------------------------
; Killed_MarkObject — mark object as killed in bitmask
;
; In:  d0.b = section_id
;      d1.b = list_index
; Out: none
; Clobbers: d0, d2, a0
; -----------------------------------------------
Killed_MarkObject:
        move.w  d1, -(sp)
        bsr.w   Collected_FindSlot
        move.w  (sp)+, d1
        beq.s   .markdone
        moveq   #0, d2
        move.b  d1, d2
        move.w  d2, d0
        lsr.w   #3, d0
        bset    d2, KILLED_BITMASK_OFFSET(a0, d0.w)
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
        bsr.s   Collected_FindSlot
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
; Collected_UpdateCenter — evict slots outside new 3×3 range
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

        ; Check |slot_x - center_x| <= 2
        sub.w   d2, d1
        bpl.s   .sx_pos
        neg.w   d1
.sx_pos:
        cmpi.w  #2, d1
        bhi.s   .evict

        ; Check |slot_y - center_y| <= 2
        sub.w   d4, d0
        bpl.s   .sy_pos
        neg.w   d0
.sy_pos:
        cmpi.w  #2, d0
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
; Entity Window Core
; =====================================================

; -----------------------------------------------
; EntityWindow_InitSection — populate one EntityScanState entry
;
; In:  a0 = Sec struct pointer (ROM)
;      a1 = EntityScanState pointer (RAM)
;      d0.w = section origin X (engine-space)
;      d1.b = section_id
; Out: none
; Clobbers: none
; -----------------------------------------------
EntityWindow_InitSection:
        move.l  Sec_sec_rings(a0), EntityScanState_ess_rom_ring_ptr(a1)
        move.l  Sec_sec_objects(a0), EntityScanState_ess_rom_obj_ptr(a1)
        move.l  Sec_sec_type_table(a0), EntityScanState_ess_rom_type_tbl_ptr(a1)
        move.w  d0, EntityScanState_ess_origin_x(a1)
        move.b  d1, EntityScanState_ess_section_id(a1)
        clr.b   EntityScanState_ess_pad(a1)
        clr.w   EntityScanState_ess_ring_right_idx(a1)
        clr.w   EntityScanState_ess_ring_left_idx(a1)
        clr.w   EntityScanState_ess_obj_right_idx(a1)
        clr.w   EntityScanState_ess_obj_left_idx(a1)
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

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d7                  ; tracked section count

        ; --- Active slot 0 ---
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef      ; a0 = Sec ptr
        movea.l a0, a4                  ; save Sec ptr
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID      ; d0.w = flat section_id (sec_y*grid_w+sec_x)
        move.w  d0, d1                  ; d1.b = section_id
        movea.l a4, a0                  ; restore Sec ptr
        move.w  #SLOT_ORIGIN_L, d0     ; origin X
        lea     (a3), a1               ; scan state entry
        bsr.w   EntityWindow_InitSection
        ; Claim bitmask slot
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d7

        ; --- Active slot 1 ---
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef
        movea.l a0, a4
        moveq   #SLOT_RIGHT, d0
        bsr.w   Section_SlotFlatID      ; d0.w = flat section_id
        move.w  d0, d1
        movea.l a4, a0
        move.w  #SLOT_ORIGIN_R, d0
        lea     (a3), a1
        bsr.w   EntityWindow_InitSection
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d7

        move.b  d7, (Entity_Window_Active).w

        ; Set center section for collected bitmask window (slot 0 flat id)
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        bsr.w   Collected_UpdateCenter

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
        moveq   #0, d5
        move.b  (Entity_Window_Active).w, d5
        beq.s   .scan_done
        subq.w  #1, d5

        ; Compute window edges
        move.w  (Camera_X).w, d6
        move.w  d6, d7
        addi.w  #SCREEN_WIDTH+ENTITY_LOAD_BUFFER, d7   ; d7 = right load edge

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d6                  ; d6.b = slot tag (0=left, 1=right)

.section_loop:
        lea     (a3), a1
        bsr.w   EntityWindow_ScanRingsRight
        bsr.w   EntityWindow_ScanObjectsRight
        lea     EntityScanState_len(a3), a3
        addq.b  #1, d6
        dbf     d5, .section_loop

.scan_done:
        bsr.w   EntityWindow_DespawnRings
        bsr.w   EntityWindow_DespawnObjects
        rts

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
        beq.s   .done
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

        ; Spawn ring into buffer
        movem.l d3-d4/d7/a0-a1, -(sp)
        move.w  (a0), d0
        add.w   d3, d0                  ; engine X
        move.w  2(a0), d1               ; engine Y (section-local = engine for 1-row)
        move.b  EntityScanState_ess_section_id(a1), d2  ; section_id
        move.b  d4, d3                  ; list_index
        bsr.w   RingBuffer_Add
        movem.l (sp)+, d3-d4/d7/a0-a1

.skip:
        addq.w  #1, d4
        addq.w  #4, a0
        bra.s   .loop

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

        ; Pass 2: add all uncollected rings to buffer
        movea.l a2, a0
        moveq   #0, d4
.ploop:
        move.l  (a0), d1
        beq.s   .pdone

        movem.l d3-d4/a0-a1, -(sp)
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1
        bsr.w   Collected_CheckRing
        movem.l (sp)+, d3-d4/a0-a1
        bne.s   .pskip

        movem.l d3-d4/a0-a1, -(sp)
        move.w  (a0), d0
        add.w   d3, d0
        move.w  2(a0), d1
        move.b  EntityScanState_ess_section_id(a1), d2
        move.b  d4, d3
        bsr.w   RingBuffer_Add
        movem.l (sp)+, d3-d4/a0-a1

.pskip:
        addq.w  #1, d4
        addq.w  #4, a0
        bra.s   .ploop

.pdone:
        rts

; -----------------------------------------------
; EntityWindow_ScanObjectsRight — load objects entering right edge
;
; Entry format (v2): 6 bytes — dc.w x, y, flags|type|subtype
;   +0 dc.w  section-local X
;   +2 dc.w  section-local Y   (engine Y for current 1-row window — §4.9 X-only)
;   +4 dc.w  flags|type|subtype  (OEF_* bits; flows to Load_Object in d2)
; Terminated by dc.w -1 (X is section-local, always >= 0 → bmi fires on sentinel).
; List is X-sorted; bhi exits as soon as X exceeds load edge.
;
; In:  a1 = EntityScanState pointer
;      d6.b = slot tag (SLOT_TAG_LEFT or SLOT_TAG_RIGHT)
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
        bmi.s   .obj_update_idx         ; bmi fires on -1 terminator

        ; Engine-space X
        add.w   d3, d0

        ; Past right edge? List is X-sorted, stop
        cmp.w   d7, d0
        bhi.s   .obj_update_idx

        ; Check if object was killed in previous visit
        movem.l d0/a0, -(sp)
        move.b  EntityScanState_ess_section_id(a1), d0
        moveq   #0, d1
        move.w  d4, d1
        bsr.w   Killed_CheckObject
        movem.l (sp)+, d0/a0
        bne.s   .obj_skip

        ; Spawn this object (d5 stashes section_id; a3 saved: Load_Object clobbers it; d4-d7 preserved by Load_Object)
        movem.l d3-d7/a0-a1/a3, -(sp)

        moveq   #0, d5
        move.b  EntityScanState_ess_section_id(a1), d5

        ; d0.w = engine X (already computed above)
        move.w  2(a0), d1               ; section-local Y (engine Y for 1-row window)
        move.w  4(a0), d2               ; full placement word — Load_Object reads flips from bits 13-14

        ; Type extraction: bits 12-8 → d3, then type-table lookup
        move.w  4(a0), d3
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

.obj_spawn_fail:
        movem.l (sp)+, d3-d7/a0-a1/a3

.obj_skip:
        addq.w  #1, d4
        adda.w  #OBJ_ENTRY_SIZE, a0
        bra.s   .obj_loop

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
        cmp.b   (Entity_Scan_State+EntityScanState_len+EntityScanState_ess_section_id).w, d1
        beq.s   .next

.remove:
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
        cmp.b   (Entity_Scan_State+EntityScanState_len+EntityScanState_ess_section_id).w, d1
        beq.s   .next

.despawn:
        movem.l d5-d7/a0, -(sp)
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
        lea     (Entity_Scan_State).w, a3
        moveq   #0, d7

        ; Slot 0
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef
        movea.l a0, a4
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID      ; d0.w = flat section_id
        move.w  d0, d1
        movea.l a4, a0
        move.w  #SLOT_ORIGIN_L, d0
        lea     (a3), a1
        bsr.w   EntityWindow_InitSection
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        bsr.w   EntityWindow_PopulateSectionRings
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d7

        ; Slot 1
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef
        movea.l a0, a4
        moveq   #SLOT_RIGHT, d0
        bsr.w   Section_SlotFlatID      ; d0.w = flat section_id
        move.w  d0, d1
        movea.l a4, a0
        move.w  #SLOT_ORIGIN_R, d0
        lea     (a3), a1
        bsr.w   EntityWindow_InitSection
        moveq   #0, d0
        move.b  EntityScanState_ess_section_id(a1), d0
        bsr.w   Collected_ClaimSlot
        bsr.w   EntityWindow_PopulateSectionRings
        lea     EntityScanState_len(a3), a3
        addq.w  #1, d7

        move.b  d7, (Entity_Window_Active).w

        ; Update collected bitmask center (slot 0 flat id)
        moveq   #SLOT_LEFT, d0
        bsr.w   Section_SlotFlatID
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        bsr.w   Collected_UpdateCenter
        rts
