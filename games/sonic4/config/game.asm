; Sonic 4 — game contract declarations consumed by the engine.

; --- ROM header fields (exact widths asserted by gameHeader) ---
GAME_CONSOLE    equ "SEGA GENESIS    "
GAME_COPYRIGHT  equ "(C)     2026.APR"
GAME_TITLE_DOM  equ "SONIC THE HEDGEHOG 4                            "
GAME_TITLE_OVS  equ "SONIC THE HEDGEHOG 4                            "
GAME_SERIAL     equ "GM S4-0001-00 "
GAME_IO         equ "J               "
GAME_SRAM       equ "            "
GAME_MEMO       equ "                                                    "
GAME_REGION     equ "JUE             "

; --- Boot handoff: the engine boot ends by entering the game here ---
Game_Entry      = GameState_OJZScroll_Init
GAME_ENTRY_ID   = GS_OJZ_SCROLL_TEST

; --- gameBootHook — engine boot invokes this after Sound_Init, before the
;     game-state handoff. May be empty. Sonic 4: sound test-harness ping +
;     autoplay (moved verbatim from engine/system/boot.asm).
gameBootHook macro {GLOBALSYMBOLS}
    ifdef SOUND_DRIVER_ENABLED
      ifdef SOUND_DEBUG_HOTKEYS
        moveq   #$3C, d0                 ; ping with a recognizable value
        bsr.w   Sound_Ping
        moveq   #SONG_MOVINGTRUCKS, d0   ; autoplay the test song
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w     ; track play state for the Start-toggle
      endif
    endif
    endm
