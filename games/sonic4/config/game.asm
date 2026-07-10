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
; includes this file before boot.asm pulls in the Z80 sound driver). As of
; sound-migration T3 (ruling R2) the declaration lives in main.asm right after
; SND_ENGINE_TABLE_BANK, spelled `SFX_BLOB_BANK = SND_ENGINE_TABLE_BANK` —
; sound because the SFX co-residency guard (and sfx_bank.emp's ensure successor)
; asserts exactly that equality, and it no longer derives from the .emp-side
; Sfx_33 label. The related SFX_ID_BASE / SFX_COUNT / SFX_TABLE_LEN ints live in
; config/sound_ids.asm beside the SFXID_* ladder. This comment documents the
; contract; there is no assignment here.

SFXID_REV_LOOP = SFXID_SPINDASH   ; spindash-rev special case; -1 = feature off (games without a spindash)

; SFXID_RING_LEFT / SFXID_RING_RIGHT are engine contract constants: the
; engine ring system's L/R stereo alternation (Ring_Sfx_Speaker,
; engine/sound/sound_api.asm) posts one or the other depending on which
; speaker side the ring pickup should pan toward. Currently defined in
; sound_constants.asm (root); they move to this file in a later task. No
; code change here — comment only.

; SndDefaultPitchTable is an engine contract label: sound_fm.asm's
; Fm_NoteFromTable falls back to it when a song's pitchtable_ptr is 0. The
; song bank head MUST define it inside the $8000 window — Sonic 4 defines it
; above MovingTrucks_PitchTable: in
; games/sonic4/data/sound/movingtrucks_pitchtable.asm.

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

; --- gameDebugTick — engine GameLoop invokes this once per frame after
;     VSync/SFX-drain. May be empty. Sonic 4: sound test-harness hotkeys.
;     LOCKSTEP: engine/system/game_loop.emp mirrors this macro's EXPANSION
;     (comptime if over the same defines) — edit both together; sigil's
;     game_loop combo matrix re-extracts this body and fails on drift.
gameDebugTick macro {GLOBALSYMBOLS}
    ifdef SOUND_DEBUG_HOTKEYS
      ifdef SOUND_DRIVER_ENABLED
        jsr     Debug_MusicToggle       ; jsr not bsr.w — placement-free
      endif
    endif
    endm
