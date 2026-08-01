; Aeon engine demo — the AS root (Parcel K4 inc-6B, the A1 stub).
;
; The from-scratch ROM layout is the DECLARED sigil map + registry (games/demo/map.toml,
; crates/sigil-harness/src/native.rs) — main.asm + engine/engine.inc are DELETED. This
; file is the minimal AS entry the sigil-frontend-as assembles as the residual root: it
; pulls in the two named survivors (the game contract + the vendored debugger) so their
; defines/macros/link-externs enter the residual symbol environment. It EMITS NO BYTES
; and declares NO orgs — every ROM byte is a natively-placed `.emp` section. The demo is
; sound-OFF, so it carries no sound-bank cross-seam include (unlike sonic4's game_root).

    cpu 68000
    padding off
    supmode on

    ; The game contract (survives per spec §0): GAME_CAMERA_JUMP_LOCK, Game_Entry /
    ; GAME_ENTRY_ID, and the (empty) gameBootHook / gameDebugTick macro bodies. The
    ; kill-row-9/45 combo matrices re-extract those bodies from this exact file, so its
    ; text and expansion must stay byte-identical — this include site preserves them.
    include "games/demo/config/game.asm"

    ; The MD Debugger / Error Handler (vendored survivor per spec §0): definitions +
    ; macros only here; the error-handler blob itself is native (engine/debug/
    ; error_handler.emp), and debugger.asm resolves MDDBG__* as link externs off that base.
    include "engine/debug/debugger.asm"

    END
