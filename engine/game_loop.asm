; Game state machine and main loop

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
        movea.l (Game_State).w, a0
        jsr     (a0)
        ; Press accumulators are consumed by this tick's logic; clear so
        ; next tick sees fresh edges. VBlank ORs into these (lag-frame
        ; presses survive); a press landing in the final instructions of
        ; a lag frame can be lost — same window as the classics.
        clr.b   (Ctrl_1_Press).w
        clr.b   (Ctrl_2_Press).w
        bra.s   GameLoop

; -----------------------------------------------
; GameState_Idle — minimal state (VSync only)
; -----------------------------------------------
GameState_Idle:
        rts
