; Deferred nametable plane buffer (§4.1)
; Producers: Draw_TileColumn / Draw_TileRow_FromCache (game loop)
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
; Clobbers: d0–d5, a0–a2 (a1 = row-wrap sentinel through both parts)
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

        ; compute cache source pointer for cache[logical row 0][col]
        ; = physical row Cache_Origin_Row (circular)
        move.w  d0, -(sp)                     ; save nametable col
        move.w  d1, d0
        sub.w   (Cache_Left_Col).w, d0
        add.w   (Cache_Origin_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d0
.col_nowrap:
        add.w   d0, d0
        move.w  (Cache_Origin_Row).w, d1
        move.w  d1, d2
        lsl.w   #7, d1                         ; × 128
        lsl.w   #5, d2                         ; × 32
        add.w   d2, d1                         ; origin_row × 160 (stride bytes)
        add.w   d1, d0
        lea     (Tile_Cache_Nametable).l, a0
        adda.w  d0, a0                         ; a0 = cache source
        lea     (Tile_Cache_Nametable+TILE_CACHE_NT_SIZE).l, a1   ; wrap sentinel
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
        cmpa.l  a1, a0
        blo.s   .pa_nowrap
        suba.w  #TILE_CACHE_NT_SIZE, a0        ; physical row 59 → 0
.pa_nowrap:
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
        cmpa.l  a1, a0
        blo.s   .pb_nowrap
        suba.w  #TILE_CACHE_NT_SIZE, a0        ; physical row 59 → 0
.pb_nowrap:
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

        ; compute source: cache nametable row base (physical col 0)
        move.w  d1, d0
        sub.w   (Cache_Top_Row).w, d0
        add.w   (Cache_Origin_Row).w, d0       ; map to physical row (circular)
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .row_nowrap
        subi.w  #TILE_CACHE_ROWS, d0
.row_nowrap:
        ; row × 80 via shift-add
        move.w  d0, d3
        lsl.w   #6, d0
        lsl.w   #4, d3
        add.w   d3, d0
        add.w   d0, d0                         ; byte offset (words → bytes)
        lea     (Tile_Cache_Nametable).l, a0
        adda.w  d0, a0                         ; a0 = cache row base (physical col 0)

        ; -- Source window: the 64 world cols the plane currently holds,
        ;    [R-63, R] with R = Section_Right_Col_Written (cache-clamped).
        ;    NT col P shows world col W ≡ P (mod 64) — every engine→plane
        ;    offset is a multiple of 64 — so the source walks W = A, A+1,
        ;    …, R, then wraps to R-63 … A-1, where A = R & ~63. Cols behind
        ;    Cache_Left_Col have no cache data; write tile 0 (they sit
        ;    behind the streamed window, never visible).
        ;    The cache spans 80 cols — 16 plane cols have two cached
        ;    candidates (W and W+64); anchor R to Section_Right_Col_Written
        ;    (cache-clamped to Cache_Head_Col) so the visible-left plane
        ;    cols pick the correct twin, not the wrap twin 64 cols ahead.
        move.w  (Section_Right_Col_Written).w, d4
        cmp.w   (Cache_Head_Col).w, d4
        ble.s   .r_clamp_ok
        move.w  (Cache_Head_Col).w, d4         ; R = min(R, Cache_Head_Col)
.r_clamp_ok:
        move.w  d4, d0
        andi.w  #$FFC0, d0                     ; d0 = W cursor, starts at A = R & ~63
        move.w  (Cache_Origin_Col).w, d3
        sub.w   (Cache_Left_Col).w, d3         ; d3 = Origin - Left (physical adjust)
        move.w  (Cache_Left_Col).w, d5
        move.w  #PLANE_H_CELLS-1, d2
.row_src_loop:
        cmp.w   d5, d0                         ; W < Cache_Left → no data
        blt.s   .row_src_zero
        move.w  d0, d1
        add.w   d3, d1                         ; physical col = W + (Origin - Left)
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .row_src_nowrap
        subi.w  #TILE_CACHE_COLS, d1
.row_src_nowrap:
        add.w   d1, d1
        move.w  (a0, d1.w), (a2)+
        bra.s   .row_src_next
.row_src_zero:
        clr.w   (a2)+
.row_src_next:
        addq.w  #1, d0
        cmp.w   d4, d0                         ; past R → wrap back one plane width
        ble.s   .row_src_cont
        subi.w  #64, d0
.row_src_cont:
        dbf     d2, .row_src_loop

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
