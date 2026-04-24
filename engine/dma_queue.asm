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
