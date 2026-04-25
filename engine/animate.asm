; Animation system — frame index + timer with control codes
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

AF_END              = $FF
AF_BACK             = $FE
AF_CHANGE           = $FD
AF_ROUTINE          = $FC
AF_DELETE           = $FB

; -----------------------------------------------
; AnimateSprite — per-animation duration
; In:  a0 = SST pointer (anim_table must be set)
; Out: mapping_frame updated if frame advanced
; Clobbers: d0-d2, a1
; -----------------------------------------------
AnimateSprite:
        moveq   #0, d0
        move.b  SST_anim(a0), d0
        cmp.b   SST_prev_anim(a0), d0
        bne.s   .anim_changed

        subq.b  #1, SST_anim_timer(a0)
        bpl.s   .done

        ; Timer expired — resolve script pointer and advance frame
        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1           ; a1 = animation script start

        move.b  (a1), SST_anim_timer(a0) ; reload timer from script byte 0
        addq.b  #1, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0          ; read frame byte (skip duration at byte 0)
        bmi.s   .control_code
        bra.s   .set_frame
.done:
        rts

.anim_changed:
        move.b  d0, SST_prev_anim(a0)
        clr.b   SST_anim_frame(a0)

        ; Resolve animation script
        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1           ; a1 = animation script start

        move.b  (a1), SST_anim_timer(a0) ; load duration from byte 0
        move.b  1(a1), d0               ; first frame byte
        bmi.s   .control_code

.set_frame:
        move.b  d0, SST_mapping_frame(a0)
        rts

; --- Control code dispatch via jump table ---
.control_code:
        neg.b   d0                      ; $FF->$01, $FE->$02, $FD->$03, $FC->$04, $FB->$05
        andi.w  #$FF, d0
        cmpi.b  #5, d0
        bhi.s   .cc_end                 ; unknown code -> treat as loop
        add.w   d0, d0
        add.w   d0, d0                  ; d0 * 4 (bra.w entry size)
        jmp     .cc_table-4(pc,d0.w)    ; -4 because index starts at 1

.cc_table:
        bra.w   .cc_end                 ; $FF (neg=1) — loop
        bra.w   .cc_back                ; $FE (neg=2) — jump back
        bra.w   .cc_change              ; $FD (neg=3) — switch anim
        bra.w   .cc_routine             ; $FC (neg=4) — advance routine
        bra.w   .cc_delete              ; $FB (neg=5) — delete object

.cc_end:
        ; $FF — restart from first frame
        clr.b   SST_anim_frame(a0)
        move.b  1(a1), d0               ; re-read first frame byte
        bmi.s   .control_code            ; handle chained control codes
        bra.s   .set_frame

.cc_back:
        ; $FE — jump back N frames: next byte = count
        addq.b  #1, d1                   ; d1 was anim_frame index
        move.b  1(a1,d1.w), d0           ; read rewind count
        sub.b   d0, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0           ; read frame at new position
        bmi.s   .control_code
        bra.s   .set_frame

.cc_change:
        ; $FD — switch to animation N: next byte = new anim ID
        addq.b  #1, d1
        move.b  1(a1,d1.w), SST_anim(a0) ; set new animation ID
        bra.w   AnimateSprite             ; restart with new anim

.cc_routine:
        ; $FC — increment routine counter (first byte of SST_custom) by 2
        addq.b  #2, SST_sst_custom(a0)
        rts

.cc_delete:
        ; $FB — delete the object
        jmp     DeleteObject

; -----------------------------------------------
; AnimateSprite_PerFrame — per-frame duration (pairs: frame, duration)
; Script format: dc.b frame0, dur0, frame1, dur1, ..., control_code
; In:  a0 = SST pointer (anim_table must be set)
; Out: mapping_frame updated if frame advanced
; Clobbers: d0-d2, a1
; -----------------------------------------------
AnimateSprite_PerFrame:
        moveq   #0, d0
        move.b  SST_anim(a0), d0
        cmp.b   SST_prev_anim(a0), d0
        bne.s   .pf_changed

        subq.b  #1, SST_anim_timer(a0)
        bpl.s   .pf_done

        ; Timer expired — resolve and advance
        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        addq.b  #2, SST_anim_frame(a0)  ; advance by 2 (frame+duration pair)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0           ; read frame byte
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1,d1.w), SST_anim_timer(a0) ; per-frame duration
        bra.s   .pf_set_frame
.pf_done:
        rts

.pf_changed:
        move.b  d0, SST_prev_anim(a0)
        clr.b   SST_anim_frame(a0)

        movea.l SST_anim_table(a0), a1
        add.w   d0, d0
        adda.w  (a1,d0.w), a1

        move.b  (a1), d0                ; first frame byte
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1), SST_anim_timer(a0) ; first frame's duration

.pf_set_frame:
        rts

; --- PerFrame control code dispatch via jump table ---
.pf_control:
        neg.b   d0
        andi.w  #$FF, d0
        cmpi.b  #5, d0
        bhi.s   .pfc_end
        add.w   d0, d0
        add.w   d0, d0
        jmp     .pf_cc_table-4(pc,d0.w)

.pf_cc_table:
        bra.w   .pfc_end                ; $FF — loop
        bra.w   .pfc_back               ; $FE — jump back (double rewind)
        bra.w   .pfc_change             ; $FD — switch anim
        bra.w   .pfc_routine            ; $FC — advance routine
        bra.w   AnimateSprite.cc_delete  ; $FB — delete (shared handler)

.pfc_end:
        clr.b   SST_anim_frame(a0)
        move.b  (a1), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1), SST_anim_timer(a0)
        bra.s   .pf_set_frame

.pfc_back:
        addq.b  #1, d1
        move.b  (a1,d1.w), d0           ; rewind count
        add.b   d0, d0                   ; double for per-frame pairs
        sub.b   d0, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  (a1,d1.w), d0
        bmi.s   .pf_control
        move.b  d0, SST_mapping_frame(a0)
        move.b  1(a1,d1.w), SST_anim_timer(a0)
        bra.s   .pf_set_frame

.pfc_change:
        addq.b  #1, d1
        move.b  (a1,d1.w), SST_anim(a0)
        bra.w   AnimateSprite_PerFrame

.pfc_routine:
        addq.b  #2, SST_sst_custom(a0)
        rts
