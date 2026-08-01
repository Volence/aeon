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
    ; Sound constants are authored in engine/sound/sound_constants.emp (the sound
    ; contract's single authority); the residual AS reads none of its symbols.
    include "engine/macros.asm"
    ; The §4.6 parallax authoring vocabulary is engine/level/parallax_dsl.emp (conv-g);
    ; the config data is games/sonic4/data/parallax/configs.emp. Both are native.
    include "engine/sound/sound_bank.inc"
    gameConfigIncludes
    ; Engine RAM is authored in engine/ram.emp (item #7b) — the `.emp` region form.
    ; Its `pub vars` labels are the joint-link RAM authority; the residual AS reads
    ; the addresses it needs eagerly (demo_state writes, `phase Engine_RAM_End`) via
    ; the harvested value defines (native.rs harvest_engine_ram_addresses).
    gameRamIncludes
    include "engine/debug/debugger.asm"

    org 0
    include "engine/system/header.inc"
    ; The 64-entry vector table ($000-$0FF) is native (engine/system/vectors.emp),
    ; placed by the sigil map at base 0. The region is FIXED SIZE (256 bytes, pure
    ; data), so the AS residual resumes at org $100 — the header lands exactly
    ; where vectors.asm's 64 dc.l would leave it (the boundary is fixed).
    org     $100
    gameHeader

; -----------------------------------------------
; Engine code
; -----------------------------------------------
__BUDGET_ENGINE:
    ; EntryPoint..GameLoop entry (boot): native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $3AC
    else
        org     $3A8
    endif
    include "engine/system/boot_data.asm"
    ; VDP_Shadow_Init/Flush_VDP_Shadow: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $1CD4
    else
        org     $1C52
    endif
    ; Init_DMA_Queue/QueueDMA_*/Process_DMA_*: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $1FDA
    else
        org     $1F54
    endif
    ; Init_SpriteTable/BuildStaticDMA/PlaneMapToVRAM: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $2232
    else
        org     $21AC
    endif
    ; VBlank_Handler/VInt_Level/VInt_Lag/VSync_Wait: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $236A
    else
        org     $22DC
    endif
    ; HBlank_Install/HBlank_Uninstall: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $23B2
    else
        org     $2324
    endif
    ; Read_Controllers: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $2428
    else
        org     $239A
    endif
    ; GameLoop/GameState_Idle: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $243A
    else
        org     $23AC
    endif
    ; S4LZ_DecompressDict/S4LZ_Decompress are native (engine/compression/
    ; s4lz_decompress.emp, sigil-map-pinned at the per-shape reference address).
    ; The AS residual resumes past the native region. These sonic4-shape orgs are
    ; used directly by the canonical sonic4 build; the off-canonical chainer
    ; (demo/Config) derives placement from the frozen listing and ignores them.
    ifdef __DEBUG__
        org     $263A
    else
        org     $24A4
    endif
    ; ZX0_Decompress is native (engine/compression/zx0_decompress.emp,
    ; sigil-map-pinned). Same resume-org contract as s4lz above.
    ifdef __DEBUG__
        org     $2692
    else
        org     $24FC
    endif
    ; GetSineCosine/Sine_Table are native (engine/system/math.emp,
    ; sigil-map-pinned at the per-shape reference address). The AS residual
    ; resumes past the native region. These sonic4-shape orgs are used directly
    ; by the canonical sonic4 build; the off-canonical chainer (demo/Config)
    ; derives placement from the frozen listing and ignores them.
    ifdef __DEBUG__
        org     $292A
    else
        org     $2794
    endif
    ; Perform_DPLC/Perform_DPLC_Deferrable: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $29CE
    else
        org     $2838
    endif
    ; InitObjectRAM..ObjectMove*: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $30FA
    else
        org     $2B1C
    endif
    ; InitSpriteSystem..InsertSpriteMasks: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $351A
    else
        org     $2F3C
    endif
    ; AnimateSprite/RefreshSpritePieceCount: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $37C2
    else
        org     $30C6
    endif
    ; TouchResponse: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $39CA
    else
        org     $32C6
    endif
    ; RingBuffer_*/DrawRings/RingCollision: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $3BDE
    else
        org     $347E
    endif
    ; entity_window Collected_*/EntityWindow_*: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $4906
    else
        org     $3D38
    endif
    ; CreateChild_*/CreateEffect_*/DeleteChildren: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $4CE0
    else
        org     $4008
    endif
    ; Load_Object/Load_ObjectList: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $4D62
    else
        org     $408A
    endif
    ; Plane_Buffer_Reset..VInt_DrawLevel: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $503C
    else
        org     $4364
    endif
    ; Tile_Cache_GetTile..TileCache_Reinit: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $5E1C
    else
        org     $5084
    endif
    ; Collision_GetType: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $5E40
    else
        org     $50A8
    endif
    gameEngineBlockIncludes
    ; Section_Init..Section_UpdateColumns: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $6718
    else
        org     $5980
    endif
    ; Camera_Init/Camera_Update: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $687C
    else
        org     $5AE4
    endif
    ; Parallax pipeline (Parallax_Init..Fill_PerCell): native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $6DF2
    else
        org     $605A
    endif
    ; Art_Decompress/Level_LoadArt: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $6EA0
    else
        org     $60BE
    endif
    ; BG_Init: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $6F4E
    else
        org     $616C
    endif
    ; BgAnim_Init/BgAnim_Update: native (.emp), sigil-map-pinned; the AS residual resumes past it.
    ; INERT: the chainer derives every target's placement from its frozen table +
    ; live sizes and ignores these orgs (deletion rides the residual-split capstone).
    ifdef __DEBUG__
        org     $70A6
    else
        org     $620A
    endif
    ; CompressionSelfTest is native (engine/debug/compression_selftest.emp) — a
    ; DEBUG-ONLY region: the plain shape emits nothing, so placement stays at the
    ; previous region's resume org (no plain arm). The generated golden-vector data
    ; (CSelf_*/CSELF_*, tools/gen_compression_vectors.py) stays AS-side here — the
    ; .emp consumes those symbols cross-seam at link. The org is a sonic4-shape
    ; address; the off-canonical frozen-table chainer ignores it.
    ifdef __DEBUG__
        org     $72BE
        include "engine/debug/generated/vectors.asm"
    endif
    ifdef SOUND_DRIVER_ENABLED
        ; The Sound_* API procs are native (engine/sound/sound_api.emp), pinned by
        ; the sigil map at the per-shape reference address; the AS residual resumes
        ; at the region end. The .emp keeps the slot ADDRESSES AS-owned (extern-equ
        ; sums over sound_constants.asm) and mirrors only immediate-position values.
        ; The org values are sonic4-shape; the off-canonical chainer ignores them.
        ifdef __DEBUG__
        org     $80E4
        else
        org     $6414
        endif
    endif
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        ifdef SIGIL_EMP_SOUND_DEBUG
        ; Sound_DebugMirror is native (engine/debug/sound_debug.emp), placed by the
        ; sigil map (Config-A only: __DEBUG__ + SOUND_DRIVER_ENABLED + SOUND_DBG_MIRROR).
        ; org resumes at the region end. Canonically this region emits ZERO bytes
        ; (SOUND_DBG_MIRROR off in every shipped build), so the canonical shapes place
        ; nothing here (the gate is set only by the sigil Config-A whole-ROM build) —
        ; byte-neutral. This org is the CONFIG-A sonic4-shape address.
        org     $827C
        endif
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

    ; The 64KB object-bank overflow guard is now a MAP-owned check: sigil's
    ; `object_bank` region (sigil.map.toml, lma_base $10000 size $10000) is checked
    ; against the __BUDGET_DATA cursor at link time (native::check_object_bank_budget).
    ; The __BUDGET_OBJBANK/__BUDGET_DATA labels bracket the bank for that check.

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

    ; The exception-vector stubs (BusError..) and the MD Debugger blob are native
    ; (engine/debug/error_handler.emp, ErrorHandlerBlob), placed by the sigil map in
    ; every build. That module also owns the MDDBG__* `pub equ` table (each entry
    ; ErrorHandlerBlob+off, link-folded per shape AND per game); the AS-side vendored
    ; debugger.asm resolves those names as link externs off that base.
    ;
    ; The org resumes AS-residual placement at EndOfRom (error_handler emits nothing
    ; after the region, so the resume address IS EndOfRom). Its value is sonic4-shape;
    ; the off-canonical frozen-table chainer relocates the resumed section to that
    ; game's EndOfRom.
    ifdef __DEBUG__
        org     $5F65A                      ; EndOfRom (sonic4 debug) = BusError($5E5AA) + region $10B0
    else
        org     $5DB60                      ; EndOfRom (sonic4 plain) = BusError($5CAB0) + region $10B0
    endif

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
