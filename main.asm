; Sonic 4 Engine — main assembly file
    cpu 68000
    padding off
    supmode on

; -----------------------------------------------
; Assembly options
; -----------------------------------------------
padToPowerOfTwo         = 1

; -----------------------------------------------
; Definitions (no ROM output)
; -----------------------------------------------
    include "constants.asm"
    include "structs.asm"
    include "macros.asm"
    include "ram.asm"
    include "debug/debugger.asm"

; -----------------------------------------------
; ROM image
; -----------------------------------------------
    org 0

; -----------------------------------------------
; Vector Table ($000000 - $0000FF)
; -----------------------------------------------
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
    include "engine/boot.asm"
    include "engine/vdp_init.asm"
    include "engine/dma_queue.asm"
    include "engine/buffers.asm"
    include "engine/vblank.asm"
    include "engine/hblank.asm"
    include "engine/controllers.asm"
    include "engine/game_loop.asm"
    include "engine/s4lz_decompress.asm"
    include "engine/dplc.asm"
    include "engine/objects.asm"
    include "engine/sprites.asm"
    include "engine/animate.asm"
    include "engine/collision.asm"
    include "engine/children.asm"
    include "engine/load_object.asm"

; -----------------------------------------------
; Object code bank
; All object routines must live within this 64KB block.
; objroutine() computes offsets from ObjCodeBase.
; -----------------------------------------------
    org $10000
ObjCodeBase:
    rts                         ; offset 0 = empty slot safety net

    include "objects/test_static.asm"
    include "objects/test_animated.asm"
    include "objects/test_player.asm"
    include "objects/test_enemy.asm"
    include "objects/test_solid.asm"

; -----------------------------------------------
; Data (outside object code bank — addressed directly, not via objroutine)
; -----------------------------------------------
    include "data/mappings/test_mappings.asm"
    include "data/animations/sonic_anims.asm"
    include "data/objdefs/test_objects.asm"

Map_Sonic:
    BINCLUDE "data/mappings/sonic.bin"
    align 2
DPLC_Sonic:
    BINCLUDE "data/dplc/optimized/sonic.bin"
    align 2
Art_Sonic:
    BINCLUDE "art/optimized/characters/sonic.bin"
    align 2

; -----------------------------------------------
; Test game states
; -----------------------------------------------
    include "test/object_test_state.asm"

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
