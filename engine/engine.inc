; Aeon engine — engine.inc
; -----------------------------------------------
; This file owns the ROM layout (org 0 header/vectors, engine code block,
; object code bank scaffold, data region, sound-data region, epilogue). A
; game's main.asm is a thin manifest: it defines the macros below (each may
; be empty, but ALL must be declared with {GLOBALSYMBOLS} — see MACRO LAW),
; sets PAD_TO_POWER_OF_TWO, then `include`s this file and ends with END.
;
; ---------------------------------------------------------------
; GAME CONTRACT — symbols the game's included files must define
; ---------------------------------------------------------------
; Required symbols:
;   Game_Entry                    — game entry point (called from boot)
;   GAME_ENTRY_ID                 — initial game-state id
;   GAME_CAMERA_JUMP_LOCK         — camera jump-lock constant
;   GAME_* header strings         — per engine/system/header.inc (domestic/
;                                   overseas names, ROM type, etc.)
;   VRAM_RING_PLACEHOLDER         — ring art VRAM slot
;   Ring/collected capacity constants:
;     MAX_RING_BUFFER, RING_BUFFER_ENTRY_SIZE, RING_WIDTH,
;     COLLECTED_WINDOW_SLOTS, COLLECTED_SLOT_SIZE,
;     COLLECTED_PARK_SLOTS, COLLECTED_PARK_ENTRY_SIZE
;   With SOUND_DRIVER_ENABLED, additionally:
;     SFXID_REV_LOOP, SFXID_RING_LEFT, SFXID_RING_RIGHT
;     SND_ENGINE_TABLE_BANK
;     SndDefaultPitchTable, SfxBlobWinTab (via soundBankHead)
;     SongTable, SfxTable + song data
;
; Required macros (ALL must be declared `name macro {GLOBALSYMBOLS}` — a
; macro-included file's labels are macro-local without it, breaking both
; references and the symbol table; may be empty bodies):
;   gameConfigIncludes       — game config includes (constants/ids/game.asm)
;   gameRamIncludes          — game RAM includes
;   gameEngineBlockIncludes  — game files that must live in the engine code
;                              block (e.g. player_sensors.asm, game_debug.asm)
;   gameObjectBankIncludes   — game files that must live in the object code
;                              bank (player state files, test/path objects)
;   gameDataIncludes         — game data region (parallax, objdefs, entity/act
;                              data, mappings, animations, collision, character
;                              art, test states)
;   gameSoundDataIncludes    — game sound-data region contents (DAC samples,
;                              MT bank, songs, sfx) — WITHOUT the outer
;                              `ifdef SOUND_DRIVER_ENABLED` (this file
;                              provides that)
;   gameBootHook             — called during boot (defined in the game's
;                              contract file, pulled in by gameConfigIncludes)
;   gameDebugTick            — called during the debug tick (ditto)
;
; PAD_TO_POWER_OF_TWO must be defined by the game manifest BEFORE including
; this file.
; ---------------------------------------------------------------

    cpu 68000
    padding off
    supmode on

; -----------------------------------------------
; Definitions (no ROM output)
; -----------------------------------------------
    include "engine/constants.asm"
    include "engine/sound_constants.asm"
    include "engine/structs.asm"
    include "engine/macros.asm"
    include "engine/parallax_macros.inc"
    include "engine/sound/sound_bank.inc"
    gameConfigIncludes
    include "engine/ram.asm"
    gameRamIncludes
    include "engine/debug/debugger.asm"

    org 0
    include "engine/system/header.inc"
    include "engine/system/vectors.asm"
    gameHeader

; -----------------------------------------------
; Engine code
; -----------------------------------------------
__BUDGET_ENGINE:
    include "engine/system/boot.asm"
    include "engine/system/vdp_init.asm"
    include "engine/system/dma_queue.asm"
    include "engine/system/buffers.asm"
    include "engine/system/vblank.asm"
    include "engine/system/hblank.asm"
    include "engine/system/controllers.asm"
    include "engine/system/game_loop.asm"
    include "engine/compression/s4lz_decompress.asm"
    include "engine/compression/zx0_decompress.asm"
    include "engine/system/math.asm"
    include "engine/objects/dplc.asm"
    include "engine/objects/core.asm"
    include "engine/objects/sprites.asm"
    include "engine/objects/animate.asm"
    include "engine/objects/collision.asm"
    include "engine/objects/rings.asm"
    include "engine/objects/entity_window.asm"
    include "engine/objects/children.asm"
    include "engine/objects/load_object.asm"
    include "engine/level/plane_buffer.asm"
    include "engine/level/tile_cache.asm"
    include "engine/level/collision_lookup.asm"
    gameEngineBlockIncludes
    include "engine/level/section.asm"
    include "engine/level/camera.asm"
    include "engine/level/parallax.asm"
    include "engine/level/load_art.asm"
    include "engine/level/bg.asm"
    include "engine/level/bg_anim.asm"
    include "engine/debug/compression_selftest.asm"
    ifdef SOUND_DRIVER_ENABLED
        include "engine/sound/sound_api.asm"
    endif
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        include "engine/debug/sound_debug.asm"
      endif
    endif

; -----------------------------------------------
; Object code bank
; All object routines must live within this 64KB block.
; objroutine() computes offsets from ObjCodeBase.
; -----------------------------------------------
    org $10000
ObjCodeBase:
    rts                         ; offset 0 = empty slot safety net
__BUDGET_OBJBANK:

    gameObjectBankIncludes

    if * > $20000
      error "Object code bank overflows 64KB by \{*-$20000} bytes"
    endif

; -----------------------------------------------
; Data (outside object code bank — addressed directly, not via objroutine)
; -----------------------------------------------
__BUDGET_DATA:
    gameDataIncludes

; -----------------------------------------------
; DAC sample data (§1B — ROM-streamed via Z80 bank window)
; Bank-aligned (align $8000); the Z80 reads it through its $8000 window.
; -----------------------------------------------
    ifdef SOUND_DRIVER_ENABLED
        gameSoundDataIncludes
    endif

; -----------------------------------------------
; Temporary stubs (replaced in later tasks)
; -----------------------------------------------
NullInterrupt:
    rte

    include "engine/debug/error_handler.asm"

; -----------------------------------------------
; End of ROM
; -----------------------------------------------
EndOfRom:
    align 2

    if (EndOfRom & 1) <> 0
      error "ROM size is odd"
    endif

    if EndOfRom > $3FFFFF
      error "ROM exceeds 4MB without banking"
    endif

; -----------------------------------------------
; Compile-time validation
; -----------------------------------------------
    if PLANE_H_CELLS * PLANE_V_CELLS > 4096
      error "Plane exceeds 8KB"
    endif
