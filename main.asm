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
    include "debug/debugger.asm"

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
    include "engine/boot.asm"
    include "engine/vdp_init.asm"
    include "engine/dma_queue.asm"
    include "engine/buffers.asm"
    include "engine/vblank.asm"
    include "engine/hblank.asm"
    include "engine/controllers.asm"
    include "engine/game_loop.asm"
    include "engine/s4lz_decompress.asm"
    include "engine/zx0_decompress.asm"
    include "engine/math.asm"
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
    include "engine/player/player_sensors.asm"
    include "engine/level/section.asm"
    include "engine/level/camera.asm"
    include "engine/level/parallax.asm"
    include "engine/level/load_art.asm"
    include "engine/level/bg.asm"
    include "engine/level/bg_anim.asm"
    include "debug/compression_selftest.asm"
    ifdef SOUND_DRIVER_ENABLED
        include "engine/sound_api.asm"
    endif
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        include "debug/sound_debug.asm"
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
    include "engine/player/player_common.asm"
    include "engine/player/player_ground.asm"
    include "engine/player/player_air.asm"
    include "engine/player/player_spindash.asm"
    include "engine/player/sonic.asm"

    include "objects/test_static.asm"
    include "objects/test_animated.asm"
    include "objects/test_player.asm"
    include "objects/test_enemy.asm"
    include "objects/test_solid.asm"
    include "objects/test_particle.asm"
    include "objects/test_emitter.asm"
    include "objects/test_parent.asm"
    include "objects/test_stress_emitter.asm"
    include "objects/path_swap.asm"

    if * > $20000
      error "Object code bank overflows 64KB by \{*-$20000} bytes"
    endif

; -----------------------------------------------
; Data (outside object code bank — addressed directly, not via objroutine)
; -----------------------------------------------
__BUDGET_DATA:
    include "data/parallax/ojz_default.asm"
    include "data/parallax/ojz_windy.asm"
    ; Reusable parallax effects library — drop new effects under
    ; data/parallax/effects/ and include them here. Each file defines a
    ; deform table + ParallaxConfig_* record that any section can point
    ; at via Sec_sec_parallax_config. Must come AFTER ojz_default.asm
    ; because some effects reference DeformTable_Zero from there.
    include "data/parallax/effects/shimmer.asm"
    include "data/parallax/effects/haze.asm"
    include "data/parallax/effects/rocking.asm"
    include "data/parallax/effects/perspective.asm"
    ; Composite scenes — hand-authored configs that stack multiple effects
    ; with custom per-band gradients. Must come AFTER effects/ for the
    ; deform-table references to resolve.
    include "data/parallax/scenes/windy_haze.asm"
    include "data/parallax/scenes/sky_haze.asm"
    include "data/parallax/scenes/caves.asm"
    include "data/parallax/scenes/locked_clouds.asm"
    include "data/objdefs/test_objects.asm"
    include "data/generated/ojz/act1/entity_data.asm"
    include "data/levels/ojz/act1/act_descriptor.asm"
    include "data/mappings/test_mappings.asm"
    include "data/animations/sonic_anims.asm"
    include "data/animations/particle_anims.asm"

; -----------------------------------------------
; Collision data (§4.7 — global, shared across all zones)
; -----------------------------------------------
HeightMaps:
    BINCLUDE "data/collision/heightmaps.bin"
    align 2
HeightMapsRot:
    BINCLUDE "data/collision/heightmaps_rot.bin"
    align 2
AngleTable:
    BINCLUDE "data/collision/angles.bin"
    align 2
SolidityTable:
    BINCLUDE "data/collision/solidity.bin"
    align 2

Map_Sonic:
    BINCLUDE "data/mappings/sonic.bin"
    align 2
    if (*-Map_Sonic) > $7FFF
      error "Map_Sonic exceeds signed word-offset range"
    endif
DPLC_Sonic:
    BINCLUDE "data/dplc/optimized/sonic.bin"
    align 2
    if (*-DPLC_Sonic) > $7FFF
      error "DPLC_Sonic exceeds signed word-offset range"
    endif
Art_Sonic:
    BINCLUDE "art/optimized/characters/sonic.bin"
    align 2

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

    include "debug/error_handler.asm"

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
