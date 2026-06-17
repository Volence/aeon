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
    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_DebugMirror       ; always-run snapshot (any game state)
      endif
    endif
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
        ; --- VDP work ---
        ; Sound (MegaPCM-2 model): when the Z80 sound driver is enabled we do NOT
        ; stop the Z80 during the VDP/DMA pipeline. Instead we raise a FLAG BRACKET
        ; around the whole VDP/DMA window: SND_CTRL_DMA_ACTIVE=1 here at the very
        ; top (before ANY VDP work), cleared =0 after the last DMA below. The Z80
        ; producer checks this flag every sample and takes its DRAIN path (feeds
        ; the DAC from the RAM ring with NO ROM read) for as long as the flag is
        ; set — so a banked ROM read can never land inside a DMA burst and stall
        ; the Z80 bus (the under-load pitch sag). The brief bus-held byte write is
        ; the ONLY 68k stopZ80 in the sound build; the DMA pipeline itself runs
        ; with the Z80 free. The OFF build keeps the original full-DMA Z80 fence.
    ifdef SOUND_DRIVER_ENABLED
        stopZ80
        move.b  #1, (SND_Z80_BASE+SND_CTRL_DMA_ACTIVE).l   ; raise: DMA window open (Z80 -> DRAIN)
        startZ80
    endif
    ifndef SOUND_DRIVER_ENABLED
        stopZ80
    endif

        bsr.w   Flush_VDP_Shadow

        bsr.w   Enqueue_Dirty_Buffers   ; queues palette + sprites + HScroll (§4.6)

        bsr.w   VInt_DrawLevel          ; drain Plane_Buffer to VDP (§4.1)

        bsr.w   Process_DMA_Critical    ; drains palette + sprites + HScroll

        ; §4.6: VSRAM write must come AFTER HScroll DMA (CODING_CONVENTIONS §3.4)
        bsr.w   Vscroll_Write

        move.w  (DMA_Budget_Default).w, (DMA_Budget_Remaining).w
        bsr.w   Process_DMA_Important
        bsr.w   Process_DMA_Deferrable

    ifndef SOUND_DRIVER_ENABLED
        startZ80
    endif

        ; Sound (flag bracket close): the VDP/DMA window is finished — ROM is safe
        ; to read again. Clear SND_CTRL_DMA_ACTIVE=0 so the Z80 producer leaves its
        ; DRAIN path and resumes FILL read-ahead. Net: the flag was 1 for the
        ; whole VDP/DMA window. Brief bus-held write (the only 68k stopZ80 in the
        ; sound build); the DMA pipeline above ran with the Z80 free.
    ifdef SOUND_DRIVER_ENABLED
        stopZ80
        move.b  #0, (SND_Z80_BASE+SND_CTRL_DMA_ACTIVE).l   ; lower: DMA window closed (Z80 -> FILL)
        startZ80
    endif

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
        rts

; -----------------------------------------------
; VInt_Lag — minimal handler (lag frames)
; Critical DMA only. Important/Deferrable entries persist.
; -----------------------------------------------
VInt_Lag:
        ; Sound (flag bracket): see VInt_Level — raise SND_CTRL_DMA_ACTIVE=1 at the
        ; very top (before any VDP work) so the Z80 producer takes its DRAIN path
        ; for the whole VDP/DMA window; cleared =0 after the last DMA below. OFF
        ; build keeps the original full-DMA Z80 fence.
    ifdef SOUND_DRIVER_ENABLED
        stopZ80
        move.b  #1, (SND_Z80_BASE+SND_CTRL_DMA_ACTIVE).l   ; raise: DMA window open (Z80 -> DRAIN)
        startZ80
    endif
    ifndef SOUND_DRIVER_ENABLED
        stopZ80
    endif

        bsr.w   Flush_VDP_Shadow
        bsr.w   Enqueue_Dirty_Buffers
        bsr.w   VInt_DrawLevel
        bsr.w   Process_DMA_Critical
        bsr.w   Vscroll_Write           ; §4.6 — after Critical DMA

    ifndef SOUND_DRIVER_ENABLED
        startZ80
    endif

        ; Sound (flag bracket close): VDP/DMA window finished — clear the flag so
        ; the Z80 producer resumes FILL read-ahead (see VInt_Level).
    ifdef SOUND_DRIVER_ENABLED
        stopZ80
        move.b  #0, (SND_Z80_BASE+SND_CTRL_DMA_ACTIVE).l   ; lower: DMA window closed (Z80 -> FILL)
        startZ80
    endif

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
