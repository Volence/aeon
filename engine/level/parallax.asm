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

        ; Snap: drive the lerp to convergence so the first visible frame
        ; shows the correct band scrolls instead of the "race" from 0.
        ; PARALLAX_LERP_SHIFT=3 → ~32 iterations to zero-error.
        ; Use d7 as counter (Parallax_Update preserves nothing, so save+restore).
        move.l  d7, -(sp)
        moveq   #32-1, d7
.snap_loop:
        move.l  d7, -(sp)
        bsr.w   Parallax_Update
        move.l  (sp)+, d7
        dbf     d7, .snap_loop
        move.l  (sp)+, d7
        rts

; ----------------------------------------------------------------------
; Parallax_StartTransition — handle parallax_config change at section boundary
; T8: instant snap regardless of pcfg_transition. Smooth lerp lands in T14.
;
; In:  a0 = new parallax_config* (NULL = inherit, no-op)
; Out: Parallax_Current_Config swapped; transition state cleared;
;      VDP shadow reg $0B (Mode Set 3) updated for new H-/V-scroll modes.
; Clobbers: d0, d1
; ----------------------------------------------------------------------
Parallax_StartTransition:
        cmpa.w  #0, a0
        beq.w   .no_change                          ; null → inherit, no-op
        cmpa.l  (Parallax_Current_Config).w, a0
        beq.w   .no_change                          ; same config → no-op

        move.l  a0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        move.b  #0, (Parallax_Transition_Frames).w

        ; --- VDP reg $0B Mode Set 3 update ---
        ;   bits 1:0 = HScroll mode: %10 per-cell, %11 per-line
        ;   bit 2    = VScroll mode: 0 whole-plane, 1 per-column
        moveq   #%10, d0                            ; default per-cell HScroll
        move.l  parallax_config_pcfg_deform_table_fg(a0), d1
        or.l    parallax_config_pcfg_deform_table_bg(a0), d1
        beq.s   .h_done
        moveq   #%11, d0                            ; per-line if any H-deform
.h_done:
        move.l  parallax_config_pcfg_v_deform_table_bg(a0), d1
        beq.s   .v_done
        ori.b   #%100, d0                           ; bit 2 = per-column V
.v_done:
        setVDPReg VDP_Shadow_vdp_mode3, d0

.no_change:
        rts

; ----------------------------------------------------------------------
; Vscroll_Write — emit Vscroll_Factor (whole-plane) or column buf (per-column)
; T6 stub: always whole-plane. T12 adds per-column branch.
;
; Caller (VBlank handler) must hold stopZ80 — VDP writes happen here.
;
; In:  none (reads Parallax_Current_Config, Vscroll_Factor)
; Out: VSRAM written
; Clobbers: a5
; ----------------------------------------------------------------------
Vscroll_Write:
        lea     (VDP_CTRL).l, a5
        move.l  #vdpComm(0, VSRAM, WRITE), (a5)

        ; per-column or whole-plane? Validate config ptr first.
        move.l  (Parallax_Current_Config).w, d0
        beq.s   .whole_plane
        cmpi.l  #$00400000, d0
        bhs.s   .whole_plane                        ; outside ROM = garbage
        movea.l d0, a0
        move.l  parallax_config_pcfg_v_deform_table_bg(a0), d0
        beq.s   .whole_plane

        ; per-column: emit 20 longwords from column buffer to VSRAM
        lea     (Parallax_Vscroll_Column_Buf).w, a0
        rept 20
        move.l  (a0)+, VDP_DATA-VDP_CTRL(a5)
        endr
        rts

.whole_plane:
        move.l  (Vscroll_Factor).w, VDP_DATA-VDP_CTRL(a5)
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
        ; Validate Parallax_Current_Config: 0 = inert; otherwise must be in
        ; ROM range (< $400000 = 4MB). Defensive against the deferred-work
        ; intermittent clobber that produces garbage like $FF71FF71.
        move.l  (Parallax_Current_Config).w, d0
        beq.w   .no_config
        cmpi.l  #$00400000, d0
        bhs.w   .no_config                          ; outside ROM = garbage
        movea.l d0, a0

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

        ; --- Step 4: fill HScroll buffer (mode auto-selected from config) ---
        ;   mode_per_line if either H-deform table is non-NULL.
        move.l  parallax_config_pcfg_deform_table_fg(a0), d0
        or.l    parallax_config_pcfg_deform_table_bg(a0), d0
        beq.s   .fill_per_cell
        bsr.w   Parallax_Fill_PerLine
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #(28*8)-1, (Hscroll_Dirty_End).w
        bra.s   .fill_done
.fill_per_cell:
        bsr.w   Parallax_Fill_PerCell
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #27, (Hscroll_Dirty_End).w
.fill_done:

        ; --- Step 5: compute whole-plane Vscroll (always — used by per-column too) ---
        ; FG: vscroll_a = camY (Plane A follows camera 1:1)
        ; BG: target_b  = ((camY - v_center_y) >> v_factor_bg) + v_offset
        ;     current_vscroll_bg += (target_b - current_vscroll_bg) >> PARALLAX_LERP_SHIFT
        ;
        ; Lock sentinel: v_factor_bg = 15 → skip lerp, pin BG = 0. Used by
        ; configs that want the BG plane vertically locked regardless of
        ; Camera_Y. Workaround for §4.6 deferred Camera_Y intermittent
        ; clobber; remove once that's root-caused.
        move.l  (Camera_Y).w, d0
        swap    d0                                  ; d0.w = camY (signed pixels)
        move.w  d0, d1                              ; d1.w = camY  (FG vscroll)
        moveq   #0, d2
        move.b  parallax_config_pcfg_v_factor_bg(a0), d2
        cmpi.b  #15, d2
        beq.s   .v_locked
        sub.w   parallax_config_pcfg_v_center_y(a0), d0
        asr.w   d2, d0
        add.w   parallax_config_pcfg_v_offset(a0), d0     ; d0 = target_b

        move.w  (Parallax_Current_Vscroll_BG).w, d2
        sub.w   d2, d0
        asr.w   #PARALLAX_LERP_SHIFT, d0
        add.w   d0, d2                              ; d2 = new current_vscroll_bg
        bra.s   .v_pack
.v_locked:
        ; locked: BG = vOffset (static, ignores camera + lerp)
        ; Also pins FG to 0 — for OJZ Phase 1 (X-only-scroll) the FG plane
        ; is filled at plane row 0 (no camera-Y compensation in
        ; Section_FillInitial), so any non-zero VSRAM Y exposes the
        ; unfilled rows 48-63. Override d1 here.
        move.w  parallax_config_pcfg_v_offset(a0), d2
        moveq   #0, d1                              ; FG = 0 (overrides camY)
.v_pack:
        move.w  d2, (Parallax_Current_Vscroll_BG).w

        ; pack into Vscroll_Factor (used by Vscroll_Write whole-plane branch)
        swap    d1                                  ; FG in high half
        move.w  d2, d1                              ; BG in low half (d2 = current_vscroll_bg)
        move.l  d1, (Vscroll_Factor).w

        ; --- Step 5b (T12): per-column V-scroll buffer fill ---
        ; If v_deform_table_bg != NULL, sample table per column and write
        ; column buffer. Vscroll_Write picks this up via the same flag.
        ; Whole-plane Vscroll_Factor is also kept correct (above) so the
        ; whole-plane fallback path stays valid if per-column gets disabled.
        move.l  parallax_config_pcfg_v_deform_table_bg(a0), d0
        beq.s   .v_done

        ; advance v_deform_phase_bg by speed
        moveq   #0, d3
        move.b  parallax_config_pcfg_v_deform_speed_bg(a0), d3
        add.w   d3, (Parallax_V_Deform_Phase_BG).w
        and.w   #$FF, (Parallax_V_Deform_Phase_BG).w

        ; fill 20 column-pairs (80 bytes total)
        ; d1 = camY (FG, swap'd into high half — restore low word)
        swap    d1                                  ; restore d1.w = camY (FG)
        ; d2 = current_vscroll_bg (BG base)
        movea.l d0, a1                              ; a1 = v_deform_table_bg
        lea     (Parallax_Vscroll_Column_Buf).w, a2
        moveq   #0, d3
        move.b  parallax_config_pcfg_v_deform_shift_bg(a0), d3   ; amplitude shift
        moveq   #0, d4
        move.b  (Parallax_V_Deform_Phase_BG+1).w, d4   ; phase low byte
        moveq   #20-1, d6                           ; 20 column-pairs
.col:
        move.b  (a1, d4.w), d5                      ; sample (signed byte)
        ext.w   d5
        asr.w   d3, d5                              ; offset = sample >> v_deform_shift_bg
        move.w  d1, (a2)+                           ; FG word = camY (constant per column)
        move.w  d2, d0
        add.w   d5, d0
        move.w  d0, (a2)+                           ; BG word = base + offset
        addq.b  #1, d4
        dbf     d6, .col

.v_done:

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
; Parallax_Fill_PerLine — emit 224 longwords with FG/BG deform sampling
; In:  a0 = parallax_config*, d7 = band count
; Out: Hscroll_Buffer filled (224 longwords); a0/d7 preserved
; Clobbers: d0-d6, a1-a6
;
; Per band:
;   1. Cache (current_a << 16) | current_b in a stack-saved word pair
;   2. For each line in [band.top_cell*8, end_line):
;        - reload base scroll (FG_a, BG_b)
;        - if FG deform active: sample table, shift, add to FG word
;        - if BG deform active: sample table, shift, add to BG word
;        - pack + emit longword
;   3. Advance to next band
;
; Deform-table indices wrap at 256 via byte arithmetic on the index register.
; ----------------------------------------------------------------------
Parallax_Fill_PerLine:
        movem.l a0/d7, -(sp)                        ; preserve caller's config ptr + band count

        lea     (Hscroll_Buffer).w, a4              ; output ptr
        lea     parallax_config_len(a0), a1         ; band[0]
        lea     (Parallax_Current_Scroll_A).w, a2
        lea     (Parallax_Current_Scroll_B).w, a3
        movea.l parallax_config_pcfg_deform_table_fg(a0), a5  ; NULL = no FG sampling
        movea.l parallax_config_pcfg_deform_table_bg(a0), a6  ; NULL = no BG sampling

        moveq   #0, d4                              ; current line index (0..223)
        moveq   #0, d3                              ; band index (0..count-1)

.next_band:
        ; --- compute end_line for this band ---
        addq.w  #1, d3                              ; d3 = band_index + 1
        cmp.w   d7, d3
        bhi.s   .last_band
        moveq   #0, d5
        move.b  band_entry_band_top_cell+band_entry_len(a1), d5
        lsl.w   #3, d5                              ; end_line = next.top_cell × 8
        bra.s   .have_end
.last_band:
        move.w  #224, d5                            ; last band ends at line 224
.have_end:

        ; --- per-band setup: phase index = (Phase_xx + band_phase + line) & $FF ---
        ; Precompute (Phase_xx + band_phase) into d_idx_fg / d_idx_bg.
        ; Then add line each iteration.
        moveq   #0, d6                              ; d6.w = FG phase index base
        cmpa.w  #0, a5
        beq.s   .skip_fg_idx
        move.w  (Parallax_Deform_Phase_FG).w, d6
        add.b   band_entry_band_phase_offset(a1), d6
.skip_fg_idx:

        ; .line loop
.line:
        ; --- start with band's base scroll (in d0 = packed FG_high|BG_low) ---
        move.w  (a2), d0                            ; FG (already negated)
        swap    d0
        move.w  (a3), d0                            ; BG

        ; --- FG deform sampling ---
        cmpa.w  #0, a5
        beq.s   .skip_fg_sample
        moveq   #15, d2
        cmp.b   band_entry_band_deform_shift_a(a1), d2
        beq.s   .skip_fg_sample
        ; index = (d6 + line) & $FF
        move.w  d6, d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a5, d1.w), d2                      ; sample (signed byte)
        ext.w   d2
        moveq   #0, d1
        move.b  band_entry_band_deform_shift_a(a1), d1
        asr.w   d1, d2                              ; offset = sample >> deform_shift_a
        ; Add offset to FG word (high half of d0)
        swap    d0
        add.w   d2, d0
        swap    d0
.skip_fg_sample:

        ; --- BG deform sampling ---
        cmpa.w  #0, a6
        beq.s   .skip_bg_sample
        moveq   #15, d2
        cmp.b   band_entry_band_deform_shift_b(a1), d2
        beq.s   .skip_bg_sample
        ; index = (Phase_BG + band_phase + line) & $FF
        ; Recompute base each line (BG path doesn't cache, simpler)
        move.w  (Parallax_Deform_Phase_BG).w, d1
        add.b   band_entry_band_phase_offset(a1), d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a6, d1.w), d2
        ext.w   d2
        moveq   #0, d1
        move.b  band_entry_band_deform_shift_b(a1), d1
        asr.w   d1, d2                              ; offset
        add.w   d2, d0                              ; add to BG word (low half)
.skip_bg_sample:

        ; --- emit packed longword ---
        move.l  d0, (a4)+
        addq.w  #1, d4
        cmp.w   d5, d4
        blo.w   .line

        ; advance to next band
        adda.l  #band_entry_len, a1
        addq.l  #2, a2
        addq.l  #2, a3
        cmp.w   d7, d3
        blo.w   .next_band

        movem.l (sp)+, a0/d7
        rts

; ----------------------------------------------------------------------
; Parallax_Fill_PerCell — emit 28 longwords from current_scroll arrays

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
