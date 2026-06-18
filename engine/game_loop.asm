; Game state machine and main loop

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        bsr.w   Debug_MusicToggle       ; START toggles the demo song (stop/play)
      endif
    endif
        movea.l (Game_State).w, a0
        jsr     (a0)
        bra.s   GameLoop

; -----------------------------------------------
; GameState_Idle — minimal state (VSync only)
; -----------------------------------------------
GameState_Idle:
        rts

    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
; -----------------------------------------------
; Debug_MusicToggle — START button toggles the demo song (DEBUG test harness).
; Edge-detected on Ctrl_1_Press. Also exercises Sound_StopMusic and the
; song-switch silence path (a fresh PlayMusic). Clobbers: d0-d2/a0/a1.
; -----------------------------------------------
Debug_MusicToggle:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_START, d0
        beq.s   .done                   ; START not pressed this frame
        tst.b   (Dbg_Music_On).w
        bne.s   .stop
        moveq   #SONG_MOVINGTRUCKS, d0  ; was stopped -> play (Phase 3 native Moving Trucks)
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w
        rts
.stop:
        bsr.w   Sound_StopMusic         ; was playing -> stop
        clr.b   (Dbg_Music_On).w
.done:
        rts
      endif
    endif
