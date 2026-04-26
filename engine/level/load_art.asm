; Level art loader (§2 Phase 2 A.1)
; Blocking S4LZ → DMA pipeline used at level init.

; -----------------------------------------------
; LoadArt_S4LZ — decompress an S4LZ stream and queue Critical DMA to VRAM.
;
; In:  a0 = source ROM pointer (S4LZ stream, word-aligned)
;      d0.w = VRAM byte destination (tile-slot * 32)
; Out: a0 = past end of compressed data (returned from S4LZ_Decompress)
; Clobbers: d0–d3, a0–a3
;
; Decompression target is the global Decomp_Buffer (32 KB transient at
; $FFFF0000). For levels whose compressed size exceeds one VBlank's DMA
; budget, the caller is responsible for running with the display blanked
; off so multiple Critical DMAs can drain across one extended VBlank.
; A.1's only call site (Level_LoadArt) does this.
; -----------------------------------------------
LoadArt_S4LZ:
        movem.l d4-d6/a4, -(sp)
        move.w  d0, d6                              ; d6.w = VRAM dest
        movea.l a0, a4                              ; a4 = saved source ptr (size peek)
        move.w  (a4), d4                            ; d4.w = uncompressed size (BE)

        lea     (Decomp_Buffer).l, a1               ; a1 = work buffer
        bsr.w   S4LZ_Decompress                     ; decompress; a0 advances past stream

        ; -- queue DMA: work buffer → VRAM, length = uncompressed size --
        move.l  #Decomp_Buffer, d1                  ; d1 = source (RAM, $FFFF0000)
        moveq   #0, d2
        move.w  d6, d2                              ; d2.w = VRAM dest
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical

        ; -- drain the queue this frame (display is off during level init) --
        bsr.w   VSync_Wait

        movem.l (sp)+, d4-d6/a4
        rts

; -----------------------------------------------
; Level_LoadArt — load all FG tile art for the act referenced by a0.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.2 behaviour: region 1 always loads (Act_tile_art_s4lz / Act_tile_art_vram).
; Region 2 loads only when Act_tile_art_r2_s4lz is non-null AND the S4LZ
; stream's uncompressed-size header is non-zero. Region 2's VRAM destination
; is the engine constant REGION2_VRAM_BASE.
; -----------------------------------------------
Level_LoadArt:
        movea.l a0, a4                              ; a4 = act ptr (saved across LoadArt_S4LZ)

        ; -- region 1 (always) --
        moveq   #0, d0
        move.w  Act_tile_art_vram(a4), d0           ; d0.w = VRAM byte dest
        movea.l Act_tile_art_s4lz(a4), a0           ; a0 = compressed S4LZ source
        bsr.w   LoadArt_S4LZ

        ; -- region 2 (skip if pointer null) --
        movea.l Act_tile_art_r2_s4lz(a4), a0
        cmpa.w  #0, a0
        beq.s   .done

        ; -- skip if uncompressed-size header is zero (placeholder no-spill blob) --
        move.w  (a0), d4
        beq.s   .done

        move.w  #REGION2_VRAM_BASE, d0              ; d0.w = region 2 VRAM byte dest
        bra.w   LoadArt_S4LZ                        ; tail call

.done:
        rts
