; Section streaming engine (§4)
; Continuous-scroll: the camera, player, and all entities live in WORLD
; coordinates and the level scrolls live with no section rebases. World ==
; engine throughout; the nametable is a 64-cell ring the world wraps through.

; -----------------------------------------------
; Section_Init — record the act, fill nametable, init the entity window
; In:  a0 = act descriptor pointer (Act struct)
; Out: none
; Clobbers: d0–d7, a0–a4   (transitive via EntityWindow_Init)
; -----------------------------------------------
Section_Init:
        move.l  a0, (Current_Act_Ptr).w

        ; -- set up column/row trackers; first frame streams the plane --
        bsr.w   Section_FillInitial

        ; -- §4.9: camera-driven entity window init --
        jsr     EntityWindow_Init
        rts

; -----------------------------------------------
; Section_FillInitial — set up trackers; let Section_UpdateColumns
; fill plane on first frame.
;
; Trackers are seeded one column/row tight on each side of the camera so
; Section_UpdateColumns streams the visible window outward in scroll-
; direction order on the first frames (avoids a left-edge content pop).
;
; Out: Section_Right_Col_Written, Section_Left_Col_Written initialised
; Clobbers: none
; -----------------------------------------------
Section_FillInitial:
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                              ; d0 = camera world tile col
        subq.w  #1, d0
        move.w  d0, (Section_Right_Col_Written).w
        addq.w  #1, d0
        move.w  d0, (Section_Left_Col_Written).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                              ; d0 = camera world tile row
        subq.w  #1, d0
        move.w  d0, (Section_Bottom_Row_Written).w
        addq.w  #1, d0
        move.w  d0, (Section_Top_Row_Written).w
        rts

; -----------------------------------------------
; Section_FlatIDXY — flat section id from grid coordinates.
; In:  d2.b = sec_x, d3.b = sec_y, a2 = Act ptr
; Out: d0.w = sec_y * grid_w + sec_x
; Clobbers: d1
; -----------------------------------------------
Section_FlatIDXY:
        moveq   #0, d0
        moveq   #0, d1
        move.b  d3, d1
        subq.w  #1, d1
        bmi.s   .fxy_add_x
.fxy_mul:
        add.w   Act_grid_w(a2), d0
        dbf     d1, .fxy_mul
.fxy_add_x:
        moveq   #0, d1
        move.b  d2, d1
        add.w   d1, d0
        rts

; -----------------------------------------------
; Section_GetSecPtrXY — Sec ptr lookup by grid coordinates (§4.2).
; In:  d2.b = sec_x, d3.b = sec_y, a2 = Act ptr
; Out: a0 = Sec ptr; Z clear if found, Z set if out of range (a0 = 0)
; Clobbers: d0, d1
; -----------------------------------------------
Section_GetSecPtrXY:
        cmp.b   Act_grid_w+1(a2), d2
        bcc.s   .out_of_range                       ; sec_x >= grid_w (unsigned)
        cmp.b   Act_grid_h+1(a2), d3
        bcc.s   .out_of_range                       ; sec_y >= grid_h (unsigned)

        ; flat_id = sec_y * grid_w + sec_x (repeated-add, no multiply)
        moveq   #0, d0
        move.b  d3, d0                              ; d0 = sec_y
        beq.s   .gxy_add_x
        move.w  d2, -(sp)                           ; save sec_x input
        move.w  Act_grid_w(a2), d1                  ; d1 = grid_w
        move.w  d0, d2                              ; d2 = sec_y counter
        moveq   #0, d0                              ; d0 = accumulator
        subq.w  #1, d2
.gxy_mul:
        add.w   d1, d0
        dbf     d2, .gxy_mul
        move.w  (sp)+, d2                           ; restore sec_x
.gxy_add_x:
        moveq   #0, d1
        move.b  d2, d1
        add.w   d1, d0                              ; d0 = flat section index

        ; d0 × Sec_len ($42 = 66 = 64 + 2)
        if Sec_len <> 66
          error "Section_GetSecPtrXY stride (lsl #6 + lsl #1 = ×66) assumes Sec_len=66 — update the shifts"
        endif
        movea.l Act_sec_grid_ptr(a2), a0
        move.w  d0, d1
        lsl.w   #6, d0                              ; flat × 64
        lsl.w   #1, d1                              ; flat × 2
        add.w   d1, d0                              ; flat × 66
        adda.w  d0, a0

        tst.l   (a0)
        beq.s   .out_of_range

        moveq   #1, d0                              ; Z clear (success)
        rts
.out_of_range:
        suba.l  a0, a0                              ; a0 = 0
        moveq   #0, d0                              ; Z set (not found)
        rts

; -----------------------------------------------
; Section_RedrawPlanes — camera-aware atomic full-plane rewrite (§4.2).
; Level-init draw + cache-recovery path only (via Section_Plane_Dirty);
; continuous-scroll streams the plane incrementally, so this never fires
; mid-traversal (~3 frames synchronous when it does run).
;
; Models sonic_hack's Dirty_flag → Draw_All pattern: the entire visible
; plane content is rewritten in one synchronous pass via direct VDP
; pokes. No multi-frame scroll-across.
;
; Camera-aware: fills 64 plane cols starting at Camera_X/8 (world col),
; reading each col straight from the tile cache. Nametable cell =
; world_col & 63 (continuous-scroll: world == engine, the plane is a
; 64-cell ring the world wraps through).
;
; In:  none (reads Camera_X, Cache_*, Current_Act_Ptr; Plane B derives the
;      on-screen section from the world camera for the BG layout ptr)
; Out: d5.w = start_world_col (for tracker reset by caller)
;      d7.w = start_world_col + 63 (for tracker reset by caller)
; Clobbers: d0–d7, a0–a4, a5–a6
; -----------------------------------------------
Section_RedrawPlanes:
        lea     (VDP_CTRL).l, a5
        lea     (VDP_DATA).l, a6
        move.w  sr, -(sp)
        move.w  #$2700, sr

        ; -- Plane A: column-major write --
        move.w  #$8F80, (a5)

        ; compute start nametable row from Cache_Top_Row (world_row & 63)
        move.w  (Cache_Top_Row).w, d6
        andi.w  #63, d6                         ; d6 = start_nt_row (preserved)

        ; compute start world col = Camera_X >> 3
        move.l  (Camera_X).w, d5
        swap    d5
        lsr.w   #3, d5                          ; d5 = start_world_col

        moveq   #0, d3                          ; col counter (0..63)
        lea     (Tile_Cache_Nametable+TILE_CACHE_NT_SIZE).l, a0   ; row-wrap sentinel
                                                ; (a0 free until the Plane B pass)

.pla_fill:
        move.w  d5, d7
        add.w   d3, d7                          ; d7 = world_col

        ; check cache range BEFORE setting VDP address — skip entirely
        ; on miss so off-screen columns retain old nametable content
        ; instead of flashing black/zero tiles
        cmp.w   (Cache_Left_Col).w, d7
        blt.w   .pla_next
        cmp.w   (Cache_Head_Col).w, d7
        bgt.w   .pla_next

        ; convert world col → plane col (world_col & 63)
        move.w  d7, d0
        andi.w  #63, d0                         ; d0 = plane_col = world_col & 63
        add.w   d0, d0                          ; d0 = col byte offset
        move.w  d0, -(sp)                       ; save for Part B

        ; read from tile cache — compute cache column pointer
        move.w  d7, d0
        sub.w   (Cache_Left_Col).w, d0
        add.w   (Cache_Origin_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d0
.col_nowrap:
        add.w   d0, d0                         ; byte offset = col × 2
        move.w  (Cache_Origin_Row).w, d1
        move.w  d1, d2
        lsl.w   #7, d1                         ; × 128
        lsl.w   #5, d2                         ; × 32
        add.w   d2, d1                         ; origin_row × 160 (stride bytes)
        add.w   d1, d0
        lea     (Tile_Cache_Nametable).l, a1
        adda.w  d0, a1                         ; a1 = cache[logical row 0][col]

        ; -- Part A: nametable rows start_nt_row to 63 --
        move.w  (sp), d4                       ; col byte offset
        move.w  d6, d2
        lsl.w   #7, d2                         ; start_nt_row × 128
        add.w   d2, d4
        moveq   #0, d2
        move.w  d4, d2
        addi.l  #VRAM_PLANE_A, d2
        vdpCommReg d2, VRAM, WRITE, 1
        move.l  d2, (a5)

        move.w  #64, d2
        sub.w   d6, d2                         ; d2 = count_A (rows in Part A)
        moveq   #TILE_CACHE_ROWS, d4
        cmp.w   d2, d4
        ble.s   .pA_clamp
        move.w  d2, d4                         ; d4 = data_A = min(cache_rows, count_A)
.pA_clamp:
        move.w  d4, d0
        subq.w  #1, d0
        bmi.s   .pA_dskip
.pA_data:
        move.w  (a1), (a6)
        lea     TILE_CACHE_STRIDE*2(a1), a1
        cmpa.l  a0, a1
        blo.s   .pa_nowrap
        suba.w  #TILE_CACHE_NT_SIZE, a1        ; physical row 59 → 0
.pa_nowrap:
        dbf     d0, .pA_data
.pA_dskip:
        move.w  d2, d0
        sub.w   d4, d0                         ; zero_A = count_A - data_A
        subq.w  #1, d0
        bmi.s   .pA_zskip
        moveq   #0, d1                         ; zero source (clr.w would RMW-read VDP)
.pA_zero:
        move.w  d1, (a6)
        dbf     d0, .pA_zero
.pA_zskip:

        ; -- Part B: nametable rows 0 to start_nt_row - 1 --
        tst.w   d6
        beq.s   .pB_skip
        moveq   #0, d2
        move.w  (sp), d2                       ; col byte offset
        addi.l  #VRAM_PLANE_A, d2
        vdpCommReg d2, VRAM, WRITE, 1
        move.l  d2, (a5)
        move.w  d6, d2                         ; d2 = count_B = start_nt_row
        move.w  #TILE_CACHE_ROWS, d0
        sub.w   d4, d0                         ; remaining cache rows
        ble.s   .pB_allz
        cmp.w   d2, d0
        ble.s   .pB_dok
        move.w  d2, d0
.pB_dok:
        move.w  d0, d4
        subq.w  #1, d0
.pB_data:
        move.w  (a1), (a6)
        lea     TILE_CACHE_STRIDE*2(a1), a1
        cmpa.l  a0, a1
        blo.s   .pb_nowrap
        suba.w  #TILE_CACHE_NT_SIZE, a1        ; physical row 59 → 0
.pb_nowrap:
        dbf     d0, .pB_data
        move.w  d2, d0
        sub.w   d4, d0
        subq.w  #1, d0
        bmi.s   .pB_skip
        moveq   #0, d1                         ; zero source (clr.w would RMW-read VDP)
.pB_zfill:
        move.w  d1, (a6)
        dbf     d0, .pB_zfill
        bra.s   .pB_skip
.pB_allz:
        move.w  d2, d0
        subq.w  #1, d0
        moveq   #0, d1                         ; zero source (clr.w would RMW-read VDP)
.pB_az:
        move.w  d1, (a6)
        dbf     d0, .pB_az
.pB_skip:
        addq.l  #2, sp                         ; pop col byte offset

.pla_next:
        addq.w  #1, d3
        cmpi.w  #64, d3
        blt.w   .pla_fill

        ; -- Plane B: row-major linear write (BG layout is act-wide, not position-dependent) --
        ; Continuous-scroll: derive the on-screen section straight from the
        ; world camera (sec_x = Camera_X >> SECTION_SIZE_SHIFT, sec_y likewise).
        ; At level init the camera sits in the start section, so this returns the
        ; start section's BG.
        movea.l (Current_Act_Ptr).w, a2
        move.w  (Camera_X).w, d2                    ; world X px (16.16 high word)
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d2                              ; d2.w = sec_x
        move.w  (Camera_Y).w, d3                    ; world Y px
        asr.w   d0, d3                              ; d3.w = sec_y
        bsr.w   Section_GetSecPtrXY                 ; a0 = on-screen Sec ptr (Z set = none)
        beq.s   .plb_use_act_layout
        movea.l Sec_sec_bg_layout(a0), a1
        cmpa.w  #0, a1
        bne.s   .plb_have_layout
.plb_use_act_layout:
        movea.l Act_act_bg_layout(a2), a1           ; T1 fallback to act-level BG
        cmpa.w  #0, a1
        beq.s   .plb_done
.plb_have_layout:
        move.w  #$8F02, (a5)                        ; autoincrement $02 (row-major)
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (a5)
        move.w  #1024-1, d3                         ; 4096 bytes / 4 = 1024 longwords - 1
.plb_loop:
        move.l  (a1)+, (a6)
        dbf     d3, .plb_loop
.plb_done:
        ; Restore default autoincrement (matches VInt_DrawLevel cleanup)
        move.w  #$8F02, (a5)

        ; Restore interrupt mask (allow VBlank again)
        move.w  (sp)+, sr

        ; -- return tracker bounds in d5/d7 for caller --
        ; Clamp to cache range so Section_UpdateColumns streams any
        ; columns we skipped (outside cache at redraw time).
        move.w  (Cache_Left_Col).w, d0
        cmp.w   d0, d5
        bge.s   .track_left_ok
        move.w  d0, d5
.track_left_ok:
        move.w  (Cache_Head_Col).w, d7
        rts

; -----------------------------------------------
; Section_UpdateColumns — per-frame nametable ring-buffer streaming
; Writes newly-revealed tile columns on right and left edges each frame.
; Must be called AFTER Camera_X is updated each frame.
; In:  none
; Out: none
; Clobbers: d0–d7, a0–a3, a5–a6 (a5/a6 only when Plane_Dirty triggers redraw)
; -----------------------------------------------
Section_UpdateColumns:
        ; -- §4.2: full-plane redraw if dirty (level init + cache recovery only) --
        tst.b   (Section_Plane_Dirty).w
        beq.s   .not_dirty
        clr.b   (Section_Plane_Dirty).w
        bsr.w   Section_RedrawPlanes
        move.w  d7, (Section_Right_Col_Written).w
        move.w  d5, (Section_Left_Col_Written).w
        move.w  (Cache_Top_Row).w, (Section_Top_Row_Written).w
        move.w  (Cache_Bottom_Row).w, (Section_Bottom_Row_Written).w
        rts
.not_dirty:
        movem.l d2-d7/a0-a3, -(sp)

        move.l  (Camera_X).w, d6
        swap    d6                              ; d6.w = Camera_X pixels

        ; -------- right side --------
        move.w  d6, d7
        addi.w  #327, d7
        lsr.w   #3, d7                          ; d7 = right_needed world col

        ; clamp to act boundary
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.w  Act_grid_w(a0), d0
        lsl.w   #8, d0
        subq.w  #1, d0
        cmp.w   d0, d7
        ble.s   .right_clamp_ok
        move.w  d0, d7
.right_clamp_ok:
        ; clamp to cache bounds
        move.w  (Cache_Head_Col).w, d0
        cmp.w   d0, d7
        ble.s   .right_cache_ok
        move.w  d0, d7
.right_cache_ok:
        ; clamp to VDP plane wrap: max right = visible_left_world + 63
        move.w  d6, d0
        lsr.w   #3, d0                          ; camera tile col (world)
        addi.w  #63, d0                         ; max right = visible_left + 63 VDP cells
        cmp.w   d0, d7
        ble.s   .right_wrap_ok
        move.w  d0, d7
.right_wrap_ok:

        move.w  (Section_Right_Col_Written).w, d5
.right_loop:
        cmp.w   d7, d5
        bge.w   .right_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + PLANE_V_CELLS*2), (Plane_Buffer_Ptr).w
        bhi.w   .right_done
        addq.w  #1, d5

        ; convert world col → nametable position (world_col & 63)
        move.w  d5, d0
        andi.w  #63, d0                         ; d0 = nametable col = world_col & 63

        move.w  d5, d1                          ; d1 = world col
        move.w  d5, -(sp)
        bsr.w   Draw_TileColumn
        move.w  (sp)+, d5
        bra.w   .right_loop
.right_done:
        move.w  d5, (Section_Right_Col_Written).w
        move.w  d5, d3
        subi.w  #63, d3                         ; left = right - 63 (VDP wrap span)
        cmp.w   (Cache_Left_Col).w, d3          ; clamp to cache: left = max(., Cache_Left_Col)
        bge.s   .right_done_cache_ok
        move.w  (Cache_Left_Col).w, d3
.right_done_cache_ok:
        cmp.w   (Section_Left_Col_Written).w, d3
        ble.s   .left_clamp_skip
        move.w  d3, (Section_Left_Col_Written).w
.left_clamp_skip:

        ; -------- left side --------
        move.w  d6, d7
        lsr.w   #3, d7                          ; d7 = left_needed world col

        ; clamp to cache and act bounds
        move.w  (Cache_Left_Col).w, d0
        cmp.w   d0, d7
        bge.s   .left_cache_ok
        move.w  d0, d7
.left_cache_ok:
        ; clamp to VDP plane wrap: min left = visible_right_world - 63
        move.w  d6, d0
        addi.w  #327, d0                        ; visible_right_px = Camera_X + screen−1
        lsr.w   #3, d0
        subi.w  #63, d0                         ; min left = visible_right − 63 VDP cells
        cmp.w   d0, d7
        bge.s   .left_wrap_ok
        move.w  d0, d7
.left_wrap_ok:

        move.w  (Section_Left_Col_Written).w, d5
.left_loop:
        cmp.w   d7, d5
        ble.w   .left_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + PLANE_V_CELLS*2), (Plane_Buffer_Ptr).w
        bhi.w   .left_done
        subq.w  #1, d5

        move.w  d5, d0
        andi.w  #63, d0                         ; nametable col = world_col & 63

        move.w  d5, d1
        move.w  d5, -(sp)
        bsr.w   Draw_TileColumn
        move.w  (sp)+, d5
        bra.w   .left_loop
.left_done:
        move.w  d5, (Section_Left_Col_Written).w
        move.w  d5, d3
        addi.w  #63, d3                         ; right = left + 63 (VDP wrap span)
        cmp.w   (Cache_Head_Col).w, d3          ; clamp to cache: right = min(., Cache_Head_Col)
        ble.s   .left_done_cache_ok
        move.w  (Cache_Head_Col).w, d3
.left_done_cache_ok:
        cmp.w   (Section_Right_Col_Written).w, d3
        bge.s   .right_clamp_skip2
        move.w  d3, (Section_Right_Col_Written).w
.right_clamp_skip2:

        ; -------- bottom side (vertical row streaming) --------
        move.l  (Camera_Y).w, d6
        swap    d6
        move.w  d6, d7
        addi.w  #231, d7                           ; 224 + 7
        lsr.w   #3, d7                             ; d7 = bottom_needed world row

        ; clamp to cache bounds
        move.w  (Cache_Bottom_Row).w, d0
        cmp.w   d0, d7
        ble.s   .bot_cache_ok
        move.w  d0, d7
.bot_cache_ok:

        move.w  (Section_Bottom_Row_Written).w, d5
.bot_loop:
        cmp.w   d7, d5
        bge.s   .bot_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + PLANE_H_CELLS*2), (Plane_Buffer_Ptr).w
        bhi.s   .bot_done
        addq.w  #1, d5

        ; convert world row → nametable row (world_row & 63)
        move.w  d5, d0
        andi.w  #63, d0                            ; d0 = nametable row = world_row & 63

        move.w  d5, d1                             ; d1 = world row
        move.w  d5, -(sp)
        bsr.w   Draw_TileRow_FromCache
        move.w  (sp)+, d5
        bra.s   .bot_loop
.bot_done:
        move.w  d5, (Section_Bottom_Row_Written).w
        move.w  d5, d3
        subi.w  #63, d3                         ; top = bottom - 63 (VDP wrap span)
        cmp.w   (Cache_Top_Row).w, d3           ; clamp to cache: top = max(., Cache_Top_Row)
        bge.s   .bot_done_cache_ok
        move.w  (Cache_Top_Row).w, d3
.bot_done_cache_ok:
        cmp.w   (Section_Top_Row_Written).w, d3
        ble.s   .top_row_clamp_skip
        move.w  d3, (Section_Top_Row_Written).w
.top_row_clamp_skip:

        ; -------- top side --------
        lsr.w   #3, d6
        move.w  d6, d7                             ; d7 = top_needed world row

        move.w  (Cache_Top_Row).w, d0
        cmp.w   d0, d7
        bge.s   .top_cache_ok
        move.w  d0, d7
.top_cache_ok:

        move.w  (Section_Top_Row_Written).w, d5
.top_loop:
        cmp.w   d7, d5
        ble.s   .top_done
        cmpi.w  #PLANE_BUFFER_SIZE - 2 - (4 + PLANE_H_CELLS*2), (Plane_Buffer_Ptr).w
        bhi.s   .top_done
        subq.w  #1, d5

        move.w  d5, d0
        andi.w  #63, d0                            ; nametable row = world_row & 63

        move.w  d5, d1
        move.w  d5, -(sp)
        bsr.w   Draw_TileRow_FromCache
        move.w  (sp)+, d5
        bra.s   .top_loop
.top_done:
        move.w  d5, (Section_Top_Row_Written).w
        move.w  d5, d3
        addi.w  #63, d3                         ; bottom = top + 63 (VDP wrap span)
        cmp.w   (Cache_Bottom_Row).w, d3        ; clamp to cache: bottom = min(., Cache_Bottom_Row)
        ble.s   .top_done_cache_ok
        move.w  (Cache_Bottom_Row).w, d3
.top_done_cache_ok:
        cmp.w   (Section_Bottom_Row_Written).w, d3
        bge.s   .bot_row_clamp_skip
        move.w  d3, (Section_Bottom_Row_Written).w
.bot_row_clamp_skip:

        movem.l (sp)+, d2-d7/a0-a3
        rts
