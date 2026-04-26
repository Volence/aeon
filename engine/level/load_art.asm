; Level art loader (§2 Phase 2 A.1/A.2/A.3)
; Blocking S4LZ → DMA pipeline. A.3 reorganized loading around per-section
; pools (graph-colored) instead of global region pools.

; -----------------------------------------------
; LoadArt_S4LZ — decompress an S4LZ stream and queue Critical DMA to VRAM.
;
; In:  a0 = source ROM pointer (S4LZ stream, word-aligned)
;      d0.w = VRAM byte destination (tile-slot * 32)
; Out: a0 = past end of compressed data (returned from S4LZ_Decompress)
; Clobbers: d0–d3, a0–a3
;
; Uses Decomp_Buffer (32 KB transient at $FFFF0000). For loads exceeding
; one VBlank's DMA budget, the caller is responsible for running with
; the display blanked off so multiple Critical DMAs can drain across one
; extended VBlank.
; -----------------------------------------------
LoadArt_S4LZ:
        movem.l d4-d6/a4, -(sp)
        move.w  d0, d6                              ; d6.w = VRAM dest
        movea.l a0, a4                              ; a4 = saved source ptr (size peek)
        move.w  (a4), d4                            ; d4.w = uncompressed size (BE)

        ; -- skip the entire decompress + DMA if size is zero (placeholder blob) --
        beq.s   .return

        lea     (Decomp_Buffer).l, a1               ; a1 = work buffer
        bsr.w   S4LZ_Decompress                     ; decompress; a0 advances past stream

        move.l  #Decomp_Buffer, d1                  ; d1 = source (RAM, $FFFF0000)
        moveq   #0, d2
        move.w  d6, d2                              ; d2.w = VRAM dest
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical
        bsr.w   VSync_Wait

.return:
        movem.l (sp)+, d4-d6/a4
        rts

; -----------------------------------------------
; Section_LoadArt — load one section's tile art group.
;
; In:  a0 = Sec struct pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: each section has its own S4LZ blob and VRAM dest.
; Sections in the same color class overlay each other in VRAM as the
; camera traverses; the leapfrog system guarantees that the two
; currently-resident slots hold ADJACENT sections, which by graph-
; coloring construction are in DIFFERENT colors → DIFFERENT VRAM ranges,
; so both render correctly simultaneously.
; -----------------------------------------------
Section_LoadArt:
        moveq   #0, d0
        move.w  Sec_sec_tile_art_vram(a0), d0       ; d0.w = VRAM byte dest
        movea.l Sec_sec_tile_art_s4lz(a0), a0       ; a0 = compressed S4LZ source
        cmpa.w  #0, a0
        beq.s   .skip                               ; null pointer → no art for this section
        bra.w   LoadArt_S4LZ                        ; tail call
.skip:
        rts

; -----------------------------------------------
; Level_LoadArt — load tile art for both initial slot sections.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: walks the slot section map and calls Section_LoadArt
; for each slot's currently-assigned section. At Section_Init time, both
; slots hold the starting section + its right neighbor (per leapfrog
; convention).
; -----------------------------------------------
Level_LoadArt:
        movem.l a0/a4, -(sp)
        movea.l a0, a4                              ; a4 = act ptr (saved across calls)

        ; -- slot 0 --
        moveq   #SLOT_LEFT, d0
        movea.l a4, a2                              ; a2 = act ptr for Section_GetSlotDef
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 0
        bsr.w   Section_LoadArt

        ; -- slot 1 --
        moveq   #SLOT_RIGHT, d0
        movea.l a4, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 1
        bsr.w   Section_LoadArt

        movem.l (sp)+, a0/a4
        rts
