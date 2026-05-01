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

        ; -- §4.9: camera-driven entity window init --
        jsr     EntityWindow_Init

 ; -----------------------------------------------
; Section_FillInitial — set up trackers; let Section_UpdateColumns
; fill plane on first frame (matches post-teleport behavior).
;
; Previously pre-filled plane cols 0..63 with section cols 0..63
; (linear order). This caused a visual artifact: when user scrolled
; right past Cam_X = 689, streaming overwrote plane col 0 with
; section col 64. Plane col 0 then visible at screen LEFT at Cam_X
; = 1024 with section col 64 — content "appearing from left."
;
; New behavior: trackers set as if Section_TeleportFwd just fired.
; Section_UpdateColumns on first frame streams the visible window
; in scroll-direction order (= same as post-teleport behavior, which
; doesn't show the artifact). User sees plane fill from screen-left
; outward over ~3 frames as Plane_Buffer drains, then steady-state
; matches Section_UpdateColumns' streaming pattern.
;
; Out: Section_Right_Col_Written, Section_Left_Col_Written initialised
; Clobbers: none
; -----------------------------------------------
Section_FillInitial:
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                          ; d0 = engine tile col of camera left
        bsr.w   Engine_To_World_Col             ; d0 = world col
        subq.w  #1, d0
        move.w  d0, (Section_Right_Col_Written).w
        addq.w  #1, d0
        move.w  d0, (Section_Left_Col_Written).w
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
        ; sec_x × Sec_len ($48 = 72): compute as sec_x*64 + sec_x*8
        moveq   #0, d0
        move.b  d1, d0
        move.w  d0, d2
        lsl.w   #6, d0                             ; sec_x × 64
        lsl.w   #3, d2                             ; sec_x × 8
        add.w   d2, d0                             ; sec_x × 72 = Sec_len
        adda.w  d0, a1                             ; a1 → Sec struct for this section
        movea.l a1, a0
        rts

.slot0: moveq   #SLOT_LEFT, d0
        bra.w   Section_GetSlotDef

.slot1: moveq   #SLOT_RIGHT, d0
        bra.w   Section_GetSlotDef

; -----------------------------------------------
; Section_GetSecPtrXY — Sec ptr lookup by grid coordinates (§4.2).
; In:  d2.b = sec_x, d3.b = sec_y (unused — 1-row grid only), a2 = Act ptr
; Out: a0 = Sec ptr; Z clear if found, Z set if out of range (a0 = 0)
; Clobbers: d0, d1
; Note: Phase 1 single-row layout (grid_h = 1). Multi-row deferred.
; -----------------------------------------------
Section_GetSecPtrXY:
        cmp.b   Act_grid_w+1(a2), d2
        bcc.s   .out_of_range                       ; sec_x >= grid_w (unsigned)
        moveq   #0, d0
        move.b  d2, d0
        movea.l Act_sec_grid_ptr(a2), a0
        move.w  d0, d1
        lsl.w   #6, d0                              ; sec_x × 64
        lsl.w   #3, d1                              ; sec_x × 8
        add.w   d1, d0                              ; sec_x × 72 = Sec_len
        adda.w  d0, a0
        moveq   #1, d0                              ; Z clear (success)
        rts
.out_of_range:
        suba.l  a0, a0                              ; a0 = 0
        moveq   #0, d0                              ; Z set (not found)
        rts

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
        ; Guard active — hold only while player sits exactly on a threshold
        move.l  (Player_1+SST_x_pos).w, d0
        swap    d0
        cmpi.w  #SECTION_FWD_THRESHOLD, d0
        beq.s   .guard_hold
        cmpi.w  #SECTION_BWD_THRESHOLD, d0
        beq.s   .guard_hold
        clr.b   (Section_Teleport_Guard).w
.guard_hold:
        rts

.check:
        ; -- §4.2: thresholds keyed off Player_1's x_pos (not Camera_X) so
        ;    teleport fires when the CHARACTER crosses the boundary, not when
        ;    the camera does. Camera lags player by deadzone; if we used
        ;    camera_x, teleport would fire ~16 px after the player visually
        ;    crossed the line. --
        move.l  (Player_1+SST_x_pos).w, d0
        swap    d0                                 ; d0.w = player engine X

        ; -- §4.2 deferred cold-loads — fire when camera passes mid-traversal
        ;    threshold of new pair's first section. Independent of camera
        ;    direction; gated by both range and pending flag. --
        btst    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
        beq.s   .skip_deferred_fwd
        cmpi.w  #SECTION_DEFERRED_FWD_LOAD, d0
        blt.s   .skip_deferred_fwd
        bsr.w   .deferred_fwd_load
        bclr    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
.skip_deferred_fwd:
        btst    #SPF_DEFERRED_BWD_LOAD, (Section_Preload_Flags).w
        beq.s   .skip_deferred_bwd
        cmpi.w  #SECTION_DEFERRED_BWD_LOAD, d0
        bgt.s   .skip_deferred_bwd
        bsr.w   .deferred_bwd_load
        bclr    #SPF_DEFERRED_BWD_LOAD, (Section_Preload_Flags).w
.skip_deferred_bwd:

        ; -- preload triggers (§2 A.4) — fire BEFORE teleport thresholds --
        cmpi.w  #SECTION_FWD_PRELOAD, d0
        bge.s   .fwd_preload_check
        cmpi.w  #SECTION_BWD_PRELOAD, d0
        ble.s   .bwd_preload_check
        bra.s   .threshold_check

.fwd_preload_check:
        btst    #SPF_FWD_PRELOADED, (Section_Preload_Flags).w
        bne.s   .threshold_check
        bsr.w   .preload_fwd
        bset    #SPF_FWD_PRELOADED, (Section_Preload_Flags).w
        bra.s   .threshold_check

.bwd_preload_check:
        btst    #SPF_BWD_PRELOADED, (Section_Preload_Flags).w
        bne.s   .threshold_check
        bsr.w   .preload_bwd
        bset    #SPF_BWD_PRELOADED, (Section_Preload_Flags).w

.threshold_check:
        ; -- preload_{fwd,bwd} above clobber d0 (build a Sec offset). Reload
        ;    Player_1.x_pos high word so the threshold compares aren't reading
        ;    stale register state from the preload path. (§4.2: keyed off
        ;    player position, not camera — see .check entry comment.) --
        move.l  (Player_1+SST_x_pos).w, d0
        swap    d0
        cmpi.w  #SECTION_FWD_THRESHOLD, d0
        bge.w   .fwd_check
        cmpi.w  #SECTION_BWD_THRESHOLD, d0
        ble.w   .bwd_check
        rts

.preload_fwd:
        ; Section to forward = current slot 1's sec_x + 1 (clamped to grid_w).
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d6
        move.b  (Slot_Section_Map+2).w, d6         ; slot 1 sec_x (and section_id since 1-row)
        addq.b  #1, d6
        cmp.b   Act_grid_w+1(a2), d6
        bge.s   .preload_skip
        ; Compute Sec ptr for section_id d6.w
        movea.l Act_sec_grid_ptr(a2), a4
        moveq   #0, d0
        move.b  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0                             ; sec × 64
        lsl.w   #3, d1                             ; sec × 8
        add.w   d1, d0                             ; sec × 72 = Sec_len
        adda.w  d0, a4                             ; a4 = Sec ptr
        movea.l a4, a0                             ; a0 = Sec ptr (Section_StreamArtGroup convention)
        bra.w   Section_StreamArtGroup
.preload_skip:
        rts

.preload_bwd:
        ; Section to backward = current slot 0's sec_x - 1 (clamped to 0).
        movea.l (Current_Act_Ptr).w, a2
        moveq   #0, d6
        move.b  (Slot_Section_Map).w, d6           ; slot 0 sec_x
        tst.b   d6
        beq.s   .preload_skip                       ; already at section 0 → no BWD neighbour
        subq.b  #1, d6
        ; Compute Sec ptr for section_id d6.w
        movea.l Act_sec_grid_ptr(a2), a4
        moveq   #0, d0
        move.b  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0
        lsl.w   #3, d1
        add.w   d1, d0
        adda.w  d0, a4
        movea.l a4, a0
        bra.w   Section_StreamArtGroup

; -----------------------------------------------
; §4.2 deferred cold-load routines — invoked from .check when the deferred
; flag is set AND camera has reached the mid-traversal threshold.
;
; .deferred_fwd_load: fires at SECTION_DEFERRED_FWD_LOAD ($0600) post-FWD-teleport.
;                     Streams slot 1's section into VRAM. By this point camera
;                     has moved past the BWD-preview-visible window.
;
; .deferred_bwd_load: mirror for BWD-teleport, fires at $0C00.
; -----------------------------------------------
.deferred_fwd_load:
        clr.l   (Section_Bwd_Neighbor_Strips).w     ; old art about to be overwritten
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 1
        moveq   #0, d6
        move.b  (Slot_Section_Map+2).w, d6          ; slot 1 flat section_id
        movea.l a0, a4                              ; Section_StreamArtGroup convention
        bra.w   Section_StreamArtGroup

.deferred_bwd_load:
        clr.l   (Section_Fwd_Neighbor_Strips).w     ; old art about to be overwritten
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 0
        moveq   #0, d6
        move.b  (Slot_Section_Map).w, d6            ; slot 0 flat section_id
        movea.l a0, a4
        bra.w   Section_StreamArtGroup

.bwd_check:
        ; skip BWD if slot 0 already at leftmost section (sec_x = 0)
        tst.b   (Slot_Section_Map).w
        beq.s   .skip
        bra.w   Section_TeleportBwd

.fwd_check:
        ; skip FWD if slot 1 already at rightmost section (sec_x + 1 = grid_w)
        movea.l (Current_Act_Ptr).w, a0
        move.b  (Slot_Section_Map+2).w, d0
        addq.b  #1, d0
        cmp.b   Act_grid_w+1(a0), d0     ; grid_w is a word; low byte at +1
        bge.s   .skip
        bra.w   Section_TeleportFwd

.skip:  rts

; -----------------------------------------------
; Section_TeleportFwd — forward (rightward) teleport
; Old slot 1 becomes slot 0. Loads next section into slot 1.
; Clobbers: d0–d3, a0–a1
; -----------------------------------------------
Section_TeleportFwd:
        move.l  (Camera_X).w, d0
        subi.l  #SECTION_SHIFT<<16, d0
        move.l  d0, (Camera_X).w

        ; -- §4.2: player teleports with camera. Without this shift Player_1
        ;    stays at its old world X while camera rewinds, putting the
        ;    player off-screen. Same SECTION_SHIFT applies. --
        subi.l  #SECTION_SHIFT<<16, (Player_1+SST_x_pos).w

        ; -- block-style rotation: advance pair index by 1 = both slots advance
        ;    by 2 sections. New slot 0 takes the section that was preloaded
        ;    into slot 0 during slot 1 traversal (= old slot 1 + 1). New
        ;    slot 1 = the section after that. --
        lea     (Slot_Section_Map).w, a0
        move.b  2(a0), d0                          ; old slot 1 sec_x
        move.b  3(a0), d1                          ; old slot 1 sec_y
        addq.b  #1, d0                             ; new slot 0 sec_x = old slot 1 + 1
        ; TODO: clamp d0 to act grid width — Act_grid_w; Phase 1 safe (OJZ = 9 sections)
        move.b  d0, (a0)
        move.b  d1, 1(a0)
        addq.b  #1, d0                             ; new slot 1 sec_x = new slot 0 + 1
        move.b  d0, 2(a0)
        ; sec_y unchanged

        ; -- §4.9: shift nearby entities, despawn rest, rebuild scan state --
        move.w  #-SECTION_SHIFT, d0
        jsr     EntityWindow_TeleportShift

        st      (Section_Teleport_Guard).w

        ; -- A.4 + §4.2: reset all preload/deferred flags for the new pair --
        clr.b   (Section_Preload_Flags).w

        ; -- promote new slot 1 section's state to RESIDENT if already streaming.
        ;    If SS_IDLE, defer the load to SECTION_DEFERRED_FWD_LOAD ($0600) so
        ;    slot 1 retains the just-left section's art for BWD preview validity. --
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 1
        moveq   #0, d6
        move.b  (Slot_Section_Map+2).w, d6         ; slot 1 flat section_id
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0
        cmpi.b  #SS_IDLE, d0
        bne.s   .fwd_mark_resident
        ; -- §4.2 deferred cold-load — slot 1 keeps just-left art; load fires at $0600 --
        bset    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
        bra.s   .fwd_redraw_bg
.fwd_mark_resident:
        move.b  #SS_RESIDENT, (a1, d6.w)
.fwd_redraw_bg:
        ; -- §4.2: mark plane dirty for next-frame full atomic redraw.
        ;    Section_UpdateColumns picks this up and calls Section_RedrawPlanes,
        ;    rewriting both planes' nametables in one pass (matches sonic_hack
        ;    Dirty_flag → Draw_All pattern). Replaces the old per-teleport
        ;    BG_RedrawForSection burst.
        st      (Section_Plane_Dirty).w

        ; -- §4.6: force-snap parallax after teleport.
        ;    Camera_X jumped SECTION_SHIFT pixels — band scroll values must
        ;    snap to match. If the section has a config, force it as Current.
        ;    If NULL, fall back to act_parallax_config. --
        move.b  #1, (Parallax_Snap_Pending).w
        clr.l   (Parallax_Target_Config).w
        clr.b   (Parallax_Transition_Frames).w
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = new slot 0 sec ptr
        movea.l Sec_sec_parallax_config(a0), a0
        cmpa.w  #0, a0
        bne.s   .fwd_parallax_set
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
        cmpa.w  #0, a0
        beq.s   .fwd_parallax_done
.fwd_parallax_set:
        move.l  a0, (Parallax_Current_Config).w
.fwd_parallax_done:
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

        ; -- §4.2: player teleports with camera (mirror of FWD). --
        addi.l  #SECTION_SHIFT<<16, (Player_1+SST_x_pos).w

        ; -- block-style rotation: retreat pair index by 1 = both slots
        ;    retreat by 2 sections. New slot 1 takes the section that was
        ;    preloaded during slot 0 traversal (= old slot 0 - 1). New slot
        ;    0 = the section before that. Clamp to 0 if at act start. --
        lea     (Slot_Section_Map).w, a0
        move.b  (a0), d0                           ; old slot 0 sec_x
        move.b  1(a0), d1                          ; old slot 0 sec_y
        tst.b   d0
        beq.s   .at_start                          ; can't go below sec 0
        subq.b  #1, d0                             ; new slot 1 sec_x = old slot 0 - 1
        move.b  d0, 2(a0)
        move.b  d1, 3(a0)
        tst.b   d0
        beq.s   .clamp_zero
        subq.b  #1, d0                             ; new slot 0 sec_x = new slot 1 - 1
.clamp_zero:
        move.b  d0, (a0)                           ; new slot 0
.at_start:
        ; If we branched here, slot map is left as-is (Section_Check should
        ; guard BWD at sec 0 anyway).

        ; -- §4.9: shift nearby entities, despawn rest, rebuild scan state --
        move.w  #SECTION_SHIFT, d0
        jsr     EntityWindow_TeleportShift

        st      (Section_Teleport_Guard).w

        ; -- A.4 + §4.2: reset all preload/deferred flags for the new pair --
        clr.b   (Section_Preload_Flags).w

        ; -- defer slot 0 cold-load to SECTION_DEFERRED_BWD_LOAD ($0C00) so
        ;    slot 0 retains the just-left section's art for FWD preview validity. --
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 0
        moveq   #0, d6
        move.b  (Slot_Section_Map).w, d6           ; slot 0 flat section_id
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0
        cmpi.b  #SS_IDLE, d0
        bne.s   .bwd_mark_resident
        bset    #SPF_DEFERRED_BWD_LOAD, (Section_Preload_Flags).w
        bra.s   .bwd_redraw_bg
.bwd_mark_resident:
        move.b  #SS_RESIDENT, (a1, d6.w)
.bwd_redraw_bg:
        ; -- §4.2: mark plane dirty for next-frame full atomic redraw.
        ;    See Section_TeleportFwd's equivalent comment.
        st      (Section_Plane_Dirty).w

        ; -- §4.6: force-snap parallax (camera lands at $1200 = slot 1 territory). --
        move.b  #1, (Parallax_Snap_Pending).w
        clr.l   (Parallax_Target_Config).w
        clr.b   (Parallax_Transition_Frames).w
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = new slot 1 sec ptr
        movea.l Sec_sec_parallax_config(a0), a0
        cmpa.w  #0, a0
        bne.s   .bwd_parallax_set
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
        cmpa.w  #0, a0
        beq.s   .bwd_parallax_done
.bwd_parallax_set:
        move.l  a0, (Parallax_Current_Config).w
.bwd_parallax_done:
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
; Section_RedrawPlanes — camera-aware atomic full-plane rewrite at teleport (§4.2).
;
; Models sonic_hack's Dirty_flag → Draw_All pattern. At teleport, the entire
; visible plane content is rewritten in one synchronous pass via direct VDP
; pokes. No multi-frame scroll-across.
;
; Camera-aware: fills 64 plane cols starting at Camera_X/8, sourcing each
; world col from the correct region (BWD neighbor → slot 0 → slot 1 → FWD
; neighbor → tile-0 fill). This handles both FWD teleport (camera≈$0200)
; and BWD teleport (camera≈$1200) correctly.
;
; In:  none (reads Camera_X, Slot_Section_Map, Current_Act_Ptr, neighbor ptrs)
; Out: d5.w = start_world_col (for tracker reset by caller)
;      d7.w = start_world_col + 63 (for tracker reset by caller)
; Clobbers: d0–d7, a0–a4, a5–a6
; -----------------------------------------------
Section_RedrawPlanes:
        lea     (VDP_CTRL).l, a5
        lea     (VDP_DATA).l, a6
        move.w  sr, -(sp)
        move.w  #$2700, sr

        ; -- Plane A: column-major write --
        move.w  #$8F80, (a5)

        ; compute start world col
        move.l  (Camera_X).w, d5
        swap    d5
        lsr.w   #3, d5                          ; d5 = engine start tile col
        move.w  d5, d0
        bsr.w   Engine_To_World_Col             ; d0 = world start col
        move.w  d0, d5                          ; d5 = start_world_col

        moveq   #0, d3                          ; col counter (0..63)
        moveq   #0, d6                          ; zero for fill

.pla_fill:
        move.w  d5, d7
        add.w   d3, d7                          ; d7 = world_col
        move.w  d7, d0

        ; convert world col → engine col for nametable position
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0
        andi.w  #63, d0                         ; d0 = plane_col

        ; set VDP write address
        moveq   #0, d4
        move.w  d0, d4
        add.w   d4, d4
        addi.l  #VRAM_PLANE_A, d4
        vdpCommReg d4, VRAM, WRITE, 1
        move.l  d4, (a5)

        ; check if world_col is in cache range
        move.w  d7, d0
        cmp.w   (Strip_Cache_Left_Col).w, d0
        blt.s   .pla_zero_fill
        cmp.w   (Strip_Cache_Head_Col).w, d0
        bgt.s   .pla_zero_fill

        ; read from strip cache
        bsr.w   Strip_Cache_GetColumn           ; a0 = strip data
        movea.l a0, a1
        moveq   #STRIP_TILE_HEIGHT/2-1, d4
.pla_copy:
        move.l  (a1)+, (a6)
        dbf     d4, .pla_copy
        bra.s   .pla_next

.pla_zero_fill:
        moveq   #STRIP_TILE_HEIGHT/2-1, d4
.pla_zero:
        move.l  d6, (a6)
        dbf     d4, .pla_zero

.pla_next:
        addq.w  #1, d3
        cmpi.w  #64, d3
        blt.w   .pla_fill

        ; -- Plane B: row-major linear write (BG layout is act-wide, not position-dependent) --
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = slot 0 Sec ptr
        movea.l Sec_sec_bg_layout(a0), a1
        cmpa.w  #0, a1
        bne.s   .plb_have_layout
        movea.l Act_act_bg_layout(a2), a1           ; T1 fallback to act-level BG
        cmpa.w  #0, a1
        beq.s   .plb_done
.plb_have_layout:
        move.w  #$8F02, (a5)                        ; autoincrement $02 (row-major)
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (a5)
        move.w  #1024-1, d3                         ; 4096 bytes / 4 = 1024 longwords - 1
.plb_loop:
        move.l  (a1)+, (a6)
        dbf     d3, .plb_loop
.plb_done:
        ; Restore default autoincrement (matches VInt_DrawLevel cleanup)
        move.w  #$8F02, (a5)

        ; Restore interrupt mask (allow VBlank again)
        move.w  (sp)+, sr

        ; -- return tracker bounds in d5/d7 for caller --
        ; d5 = start_world_col (already set above)
        move.w  d5, d7
        addi.w  #63, d7                             ; d7 = start_world_col + 63
        rts

; -----------------------------------------------
; Section_UpdateColumns — per-frame nametable ring-buffer streaming
; Writes newly-revealed tile columns on right and left edges each frame.
; Must be called AFTER Camera_X is updated each frame.
; In:  none
; Out: none
; Clobbers: d0–d7, a0–a3, a5–a6 (a5/a6 only when Plane_Dirty triggers redraw)
; -----------------------------------------------
Section_UpdateColumns:
        ; -- §4.2: full-plane redraw if dirty (post-teleport atomic transition) --
        tst.b   (Section_Plane_Dirty).w
        beq.s   .not_dirty
        clr.b   (Section_Plane_Dirty).w
        bsr.w   Section_RedrawPlanes
        move.w  d7, (Section_Right_Col_Written).w
        move.w  d5, (Section_Left_Col_Written).w
        rts
.not_dirty:
        movem.l d2-d7/a0-a3, -(sp)

        move.l  (Camera_X).w, d6
        swap    d6                              ; d6.w = Camera_X pixels

        ; -------- right side --------
        move.w  d6, d7
        addi.w  #327, d7
        lsr.w   #3, d7                          ; d7 = right_needed engine tile col

        move.w  d7, d0
        bsr.w   Engine_To_World_Col
        move.w  d0, d7                          ; d7 = right_needed world col

        ; clamp to act boundary
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.w  Act_grid_w(a0), d0
        lsl.w   #8, d0
        subq.w  #1, d0
        cmp.w   d0, d7
        ble.s   .right_clamp_ok
        move.w  d0, d7
.right_clamp_ok:
        ; clamp to cache bounds
        move.w  (Strip_Cache_Head_Col).w, d0
        cmp.w   d0, d7
        ble.s   .right_cache_ok
        move.w  d0, d7
.right_cache_ok:

        move.w  (Section_Right_Col_Written).w, d5
.right_loop:
        cmp.w   d7, d5
        bge.w   .right_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + STRIP_TILE_HEIGHT*2), (Plane_Buffer_Ptr).w
        bhi.w   .right_done
        addq.w  #1, d5

        ; convert world col → engine col for nametable position
        move.w  d5, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0           ; d0 = engine tile col
        andi.w  #63, d0                         ; d0 = nametable col

        move.w  d5, d1                          ; d1 = world col
        bsr.w   Draw_TileColumn
        bra.w   .right_loop
.right_done:
        move.w  d5, (Section_Right_Col_Written).w
        move.w  d5, d3
        subi.w  #63, d3
        cmp.w   (Section_Left_Col_Written).w, d3
        ble.s   .left_clamp_skip
        move.w  d3, (Section_Left_Col_Written).w
.left_clamp_skip:

        ; -------- left side --------
        move.w  d6, d7
        lsr.w   #3, d7                          ; d7 = left edge engine tile col
        move.w  d7, d0
        bsr.w   Engine_To_World_Col
        move.w  d0, d7                          ; d7 = left_needed world col

        ; clamp to cache and act bounds
        move.w  (Strip_Cache_Left_Col).w, d0
        cmp.w   d0, d7
        bge.s   .left_cache_ok
        move.w  d0, d7
.left_cache_ok:

        move.w  (Section_Left_Col_Written).w, d5
.left_loop:
        cmp.w   d7, d5
        ble.w   .left_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + STRIP_TILE_HEIGHT*2), (Plane_Buffer_Ptr).w
        bhi.w   .left_done
        subq.w  #1, d5

        move.w  d5, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        sub.w   d1, d0
        addi.w  #SLOT_ORIGIN_L/8, d0
        andi.w  #63, d0

        move.w  d5, d1
        bsr.w   Draw_TileColumn
        bra.w   .left_loop
.left_done:
        move.w  d5, (Section_Left_Col_Written).w
        move.w  d5, d3
        addi.w  #63, d3
        cmp.w   (Section_Right_Col_Written).w, d3
        bge.s   .right_clamp_skip2
        move.w  d3, (Section_Right_Col_Written).w
.right_clamp_skip2:

        movem.l (sp)+, d2-d7/a0-a3
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
; Note: d0.b (section_x) not used in Phase 1 — target always placed in slot 0.
;       Pass section_x in d0 for Phase 2+ compatibility.
; -----------------------------------------------
Section_WorldToEngine:
        move.w  d1, d0
        addi.w  #SLOT_ORIGIN_L, d0
        rts
