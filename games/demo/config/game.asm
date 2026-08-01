; Aeon engine demo — game contract declarations consumed by the engine.
; This is the minimal manifest: the engine-boots-without-Sonic proof.

; --- ROM header fields ---
; The $100-$1FF ROM header is authored in games/demo/config/header.emp (Parcel K4):
; the game-declared strings are typed `[u8; N]` data there (the type is the exact-
; width guard), placed natively right after the vectors.

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
