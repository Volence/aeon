; Game state machine and main loop (§9.13)

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
; GameState_Boot — initial boot state
; Displays solid blue screen to prove pipeline works
; -----------------------------------------------
GameState_Boot:
        tst.b   (Game_State_Init).w
        bne.s   .update

        ; First-frame init
        move.b  #1, (Game_State_Init).w

        ; Set background color to blue (CRAM entry 0)
        move.l  #vdpComm(0, CRAM, WRITE), (VDP_CTRL).l
        move.w  #$0E00, (VDP_DATA).l        ; blue ($0E00 = 0000 EEE0 0000 0000)

        ; Enable display
        SetVDPReg VDP_Shadow_vdp_mode2, #$74           ; $34 | $40 (display enable) = $74

.update:
        rts
