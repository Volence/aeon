; DPLC — Dynamic Pattern Load Cue (per-frame sprite art loading via DMA)

; -----------------------------------------------
; Perform_DPLC — load art for current mapping frame if changed
;
; DPLC table format:
;   Offset table: word per frame (offset from file start to frame data)
;   Frame data:   word entry_count, then entry_count words
;   Entry word:   bits 15-12 = tile_count-1 (1-16), bits 11-0 = tile_start
;
; With contiguous art layout (build-time optimized), each frame has
; exactly 1 DPLC entry — guaranteed single DMA per frame change.
;
; In:  a0 = SST pointer
;      a2 = DPLC table pointer (ROM)
;      a3 = uncompressed art base address (ROM)
;      d1.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
Perform_DPLC:
        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
            ifdef __DEBUG__
            beq.w   .done           ; item 6: the DPLC single-entry assert pushes .done past .s in DEBUG
            else
            beq.s   .done           ; frame unchanged, skip
            endif
        ; item 11: prev_frame is committed AFTER a successful enqueue (below), not
        ; here — QueueDMATransfer returns carry-set on a full-queue drop. d0 still
        ; holds mapping_frame for the resolve below.

        ; Resolve DPLC frame data
        andi.w  #$FF, d0
        add.w   d0, d0
        adda.w  (a2,d0.w), a2                   ; a2 = frame data pointer
        move.w  (a2)+, d4                        ; d4 = entry count
        subq.w  #1, d4
            ifdef __DEBUG__
            bmi.w   .done           ; item 6: the DPLC single-entry assert pushes .done past .s in DEBUG
            else
            bmi.s   .done           ; 0 entries
            endif
    ifdef __DEBUG__
        ; DEBUG (item 6): the contiguous-art build guarantees EXACTLY 1 DPLC entry
        ; per frame (single DMA). d4 = entry_count-1, so it must be 0 here; a
        ; nonzero count means the art layout broke the guarantee. (ifdef so the
        ; standalone AS-twin assembly, which has no debugger.asm assert macro,
        ; skips it in plain — byte-neutral: the macro is itself ifdef __DEBUG__.)
        assert.w d4, eq, #0
    endif

        move.w  d1, d2                           ; d2 = running VRAM dest

.entry_loop:
        move.w  (a2)+, d0                        ; DPLC entry word
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3                           ; d3 = tile_count - 1
        addq.w  #1, d3                           ; d3 = tile_count

        andi.l  #$0FFF, d0                       ; tile_start_index
        lsl.l   #5, d0                           ; byte offset
        move.l  a3, d1                           ; art base
        add.l   d0, d1                           ; d1.l = source address

        lsl.w   #5, d3                           ; d3.w = length (bytes)

        movem.l d2-d4/a2-a3, -(sp)
        bsr.w   QueueDMA_Important      ; LOCKSTEP dplc.emp step 2: jbsr cross-seam static call (was jsr abs.w; same 4 bytes, 4EB8→6100)
        movem.l (sp)+, d2-d4/a2-a3      ; movem preserves CCR — the carry survives
        bcs.s   .done                   ; item 11: dropped (queue full) — leave prev_frame stale, retry next frame

        add.w   d3, d2
        dbf     d4, .entry_loop
        ; All entries enqueued OK — NOW commit prev_frame (item 11). Re-read
        ; mapping_frame (unchanged this routine; d0 was consumed by the loop).
        move.b  SST_mapping_frame(a0), d0
        move.b  d0, SST_prev_frame(a0)
.done:
        rts

; -----------------------------------------------
; Perform_DPLC_Deferrable — same as Perform_DPLC but Deferrable priority
; Used for non-player objects (budget-gated, can slip one frame)
;
; In:  a0 = SST pointer
;      a2 = DPLC table pointer (ROM)
;      a3 = uncompressed art base address (ROM)
;      d1.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
Perform_DPLC_Deferrable:
        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
            ifdef __DEBUG__
            beq.w   .done           ; item 6: the DPLC single-entry assert pushes .done past .s in DEBUG
            else
            beq.s   .done           ; frame unchanged, skip
            endif
        ; item 11: prev_frame committed AFTER a successful enqueue (below), not
        ; here — QueueDMATransfer returns carry-set on a full-queue drop.

        andi.w  #$FF, d0
        add.w   d0, d0
        adda.w  (a2,d0.w), a2
        move.w  (a2)+, d4
        subq.w  #1, d4
            ifdef __DEBUG__
            bmi.w   .done           ; item 6: the DPLC single-entry assert pushes .done past .s in DEBUG
            else
            bmi.s   .done           ; 0 entries
            endif
    ifdef __DEBUG__
        ; DEBUG (item 6): the contiguous-art build guarantees EXACTLY 1 DPLC entry
        ; per frame (single DMA). d4 = entry_count-1, so it must be 0 here; a
        ; nonzero count means the art layout broke the guarantee. (ifdef so the
        ; standalone AS-twin assembly, which has no debugger.asm assert macro,
        ; skips it in plain — byte-neutral: the macro is itself ifdef __DEBUG__.)
        assert.w d4, eq, #0
    endif

        move.w  d1, d2

.entry_loop:
        move.w  (a2)+, d0
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3
        addq.w  #1, d3
        andi.l  #$0FFF, d0

        lsl.l   #5, d0
        move.l  a3, d1
        add.l   d0, d1

        lsl.w   #5, d3

        movem.l d2-d4/a2-a3, -(sp)
        bsr.w   QueueDMA_Deferrable     ; LOCKSTEP dplc.emp step 2: jbsr cross-seam static call (was jsr abs.w; same 4 bytes, 4EB8→6100)
        movem.l (sp)+, d2-d4/a2-a3      ; movem preserves CCR — the carry survives
        bcs.s   .done                   ; item 11: dropped (queue full) — leave prev_frame stale, retry next frame

        add.w   d3, d2
        dbf     d4, .entry_loop
        ; All entries enqueued OK — NOW commit prev_frame (item 11).
        move.b  SST_mapping_frame(a0), d0
        move.b  d0, SST_prev_frame(a0)
.done:
        rts
