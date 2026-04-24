; DMA queue — 3-priority sub-queue system with Flamewing Ultra format

; -----------------------------------------------
; Init_DMA_Queue — pre-fill all 32 slots with VDP register markers
; Called once at boot. Uses rept to unroll at assembly time.
; In:  none
; Out: none
; Clobbers: d0-d1, a0
; -----------------------------------------------
Init_DMA_Queue:
        lea     (DMA_Queue).w, a0
        moveq   #-$6C, d0                      ; $94 sign-extended
        move.l  #$93979695, d1

    set .c, 0
    rept DMA_TOTAL_SLOTS
        move.b  d0, .c+DMAEntry_Reg94(a0)
        movep.l d1, .c+DMAEntry_Reg93(a0)
    set .c, .c+DMAEntry_len
    endr

        move.w  #DMA_Critical, (DMA_Critical_Slot).w
        move.w  #DMA_Important, (DMA_Important_Slot).w
        move.w  #DMA_Deferrable, (DMA_Deferrable_Slot).w
        rts

; -----------------------------------------------
; QueueDMA_Critical / QueueDMA_Important / QueueDMA_Deferrable
; Entry points that select the target sub-queue, then fall
; through to the shared QueueDMATransfer core.
;
; In:  d1.l = source address (bytes, even)
;      d2.w = VRAM destination (byte address)
;      d3.w = transfer length (bytes, even, non-zero)
; Out: none (carry set = queue was full)
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
QueueDMA_Critical:
        lea     (DMA_Critical_Slot).w, a2
        move.w  #DMA_Critical_End, d4
        bra.s   QueueDMATransfer

QueueDMA_Important:
        lea     (DMA_Important_Slot).w, a2
        move.w  #DMA_Important_End, d4
        bra.s   QueueDMATransfer

QueueDMA_Deferrable:
        lea     (DMA_Deferrable_Slot).w, a2
        move.w  #DMA_Deferrable_End, d4

; -----------------------------------------------
; QueueDMATransfer — shared enqueue core
; In:  d1.l = source (bytes), d2.w = dest, d3.w = length (bytes)
;      a2 = pointer to slot variable, d4.w = queue end address
; -----------------------------------------------
QueueDMATransfer:
        move.w  sr, -(sp)
        disableInts
        movea.w (a2), a1
        cmpa.w  d4, a1
        beq.s   .full

        lsr.l   #1, d1                          ; source to words
        bclr.l  #23, d1                         ; RAM source safety
        movep.l d1, DMAEntry_SizeL(a1)          ; source → offsets 3,5,7,9

        lsr.w   #1, d3                          ; length to words
        movep.w d3, DMAEntry_SizeH(a1)          ; length → offsets 1,3 (overwrites junk at 3)

        moveq   #0, d0
        move.w  d2, d0
        vdpCommReg d0, VRAM, DMA, 0
        move.l  d0, DMAEntry_Command(a1)

        lea     DMAEntry_len(a1), a1
        move.w  a1, (a2)

        move.w  (sp)+, sr
        rts

.full:
    ifdef __DEBUG__
        addq.w  #1, (DMA_Overflow_Count).w
    endif
        move.w  (sp)+, sr
        rts
