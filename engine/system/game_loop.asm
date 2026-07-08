; Game state machine and main loop

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
    ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_DrainSfxRing      ; A2: drain ONE pending SFX/frame into the mailbox
    endif                               ; (release sound builds need this too, not just DEBUG)
        gameDebugTick                   ; game-supplied per-frame debug hook (may be empty)
        movea.l (Game_State).w, a0
        jsr     (a0)
        bra.s   GameLoop

; -----------------------------------------------
; GameState_Idle — minimal state (VSync only)
; -----------------------------------------------
GameState_Idle:
        rts

