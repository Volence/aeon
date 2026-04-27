; engine/level/parallax.asm — §4.6 parallax pipeline
;
; Public:
;   Parallax_Init(a0=parallax_config*) — initialize Parallax_State at level load
;   Parallax_Update                    — main-loop per-frame builder
;   Parallax_StartTransition(a0=new)   — section boundary handler (T8+)
;   Vscroll_Write                      — VBlank VSRAM emitter (T6+)

; ----------------------------------------------------------------------
; Parallax_Init — wipe Parallax_State and seed current_config
; In:  a0 = parallax_config* (NULL = inert; pipeline will skip)
; Out: none
; Clobbers: d0, d1, a1
; ----------------------------------------------------------------------
Parallax_Init:
        lea     (Parallax_State).w, a1
        moveq   #(Parallax_State_End-Parallax_State)/4-1, d0
        moveq   #0, d1
.zero:
        move.l  d1, (a1)+
        dbf     d0, .zero

        move.l  a0, (Parallax_Current_Config).w
        ; Target_Config and Transition_Frames stay 0 (no transition active).
        rts

; ----------------------------------------------------------------------
; Parallax_Update — per-frame parallax buffer build (T5: per-cell only)
;
; Reads:  Camera_X, Parallax_Current_Config, Parallax_Current_Scroll_A/B
; Writes: Parallax_Current_Scroll_A/B (lerp toward target),
;         Hscroll_Buffer (28 longwords for per-cell mode),
;         Hscroll_Dirty_Start/End
;
; Per-frame cost target: ~410 NTSC cycles for 5-band per-cell pure shift-add.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a4
; ----------------------------------------------------------------------
Parallax_Update:
        movea.l (Parallax_Current_Config).w, a0
        cmpa.w  #0, a0
        beq.w   .no_config

        moveq   #0, d7
        move.b  parallax_config_pcfg_band_count(a0), d7
        beq.w   .no_config

        ; -- camera X (signed pixel high word) --
        move.l  (Camera_X).w, d0
        swap    d0                                  ; d0.w = camX

        ; -- compute target band scrolls and lerp current_scroll_a/b --
        lea     parallax_config_len(a0), a1         ; a1 = first band_entry
        lea     (Parallax_Current_Scroll_A).w, a2
        lea     (Parallax_Current_Scroll_B).w, a3

        moveq   #0, d6
        move.b  parallax_config_pcfg_layer_mask(a0), d6             ; d6 = layer mask
        moveq   #0, d5                              ; d5 = band index
        moveq   #0, d3                              ; d3 = previous-band current_a (for inheritance)
        moveq   #0, d4                              ; d4 = previous-band current_b

.band_loop:
        btst    d5, d6
        beq.s   .band_disabled

        ; -- factor_a: target into d2, lerp into current --
        bsr.w   Decode_Factor_A                     ; out: d2 = -decode(camX, factor_a)
        move.w  (a2), d1                            ; current_a
        sub.w   d1, d2                              ; delta = target - current
        asr.w   #PARALLAX_LERP_SHIFT, d2
        add.w   d2, d1                              ; current_a += delta >> 3
        move.w  d1, (a2)
        move.w  d1, d3                              ; remember for inheritance

        ; -- factor_b --
        bsr.w   Decode_Factor_B                     ; out: d2 = -decode(camX, factor_b)
        move.w  (a3), d1
        sub.w   d1, d2
        asr.w   #PARALLAX_LERP_SHIFT, d2
        add.w   d2, d1
        move.w  d1, (a3)
        move.w  d1, d4
        bra.s   .band_done

.band_disabled:
        ; inherit previous-band scroll
        move.w  d3, (a2)
        move.w  d4, (a3)

.band_done:
        adda.l  #band_entry_len, a1
        addq.l  #2, a2
        addq.l  #2, a3
        addq.w  #1, d5
        cmp.w   d7, d5
        blo.s   .band_loop

        ; --- fill HScroll buffer (per-cell mode) ---
        bsr.w   Parallax_Fill_PerCell

        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #27, (Hscroll_Dirty_End).w

.no_config:
        rts

; ----------------------------------------------------------------------
; Decode_Factor_A — return negated Plane A scroll for current band
; In:  d0.w = camX (signed pixels), a1 = band_entry*
; Out: d2.w = negated factor result. Returns 0 if s1 == 15 (locked).
; Preserves: d0, d3-d7, a0-a4. Clobbers: d1, d2.
; (Pushes d3 internally to use as the second-term scratch register.)
; ----------------------------------------------------------------------
Decode_Factor_A:
        moveq   #0, d1
        move.b  band_entry_band_factor_a_s1(a1), d1
        cmpi.b  #15, d1
        beq.s   .locked
        move.w  d0, d2
        asr.w   d1, d2                              ; first term = camX >> s1
        moveq   #0, d1
        move.b  band_entry_band_factor_a_s2(a1), d1
        cmpi.b  #15, d1
        beq.s   .negate
        ; second term: combine with d2 via op (need scratch — borrow d3 via stack)
        move.l  d3, -(sp)
        move.w  d0, d3
        asr.w   d1, d3                              ; second term = camX >> s2
        tst.b   band_entry_band_factor_a_op(a1)
        bne.s   .a_sub
        add.w   d3, d2
        bra.s   .a_pop_d3
.a_sub:
        sub.w   d3, d2
.a_pop_d3:
        move.l  (sp)+, d3
.negate:
        neg.w   d2
        rts
.locked:
        moveq   #0, d2
        rts

; ----------------------------------------------------------------------
; Decode_Factor_B — same shape as Decode_Factor_A, reads factor_b fields
; ----------------------------------------------------------------------
Decode_Factor_B:
        moveq   #0, d1
        move.b  band_entry_band_factor_b_s1(a1), d1
        cmpi.b  #15, d1
        beq.s   .locked
        move.w  d0, d2
        asr.w   d1, d2
        moveq   #0, d1
        move.b  band_entry_band_factor_b_s2(a1), d1
        cmpi.b  #15, d1
        beq.s   .negate
        move.l  d3, -(sp)
        move.w  d0, d3
        asr.w   d1, d3
        tst.b   band_entry_band_factor_b_op(a1)
        bne.s   .b_sub
        add.w   d3, d2
        bra.s   .b_pop_d3
.b_sub:
        sub.w   d3, d2
.b_pop_d3:
        move.l  (sp)+, d3
.negate:
        neg.w   d2
        rts
.locked:
        moveq   #0, d2
        rts

; ----------------------------------------------------------------------
; Parallax_Fill_PerCell — emit 28 longwords from current_scroll arrays
; In:  a0 = parallax_config*, d7 = band count
; Out: Hscroll_Buffer filled (28 longwords)
; Clobbers: d0-d4, a1-a4
; ----------------------------------------------------------------------
Parallax_Fill_PerCell:
        lea     (Hscroll_Buffer).w, a4
        lea     parallax_config_len(a0), a1         ; a1 = band[0]
        lea     (Parallax_Current_Scroll_A).w, a2
        lea     (Parallax_Current_Scroll_B).w, a3
        moveq   #0, d3                              ; d3 = current cell index
        moveq   #0, d2                              ; d2 = band index

.next_band:
        ; -- determine end_cell for this band --
        addq.w  #1, d2
        cmp.w   d7, d2
        bhi.s   .last_band_end
        ; not last: peek next band's top_cell
        moveq   #0, d4
        move.b  band_entry_band_top_cell+band_entry_len(a1), d4
        bra.s   .have_end
.last_band_end:
        moveq   #28, d4

.have_end:
        ; -- pack scroll word: (current_a << 16) | (current_b & $FFFF) --
        move.w  (a2), d0                            ; current_a (already negated)
        move.w  (a3), d1                            ; current_b
        swap    d0
        move.w  d1, d0                              ; d0 = packed longword

        ; -- fill cells [d3 .. d4) --
.fill:
        cmp.w   d4, d3
        bge.s   .band_done
        move.l  d0, (a4)+
        addq.w  #1, d3
        bra.s   .fill

.band_done:
        adda.l  #band_entry_len, a1
        addq.l  #2, a2
        addq.l  #2, a3
        cmp.w   d7, d2
        blo.s   .next_band
        rts
