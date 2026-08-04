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
    ;
    ; DEBUG-ONLY (review item 29 part 4 — the MDDBG strip): error_handler.emp is now a
    ; DEBUG-only native module, so in the RELEASE shape the MDDBG__* link externs
    ; debugger.asm's equ table derives off (MDDBG__Debugger_AddressRegisters, …,
    ; MDDBG__Str_OffsetLocation_24bit) have no definition. Including it in release makes
    ; those equs unresolvable — a hard link error. Gate the include on __DEBUG__ (defined
    ; only in debug builds): release ships zero debugger definitions, exactly as it ships
    ; zero debugger code.
    ifdef __DEBUG__
    include "engine/debug/debugger.asm"
    endif

    ; EquSym carrier (review item 29 part 4). The residual AS root's real job now is
    ; to re-export the harvested `.emp`-owned engine constants (HW_*, …) as link
    ; EquSyms, so the `.emp` modules that reference them as BARE link symbols (e.g.
    ; boot.emp's `tst.l HW_PORT_A_CTRL_FULL`) resolve at the joint link. That export
    ; (attach_guarded_equ_exports) only runs when the assembled module has ≥1 section.
    ; In DEBUG the debugger.asm include opens one; in RELEASE it is gated out, so this
    ; single zero-byte equate forces the carrier section open. It emits no bytes and is
    ; filtered from the (DEBUG-only) deb2 symbol appendix — byte-neutral in both shapes.
__Aeon_AS_Carrier:  equ 0

    END
