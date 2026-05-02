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
; Draw_TileColumn — append one tile column from 2D cache to Plane_Buffer
; Maps cache rows to correct nametable rows using Cache_Top_Row mod 64.
; Splits into two column entries at the nametable row 63/0 boundary.
; Column entries use word-level data (VInt_DrawLevel drains with move.w).
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = world tile column
; Out: none (silently drops if buffer full)
; Clobbers: d0–d5, a0–a2
; -----------------------------------------------
Draw_TileColumn:
        ; worst case: 2 headers (8 bytes) + 64 data words (128 bytes) = 136
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #8 + PLANE_V_CELLS*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.w   .done

        cmp.w   (Cache_Left_Col).w, d1
        blt.w   .done
        cmp.w   (Cache_Head_Col).w, d1
        bgt.w   .done

        ; compute cache source pointer for cache[row=0][col]
        move.w  d0, -(sp)                     ; save nametable col
        move.w  d1, d0
        sub.w   (Cache_Left_Col).w, d0
        add.w   (Cache_Origin_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d0
.col_nowrap:
        add.w   d0, d0
        lea     (Tile_Cache_Nametable).l, a0
        adda.w  d0, a0                         ; a0 = cache source
        move.w  (sp)+, d0                      ; restore nametable col

        add.w   d0, d0                         ; d0 = col byte offset
        move.w  (Cache_Top_Row).w, d3
        andi.w  #63, d3                        ; d3 = start_nt_row

        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; === Part A: nametable rows start_nt_row to 63 ===
        move.w  d3, d1
        lsl.w   #7, d1                         ; start_nt_row × 128
        add.w   d0, d1
        addi.w  #VRAM_PLANE_A & $FFFF, d1
        move.w  d1, (a2)+                      ; VRAM addr

        move.w  #64, d5
        sub.w   d3, d5                         ; d5 = rows_A
        move.w  d5, d1
        subq.w  #1, d1
        ori.w   #$8000, d1
        move.w  d1, (a2)+                      ; word count | column flag

        move.w  d5, d4
        cmpi.w  #TILE_CACHE_ROWS, d4
        ble.s   .pA_clamp
        move.w  #TILE_CACHE_ROWS, d4
.pA_clamp:
        move.w  d4, d1
        subq.w  #1, d1
.pA_data:
        move.w  (a0), (a2)+
        lea     TILE_CACHE_STRIDE*2(a0), a0
        dbf     d1, .pA_data

        move.w  d5, d1
        sub.w   d4, d1
        beq.s   .pA_zend
        subq.w  #1, d1
.pA_zero:
        clr.w   (a2)+
        dbf     d1, .pA_zero
.pA_zend:

        ; === Part B: nametable rows 0 to start_nt_row-1 ===
        tst.w   d3
        beq.s   .no_pB

        move.w  d0, d1
        addi.w  #VRAM_PLANE_A & $FFFF, d1
        move.w  d1, (a2)+                      ; VRAM addr (row 0)

        move.w  d3, d5                         ; d5 = rows_B = start_nt_row
        move.w  d5, d1
        subq.w  #1, d1
        ori.w   #$8000, d1
        move.w  d1, (a2)+                      ; word count | column flag

        move.w  #TILE_CACHE_ROWS, d1
        sub.w   d4, d1                         ; remaining cache = 60 - data_in_A
        ble.s   .pB_allz

        cmp.w   d5, d1
        ble.s   .pB_dok
        move.w  d5, d1
.pB_dok:
        move.w  d1, d4
        subq.w  #1, d1
.pB_data:
        move.w  (a0), (a2)+
        lea     TILE_CACHE_STRIDE*2(a0), a0
        dbf     d1, .pB_data

        move.w  d5, d1
        sub.w   d4, d1
        beq.s   .pB_zend
        subq.w  #1, d1
.pB_zfill:
        clr.w   (a2)+
        dbf     d1, .pB_zfill
        bra.s   .pB_zend

.pB_allz:
        move.w  d5, d1
        subq.w  #1, d1
.pB_az:
        clr.w   (a2)+
        dbf     d1, .pB_az
.pB_zend:
.no_pB:
        move.w  #0, (a2)
        move.w  #4 + PLANE_V_CELLS*2, d2
        tst.w   d3
        beq.s   .sz_ok
        addq.w  #4, d2
.sz_ok:
        add.w   (Plane_Buffer_Ptr).w, d2
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
; Draw_TileRow_FromCache — append one tile row from 2D cache to Plane_Buffer
; In:  d0.w = target VDP nametable row (0–63)
;      d1.w = world tile row
; Out: none (silently drops if buffer full)
; Clobbers: d0–d5, a0–a2
; -----------------------------------------------
Draw_TileRow_FromCache:
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + PLANE_H_CELLS*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.w   .done

        cmp.w   (Cache_Top_Row).w, d1
        blt.w   .done
        cmp.w   (Cache_Bottom_Row).w, d1
        bgt.w   .done

        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2

        ; row header (bit 15 clear = row mode)
        lsl.w   #7, d0                         ; row × 128 (64 cols × 2 bytes)
        addi.w  #VRAM_PLANE_A & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #PLANE_H_CELLS/2 - 1, (a2)+

        ; compute source: cache nametable row
        move.w  d1, d0
        sub.w   (Cache_Top_Row).w, d0
        ; row × 80 via shift-add
        move.w  d0, d3
        lsl.w   #6, d0
        lsl.w   #4, d3
        add.w   d3, d0
        add.w   d0, d0                         ; byte offset (words → bytes)
        lea     (Tile_Cache_Nametable).l, a0
        adda.w  d0, a0                         ; a0 = start of cache row (physical col 0)

        ; Rearrange cache read so buffer matches nametable column order.
        ; World col W occupies NT col (W & 63). The row entry writes to
        ; NT col 0 first, so we start reading from the cache position
        ; whose world col maps to NT col 0: shift = (64 - start_nt_col) & 63.
        move.w  (Cache_Left_Col).w, d3
        andi.w  #63, d3                        ; d3 = start_nt_col
        move.w  #64, d4
        sub.w   d3, d4
        andi.w  #63, d4                        ; d4 = shift from origin to NT col 0

        add.w   (Cache_Origin_Col).w, d4       ; d4 = adjusted physical column
        cmp.w   #TILE_CACHE_COLS, d4
        blt.s   .adj_nowrap
        subi.w  #TILE_CACHE_COLS, d4
.adj_nowrap:
        move.w  d4, d3
        add.w   d3, d3
        adda.w  d3, a0                         ; a0 = data for NT col 0

        ; check if 64 tiles fit without wrapping in cache row
        move.w  #TILE_CACHE_COLS, d3
        sub.w   d4, d3                         ; d3 = tiles from adjusted origin to row end
        cmpi.w  #PLANE_H_CELLS, d3
        bge.s   .no_split

        ; split copy: d3 tiles before cache wrap, then (64-d3) after wrap
        move.w  d3, d5
        subq.w  #1, d5
.copy_part1:
        move.w  (a0)+, (a2)+
        dbf     d5, .copy_part1

        suba.w  #TILE_CACHE_COLS*2, a0         ; wrap to physical col 0

        move.w  #PLANE_H_CELLS, d5
        sub.w   d3, d5
        subq.w  #1, d5
.copy_part2:
        move.w  (a0)+, (a2)+
        dbf     d5, .copy_part2
        bra.s   .row_copy_done

.no_split:
        moveq   #PLANE_H_CELLS/2-1, d5
.copy_row:
        move.l  (a0)+, (a2)+
        dbf     d5, .copy_row
.row_copy_done:

        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + PLANE_H_CELLS*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w
.done:
        rts

; -----------------------------------------------
; Draw_BG_TileColumn — append one tile column strip to Plane_Buffer for plane B (§4.2).
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = section tile column index (0..63)
;      a0   = section def pointer (uses Sec_sec_bg_layout, Act fallback if NULL)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d3, a1–a2
; Note: plane B is 64×32 tiles. Strip = 32 words; header = $8000 | (32-1) = $801F.
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
        move.w  #$8000 | (32 - 1), (a2)+         ; column write, 32 words - 1

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
; Each entry: [addr.w][flags_cnt.w][data...]
;   bit 15 clear = row mode: autoinc $02, longword drain (cnt = longwords-1)
;   bit 15 set   = col mode: autoinc $80, word drain    (cnt = words-1)
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
        moveq   #0, d0
        move.w  (a0)+, d0                          ; VRAM addr (0 = end)
        beq.s   .done
        move.w  (a0)+, d1                          ; flags | count
        bmi.s   .col_entry

        ; -- ROW entry: autoincrement $02, longword drain --
        move.w  #$8F02, (a5)
        lsl.l   #2, d0
        addq.w  #1, d0
        ror.w   #2, d0
        swap    d0
        move.l  d0, (a5)
.drain_row:
        move.l  (a0)+, (a6)
        dbf     d1, .drain_row
        bra.s   .next

.col_entry:
        ; -- COL entry: autoincrement $80, word drain --
        move.w  #$8F80, (a5)
        andi.w  #$7FFF, d1
        lsl.l   #2, d0
        addq.w  #1, d0
        ror.w   #2, d0
        swap    d0
        move.l  d0, (a5)
.drain_col:
        move.w  (a0)+, (a6)
        dbf     d1, .drain_col
        bra.s   .next

.done:
        move.w  #$8F02, (a5)

.reset:
        move.w  #0, (Plane_Buffer_Ptr).w
        rts
