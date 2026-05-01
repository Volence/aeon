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
        ; --- horizontal fill ---
        ; compute desired right edge (camera right + margin, world coords)
        move.l  (Camera_X).w, d6
        swap    d6
        addi.w  #327, d6                       ; 320 + 7 (screen width + alignment)
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        addi.w  #TILE_CACHE_MARGIN_H, d0
        move.w  d0, d7                         ; d7 = desired right edge (world col)

        move.w  (Cache_Head_Col).w, d5
        cmp.w   d7, d5
        bge.s   .h_right_done

        ; fill columns d5+1 .. d7
.h_right_fill:
        addq.w  #1, d5
        cmp.w   d7, d5
        bgt.s   .h_right_done

        ; determine block for this column
        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillColumn
        movem.l (sp)+, d5/d7
        move.w  d5, (Cache_Head_Col).w
        bra.s   .h_right_fill
.h_right_done:

        ; --- leftward cache miss check ---
        move.l  (Camera_X).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .h_left_clamp_ok
        moveq   #0, d0
.h_left_clamp_ok:
        cmp.w   (Cache_Left_Col).w, d0
        bge.s   .h_left_done
        bsr.w   TileCache_Reinit
        rts
.h_left_done:

        ; --- vertical fill ---
        ; compute desired bottom edge
        move.l  (Camera_Y).w, d6
        swap    d6
        addi.w  #231, d6                       ; 224 + 7
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Row
        addi.w  #TILE_CACHE_MARGIN_V, d0
        move.w  d0, d7

        move.w  (Cache_Bottom_Row).w, d5
        cmp.w   d7, d5
        bge.s   .v_bottom_done

.v_bottom_fill:
        addq.w  #1, d5
        cmp.w   d7, d5
        bgt.s   .v_bottom_done

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillRow
        movem.l (sp)+, d5/d7
        move.w  d5, (Cache_Bottom_Row).w
        bra.s   .v_bottom_fill
.v_bottom_done:

        ; --- upward cache miss check ---
        move.l  (Camera_Y).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .v_top_clamp_ok
        moveq   #0, d0
.v_top_clamp_ok:
        cmp.w   (Cache_Top_Row).w, d0
        bge.s   .v_top_done
        bsr.w   TileCache_Reinit
.v_top_done:
        rts

; -----------------------------------------------
; TileCache_FillColumn — fill one world column into cache at Cache_Head_Col+1
; In:  d5.w = world tile col to fill
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillColumn:
        ; slide if needed: check if Head_Col - Left_Col >= TILE_CACHE_COLS
        move.w  (Cache_Head_Col).w, d0
        sub.w   (Cache_Left_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS-1, d0
        blt.s   .fc_no_slide
        ; need to evict left columns
        moveq   #BLOCK_TILE_SIZE, d0
        bsr.w   TileCache_HSlide
.fc_no_slide:

        ; cache col offset for new column
        move.w  d5, d1
        sub.w   (Cache_Left_Col).w, d1         ; d1 = cache col offset

        ; iterate over all block rows in the cache's vertical range
        move.w  (Cache_Top_Row).w, d7
.fc_block_loop:
        cmp.w   (Cache_Bottom_Row).w, d7
        bgt.s   .fc_done

        ; decompose into section + block + intra
        move.w  d5, d0
        lsr.w   #8, d0                         ; sec_x = world_col / 256
        move.w  d7, d6
        lsr.w   #8, d6                         ; sec_y = world_row / 256
        move.w  d6, d1                         ; d1 = sec_y

        move.w  d5, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x within section
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y within section
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; d2 = block_index

        ; check if staging already has this block
        bsr.w   TileCache_StagedBlockMatch
        beq.s   .fc_have_block
        movem.l d5/d7, -(sp)
        bsr.w   TileCache_DecompressBlock
        movem.l (sp)+, d5/d7
.fc_have_block:

        ; intra-block col
        move.w  d5, d0
        andi.w  #$F, d0                        ; d0 = intra-block col (0-15)

        ; cache col offset
        move.w  d5, d1
        sub.w   (Cache_Left_Col).w, d1

        ; cache row offset = block_top_row - Cache_Top_Row
        move.w  d7, d2
        andi.w  #$FFF0, d2                     ; block_top_row (rounded to block boundary)
        sub.w   (Cache_Top_Row).w, d2
        bmi.s   .fc_clamp_top
        bra.s   .fc_calc_rows
.fc_clamp_top:
        moveq   #0, d2
.fc_calc_rows:
        moveq   #BLOCK_TILE_SIZE, d3
        ; clamp rows to cache bounds
        move.w  #TILE_CACHE_ROWS, d4
        sub.w   d2, d4
        cmp.w   d4, d3
        ble.s   .fc_rows_ok
        move.w  d4, d3
.fc_rows_ok:
        tst.w   d3
        ble.s   .fc_next_block

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d5/d7

.fc_next_block:
        ; advance to next block row (align to next 16-tile boundary)
        move.w  d7, d0
        andi.w  #$FFF0, d0
        addi.w  #BLOCK_TILE_SIZE, d0
        move.w  d0, d7
        bra.s   .fc_block_loop
.fc_done:
        rts

; -----------------------------------------------
; TileCache_FillRow — fill one world row into cache at Cache_Bottom_Row+1
; In:  d5.w = world tile row to fill
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillRow:
        ; slide if needed
        move.w  (Cache_Bottom_Row).w, d0
        sub.w   (Cache_Top_Row).w, d0
        cmpi.w  #TILE_CACHE_ROWS-1, d0
        blt.s   .fr_no_slide
        moveq   #BLOCK_TILE_SIZE, d0
        bsr.w   TileCache_VSlide
.fr_no_slide:

        ; iterate over all block cols in the cache's horizontal range
        move.w  (Cache_Left_Col).w, d7
.fr_block_loop:
        cmp.w   (Cache_Head_Col).w, d7
        bgt.s   .fr_done

        ; decompose into section + block + intra
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

        ; intra-block row
        move.w  d5, d0
        andi.w  #$F, d0                        ; d0 = intra-block row (0-15)

        ; for row fill: copy all BLOCK_TILE_SIZE cols of this block into cache
        ; Rather than a dedicated row copy, reuse column copy for each col in block
        moveq   #0, d6                         ; intra-block col counter
.fr_col_loop:
        move.w  d6, d0                         ; intra-block col

        ; cache col offset
        move.w  d7, d1
        add.w   d6, d1                         ; world col = block_left + intra_col
        sub.w   (Cache_Left_Col).w, d1
        bmi.s   .fr_skip_col
        cmpi.w  #TILE_CACHE_COLS, d1
        bge.s   .fr_skip_col

        ; cache row offset
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.s   .fr_skip_col

        moveq   #1, d3                        ; 1 row only
        movem.l d5-d7, -(sp)
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d5-d7

.fr_skip_col:
        addq.w  #1, d6
        cmpi.w  #BLOCK_TILE_SIZE, d6
        blt.s   .fr_col_loop

        ; advance to next block col
        move.w  d7, d0
        andi.w  #$FFF0, d0
        addi.w  #BLOCK_TILE_SIZE, d0
        move.w  d0, d7
        bra.s   .fr_block_loop
.fr_done:
        rts

; -----------------------------------------------
; TileCache_HSlide — evict stale left columns, shift data left
; In:  d0.w = columns to evict from left side
; Out: none
; Clobbers: d0-d5, a0-a1
; -----------------------------------------------
TileCache_HSlide:
        tst.w   d0
        ble.s   .hslide_done
        move.w  d0, d1                         ; d1 = evict count

        ; nametable: per-row shift
        lea     (Tile_Cache_Nametable).l, a0
        move.w  #TILE_CACHE_ROWS-1, d3
        move.w  d1, d4
        add.w   d4, d4                         ; evict bytes per row (words)
.hslide_nt_row:
        lea     (a0, d4.w), a1                 ; a1 = src (start + evict_cols*2)
        move.w  #TILE_CACHE_COLS, d5
        sub.w   d1, d5                         ; words to copy
        subq.w  #1, d5
.hslide_nt_copy:
        move.w  (a1)+, (a0)+
        dbf     d5, .hslide_nt_copy
        ; skip past the gap where evicted cols were in dest
        adda.w  d4, a0                         ; dest already advanced by copy; add evict gap
        dbf     d3, .hslide_nt_row

        ; collision: per-row shift (byte-sized, half rows)
        lea     (Tile_Cache_Collision).l, a0
        move.w  #TILE_CACHE_COLL_ROWS-1, d3
.hslide_coll_row:
        lea     (a0, d1.w), a1                 ; src = dest + evict cols
        move.w  #TILE_CACHE_COLS, d5
        sub.w   d1, d5
        subq.w  #1, d5
.hslide_coll_copy:
        move.b  (a1)+, (a0)+
        dbf     d5, .hslide_coll_copy
        adda.w  d1, a0
        dbf     d3, .hslide_coll_row

        add.w   d1, (Cache_Left_Col).w
.hslide_done:
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
