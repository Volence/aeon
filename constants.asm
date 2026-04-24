; Hardware constants and system definitions

; -----------------------------------------------
; Hardware addresses
; -----------------------------------------------
Z80_RAM                 = $A00000
Z80_RAM_END             = $A02000       ; 8KB
Z80_BUS_REQUEST         = $A11100
Z80_RESET               = $A11200

VDP_DATA                = $C00000
VDP_CTRL                = $C00004
VDP_HV_COUNTER          = $C00008
PSG_PORT                = $C00011

HW_VERSION              = $A10001
HW_PORT_1_DATA          = $A10003
HW_PORT_2_DATA          = $A10005
HW_PORT_EXP_DATA        = $A10007
HW_PORT_1_CTRL          = $A10009
HW_PORT_2_CTRL          = $A1000B
HW_EXPANSION_CTRL       = $A1000D
HW_PORT_A_CTRL_FULL     = $A10008
HW_EXPANSION_CTRL_FULL  = $A1000C

TMSS_REGISTER           = $A14000

YM2612_A0               = $A04000
YM2612_D0               = $A04001
YM2612_A1               = $A04002
YM2612_D1               = $A04003

; -----------------------------------------------
; VDP access type constants (for vdpComm function)
; -----------------------------------------------
VRAM                    = %100001
CRAM                    = %101011
VSRAM                   = %100101
READ                    = %001100
WRITE                   = %000111
DMA                     = %100111

; -----------------------------------------------
; System constants
; -----------------------------------------------
SYSTEM_STACK            = $FFFFFF00

; -----------------------------------------------
; VRAM layout (tile indices)
; -----------------------------------------------
VRAM_PLANE_A            = $C000         ; Byte address (tile $600)
VRAM_PLANE_B            = $E000         ; Byte address (tile $700)
VRAM_SPRITE_TABLE       = $D800
VRAM_HSCROLL_TABLE      = $DC00
VRAM_WINDOW             = $F000

; Plane size
PLANE_H_CELLS           = 64
PLANE_V_CELLS           = 64

; -----------------------------------------------
; Timing constants
; -----------------------------------------------
NTSC_TIMING_STEP        = $0100         ; 1.0 (8.8 fixed)
PAL_TIMING_STEP         = $0133         ; 1.2 (8.8 fixed, 6/5 ratio)

; -----------------------------------------------
; Controller button masks
; -----------------------------------------------
BUTTON_UP               = 1<<0          ; $01
BUTTON_DOWN             = 1<<1          ; $02
BUTTON_LEFT             = 1<<2          ; $04
BUTTON_RIGHT            = 1<<3          ; $08
BUTTON_B                = 1<<4          ; $10
BUTTON_C                = 1<<5          ; $20
BUTTON_A                = 1<<6          ; $40
BUTTON_START            = 1<<7          ; $80

; -----------------------------------------------
; CrossResetRAM
; -----------------------------------------------
CROSS_RESET_MAGIC       = 'INIT'

; -----------------------------------------------
; Game state IDs
; -----------------------------------------------
GS_BOOT                 = 0
GS_DMATEST              = 1
GS_S4LZ_TEST            = 2

; -----------------------------------------------
; DMA Queue (§1.1)
; -----------------------------------------------
DMA_CRITICAL_SLOTS      = 8
DMA_IMPORTANT_SLOTS     = 12
DMA_DEFERRABLE_SLOTS    = 12
DMA_TOTAL_SLOTS         = DMA_CRITICAL_SLOTS+DMA_IMPORTANT_SLOTS+DMA_DEFERRABLE_SLOTS

DMA_BUDGET_NTSC         = 7200          ; usable DMA bytes per NTSC VBlank
DMA_BUDGET_PAL          = 15000         ; usable DMA bytes per PAL VBlank

; -----------------------------------------------
; Decompression (§2)
; -----------------------------------------------
TILE_SIZE               = 32            ; bytes per 8x8 4bpp tile
DECOMP_BUFFER_SIZE      = 32768         ; 32KB decompression work buffer
