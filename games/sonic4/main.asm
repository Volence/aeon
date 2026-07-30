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
    ifndef SIGIL_EMP_PLAYER_SENSORS
        include "games/sonic4/player/player_sensors.asm"
    else
        ; sigil mixed build: the collision sensor primitives (Collision_Probe*,
        ; Player_Sensor*, Player_AtLedgeEdge) come from player_sensors.emp,
        ; pinned by the sigil map at the engine-block region start. Unlike the
        ; object-bank player state files, this region's BASE shifts with upstream
        ; __DEBUG__ growth (SHAPE-VARYING base, shape-invariant own layout $4FC),
        ; so the resume org is PER-SHAPE. Resume lands on game_debug.asm's start,
        ; which emits ZERO canonical bytes (whole-file ifdef SOUND_DEBUG_HOTKEYS),
        ; i.e. Section_Init. The gate define must never be set for other games.
      ifdef __DEBUG__
        org     $633C
      else
        org     $55A4
      endif
    endif
    ifndef SIGIL_EMP_GAME_DEBUG
        include "games/sonic4/debug/game_debug.asm"
    else
        ; sigil mixed build (off-canonical Config A: __DEBUG__ + SOUND_DRIVER_ENABLED
        ; + SOUND_DEBUG_HOTKEYS): Debug_MusicToggle/Dbg_SfxIdTable come from
        ; game_debug.emp, placed by the sigil map at the region start. org resumes
        ; at the region end (Section_Init). Canonically game_debug.asm emits ZERO
        ; bytes (whole-file ifdef SOUND_DEBUG_HOTKEYS, off in every shipped build),
        ; so the gate-OFF build is byte-neutral. This org value is the CONFIG-A
        ; sonic4-shape address — the gate define must NEVER be set except by the
        ; sigil off-canonical whole-ROM gate at Config A.
        org     $6408
    endif
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
    ifndef SIGIL_EMP_PLAYER_GROUND
      include "games/sonic4/player/player_ground.asm"
    else
        ; sigil mixed build: the grounded state bodies (PState_Ground/Roll,
        ; Ground_Move/Cap/PostMove, Player_SlopeRepel, Ground_DetachState,
        ; Player_Jump) come from games/sonic4/player/player_ground.emp. Pure code,
        ; shape-invariant window; ONE org both shapes. Resume lands on player_air's
        ; first label PState_Air. The gate define must never be set for other games.
        org     $10896
    endif
    ifndef SIGIL_EMP_PLAYER_AIR
      include "games/sonic4/player/player_air.asm"
    else
        ; sigil mixed build: the airborne state bodies (PState_Air/AirBall/RollJump/
        ; Jump/AirShared + the Air_* helpers) come from player_air.emp. Shape-invariant
        ; window; ONE org both shapes. Resume lands on player_spindash's first label
        ; PState_Spindash.
        org     $10B58
    endif
    ifndef SIGIL_EMP_PLAYER_SPINDASH
      include "games/sonic4/player/player_spindash.asm"
    else
        ; sigil mixed build: PState_Spindash comes from player_spindash.emp. Shape-
        ; invariant window; ONE org both shapes. Resume lands on sonic.asm's first
        ; label Sonic_InitAssets.
        org     $10BF4
    endif
    ifndef SIGIL_EMP_SONIC
      include "games/sonic4/player/sonic.asm"
    else
        ; sigil mixed build: Sonic_InitAssets/Sonic_LoadArt/PhysTable_Sonic come
        ; from games/sonic4/player/sonic.emp. Shape-invariant window; ONE org both
        ; shapes. Resume lands on test_static.asm's first label TestStatic_Main.
        ; The gate define must never be set for other games (demo takes the
        ; includes).
        org     $10C34
    endif

    ifndef SIGIL_EMP_TEST_STATIC
      include "games/sonic4/objects/test_static.asm"
    else
        ; sigil mixed build: TestStatic_Main comes from
        ; games/sonic4/objects/test_static.emp, pinned by the sigil map at the
        ; reference address inside the object code bank (org $10000, ObjCodeBase).
        ; Shape-invariant window; ONE org serves both shapes while the banks
        ; coincide (the $8000 abs.w/abs.l bar — see the test_objects arm below).
        ; The gate define must never be set for other games (demo takes the
        ; includes).
        org     $10C38
    endif
    ifndef SIGIL_EMP_TEST_ANIMATED
      include "games/sonic4/objects/test_animated.asm"
    else
        ; sigil mixed build: TestAnimated/TestAnimated_Main come from
        ; games/sonic4/objects/test_animated.emp. The DplcV sst_custom overlay
        ; is defined AS-side by the surviving test_player.asm copy (identical
        ; equs), so _dplc_ptr/_art_base still resolve for it. Shape-invariant
        ; window; ONE org both shapes.
        org     $10C92
    endif
    include "games/sonic4/objects/test_player.asm"
    include "games/sonic4/objects/test_enemy.asm"
    ifndef SIGIL_EMP_TEST_OBJECTS
      include "games/sonic4/objects/test_solid.asm"
      include "games/sonic4/objects/test_particle.asm"
    else
        ; sigil mixed build: TestSolid_Init/Main + TestParticle/Main come from
        ; games/sonic4/objects/test_solid.emp + test_particle.emp, pinned by
        ; the sigil map at the reference addresses. Resume placement at the
        ; region end (see sigil-harness golden/PROVENANCE.md; re-pin on
        ; re-baseline). These addresses live inside the object code bank
        ; (org $10000, ObjCodeBase). ONE org serves both shapes only while the
        ; two banks coincide, which is a CONDITIONAL fact, not a structural
        ; one: the bank's own contents are __DEBUG__-invariant, but the player
        ; code inside it calls ENGINE symbols, so a debug-only engine growth
        ; that pushes one of those symbols past $8000 widens `jsr (Sym).w` to
        ; abs.l (+2 bytes each) and slides the whole debug bank. If that
        ; happens, this arm needs per-shape orgs and every harness fixture
        ; keyed to the bank needs its debug pin (measured at tranche 24, where
        ; a +$14E debug-only growth did exactly that before it was trimmed).
        ; AS-side consumers (ObjDef_Solid's objdef, the emitters' objroutine
        ; words) keep resolving through the shared link.
        ; NOTE: the gate define must never be set for other games (demo
        ; builds take the includes).
        org     $10FAA
    endif
    ifndef SIGIL_EMP_TEST_EMITTER
      include "games/sonic4/objects/test_emitter.asm"
    else
        ; sigil mixed build: TestEmitter/TestEmitter_Main come from
        ; games/sonic4/objects/test_emitter.emp. Shape-invariant window; ONE org
        ; serves both shapes while the object banks coincide (the $8000
        ; abs.w/abs.l bar — see the test_objects arm above). Resume lands on
        ; test_parent.asm's FIRST label TestChildPart (NOT TestParent — that is
        ; its third label). AS-side consumers (the effect descriptor's objroutine
        ; word for TestParticle) keep resolving through the shared link. The gate
        ; define must never be set for other games (demo takes the includes).
        org     $10FFE
    endif
    ifndef SIGIL_EMP_TEST_PARENT
      include "games/sonic4/objects/test_parent.asm"
    else
        ; sigil mixed build: TestChildPart/TestChildPart_Main/TestParent/
        ; TestParent_Main come from games/sonic4/objects/test_parent.emp. Shape-
        ; invariant window; ONE org both shapes while the object banks coincide
        ; (the $8000 abs.w/abs.l bar — see the test_objects arm above). Resume
        ; lands on test_stress_emitter's first label TestStressEmitter. All
        ; callees (CreateChild_Normal / DeleteChildren / GetSineCosine /
        ; DeleteObject / Draw_Sprite) resolve through the shared link. The gate
        ; define must never be set for other games (demo takes the includes).
        org     $11128
    endif
    ifndef SIGIL_EMP_TEST_STRESS_EMITTER
      include "games/sonic4/objects/test_stress_emitter.asm"
    else
        ; sigil mixed build: TestStressEmitter/TestStressEmitter_Main come from
        ; games/sonic4/objects/test_stress_emitter.emp. Shape-invariant window;
        ; ONE org both shapes. Resume lands on test_churn's TestChurnObj.
        org     $11182
    endif
    ifndef SIGIL_EMP_TEST_CHURN
      include "games/sonic4/objects/test_churn.asm"
    else
        ; sigil mixed build: TestChurnObj/TestChurnObj_Main come from
        ; games/sonic4/objects/test_churn.emp. Shape-invariant window; ONE org
        ; both shapes. Resume lands on path_swap.asm's ObjDef_PathSwap.
        org     $111FA
    endif
    ifndef SIGIL_EMP_PATH_SWAP
      include "games/sonic4/objects/path_swap.asm"
    else
        ; sigil mixed build: ObjDef_PathSwap descriptor + PathSwap_Init/Main come
        ; from games/sonic4/objects/path_swap.emp. SHAPE-DEPENDENT window (2
        ; __DEBUG__ blocks: the reserved-bit RaiseError guard + the debug jmp
        ; Draw_Sprite vs release rts tail) — the debug shape is +$68 longer, so
        ; this is the object bank's first PER-SHAPE gate resume org. Resume lands
        ; on gameDataIncludes' first label DeformTable_Zero (ojz_default.asm), the
        ; next placement. AS-side consumers (act_descriptor / entity_data
        ; `dc.l ObjDef_PathSwap`) resolve to the .emp-exported label through the
        ; shared link. The gate define must never be set for other games (demo
        ; takes the include).
      ifdef __DEBUG__
        org     $112F4
      else
        org     $1128C
      endif
    endif
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
    ifndef SIGIL_EMP_OBJDEFS
        include "games/sonic4/data/objdefs/test_objects.asm"
    else
        ; sigil mixed build: the four ObjDef_* archetype templates come from
        ; games/sonic4/data/objdefs/test_objects.emp, pinned by the sigil map
        ; at the per-shape reference address. Resume placement at the region
        ; end (objdef_port pins OBJDEFS; re-pin on re-baseline). NOTE:
        ; sonic4-shape addresses — never set the define for other games.
      ifdef __DEBUG__
        org     $11DE6
      else
        org     $11D7E
      endif
    endif
    include "games/sonic4/data/generated/ojz/act1/entity_data.asm"
    include "games/sonic4/data/levels/ojz/act1/act_descriptor.asm"
    include "games/sonic4/data/mappings/test_mappings.asm"
    ifndef SIGIL_EMP_SONIC_ANIMS
        include "games/sonic4/data/animations/sonic_anims.asm"
    else
        ; sigil mixed build: Ani_Sonic comes from
        ; games/sonic4/data/animations/sonic_anims.emp, pinned by the sigil
        ; map at the per-shape reference address. Resume placement at the
        ; region end (see sigil-harness golden/PROVENANCE.md; re-pin on
        ; re-baseline). NOTE: sonic4-shape addresses — never set the define
        ; for other games.
      ifdef __DEBUG__
        org     $257B2
      else
        org     $2574A
      endif
    endif
    ifndef SIGIL_EMP_PARTICLE_ANIMS
        include "games/sonic4/data/animations/particle_anims.asm"
    else
        ; sigil mixed build: Ani_Particle comes from
        ; games/sonic4/data/animations/particle_anims.emp, pinned by the
        ; sigil map at the per-shape reference address. Resume placement at
        ; the region end (see sigil-harness golden/PROVENANCE.md; re-pin on
        ; re-baseline). NOTE: sonic4-shape addresses — never set the define
        ; for other games.
      ifdef __DEBUG__
        org     $257BA
      else
        org     $25752
      endif
    endif

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
    ifndef SIGIL_EMP_DAC
        include "games/sonic4/data/sound/dac_samples.asm"
    else
        ; sigil mixed build: the DAC banks come from dac_samples.emp, pinned by
        ; the sigil map at $48000/$50000. org skips the two-bank hole; the next
        ; align $8000 (MT bank) then lands at $58000 exactly as before. If art
        ; growth ever collides with the pins, the sigil linker errors loudly.
        org     $58000
    endif
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
; The SFX blobs share the engine-table bank (asserted by the SFX co-residency
; guard below / sfx_bank.emp's ensure) — declare the contract directly rather
; than deriving from Sfx_33, whose label is .emp-side under SIGIL_EMP_SFX.
SFX_BLOB_BANK = SND_ENGINE_TABLE_BANK
        save
        cpu     z80
        phase   08000h
        soundBankHead "games/sonic4/data/sound/movingtrucks_pitchtable.asm", "games/sonic4/data/sound/sfx_blob_win_tab.asm"
        dephase
        restore
    ifndef SIGIL_EMP_MT
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
    else
        ; sigil mixed build: everything from Song_MovingTrucks ($58607) through
        ; SongPatchTable_End comes from mt_bank.emp, pinned by the sigil map.
        ; Resume placement for the SFX block at the per-shape reference address
        ; (from s4.lst/s4.debug.lst; re-pin on re-baseline — see sigil-harness
        ; golden/PROVENANCE.md).
      ifdef __DEBUG__
        org     $5D53A
      else
        org     $5BAE8
      endif
    endif
        ; --- Phase 5a SFX data (generated by tools/sfx_transcode.py) ---
        ; Small FM/PSG blobs (no DAC, no bank-streaming) — plain inline data the
        ; Z80 SFX loader reads via the $8000 window. SfxTable indexes id -> blob.
        ; Each SFX has its own blob + FmPatch bank (independent labels, no sharing).
        ; Include order: blobs + their patch banks before sfx_table.asm (which
        ; references the blob labels). PSG-only SFX have empty patch banks.
    ifndef SIGIL_EMP_SFX
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
    else
        ; sigil mixed build: everything from Sfx_33 through SfxTable_End comes
        ; from sfx_bank.emp, pinned by the sigil map (region `sfx_bank`).
        ; Resume placement at the per-shape reference address
        ; (see sigil-harness golden/PROVENANCE.md; re-pin on re-baseline).
      ifdef __DEBUG__
        org     $5DC82
      else
        org     $5C230
      endif
    endif
    endm

; -----------------------------------------------
; Test game states
; -----------------------------------------------
gameStatesIncludes macro {GLOBALSYMBOLS}
    ifndef SIGIL_EMP_OBJECT_TEST_STATE
      include "games/sonic4/test/object_test_state.asm"
    else
        ; sigil mixed build: GameState_ObjectTest{,_Init}/ObjectTestChurn{,_Init}
        ; + TestObjectList/TestArt/TestPalette come from
        ; games/sonic4/test/object_test_state.emp. SHAPE-DEPENDENT window (the
        ; DEBUG profiling block grows the region +$9C). Resume lands on
        ; ojz_scroll_test's first label GameState_OJZScroll_Init, the next
        ; placement. AS-side consumers (ojz's `TestArt`/`TestArt_End` refs, the
        ; runtime GameState_ObjectTestChurn_Init poke) resolve to the .emp-exported
        ; labels through the shared link. The gate define must never be set for
        ; other games (demo takes the include).
      ifdef __DEBUG__
        org     $5E2DA
      else
        org     $5C7EC
      endif
    endif
    ifndef SIGIL_EMP_OJZ_SCROLL_TEST
      include "games/sonic4/test/ojz_scroll_test.asm"
    else
        ; sigil mixed build: GameState_OJZScroll_Init/_Update (Game_Entry) +
        ; OJZ_SectionMarkerColors/PlayerMarkerTile come from
        ; games/sonic4/test/ojz_scroll_test.emp. SHAPE-DEPENDENT window (the two
        ; Debug_Scene_Freeze skip blocks grow the region +$C). Resume lands on
        ; main.asm's NullInterrupt stub (the post-gameStates level-1 placement).
        ; config/game.asm's `Game_Entry = GameState_OJZScroll_Init` resolves to
        ; the .emp export. The gate define must never be set for other games.
      ifdef __DEBUG__
        org     $5E5A8
      else
        org     $5CAAE
      endif
    endif
    endm

    include "engine/engine.inc"
    END
