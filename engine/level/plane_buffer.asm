; Deferred nametable plane buffer (§4.1)
; Producer: Draw_TileColumn / Draw_TileRow (game loop)
; Consumer: VInt_DrawLevel (VBlank)

; -----------------------------------------------
; Plane_Buffer_Reset — clear buffer (call each frame after drain)
; Clobbers: none
; -----------------------------------------------
Plane_Buffer_Reset:
        move.w  #0, (Plane_Buffer_Ptr).w
        rts

; -----------------------------------------------
; Draw_TileColumn — append one tile column strip to Plane_Buffer
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = section tile column index (0-based from section left edge)
;      a0   = section def pointer (Sec struct in ROM)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d3, a0–a2
; -----------------------------------------------
Draw_TileColumn:
        ; -- overflow check --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2       ; header 4B + data 64B = 68B per entry
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2         ; -2 for terminator word
        bhi.s   .done

        ; -- get source strip data --
        movea.l Sec_sec_strips_a(a0), a1           ; ROM strip array
        lsl.w   #6, d1                             ; d1 = section_col × 64 bytes
        adda.w  d1, a1                             ; a1 → ROM strip for this tile column

        ; -- buffer write pointer --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; -- write entry header --
        add.w   d0, d0                             ; d0 = col × 2
        addi.w  #VRAM_PLANE_A & $FFFF, d0          ; d0 = $C000 + col*2
        move.w  d0, (a2)+                          ; write VRAM addr
        move.w  #$800F, (a2)+                      ; column flag | (32/2-1 = 15)

        ; -- copy strip data (32 words = 16 longwords) --
        moveq   #16-1, d3
.copy:
        move.l  (a1)+, (a2)+
        dbf     d3, .copy

        ; -- update buffer pointer --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w

.done:
        rts

; -----------------------------------------------
; Draw_TileRow — append one tile row to Plane_Buffer
; In:  d0.w = target VDP nametable row (0–63)
;      d2.w = number of tiles to write
;      a1   = ROM pointer to row tile data (d2 consecutive words)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d4, a1–a2
; Note: not called in Phase 1 (no vertical scroll). Exists for Phase 2+.
; -----------------------------------------------
Draw_TileRow:
        ; -- entry size = 4 + d2*2 bytes --
        move.w  d2, d3
        add.w   d3, d3                             ; d3 = d2*2 bytes of data
        addq.w  #4, d3                             ; +4 header
        move.w  (Plane_Buffer_Ptr).w, d4
        add.w   d3, d4
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d4
        bhi.s   .done

        ; -- buffer write pointer --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; -- write header --
        lsl.w   #7, d0                             ; d0 = row × 128
        addi.w  #VRAM_PLANE_A & $FFFF, d0
        move.w  d0, (a2)+                          ; VRAM addr
        move.w  d2, d0
        lsr.w   #1, d0
        subq.w  #1, d0                             ; cnt = words/2 - 1
        move.w  d0, (a2)+

        ; -- copy row data --
        move.w  d2, d0
        lsr.w   #1, d0
        subq.w  #1, d0
.copy:
        move.l  (a1)+, (a2)+
        dbf     d0, .copy

        ; -- update pointer --
        move.w  (Plane_Buffer_Ptr).w, d4
        add.w   d3, d4
        move.w  d4, (Plane_Buffer_Ptr).w

.done:
        rts

; -----------------------------------------------
; VInt_DrawLevel — drain Plane_Buffer entries to VDP (called from VBlank)
; Each entry: [addr.w][flags_cnt.w][data words...]
; addr=0 terminates.
; Called with Z80 already stopped by VInt_Level / VInt_Lag.
; Clobbers: d0–d1, a0, a5–a6
; -----------------------------------------------
VInt_DrawLevel:
        tst.w   (Plane_Buffer_Ptr).w
        beq.s   .reset                             ; nothing to draw

        lea     (Plane_Buffer).w, a0
        lea     (VDP_DATA).l, a6
        lea     VDP_CTRL-VDP_DATA(a6), a5          ; a5 = VDP_CTRL (register, no lint hit)

.next:
        move.w  (a0)+, d0                          ; VRAM addr (0 = end)
        beq.s   .done
        move.w  (a0)+, d1                          ; flags | count

        ; -- set autoincrement based on flag --
        bmi.s   .col_write
        ; row write: autoincrement = $02
        move.w  #$8F02, (a5)
        andi.w  #$7FFF, d1
        bra.s   .write
.col_write:
        ; column write: autoincrement = $80 (one row stride in 64-wide plane)
        move.w  #$8F80, (a5)
        andi.w  #$7FFF, d1

.write:
        ; -- reconstruct 32-bit VDP write command from 16-bit addr --
        swap    d0
        clr.w   d0
        swap    d0
        lsl.l   #2, d0
        lsr.w   #2, d0
        ori.w   #vdpComm(0,VRAM,WRITE) & $FFFF, d0
        swap    d0
        move.l  d0, (a5)                           ; send VDP write command

        ; -- write d1+1 longwords --
.drain:
        move.l  (a0)+, (a6)
        dbf     d1, .drain

        bra.s   .next

.done:
        ; restore normal autoincrement
        move.w  #$8F02, (a5)

.reset:
        move.w  #0, (Plane_Buffer_Ptr).w
        rts
