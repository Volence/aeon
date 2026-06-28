; Sonic 4 Engine — main assembly file
    cpu 68000
    padding off
    supmode on

; -----------------------------------------------
; Assembly options
; -----------------------------------------------
PAD_TO_POWER_OF_TWO     = 1

; -----------------------------------------------
; Definitions (no ROM output)
; -----------------------------------------------
    include "constants.asm"
    include "sound_constants.asm"
    include "structs.asm"
    include "macros.asm"
    include "engine/parallax_macros.inc"
    include "ram.asm"
    include "engine/debug/debugger.asm"

; -----------------------------------------------
; ROM image
; -----------------------------------------------
    org 0

; -----------------------------------------------
; Vector Table ($000000 - $0000FF)
; -----------------------------------------------
__BUDGET_VECTORS:
Vectors:
    dc.l    SYSTEM_STACK                    ; $00: Initial SSP
    dc.l    EntryPoint                      ; $04: Reset PC
    dc.l    BusError                        ; $08: Bus error
    dc.l    AddressError                    ; $0C: Address error
    dc.l    IllegalInstr                    ; $10: Illegal instruction
    dc.l    ZeroDivide                      ; $14: Division by zero
    dc.l    ChkInstr                        ; $18: CHK exception
    dc.l    TrapvInstr                      ; $1C: TRAPV
    dc.l    PrivilegeViol                   ; $20: Privilege violation
    dc.l    Trace                           ; $24: Trace
    dc.l    Line1010Emu                     ; $28: Line 1010
    dc.l    Line1111Emu                     ; $2C: Line 1111
    dc.l    ErrorExcept                     ; $30: Reserved
    dc.l    ErrorExcept                     ; $34: Reserved
    dc.l    ErrorExcept                     ; $38: Reserved
    dc.l    ErrorExcept                     ; $3C: Reserved
    dc.l    ErrorExcept                     ; $40: Reserved
    dc.l    ErrorExcept                     ; $44: Reserved
    dc.l    ErrorExcept                     ; $48: Reserved
    dc.l    ErrorExcept                     ; $4C: Reserved
    dc.l    ErrorExcept                     ; $50: Reserved
    dc.l    ErrorExcept                     ; $54: Reserved
    dc.l    ErrorExcept                     ; $58: Reserved
    dc.l    ErrorExcept                     ; $5C: Reserved
    dc.l    ErrorExcept                     ; $60: Spurious interrupt
    dc.l    NullInterrupt                   ; $64: IRQ1 (external)
    dc.l    NullInterrupt                   ; $68: IRQ2 (external)
    dc.l    NullInterrupt                   ; $6C: IRQ3
    dc.l    HBlank_Dispatch                 ; $70: IRQ4 (HBlank)
    dc.l    NullInterrupt                   ; $74: IRQ5
    dc.l    VBlank_Handler                  ; $78: IRQ6 (VBlank)
    dc.l    NullInterrupt                   ; $7C: IRQ7 (NMI)
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $80-$8C: TRAP 0-3
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $90-$9C: TRAP 4-7
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $A0-$AC: TRAP 8-11
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $B0-$BC: TRAP 12-15
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $C0-$CC: Reserved
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $D0-$DC: Reserved
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $E0-$EC: Reserved
    dc.l    ErrorTrap, ErrorTrap, ErrorTrap, ErrorTrap   ; $F0-$FC: Reserved

; -----------------------------------------------
; ROM Header ($000100 - $0001FF)
; -----------------------------------------------
    dc.b    "SEGA GENESIS    "                          ; $100: Console name (16 bytes)
    dc.b    "(C)     2026.APR"                          ; $110: Copyright (16 bytes)
    dc.b    "SONIC THE HEDGEHOG 4                            "  ; $120: Domestic name (48 bytes)
    dc.b    "SONIC THE HEDGEHOG 4                            "  ; $150: Overseas name (48 bytes)
    dc.b    "GM S4-0001-00 "                            ; $180: Serial (14 bytes)
Checksum:
    dc.w    $0000                                       ; $18E: Checksum (fixheader patches)
    dc.b    "J               "                          ; $190: I/O support (16 bytes)
    dc.l    $00000000                                   ; $1A0: ROM start
    dc.l    EndOfRom-1                                  ; $1A4: ROM end
    dc.l    $00FF0000                                   ; $1A8: RAM start
    dc.l    $00FFFFFF                                   ; $1AC: RAM end
    dc.b    "            "                              ; $1B0: No SRAM (12 bytes)
    dc.b    "                                                    "  ; $1BC: Memo (52 bytes, fills $1BC-$1EF)
    dc.b    "JUE             "                          ; $1F0: Region (16 bytes)

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
    include "games/sonic4/player/player_sensors.asm"
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

    ; Player (§5) — in the object bank: Player_Main dispatches via
    ; objroutine(), which needs the routine within ObjCodeBase+64KB.
    ; (player_sensors.asm stays in the engine block above — it has no
    ; code_addr entry points.)
    ; player_common first — it defines the overlay equates and macros
    ; the state files use; ground/air are reached only via the offset
    ; tables, so order among them is otherwise free.
    include "games/sonic4/player/player_common.asm"
    include "games/sonic4/player/player_ground.asm"
    include "games/sonic4/player/player_air.asm"
    include "games/sonic4/player/player_spindash.asm"
    include "games/sonic4/player/sonic.asm"

    include "games/sonic4/objects/test_static.asm"
    include "games/sonic4/objects/test_animated.asm"
    include "games/sonic4/objects/test_player.asm"
    include "games/sonic4/objects/test_enemy.asm"
    include "games/sonic4/objects/test_solid.asm"
    include "games/sonic4/objects/test_particle.asm"
    include "games/sonic4/objects/test_emitter.asm"
    include "games/sonic4/objects/test_parent.asm"
    include "games/sonic4/objects/test_stress_emitter.asm"
    include "games/sonic4/objects/path_swap.asm"

    if * > $20000
      error "Object code bank overflows 64KB by \{*-$20000} bytes"
    endif

; -----------------------------------------------
; Data (outside object code bank — addressed directly, not via objroutine)
; -----------------------------------------------
__BUDGET_DATA:
    include "games/sonic4/data/parallax/ojz_default.asm"
    include "games/sonic4/data/parallax/ojz_windy.asm"
    ; Reusable parallax effects library — drop new effects under
    ; data/parallax/effects/ and include them here. Each file defines a
    ; deform table + ParallaxConfig_* record that any section can point
    ; at via Sec_sec_parallax_config. Must come AFTER ojz_default.asm
    ; because some effects reference DeformTable_Zero from there.
    include "games/sonic4/data/parallax/effects/shimmer.asm"
    include "games/sonic4/data/parallax/effects/haze.asm"
    include "games/sonic4/data/parallax/effects/rocking.asm"
    include "games/sonic4/data/parallax/effects/perspective.asm"
    ; Composite scenes — hand-authored configs that stack multiple effects
    ; with custom per-band gradients. Must come AFTER effects/ for the
    ; deform-table references to resolve.
    include "games/sonic4/data/parallax/scenes/windy_haze.asm"
    include "games/sonic4/data/parallax/scenes/sky_haze.asm"
    include "games/sonic4/data/parallax/scenes/caves.asm"
    include "games/sonic4/data/parallax/scenes/locked_clouds.asm"
    include "games/sonic4/data/objdefs/test_objects.asm"
    include "games/sonic4/data/generated/ojz/act1/entity_data.asm"
    include "games/sonic4/data/levels/ojz/act1/act_descriptor.asm"
    include "games/sonic4/data/mappings/test_mappings.asm"
    include "games/sonic4/data/animations/sonic_anims.asm"
    include "games/sonic4/data/animations/particle_anims.asm"

; -----------------------------------------------
; Collision data (§4.7 — global, shared across all zones)
; -----------------------------------------------
HeightMaps:
    BINCLUDE "games/sonic4/data/collision/heightmaps.bin"
    align 2
HeightMapsRot:
    BINCLUDE "games/sonic4/data/collision/heightmaps_rot.bin"
    align 2
AngleTable:
    BINCLUDE "games/sonic4/data/collision/angles.bin"
    align 2
SolidityTable:
    BINCLUDE "games/sonic4/data/collision/solidity.bin"
    align 2

Map_Sonic:
    BINCLUDE "games/sonic4/data/mappings/sonic.bin"
    align 2
    if (*-Map_Sonic) > $7FFF
      error "Map_Sonic exceeds signed word-offset range"
    endif
DPLC_Sonic:
    BINCLUDE "games/sonic4/data/dplc/optimized/sonic.bin"
    align 2
    if (*-DPLC_Sonic) > $7FFF
      error "DPLC_Sonic exceeds signed word-offset range"
    endif
Art_Sonic:
    BINCLUDE "art/optimized/characters/sonic.bin"
    align 2

; -----------------------------------------------
; DAC sample data (§1B — ROM-streamed via Z80 bank window)
; Bank-aligned (align $8000); the Z80 reads it through its $8000 window.
; -----------------------------------------------
    ifdef SOUND_DRIVER_ENABLED
        include "games/sonic4/data/sound/dac_samples.asm"
        ; NOTE: the 68k DUPLICATE sound tables (data/sound/sound_tables.asm =
        ; FmPitchTable/PsgDivisorTable/LogVolumeLut/CarrierMaskTable, and
        ; data/sound/fm_patches.asm = FmPatchTable) were REMOVED. They are never
        ; referenced — the runtime reads the Z80-resident *Z copies co-located in the
        ; Moving Trucks bank below — AND they broke the build: their placement made
        ; FmPitchTable's address oscillate across AS passes (warning #80, "change of
        ; symbol values forces additional pass"), so asl repassed forever and never
        ; produced s4.bin. song_table + the song data follow in the bank-aligned block.
        ; The NATIVE "Moving Trucks" port — a native sequencer playback of the song
        ; data (NOT a register replay), generated by
        ; tools/zyrinx_player.py --emit-native-song. T3 streams it from ROM with the
        ; DAC OFF (the adaptive FM6 slot): the Z80 sequencer reads BOTH the song
        ; streams AND the patch bank AND the per-song pitch table DIRECTLY through
        ; the banked $8000 window with ONE SetBank. So the whole streaming block
        ; (song + pitch table + patch bank) must live in ONE 32KB bank, bank-aligned
        ; (like dac_samples.asm). align $8000 snaps to a bank start; the contiguous
        ; block is asserted below in song_table.asm to NOT cross a bank boundary.
        align   $8000                          ; MT's streamed bank start (window $8000)
MovingTrucks_Bank_Start:                        ; real ROM address of the bank start (tables first)
        ; F5 co-location: the engine lookup tables live at the START of MT's OWN
        ; streamed bank. MT reads its stream/patch/pitch through the $8000 window
        ; every frame, so the tables are read from the SAME bank already in the
        ; window — no separate table bank, no per-frame swap. Emitted under
        ; `cpu z80` + `phase 08000h` so the labels equal their $8000-window ptrs
        ; (little-endian, as the Z80 reads them). The song/pitch/patch follow.
        save
        cpu     z80
        phase   08000h
        include "engine/sound/sound_tables_z80.asm"
        include "games/sonic4/data/sound/movingtrucks_pitchtable.asm"
        if (MovingTrucks_PitchTable_End - MovingTrucks_PitchTable) <> 2*PITCHTAB_COUNT
          fatal "MovingTrucks_PitchTable wrong size: \{MovingTrucks_PitchTable_End - MovingTrucks_PitchTable} != \{2*PITCHTAB_COUNT}"
        endif
        ; SfxBlobWinTab — moved here from the resident Z80 blob (Phase-2 budget
        ; recovery, ~270 B). Co-located in this same MT/SFX bank so the two readers
        ; (sound_sfx.asm) read it through the $8000 window after SetBank(SFX_BLOB_BANK).
        include "engine/sound/sfx_blob_win_tab.asm"
        ; Banked in-frame Z80 routines (Phase-2 music expression). Authored in the
        ; window (not the resident blob) so they cost 0 against the $16F0 ceiling;
        ; called only from in-frame code (song bank guaranteed in window). See the
        ; file header for the banking invariants.
        include "engine/sound/sound_banked_z80.asm"
        dephase
        restore
        include "games/sonic4/data/sound/song_movingtrucks.asm"
        ; The per-song pitch table (the 132-entry Zyrinx Moving-Trucks fnum table,
        ; two parallel A4/A0 pages). Placed CONTIGUOUSLY right after the song so the
        ; header's pitchtable_ptr (= the song length) resolves to base+offset inside
        ; the same bank-aligned 32KB block. Distinct label from the engine-default
        ; inline copy in the Z80 blob (no label collision). The loader points
        ; Snd_PitchTabPtr here via the header offset.
        include "games/sonic4/data/sound/movingtrucks_pitchtable_stream.asm"
        ; The per-song FmPatch bank (33 records * 26 = 858 bytes), read by
        ; Fm_PatchLoad at SND_SEQ_PATCHTAB + local_idx*26. Placed CONTIGUOUSLY after
        ; the pitch table (no align between) so the whole block stays in the one
        ; bank-aligned 32KB bank. The stream-path loader points SND_SEQ_PATCHTAB at
        ; this bank's window ptr (from SongPatchTable). Emitted via the `pbyte`
        ; single-source pattern (so it can ALSO be inlined in the Z80 blob).
        include "games/sonic4/data/sound/movingtrucks_patches.asm"
    ifdef __DEBUG__
        ; DEBUG STREAM DAC-on drum-test song (DAC-drum phase Layer 5 Task 5.3, id 2).
        ; Co-located in THIS bank (the only one holding the engine tables, which the
        ; FM writer reads window-relative): it reuses the engine-default pitch table
        ; (pitchtable_ptr=0 -> FmPitchTableZ above) and Moving Trucks' FM patch bank
        ; (SongPatchTable[1] = MovingTrucks_Patches). The drum payloads stay in the
        ; SEPARATE shared DAC bank (dac_samples.asm), so its song bank != the sample
        ; bank and the per-frame B1 swap is genuinely exercised. Defined BEFORE
        ; song_table.asm (which references Song_DrumTest). Tiny (< 300 B) — fits the
        ; same bank; the no-straddle guard is in song_table.asm.
        include "games/sonic4/data/sound/song_drumtest.asm"

        ; --- HCZ2 (S3K Hydrocity Zone Act 2) import — Phase 7 (id 3) ----------
        ; A faithful native sequencer playback (NOT a register replay) of the original
        ; S3K SMPS song, generated from skdisasm by song_hcz2.py. STREAM song
        ; (SH_F_STREAM, like Moving Trucks): the Z80 sequencer reads its command streams
        ; AND its FM patch bank DIRECTLY through the banked $8000 window with ONE SetBank.
        ; CO-LOCATED in THIS bank (same as Moving Trucks + DrumTest) — NO own `align
        ; $8000`. WHY: the FM/PSG voice writers read the engine tables (FmPitchTableZ /
        ; LogVolumeLutZ / CarrierMaskTableZ / PsgDivisorTableZ / PsgVolEnv_* and the
        ; default MovingTrucks_PitchTable) as bare `phase 08000h` labels = window-
        ; relative, and those tables physically live ONLY at the start of THIS bank. An
        ; own HCZ2 bank would window-in a bank WITHOUT them -> garbage pitch/volume. Co-
        ; locating lets HCZ2 reuse them with zero duplication (pitchtable_ptr=0 ->
        ; FmPitchTableZ above), exactly as DrumTest does. song_hcz2.asm + its FM patch
        ; bank (HCZ2_Patches, 4*26=104 B) follow CONTIGUOUSLY so one SetBank covers every
        ; HCZ2 sequencer ROM read; the whole MT+DrumTest+HCZ2 block must fit ONE 32KB
        ; bank (the no-straddle + window-top guards in song_table.asm enforce it — if it
        ; overflows, a label-free engine-table copy in a dedicated HCZ2 bank is the
        ; fallback). Defined BEFORE song_table.asm (which references Song_HCZ2 +
        ; HCZ2_Patches in SongTable/SongPatchTable + the bank-fit asserts).
        include "games/sonic4/data/sound/song_hcz2.asm"
        include "games/sonic4/data/sound/hcz2_patches.asm"
    endif
        include "games/sonic4/data/sound/song_table.asm"
        ; --- Phase 5a SFX data (generated by tools/sfx_transcode.py) ---
        ; Small FM/PSG blobs (no DAC, no bank-streaming) — plain inline data the
        ; Z80 SFX loader reads via the $8000 window. SfxTable indexes id -> blob.
        ; Each SFX has its own blob + FmPatch bank (independent labels, no sharing).
        ; Include order: blobs + their patch banks before sfx_table.asm (which
        ; references the blob labels). PSG-only SFX have empty patch banks.
        include "games/sonic4/data/sound/sfx/sfx_33.asm"
        include "games/sonic4/data/sound/sfx/sfx_33_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_34.asm"
        include "games/sonic4/data/sound/sfx/sfx_34_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_35.asm"
        include "games/sonic4/data/sound/sfx/sfx_35_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_36.asm"
        include "games/sonic4/data/sound/sfx/sfx_36_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_3C.asm"
        include "games/sonic4/data/sound/sfx/sfx_3C_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_62.asm"
        include "games/sonic4/data/sound/sfx/sfx_62_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_AB.asm"
        include "games/sonic4/data/sound/sfx/sfx_AB_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_B6.asm"
        include "games/sonic4/data/sound/sfx/sfx_B6_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_B9.asm"
        include "games/sonic4/data/sound/sfx/sfx_B9_patches.asm"
        include "games/sonic4/data/sound/sfx/sfx_table.asm"
        ; The Z80 SFX reader derives a single SFX_BLOB_BANK from the first blob and
        ; addresses every blob through the $8000 window (low 15 bits). That only holds
        ; while the whole contiguous SFX block lives in one $8000 ROM page. Sfx_33 is
        ; the lowest SFX symbol, Sfx_B9_Patches_End the highest — guard that they share
        ; a page so a future blob set growing across a boundary fails the build, not on HW.
        if (Sfx_33>>15) <> ((Sfx_B9_Patches_End-1)>>15)
            fatal "SFX blob set straddles a $8000 bank boundary; SFX_BLOB_BANK invalid (split blobs or add per-blob banking)"
        endif
    endif

; -----------------------------------------------
; Test game states
; -----------------------------------------------
    include "test/object_test_state.asm"
    include "test/ojz_scroll_test.asm"

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

    END
