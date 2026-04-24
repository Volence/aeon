; Game state machine and main loop

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
        movea.l (Game_State).w, a0
        jsr     (a0)
        bra.s   GameLoop

; -----------------------------------------------
; GameState_Idle — minimal state (VSync only)
; -----------------------------------------------
GameState_Idle:
        rts
