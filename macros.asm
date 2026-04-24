; AS functions, macros, and compile-time utilities

; -----------------------------------------------
; AS functions — build-time computation
; -----------------------------------------------

; VDP command word generation
vdpComm     function addr,type,rwd, \
              (((type & rwd) & 3) << 30) | ((addr & $3FFF) << 16) | (((type & rwd) & $FC) << 2) | ((addr & $C000) >> 14)

; VDP register command
vdpReg      function reg,val, ($8000 | ((reg) << 8) | (val))

; Art tile encoding
vram_art    function tile,pal,pri, (pri<<15)|(pal<<13)|tile

; Tile index to VDP byte address
vram_bytes  function tile, tile<<5

; Sprite size encoding (width/height in cells, 1-4)
sprSize     function w,h, ((((h)-1)<<2)|((w)-1))<<8

; Byte count to longword loop count (for dbf)
bytesToLcnt function n, (n)/4-1

; -----------------------------------------------
; Struct macros
; -----------------------------------------------
; AS has built-in struct/endstruct:
;   Label struct / Label endstruct
; Auto-generates Label_len. No custom macros needed.

; -----------------------------------------------
; Hardware control macros
; -----------------------------------------------

stopZ80 macro
        move.w  #$0100, (Z80_BUS_REQUEST).l
.wait_z80:
        btst    #0, (Z80_BUS_REQUEST).l
        bne.s   .wait_z80
        endm

startZ80 macro
        move.w  #$0000, (Z80_BUS_REQUEST).l
        endm

disableInts macro
        move.w  #$2700, sr
        endm

enableInts macro
        move.w  #$2300, sr
        endm

; -----------------------------------------------
; VDP shadow table write-through
; -----------------------------------------------

; SetVDPReg — write to shadow table + mark dirty
; \1 = register number (0-18), \2 = value (register or immediate)
SetVDPReg macro
        move.b  \2, VDP_Shadow_Table+\1
        ori.l   #(1<<\1), (VDP_Dirty_Mask).w
        endm

; -----------------------------------------------
; Debug subsystem flags (only meaningful when __DEBUG__ is defined)
; Use the MD Debugger's ifdebug macro (from debug/debugger.asm) for conditionals.
; -----------------------------------------------
DEBUG_ALL               = 0
DEBUG_DMA               = 0 | DEBUG_ALL
DEBUG_VRAM              = 0 | DEBUG_ALL
DEBUG_OBJECTS            = 0 | DEBUG_ALL
DEBUG_COLLISION         = 0 | DEBUG_ALL
