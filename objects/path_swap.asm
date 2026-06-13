; PathSwap — invisible vertical line that flips Player_1's collision layer
;
; Crossing the line writes SST_layer (0 = path A / primary, 1 = path B /
; secondary). Side tracking is UNCONDITIONAL (S.C.E. Path Swap arming
; semantics: the passed flag flips on every crossing); only the LAYER WRITE
; is gated by the vertical band and the optional grounded check. S.C.E.'s
; extra |dx| < $40 proximity gate is intentionally dropped — its job
; (don't fire on far-away re-expression) is covered here by spawn-time
; re-arming (Init) and by the teleport rebase shifting object and player
; X by the same delta (side relation invariant).
;
; Subtype:
;   bits 0-3 = half-height in 32px units (0 = default 64px)
;   bit 4    = direction-sense invert
;              (normal: crossing rightward -> layer 1, leftward -> layer 0)
;   bit 5    = reserved: render-priority swap (future)
;   bit 6    = grounded-only (skip the write while ST_IN_AIR — classic
;              swappers use this on lines a player may legitimately jump
;              across without changing path)
;
; Line position is read from SST_x_pos/SST_y_pos every frame — never cached
; in sst_custom (CODING_CONVENTIONS §7.8: teleport rebases shift SST
; positions but cannot see absolute coordinates in custom vars).
;
; Entity-window lifecycle: despawn (camera leaves) deletes the SST and
; clears the loaded bit WITHOUT setting the killed bit, so the swapper
; respawns when scrolled back in and Init re-arms prev_side from the
; player's current position — re-armable by construction. Never mark a
; swapper killed.

PATHSWAP_BIT_INVERT     = 4         ; subtype: invert direction sense
PATHSWAP_BIT_PRIO       = 5         ; subtype: reserved (priority swap)
PATHSWAP_BIT_GROUNDED   = 6         ; subtype: only swap while grounded
PATHSWAP_DEFAULT_HH     = 64        ; half-height when subtype bits 0-3 = 0

; Custom SST fields (overlay on sst_custom)
PathSwapV struct
half_height     ds.w 1              ; vertical write-gate half-extent (px)
prev_side       ds.b 1              ; scc byte: $FF = player right of line
PathSwapV endstruct
        objvarsCheck PathSwapV_len
_ps_half_height = SST_sst_custom+PathSwapV_half_height
_ps_prev_side   = SST_sst_custom+PathSwapV_prev_side

ObjDef_PathSwap:
        objdef code=PathSwap_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
               wdth=4, hght=64, col=COLLISION_NONE

; -----------------------------------------------
; PathSwap_Init — behavior-specific init (first-frame code_addr)
; Decodes half-height from the subtype and arms prev_side from the
; player's CURRENT position so a spawn/respawn never counts as a crossing.
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
PathSwap_Init:
        moveq   #$F, d0
        and.b   SST_subtype(a0), d0
        lsl.w   #5, d0                          ; units of 32px
        bne.s   .have_hh
        moveq   #PATHSWAP_DEFAULT_HH, d0
.have_hh:
        move.w  d0, _ps_half_height(a0)

        lea     (Player_1).w, a1
        move.w  SST_x_pos(a1), d0
        cmp.w   SST_x_pos(a0), d0               ; signed — engine X can be negative
        sgt     d1
        move.b  d1, _ps_prev_side(a0)

        move.w  #objroutine(PathSwap_Main), SST_code_addr(a0)
        rts                                     ; first swap chance is next frame

; -----------------------------------------------
; PathSwap_Main — per-frame crossing check
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
PathSwap_Main:
        lea     (Player_1).w, a1
        move.w  SST_x_pos(a1), d0
        cmp.w   SST_x_pos(a0), d0
        sgt     d1                              ; d1 = $FF right of line, $00 left
        cmp.b   _ps_prev_side(a0), d1
        beq.s   .done                           ; no crossing
        move.b  d1, _ps_prev_side(a0)           ; track ALWAYS — even when the
                                                ; write below is gated off

        ; vertical band gate: |player_y - line_y| <= half_height
        move.w  SST_y_pos(a1), d0
        sub.w   SST_y_pos(a0), d0
        bpl.s   .y_abs
        neg.w   d0
.y_abs:
        cmp.w   _ps_half_height(a0), d0
        bhi.s   .done

        ; grounded-only gate (subtype bit 6)
        move.b  SST_subtype(a0), d2
        btst    #PATHSWAP_BIT_GROUNDED, d2
        beq.s   .sense
        btst    #ST_IN_AIR, SST_status(a1)
        bne.s   .done

.sense:
        ; layer = crossing direction (rightward = 1) XOR invert bit
        moveq   #1, d0
        and.b   d1, d0                          ; $FF -> 1, $00 -> 0
        btst    #PATHSWAP_BIT_INVERT, d2
        beq.s   .write
        eori.b  #1, d0
.write:
        move.b  d0, SST_layer(a1)
.done:
    ifdef __DEBUG__
        jmp     Draw_Sprite                     ; DEBUG: visible test marker
    else
        rts                                     ; invisible — never enqueued
    endif
