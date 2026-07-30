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
    ifdef SIGIL_EMP_DAC_BODY_STUB
        ; sigil DSM mixed harness ONLY: the two DAC banks are composed IN-MEMORY as
        ; dac_samples.emp sections (the dac_port.rs pipeline, pinned at $48000/$50000
        ; by the harness bank map). org skips the two-bank hole; the next align $8000
        ; (MT bank) lands at $58000 exactly as before. This arm exercises the .emp
        ; bank composition inside the whole ROM; the real build takes the BINCLUDE arm.
        org     $58000
    else
        ; seam-2 (Option Y): the DAC sample banks are the byte-identical artifacts
        ; sigil emits from dac_samples.emp (the CANONICAL source — the .asm twin is
        ; deleted) — dac_blip_bank.bin @ $48000, dac_shared_bank.bin @ $50000 —
        ; BINCLUDE'd here in the align/label/BINCLUDE order the descriptor head + the
        ; runtime bank latch expect. build.sh's sigil emit step is a HARD dependency:
        ; there is no asl fallback. The trailing snap to $58000 is the MT bank's own
        ; `align $8000` below (the shared bank ends at $578BC).
        align   $8000                          ; align to a bank start (no boundary cross)
Dac_Temp_Blip:
        BINCLUDE "engine/sound/generated/dac_blip_bank.bin"
        align   $8000                          ; align to a bank start (shared drum bank)
Dac_SharedBank_Start:
Dac_Kick:
        BINCLUDE "engine/sound/generated/dac_shared_bank.bin"
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
; The SFX blobs share the engine-table bank (asserted by sfx_bank.emp's ensure)
; — declare the contract directly rather than deriving from Sfx_33, whose label
; is now .emp-side (the SFX block is the BINCLUDE'd sfx_bank.bin, seam-2 2d).
SFX_BLOB_BANK = SND_ENGINE_TABLE_BANK
        save
        cpu     z80
        phase   08000h
        soundBankHead "games/sonic4/data/sound/movingtrucks_pitchtable.asm"
        dephase
        restore
    ifdef SIGIL_EMP_MT_BODY_STUB
        ; sigil DSM mixed harness ONLY: everything from Song_MovingTrucks ($58607)
        ; through SongPatchTable_End is composed IN-MEMORY as the mt_bank.emp section
        ; (the mt_port.rs pipeline). org resumes the SFX block at the per-shape
        ; reference address; SongTable/SongPatchTable resolve cross-seam from the
        ; composed .emp. Re-pin on re-baseline (see golden/PROVENANCE.md).
      ifdef __DEBUG__
        org     $5D53A
      else
        org     $5BAE8
      endif
    else
        ; seam-2 stage-2c (the real build): the whole Moving-Trucks streaming bank is
        ; the byte-identical artifact sigil emits from mt_bank.emp (the CANONICAL
        ; source — the .asm stream is deleted) — mt_bank{,_debug}.bin — BINCLUDE'd at
        ; $58607. mt_syms{,_debug}.asm supplies SongTable/SongPatchTable (the two labels
        ; sound_api.asm's `movea.l` consumes) as equs at their emitted addresses.
        ; build.sh's sigil emit step is a HARD dependency. Shape-dependent (the debug
        ; build adds DrumTest + HCZ2). The MT stream's old contiguity/straddle/window
        ; guards became mt_bank.emp's link-time ensures (proven at emit).
      ifdef __DEBUG__
        BINCLUDE "engine/sound/generated/mt_bank_debug.bin"
        include  "engine/sound/generated/mt_syms_debug.asm"
      else
        BINCLUDE "engine/sound/generated/mt_bank.bin"
        include  "engine/sound/generated/mt_syms.asm"
      endif
    endif
        ; --- Phase 5a SFX data ---
        ; Small FM/PSG blobs (no DAC, no bank-streaming) — plain inline data the
        ; Z80 SFX loader reads via the $8000 window. SfxTable indexes id -> blob.
    ifdef SIGIL_EMP_SFX_BODY_STUB
        ; sigil DSM mixed harness ONLY: everything from Sfx_33 through SfxTable_End
        ; is composed IN-MEMORY as the sfx_bank.emp section (the sfx_port.rs
        ; pipeline). org resumes at the per-shape reference address (SfxTable_End).
        ; Re-pin on re-baseline (see golden/PROVENANCE.md).
      ifdef __DEBUG__
        org     $5DC82
      else
        org     $5C230
      endif
    else
        ; seam-2 stage-2d (the real build): the whole SFX block (the 9 blobs, their
        ; 9 patch banks, and the sparse id->blob SfxTable) is the byte-identical
        ; artifact sigil emits from sfx_bank.emp (the CANONICAL source — the .asm
        ; stream is deleted) — sfx_bank{,_debug}.bin — BINCLUDE'd at $5BAE8 (plain)
        ; / $5D53A (debug). No syms: no surviving AS code reads SfxTable
        ; (sound_sfx.emp's SfxBlobWinTab reads are native). The old straddle/
        ; co-residency fatals became sfx_bank.emp's link-time ensures (proven at
        ; emit). Shape-dependent (the SfxTable pointer cells hold the per-shape
        ; absolute Sfx_NN addresses). build.sh's sigil emit step is a HARD dependency.
      ifdef __DEBUG__
        BINCLUDE "engine/sound/generated/sfx_bank_debug.bin"
      else
        BINCLUDE "engine/sound/generated/sfx_bank.bin"
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
