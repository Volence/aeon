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
; Clobbers: d0–d3, a1–a2
; -----------------------------------------------
Draw_TileColumn:
        ; -- overflow check --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2       ; header 4B + data 64B = 68B per entry
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2         ; -2 for terminator word
        bhi.s   .done

        ; -- get source strip data --
        movea.l Sec_sec_strips_a(a0), a1           ; ROM strip array
        ; col × STRIP_BYTE_SIZE (= col × 96 for 48-row strips: col*64 + col*32)
        move.w  d1, d3
        lsl.w   #6, d1                             ; d1 = col × 64
        lsl.w   #5, d3                             ; d3 = col × 32
        add.w   d3, d1                             ; d1 = col × 96 (= STRIP_BYTE_SIZE)
        adda.w  d1, a1                             ; a1 → ROM strip for this tile column

        ; -- buffer write pointer --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; -- write entry header --
        add.w   d0, d0                             ; d0 = col × 2
        addi.w  #VRAM_PLANE_A & $FFFF, d0          ; d0 = $C000 + col*2
        move.w  d0, (a2)+                          ; write VRAM addr
        ; column flag | (longword count - 1) = $8000 | (STRIP_TILE_HEIGHT/2 - 1)
        move.w  #$8000 | (STRIP_TILE_HEIGHT/2 - 1), (a2)+

        ; -- copy strip data (STRIP_TILE_HEIGHT words = STRIP_TILE_HEIGHT/2 longwords) --
        moveq   #STRIP_TILE_HEIGHT/2 - 1, d3
.copy:
        move.l  (a1)+, (a2)+
        dbf     d3, .copy

        ; -- write zero terminator (consumed by VInt_DrawLevel as end-of-buffer) --
        move.w  #0, (a2)

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
; Note: d2 must be even — odd values produce wrong tile count.
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

        ; -- write zero terminator (consumed by VInt_DrawLevel as end-of-buffer) --
        move.w  #0, (a2)

        ; -- update pointer --
        move.w  (Plane_Buffer_Ptr).w, d4
        add.w   d3, d4
        move.w  d4, (Plane_Buffer_Ptr).w

.done:
        rts

; -----------------------------------------------
; Draw_BG_TileColumn — append one tile column strip to Plane_Buffer for plane B (§4.2).
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = section tile column index (0..63)
;      a0   = section def pointer (uses Sec_sec_bg_layout, Act fallback if NULL)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d3, a1–a2
; Note: plane B is 64×32 tiles. Strip = 32 words; header = $8000 | (16-1) = $800F.
;       Source layout is row-major 64×32 — for col N, words at byte offsets
;       row*128 + N*2 for row=0..31 (stride = 64 cols * 2 B = 128).
; -----------------------------------------------
Draw_BG_TileColumn:
        ; -- overflow check (entry size = 4 + 32*2 = 68 bytes) --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.s   .done

        ; -- get source: sec_bg_layout. Fall back to act default if NULL. --
        movea.l Sec_sec_bg_layout(a0), a1
        cmpa.w  #0, a1
        bne.s   .have_layout
        movea.l (Current_Act_Ptr).w, a2
        movea.l Act_act_bg_layout(a2), a1
        cmpa.w  #0, a1
        beq.s   .done
.have_layout:
        ; -- a1 = layout base; advance by (col * 2) to point at row 0 of col --
        move.w  d1, d3
        add.w   d3, d3
        adda.w  d3, a1

        ; -- write buffer header --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2
        add.w   d0, d0
        addi.w  #VRAM_PLANE_B_BYTES & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #$8000 | (32/2 - 1), (a2)+      ; column write, 16 longwords - 1

        ; -- copy 32 words (one per row), reading column-major (stride = 128) --
        moveq   #32-1, d3
.copy:
        move.w  (a1), (a2)+
        adda.w  #128, a1
        dbf     d3, .copy

        ; -- zero terminator + buffer pointer update --
        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w

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
        lea     VDP_CTRL-VDP_DATA(a6), a5          ; a5 = VDP_CTRL

.next:
        moveq   #0, d0                             ; clear high word: lsl.l later
                                                   ; would otherwise let d0[31:16]
                                                   ; garbage corrupt CD bits
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
        lsl.l   #2, d0                             ; shift addr bits for VDP encoding
        addq.w  #1, d0                             ; VRAM WRITE lower CD bits = 1
        ror.w   #2, d0                             ; rotate lower CD bits into position 15:14
        swap    d0                                 ; d0 = 32-bit VDP WRITE command
        move.l  d0, (a5)                           ; write to VDP_CTRL

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
