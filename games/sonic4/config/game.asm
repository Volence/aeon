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

; --- sound contract ---
; SFX_BLOB_BANK — the bank all SFX blobs live in (engine/sound/sound_sfx.asm
; SetBank()s this before reading a blob). Game-declared, but sfx_bankid()
; (sound_sfx.asm) isn't visible yet at THIS include position (main.asm
; includes this file before boot.asm pulls in the Z80 sound driver), and the
; first SFX blob label doesn't exist until the generated sfx_NN.asm includes
; run later still. The actual declaration lives at the top of the generated
; games/sonic4/data/sound/sfx/sfx_table.asm (emitted by
; tools/sfx_transcode.py's emit_sfx_table_asm()), which is included after
; both are visible. This comment documents the contract; there is no
; assignment here.

SFXID_REV_LOOP = SFXID_SPINDASH   ; spindash-rev special case; -1 = feature off (games without a spindash)

; SFXID_RING_LEFT / SFXID_RING_RIGHT are engine contract constants: the
; engine ring system's L/R stereo alternation (Ring_Sfx_Speaker,
; engine/sound/sound_api.asm) posts one or the other depending on which
; speaker side the ring pickup should pan toward. Currently defined in
; sound_constants.asm (root); they move to this file in a later task. No
; code change here — comment only.

; SndDefaultPitchTable (engine contract: sound_fm.asm's Fm_NoteFromTable
; fallback when a song's pitchtable_ptr is 0) is DEFERRED — see the comment
; above MovingTrucks_PitchTable: in games/sonic4/data/sound/movingtrucks_pitchtable.asm.
; Adding a same-address alias label was found to perturb the convsym-appended
; MD-debugger symbol table in the plain (non-DEBUG) build, breaking the
; Phase A byte-identical gate; sound_fm.asm still reads MovingTrucks_PitchTable
; directly today.

; --- engine feature gates ---
GAME_CAMERA_JUMP_LOCK = 1   ; camera suppresses down-scroll during jump states; requires game-defined _pl_state, PSTATE_JUMP, PSTATE_ROLLJUMP; 0 = plain deadzone follow

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
