; Sonic 4 — game contract declarations consumed by the engine.

; --- ROM header fields ---
; The $100-$1FF ROM header is authored in games/sonic4/config/header.emp (Parcel
; K4): the game-declared strings are typed `[u8; N]` data there (the type is the
; exact-width guard), and it places natively right after the vectors.

; --- sound contract ---
; SFX_BLOB_BANK — the bank all SFX blobs live in (engine/sound/sound_sfx.asm
; SetBank()s this before reading a blob). Game-declared, but sfx_bankid()
; (sound_sfx.asm) isn't visible yet at THIS include position (main.asm
; includes this file before boot.asm pulls in the Z80 sound driver). As of
; sound-migration T3 (ruling R2) the declaration lives in main.asm right after
; SND_ENGINE_TABLE_BANK, spelled `SFX_BLOB_BANK = SND_ENGINE_TABLE_BANK` —
; sound because the SFX co-residency guard (and sfx_bank.emp's ensure successor)
; asserts exactly that equality, and it no longer derives from the .emp-side
; Sfx_33 label. The related SFX_ID_BASE / SFX_COUNT / SFX_TABLE_LEN are DERIVED in
; games/sonic4/data/sound/sfx/sfx_bank.emp (from the SfxTable rows) and harvested
; into the residual AS (Parcel F2). This comment documents the contract; there is
; no assignment here.

; The song ids, symbolic SFX ids (incl. SFXID_RING_LEFT / SFXID_RING_RIGHT for
; the engine ring system's L/R stereo alternation, Ring_Sfx_Speaker), the
; spindash-rev special case (SFXID_REV_LOOP), and the SFX priority ladder live in
; games/sonic4/config/sound_ids.emp (module games.sonic4.sound_ids) — flipped
; from AS at Parcel F2, harvested into the residual AS. sound_api.emp keeps the
; typed `SFXID_RING_*: SfxId` mirrors (the SfxId newtype is a language-round
; deferral), drift-guarded against that authority.

; SndDefaultPitchTable is an engine contract label: sound_fm.asm's
; Fm_NoteFromTable falls back to it when a song's pitchtable_ptr is 0. The
; song bank head MUST define it inside the $8000 window — Sonic 4 defines it
; (aliased over MovingTrucks_PitchTable:) at the soundBankHead BINCLUDE of
; movingtrucks_pitchtable.bin, which sigil lowers from
; games/sonic4/data/sound/movingtrucks_pitchtable.emp.

; --- engine feature gates ---
GAME_CAMERA_JUMP_LOCK = 1   ; camera suppresses down-scroll during jump states; requires game-defined _pl_state, PSTATE_JUMP, PSTATE_ROLLJUMP; 0 = plain deadzone follow

; --- Boot handoff: the engine boot ends by entering the game here ---
; Game_Entry is the game-state handoff pointer boot.asm loads (move.l #Game_Entry).
; ojz_scroll_test owns GameState_OJZScroll_Init — a local label in the pure-AS
; build (the twin is included) or a placed .emp module in the sigil mixed build
; (SIGIL_EMP_OJZ_SCROLL_TEST). Either way the equalate resolves it: the assembler
; folds it in the pure-AS build, the link folds it off the extern base in the
; mixed build (the "equ off link-external base" capability — sigil links it per
; shape AND per game, so no sonic4-shape numeric fold is needed).
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
