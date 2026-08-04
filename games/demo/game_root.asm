; Aeon engine demo — the AS root (Parcel K4 inc-6B, the A1 stub).
;
; The from-scratch ROM layout is the DECLARED sigil map + registry (games/demo/map.toml,
; crates/sigil-harness/src/native.rs) — main.asm + engine/engine.inc are DELETED. This
; file is the minimal AS entry the sigil-frontend-as assembles as the residual root: it
; pulls in the one named survivor (the vendored debugger) so its defines/macros/link-
; externs enter the residual symbol environment. It EMITS NO BYTES and declares NO orgs —
; every ROM byte is a natively-placed `.emp` section. The demo is sound-OFF, so it carries
; no sound-bank cross-seam include (unlike sonic4's game_root).
;
; The game contract is `.emp`-native (L1 P2): the engine declares the `Game` interface
; (engine/system/game_contract.emp) and the demo binds it in games/demo/config/game.emp
; (module games.demo.game) — the minimal manifest, no hooks bound.

    cpu 68000
    padding off
    supmode on

    ; The MD Debugger / Error Handler (vendored survivor per spec §0): definitions +
    ; macros only here; the error-handler blob itself is native (engine/debug/
    ; error_handler.emp), and debugger.asm resolves MDDBG__* as link externs off that base.
    ;
    ; DEBUG-ONLY (review item 29 part 4 — the MDDBG strip): error_handler.emp is now a
    ; DEBUG-only native module, so in the RELEASE shape the MDDBG__* link externs
    ; debugger.asm's equ table derives off have no definition and the include would be a
    ; hard link error. Gate the include on __DEBUG__ (defined only in debug builds).
    ifdef __DEBUG__
    include "engine/debug/debugger.asm"
    endif

    ; EquSym carrier (review item 29 part 4) — see games/sonic4/game_root.asm for the
    ; full rationale. In RELEASE the debugger.asm include is gated out, so this single
    ; zero-byte equate forces the carrier section that attach_guarded_equ_exports needs
    ; to re-export the harvested engine-constant EquSyms (HW_*, …) to the `.emp` link.
    ; Byte-neutral in both shapes.
__Aeon_AS_Carrier:  equ 0

    END
