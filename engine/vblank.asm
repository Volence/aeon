; VBlank handler and VSync synchronization

; -----------------------------------------------
; VBlank_Handler — IRQ6, fires once per frame (§0.10)
; -----------------------------------------------
VBlank_Handler:
        movem.l d0-a6, -(sp)

        move.b  #1, (VBlank_Flag).w

        ; Phase 1: Time-critical VDP work
        bsr.w   Flush_VDP_Shadow
        bsr.w   DMA_Queue_Drain_Stub
        bsr.w   Sprite_Table_Upload_Stub

        ; Phase 2: I/O
        bsr.w   Read_Controllers_Stub

        ; Phase 3: Sound
        bsr.w   Sound_Update_Stub

        ; Phase 4: Frame tracking
        addq.w  #1, (Frame_Counter).w

        movem.l (sp)+, d0-a6
        rte

; -----------------------------------------------
; Stubs for systems not yet implemented
; Replaced by real routines as systems are built
; -----------------------------------------------
DMA_Queue_Drain_Stub:
        rts

Sprite_Table_Upload_Stub:
        rts

Read_Controllers_Stub:
        rts

Sound_Update_Stub:
        rts

; -----------------------------------------------
; VSync_Wait — block until VBlank fires
; In:  none
; Out: none
; Clobbers: none
; -----------------------------------------------
VSync_Wait:
.wait:
        tst.b   (VBlank_Flag).w
        beq.s   .wait
        clr.b   (VBlank_Flag).w
        rts

