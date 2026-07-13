; Game state machine and main loop

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; Clobbers: d0-d7, a0-a6 (retro-fix batch 2, item 9 sweep) — the jsr (a0) state
;   dispatch runs arbitrary game-state code, so nothing is preserved. Never
;   returns (bra.s GameLoop), so the contract is nominal.
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

