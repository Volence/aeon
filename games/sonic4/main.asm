; Sonic 4 Engine — main assembly file (game manifest)
; The engine owns the ROM layout (engine/engine.inc). This file supplies the
; game-specific includes via the contract macros it requires.

; -----------------------------------------------
; Assembly options
; -----------------------------------------------
PAD_TO_POWER_OF_TWO     = 1

gameConfigIncludes macro {GLOBALSYMBOLS}
    ; Game constants are authored in games/sonic4/config/constants.emp (conversion
    ; Parcel F) — the `.emp` module `games.sonic4.constants`. The song / SFX ids +
    ; priority ladder are in games/sonic4/config/sound_ids.emp (module
    ; games.sonic4.sound_ids, Parcel F2), and the SFX-bank id counts are DERIVED in
    ; games/sonic4/data/sound/sfx/sfx_bank.emp. All are harvested (native.rs
    ; harvest_game_constants) into guarded AS `-D` defines + link EquSyms, so the
    ; residual AS and the game-agnostic engine `.emp` read them; game `.emp`
    ; consumers read them via `use games.sonic4.{constants,sound_ids}`. config/
    ; sound_ids.asm is retired (fully `.emp`-authored now).
    include "games/sonic4/config/game.asm"
    endm

gameRamIncludes macro {GLOBALSYMBOLS}
    ; Game RAM is authored in games/sonic4/config/ram.emp (item #7c) — the `.emp`
    ; region form (`game_ram @ after(upper_ram)`). Its `pub vars` labels are the
    ; joint-link RAM authority; the residual AS reads the one address it needs
    ; eagerly (`move.b #1,(Dbg_Music_On).w` in config/game.asm) via the harvested
    ; value defines (native.rs harvest_engine_ram_addresses).
    endm

gameEngineBlockIncludes macro {GLOBALSYMBOLS}
    ; The collision sensor primitives (Collision_Probe*, Player_Sensor*,
    ; Player_AtLedgeEdge) are native (player_sensors.emp), pinned by the sigil map
    ; at the engine-block region start. Unlike the object-bank player state files,
    ; this region's BASE shifts with upstream __DEBUG__ growth (shape-varying base,
    ; shape-invariant $4FC own layout), so the resume org is PER-SHAPE; it lands on
    ; Section_Init (game_debug emits zero canonical bytes). The orgs are sonic4-shape.
    ifdef __DEBUG__
        org     $633C
    else
        org     $55A4
    endif
    ifdef SIGIL_EMP_GAME_DEBUG
        ; Debug_MusicToggle/Dbg_SfxIdTable are native (game_debug.emp), placed by
        ; the sigil map (Config-A only: __DEBUG__ + SOUND_DRIVER_ENABLED +
        ; SOUND_DEBUG_HOTKEYS). org resumes at the region end (Section_Init).
        ; Canonically this region emits ZERO bytes (SOUND_DEBUG_HOTKEYS off in every
        ; shipped build), so the canonical shapes place nothing here (the gate is set
        ; only by the sigil Config-A whole-ROM build) — byte-neutral. This org is the
        ; CONFIG-A sonic4-shape address.
        org     $6408
    endif
    endm

gameObjectBankIncludes macro {GLOBALSYMBOLS}
    ; Player (§5) — in the object bank: Player_Main dispatches via
    ; objroutine(), which needs the routine within ObjCodeBase+64KB.
    ; (player_sensors.asm stays in the engine block above — it has no
    ; code_addr entry points.)
    ; Player_Init/Main/Display/RefreshPhysics/SetState + the state dispatch + the
    ; Player_States/EnterHooks/ExitHooks offset tables are native (player_common.emp),
    ; pinned by the sigil map inside the object code bank. It owns the PlayerV overlay
    ; and the PPHYS_*/macro templates the state files import by `use`. Shape-invariant
    ; window; ONE org both shapes, resuming on player_ground's first label PState_Ground.
    org     $10448
    ; The grounded state bodies (PState_Ground/Roll, Ground_Move/Cap/PostMove,
    ; Player_SlopeRepel, Ground_DetachState, Player_Jump) are native
    ; (player_ground.emp). Pure code, shape-invariant window; ONE org both shapes,
    ; resuming on player_air's first label PState_Air.
    org     $10896
    ; The airborne state bodies (PState_Air/AirBall/RollJump/Jump/AirShared + the
    ; Air_* helpers) are native (player_air.emp). Shape-invariant window; ONE org
    ; both shapes, resuming on player_spindash's first label PState_Spindash.
    org     $10B58
    ; PState_Spindash is native (player_spindash.emp). Shape-invariant window; ONE
    ; org both shapes, resuming on sonic.asm's first label Sonic_InitAssets.
    org     $10BF4
    ; Sonic_InitAssets/Sonic_LoadArt/PhysTable_Sonic are native (sonic.emp).
    ; Shape-invariant window; ONE org both shapes, resuming on test_static.asm's
    ; first label TestStatic_Main.
    org     $10C34

    ; TestStatic_Main is native (test_static.emp), pinned by the sigil map inside
    ; the object code bank (org $10000, ObjCodeBase). Shape-invariant window; ONE
    ; org both shapes while the banks coincide (the $8000 abs.w/abs.l bar below).
    org     $10C38
    ; TestAnimated/TestAnimated_Main are native (test_animated.emp). It owns its
    ; DplcV sst_custom overlay ($2E/$32). Shape-invariant window; ONE org.
    org     $10C92
    ; TestPlayer/TestPlayer_Main/TestPlayer_Debug are native (test_player.emp), pinned
    ; by the sigil map inside the object code bank. Shape-invariant window; ONE org both
    ; shapes, resuming on test_enemy's first label TestEnemy_Init. AS-side consumers
    ; (object_test_state's ObjSpawn code_addr) resolve through the shared link.
    org     $10F02
    ; TestEnemy_Init/Main are native (test_enemy.emp), pinned by the sigil map inside
    ; the object code bank. Shape-invariant window; ONE org both shapes, resuming on
    ; test_solid's first label TestSolid_Init. AS-side consumers (ObjDef_Enemy's
    ; objdef x_vel) resolve through the shared link.
    org     $10F4A
    ; TestSolid_Init/Main + TestParticle/Main are native (test_solid.emp +
    ; test_particle.emp), pinned by the sigil map inside the object code bank. ONE
    ; org serves both shapes while the two banks coincide (the $8000 abs.w/abs.l
    ; bar): the bank contents are __DEBUG__-invariant, but a debug-only engine
    ; growth pushing a called ENGINE symbol past $8000 would widen jsr (Sym).w to
    ; abs.l (+2 bytes each) and slide the whole debug bank — then this arm needs
    ; per-shape orgs and every bank-keyed harness fixture needs its debug pin
    ; (measured at t24, where a +$14E debug-only growth did exactly that before it
    ; was trimmed). AS-side consumers (ObjDef_Solid's objdef, the emitters'
    ; objroutine words) resolve through the shared link.
    org     $10FAA
    ; TestEmitter/TestEmitter_Main are native (test_emitter.emp). Shape-invariant
    ; window; ONE org both shapes while the object banks coincide. Resume lands on
    ; test_parent's FIRST label TestChildPart. AS-side consumers (the effect
    ; descriptor's objroutine word for TestParticle) resolve through the shared link.
    org     $10FFE
    ; TestChildPart/TestChildPart_Main/TestParent/TestParent_Main are native
    ; (test_parent.emp). Shape-invariant window; ONE org both shapes while the
    ; object banks coincide. Resume lands on test_stress_emitter's TestStressEmitter.
    ; All callees resolve through the shared link.
    org     $11128
    ; TestStressEmitter/TestStressEmitter_Main are native (test_stress_emitter.emp).
    ; Shape-invariant window; ONE org both shapes, resuming on test_churn's TestChurnObj.
    org     $11182
    ; TestChurnObj/TestChurnObj_Main are native (test_churn.emp). Shape-invariant
    ; window; ONE org both shapes, resuming on path_swap's ObjDef_PathSwap.
    org     $111FA
    ; ObjDef_PathSwap descriptor + PathSwap_Init/Main are native (path_swap.emp).
    ; SHAPE-DEPENDENT window (two __DEBUG__ blocks: the reserved-bit RaiseError guard
    ; + the debug jmp Draw_Sprite vs release rts tail; the debug shape is +$68), so
    ; per-shape resume orgs. Resume lands on gameDataIncludes' DeformTable_Zero.
    ; AS-side consumers (act_descriptor / entity_data dc.l ObjDef_PathSwap) resolve
    ; to the .emp-exported label through the shared link.
    ifdef __DEBUG__
        org     $112F4
    else
        org     $1128C
    endif
    endm

gameDataIncludes macro {GLOBALSYMBOLS}
    ; The OJZ parallax block (DeformTable_Zero .. ParallaxConfig_OJZ_LockedClouds)
    ; is native (conv-g): games/sonic4/data/parallax/configs.emp emits the 6 deform
    ; tables + 20 parallax_config records via the engine.level.parallax_dsl authoring
    ; vocabulary, pinned by the sigil map (PARALLAX_CONFIGS). The path_swap resume org
    ; above lands on the block's DeformTable_Zero; the AS residual resumes past it at
    ; the test_objects region below. AS-side consumers (act_descriptor's
    ; act_parallax_config) resolve ParallaxConfig_OJZ_Default through the shared link.
    ; The four ObjDef_* archetype templates are native (test_objects.emp), pinned by
    ; the sigil map; the AS residual resumes at the region end. The orgs are
    ; sonic4-shape (the off-canonical chainer ignores them).
    ;
    ; Parcel K3 run A: the OJZ act1 entity data + art pool are native too now —
    ; entity_data.emp (games.sonic4.ojz_entity_data_act1: the 9-section type
    ; tables / object placements / ring lists) + ojz_act_pool.emp
    ; (games.sonic4.ojz_act_pool_act1: the 3 ZX0 page embeds + page table). With
    ; the descriptor + the run-B tail already native, the whole OJZ block is `.emp`
    ; and act_descriptor.asm is deleted; the org below is an inert resume.
    ifdef __DEBUG__
        org     $11DE6
    else
        org     $11D7E
    endif
    ; Map_TestObj is native (test_mappings.emp), Ani_Sonic is native
    ; (sonic_anims.emp) — both pinned by the sigil map; the AS residual resumes
    ; past them at the region end below. The orgs are sonic4-shape.
    ifdef __DEBUG__
        org     $257B2
    else
        org     $2574A
    endif
    ; Ani_Particle is native (particle_anims.emp), pinned by the sigil map; the AS
    ; residual resumes at the region end. The orgs are sonic4-shape.
    ifdef __DEBUG__
        org     $257BA
    else
        org     $25752
    endif

; -----------------------------------------------
; Collision data (§4.7 — global, shared across all zones) + the Sonic character
; mapping/DPLC/art are native (Parcel K4): games/sonic4/data/collision/
; collision_data.emp emits HeightMaps / HeightMapsRot / AngleTable / SolidityTable
; / Map_Sonic / DPLC_Sonic / Art_Sonic as `embed()`s (the word-offset walls are
; comptime `ensure`s). Placed by the sigil map (boundary key HeightMaps); the org
; above is an inert resume.
; -----------------------------------------------
    endm

gameSoundDataIncludes macro {GLOBALSYMBOLS}
    ; The DAC sample banks are NATIVE (K4 inc-5 Stage 2, the P2 probe):
    ; games/sonic4/data/sound/dac_banks.emp embeds the seam-2 dac_blip_bank.bin @
    ; $48000 + dac_shared_bank.bin @ $50000 at the declared map anchors. The AS
    ; residual SKIPS the two-bank hole so the MT bank's `align $8000` below lands at
    ; $58000. STRUCTURAL EXCLUSIVITY (spec §6): the native section is the SOLE DAC
    ; placement — the BINCLUDE arm is DELETED (can't-both) and the native section is
    ; unconditional in the sound-on registry (can't-neither). SIGIL_EMP_DAC is set in
    ; every sound-on build (native.rs), and gameSoundDataIncludes only runs under
    ; SOUND_DRIVER_ENABLED, so the skip always runs. (The dead SIGIL_EMP_DAC_BODY_STUB
    ; arm — a never-set gate on a dead org-skip — was deleted; the bare SIGIL_EMP_DAC
    ; gate native.rs already sets is the consumed one now.)
    ifdef SIGIL_EMP_DAC
        org     $58000                         ; skip the native DAC banks ($48000..$58000)
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
        soundBankHead
        dephase
        restore
    ; The Moving-Trucks streaming bank BODY is NATIVE (K4 inc-5 Stage 3, the P2 MT
    ; probe): games/sonic4/data/sound/mt_bank_blob.emp embeds the seam-2
    ; mt_bank{,_debug}.bin @ $58607. The AS residual SKIPS the native body (per-shape
    ; end) so the SFX block below lands correctly. mt_syms{,_debug}.asm (an emitted
    ; artifact) STILL supplies SongTable/SongPatchTable — the two labels sound_api.emp
    ; externs — because they sit at mid-blob offsets (len - SONG_COUNT*8/4) a single
    ; embed cannot label. STRUCTURAL EXCLUSIVITY (spec §6): the native section is the
    ; SOLE MT-body placement (the BINCLUDE is DELETED); the section is unconditional in
    ; the sound-on registry; SIGIL_EMP_MT is set in every sound-on build. (The dead
    ; SIGIL_EMP_MT_BODY_STUB arm was deleted.)
    ifdef SIGIL_EMP_MT
      ifdef __DEBUG__
        include  "engine/sound/generated/mt_syms_debug.asm"
        org     $5D53A                         ; skip the native MT body (debug ends $5D53A)
      else
        include  "engine/sound/generated/mt_syms.asm"
        org     $5BAE8                         ; skip the native MT body (plain ends $5BAE8)
      endif
    endif
        ; --- Phase 5a SFX data ---
        ; Small FM/PSG blobs (no DAC, no bank-streaming) — plain inline data the
        ; Z80 SFX loader reads via the $8000 window. SfxTable indexes id -> blob.
    ; The SFX block is NATIVE (K4 inc-5 Stage 4, the P2 SFX probe):
    ; games/sonic4/data/sound/sfx_bank_blob.emp embeds the seam-2 sfx_bank{,_debug}.bin
    ; @ $5BAE8 (plain) / $5D53A (debug). The AS residual SKIPS the native block (per-
    ; shape end) — nothing byte-emitting follows in this macro. No syms (no surviving
    ; AS/emp reads SfxTable; sound_sfx.emp's SfxBlobWinTab reads are native, in the
    ; head). STRUCTURAL EXCLUSIVITY (spec §6): the native section is the SOLE SFX
    ; placement (the BINCLUDE is DELETED); the section is unconditional in the sound-on
    ; registry; SIGIL_EMP_SFX is set in every sound-on build. (The dead
    ; SIGIL_EMP_SFX_BODY_STUB arm was deleted.)
    ifdef SIGIL_EMP_SFX
      ifdef __DEBUG__
        org     $5DC82                         ; skip the native SFX block (debug ends $5DC82)
      else
        org     $5C230                         ; skip the native SFX block (plain ends $5C230)
      endif
    endif
    endm

; -----------------------------------------------
; Test game states
; -----------------------------------------------
gameStatesIncludes macro {GLOBALSYMBOLS}
    ; GameState_ObjectTest{,_Init}/ObjectTestChurn{,_Init} + TestObjectList/TestArt/
    ; TestPalette are native (object_test_state.emp). SHAPE-DEPENDENT window (the
    ; DEBUG profiling block grows the region +$9C), so per-shape resume orgs; resume
    ; lands on ojz_scroll_test's GameState_OJZScroll_Init. AS-side consumers (ojz's
    ; TestArt/TestArt_End refs, the runtime GameState_ObjectTestChurn_Init poke)
    ; resolve to the .emp-exported labels through the shared link.
    ifdef __DEBUG__
        org     $5E2DA
    else
        org     $5C7EC
    endif
    ; GameState_OJZScroll_Init/_Update (Game_Entry) + OJZ_SectionMarkerColors/
    ; PlayerMarkerTile are native (ojz_scroll_test.emp). SHAPE-DEPENDENT window (the
    ; two Debug_Scene_Freeze skip blocks grow the region +$C), so per-shape resume
    ; orgs; resume lands on main.asm's NullInterrupt stub. config/game.asm's
    ; Game_Entry = GameState_OJZScroll_Init resolves to the .emp export.
    ifdef __DEBUG__
        org     $5E5A8
    else
        org     $5CAAE
    endif
    endm

    include "engine/engine.inc"
    END
