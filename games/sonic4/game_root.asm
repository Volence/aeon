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
    ; GATED ON __MDDBG__ (the crash-report axis, owner-ruled 2026-08-04): the include is
    ; valid exactly when error_handler.emp is placed, because the MDDBG__* link externs
    ; its equ table derives off (MDDBG__Debugger_AddressRegisters, …,
    ; MDDBG__Str_OffsetLocation_24bit) are that module's `pub equ`s. Including it without
    ; the island makes those equs unresolvable — a hard link error.
    ; __MDDBG__ is pushed by the native driver when `profile.debug || profile.crash_report`,
    ; i.e. in the DEBUG and RELEASE shapes but NOT in the opt-in LEAN shape
    ; (`sigil build --native --lean`, CRASH_REPORT=0). It is a separate define from
    ; __DEBUG__ — __DEBUG__ still means exactly "debug shape" (asserts, hotkeys, selftest,
    ; boot autoplay). AS `ifdef` tests DEFINEDNESS, not value, so the axis is push-or-omit:
    ; a `__MDDBG__ = 0` would still take this arm.
    ifdef __MDDBG__
    include "engine/debug/debugger.asm"
    endif

    ; EquSym carrier (review item 29 part 4). The residual AS root's real job now is
    ; to re-export the harvested `.emp`-owned engine constants (HW_*, …) as link
    ; EquSyms, so the `.emp` modules that reference them as BARE link symbols (e.g.
    ; boot.emp's `tst.l HW_PORT_A_CTRL_FULL`) resolve at the joint link. That export
    ; (attach_guarded_equ_exports) only runs when the assembled module has ≥1 section.
    ; Since the crash-report ruling the RELEASE shape normally HAS a section again (the
    ; __MDDBG__ debugger.asm include opens one, as DEBUG always did) — but the carrier
    ; stays as the belt-and-braces for the LEAN shape, the one shape where the include is
    ; gated out and nothing else would open a section. It emits no bytes and is filtered
    ; from the deb2 symbol appendix — byte-neutral in every shape.
__Aeon_AS_Carrier:  equ 0

    END
