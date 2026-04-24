; RAM layout via phase/dephase
; Upper 32KB ($FFFF8000+) uses .w addressing for speed

        phase $FFFF8000

RAM_Start:

; -----------------------------------------------
; System
; -----------------------------------------------
VBlank_Flag:            ds.b 1
                        ds.b 1
Frame_Counter:          ds.w 1
Game_State:             ds.l 1
Game_State_ID:          ds.b 1
Game_State_Init:        ds.b 1

; -----------------------------------------------
; VDP Shadow Table (§0.4)
; -----------------------------------------------
VDP_Shadow_Table:       ds.b VDP_Shadow_len
                        ds.b 1          ; pad to even
VDP_Dirty_Mask:         ds.l 1          ; bits 0-18 for regs $00-$12

; -----------------------------------------------
; Interrupt dispatch
; -----------------------------------------------
HBlank_Handler_Ptr:     ds.l 1

; -----------------------------------------------
; Region detection (§0.8)
; -----------------------------------------------
Hardware_Region:        ds.b 1
Region_Flags:           ds.b 1
Timing_Step:            ds.w 1
Frame_Accumulator:      ds.w 1

; -----------------------------------------------
; Controllers
; -----------------------------------------------
Ctrl_1_Held:            ds.b 1
Ctrl_1_Press:           ds.b 1
Ctrl_2_Held:            ds.b 1
Ctrl_2_Press:           ds.b 1

; -----------------------------------------------
; RNG
; -----------------------------------------------
RNG_Seed:               ds.l 1

RAM_End:

        if RAM_End >= SYSTEM_STACK
          error "RAM overflow into stack by \{RAM_End - SYSTEM_STACK} bytes!"
        endif

; -----------------------------------------------
; CrossResetRAM (fixed address near top of RAM)
; Survives soft reset, cleared only on cold boot
; -----------------------------------------------
CrossResetRAM:          = $FFFFFE00
Cross_Reset_Magic_Addr: = $FFFFFE00
Cross_Reset_Magic_End:  = $FFFFFE04
CrossResetRAM_End:      = $FFFFFF00

        dephase
