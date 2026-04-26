; VBlank handler with function pointer dispatch and lag detection (§1.2)

; -----------------------------------------------
; VBlank_Handler — IRQ6 entry point
; Dispatches through VInt_Ptr on normal frames,
; VInt_Lag when main loop hasn't finished.
; -----------------------------------------------
VBlank_Handler:
        movem.l d0-a6, -(sp)
        tst.b   (VBlank_Ready).w
        beq.s   .lag
        movea.l (VInt_Ptr).w, a0
        jsr     (a0)
        bra.s   .done
.lag:
        bsr.w   VInt_Lag
.done:
        moveq   #0, d0
        move.b  d0, (VBlank_Ready).w
        movem.l (sp)+, d0-a6
        rte

; -----------------------------------------------
; VInt_Level — full pipeline handler (normal frames)
; Execution order: shadow flush -> VSRAM -> dirty enqueue ->
;   Critical drain -> budget -> Important drain -> Deferrable drain ->
;   controllers -> frame counter -> VBlank flag
; -----------------------------------------------
VInt_Level:
        ; --- VDP work (Z80 stopped) ---
        stopZ80

        bsr.w   Flush_VDP_Shadow

        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l

        bsr.w   Enqueue_Dirty_Buffers

        bsr.w   VInt_DrawLevel          ; drain Plane_Buffer to VDP (§4.1)

        bsr.w   Process_DMA_Critical

        move.w  (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
        bsr.w   Process_DMA_Important
        bsr.w   Process_DMA_Deferrable

        startZ80

        ; --- Non-VDP work ---
        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w
        rts

; -----------------------------------------------
; VInt_Lag — minimal handler (lag frames)
; Critical DMA only. Important/Deferrable entries persist.
; -----------------------------------------------
VInt_Lag:
        stopZ80

        bsr.w   Flush_VDP_Shadow

        move.l  #vdpComm(0, VSRAM, WRITE), (VDP_CTRL).l
        move.l  (Vscroll_Factor).w, (VDP_DATA).l

        bsr.w   Enqueue_Dirty_Buffers
        bsr.w   VInt_DrawLevel
        bsr.w   Process_DMA_Critical

        startZ80

        bsr.w   Read_Controllers
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w

    ifdef __DEBUG__
        addq.l  #1, (Lag_Frame_Count).w
    endif
        rts

; -----------------------------------------------
; VSync_Wait — block until VBlank fires (§1.2.5)
; In:  none
; Out: none
; Clobbers: d0
; -----------------------------------------------
VSync_Wait:
        move.b  #1, (VBlank_Ready).w
.wait:
        tst.b   (VBlank_Flag).w
        beq.s   .wait
        moveq   #0, d0
        move.b  d0, (VBlank_Flag).w
    ifdef __DEBUG__
        move.w  d0, (DMA_Bytes_ThisFrame).w
    endif
        rts
