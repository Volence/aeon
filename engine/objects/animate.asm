; Animation system — frame index + timer with control codes and events
;
; Animation script format (per-animation duration):
;   AnimTable:  dc.w Anim0-AnimTable, Anim1-AnimTable, ...
;   Anim0:      dc.b duration, frame0, frame1, ..., control_code [, arg]
;               even
;
; Control codes occupy $F7-$FF; FRAME bytes 0-$F6 are valid mapping
; frame indices (Sonic's sheet uses up to $DF — an $80+ frame byte is
; data, not a command; only $F7+ dispatches).
; Control codes:
;   $FF (AF_END)     — loop: restart from first frame
;   $FE (AF_BACK)    — jump back N: next byte = rewind count
;   $FD (AF_CHANGE)  — switch animation: next byte = new anim ID
;   $FC (AF_ROUTINE) — increment routine counter (SST_custom byte 0) by 2
;   $FB (AF_DELETE)  — delete the object
;
; Animation events (inline, transparent to frame counter):
;   $FA (AF_CALLBACK)  — call routine; format: dc.b $FA, target_hi, target_lo, 0
;                        (objroutine offset stored big-endian as two BYTES — scripts are unaligned)
;                        Callback contract: in a0 = SST. May clobber d0-d2, a1-a2.
;                        Must preserve a0, d3-d7, a3-a6. Must not delete the object —
;                        the handler keeps writing SST fields after the call returns.
;   $F9 (AF_SOUND)     — play sound effect; format: dc.b $F9, sound_id
;   $F8 (AF_COLLISION) — set collision type; format: dc.b $F8, collision_type
;   $F7 (AF_SET_FIELD) — set SST byte; format: dc.b $F7, sst_offset, value, 0
;
; Events execute inline when encountered and continue reading the next byte.
; Multiple events can chain before a frame byte.
; All events consume an even number of bytes (a format invariant scripts
; may rely on; also keeps `even`-terminated scripts stable).

; AF_* control-code values live in engine/constants.asm (next to DUR_DYNAMIC):
; script DATA files read them in the mixed build, where SIGIL_EMP_ANIMATE
; gates this file out of the AS side.

; LOCKSTEP: engine/objects/animate.emp's reload_anim_timer comptime fn is this
; macro's .emp twin (sigil kill-list row 5 class — dies with this file at
; Spec 5). The `tag` param has no .emp counterpart: template labels are
; hygienic, so each expansion gets its own .rt_static.
; Reload SST_anim_timer from the script duration byte at (srcReg), substituting
; the caller's d3 when the byte is the DUR_DYNAMIC sentinel. srcReg points at
; the script's byte 0. Clobbers d2.
reloadAnimTimer macro srcReg, tag
        move.b  (srcReg), d2
        cmpi.b  #DUR_DYNAMIC, d2
        bne.s   .rt_static_tag
        move.b  d3, d2                  ; dynamic: substitute caller's d3 hold
.rt_static_tag:
        move.b  d2, SST_anim_timer(a0)
        endm

; -----------------------------------------------
; AnimateSprite — per-animation duration
; In:  a0 = SST pointer (anim_table must be set)
;      d3.b = dynamic per-anim hold, used ONLY when a script's duration byte
;             == DUR_DYNAMIC (speed-scaled anims). Callers without DUR_DYNAMIC
;             scripts need not set d3.
; Out: mapping_frame updated if frame advanced
; Clobbers: d0-d2, a1-a2
; -----------------------------------------------
AnimateSprite:
        ; Propagate facing from status -> render_flags each frame. The flip bits
        ; are bit-aligned (ST_XFLIP/ST_YFLIP == RF_XFLIP/RF_YFLIP), so this is a
        ; straight copy of bits 1-2. $F9 = ~(RF_XFLIP|RF_YFLIP): clear the two
        ; flip bits, preserve the rest (on-screen, multisprite, priority, coord).
        andi.b  #$F9, SST_render_flags(a0)
        move.b  SST_status(a0), d0
        andi.b  #$06, d0                ; $06 = RF_XFLIP|RF_YFLIP: isolate flip bits
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

        reloadAnimTimer a1,adv
        addq.b  #1, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0
        cmpi.b  #AF_SET_FIELD, d0       ; $F7+ = control/event; frames 0-$F6 are valid
        bhs.s   .control_code
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

        reloadAnimTimer a1,chg
        moveq   #0, d1
        move.b  1(a1), d0
        cmpi.b  #AF_SET_FIELD, d0       ; $F7+ = control/event; frames 0-$F6 are valid
        bhs.s   .control_code
        bra.s   .set_frame

; --- Control code / event dispatch ---
.control_code:
        neg.b   d0
        andi.w  #$FF, d0
        cmpi.b  #9, d0
        bhi.s   .cc_end   ; was .w — asl width-selected .s at the t9 step-2 sweep
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
        cmpi.b  #AF_SET_FIELD, d0       ; $F7+ = control/event; frames 0-$F6 are valid
        bhs.s   .control_code           ; was .w — asl width-selected .s at the t9 step-2 sweep
        bra.w   .set_frame

.cc_back:
        addq.b  #1, d1
        move.b  1(a1,d1.w), d0
        sub.b   d0, SST_anim_frame(a0)

        moveq   #0, d1
        move.b  SST_anim_frame(a0), d1
        move.b  1(a1,d1.w), d0
        cmpi.b  #AF_SET_FIELD, d0       ; $F7+ = control/event; frames 0-$F6 are valid
        bhs.s   .control_code           ; was .w — asl width-selected .s at the t9 step-2 sweep
        bra.w   .set_frame

.cc_change:
        addq.b  #1, d1
        move.b  1(a1,d1.w), SST_anim(a0)
        bra.w   AnimateSprite

.cc_routine:
        addq.b  #2, SST_sst_custom(a0)
        rts

.cc_delete:
        bra.w   DeleteObject            ; LOCKSTEP animate.emp step 2: static tail-call spelled as a branch (jmp reserved for computed targets); same length as the old jmp (xxx).w

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
        ; dc.b AF_SOUND, sound_id -> play the SFX
        move.b  2(a1,d1.w), d0
      ifdef SOUND_DRIVER_ENABLED
        movem.l a1/d1, -(sp)
        bsr.w   Sound_PlaySFX
        movem.l (sp)+, a1/d1
      endif
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
        cmpi.b  #AF_SET_FIELD, d0       ; $F7+ = control/event; frames 0-$F6 are valid
        bhs.w   .control_code
        bra.w   .set_frame

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
        ; piece count is at FRAME_PIECE_COUNT (+4), after 4 bbox bytes
        move.w  FRAME_PIECE_COUNT(a1,d2.w), d2
        move.b  d2, SST_sprite_piece_count(a0)
.skip:
        rts
