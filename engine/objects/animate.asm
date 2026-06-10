; Animation system — frame index + timer with control codes and events
;
; Animation script format (per-animation duration):
;   AnimTable:  dc.w Anim0-AnimTable, Anim1-AnimTable, ...
;   Anim0:      dc.b duration, frame0, frame1, ..., control_code [, arg]
;               even
;
; Per-frame duration format (used by AnimateSprite_PerFrame):
;   Anim0:      dc.b frame0, dur0, frame1, dur1, ..., control_code
;               even
;
; Control codes (negative bytes, $80+):
;   $FF (AF_END)     — loop: restart from first frame
;   $FE (AF_BACK)    — jump back N: next byte = rewind count
;   $FD (AF_CHANGE)  — switch animation: next byte = new anim ID
;   $FC (AF_ROUTINE) — increment routine counter (SST_custom byte 0) by 2
;   $FB (AF_DELETE)  — delete the object
;
; Animation events (inline, transparent to frame counter):
;   $FA (AF_CALLBACK)  — call routine; format: dc.b $FA, target_hi, target_lo, 0
;                        (objroutine offset stored big-endian as two BYTES — scripts are unaligned)
;   $F9 (AF_SOUND)     — play sound effect; format: dc.b $F9, sound_id
;   $F8 (AF_COLLISION) — set collision type; format: dc.b $F8, collision_type
;   $F7 (AF_SET_FIELD) — set SST byte; format: dc.b $F7, sst_offset, value, 0
;
; Events execute inline when encountered and continue reading the next byte.
; Multiple events can chain before a frame byte.
; All events consume an even number of bytes for PerFrame alignment.

AF_END              = $FF
AF_BACK             = $FE
AF_CHANGE           = $FD
AF_ROUTINE          = $FC
AF_DELETE           = $FB

AF_CALLBACK         = $FA
AF_SOUND            = $F9
AF_COLLISION        = $F8
AF_SET_FIELD        = $F7

; -----------------------------------------------
; AnimateSprite — per-animation duration
; In:  a0 = SST pointer (anim_table must be set)
; Out: mapping_frame updated if frame advanced
; Clobbers: d0-d2, a1-a2
; -----------------------------------------------
AnimateSprite:
        andi.b  #$F9, SST_render_flags(a0)
        move.b  SST_status(a0), d0
        andi.b  #$06, d0
        or.b    d0, SST_render_flags(a0)

        moveq   #0, d0
        move.b  SST_anim(a0), d0
        cmp.b   SST_prev_anim(a0), d0
        bne.s   .anim_changed

        subq.b  #1, SST_anim_timer(a0)
        bpl.s   .done

        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        move.b  (a1), SST_anim_timer(a0)
        addq.b  #1, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0
        bmi.s   .control_code
.set_frame:
        move.b  d0, SST_mapping_frame(a0)
        bsr.w   RefreshSpritePieceCount
.done:
        rts

.anim_changed:
        move.b  d0, SST_prev_anim(a0)
        clr.b   SST_anim_frame(a0)

        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        move.b  (a1), SST_anim_timer(a0)
        moveq   #0, d1
        move.b  1(a1), d0
        bmi.s   .control_code
        bra.s   .set_frame

; --- Control code / event dispatch ---
.control_code:
        neg.b   d0
        andi.w  #$FF, d0
        cmpi.b  #9, d0
        bhi.w   .cc_end
        add.w   d0, d0
        add.w   d0, d0
        jmp     .cc_table-4(pc,d0.w)

.cc_table:
        bra.w   .cc_end                 ; $FF (1) — loop
        bra.w   .cc_back                ; $FE (2) — jump back
        bra.w   .cc_change              ; $FD (3) — switch anim
        bra.w   .cc_routine             ; $FC (4) — advance routine
        bra.w   .cc_delete              ; $FB (5) — delete object
        bra.w   .evt_callback           ; $FA (6) — call callback
        bra.w   .evt_sound              ; $F9 (7) — play sound
        bra.w   .evt_collision          ; $F8 (8) — set collision
        bra.w   .evt_set_field          ; $F7 (9) — set field

.cc_end:
        clr.b   SST_anim_frame(a0)
        moveq   #0, d1
        move.b  1(a1), d0
        bmi.w   .control_code
        bra.w   .set_frame

.cc_back:
        addq.b  #1, d1
        move.b  1(a1,d1.w), d0
        sub.b   d0, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0
        bmi.w   .control_code
        bra.w   .set_frame

.cc_change:
        addq.b  #1, d1
        move.b  1(a1,d1.w), SST_anim(a0)
        bra.w   AnimateSprite

.cc_routine:
        addq.b  #2, SST_sst_custom(a0)
        rts

.cc_delete:
        jmp     DeleteObject

; --- Animation event handlers ---

.evt_callback:
        ; dc.b AF_CALLBACK, target_hi, target_lo, 0  (objroutine offset, byte pair)
        ; a0 = SST pointer passed to called routine
        moveq   #0, d0
        move.b  2(a1,d1.w), d0
        lsl.w   #8, d0
        move.b  3(a1,d1.w), d0
        tst.w   d0                      ; Z from the full word — $xx00 offsets are valid targets
        beq.s   .evt_cb_done            ; offset 0 = no-op safety
        moveq   #OBJ_CODE_BANK, d2
        swap    d2
        move.w  d0, d2
        move.l  a1, -(sp)
        movea.l d2, a2
        jsr     (a2)
        movea.l (sp)+, a1
.evt_cb_done:
        addq.b  #4, SST_anim_frame(a0)
        bra.s   .after_event

.evt_sound:
        ; dc.b AF_SOUND, sound_id
        ; Sound ID at 2(a1,d1.w) — consumed but not played (no driver yet)
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .after_event

.evt_collision:
        ; dc.b AF_COLLISION, collision_type
        move.b  2(a1,d1.w), SST_collision_resp(a0)
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .after_event

.evt_set_field:
        ; dc.b AF_SET_FIELD, sst_offset, value, 0
        moveq   #0, d0
        move.b  2(a1,d1.w), d0
        move.b  3(a1,d1.w), (a0,d0.w)
        addq.b  #4, SST_anim_frame(a0)
        ; fall through to .after_event

.after_event:
        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0
        bmi.w   .control_code
        bra.w   .set_frame

; -----------------------------------------------
; AnimateSprite_PerFrame — per-frame duration (pairs: frame, duration)
; Script format: dc.b frame0, dur0, frame1, dur1, ..., control_code
; In:  a0 = SST pointer (anim_table must be set)
; Out: mapping_frame updated if frame advanced
; Clobbers: d0-d2, a1-a2
; -----------------------------------------------
AnimateSprite_PerFrame:
        andi.b  #$F9, SST_render_flags(a0)
        move.b  SST_status(a0), d0
        andi.b  #$06, d0
        or.b    d0, SST_render_flags(a0)

        moveq   #0, d0
        move.b  SST_anim(a0), d0
        cmp.b   SST_prev_anim(a0), d0
        bne.s   .pf_changed

        subq.b  #1, SST_anim_timer(a0)
        bpl.s   .pf_done

        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        addq.b  #2, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0
        bmi.s   .pf_control

.pf_set_frame:
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1,d1.w), SST_anim_timer(a0)
        bsr.w   RefreshSpritePieceCount
.pf_done:
        rts

.pf_changed:
        move.b  d0, SST_prev_anim(a0)
        clr.b   SST_anim_frame(a0)

        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        moveq   #0, d1
        move.b  (a1), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1), SST_anim_timer(a0)
        bra.w   RefreshSpritePieceCount    ; tail-call

; --- PerFrame control code / event dispatch ---
.pf_control:
        neg.b   d0
        andi.w  #$FF, d0
        cmpi.b  #9, d0
        bhi.w   .pfc_end
        add.w   d0, d0
        add.w   d0, d0
        jmp     .pf_cc_table-4(pc,d0.w)

.pf_cc_table:
        bra.w   .pfc_end                ; $FF — loop
        bra.w   .pfc_back               ; $FE — jump back
        bra.w   .pfc_change             ; $FD — switch anim
        bra.w   .pfc_routine            ; $FC — advance routine
        bra.w   AnimateSprite.cc_delete  ; $FB — delete (shared)
        bra.w   .pf_evt_callback        ; $FA — call callback
        bra.w   .pf_evt_sound           ; $F9 — play sound
        bra.w   .pf_evt_collision       ; $F8 — set collision
        bra.w   .pf_evt_set_field       ; $F7 — set field

.pfc_end:
        clr.b   SST_anim_frame(a0)
        moveq   #0, d1
        move.b  (a1), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1), SST_anim_timer(a0)
        bra.w   RefreshSpritePieceCount    ; tail-call

.pfc_back:
        addq.b  #1, d1
        move.b  (a1,d1.w), d0
        add.b   d0, d0
        sub.b   d0, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1,d1.w), SST_anim_timer(a0)
        bra.w   RefreshSpritePieceCount    ; tail-call

.pfc_change:
        addq.b  #1, d1
        move.b  (a1,d1.w), SST_anim(a0)
        bra.w   AnimateSprite_PerFrame

.pfc_routine:
        addq.b  #2, SST_sst_custom(a0)
        rts

; --- PerFrame animation event handlers ---

.pf_evt_callback:
        ; dc.b AF_CALLBACK, target_hi, target_lo, 0  (objroutine offset, byte pair)
        ; a0 = SST pointer passed to called routine
        moveq   #0, d0
        move.b  1(a1,d1.w), d0
        lsl.w   #8, d0
        move.b  2(a1,d1.w), d0
        tst.w   d0                      ; Z from the full word — $xx00 offsets are valid targets
        beq.s   .pf_evt_cb_done         ; offset 0 = no-op safety
        moveq   #OBJ_CODE_BANK, d2
        swap    d2
        move.w  d0, d2
        move.l  a1, -(sp)
        movea.l d2, a2
        jsr     (a2)
        movea.l (sp)+, a1
.pf_evt_cb_done:
        addq.b  #4, SST_anim_frame(a0)
        bra.s   .pf_after_event

.pf_evt_sound:
        ; dc.b AF_SOUND, sound_id
        ; Sound ID at 1(a1,d1.w) — consumed but not played (no driver yet)
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .pf_after_event

.pf_evt_collision:
        ; dc.b AF_COLLISION, collision_type
        move.b  1(a1,d1.w), SST_collision_resp(a0)
        addq.b  #2, SST_anim_frame(a0)
        bra.s   .pf_after_event

.pf_evt_set_field:
        ; dc.b AF_SET_FIELD, sst_offset, value, 0
        moveq   #0, d0
        move.b  1(a1,d1.w), d0
        move.b  2(a1,d1.w), (a0,d0.w)
        addq.b  #4, SST_anim_frame(a0)
        ; fall through to .pf_after_event

.pf_after_event:
        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0
        bmi.w   .pf_control
        bra.w   .pf_set_frame

; -----------------------------------------------
; RefreshSpritePieceCount — refresh SST_sprite_piece_count from current frame
; Called from AnimateSprite paths whenever mapping_frame is written.
; In:  a0 = SST pointer
; Out: SST_sprite_piece_count(a0) = first word of current frame's data
; Clobbers: d2, a1
; -----------------------------------------------
RefreshSpritePieceCount:
        movea.l SST_mappings(a0), a1
        move.l  a1, d2
        beq.s   .skip                       ; null mappings — leave field untouched
        moveq   #0, d2
        move.b  SST_mapping_frame(a0), d2
        add.w   d2, d2                       ; word offset
        move.w  (a1,d2.w), d2                ; offset to frame data
        move.w  (a1,d2.w), d2                ; first word = piece count
        move.b  d2, SST_sprite_piece_count(a0)
.skip:
        rts
