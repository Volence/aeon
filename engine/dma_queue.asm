; DMA queue — 3-priority sub-queue system with movep-interleaved format

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

        ; 128KB boundary check (sub+sub approach).
        ; Detects if (source_words.w + length_words.w) > $10000,
        ; i.e. the DMA crosses a 128KB byte boundary.
        moveq   #0, d0
        sub.w   d3, d0
        sub.w   d1, d0
        blo.s   .split                          ; carry = crosses boundary

        ; No crossing — write length and finish
        movep.w d3, DMAEntry_SizeH(a1)          ; length → offsets 1,3

.finish_entry:
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

        ; --- 128KB boundary split ---
        ; Split the transfer into two queue entries: one up to the boundary,
        ; one for the remainder. Both go to the same sub-queue.
.split:
        add.w   d3, d0                          ; d0 = words until 128KB boundary
        movep.w d0, DMAEntry_SizeH(a1)         ; write first part length

        ; Need two free slots — check room for second entry
        subi.w  #DMAEntry_len, d4               ; d4 = start of last slot
        cmpa.w  d4, a1
        bhs.s   .finish_entry                   ; only one slot — finish first part

        ; Second part parameters
        sub.w   d0, d3                          ; d3 = second part length (words)
        add.l   d0, d1                          ; d1 = second part source (words)
        add.w   d0, d0                          ; d0 = first part length (bytes)
        add.w   d2, d0                          ; d0 = second part VRAM dest

        ; Finish first entry with original destination
        vdpCommReg d2, VRAM, DMA, 1             ; d2 → VDP command (clr=1, upper word unknown)
        move.l  d2, DMAEntry_Command(a1)

        ; Write second entry into next slot
        movep.l d1, DMAEntry_len+DMAEntry_SizeL(a1)
        movep.w d3, DMAEntry_len+DMAEntry_SizeH(a1)

        ; Second entry VDP command — d0 upper word known zero
        vdpCommReg d0, VRAM, DMA, 0
        lea     DMAEntry_len+DMAEntry_Command(a1), a1
        move.l  d0, (a1)+
        move.w  a1, (a2)

        move.w  (sp)+, sr
        rts

; -----------------------------------------------
; Process_DMA_Critical — drain Critical queue via jump table
; Zero branches per entry. ~64 cycles/entry, ~514 for all 8.
; Jump-table drain — zero branches per entry.
; In:  none
; Out: none
; Clobbers: a1, a5
; -----------------------------------------------
Process_DMA_Critical:
        movea.w (DMA_Critical_Slot).w, a1
        suba.w  #DMA_Critical, a1               ; a1 = byte offset into queue
        jmp     .jump_table(a1)

.jump_table:
        bra.w   .done
        rept 5
        trap    #0
        endr

    set .c, 1
    rept DMA_CRITICAL_SLOTS
        lea     (VDP_CTRL).l, a5
        lea     (DMA_Critical).w, a1
    if .c <> DMA_CRITICAL_SLOTS
        bra.w   .drain_end-.c*8
    endif
    set .c, .c+1
    endr

    rept DMA_CRITICAL_SLOTS
        move.l  (a1)+, (a5)
        move.l  (a1)+, (a5)
        move.l  (a1)+, (a5)
        move.w  (a1)+, (a5)
    endr

.drain_end:
        move.w  #DMA_Critical, (DMA_Critical_Slot).w
.done:
        rts

; -----------------------------------------------
; Process_DMA_Important — drain Important queue with byte budget
; In:  none (reads DMA_Budget_Remaining)
; Out: none
; Clobbers: d0-d1, a0-a3, a5
; -----------------------------------------------
Process_DMA_Important:
        movea.w (DMA_Important_Slot).w, a1
        lea     (DMA_Important).w, a0
        cmpa.l  a0, a1
        bls.s   .done
        lea     (DMA_Important_Slot).w, a2
        bra.s   Drain_Budgeted_Queue            ; tail call — updates slot var
.done:
        rts

; -----------------------------------------------
; Process_DMA_Deferrable — drain Deferrable queue with byte budget
; In:  none (reads DMA_Budget_Remaining)
; Out: none
; Clobbers: d0-d1, a0-a3, a5
; -----------------------------------------------
Process_DMA_Deferrable:
        movea.w (DMA_Deferrable_Slot).w, a1
        lea     (DMA_Deferrable).w, a0
        cmpa.l  a0, a1
        bls.s   .done
        lea     (DMA_Deferrable_Slot).w, a2
        bra.s   Drain_Budgeted_Queue            ; tail call — updates slot var
.done:
        rts

; -----------------------------------------------
; Drain_Budgeted_Queue — shared loop for Important/Deferrable
; Entries that don't fit this frame's budget are COMPACTED to the
; queue base and persist to the next frame (consumers like
; Perform_DPLC queue once and rely on eventual delivery —
; discarding meant stale art).
; In:  a0 = queue start, a1 = slot pointer value (first free)
;      a2 = slot variable address
;      DMA_Budget_Remaining must be set
; Out: slot variable updated (base if fully drained,
;      base + survivors after compaction, unchanged if nothing drained)
; Clobbers: d0-d1, a0-a1, a3, a5
; -----------------------------------------------
Drain_Budgeted_Queue:
        lea     (VDP_CTRL).l, a5
        movea.l a0, a3                          ; a3 = queue base
.loop:
        move.w  (DMA_Budget_Remaining).w, d0
        ble.s   .out_of_budget
        movep.w DMAEntry_SizeH(a0), d1          ; read size in words
        add.w   d1, d1                          ; words -> bytes
        sub.w   d1, (DMA_Budget_Remaining).w
        move.l  (a0)+, (a5)
        move.l  (a0)+, (a5)
        move.l  (a0)+, (a5)
        move.w  (a0)+, (a5)
        cmpa.l  a0, a1
        bhi.s   .loop
        move.w  a3, (a2)                        ; fully drained — slot = base
        rts

.out_of_budget:
        cmpa.l  a0, a3
        beq.s   .no_drain                       ; nothing sent — slot already correct
.compact:
        move.l  (a0)+, (a3)+                    ; src always above dst — safe forward copy
        move.l  (a0)+, (a3)+
        move.l  (a0)+, (a3)+
        move.w  (a0)+, (a3)+
        cmpa.l  a0, a1
        bhi.s   .compact
        move.w  a3, (a2)                        ; slot = base + surviving entries
.no_drain:
        rts
