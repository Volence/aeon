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
        org     $1CD6
      else
        org     $1C54
      endif
    endif
    ifndef SIGIL_EMP_DMA_QUEUE
        include "engine/system/dma_queue.asm"
    else
        ; sigil mixed build: the 3-priority DMA queue (Init_DMA_Queue,
        ; QueueDMA_* + the shared transfer core, Process_DMA_*,
        ; Drain_Budgeted_Queue) comes from engine/system/dma_queue.emp, pinned
        ; by the sigil map at the per-shape reference address. Resume placement
        ; at the region end (buffers.asm's Init_SpriteTable). Shape-DEPENDENT
        ; length ($302 plain / $306 debug — the debug surplus is the
        ; overflow-count bump in the enqueue's full-queue arm), so the two
        ; resume orgs differ by more than the base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $1FDC
      else
        org     $1F56
      endif
    endif
    ifndef SIGIL_EMP_BUFFERS
        include "engine/system/buffers.asm"
    else
        ; sigil mixed build: Init_SpriteTable/BuildStaticDMA/PlaneMapToVRAM/
        ; Enqueue_Dirty_Buffers come from engine/system/buffers.emp, pinned by
        ; the sigil map at the per-shape reference address. Resume placement
        ; at the region end (vblank.asm's VBlank_Handler). Shape-INVARIANT
        ; length (no ifdef arms), so the two orgs differ only by the base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $2234
      else
        org     $21AE
      endif
    endif
    ifndef SIGIL_EMP_VBLANK
        include "engine/system/vblank.asm"
    else
        ; sigil mixed build: VBlank_Handler/VInt_Level/VInt_Lag/VSync_Wait come
        ; from engine/system/vblank.emp, pinned by the sigil map at the
        ; per-shape reference address. Resume placement at the region end
        ; (hblank.asm's HBlank_Install). Shape-DEPENDENT length ($130 plain /
        ; $138 debug — the debug surplus is VInt_Lag's lag-frame counter bump
        ; + VSync_Wait's DMA-bytes clear), so the two resume orgs differ by
        ; more than the base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $236C
      else
        org     $22DE
      endif
    endif
    ifndef SIGIL_EMP_HBLANK
        include "engine/system/hblank.asm"
    else
        ; sigil mixed build: HBlank_Install/HBlank_Uninstall come from
        ; engine/system/hblank.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $23B4
      else
        org     $2326
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
        org     $242A
      else
        org     $239C
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
        org     $243C
      else
        org     $23AE
      endif
    endif
    ifndef SIGIL_EMP_S4LZ
        include "engine/compression/s4lz_decompress.asm"
    else
        ; sigil mixed build: S4LZ_DecompressDict/S4LZ_Decompress come from
        ; engine/compression/s4lz_decompress.emp, pinned by the sigil map at
        ; the per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $263C
      else
        org     $24AA
      endif
    endif
    ifndef SIGIL_EMP_ZX0
        include "engine/compression/zx0_decompress.asm"
    else
        ; sigil mixed build: ZX0_Decompress comes from
        ; engine/compression/zx0_decompress.emp, pinned by the sigil map at
        ; the per-shape reference address. Resume placement at the region end
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $2694
      else
        org     $2502
      endif
    endif
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
        org     $292C
      else
        org     $279A
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
        org     $29D0
      else
        org     $283E
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
        org     $30FC
      else
        org     $2B22
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
        org     $351C
      else
        org     $2F42
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
        org     $37C4
      else
        org     $30CC
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
        org     $39CC
      else
        org     $32CC
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
        org     $3BE0
      else
        org     $3484
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
        org     $4908
      else
        org     $3D3E
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
        org     $4C98
      else
        org     $40CE
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
        org     $4F72
      else
        org     $43A8
      endif
    endif
    ifndef SIGIL_EMP_TILE_CACHE
        include "engine/level/tile_cache.asm"
    else
        ; sigil mixed build: Tile_Cache_GetTile..TileCache_Reinit come from
        ; engine/level/tile_cache.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (collision_lookup's
        ; Collision_GetType — the SIGIL_EMP_COLLISION_LOOKUP block below). Shape-
        ; VARYING length ($D04 plain / $DC4 debug — the .raw_direct assert block;
        ; unified-prefetch grew tile_cache: +$10 (H5 slots), +$14C (H1/H2/H3/H4 prefetch
        ; tail), +$C (H6 base-lea hoist), +$2A (interim H4 VBlank fix + Cache_Prev_Cam_X
        ; init), +$2C (H4 reworked to the Frame_Counter-delta trailing-lag gate) over the
        ; Wave-2 (ii) $996/$A56; +$88 (pass-2 1.1a FillRow nametable segment restructure) + $56 (1.1b FillRow collision segment restructure)).
        ; The +$22 for pass-2 1.2 (Draw_TileRow_FromCache segment restructure) lands
        ; in plane_buffer, not tile_cache, but slides every resume org below by +$22.
        ; +$42 for pass-2 1.3 (CopyBlockColumn wrap-split) lands INSIDE tile_cache
        ; (grows this region's len) and slides every resume org below by +$42 too.
        ; NOTE: these org values are sonic4-shape addresses — the gate define must
        ; never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $5D52
      else
        org     $50C8
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
        org     $5D76
      else
        org     $50EC
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
        org     $664E
      else
        org     $59C4
      endif
    endif
    ifndef SIGIL_EMP_CAMERA
        include "engine/level/camera.asm"
    else
        ; sigil mixed build: Camera_Init/Camera_Update come from
        ; engine/level/camera.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (parallax.asm's
        ; Parallax_Init). Shape-INVARIANT length ($164 both shapes — no
        ; __DEBUG__ code, no asserts) — the two resume orgs differ only by the
        ; upstream base slide. The .emp takes -D GAME_CAMERA_JUMP_LOCK (0|1)
        ; and mirrors the conditional (see games/*/config/game.asm).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $67B2
      else
        org     $5B28
      endif
    endif
    ifndef SIGIL_EMP_PARALLAX
        include "engine/level/parallax.asm"
    else
        ; sigil mixed build: the §4.6 parallax pipeline (Parallax_Init ..
        ; Parallax_Fill_PerCell) comes from engine/level/parallax.emp, pinned by
        ; the sigil map at the per-shape reference address. Resume placement at
        ; the region end (load_art's Art_Decompress; see sigil-harness
        ; golden/PROVENANCE.md; re-pin on re-baseline).
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $6D28
      else
        org     $609E
      endif
    endif
    ifndef SIGIL_EMP_LOAD_ART
        include "engine/level/load_art.asm"
    else
        ; sigil mixed build: Art_Decompress/Level_LoadArt come from
        ; engine/level/load_art.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (bg.asm's
        ; BG_Init). Shape-DEPENDENT length ($68 plain / $B2 debug — the debug
        ; surplus is the .drop_page RaiseError expansion; the release arm is
        ; the 6-byte drain-and-retry), so the two resume orgs differ by more
        ; than the base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $6DD6
      else
        org     $6102
      endif
    endif
    ifndef SIGIL_EMP_BG
        include "engine/level/bg.asm"
    else
        ; sigil mixed build: BG_Init comes from engine/level/bg.emp, pinned by
        ; the sigil map at the per-shape reference address. Resume placement at
        ; the region end (bg_anim.asm's BgAnim_Init). Shape-INVARIANT length
        ; ($AE both shapes — no __DEBUG__ code, no asserts) — the two resume
        ; orgs differ only by the upstream base slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $6E84
      else
        org     $61B0
      endif
    endif
    ifndef SIGIL_EMP_BG_ANIM
        include "engine/level/bg_anim.asm"
    else
        ; sigil mixed build: BgAnim_Init/BgAnim_Update come from
        ; engine/level/bg_anim.emp, pinned by the sigil map at the per-shape
        ; reference address. Resume placement at the region end (the next
        ; placement is compression_selftest.asm, whose only label is
        ; __DEBUG__-gated — the region carries a literal length in repin.toml,
        ; the sound_api precedent). Shape-DEPENDENT length ($9E plain / $100
        ; debug — the band-count assert + its message blob exist only in the
        ; debug shape), so the two resume orgs differ by more than the base
        ; slide.
        ; NOTE: these org values are sonic4-shape addresses — the gate define
        ; must never be set for other games (demo builds take the include).
      ifdef __DEBUG__
        org     $6FDC
      else
        org     $624E
      endif
    endif
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
        org     $802A
        else
        org     $6458
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
