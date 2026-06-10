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
; BlockStage_PtrTable — ROM table of staging slot base addresses.
; Parallel to Block_Stage_Keys; slot N's nametable starts here, collision
; follows at +BLOCK_NT_SIZE.
; -----------------------------------------------
BlockStage_PtrTable:
BLKSTG_I set 0
        rept BLOCK_STAGE_SLOTS
        dc.l Block_Stage_Buffers + BLKSTG_I * BLOCK_RAW_SIZE
BLKSTG_I set BLKSTG_I + 1
        endm

; -----------------------------------------------
; TileCache_FindStagedBlock — probe staging cache for a decompressed block
; In:  d0.w = sec_x, d1.w = sec_y, d2.w = block_index (0–255)
; Out: Z set + a1 = slot base (nametable; collision at +BLOCK_NT_SIZE) on hit;
;      Z clear on miss (a1 trashed). d0–d2 preserved.
; Clobbers: d3-d4, a1
; -----------------------------------------------
TileCache_FindStagedBlock:
        move.w  d0, d3
        lsl.w   #8, d3
        move.b  d1, d3
        swap    d3
        move.w  d2, d3                         ; d3.l = key (sec_x|sec_y|block_index)
        lea     (Block_Stage_Keys).w, a1
        moveq   #BLOCK_STAGE_SLOTS-1, d4
.probe:
        cmp.l   (a1)+, d3
        dbeq    d4, .probe
        bne.s   .miss
        ; slot index × 4 = (a1 - 4) - Block_Stage_Keys
        move.w  a1, d3
        subi.w  #(Block_Stage_Keys+4) & $FFFF, d3
        lea     BlockStage_PtrTable(pc), a1
        movea.l (a1, d3.w), a1                 ; a1 = slot base
        moveq   #0, d3                         ; Z set (hit)
        rts
.miss:
        moveq   #1, d3                         ; Z clear (miss)
        rts

; -----------------------------------------------
; TileCache_InvalidateStaging — empty all staging slots
; Clobbers: d0, a0
; -----------------------------------------------
TileCache_InvalidateStaging:
        lea     (Block_Stage_Keys).w, a0
        moveq   #BLOCK_STAGE_SLOTS-1, d0
.inv:
        move.l  #-1, (a0)+
        dbf     d0, .inv
        clr.w   (Block_Stage_Next).w
        rts

; -----------------------------------------------
; TileCache_DecompressBlock — decompress one 16×16 block into a staging slot
; Claims the next round-robin slot and records the key, so subsequent
; TileCache_FindStagedBlock probes hit it.
; In:  d0.w = sec_x, d1.w = sec_y, d2.w = block_index (0–255)
; Out: a1 = slot base (nametable; collision at +BLOCK_NT_SIZE)
; Clobbers: d0-d5, a0-a3
; -----------------------------------------------
TileCache_DecompressBlock:
        ; claim next round-robin slot, record key
        move.w  d0, d3
        lsl.w   #8, d3
        move.b  d1, d3
        swap    d3
        move.w  d2, d3                         ; d3.l = key
        move.w  (Block_Stage_Next).w, d4
        move.w  d4, d5
        addq.w  #1, d5
        cmpi.w  #BLOCK_STAGE_SLOTS, d5
        blt.s   .rr_ok
        moveq   #0, d5
.rr_ok:
        move.w  d5, (Block_Stage_Next).w
        add.w   d4, d4
        add.w   d4, d4                         ; slot index × 4
        lea     (Block_Stage_Keys).w, a1
        move.l  d3, (a1, d4.w)
        lea     BlockStage_PtrTable(pc), a1
        movea.l (a1, d4.w), a3                 ; a3 = dest slot base

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
        movea.l a3, a1
        move.l  a3, -(sp)                      ; S4LZ_Decompress clobbers a3, advances a1
        bsr.w   S4LZ_Decompress
        movea.l (sp)+, a1                      ; a1 = slot base
        rts

.empty_block:
        movea.l a3, a0
        move.w  #(BLOCK_RAW_SIZE/4)-1, d0
.zero_loop:
        clr.l   (a0)+
        dbf     d0, .zero_loop
        movea.l a3, a1
        rts

; -----------------------------------------------
; TileCache_CopyBlockColumn — copy a vertical run of one block column into cache
; In:  d0.w = intra-block col (0–15)
;      d1.w = cache col offset (world_col - Cache_Left_Col)
;      d2.w = dest cache row offset (world_row - Cache_Top_Row); even
;      d3.w = rows to copy (> 0, even)
;      d4.w = source start row within block (0–15, even)
;      a1   = staged block base (nametable; collision at +BLOCK_NT_SIZE)
; Out: none; a1 preserved
; Clobbers: d0-d3, d5, a0, a2
; Note: d2/d3/d4 even is guaranteed because Cache_Top_Row is kept even and
;       block tops are multiples of 16 — collision halving stays exact.
; -----------------------------------------------
TileCache_CopyBlockColumn:
        ; wrap d1 (logical cache col) to physical column via circular origin
        add.w   (Cache_Origin_Col).w, d1
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d1
.col_nowrap:
        ; source: slot base + (src_row * 16 + col) * 2
        movea.l a1, a0
        move.w  d4, d5
        lsl.w   #5, d5                         ; src_row * 32 bytes
        adda.w  d5, a0
        move.w  d0, d5
        add.w   d5, d5                         ; col * 2
        adda.w  d5, a0                         ; a0 = first tile word in run

        ; dest: Tile_Cache_Nametable + (dest_row * stride + cache_col) * 2
        ; ×80 = ((x<<2)+x)<<4 — single temp
        move.w  d2, d5
        lsl.w   #2, d5
        add.w   d2, d5
        lsl.w   #4, d5                         ; d5 = dest_row * 80
        add.w   d1, d5                         ; + cache_col
        add.w   d5, d5                         ; byte offset
        lea     (Tile_Cache_Nametable).l, a2
        adda.w  d5, a2

        move.w  d3, d5
        subq.w  #1, d5
.copy_nt:
        move.w  (a0), (a2)
        lea     BLOCK_TILE_SIZE*2(a0), a0      ; next block row (32 bytes)
        lea     TILE_CACHE_STRIDE*2(a2), a2    ; next cache row (160 bytes)
        dbf     d5, .copy_nt

        ; collision: src = slot base + BLOCK_NT_SIZE + (src_row/2)*16 + col
        lea     BLOCK_NT_SIZE(a1), a0
        move.w  d4, d5
        lsl.w   #3, d5                         ; (src_row/2) * 16 = src_row * 8
        adda.w  d5, a0
        adda.w  d0, a0                         ; + col (bytes, not words)

        ; dest: Tile_Cache_Collision + (dest_row/2)*80 + cache_col
        lsr.w   #1, d2                         ; dest collision row
        move.w  d2, d5
        lsl.w   #2, d5
        add.w   d2, d5
        lsl.w   #4, d5                         ; collision_row * 80
        add.w   d1, d5
        lea     (Tile_Cache_Collision).l, a2
        adda.w  d5, a2

        lsr.w   #1, d3                         ; tile rows → collision rows
        subq.w  #1, d3
        bmi.s   .done_coll
.copy_coll:
        move.b  (a0), (a2)
        lea     BLOCK_TILE_SIZE(a0), a0        ; next collision row in block (16 bytes)
        lea     TILE_CACHE_STRIDE(a2), a2      ; next collision row in cache (80 bytes)
        dbf     d3, .copy_coll
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
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera tile row (engine)
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .top_ok
        moveq   #0, d0
.top_ok:
        andi.w  #$FFFE, d0                     ; keep Cache_Top_Row even (collision cell alignment)
        move.w  d0, (Cache_Top_Row).w
        addi.w  #TILE_CACHE_ROWS-1, d0
        move.w  d0, (Cache_Bottom_Row).w

        bsr.w   TileCache_InvalidateStaging

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

        ; dest row offset = block_top_tile - Cache_Top_Row.
        ; If the block straddles the cache top, clip dest to row 0 and
        ; offset the SOURCE by the clipped amount instead.
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2          ; signed dest row
        move.w  d2, d7
        bpl.s   .fill_no_clip
        moveq   #0, d2
.fill_no_clip:
        sub.w   d2, d7
        neg.w   d7                             ; d7 = source start row (0 if no clip)
        cmpi.w  #BLOCK_TILE_SIZE, d7
        bge.s   .fill_skip_col                 ; block entirely above cache

        ; rows = min(TILE_CACHE_ROWS - dest_row, BLOCK_TILE_SIZE - src_start)
        move.w  #TILE_CACHE_ROWS, d3
        sub.w   d2, d3
        ble.s   .fill_skip_col                 ; block entirely below cache
        neg.w   d7
        addi.w  #BLOCK_TILE_SIZE, d7           ; d7 = rows available in block
        cmp.w   d7, d3
        ble.s   .fill_rows_ok
        move.w  d7, d3
.fill_rows_ok:
        movem.l d0/d4-d6, -(sp)
        move.w  #BLOCK_TILE_SIZE, d4
        sub.w   d7, d4                         ; d4 = source start row
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d0/d4-d6
.fill_skip_col:
        addq.w  #1, d0
        cmpi.w  #BLOCK_TILE_SIZE, d0
        blt.s   .fill_copy_col

        ; next block col
        addq.w  #1, d6
        cmp.w   4(sp), d6                     ; compare with end_block_col
        ble.w   .block_col_loop

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
        ; --- frame gate: at most one fill pass per physical frame ---
        ; Frame_Counter only increments in VBlank, so all game-loop
        ; iterations within the same VBlank period see the same value.
        move.w  (Frame_Counter).w, d0
        cmp.w   (Cache_Fill_Last_Frame).w, d0
        beq.w   .fill_return
        move.w  d0, (Cache_Fill_Last_Frame).w

        ; --- reset per-frame decompress budget (column fill only) ---
        move.w  #BLOCK_DECOMP_BUDGET, (Cache_Fill_Budget).w

        ; --- finish any pending partial column before extending further.
        ;     At most one partial can be outstanding (a partial exhausts the
        ;     budget, which stops all further column work for the frame). ---
        move.w  (Cache_Fill_Resume_Col).w, d5
        cmpi.w  #$FFFF, d5
        beq.s   .no_pending
        cmp.w   (Cache_Left_Col).w, d5
        blt.s   .pending_stale                 ; column evicted since — drop it
        cmp.w   (Cache_Head_Col).w, d5
        bgt.s   .pending_stale
        ; if rows were evicted from the top since, resume from the new top
        move.w  (Cache_Top_Row).w, d0
        cmp.w   (Cache_Fill_Resume_Row).w, d0
        ble.s   .pending_row_ok
        move.w  d0, (Cache_Fill_Resume_Row).w
.pending_row_ok:
        bsr.w   TileCache_FillColumn
        tst.w   d0
        bne.w   .v_section                     ; budget out again — vertical still runs
        bra.s   .no_pending
.pending_stale:
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w
.no_pending:

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

        ; --- fill rightward columns (evict 1 from left as needed) ---
        move.w  (Cache_Head_Col).w, d5
.h_right_fill:
        cmp.w   d7, d5
        bge.s   .h_right_done
        addq.w  #1, d5

        ; evict 1 column from left if cache is at capacity
        move.w  d5, d0
        sub.w   (Cache_Left_Col).w, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .h_no_evict
        moveq   #1, d0
        bsr.w   TileCache_HSlide
.h_no_evict:
        move.w  d5, (Cache_Head_Col).w         ; commit before fill (resume is keyed by column)

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillColumn
        movem.l (sp)+, d5/d7
        tst.w   d0
        beq.s   .h_right_fill
        ; budget out — skip remaining column work, vertical still runs
        addq.l  #2, sp                         ; pop desired_left
        bra.w   .v_section
.h_right_done:

        ; --- fill leftward columns (evict 1 from right as needed) ---
        move.w  (sp)+, d4                      ; d4 = desired_left
        move.w  (Cache_Left_Col).w, d5
.h_left_fill:
        cmp.w   d4, d5
        ble.s   .h_left_done
        subq.w  #1, d5

        ; evict 1 column from right if cache is at capacity
        move.w  (Cache_Head_Col).w, d0
        sub.w   d5, d0
        cmpi.w  #TILE_CACHE_COLS, d0
        blt.s   .h_no_evict_left
        subq.w  #1, (Cache_Head_Col).w
.h_no_evict_left:

        ; commit + slide origin left before fill
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
        tst.w   d0
        beq.s   .h_left_fill
.h_left_done:

.v_section:
        ; --- compute desired top edge (kept even: collision cell alignment) ---
        move.l  (Camera_Y).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .v_top_pos
        moveq   #0, d0
.v_top_pos:
        andi.w  #$FFFE, d0
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

        ; --- fill downward rows (evict 2 from top as needed; Top stays even) ---
        move.w  (Cache_Bottom_Row).w, d5
        cmp.w   d7, d5
        bge.s   .v_bottom_done

.v_bottom_fill:
        addq.w  #1, d5
        cmp.w   d7, d5
        bgt.s   .v_bottom_done

        ; evict 2 rows from top if cache is at capacity
        move.w  d5, d0
        sub.w   (Cache_Top_Row).w, d0
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .v_no_evict
        moveq   #2, d0
        bsr.w   TileCache_VSlide
.v_no_evict:

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillRow
        movem.l (sp)+, d5/d7

        move.w  d5, (Cache_Bottom_Row).w
        bra.s   .v_bottom_fill
.v_bottom_done:

        ; --- fill upward rows in pairs (evict 2 from bottom as needed) ---
        move.w  (sp)+, d4                      ; d4 = desired_top (even)
        move.w  (Cache_Top_Row).w, d5
.v_top_fill:
        cmp.w   d4, d5
        ble.s   .v_top_done
        subq.w  #2, d5                         ; 2-row step keeps Top even

        ; evict 2 rows from bottom if cache would exceed capacity
        move.w  (Cache_Bottom_Row).w, d0
        sub.w   d5, d0
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .v_no_evict_up
        moveq   #2, d0
        movem.l d4-d5, -(sp)                   ; VSlideUp clobbers d4/d5; preserve loop target + cursor
        bsr.w   TileCache_VSlideUp
        movem.l (sp)+, d4-d5
.v_no_evict_up:

        ; decrement Cache_Top_Row BEFORE fill so FillRow sees correct offset
        move.w  d5, (Cache_Top_Row).w

        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillRow              ; new top row
        movem.l (sp)+, d4-d5
        addq.w  #1, d5
        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillRow              ; second row of the pair
        movem.l (sp)+, d4-d5
        subq.w  #1, d5
        bra.s   .v_top_fill
.v_top_done:
.fill_return:
        rts

; -----------------------------------------------
; TileCache_FillColumn — fill one world column into cache (budget-limited)
; In:  d5.w = world tile col (must already be within cache bounds)
; Out: d0.w = 0 if column complete, nonzero if partial.
;      On partial, resume state (Cache_Fill_Resume_Col/Row) is stored;
;      Tile_Cache_Fill finishes it first next frame.
; Uses Cache_Fill_Budget — shared per-frame decompress allowance.
; Clobbers: d0-d7, a0-a3
; -----------------------------------------------
TileCache_FillColumn:
        ; resume only if a partial is pending for THIS column
        move.w  (Cache_Top_Row).w, d7
        cmp.w   (Cache_Fill_Resume_Col).w, d5
        bne.s   .fc_from_top
        move.w  (Cache_Fill_Resume_Row).w, d7
.fc_from_top:

.fc_block_loop:
        cmp.w   (Cache_Bottom_Row).w, d7
        bgt.w   .fc_complete                   ; cursor past bottom — done

        ; decompose into section + block + intra
        move.w  d5, d0
        lsr.w   #8, d0                         ; sec_x
        move.w  d7, d1
        lsr.w   #8, d1                         ; sec_y
        move.w  d5, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; d2 = block_index

        ; probe staging cache (a1 = slot base on hit)
        bsr.w   TileCache_FindStagedBlock
        beq.s   .fc_have_block

        ; need decompress — check shared frame budget
        tst.w   (Cache_Fill_Budget).w
        beq.s   .fc_budget_out
        subq.w  #1, (Cache_Fill_Budget).w

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_DecompressBlock      ; a1 = slot base
        movem.l (sp)+, d5/d7
.fc_have_block:

        ; copy run [d7 .. min(block_bottom, Cache_Bottom_Row)]
        move.w  d5, d0
        andi.w  #$F, d0                        ; intra-block col
        move.w  d5, d1
        sub.w   (Cache_Left_Col).w, d1         ; cache col offset
        move.w  d7, d2
        sub.w   (Cache_Top_Row).w, d2          ; dest row offset (even)
        move.w  d7, d4
        andi.w  #$F, d4                        ; source start row (even)

        ; rows = min(block_top + 16, Bottom + 1) - cursor
        move.w  d7, d3
        andi.w  #$FFF0, d3
        addi.w  #BLOCK_TILE_SIZE, d3           ; block bottom + 1
        move.w  (Cache_Bottom_Row).w, d6
        addq.w  #1, d6
        cmp.w   d6, d3
        ble.s   .fc_rows_ok
        move.w  d6, d3
.fc_rows_ok:
        sub.w   d7, d3                         ; d3 = rows (> 0, even)

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d5/d7

        ; advance cursor to next block top
        andi.w  #$FFF0, d7
        addi.w  #BLOCK_TILE_SIZE, d7
        bra.w   .fc_block_loop

.fc_budget_out:
        move.w  d5, (Cache_Fill_Resume_Col).w
        move.w  d7, (Cache_Fill_Resume_Row).w
        moveq   #1, d0
        rts

.fc_complete:
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w
        moveq   #0, d0
        rts

; -----------------------------------------------
; TileCache_FillRow — fill one world row into cache (nametable + collision)
; In:  d5.w = world tile row to fill
; Out: none
; Clobbers: d0-d7, a0-a3
; Note: collision is copied only on the odd row of each 16px cell (the row
;       that completes the cell). Cache_Top_Row is kept even, so cell
;       boundaries align with world block data.
; -----------------------------------------------
TileCache_FillRow:
        ; cache row offset (constant for all columns)
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.w   .fr_early_out

        ; collision dest row offset (bytes); $FFFF = even row, skip collision
        move.w  #$FFFF, d3
        btst    #0, d2
        beq.s   .fr_no_coll
        move.w  d2, d3
        lsr.w   #1, d3                         ; collision row
        move.w  d3, d4
        lsl.w   #2, d4
        add.w   d3, d4
        lsl.w   #4, d4                         ; * 80
        move.w  d4, d3
.fr_no_coll:
        move.w  d3, -(sp)                      ; 2(sp) = collision row offset

        ; pre-compute cache row stride in words — pushed once for entire call
        move.w  d2, d3
        lsl.w   #6, d2                         ; * 64
        lsl.w   #4, d3                         ; * 16
        add.w   d3, d2                         ; * 80
        move.w  d2, -(sp)                      ; 0(sp) = cache_row_offset_words

        move.w  (Cache_Left_Col).w, d7
.fr_block_loop:
        cmp.w   (Cache_Head_Col).w, d7
        bgt.w   .fr_done

        ; decompose d7 into section + block for staging probe
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

        bsr.w   TileCache_FindStagedBlock      ; a1 = slot base on hit
        beq.s   .fr_have_block
        movem.l d5/d7, -(sp)
        bsr.w   TileCache_DecompressBlock      ; a1 = slot base
        movem.l (sp)+, d5/d7
.fr_have_block:

        ; staging source bases for this row:
        ;   a0 = nametable row base = slot + intra_row * 32
        ;   a3 = collision row base = slot + BLOCK_NT_SIZE + (intra_row/2) * 16
        move.w  d5, d4
        andi.w  #$F, d4                        ; intra-block row
        move.w  d4, d3
        lsl.w   #5, d4                         ; * 32
        lea     (a1, d4.w), a0
        lsl.w   #3, d3                         ; (intra_row/2) * 16 = intra_row * 8
        lea     BLOCK_NT_SIZE(a1), a3
        adda.w  d3, a3

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

        ; read source tile from staging slot
        move.w  d6, d0
        add.w   d0, d0                         ; intra_col * 2
        move.w  (a0, d0.w), d3                 ; d3 = nametable word

        ; dest offset = (cache_row_stride + cache_col) * 2
        move.w  (sp), d0                       ; cache_row_offset_words
        add.w   d1, d0                         ; + cache_col
        add.w   d0, d0                         ; byte offset
        lea     (Tile_Cache_Nametable).l, a1
        move.w  d3, (a1, d0.w)                 ; write tile

        ; collision byte (cell-completing rows only)
        move.w  2(sp), d0
        cmpi.w  #$FFFF, d0
        beq.s   .fr_skip_col
        add.w   d1, d0                         ; + cache col (byte index)
        lea     (Tile_Cache_Collision).l, a2
        move.b  (a3, d6.w), (a2, d0.w)

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
        addq.l  #4, sp                         ; pop row offsets
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
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0
        bsr.w   Engine_To_World_Row
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .ri_top_ok
        moveq   #0, d0
.ri_top_ok:
        andi.w  #$FFFE, d0                     ; keep Cache_Top_Row even (collision cell alignment)
        move.w  d0, (Cache_Top_Row).w
        addi.w  #TILE_CACHE_ROWS-1, d0
        move.w  d0, (Cache_Bottom_Row).w

        bsr.w   TileCache_InvalidateStaging

        ; refill
        bsr.w   TileCache_FillAll

        ; mark plane dirty for full redraw
        st.b    (Section_Plane_Dirty).w
        rts
