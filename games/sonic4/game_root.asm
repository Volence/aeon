; Sonic 4 — the AS root (Parcel K4 inc-6B, the A1 stub).
;
; The from-scratch ROM layout is the DECLARED sigil map + registry (games/sonic4/
; map.toml, crates/sigil-harness/src/native.rs) — main.asm + engine/engine.inc are
; DELETED. This file is the minimal AS entry the sigil-frontend-as assembles as the
; residual root: it pulls in the one named survivor (the vendored debugger) so its
; defines/macros/link-externs enter the residual symbol environment. It EMITS NO
; BYTES and declares NO orgs — every ROM byte is a natively-placed `.emp` section;
; the residual exists only for the defines/externs the harvest + link resolve.
;
; The game contract is `.emp`-native (L1 P2): the engine declares the `Game` interface
; (engine/system/game_contract.emp) and the game binds it in games/sonic4/config/game.emp
; (module games.sonic4.game) — the last game-authored `.asm` carrying semantics is gone.

    cpu 68000
    padding off
    supmode on

    ; The MD Debugger / Error Handler (vendored survivor per spec §0): definitions +
    ; macros only here; the error-handler blob itself is native (engine/debug/
    ; error_handler.emp), and debugger.asm resolves MDDBG__* as link externs off that base.
    include "engine/debug/debugger.asm"

    END
