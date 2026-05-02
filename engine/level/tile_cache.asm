; 2D tile cache (§4.7)
; Linear 2D buffer in lower RAM. Slides in both axes as camera moves.
; Block-based decompression: each 16×16 tile block decompressed on demand.

; -----------------------------------------------
; Engine_To_World_Col — convert engine tile col to world tile col
; In:  d0.w = engine tile col (e.g., Camera_X / 8)
; Out: d0.w = world tile col
; Clobbers: d1
; -----------------------------------------------
Engine_To_World_Col:
        subi.w  #SLOT_ORIGIN_L/8, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        add.w   d1, d0
        rts

; -----------------------------------------------
; Engine_To_World_Row — convert engine tile row to world tile row
; In:  d0.w = engine tile row (e.g., Camera_Y / 8)
; Out: d0.w = world tile row
; Clobbers: d1
; -----------------------------------------------
Engine_To_World_Row:
        subi.w  #SLOT_ORIGIN_U/8, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map+1).w, d1
        lsl.w   #8, d1
        add.w   d1, d0
        rts

; -----------------------------------------------
; Tile_Cache_GetTile — look up nametable word for a world tile position
; In:  d0.w = world tile col, d1.w = world tile row
; Out: d2.w = nametable word
; Clobbers: d0-d2, a0
; -----------------------------------------------
Tile_Cache_GetTile:
        sub.w   (Cache_Left_Col).w, d0
        add.w   (Cache_Origin_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d0
.col_nowrap:
        sub.w   (Cache_Top_Row).w, d1
        ; d1 * 80 via shift-add (80 = 64 + 16)
        move.w  d1, d2
        lsl.w   #6, d1
        lsl.w   #4, d2
        add.w   d2, d1
        add.w   d0, d1
        add.w   d1, d1                         ; ×2 for word-sized entries
        lea     (Tile_Cache_Nametable).l, a0
        move.w  (a0, d1.w), d2
        rts

; -----------------------------------------------
; Tile_Cache_GetCollision — look up collision byte for a world tile position
; In:  d0.w = world tile col, d1.w = world tile row
; Out: d0.b = collision type byte (0 = air)
; Clobbers: d0-d2, a0
; -----------------------------------------------
Tile_Cache_GetCollision:
        sub.w   (Cache_Left_Col).w, d0
        add.w   (Cache_Origin_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d0
.col_nowrap:
        sub.w   (Cache_Top_Row).w, d1
        lsr.w   #1, d1                         ; tile rows → collision rows
        ; d1 * 80 via shift-add
        move.w  d1, d2
        lsl.w   #6, d1
        lsl.w   #4, d2
        add.w   d2, d1
        add.w   d0, d1
        lea     (Tile_Cache_Collision).l, a0
        move.b  (a0, d1.w), d0
        rts

; -----------------------------------------------
; TileCache_DecompressBlock — decompress one 16×16 block into staging buffer
; In:  d0.w = sec_x, d1.w = sec_y, d2.w = block_index (0–255)
; Out: Block_Stage_Nametable and Block_Stage_Collision filled
; Clobbers: d0-d5, a0-a3
; -----------------------------------------------
TileCache_DecompressBlock:
        move.w  d2, (Block_Stage_ID).w
        move.b  d0, (Block_Stage_Section_X).w
        move.b  d1, (Block_Stage_Section_Y).w

        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_sec_grid_ptr(a0), a1

        ; sec_id = sec_y * grid_w + sec_x (add loop, cold path)
        move.w  Act_grid_w(a0), d4             ; d4 = grid_w
        moveq   #0, d3                         ; accumulator
        move.w  d1, d5                         ; d5 = sec_y counter
        bra.s   .mul_test
.mul_loop:
        add.w   d4, d3
.mul_test:
        dbf     d5, .mul_loop
        add.w   d0, d3                         ; d3 = flat section id
        ; d3 × Sec_len (72 = 64+8)
        move.w  d3, d4
        lsl.w   #6, d3
        lsl.w   #3, d4
        add.w   d4, d3
        adda.w  d3, a1                         ; a1 = Sec struct pointer

        movea.l Sec_sec_block_index(a1), a2    ; a2 = block index table base (ROM)
        move.l  a2, d3
        beq.s   .empty_block

        ; index into block table: block_index × 4
        move.w  d2, d3
        lsl.w   #2, d3
        move.l  (a2, d3.w), d0                 ; d0 = offset from table base (0 = null)
        beq.s   .empty_block

        ; compute absolute ROM address: base + offset
        lea     (a2, d0.l), a0                 ; a0 = compressed block data
        lea     (Block_Stage_Nametable).l, a1
        bsr.w   S4LZ_Decompress
        rts

.empty_block:
        lea     (Block_Stage_Nametable).l, a0
        move.w  #(BLOCK_RAW_SIZE/4)-1, d0
.zero_loop:
        clr.l   (a0)+
        dbf     d0, .zero_loop
        rts

; -----------------------------------------------
; TileCache_StagedBlockMatch — check if staging buffer already holds the needed block
; In:  d0.w = sec_x, d1.w = sec_y, d2.w = block_index
; Out: Z set if match (staging buffer valid), Z clear if miss
; Clobbers: d3
; -----------------------------------------------
TileCache_StagedBlockMatch:
        cmp.w   (Block_Stage_ID).w, d2
        bne.s   .miss
        cmp.b   (Block_Stage_Section_X).w, d0
        bne.s   .miss
        cmp.b   (Block_Stage_Section_Y).w, d1
        bne.s   .miss
        moveq   #0, d3                         ; Z set
        rts
.miss:
        moveq   #1, d3                         ; Z clear
        rts

; -----------------------------------------------
; TileCache_CopyBlockColumn — copy one column from staging to cache
; In:  d0.w = intra-block col (0–15)
;      d1.w = cache col offset (world_col - Cache_Left_Col)
;      d2.w = cache row offset (world_row_of_block_top - Cache_Top_Row)
;      d3.w = rows to copy (already clamped to cache bounds)
; Out: none
; Clobbers: d0-d5, a0-a2
; -----------------------------------------------
TileCache_CopyBlockColumn:
        ; wrap d1 (logical cache col) to physical column via circular origin
        add.w   (Cache_Origin_Col).w, d1
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d1
.col_nowrap:
        ; source: Block_Stage_Nametable + (row * 16 + col) * 2
        lea     (Block_Stage_Nametable).l, a0
        move.w  d0, d4
        add.w   d4, d4                         ; col * 2 (byte offset for first row)
        adda.w  d4, a0                         ; a0 = first tile word in column

        ; dest: Tile_Cache_Nametable + (cache_row * stride + cache_col) * 2
        lea     (Tile_Cache_Nametable).l, a1
        move.w  d2, d4
        move.w  d4, d5
        lsl.w   #6, d4
        lsl.w   #4, d5
        add.w   d5, d4                         ; d4 = cache_row * 80
        add.w   d1, d4                         ; + cache_col
        add.w   d4, d4                         ; byte offset
        adda.w  d4, a1

        move.w  d3, d4
        subq.w  #1, d4
.copy_nt:
        move.w  (a0), (a1)
        lea     BLOCK_TILE_SIZE*2(a0), a0      ; next block row (32 bytes)
        lea     TILE_CACHE_STRIDE*2(a1), a1    ; next cache row (160 bytes)
        dbf     d4, .copy_nt

        ; collision: copy corresponding collision column
        lea     (Block_Stage_Collision).l, a0
        adda.w  d0, a0                         ; col offset (bytes, not words)

        lea     (Tile_Cache_Collision).l, a1
        move.w  d2, d4
        lsr.w   #1, d4                         ; cache tile row → collision row
        move.w  d4, d5
        lsl.w   #6, d4
        lsl.w   #4, d5
        add.w   d5, d4                         ; collision_row * 80
        add.w   d1, d4
        adda.w  d4, a1

        move.w  d3, d4
        lsr.w   #1, d4                         ; tile rows → collision rows
        subq.w  #1, d4
        bmi.s   .done_coll
.copy_coll:
        move.b  (a0), (a1)
        lea     BLOCK_TILE_SIZE(a0), a0        ; next collision row in block (16 bytes)
        lea     TILE_CACHE_STRIDE(a1), a1      ; next collision row in cache (80 bytes)
        dbf     d4, .copy_coll
.done_coll:
        rts

; -----------------------------------------------
; Tile_Cache_Init — populate cache for initial viewport + margins
; Called at level init (display off).
; In:  none (reads Camera_X, Camera_Y, Slot_Section_Map, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Tile_Cache_Init:
        ; compute world tile bounds for initial fill
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera tile col (engine)
        bsr.w   Engine_To_World_Col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .left_ok
        moveq   #0, d0
.left_ok:
        move.w  d0, (Cache_Left_Col).w
        addi.w  #TILE_CACHE_COLS-1, d0
        move.w  d0, (Cache_Head_Col).w
        clr.w   (Cache_Origin_Col).w
        move.w  #$FFFF, (Cache_Fill_Last_Frame).w
        move.w  #$FFFF, (Cache_Fill_Resume_Row).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera tile row (engine)
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .top_ok
        moveq   #0, d0
.top_ok:
        move.w  d0, (Cache_Top_Row).w
        addi.w  #TILE_CACHE_ROWS-1, d0
        move.w  d0, (Cache_Bottom_Row).w

        ; invalidate block staging
        move.w  #$FFFF, (Block_Stage_ID).w

        bsr.w   TileCache_FillAll
        rts

; -----------------------------------------------
; TileCache_FillAll — fill entire cache from block data
; Called at init and after full reinit.
; In:  none (reads Cache_Left_Col/Head_Col/Top_Row/Bottom_Row)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillAll:
        ; zero the cache first
        lea     (Tile_Cache_Nametable).l, a0
        move.w  #(TILE_CACHE_NT_SIZE/4)-1, d0
.zero_nt:
        clr.l   (a0)+
        dbf     d0, .zero_nt

        lea     (Tile_Cache_Collision).l, a0
        move.w  #(TILE_CACHE_COLL_SIZE/4)-1, d0
.zero_coll:
        clr.l   (a0)+
        dbf     d0, .zero_coll

        ; iterate over all blocks overlapping the cache window
        ; world_block_col = world_tile_col / 16; world_block_row = world_tile_row / 16
        ; Each world block maps to: sec_x = block_col / 16, intra_block_x = block_col & 15

        move.w  (Cache_Left_Col).w, d0
        lsr.w   #BLOCK_TILE_SHIFT, d0          ; first world block col
        move.w  d0, -(sp)                      ; save start_block_col

        move.w  (Cache_Head_Col).w, d0
        lsr.w   #BLOCK_TILE_SHIFT, d0
        move.w  d0, -(sp)                      ; save end_block_col

        move.w  (Cache_Top_Row).w, d0
        lsr.w   #BLOCK_TILE_SHIFT, d0
        move.w  d0, -(sp)                      ; save start_block_row (also current)

        move.w  (Cache_Bottom_Row).w, d0
        lsr.w   #BLOCK_TILE_SHIFT, d0
        move.w  d0, -(sp)                      ; save end_block_row

        ; stack layout: 0(sp)=end_row, 2(sp)=cur_row, 4(sp)=end_col, 6(sp)=start_col

.block_row_loop:
        move.w  6(sp), d6                      ; d6 = current block col (reset to start)

.block_col_loop:
        ; decompose world block coords into section + intra-block
        move.w  d6, d0
        lsr.w   #BLOCK_TILE_SHIFT, d0          ; sec_x = world_block_col / 16
        move.w  2(sp), d7
        move.w  d7, d1
        lsr.w   #BLOCK_TILE_SHIFT, d1          ; sec_y = world_block_row / 16
        move.w  d6, d2
        andi.w  #$F, d2                        ; intra_block_x
        move.w  d7, d3
        andi.w  #$F, d3                        ; intra_block_y
        ; block_index = intra_block_y * 16 + intra_block_x
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; d2 = block_index

        movem.l d6/d7, -(sp)
        bsr.w   TileCache_DecompressBlock
        movem.l (sp)+, d6/d7

        ; copy all 16 columns from staging into cache
        move.w  d6, d4
        lsl.w   #BLOCK_TILE_SHIFT, d4          ; world tile col of block left
        move.w  2(sp), d5                      ; current world block row
        lsl.w   #BLOCK_TILE_SHIFT, d5          ; world tile row of block top

        moveq   #0, d0                         ; intra-block col counter
.fill_copy_col:
        ; cache col offset = (block_left_tile + intra_col) - Cache_Left_Col
        move.w  d4, d1
        add.w   d0, d1
        sub.w   (Cache_Left_Col).w, d1
        bmi.s   .fill_skip_col
        cmpi.w  #TILE_CACHE_COLS, d1
        bge.s   .fill_skip_col

        ; cache row offset = block_top_tile - Cache_Top_Row
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.s   .fill_skip_col

        moveq   #BLOCK_TILE_SIZE, d3           ; rows to copy
        ; clamp to remaining cache rows
        move.w  #TILE_CACHE_ROWS, d7
        sub.w   d2, d7
        cmp.w   d7, d3
        ble.s   .fill_rows_ok
        move.w  d7, d3
.fill_rows_ok:
        tst.w   d3
        ble.s   .fill_skip_col

        movem.l d0/d4-d6, -(sp)
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d0/d4-d6
.fill_skip_col:
        addq.w  #1, d0
        cmpi.w  #BLOCK_TILE_SIZE, d0
        blt.s   .fill_copy_col

        ; next block col
        addq.w  #1, d6
        cmp.w   4(sp), d6                     ; compare with end_block_col
        ble.s   .block_col_loop

        ; next block row
        move.w  2(sp), d0
        addq.w  #1, d0
        move.w  d0, 2(sp)
        cmp.w   (sp), d0                      ; compare with end_block_row
        ble.w   .block_row_loop

        lea     8(sp), sp                     ; clean up stack
        rts

; -----------------------------------------------
; Tile_Cache_Fill — per-frame cache extension as camera moves
; Called each frame after Camera_Update, before Section_UpdatePlane.
; Handles rightward/leftward column fill and downward/upward row fill.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Tile_Cache_Fill:
        ; --- frame gate: at most one fill per physical frame ---
        ; Frame_Counter only increments in VBlank, so all game-loop
        ; iterations within the same VBlank period see the same value.
        move.w  (Frame_Counter).w, d0
        cmp.w   (Cache_Fill_Last_Frame).w, d0
        beq.w   .fill_return

        ; --- compute desired left edge ---
        move.l  (Camera_X).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .h_left_pos
        moveq   #0, d0
.h_left_pos:
        move.w  d0, -(sp)                     ; [sp] = desired_left

        ; --- compute desired right edge ---
        move.l  (Camera_X).w, d6
        swap    d6
        addi.w  #327, d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        addi.w  #TILE_CACHE_MARGIN_H, d0
        move.w  d0, d7                         ; d7 = desired right edge

        ; clamp right so span fits cache
        move.w  (sp), d0                       ; desired_left
        addi.w  #TILE_CACHE_COLS-1, d0
        cmp.w   d0, d7
        ble.s   .h_clamp_ok
        move.w  d0, d7
.h_clamp_ok:

        ; --- fill rightward columns (evict 1 from left as needed, max 1/frame) ---
        move.w  (Cache_Head_Col).w, d5
        cmp.w   d7, d5
        bge.s   .h_right_done

        ; cap to 1 new column per frame to spread decompression cost
        move.w  d5, d0
        addq.w  #1, d0
        cmp.w   d0, d7
        ble.s   .h_cap_ok
        move.w  d0, d7
.h_cap_ok:

.h_right_fill:
        addq.w  #1, d5
        cmp.w   d7, d5
        bgt.s   .h_right_done

        ; evict 1 column from left if cache is at capacity
        move.w  d5, d0
        sub.w   (Cache_Left_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .h_no_evict
        moveq   #1, d0
        bsr.w   TileCache_HSlide
.h_no_evict:

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillColumn
        movem.l (sp)+, d5/d7

        move.w  (Frame_Counter).w, (Cache_Fill_Last_Frame).w

        tst.w   d0
        bne.s   .h_right_done        ; partial fill — exit, resume next frame
        move.w  d5, (Cache_Head_Col).w
        bra.s   .h_right_fill
.h_right_done:

        ; --- fill leftward columns (evict 1 from right as needed, max 1/frame) ---
        move.w  (sp)+, d4                      ; d4 = desired_left
        move.w  (Cache_Left_Col).w, d5
        cmp.w   d4, d5
        ble.s   .h_left_done

        ; don't start leftward fill if rightward fill is pending partial resume
        cmpi.w  #$FFFF, (Cache_Fill_Resume_Row).w
        bne.s   .h_left_done

        ; cap to 1 new column per frame
        move.w  d5, d0
        subq.w  #1, d0
        cmp.w   d0, d4
        bge.s   .h_lcap_ok
        move.w  d0, d4
.h_lcap_ok:

.h_left_fill:
        subq.w  #1, d5
        cmp.w   d4, d5
        blt.s   .h_left_done

        ; evict 1 column from right if cache is at capacity
        move.w  (Cache_Head_Col).w, d0
        sub.w   d5, d0
        cmpi.w  #TILE_CACHE_COLS-1, d0
        blt.s   .h_no_evict_left
        subq.w  #1, (Cache_Head_Col).w
.h_no_evict_left:

        ; slide origin left before fill
        move.w  d5, (Cache_Left_Col).w
        move.w  (Cache_Origin_Col).w, d0
        subq.w  #1, d0
        bpl.s   .h_origin_ok
        move.w  #TILE_CACHE_COLS-1, d0
.h_origin_ok:
        move.w  d0, (Cache_Origin_Col).w

        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillColumn
        movem.l (sp)+, d4-d5

        move.w  (Frame_Counter).w, (Cache_Fill_Last_Frame).w

        tst.w   d0
        bne.s   .h_left_done                  ; partial fill — exit, resume next frame
        bra.s   .h_left_fill
.h_left_done:

        ; --- compute desired top edge ---
        move.l  (Camera_Y).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .v_top_pos
        moveq   #0, d0
.v_top_pos:
        move.w  d0, -(sp)                     ; [sp] = desired_top

        ; --- compute desired bottom edge ---
        move.l  (Camera_Y).w, d6
        swap    d6
        addi.w  #231, d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Row
        addi.w  #TILE_CACHE_MARGIN_V, d0
        move.w  d0, d7                         ; d7 = desired bottom edge

        ; clamp bottom so span fits cache
        move.w  (sp), d0                       ; desired_top
        addi.w  #TILE_CACHE_ROWS-1, d0
        cmp.w   d0, d7
        ble.s   .v_clamp_ok
        move.w  d0, d7
.v_clamp_ok:

        ; --- fill downward rows (evict 1 from top as needed) ---
        move.w  (Cache_Bottom_Row).w, d5
        cmp.w   d7, d5
        bge.s   .v_bottom_done

        ; cap to 1 new row per frame
        move.w  d5, d0
        addq.w  #1, d0
        cmp.w   d0, d7
        ble.s   .v_cap_ok
        move.w  d0, d7
.v_cap_ok:

.v_bottom_fill:
        addq.w  #1, d5
        cmp.w   d7, d5
        bgt.s   .v_bottom_done

        ; evict 1 row from top if cache is at capacity
        move.w  d5, d0
        sub.w   (Cache_Top_Row).w, d0
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .v_no_evict
        moveq   #1, d0
        bsr.w   TileCache_VSlide
.v_no_evict:

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillRow
        movem.l (sp)+, d5/d7

        move.w  (Frame_Counter).w, (Cache_Fill_Last_Frame).w
        move.w  d5, (Cache_Bottom_Row).w
        bra.s   .v_bottom_fill
.v_bottom_done:

        ; --- fill upward rows (evict 1 from bottom as needed) ---
        move.w  (sp)+, d4                      ; d4 = desired_top
        move.w  (Cache_Top_Row).w, d5
        cmp.w   d4, d5
        ble.s   .v_top_done

        ; cap to 1 new row per frame
        move.w  d5, d0
        subq.w  #1, d0
        cmp.w   d0, d4
        bge.s   .v_tcap_ok
        move.w  d0, d4
.v_tcap_ok:

.v_top_fill:
        subq.w  #1, d5
        cmp.w   d4, d5
        blt.s   .v_top_done

        ; evict 1 row from bottom if cache is at capacity
        move.w  (Cache_Bottom_Row).w, d0
        sub.w   d5, d0
        cmpi.w  #TILE_CACHE_ROWS-1, d0
        blt.s   .v_no_evict_up
        moveq   #1, d0
        bsr.w   TileCache_VSlideUp
.v_no_evict_up:

        ; decrement Cache_Top_Row BEFORE fill so FillRow sees correct offset
        move.w  d5, (Cache_Top_Row).w

        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillRow
        movem.l (sp)+, d4-d5

        move.w  (Frame_Counter).w, (Cache_Fill_Last_Frame).w
        bra.s   .v_top_fill
.v_top_done:
.fill_return:
        rts

; -----------------------------------------------
; TileCache_FillColumn — fill one world column into cache (budget-limited)
; In:  d5.w = world tile col to fill
; Out: d0.w = 0 if column complete, nonzero if partial (resume next frame)
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillColumn:
        ; resume from partial fill or start from top
        move.w  (Cache_Fill_Resume_Row).w, d7
        cmpi.w  #$FFFF, d7
        bne.s   .fc_have_start
        move.w  (Cache_Top_Row).w, d7
.fc_have_start:

        moveq   #3, d4                         ; decompress budget

.fc_block_loop:
        move.w  (Cache_Bottom_Row).w, d0
        subi.w  #BLOCK_TILE_SIZE, d0
        cmp.w   d0, d7
        bgt.w   .fc_complete

        ; decompose into section + block + intra
        move.w  d5, d0
        lsr.w   #8, d0                         ; sec_x
        move.w  d7, d6
        lsr.w   #8, d6                         ; sec_y
        move.w  d6, d1                         ; d1 = sec_y

        move.w  d5, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; d2 = block_index

        ; check staging cache
        bsr.w   TileCache_StagedBlockMatch
        beq.s   .fc_have_block

        ; need decompress — check budget
        tst.w   d4
        beq.s   .fc_budget_out
        subq.w  #1, d4

        movem.l d4-d5/d7, -(sp)
        bsr.w   TileCache_DecompressBlock
        movem.l (sp)+, d4-d5/d7
.fc_have_block:

        ; intra-block col
        move.w  d5, d0
        andi.w  #$F, d0

        ; cache col offset
        move.w  d5, d1
        sub.w   (Cache_Left_Col).w, d1

        ; cache row offset = block_top_row - Cache_Top_Row
        move.w  d7, d2
        andi.w  #$FFF0, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.s   .fc_clamp_top
        bra.s   .fc_calc_rows
.fc_clamp_top:
        moveq   #0, d2
.fc_calc_rows:
        moveq   #BLOCK_TILE_SIZE, d3
        move.w  d4, -(sp)                     ; save budget (d4 used as temp below)
        move.w  #TILE_CACHE_ROWS, d4
        sub.w   d2, d4
        cmp.w   d4, d3
        ble.s   .fc_rows_ok
        move.w  d4, d3
.fc_rows_ok:
        move.w  (sp)+, d4                     ; restore budget
        tst.w   d3
        ble.s   .fc_next_block

        movem.l d4-d5/d7, -(sp)
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d4-d5/d7

.fc_next_block:
        move.w  d7, d0
        andi.w  #$FFF0, d0
        addi.w  #BLOCK_TILE_SIZE, d0
        move.w  d0, d7
        bra.w   .fc_block_loop

.fc_budget_out:
        move.w  d7, (Cache_Fill_Resume_Row).w
        moveq   #1, d0
        rts

.fc_complete:
        move.w  #$FFFF, (Cache_Fill_Resume_Row).w
        moveq   #0, d0
        rts

; -----------------------------------------------
; TileCache_FillRow — fill one world row into cache at Cache_Bottom_Row+1
; In:  d5.w = world tile row to fill
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillRow:
        ; cache row offset (constant for all columns)
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.w   .fr_early_out

        ; pre-compute cache row stride in words — pushed once for entire call
        move.w  d2, d3
        lsl.w   #6, d2                         ; * 64
        lsl.w   #4, d3                         ; * 16
        add.w   d3, d2                         ; * 80
        move.w  d2, -(sp)                      ; (sp) = cache_row_offset_words

        move.w  (Cache_Left_Col).w, d7
.fr_block_loop:
        cmp.w   (Cache_Head_Col).w, d7
        bgt.w   .fr_done

        ; decompose d7 into section + block for staging match
        move.w  d7, d0
        lsr.w   #8, d0                         ; sec_x
        move.w  d5, d1
        lsr.w   #8, d1                         ; sec_y
        move.w  d7, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x
        move.w  d5, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; d2 = block_index

        bsr.w   TileCache_StagedBlockMatch
        beq.s   .fr_have_block
        movem.l d5/d7, -(sp)
        bsr.w   TileCache_DecompressBlock
        movem.l (sp)+, d5/d7
.fr_have_block:

        ; staging source base: Block_Stage_Nametable + (intra_row * 16) * 2
        move.w  d5, d4
        andi.w  #$F, d4                        ; intra-block row
        lsl.w   #5, d4                         ; * 32
        lea     (Block_Stage_Nametable).l, a0
        adda.w  d4, a0                         ; a0 = staging row base

        ; first intra-block col for this block
        move.w  d7, d6
        andi.w  #$F, d6

.fr_col_loop:
        cmpi.w  #BLOCK_TILE_SIZE, d6
        bge.s   .fr_next_block

        ; world col
        move.w  d7, d1
        andi.w  #$FFF0, d1
        add.w   d6, d1                         ; world_col = block_base + intra_col
        cmp.w   (Cache_Head_Col).w, d1
        bgt.s   .fr_next_block

        ; cache col offset
        sub.w   (Cache_Left_Col).w, d1
        bmi.s   .fr_skip_col
        cmpi.w  #TILE_CACHE_COLS, d1
        bge.s   .fr_skip_col

        ; circular column mapping
        add.w   (Cache_Origin_Col).w, d1
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .fr_nowrap
        subi.w  #TILE_CACHE_COLS, d1
.fr_nowrap:

        ; read source tile from staging buffer
        move.w  d6, d0
        add.w   d0, d0                         ; intra_col * 2
        move.w  (a0, d0.w), d3                 ; d3 = nametable word

        ; dest offset = (cache_row_stride + cache_col) * 2
        move.w  (sp), d0                       ; cache_row_offset_words
        add.w   d1, d0                         ; + cache_col
        add.w   d0, d0                         ; byte offset
        lea     (Tile_Cache_Nametable).l, a1
        move.w  d3, (a1, d0.w)                 ; write tile

.fr_skip_col:
        addq.w  #1, d6
        bra.s   .fr_col_loop

.fr_next_block:
        move.w  d7, d0
        andi.w  #$FFF0, d0
        addi.w  #BLOCK_TILE_SIZE, d0
        move.w  d0, d7
        bra.w   .fr_block_loop
.fr_done:
        addq.l  #2, sp                         ; pop cache_row_offset_words
.fr_early_out:
        rts

; -----------------------------------------------
; TileCache_HSlide — circular advance: evict left columns by updating origin
; In:  d0.w = columns to evict from left side
; Out: none
; Clobbers: d0-d1
; -----------------------------------------------
TileCache_HSlide:
        tst.w   d0
        ble.s   .done
        add.w   d0, (Cache_Left_Col).w
        move.w  (Cache_Origin_Col).w, d1
        add.w   d0, d1
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .nowrap
        subi.w  #TILE_CACHE_COLS, d1
.nowrap:
        move.w  d1, (Cache_Origin_Col).w
.done:
        rts

; -----------------------------------------------
; TileCache_VSlide — evict stale top rows, shift data up
; In:  d0.w = tile rows to evict from top
; Out: none
; Clobbers: d0-d5, a0-a1
; -----------------------------------------------
TileCache_VSlide:
        tst.w   d0
        ble.s   .vslide_done
        move.w  d0, d1                         ; d1 = evict tile rows

        ; nametable: contiguous, simple memmove up
        lea     (Tile_Cache_Nametable).l, a1   ; a1 = dest (start)
        ; src = start + evict_rows * stride * 2
        ; stride * 2 = 160; evict_rows * 160
        move.w  d1, d2
        move.w  d2, d3
        lsl.w   #7, d2                         ; * 128
        lsl.w   #5, d3                         ; * 32
        add.w   d3, d2                         ; * 160
        lea     (a1, d2.w), a0                 ; a0 = source

        ; bytes to copy = (TILE_CACHE_ROWS - evict_rows) * 160
        move.w  #TILE_CACHE_ROWS, d3
        sub.w   d1, d3
        move.w  d3, d4
        lsl.w   #7, d3
        lsl.w   #5, d4
        add.w   d4, d3
        lsr.w   #2, d3                         ; longwords
        subq.w  #1, d3
.vslide_nt:
        move.l  (a0)+, (a1)+
        dbf     d3, .vslide_nt

        ; collision: evict half as many rows
        move.w  d1, d2
        lsr.w   #1, d2
        beq.s   .vslide_skip_coll

        lea     (Tile_Cache_Collision).l, a1
        ; src offset = coll_evict * 80
        move.w  d2, d3
        move.w  d3, d4
        lsl.w   #6, d3
        lsl.w   #4, d4
        add.w   d4, d3
        lea     (a1, d3.w), a0

        ; bytes = (COLL_ROWS - coll_evict) * 80
        move.w  #TILE_CACHE_COLL_ROWS, d3
        sub.w   d2, d3
        move.w  d3, d4
        lsl.w   #6, d3
        lsl.w   #4, d4
        add.w   d4, d3
        lsr.w   #2, d3
        subq.w  #1, d3
.vslide_coll:
        move.l  (a0)+, (a1)+
        dbf     d3, .vslide_coll
.vslide_skip_coll:

        add.w   d1, (Cache_Top_Row).w
.vslide_done:
        rts

; -----------------------------------------------
; TileCache_VSlideUp — evict stale bottom rows, shift data down
; In:  d0.w = tile rows to evict from bottom
; Out: none
; Clobbers: d0-d5, a0-a1
; -----------------------------------------------
TileCache_VSlideUp:
        tst.w   d0
        ble.s   .vsu_done
        move.w  d0, d1                         ; d1 = evict tile rows

        ; nametable: memmove DOWN (copy backwards to avoid overlap)
        ; dest end = start + TILE_CACHE_ROWS * 160
        ; src end  = dest end - evict_rows * 160
        lea     (Tile_Cache_Nametable).l, a1

        ; compute evict offset = evict_rows * 160
        move.w  d1, d2
        move.w  d2, d3
        lsl.w   #7, d2                         ; * 128
        lsl.w   #5, d3                         ; * 32
        add.w   d3, d2                         ; d2 = evict_rows * 160

        ; total size = TILE_CACHE_ROWS * 160
        move.w  #TILE_CACHE_ROWS, d3
        move.w  d3, d4
        lsl.w   #7, d3
        lsl.w   #5, d4
        add.w   d4, d3                         ; d3 = total bytes

        ; bytes to copy = total - evict offset
        move.w  d3, d4
        sub.w   d2, d4                         ; d4 = bytes to copy

        ; a0 = src end (start + bytes to copy)
        lea     (a1, d4.w), a0
        ; a1 = dest end (start + total bytes)
        lea     (a1, d3.w), a1

        move.w  d4, d3
        lsr.w   #2, d3                         ; longwords
        subq.w  #1, d3
.vsu_nt:
        move.l  -(a0), -(a1)
        dbf     d3, .vsu_nt

        ; collision: evict half as many rows (16px cells)
        move.w  d1, d2
        lsr.w   #1, d2
        beq.s   .vsu_skip_coll

        lea     (Tile_Cache_Collision).l, a1

        ; evict offset = coll_evict * 80
        move.w  d2, d3
        move.w  d3, d4
        lsl.w   #6, d3
        lsl.w   #4, d4
        add.w   d4, d3                         ; d3 = coll evict offset

        ; total = TILE_CACHE_COLL_ROWS * 80
        move.w  #TILE_CACHE_COLL_ROWS, d4
        move.w  d4, d5
        lsl.w   #6, d4
        lsl.w   #4, d5
        add.w   d5, d4                         ; d4 = total bytes

        ; bytes to copy
        move.w  d4, d5
        sub.w   d3, d5                         ; d5 = bytes to copy

        lea     (a1, d5.w), a0                 ; src end
        lea     (a1, d4.w), a1                 ; dest end

        move.w  d5, d3
        lsr.w   #2, d3
        subq.w  #1, d3
.vsu_coll:
        move.l  -(a0), -(a1)
        dbf     d3, .vsu_coll
.vsu_skip_coll:

        sub.w   d1, (Cache_Bottom_Row).w
.vsu_done:
        rts

; -----------------------------------------------
; TileCache_Reinit — full cache re-center for cache miss recovery
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_Reinit:
        ; recompute cache bounds centered on camera
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0
        bsr.w   Engine_To_World_Col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .ri_left_ok
        moveq   #0, d0
.ri_left_ok:
        move.w  d0, (Cache_Left_Col).w
        addi.w  #TILE_CACHE_COLS-1, d0
        move.w  d0, (Cache_Head_Col).w
        clr.w   (Cache_Origin_Col).w
        move.w  #$FFFF, (Cache_Fill_Resume_Row).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .ri_top_ok
        moveq   #0, d0
.ri_top_ok:
        move.w  d0, (Cache_Top_Row).w
        addi.w  #TILE_CACHE_ROWS-1, d0
        move.w  d0, (Cache_Bottom_Row).w

        ; invalidate staging
        move.w  #$FFFF, (Block_Stage_ID).w

        ; refill
        bsr.w   TileCache_FillAll

        ; mark plane dirty for full redraw
        st.b    (Section_Plane_Dirty).w
        rts
