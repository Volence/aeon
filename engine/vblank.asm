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

        bsr.w   Enqueue_Dirty_Buffers   ; queues palette + sprites + HScroll (§4.6)

        bsr.w   VInt_DrawLevel          ; drain Plane_Buffer to VDP (§4.1)

        bsr.w   Process_DMA_Critical    ; drains palette + sprites + HScroll

        ; §4.6: VSRAM write must come AFTER HScroll DMA (CODING_CONVENTIONS §3.4)
        bsr.w   Vscroll_Write

        move.w  (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
        bsr.w   Process_DMA_Important
        bsr.w   Process_DMA_Deferrable

        startZ80

        ; --- Non-VDP work ---
        bsr.w   Read_Controllers
        ; Latch accumulated press edges for the upcoming logic tick.
        ; Lag VBlanks only OR into the accumulator, so a press landing in
        ; ANY lag frame survives into the next tick's latch (consume-once,
        ; zero race: this runs in interrupt context while the main loop is
        ; parked in VSync_Wait).
        move.b  (Ctrl_1_Press_Accum).w, (Ctrl_1_Press).w
        clr.b   (Ctrl_1_Press_Accum).w
        move.b  (Ctrl_2_Press_Accum).w, (Ctrl_2_Press).w
        clr.b   (Ctrl_2_Press_Accum).w
        addq.w  #1, (Frame_Counter).w
        move.b  #1, (VBlank_Flag).w

    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        ; Snapshot Z80 mailbox+status into 68k RAM for MCP inspection.
        ; Does its own stopZ80/startZ80 — placed after the DMA stop window
        ; (and after Read_Controllers) so d0/a0/a1 are free to clobber.
        bsr.w   Sound_DebugMirror
      endif
    endif
        rts

; -----------------------------------------------
; VInt_Lag — minimal handler (lag frames)
; Critical DMA only. Important/Deferrable entries persist.
; -----------------------------------------------
VInt_Lag:
        stopZ80

        bsr.w   Flush_VDP_Shadow
        bsr.w   Enqueue_Dirty_Buffers
        bsr.w   VInt_DrawLevel
        bsr.w   Process_DMA_Critical
        bsr.w   Vscroll_Write           ; §4.6 — after Critical DMA

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
        ; Clear any STALE VBlank_Flag first — VInt_Lag (which fires when
        ; VBlank_Ready=0) sets VBlank_Flag, so a long pre-Wait operation
        ; (e.g., S4LZ_Decompress) can leave the flag set from a previous
        ; lag-frame VBlank. Without this clear, VSync_Wait returns
        ; immediately and the queued Critical DMA never drains before the
        ; CALLER overwrites the source buffer (Decomp_Buffer).
        moveq   #0, d0
        move.b  d0, (VBlank_Flag).w
        move.b  #1, (VBlank_Ready).w
.wait:
        tst.b   (VBlank_Flag).w
        beq.s   .wait
        move.b  d0, (VBlank_Flag).w
    ifdef __DEBUG__
        move.w  d0, (DMA_Bytes_ThisFrame).w
    endif
        rts
