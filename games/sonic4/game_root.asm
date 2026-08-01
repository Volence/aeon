; Sonic 4 — the AS root (Parcel K4 inc-6B, the A1 stub).
;
; The from-scratch ROM layout is the DECLARED sigil map + registry (games/sonic4/
; map.toml, crates/sigil-harness/src/native.rs) — main.asm + engine/engine.inc are
; DELETED. This file is the minimal AS entry the sigil-frontend-as assembles as the
; residual root: it pulls in the two named survivors (the game contract + the vendored
; debugger) so their defines/macros/link-externs enter the residual symbol environment,
; and it re-homes the one cross-seam artifact include the deleted skeleton carried. It
; EMITS NO BYTES and declares NO orgs — every ROM byte is a natively-placed `.emp`
; section; the residual exists only for the defines/externs the harvest + link resolve.

    cpu 68000
    padding off
    supmode on

    ; The game contract (survives per spec §0): GAME_CAMERA_JUMP_LOCK, Game_Entry /
    ; GAME_ENTRY_ID, and the gameBootHook / gameDebugTick macro bodies. The kill-row-9/45
    ; combo matrices re-extract those macro bodies from this exact file, so its text and
    ; expansion must stay byte-identical — this include site preserves them unchanged.
    include "games/sonic4/config/game.asm"

    ; The MD Debugger / Error Handler (vendored survivor per spec §0): definitions +
    ; macros only here; the error-handler blob itself is native (engine/debug/
    ; error_handler.emp), and debugger.asm resolves MDDBG__* as link externs off that base.
    include "engine/debug/debugger.asm"

    ; Cross-seam re-home (was gameSoundDataIncludes in main.asm): the Moving-Trucks bank's
    ; SongTable / SongPatchTable labels sit at mid-blob offsets a single embed cannot
    ; label, so the seam-2 emit writes them as absolute equs (mt_syms{,_debug}.asm, a
    ; generated artifact like the .bin). engine/sound/sound_api.emp externs them; this
    ; include supplies them to the whole-ROM link. Gated by SIGIL_EMP_MT (set in every
    ; sound-on build); the shape selects the per-song-count table. Zero bytes (pure equs).
    ifdef SIGIL_EMP_MT
      ifdef __DEBUG__
        include "engine/sound/generated/mt_syms_debug.asm"
      else
        include "engine/sound/generated/mt_syms.asm"
      endif
    endif

    END
