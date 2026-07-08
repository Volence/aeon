; Aeon engine demo — game contract declarations consumed by the engine.
; This is the minimal manifest: the engine-boots-without-Sonic proof.

; --- ROM header fields (exact widths asserted by gameHeader) ---
GAME_CONSOLE    equ "SEGA GENESIS    "
GAME_COPYRIGHT  equ "(C)     2026.JUL"
GAME_TITLE_DOM  equ "AEON ENGINE DEMO                                "
GAME_TITLE_OVS  equ "AEON ENGINE DEMO                                "
GAME_SERIAL     equ "GM DEMO-000-00"
GAME_IO         equ "J               "
GAME_SRAM       equ "            "
GAME_MEMO       equ "                                                    "
GAME_REGION     equ "JUE             "

; --- engine feature gates ---
GAME_CAMERA_JUMP_LOCK = 0   ; no player/camera jump-lock system in the demo

; --- Boot handoff: the engine boot ends by entering the game here ---
Game_Entry      = GameState_Demo_Init
GAME_ENTRY_ID   = GS_DEMO

; --- gameBootHook — engine boot invokes this after Sound_Init, before the
;     game-state handoff. Empty — the demo has no boot-time hook.
gameBootHook macro {GLOBALSYMBOLS}
    endm

; --- gameDebugTick — engine GameLoop invokes this once per frame after
;     VSync/SFX-drain. Empty — the demo has no debug tick.
gameDebugTick macro {GLOBALSYMBOLS}
    endm
