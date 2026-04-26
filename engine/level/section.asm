; Section streaming engine (§4 Phase 1)
; Bidirectional leapfrog with 2 horizontal slots.
; Slot origins are FIXED. Section index selects which data is in each slot.

SLOT_LEFT   = 0
SLOT_RIGHT  = 1

; -----------------------------------------------
; Section_Init — set up slots from act descriptor, fill nametable
; In:  a0 = act descriptor pointer (Act_Desc struct)
; Out: none
; Clobbers: d0–d5, a0–a3
; -----------------------------------------------
Section_Init:
        move.l  a0, (Current_Act_Ptr).w

        ; -- set fixed slot origins --
        ; Slot_Origins layout: [origin_x.l][origin_y.l] × 4 slots
        lea     (Slot_Origins).w, a1
        move.l  #SLOT_ORIGIN_L<<16, (a1)+          ; slot 0 x (16.16)
        move.l  #0, (a1)+                          ; slot 0 y
        move.l  #SLOT_ORIGIN_R<<16, (a1)+          ; slot 1 x
        move.l  #0, (a1)+                          ; slot 1 y

        ; -- initialise section map from act descriptor --
        lea     (Slot_Section_Map).w, a2
        move.b  Act_start_sec_x(a0), (a2)+         ; slot 0 sec_x
        move.b  Act_start_sec_y(a0), (a2)+         ; slot 0 sec_y
        move.b  Act_start_sec_x(a0), d0
        addq.b  #1, d0
        move.b  d0, (a2)+                          ; slot 1 sec_x = start + 1
        move.b  Act_start_sec_y(a0), (a2)+         ; slot 1 sec_y = same row

        ; -- clear teleport guard + preload flags --
        move.w  #0, (Section_Preload_Flags).w

        ; -- fill nametable from both slots --
        bsr.w   Section_FillInitial

        rts

; -----------------------------------------------
; Section_FillInitial — fill full 64-column nametable from slot 0+1 data
; Called once at init. Drains via VSync each batch (buffer ~22 entries).
; Clobbers: d0–d5, a0–a3
; -----------------------------------------------
Section_FillInitial:
        ; Slot 0: columns 0–31 → nametable cols 0–31
        ; Slot 1: columns 0–31 → nametable cols 32–63
        ; Buffer holds ~22 entries → 3 batches needed

        ; -- first batch: slot 0 columns 0–21 --
        bsr.w   .fill_slot0_batch1
        move.b  #1, (VBlank_Ready).w
.wait1: tst.b   (VBlank_Flag).w
        beq.s   .wait1
        move.b  #0, (VBlank_Flag).w

        ; -- second batch: slot 0 cols 22–31 + slot 1 cols 0–9 --
        bsr.w   .fill_slot0_batch2
        bsr.w   .fill_slot1_batch1
        move.b  #1, (VBlank_Ready).w
.wait2: tst.b   (VBlank_Flag).w
        beq.s   .wait2
        move.b  #0, (VBlank_Flag).w

        ; -- third batch: slot 1 cols 10–31 --
        bsr.w   .fill_slot1_batch2
        move.b  #1, (VBlank_Ready).w
.wait3: tst.b   (VBlank_Flag).w
        beq.s   .wait3
        move.b  #0, (VBlank_Flag).w

        rts

.fill_slot0_batch1:
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef.slot0
        moveq   #22-1, d4
        moveq   #0, d5
.s0b1:  move.w  d5, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        dbf     d4, .s0b1
        rts

.fill_slot0_batch2:
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef.slot0
        moveq   #10-1, d4
        moveq   #22, d5
.s0b2:  move.w  d5, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        dbf     d4, .s0b2
        rts

.fill_slot1_batch1:
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef.slot1
        moveq   #10-1, d4
        moveq   #0, d5
        moveq   #32, d6
.s1b1:  move.w  d6, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        addq.w  #1, d6
        dbf     d4, .s1b1
        rts

.fill_slot1_batch2:
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef.slot1
        moveq   #22-1, d4
        moveq   #10, d5
        moveq   #42, d6
.s1b2:  move.w  d6, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        addq.w  #1, d6
        dbf     d4, .s1b2
        rts

; -----------------------------------------------
; Section_GetSlotDef — get Sec* for a given slot index
; In:  d0.w = slot index (0 or 1 for Phase 1)
;      a2   = act descriptor pointer
; Out: a0   = Sec struct pointer in ROM
; Clobbers: d0–d1, a0–a1
; -----------------------------------------------
Section_GetSlotDef:
        add.w   d0, d0                             ; slot_index × 2 bytes
        lea     (Slot_Section_Map).w, a0
        move.b  (a0, d0.w), d1                     ; d1.b = sec_x for this slot
        movea.l Act_sec_grid_ptr(a2), a1
        ; sec_x × Sec_len ($40) = sec_x × 64 = sec_x << 6
        moveq   #0, d0
        move.b  d1, d0
        lsl.w   #6, d0
        adda.w  d0, a1                             ; a1 → Sec struct for this section
        movea.l a1, a0
        rts

.slot0: moveq   #SLOT_LEFT, d0
        bra.w   Section_GetSlotDef

.slot1: moveq   #SLOT_RIGHT, d0
        bra.w   Section_GetSlotDef

; -----------------------------------------------
; Section_Check — per-frame teleport threshold check (horizontal)
; Call from game loop each frame.
; In:  none
; Out: none
; Clobbers: d0, a0
; -----------------------------------------------
Section_Check:
        tst.b   (Section_Teleport_Guard).w
        beq.s   .check
        subq.b  #1, (Section_Teleport_Guard).w
        rts

.check:
        move.l  (Camera_X).w, d0
        swap    d0                                 ; d0.w = camera X in pixels

        cmpi.w  #SECTION_FWD_THRESHOLD, d0
        bge.s   .fwd
        cmpi.w  #SECTION_BWD_THRESHOLD, d0
        ble.s   .bwd
        rts

.fwd:   bra.w   Section_TeleportFwd
.bwd:   bra.w   Section_TeleportBwd

; -----------------------------------------------
; Section_TeleportFwd — forward (rightward) teleport
; Old slot 1 becomes slot 0. Loads next section into slot 1.
; Clobbers: d0–d3, a0–a1
; -----------------------------------------------
Section_TeleportFwd:
        move.l  (Camera_X).w, d0
        subi.l  #SECTION_SHIFT<<16, d0
        move.l  d0, (Camera_X).w

        lea     (Slot_Section_Map).w, a0
        move.b  2(a0), d0                          ; old slot 1 sec_x
        move.b  3(a0), d1                          ; old slot 1 sec_y
        move.b  d0, (a0)                           ; new slot 0 sec_x
        move.b  d1, 1(a0)                          ; new slot 0 sec_y
        addq.b  #1, d0                             ; new slot 1 sec_x = slot 0 + 1
        move.b  d0, 2(a0)
        ; sec_y unchanged

        movea.l (Current_Act_Ptr).w, a1
        bsr.w   Section_QueueNewSlot1Cols

        move.b  #4, (Section_Teleport_Guard).w
        rts

; -----------------------------------------------
; Section_TeleportBwd — backward (leftward) teleport
; Old slot 0 becomes slot 1. Loads previous section into slot 0.
; Clobbers: d0–d3, a0–a1
; -----------------------------------------------
Section_TeleportBwd:
        move.l  (Camera_X).w, d0
        addi.l  #SECTION_SHIFT<<16, d0
        move.l  d0, (Camera_X).w

        lea     (Slot_Section_Map).w, a0
        move.b  (a0), d0                           ; old slot 0 sec_x
        move.b  1(a0), d1                          ; old slot 0 sec_y
        move.b  d0, 2(a0)                          ; new slot 1 sec_x
        move.b  d1, 3(a0)                          ; new slot 1 sec_y
        tst.b   d0
        beq.s   .clamp_zero
        subq.b  #1, d0
.clamp_zero:
        move.b  d0, (a0)                           ; new slot 0 sec_x = old - 1

        movea.l (Current_Act_Ptr).w, a1
        bsr.w   Section_QueueNewSlot0Cols

        move.b  #4, (Section_Teleport_Guard).w
        rts

; -----------------------------------------------
; Section_QueueNewSlot1Cols — queue slot 1 tile columns (nametable cols 32–63)
; In:  a1 = act descriptor pointer
; Clobbers: d0–d5, a0–a2
; -----------------------------------------------
Section_QueueNewSlot1Cols:
        movea.l a1, a2
        bsr.w   Section_GetSlotDef.slot1           ; a0 = new slot 1 Sec def
        moveq   #32-1, d4
        moveq   #0, d5                             ; section tile col
        moveq   #32, d6                            ; nametable col
.qloop1:
        move.w  d6, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        addq.w  #1, d6
        dbf     d4, .qloop1
        rts

; -----------------------------------------------
; Section_QueueNewSlot0Cols — queue slot 0 tile columns (nametable cols 0–31)
; In:  a1 = act descriptor pointer
; Clobbers: d0–d5, a0–a2
; -----------------------------------------------
Section_QueueNewSlot0Cols:
        movea.l a1, a2
        bsr.w   Section_GetSlotDef.slot0
        moveq   #32-1, d4
        moveq   #0, d5
        moveq   #0, d6
.qloop0:
        move.w  d6, d0
        move.w  d5, d1
        bsr.w   Draw_TileColumn
        addq.w  #1, d5
        addq.w  #1, d6
        dbf     d4, .qloop0
        rts

; -----------------------------------------------
; Section_EngineToWorld — convert engine X + slot to world X
; In:  d0.w = engine X (pixel)
;      d1.b = slot index (0 or 1)
; Out: d0.l = world X = (sec_x × SECTION_SIZE) + (engine_x - SLOT_ORIGIN_L)
; Clobbers: d0–d2
; -----------------------------------------------
Section_EngineToWorld:
        add.w   d1, d1                             ; slot_index × 2
        lea     (Slot_Section_Map).w, a0
        moveq   #0, d2
        move.b  (a0, d1.w), d2                     ; d2.b = sec_x for this slot
        lsl.l   #8, d2                             ; d2 = sec_x × $800 (SECTION_SIZE)
        lsl.l   #3, d2                             ; (11-bit shift split: 8+3)
        subi.w  #SLOT_ORIGIN_L, d0                 ; d0 = engine_x - $200
        ext.l   d0
        add.l   d2, d0                             ; d0 = world_x
        rts

; -----------------------------------------------
; Section_WorldToEngine — convert section-local X to engine X
; In:  d1.w = section-local X (0–$7FF)
; Out: d0.w = engine X = SLOT_ORIGIN_L + local_x
; Clobbers: d0
; -----------------------------------------------
Section_WorldToEngine:
        addi.w  #SLOT_ORIGIN_L, d1
        move.w  d1, d0
        rts
