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
    ; GATED ON __MDDBG__ (the crash-report axis, owner-ruled 2026-08-04): the include is
    ; valid exactly when error_handler.emp is placed, because the MDDBG__* link externs
    ; its equ table derives off are that module's `pub equ`s — without the island they are
    ; unresolvable, a hard link error. __MDDBG__ is pushed when
    ; `profile.debug || profile.crash_report`, so DEBUG and RELEASE include it and only
    ; the opt-in LEAN shape does not. The demo's release shape carries the debugger like
    ; any other game: it rides the engine.* registry filter, no exclusion. AS `ifdef`
    ; tests DEFINEDNESS, not value, so the axis is push-or-omit.
    ifdef __MDDBG__
    include "engine/debug/debugger.asm"
    endif

    ; EquSym carrier — see games/sonic4/game_root.asm for the full rationale. Since the
    ; crash-report ruling the RELEASE shape normally has a section again (the __MDDBG__
    ; include opens one); the carrier stays as the belt-and-braces for the LEAN shape,
    ; where the include is gated out and this single zero-byte equate is what forces open
    ; the carrier section attach_guarded_equ_exports needs to re-export the harvested
    ; engine-constant EquSyms (HW_*, …) to the `.emp` link. Byte-neutral in every shape.
__Aeon_AS_Carrier:  equ 0

    END
