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
; Debug_MusicToggle — DEBUG sound test-harness hotkeys (edge-detected on
; Ctrl_1_Press). Key map:
;   A     = restart Moving Trucks from pattern 0 (logger-safe re-trigger)
;   B     = fire the next test SFX in the cycle (Dbg_Sfx_Sel)
;   UP    = play HCZ2 (S3K Hydrocity Zone Act 2 import, id 3)
;   C     = play the DAC-drum-test song (id 2)
;   START = toggle Moving Trucks play/stop
; Also exercises Sound_StopMusic and the song-switch silence path (a fresh
; PlayMusic). Clobbers: d0-d2/a0/a1.
; -----------------------------------------------
Debug_MusicToggle:
        ; A button = RESTART the song from pattern 0 (re-trigger Sound_PlayMusic; NO
        ; reboot, NO toggle). For clean from-the-very-top VGM capture during sound
        ; debugging: the emulator's reset/reload either kills the VGM logger or doesn't
        ; restart the Z80 sequencer, so this gives a logger-safe pattern-0 restart on
        ; demand (press A while logging -> capture begins exactly at the song's start).
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_A, d0
        beq.s   .check_sfx
        moveq   #SONG_MOVINGTRUCKS, d0   ; re-trigger from the top (load silences first)
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w
        rts
.check_sfx:
        ; B button = fire the NEXT test SFX in the cycle (DEBUG SFX-trigger hotkey).
        ; Edge-detected on Ctrl_1_Press (one fire per fresh press). Dbg_Sfx_Sel cycles
        ; 0..7 over Dbg_SfxIdTable so every core SFX is drivable for VGM capture +
        ; the acceptance matrix. B ($10) does not collide with A($40)/START($80).
        ; RING_RIGHT is fired via Sound_PlayRing so the L/R stereo-alternation path is
        ; exercised too; all others go straight through Sound_PlaySFX. (Both preserve
        ; a0 + clobber only d0/SR — safe inside this debug-toggle's d0-d2/a0/a1 budget.)
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_B, d0
        beq.s   .check_hcz2
        move.w  (Dbg_Sfx_Sel).w, d1      ; current cycle index (0..7)
        move.w  d1, d2
        addq.w  #1, d2
        andi.w  #7, d2                    ; wrap 0..7 (8 ids)
        move.w  d2, (Dbg_Sfx_Sel).w      ; advance for the next press
        andi.w  #7, d1                    ; clamp (defensive)
        cmpi.w  #1, d1                    ; index 1 = RING_RIGHT -> use the ring path
        beq.s   .sfx_ring
        moveq   #0, d0
        lea     Dbg_SfxIdTable(pc), a1
        move.b  (a1,d1.w), d0            ; d0.b = id from the cycle table
        bsr.w   Sound_PlaySFX
        rts
.sfx_ring:
        bsr.w   Sound_PlayRing          ; L/R-alternating ring SFX ($33/$34)
        rts
.check_hcz2:
        ; UP = play the HCZ2 (S3K Hydrocity Zone Act 2) import song (id 3) on a fresh
        ; press. The plan/design proposed B for this, but B ($10) is already the SFX-
        ; cycle hotkey (above), so the dedicated HCZ2 trigger uses UP — a free D-pad
        ; bit unused by the debug harness and by the idle game state. Edge-detected on
        ; Ctrl_1_Press; UP ($01) does not collide with A($40)/B($10)/C($20)/START($80).
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_UP, d0
        beq.s   .check_sample
        moveq   #SONG_HCZ2, d0           ; S3K Hydrocity Zone Act 2 import (Phase 7)
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w     ; keep START's play/stop toggle coherent
        rts
.check_sample:
        ; C button = play the DEBUG STREAM DAC-on drum-test song (id 2) on a fresh
        ; press. Exercises the DAC-drum phase end-to-end: $E2 kick/snare from the
        ; shared DAC bank with the per-frame song<->sample bank swap (B1), the Layer-4
        ; FM6 key-on gate, and FM/PSG music streaming alongside. (Supersedes the old
        ; one-shot blip hotkey — the song fires real kick/snare via $E2.) Edge-detected
        ; on Ctrl_1_Press; C ($20) does not collide with A($40)/B($10)/START($80).
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_C, d0
        beq.s   .check_start
        moveq   #SONG_DRUMTEST, d0       ; DEBUG STREAM DAC-on drum-test song
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w     ; keep START's play/stop toggle coherent
        rts
.check_start:
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

; DEBUG SFX-trigger cycle (indexed by Dbg_Sfx_Sel, 0..7). Index 1 (RING_RIGHT) is
; special-cased to Sound_PlayRing in .check_sfx; the byte here is the fallback id.
; Order: JUMP / RING_RIGHT / SPINDASH / DASH / ROLL / SKID / DEATH / RINGLOSS.
Dbg_SfxIdTable:
        dc.b    SFXID_JUMP              ; 0
        dc.b    SFXID_RING_RIGHT        ; 1 (fired via Sound_PlayRing for L/R alt)
        dc.b    SFXID_SPINDASH          ; 2
        dc.b    SFXID_DASH              ; 3
        dc.b    SFXID_ROLL              ; 4
        dc.b    SFXID_SKID              ; 5
        dc.b    SFXID_DEATH             ; 6
        dc.b    SFXID_RINGLOSS          ; 7
        align   2
      endif
    endif
