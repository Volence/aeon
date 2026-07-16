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
;   BgAnim_Table                  — BG tile-band animation table (part of
;                                   gameDataIncludes; engine/level/bg_anim.asm
;                                   reads it at runtime). dc.w 0 (band_count)
;                                   disables the system for games with no BG
;                                   animation.
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
;   gameStatesIncludes       — game state includes (outside the sound
;                              conditional — a game must boot without sound)
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
    ifndef SIGIL_EMP_VDP_INIT
        include "engine/system/vdp_init.asm"
    else
        ; sigil mixed build: VDP_Shadow_Init/Flush_VDP_Shadow come from
        ; engine/system/vdp_init.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $1CDE
      else
        org     $1C5C
      endif
    endif
    include "engine/system/dma_queue.asm"
    include "engine/system/buffers.asm"
    include "engine/system/vblank.asm"
    ifndef SIGIL_EMP_HBLANK
        include "engine/system/hblank.asm"
    else
        ; sigil mixed build: HBlank_Dispatch/HBlank_Null come from
        ; engine/system/hblank.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $232E
      else
        org     $22A0
      endif
    endif
    ifndef SIGIL_EMP_CONTROLLERS
        include "engine/system/controllers.asm"
    else
        ; sigil mixed build: Read_Controllers comes from
        ; engine/system/controllers.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $23A4
      else
        org     $2316
      endif
    endif
    ifndef SIGIL_EMP_GAME_LOOP
        include "engine/system/game_loop.asm"
    else
        ; sigil mixed build: GameLoop/GameState_Idle come from
        ; engine/system/game_loop.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; The .emp takes -D SOUND_DRIVER_ENABLED / -D SOUND_DEBUG_HOTKEYS
        ; (0|1) and mirrors BOTH conditionals, including sonic4's
        ; gameDebugTick expansion (see games/sonic4/config/game.asm).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $23B6
      else
        org     $2328
      endif
    endif
    include "engine/compression/s4lz_decompress.asm"
    include "engine/compression/zx0_decompress.asm"
    ifndef SIGIL_EMP_MATH
        include "engine/system/math.asm"
    else
        ; sigil mixed build: GetSineCosine/Sine_Table come from
        ; engine/system/math.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $28A6
      else
        org     $2714
      endif
    endif
    ifndef SIGIL_EMP_DPLC
        include "engine/objects/dplc.asm"
    else
        ; sigil mixed build: Perform_DPLC/Perform_DPLC_Deferrable come from
        ; engine/objects/dplc.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $294A
      else
        org     $27B8
      endif
    endif
    ifndef SIGIL_EMP_CORE
        include "engine/objects/core.asm"
    else
        ; sigil mixed build: InitObjectRAM/AllocDynamic/AllocEffect/
        ; DeleteObject/RunObjects/RunObjects_Frozen/ObjectMove* come from
        ; engine/objects/core.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: core is shape-dependent-LENGTH (the __DEBUG__
        ; Debug_AssertObjLoop proc + the two ifdebug call sites exist only in
        ; the debug shape), so the two resume orgs differ by more than the
        ; usual base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $3080
      else
        org     $2AA6
      endif
    endif
    ifndef SIGIL_EMP_SPRITES
        include "engine/objects/sprites.asm"
    else
        ; sigil mixed build: InitSpriteSystem/Draw_Sprite/Render_Sprites/
        ; Emit_ObjectPieces/InsertSpriteMasks come from
        ; engine/objects/sprites.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; sprites is shape-INDEPENDENT length ($420 both shapes — no
        ; __DEBUG__ code), so the two resume orgs differ only by the core
        ; base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $34A0
      else
        org     $2EC6
      endif
    endif
    ifndef SIGIL_EMP_ANIMATE
        include "engine/objects/animate.asm"
    else
        ; sigil mixed build: AnimateSprite/RefreshSpritePieceCount come from
        ; engine/objects/animate.emp,
        ; pinned by the sigil map at the per-shape reference address. Resume
        ; placement at the region end (see sigil-harness golden/PROVENANCE.md;
        ; re-pin on re-baseline). The AF_* control-code equs the script data
        ; files read live in engine/constants.asm, NOT here, so they survive
        ; this gate.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $3748
      else
        org     $3050
      endif
    endif
    ifndef SIGIL_EMP_COLLISION
        include "engine/objects/collision.asm"
    else
        ; sigil mixed build: TouchResponse comes from
        ; engine/objects/collision.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $3950
      else
        org     $3250
      endif
    endif
    ifndef SIGIL_EMP_RINGS
        include "engine/objects/rings.asm"
    else
        ; sigil mixed build: the RingBuffer_*/DrawRings/RingCollision procs
        ; come from engine/objects/rings.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: rings is the campaign's FIRST shape-dependent-LENGTH region
        ; (the __DEBUG__ assert block exists only in the debug shape), so the
        ; two resume orgs differ by more than the usual base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $3B64
      else
        org     $3408
      endif
    endif
    ifndef SIGIL_EMP_ENTITY_WINDOW
        include "engine/objects/entity_window.asm"
    else
        ; sigil mixed build: entity_window's Collected_*/Killed_*/EntityLoaded_*/
        ; EntityWindow_* procs come from engine/objects/entity_window.emp, pinned
        ; by the sigil map at the per-shape reference address. Resume placement at
        ; the region end (see sigil-harness golden/PROVENANCE.md; re-pin on
        ; re-baseline). Shape-dependent LENGTH (the 11 asserts + 3 __DEBUG__
        ; blocks), so the two resume orgs differ by more than the base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $48A4
      else
        org     $3CDA
      endif
    endif
    include "engine/objects/children.asm"
    ifndef SIGIL_EMP_LOAD_OBJECT
        include "engine/objects/load_object.asm"
    else
        ; sigil mixed build: Load_Object / Load_ObjectList come from
        ; engine/objects/load_object.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; Shape-INVARIANT length (no asserts / no __DEBUG__) — the two resume
        ; orgs differ only by the upstream base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $4C34
      else
        org     $406A
      endif
    endif
    ifndef SIGIL_EMP_PLANE_BUFFER
        include "engine/level/plane_buffer.asm"
    else
        ; sigil mixed build: Plane_Buffer_Reset..VInt_DrawLevel come from
        ; engine/level/plane_buffer.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (Tile_Cache_GetTile).
        ; Shape-INVARIANT length ($29C both shapes; no asserts / no __DEBUG__) — the
        ; two resume orgs differ only by the upstream base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define must
        ; never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $4ED0
      else
        org     $4306
      endif
    endif
    ifndef SIGIL_EMP_TILE_CACHE
        include "engine/level/tile_cache.asm"
    else
        ; sigil mixed build: Tile_Cache_GetTile..TileCache_Reinit come from
        ; engine/level/tile_cache.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (collision_lookup's
        ; Collision_GetType — the SIGIL_EMP_COLLISION_LOOKUP block below). Shape-
        ; VARYING length ($B54 plain / $C14 debug — the .raw_direct assert block;
        ; unified-prefetch grew tile_cache: +$10 (H5 slots), +$14C (H1/H2/H3/H4 prefetch
        ; tail), +$C (H6 base-lea hoist), +$2A (interim H4 VBlank fix + Cache_Prev_Cam_X
        ; init), +$2C (H4 reworked to the Frame_Counter-delta trailing-lag gate) over the
        ; Wave-2 (ii) $996/$A56).
        ; NOTE: these org values are sonic4-shape addresses — the gate define must
        ; never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $5AE4
      else
        org     $4E5A
      endif
    endif
    ifndef SIGIL_EMP_COLLISION_LOOKUP
        include "engine/level/collision_lookup.asm"
    else
        ; sigil mixed build: Collision_GetType comes from
        ; engine/level/collision_lookup.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $5B08
      else
        org     $4E7E
      endif
    endif
    gameEngineBlockIncludes
    ifndef SIGIL_EMP_SECTION
        include "engine/level/section.asm"
    else
        ; sigil mixed build: Section_Init..Section_UpdateColumns come from
        ; engine/level/section.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (camera.asm's
        ; Camera_Init). Shape-INVARIANT length ($3EA both shapes) — the two
        ; resume orgs differ only by the upstream base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $63E0
      else
        org     $5756
      endif
    endif
    include "engine/level/camera.asm"
    include "engine/level/parallax.asm"
    include "engine/level/load_art.asm"
    include "engine/level/bg.asm"
    include "engine/level/bg_anim.asm"
    include "engine/debug/compression_selftest.asm"
    ifdef SOUND_DRIVER_ENABLED
      ifndef SIGIL_EMP_SOUND_API
        include "engine/sound/sound_api.asm"
      else
        ; sigil mixed build: the Sound_* API procs come from
        ; engine/sound/sound_api.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; The .emp keeps the slot ADDRESSES AS-owned (extern-equ sums over
        ; sound_constants.asm) and mirrors only immediate-position values
        ; (kill-list row 10).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
        ifdef __DEBUG__
        org     $7BC0
        else
        org     $61A6
        endif
      endif
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

; --- game states (outside the sound conditional — a game must boot without sound) ---
    gameStatesIncludes

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
