; Sonic 4 Engine — main assembly file (game manifest)
; The engine owns the ROM layout (engine/engine.inc). This file supplies the
; game-specific includes via the contract macros it requires.

; -----------------------------------------------
; Assembly options
; -----------------------------------------------
PAD_TO_POWER_OF_TWO     = 1

gameConfigIncludes macro {GLOBALSYMBOLS}
    include "games/sonic4/config/constants.asm"
    include "games/sonic4/config/sound_ids.asm"
    include "games/sonic4/config/game.asm"
    endm

gameRamIncludes macro {GLOBALSYMBOLS}
    include "games/sonic4/config/ram.asm"
    endm

gameEngineBlockIncludes macro {GLOBALSYMBOLS}
    include "games/sonic4/player/player_sensors.asm"
    include "games/sonic4/debug/game_debug.asm"
    endm

gameObjectBankIncludes macro {GLOBALSYMBOLS}
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
    endm

gameDataIncludes macro {GLOBALSYMBOLS}
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
    endm

gameSoundDataIncludes macro {GLOBALSYMBOLS}
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
; The Z80 bank id of the engine-table head bank (THIS bank). Used by the resident
; driver where a read of the head tables has no ambient bank guarantee (today:
; SndDrv_PollMailbox's SND_REQ_SAMPLE block before its DacSampleTable descriptor
; reads). Same derivation as sfx_bankid()/the SND_*_BANK sample constants.
SND_ENGINE_TABLE_BANK = MovingTrucks_Bank_Start >> 15
        save
        cpu     z80
        phase   08000h
        soundBankHead "games/sonic4/data/sound/movingtrucks_pitchtable.asm", "games/sonic4/data/sound/sfx_blob_win_tab.asm"
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
        ; LAYOUT GUARD: the song header bakes the pitch table's offset as the
        ; packed song length (MT_PITCHTAB_OFFSET, emitted by the generator). Any
        ; pad byte between the song and the table shifts every pitch lookup one
        ; byte early = the whole song plays a semitone flat (shipped bug,
        ; root-caused 2026-07-01 — the blob's trailing `align 2` did exactly
        ; this whenever the preceding bank content had odd total length).
        if (MovingTrucks_PitchTable_Stream - Song_MovingTrucks) <> MT_PITCHTAB_OFFSET
          fatal "MT pitch table not contiguous with the song: offset \{MovingTrucks_PitchTable_Stream - Song_MovingTrucks} != header's \{MT_PITCHTAB_OFFSET} — a pad byte would detune the whole song"
        endif
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
        ; Sfx_Frame runs the SHARED interpreter (Sequencer_Channel dispatch via the
        ; banked SeqOpcodeTable) and the FM/PSG writers (banked FmPitchTableZ/
        ; LogVolumeLutZ/...) under its entry SetBank(SFX_BLOB_BANK) — so the SFX
        ; bank MUST be the engine-table head bank (replicate-per-bank rule above).
        ; This was previously an unasserted layout fact; make it a build error.
        if (Sfx_33>>15) <> SND_ENGINE_TABLE_BANK
            fatal "SFX blobs not co-located with the engine-table bank (Sfx_33 bank \{Sfx_33>>15} != \{SND_ENGINE_TABLE_BANK}) — Sfx_Frame's dispatch/table reads would see the wrong bank"
        endif

; -----------------------------------------------
; Test game states
; -----------------------------------------------
    include "games/sonic4/test/object_test_state.asm"
    include "games/sonic4/test/ojz_scroll_test.asm"
    endm

    include "engine/engine.inc"
    END
