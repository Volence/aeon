; DPLC — Dynamic Pattern Load Cue (per-frame sprite art loading via DMA)

; -----------------------------------------------
; Perform_DPLC — queue DMA for an animation frame's sprite tiles
;
; DPLC table format:
;   Offset table: word per frame (offset from file start to frame data)
;   Frame data:   word entry_count, then entry_count words
;   Entry word:   bits 15-12 = tile_count-1 (1-16), bits 11-0 = tile_start
;
; With contiguous art layout (build-time optimized), each frame has
; exactly 1 DPLC entry — guaranteed single DMA per frame change.
;
; In:  d0.w = animation frame number (0-based, word-extended)
;      a0   = DPLC table pointer (ROM)
;      a1   = uncompressed art base address (ROM)
;      d1.w = VRAM destination (byte address)
; Out: none
; Clobbers: d0-d4, a0-a2
; -----------------------------------------------
Perform_DPLC:
        add.w   d0, d0
        adda.w  (a0,d0.w), a0                  ; a0 = frame data pointer
        move.w  (a0)+, d4                       ; d4 = entry count
        subq.w  #1, d4
        bmi.s   .done                           ; 0 entries → nothing to load

        move.w  d1, d2                          ; d2 = running VRAM dest

.entry_loop:
        move.w  (a0)+, d0                       ; read DPLC entry word
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3                          ; d3 = tile_count - 1 (0-15)
        addq.w  #1, d3                          ; d3 = tile_count (1-16)

        andi.w  #$0FFF, d0                      ; d0 = tile_start_index

        ; Compute source: art_base + tile_start * 32
        lsl.w   #5, d0                          ; tile_start * 32 = byte offset
        move.l  a1, d1                          ; d1.l = art base ROM address
        add.l   d0, d1                          ; d1.l = source address (bytes)

        ; Compute length: tile_count * 32
        move.w  d3, d3
        lsl.w   #5, d3                          ; d3.w = transfer length (bytes)

        ; Queue as Important-priority DMA (character art)
        ; d1.l = source, d2.w = VRAM dest, d3.w = length
        movem.l d3-d4/a1, -(sp)
        jsr     QueueDMA_Important
        movem.l (sp)+, d3-d4/a1

        ; Advance VRAM dest for next entry
        add.w   d3, d2

        dbf     d4, .entry_loop
.done:
        rts

; -----------------------------------------------
; Perform_DPLC_Deferrable — same as above but Deferrable priority
; Used for non-player objects (budget-gated, can slip one frame)
;
; In/Out: same as Perform_DPLC
; Clobbers: d0-d4, a0-a2
; -----------------------------------------------
Perform_DPLC_Deferrable:
        add.w   d0, d0
        adda.w  (a0,d0.w), a0
        move.w  (a0)+, d4
        subq.w  #1, d4
        bmi.s   .done

        move.w  d1, d2

.entry_loop:
        move.w  (a0)+, d0
        move.w  d0, d3
        lsr.w   #8, d3
        lsr.w   #4, d3
        addq.w  #1, d3
        andi.w  #$0FFF, d0

        lsl.w   #5, d0
        move.l  a1, d1
        add.l   d0, d1

        move.w  d3, d3
        lsl.w   #5, d3

        movem.l d3-d4/a1, -(sp)
        jsr     QueueDMA_Deferrable
        movem.l (sp)+, d3-d4/a1

        add.w   d3, d2
        dbf     d4, .entry_loop
.done:
        rts
