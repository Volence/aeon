; Aeon engine demo — main assembly file (game manifest)
; The engine owns the ROM layout (engine/engine.inc). This file supplies the
; minimal game-specific includes via the contract macros it requires — the
; "start here" template proving the engine boots without Sonic.
;
; NOTE: builds sound-off via build.conf (SOUND_DRIVER_ENABLED defaults to 0
; here) — a demo sound bank via the soundBankHead contract (engine/sound/
; sound_bank.inc) is TODO for whoever grows this into a real game.

; -----------------------------------------------
; Assembly options
; -----------------------------------------------
PAD_TO_POWER_OF_TWO     = 1

gameConfigIncludes macro {GLOBALSYMBOLS}
    ; Game constants are authored in games/demo/config/constants.emp (Parcel
    ; H-demo) — the `.emp` module `games.demo.constants`, harvested (native.rs
    ; harvest_game_constants) into guarded AS `-D` defines + link EquSyms, so this
    ; residual AS + the game-agnostic engine `.emp` drift guards resolve them.
    include "games/demo/config/game.asm"
    endm

gameRamIncludes macro {GLOBALSYMBOLS}
    ; Game RAM is authored in games/demo/config/ram.emp (item #7c) — the `.emp`
    ; region form (`game_ram @ after(upper_ram)`), defining Game_RAM_End. No eager
    ; AS reference to game RAM in the demo, so nothing to include here.
    endm

gameEngineBlockIncludes macro {GLOBALSYMBOLS}
    endm

gameObjectBankIncludes macro {GLOBALSYMBOLS}
    ; DemoBox_Main is native (games/demo/objects/demo_box.emp, module
    ; games.demo.demo_box), placed by the sigil chainer inside the object code bank
    ; (org $10000, ObjCodeBase). Shape-invariant window; ONE org, resuming on the
    ; next label (ObjDef_DemoBox). Demo-shape address; the off-canonical chainer
    ; relocates.
    org     $10006
    endm

gameDataIncludes macro {GLOBALSYMBOLS}
    ; ObjDef_DemoBox .. BgAnim_Table are native (games/demo/data/demo_data.emp,
    ; module games.demo.data.demo_data). Shape-invariant window; ONE org, resuming
    ; on the game-states region head (GameState_Demo_Init).
    org     $10100
    endm

gameSoundDataIncludes macro {GLOBALSYMBOLS}
    endm

gameStatesIncludes macro {GLOBALSYMBOLS}
    ; GameState_Demo_Init / GameState_Demo are native (games/demo/demo_state.emp,
    ; module games.demo.demo_state). Shape-invariant window; ONE org, resuming on
    ; NullInterrupt (engine.inc, right after this macro).
    org     $10172
    endm

    include "engine/engine.inc"
    END
