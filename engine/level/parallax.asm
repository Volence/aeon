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

        ; Seed the previous-section trackers to a sentinel (the .zero loop
        ; above just cleared them to 0,0, a valid grid coord). $FF,$FF can
        ; never match a real section, so the first Parallax_CheckBoundary
        ; re-selects the start section's config — a no-op against the config
        ; this Init already chose, but it primes Prev_Sec_X/Y correctly.
        move.b  #$FF, (Parallax_Prev_Sec_X).w
        move.b  #$FF, (Parallax_Prev_Sec_Y).w

        ; Snap all band scrolls to their correct positions on the first
        ; frame instead of lerping from 0. One Update with Snap_Pending
        ; writes target_scroll directly to current_scroll for every band.
        st      (Parallax_Snap_Pending).w
        bsr.w   Parallax_Update
        rts

; ----------------------------------------------------------------------
; Parallax_CheckBoundary — per-section parallax: re-select config on a
; section-boundary crossing.
;
; Continuous-scroll replacement for the deleted teleport-driven snap. The
; camera scrolls live in world space, so there is no teleport to hang the
; config switch on; instead we watch the section under the camera CENTRE
; (matching the active-section semantic used for the diagnostic tint) and
; act the frame it changes. On a crossing we look up the new section's
; Sec_sec_parallax_config (Act_act_parallax_config when NULL) and hand it
; to Parallax_StartTransition, which decides snap vs. lerp from the new
; config's pcfg_transition flag and no-ops when the config is unchanged.
;
; Edge-triggered: the per-frame cost off a boundary is two shifts and a
; byte compare. Out-of-grid sections (Section_GetSecPtrXY Z set) are left
; alone — the camera is clamped in-grid, but the guard keeps this robust.
;
; In:  none (reads Camera_X/Y, Current_Act_Ptr, Parallax_Prev_Sec_X/Y)
; Out: config switched + transition staged iff a crossing changed it.
; Clobbers: d0-d3, a0, a2
; ----------------------------------------------------------------------
Parallax_CheckBoundary:
        ; -- section under the camera centre (camX+160 / camY+112) --
        move.w  (Camera_X).w, d2                    ; world X px (high word)
        addi.w  #SCREEN_WIDTH/2, d2
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d2                              ; d2 = cur_sec_x
        move.w  (Camera_Y).w, d3                    ; world Y px
        addi.w  #SCREEN_HEIGHT/2, d3
        asr.w   d0, d3                              ; d3 = cur_sec_y

        ; -- crossing? compare against last frame's section --
        cmp.b   (Parallax_Prev_Sec_X).w, d2
        bne.s   .crossed
        cmp.b   (Parallax_Prev_Sec_Y).w, d3
        beq.s   .no_crossing
.crossed:
        ; -- look up the new section (a2 = act ptr) --
        movea.l (Current_Act_Ptr).w, a2
        jsr     Section_GetSecPtrXY                 ; a0 = Sec ptr (Z set = out of grid)
        beq.s   .no_crossing                        ; out of grid — keep current config

        ; commit the new section coords only once we have a valid section
        move.b  d2, (Parallax_Prev_Sec_X).w
        move.b  d3, (Parallax_Prev_Sec_Y).w

        ; -- resolve config: section's own, else act default --
        movea.l Sec_sec_parallax_config(a0), a0
        cmpa.w  #0, a0
        bne.s   .have_config
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
.have_config:
        bra.w   Parallax_StartTransition            ; snap/lerp + mode shadow; no-op if unchanged
.no_crossing:
        rts

; ----------------------------------------------------------------------
; Parallax_StartTransition — handle parallax_config change at section boundary
;
; Transition mode is picked from the NEW config's pcfg_transition byte:
;   0 (default) = smooth: stage as Target_Config, set frame counter to
;                 PARALLAX_TRANS_DEFAULT, leave Current_Config alone.
;                 Parallax_Update uses Target_Config to compute band
;                 targets while the per-band scroll lerp (>>PARALLAX_LERP_SHIFT)
;                 naturally eases current toward those values. When the
;                 counter hits 0, Current = Target (handled in Update).
;   1           = instant: swap Current_Config immediately.
;
; In either branch the VDP $0B (Mode Set 3) shadow updates to the NEW
; config's mode bits — the buffer is built from the new config from this
; frame onward, so the register must match for correct rendering.
;
; In:  a0 = new parallax_config* (NULL = inherit, no-op)
; Out: transition state set up; mode_set_3 shadow updated.
; Clobbers: d0, d1
; ----------------------------------------------------------------------
Parallax_StartTransition:
        cmpa.w  #0, a0
        beq.w   .no_change                          ; null → inherit, no-op
        cmpa.l  (Parallax_Current_Config).w, a0
        beq.w   .no_change                          ; matches current → no-op
        cmpa.l  (Parallax_Target_Config).w, a0
        beq.w   .no_change                          ; already transitioning to this → no-op

        ; -- pick transition mode from the new config's pcfg_transition flag --
        tst.b   parallax_config_pcfg_transition(a0)
        bne.s   .instant

        ; -- smooth: stage target, leave current_config intact --
        move.l  a0, (Parallax_Target_Config).w
        move.b  #PARALLAX_TRANS_DEFAULT, (Parallax_Transition_Frames).w
        bra.s   .update_mode

.instant:
        ; -- instant: swap current immediately, clear target, AND snap
        ;    band scroll values to the new config's targets (otherwise they
        ;    would still lerp toward the new targets over PARALLAX_LERP_SHIFT
        ;    frames, defeating the "instant" semantic). --
        move.l  a0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        move.b  #0, (Parallax_Transition_Frames).w
        move.b  #1, (Parallax_Snap_Pending).w

.update_mode:
        ; --- VDP reg $0B Mode Set 3 update from the NEW config ---
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
;
; HARDWARE QUIRK (per-column branch): the VDP's per-column V-scroll grain
; is 16 px (one VSRAM entry per column-pair). When Plane B has non-zero
; HScroll AND per-column V-scroll is on, the leftmost partial column
; (the screen sliver before HScroll's first 16-px boundary) renders at
; V-scroll = 0 regardless of VSRAM[0]. There is no register to fix this —
; it's silicon. Mitigations: (a) sprite mask the leftmost 16 px (planned
; future task), (b) lock Plane B HScroll to 0 (factor_b = FACTOR_0), or
; (c) live with it. See DEFERRED_WORK.md "VDP register $0B …" entry and
; the §4.6 spec note about leftmost-column garble.
; ----------------------------------------------------------------------
Vscroll_Write:
        lea     (VDP_CTRL).l, a5
        move.l  #vdpComm(0, VSRAM, WRITE), (a5)

        ; per-column or whole-plane?
        move.l  (Parallax_Current_Config).w, d0
        beq.s   .whole_plane
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
        ; --- Step 1: select active config for this frame ---
        ; During a smooth transition (Parallax_Transition_Frames > 0) drive
        ; band targets from Target_Config; the per-band scroll lerp eases
        ; current_scroll values toward those across PARALLAX_TRANS_DEFAULT
        ; frames. When the counter hits 0, promote target → current and
        ; clear target. Outside transitions, use Current_Config as before.
        tst.b   (Parallax_Transition_Frames).w
        beq.s   .use_current
        subq.b  #1, (Parallax_Transition_Frames).w
        bne.s   .use_target
        ; counter just hit 0 → promote target into current, clear target
        move.l  (Parallax_Target_Config).w, d0
        move.l  d0, (Parallax_Current_Config).w
        move.l  #0, (Parallax_Target_Config).w
        bra.s   .config_resolved
.use_target:
        move.l  (Parallax_Target_Config).w, d0
        bra.s   .config_resolved
.use_current:
        move.l  (Parallax_Current_Config).w, d0
.config_resolved:
        ; 0 = inert (no parallax config active)
        beq.w   .no_config
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
        move.w  d0, d3                              ; d3 = previous-band current_a seed = -camX:
        neg.w   d3                                  ;   a disabled band 0 must still hard-lock the
                                                    ;   FG to the camera (streaming window — see
                                                    ;   plane-wrap comment below); only the BG may
                                                    ;   inherit the locked/previous value
        moveq   #0, d4                              ; d4 = previous-band current_b

        ; Plane A (factor_a) is HARD-LOCKED to its factor-derived target —
        ; never lerped. The FG streaming engine draws columns in a
        ; camera-anchored 64-col window, so any FG scroll offset from the
        ; camera drags the plane-wrap seam into view at the screen edge
        ; (an always-on lerp trailed the camera by ~15 × velocity; even a
        ; 16-frame transition lerp drifts ~240 px at 16 px/frame and then
        ; visibly snaps). Transition smoothing is a plane B effect.
        ;
        ; Plane B (factor_b) lerps ONLY during an active section
        ; transition (Transition_Frames > 0) — easing between the two
        ; configs' BG factors. Outside transitions it locks to target.
        ; Parallax_Snap_Pending forces the snap path when the camera jumps
        ; (no smooth lerp can catch up).

.band_loop:
        btst    d5, d6
        beq.s   .band_disabled

        ; -- factor_a: hard-locked, current_a = target every frame --
        bsr.w   Decode_Factor_A                     ; out: d2 = -decode(camX, factor_a)
        move.w  d2, (a2)
        move.w  d2, d3                              ; remember for inheritance

        ; -- factor_b: lerp during transition, else lock --
        bsr.w   Decode_Factor_B                     ; out: d2 = -decode(camX, factor_b)
        tst.b   (Parallax_Snap_Pending).w
        bne.s   .snap_b
        tst.b   (Parallax_Transition_Frames).w
        beq.s   .snap_b                             ; no transition — lock to target
        move.w  (a3), d1
        sub.w   d1, d2
        asr.w   #PARALLAX_LERP_SHIFT, d2
        add.w   d2, d1
        bra.s   .write_b
.snap_b:
        move.w  d2, d1                              ; snap: current_b = target
.write_b:
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

        ; clear Snap_Pending flag — one-shot, consumed by this Update
        clr.b   (Parallax_Snap_Pending).w

        ; NOTE: Step 5 (Vscroll) runs BEFORE Step 4 (HScroll fill) — the
        ; band rotation in Step 4a needs this frame's Vscroll_BG.
        bra.w   Parallax_Step5_Vscroll
.no_config:
        rts

Parallax_Step4_Fill:

        ; --- Step 4a: rotate plane-space band tops into screen space ---
        ; Band tops are authored in Plane B cell rows (0..63). The screen
        ; shows plane rows starting at Vscroll_BG, so the band list is
        ; rotated by vshift = (Vscroll_BG mod 512) >> 3 each frame and tops
        ; are rebased to screen cells, clamped to 28 (the HScroll buffer is
        ; 224 lines — an unclamped top would overrun it). At vshift = 0 the
        ; rotation is an identity copy plus the clamp, so legacy
        ; screen-space configs (vFactorBg=15, vOffset=0) are unchanged.
        ; The shadow view is built EVERY frame, even at vshift = 0: the
        ; clamp below is load-bearing — raw plane-space tops (e.g. 40, 48)
        ; would make the per-line filler emit top*8 > 224 lines and spray
        ; past Hscroll_Buffer into the DMA queues (frozen-VDP crash class).
        move.w  (Parallax_Current_Vscroll_BG).w, d0
        and.w   #$1FF, d0                   ; mod plane height (512 px)
        lsr.w   #3, d0                      ; d0 = vshift in cells (0..63)
        ; -- find k = the band containing plane cell vshift --
        ; (last band whose top <= vshift; tops ascend and band 0 top is 0)
        lea     parallax_config_len(a0), a1
        lea     band_entry_len(a1), a4      ; probe = band[1]
        moveq   #0, d1                      ; d1 = k
        moveq   #1, d2                      ; probe index
.find_k:
        cmp.w   d7, d2
        bhs.s   .found_k
        moveq   #0, d3
        move.b  band_entry_band_top_cell(a4), d3
        cmp.w   d0, d3
        bhi.s   .found_k                    ; top > vshift — stop
        move.w  d2, d1
        adda.w  #band_entry_len, a4
        addq.w  #1, d2
        bra.s   .find_k
.found_k:
        ; -- copy all bands starting at k (wrapping) into the shadow view,
        ;    rebasing tops to screen cells and reordering the scroll words --
        lea     (Parallax_Shadow_Bands).w, a4
        lea     (Parallax_Shadow_Scroll_A).w, a5
        lea     (Parallax_Shadow_Scroll_B).w, a6
        move.w  d7, d6
        subq.w  #1, d6                      ; dbf counter
        move.w  d1, d2                      ; d2 = source band index (starts at k)
        moveq   #0, d4                      ; first-entry flag
.copy_band:
        ; source entry = config bands + d2*band_entry_len (10 bytes)
        move.w  d2, d3
        lsl.w   #3, d3
        move.w  d2, d5
        add.w   d5, d5
        add.w   d5, d3                      ; d3 = d2*10
        lea     parallax_config_len(a0), a1
        adda.w  d3, a1
        move.l  (a1)+, (a4)+
        move.l  (a1)+, (a4)+
        move.w  (a1)+, (a4)+
        ; rebase the copied entry's top to screen cells
        moveq   #0, d3
        move.b  -band_entry_len(a4), d3
        sub.w   d0, d3
        tst.w   d4
        bne.s   .not_first
        moveq   #0, d3                      ; band k starts at the screen top
        moveq   #1, d4
        bra.s   .write_top
.not_first:
        tst.w   d3
        bgt.s   .clamp_top
        addi.w  #64, d3                     ; wrapped past the plane bottom
.clamp_top:
        cmpi.w  #28, d3
        ble.s   .write_top
        moveq   #28, d3                     ; off-screen — zero-length fill
.write_top:
        move.b  d3, -band_entry_len(a4)
        ; reorder the matching scroll words
        move.w  d2, d3
        add.w   d3, d3
        lea     (Parallax_Current_Scroll_A).w, a1
        move.w  (a1,d3.w), (a5)+
        lea     (Parallax_Current_Scroll_B).w, a1
        move.w  (a1,d3.w), (a6)+
        addq.w  #1, d2
        cmp.w   d7, d2
        blo.s   .no_wrap
        moveq   #0, d2
.no_wrap:
        dbf     d6, .copy_band
        lea     (Parallax_Shadow_Bands).w, a1
        lea     (Parallax_Shadow_Scroll_A).w, a2
        lea     (Parallax_Shadow_Scroll_B).w, a3
.bands_ready:

        ; --- Step 4: fill HScroll buffer (mode auto-selected from config) ---
        ;   mode_per_line if either H-deform table is non-NULL.
        ;   a1/a2/a3 = band array + scroll arrays (config's own or shadow).
        move.l  parallax_config_pcfg_deform_table_fg(a0), d0
        or.l    parallax_config_pcfg_deform_table_bg(a0), d0
        beq.s   .fill_per_cell
        ; advance H-deform phase accumulators so animated tables (sine, etc.)
        ; actually scroll their wave over time. Without this the wave is
        ; static and effects like windy clouds / heat shimmer don't animate.
        moveq   #0, d0
        move.b  parallax_config_pcfg_deform_speed_fg(a0), d0
        add.w   d0, (Parallax_Deform_Phase_FG).w
        moveq   #0, d0
        move.b  parallax_config_pcfg_deform_speed_bg(a0), d0
        add.w   d0, (Parallax_Deform_Phase_BG).w
        bsr.w   Parallax_Fill_PerLine
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #(28*8)-1, (Hscroll_Dirty_End).w
        bra.s   .fill_done
.fill_per_cell:
        bsr.w   Parallax_Fill_PerCell
        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #27, (Hscroll_Dirty_End).w
.fill_done:
        rts

; ----------------------------------------------------------------------
Parallax_Step5_Vscroll:
        ; --- Step 5: compute whole-plane Vscroll (always — used by per-column too) ---
        ; FG: vscroll_a = camY (Plane A follows camera 1:1)
        ; BG: target_b  = ((camY - v_center_y) >> v_factor_bg) + v_offset
        ;     current_vscroll_bg += (target_b - current_vscroll_bg) >> PARALLAX_LERP_SHIFT
        ;
        ; Lock sentinel: v_factor_bg = 15 → skip lerp, pin BG = vOffset.
        ; For configs that want the BG plane vertically locked regardless
        ; of Camera_Y (originally a clobber workaround; kept as a feature —
        ; the clobber was root-caused 2026-06-10: TestPlayer d7 stomp).
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

        tst.b   (Parallax_Snap_Pending).w
        bne.s   .v_snap
        tst.b   (Parallax_Transition_Frames).w
        beq.s   .v_snap                             ; no transition — lock to target
        move.w  (Parallax_Current_Vscroll_BG).w, d2
        sub.w   d2, d0
        asr.w   #PARALLAX_LERP_SHIFT, d0
        add.w   d0, d2                              ; d2 = new current_vscroll_bg
        bra.s   .v_pack
.v_snap:
        move.w  d0, d2                              ; snap: current = target
        bra.s   .v_pack                             ; (was falling into .v_locked,
                                                    ;  clobbering the snap with vOffset)
.v_locked:
        ; locked: BG = vOffset (static, ignores camera + lerp)
        ; FG follows camY (d1 already loaded with camY at function entry).
        ; FG_V_scroll = camY scrolls the full 64-row Plane A: the SAT was
        ; relocated $D800->$B800 to free rows 48-63, and the tile cache fills
        ; all 64 rows, so there is no "row-47 garbage" (that note described the
        ; pre-relocation layout). Camera_Y is grid-clamped (Phase 2:
        ; [0, grid_h*SECTION_SIZE - SCREEN_HEIGHT]); the old cam_max_y is gone.
        move.w  parallax_config_pcfg_v_offset(a0), d2
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
        bra.w   Parallax_Step4_Fill         ; Step 4 runs after Vscroll is final

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
; In:  a0 = parallax_config*, d7 = band count (MUST be >= 1 — countdown loop;
;      the only caller guards band_count != 0)
; Out: Hscroll_Buffer filled (224 longwords); a0/d7 preserved
; Clobbers: d0-d6, a1-a6
;
; Per band, all loop-invariant decisions are hoisted and one of FOUR
; specialized line loops runs (both/fg/bg deform, or flat copy):
; the old single loop re-tested table pointers, re-compared shift
; sentinels, re-read shift counts from ROM, and re-derived the BG
; phase base EVERY LINE — measured 45.6k cycles/frame (35.6%% of the
; NTSC budget) at idle, the largest single frame cost in the engine.
;
; Per-band registers inside the line loops:
;   d0 = packed base scroll (FG<<16 | BG)   — constant per band
;   d1 = scratch (index / sample / out word)
;   d2 = BG phase base (Phase_BG + band_phase)
;   d3 = shift_a (low) / shift_b (high) — swap to switch
;   d4 = line index    d5 = band end line
;   d6 = FG phase base (Phase_FG + band_phase)
;   d7 = bands remaining (countdown; movem-restored at exit)
;   a5/a6 = FG/BG deform tables
; Deform-table indices wrap at 256 via andi #$FF.
; ----------------------------------------------------------------------
Parallax_Fill_PerLine:
        movem.l a0/d7, -(sp)                        ; preserve caller's config ptr + band count

        ; a1/a2/a3 = band array + scroll arrays, set by the caller (Step 4a:
        ; either the config's own data or the vscroll-rotated shadow view)
        lea     (Hscroll_Buffer).w, a4              ; output ptr
        movea.l parallax_config_pcfg_deform_table_fg(a0), a5  ; NULL = no FG sampling
        movea.l parallax_config_pcfg_deform_table_bg(a0), a6  ; NULL = no BG sampling

        moveq   #0, d4                              ; current line index (0..223)

.next_band:
        ; --- end_line for this band: next band's top_cell×8, or 224 ---
        move.w  #224, d5
        subq.w  #1, d7
        beq.s   .have_end                           ; last band
        moveq   #0, d5
        move.b  band_entry_band_top_cell+band_entry_len(a1), d5
        lsl.w   #3, d5
.have_end:

        ; --- packed base scroll (constant per band) ---
        move.w  (a2), d0                            ; FG (already negated)
        swap    d0
        move.w  (a3), d0                            ; BG → d0 = FG<<16 | BG

        ; --- hoist channel-active decisions ---
        ; FG active: table non-NULL AND shift_a != 15
        cmpa.w  #0, a5
        beq.s   .fg_inactive
        moveq   #0, d3
        move.b  band_entry_band_deform_shift_a(a1), d3
        cmpi.b  #15, d3
        beq.s   .fg_inactive
        ; FG ACTIVE — d3.w = shift_a; d6 = FG phase base
        move.w  (Parallax_Deform_Phase_FG).w, d6
        moveq   #0, d1
        move.b  band_entry_band_phase_offset(a1), d1
        add.w   d1, d6
        ; BG active too?
        cmpa.w  #0, a6
        beq.s   .band_fg_only
        moveq   #15, d1
        cmp.b   band_entry_band_deform_shift_b(a1), d1
        beq.s   .band_fg_only
        ; --- BOTH channels ---
        swap    d3
        move.b  band_entry_band_deform_shift_b(a1), d3  ; low byte = shift_b after swap below
        moveq   #0, d2
        move.b  band_entry_band_phase_offset(a1), d2
        add.w   (Parallax_Deform_Phase_BG).w, d2        ; d2 = BG phase base
        swap    d3                                  ; d3.w = shift_a, hi = shift_b
        bra.s   .lp_both
.fg_inactive:
        ; FG flat — BG active?
        cmpa.w  #0, a6
        beq.w   .lp_flat
        moveq   #15, d1
        cmp.b   band_entry_band_deform_shift_b(a1), d1
        beq.w   .lp_flat
        ; --- BG only ---
        moveq   #0, d3
        move.b  band_entry_band_deform_shift_b(a1), d3  ; d3.w = shift_b
        moveq   #0, d2
        move.b  band_entry_band_phase_offset(a1), d2
        add.w   (Parallax_Deform_Phase_BG).w, d2
        bra.s   .lp_bg

; --- BOTH: FG and BG sampled per line ---
.lp_both:
        cmp.w   d5, d4
        bhs.w   .band_done
.lb_line:
        move.w  d6, d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a5,d1.w), d1
        ext.w   d1
        asr.w   d3, d1                              ; >> shift_a
        swap    d0
        add.w   d0, d1                              ; + FG base
        swap    d0
        move.w  d1, (a4)+                           ; FG word
        swap    d3                                  ; → shift_b
        move.w  d2, d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a6,d1.w), d1
        ext.w   d1
        asr.w   d3, d1                              ; >> shift_b
        swap    d3                                  ; → shift_a
        add.w   d0, d1                              ; + BG base
        move.w  d1, (a4)+                           ; BG word
        addq.w  #1, d4
        cmp.w   d5, d4
        blo.s   .lb_line
        bra.s   .band_done

; --- FG only: BG word constant ---
.band_fg_only:
        cmp.w   d5, d4
        bhs.s   .band_done
.lf_line:
        move.w  d6, d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a5,d1.w), d1
        ext.w   d1
        asr.w   d3, d1
        swap    d0
        add.w   d0, d1
        swap    d0
        move.w  d1, (a4)+                           ; FG word
        move.w  d0, (a4)+                           ; BG word (constant)
        addq.w  #1, d4
        cmp.w   d5, d4
        blo.s   .lf_line
        bra.s   .band_done

; --- BG only: FG word constant ---
.lp_bg:
        cmp.w   d5, d4
        bhs.s   .band_done
        swap    d0                                  ; d0 = BG<<16 | FG for this loop
.lg_line:
        move.w  d2, d1
        add.w   d4, d1
        andi.w  #$FF, d1
        move.b  (a6,d1.w), d1
        ext.w   d1
        asr.w   d3, d1
        move.w  d0, (a4)+                           ; FG word (constant, low)
        swap    d0
        add.w   d0, d1                              ; + BG base
        swap    d0
        move.w  d1, (a4)+                           ; BG word
        addq.w  #1, d4
        cmp.w   d5, d4
        blo.s   .lg_line
        bra.s   .band_done

; --- FLAT: same longword for every line of the band ---
.lp_flat:
        move.w  d5, d1
        sub.w   d4, d1
        ble.s   .band_done                          ; empty/malformed band
        move.w  d5, d4                              ; line index jumps to band end
        subq.w  #1, d1
.fl_line:
        move.l  d0, (a4)+
        dbf     d1, .fl_line

.band_done:
        lea     band_entry_len(a1), a1
        addq.l  #2, a2
        addq.l  #2, a3
        tst.w   d7
        bne.w   .next_band

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
        ; a1/a2/a3 = band array + scroll arrays, set by the caller (Step 4a:
        ; either the config's own data or the vscroll-rotated shadow view)
        lea     (Hscroll_Buffer).w, a4
        moveq   #0, d3                              ; d3 = current cell index
        moveq   #0, d2                              ; d2 = band index

.next_band:
        ; -- determine end_cell for this band --
        addq.w  #1, d2
        cmp.w   d7, d2
        bhs.s   .last_band_end             ; d2 >= d7 → this is last band
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
