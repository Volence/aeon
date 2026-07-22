; 2D tile cache (§4.7)
; Linear 2D buffer in lower RAM. Slides in both axes as camera moves.
; Block-based decompression: each 16×16 tile block decompressed on demand.
; Continuous-scroll: camera, player, and entities live in WORLD coordinates,
; so a camera tile coord (Camera_X/8, Camera_Y/8) IS already a world tile coord.

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
        add.w   (Cache_Origin_Row).w, d1
        cmpi.w  #TILE_CACHE_ROWS, d1
        blt.s   .row_nowrap
        subi.w  #TILE_CACHE_ROWS, d1
.row_nowrap:
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
; In:  d0.w = world tile col, d1.w = world tile row, d3.b = layer (0=path A, 1=path B)
; Out: d0.b = collision type byte (0 = air)
; Clobbers: d0-d2, a0
; Note: layer input is in d3 (not d2) so the ×80 shift-add can use d2 as scratch
;       without clobbering the layer before the plane select.
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
        move.w  (Cache_Origin_Row).w, d2
        lsr.w   #1, d2                         ; origin even → exact collision origin
        add.w   d2, d1
        cmpi.w  #TILE_CACHE_COLL_ROWS, d1
        blt.s   .row_nowrap
        subi.w  #TILE_CACHE_COLL_ROWS, d1
.row_nowrap:
        ; d1 * 80 via shift-add
        move.w  d1, d2
        lsl.w   #6, d1
        lsl.w   #4, d2
        add.w   d2, d1
        add.w   d0, d1
        ; layer plane select: layer B shifts byte index into the second plane
        tst.b   d3
        beq.s   .plane_selected
        addi.w  #TILE_CACHE_COLL_SIZE, d1      ; plane B starts at +TILE_CACHE_COLL_SIZE
.plane_selected:
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
; Index entry forms: 0 = empty (zero-fill); bit 31 set = RAW DIRECT (offset
; from table base to an uncompressed 768-byte block in the dict region —
; straight ROM→slot copy); else = S4LZ v3 stream decoded with the section's
; block dictionary pre-seeding the window (Sec_sec_block_dict/_len).
; In:  d0.w = sec_x, d1.w = sec_y, d2.w = block_index (0–255)
; Out: a1 = slot base (nametable; collision at +BLOCK_NT_SIZE)
; Clobbers: d0-d7, a0-a4
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

        ; -- world-edge guard: the fixed-width cache extends past the act
        ;    grid at boundaries (and debug-fly wanders anywhere), so out-of-
        ;    grid requests are legitimate — they decompress as blank blocks
        ;    (tile 0, collision 0) instead of indexing the Sec table out of
        ;    range. The key recorded above caches the blank like any block. --
        cmp.w   Act_grid_w(a0), d0
    ifdef __DEBUG__
        bhs.w   .empty_block            ; debug: the assert block pushes .empty_block past .s range
    else
        bhs.s   .empty_block            ; plain: within .s range (asl/sigil relax per shape)
    endif
        cmp.w   Act_grid_h(a0), d1
    ifdef __DEBUG__
        bhs.w   .empty_block            ; debug: the assert block pushes .empty_block past .s range
    else
        bhs.s   .empty_block            ; plain: within .s range (asl/sigil relax per shape)
    endif

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
        ; d3 × Sec_len ($42 = 66 = 64 + 2)
        if Sec_len <> 66
          error "tile_cache Sec stride (lsl #6 + lsl #1 = ×66) assumes Sec_len=66 — update the shifts"
        endif
        move.w  d3, d4
        lsl.w   #6, d3                         ; flat × 64
        lsl.w   #1, d4                         ; flat × 2
        add.w   d4, d3                         ; flat × 66
        adda.w  d3, a1                         ; a1 = Sec struct pointer

        movea.l Sec_sec_block_index(a1), a2    ; a2 = block index table base (ROM)
        move.l  a2, d3
    ifdef __DEBUG__
        beq.w   .empty_block            ; debug: the assert block pushes .empty_block past .s range
    else
        beq.s   .empty_block            ; plain: within .s range (asl/sigil relax per shape)
    endif

        ; index into block table: block_index × 4
        move.w  d2, d3
        lsl.w   #2, d3
        move.l  (a2, d3.w), d0                 ; d0 = offset from table base (0 = null)
    ifdef __DEBUG__
        beq.w   .empty_block            ; debug: the assert block pushes .empty_block past .s range
    else
        beq.s   .empty_block            ; plain: within .s range (asl/sigil relax per shape)
    endif
        bmi.s   .raw_direct                    ; bit 31 = raw block in the dict region

        ; compressed v3 stream — decode with the section dictionary window
        lea     (a2, d0.l), a0                 ; a0 = compressed block data
        move.w  Sec_sec_block_dict_len(a1), d4 ; d4 = dict bytes (0 = none)
        movea.l Sec_sec_block_dict(a1), a4     ; a4 = raw dict base (ROM)
        movea.l a3, a1
        move.l  a3, -(sp)                      ; decompress clobbers a3, advances a1
        bsr.w   S4LZ_DecompressDict
        movea.l (sp)+, a1                      ; a1 = slot base
        rts

.raw_direct:
        bclr    #31, d0                        ; d0 = byte offset of the raw block
        ifdebug assert.l d0, hs, #BLOCK_INDEX_SIZE  ; raw region sits past the index
        ifdebug move.w  d0, d3
        ifdebug andi.w  #1, d3
        ifdebug assert.w d3, eq                ; raw offset must be word-even
        lea     (a2, d0.l), a0                 ; a0 = raw 768-byte block (ROM)
        movea.l a3, a1
        ; straight ROM→slot copy, 24 × 32-byte movem bursts
        ; (76r + 72w + 8 lea + 10 dbf = 166 c per 32 B ≈ 4.0k c/block —
        ; cheaper than any decompress of the same block)
        moveq   #(BLOCK_RAW_SIZE/32)-1, d7
.raw_copy:
        movem.l (a0)+, d0-d6/a2
        movem.l d0-d6/a2, (a1)
        lea     32(a1), a1
        dbf     d7, .raw_copy
        movea.l a3, a1                         ; a1 = slot base
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
;      a5   = Tile_Cache_Nametable base (H6 hoist — caller-set, loop-invariant)
;      a6   = Tile_Cache_Collision base (H6 hoist — caller-set, loop-invariant)
; Out: none; a1/a5/a6 preserved
; Clobbers: d0-d3, d5, a0, a2-a3
; Note: d2/d3/d4 even is guaranteed because Cache_Top_Row is kept even and
;       block tops are multiples of 16 — collision halving stays exact.
;       Cache_Origin_Row is also kept even, so the physical row keeps the
;       logical row's parity and physical_row/2 = physical collision row.
; -----------------------------------------------
TileCache_CopyBlockColumn:
        ; wrap d1 (logical cache col) to physical column via circular origin
        add.w   (Cache_Origin_Col).w, d1
        cmpi.w  #TILE_CACHE_COLS, d1
        blt.s   .col_nowrap
        subi.w  #TILE_CACHE_COLS, d1
.col_nowrap:
        ; wrap d2 (logical dest row) to physical row via circular origin
        add.w   (Cache_Origin_Row).w, d2
        cmpi.w  #TILE_CACHE_ROWS, d2
        blt.s   .row_nowrap
        subi.w  #TILE_CACHE_ROWS, d2
.row_nowrap:
        ; source: slot base + (src_row * 16 + col) * 2
        movea.l a1, a0
        move.w  d4, d5
        lsl.w   #5, d5                         ; src_row * 32 bytes
        adda.w  d5, a0
        move.w  d0, d5
        add.w   d5, d5                         ; col * 2
        adda.w  d5, a0                         ; a0 = first tile word in run

        ; dest: Tile_Cache_Nametable + (phys_row * stride + cache_col) * 2
        ; ×80 = ((x<<2)+x)<<4 — single temp
        move.w  d2, d5
        lsl.w   #2, d5
        add.w   d2, d5
        lsl.w   #4, d5                         ; d5 = phys_row * 80
        add.w   d1, d5                         ; + cache_col
        add.w   d5, d5                         ; byte offset
        movea.l a5, a2                        ; H6: hoisted NT base (a5, set by the caller — survives DecompressBlock)
        adda.w  d5, a2

        ; wrap-split: the vertical run (<=16 rows) crosses the cache row-59->0
        ; boundary at most once, so emit <=2 straight copies split there instead
        ; of a per-row sentinel test — byte-identical dest, no per-row wrap branch.
        move.w  #TILE_CACHE_ROWS, d5
        sub.w   d2, d5                         ; d5 = rows until the dest column wraps
        cmp.w   d3, d5
        bge.s   .nt_one_run                    ; whole run fits before the wrap
        subq.w  #1, d5
.nt_run1:
        move.w  (a0), (a2)
        lea     BLOCK_TILE_SIZE*2(a0), a0      ; next block row (32 bytes)
        lea     TILE_CACHE_STRIDE*2(a2), a2    ; next cache row (160 bytes)
        dbf     d5, .nt_run1
        suba.w  #TILE_CACHE_NT_SIZE, a2        ; dest wraps row 59 -> 0, keeping cache_col
        move.w  d3, d5
        add.w   d2, d5
        subi.w  #TILE_CACHE_ROWS, d5           ; d5 = rows after the wrap
        bra.s   .nt_run2
.nt_one_run:
        move.w  d3, d5
.nt_run2:
        subq.w  #1, d5
.nt_run2_loop:
        move.w  (a0), (a2)
        lea     BLOCK_TILE_SIZE*2(a0), a0
        lea     TILE_CACHE_STRIDE*2(a2), a2
        dbf     d5, .nt_run2_loop

        ; collision plane A: src = slot base + BLOCK_NT_SIZE + (src_row/2)*16 + col
        ; src_row (d4) is even here, but use the parity-safe macro anyway so this
        ; site cannot drift into the FillRow odd-row trap class (§5).
        lea     BLOCK_NT_SIZE(a1), a0
        move.w  d4, d5
        collSrcRowBase d5                      ; (src_row/2) * BLOCK_COLL_COLS
        adda.w  d5, a0
        adda.w  d0, a0                         ; + col (bytes, not words)

        ; dest plane A: Tile_Cache_Collision + (phys_row/2)*80 + cache_col
        lsr.w   #1, d2                         ; d2 = physical collision row (halved)
        move.w  d2, d5
        lsl.w   #2, d5
        add.w   d2, d5
        lsl.w   #4, d5                         ; d5 = collision_row * 80
        add.w   d1, d5                         ; d5 = dest byte offset within plane
        movea.l a6, a2                        ; H6: hoisted collision base (a6, set by the caller)
        adda.w  d5, a2

        lsr.w   #1, d3                         ; d3 = collision rows to copy (tile rows / 2)
        ; Both planes copied in ONE run: the fixed displacements reach plane B
        ; from the plane-A cursors (source +BLOCK_COLL_PLANE_SIZE, dest
        ; +TILE_CACHE_COLL_SIZE). Plane B's wrap is free — when the plane-A
        ; dest wraps to row 0, the +TILE_CACHE_COLL_SIZE displacement still
        ; lands on the correct plane B row. Same wrap-split as the nametable
        ; loop: the <=8-row run crosses the plane-A row-29->0 boundary at most
        ; once — <=2 straight copies, no per-row wrap branch.
        tst.w   d3
        beq.s   .done_coll
        move.w  #TILE_CACHE_COLL_ROWS, d5
        sub.w   d2, d5                         ; d5 = collision rows until the dest wraps
        cmp.w   d3, d5
        bge.s   .coll_one_run
        subq.w  #1, d5
.coll_run1:
        move.b  (a0), (a2)                                       ; plane A
        move.b  BLOCK_COLL_PLANE_SIZE(a0), TILE_CACHE_COLL_SIZE(a2) ; plane B
        lea     BLOCK_TILE_SIZE(a0), a0        ; next collision row in block (16 bytes)
        lea     TILE_CACHE_STRIDE(a2), a2      ; next collision row in cache (80 bytes)
        dbf     d5, .coll_run1
        suba.w  #TILE_CACHE_COLL_SIZE, a2      ; wrap plane A row 29 -> 0, keeping cache_col
        move.w  d3, d5
        add.w   d2, d5
        subi.w  #TILE_CACHE_COLL_ROWS, d5      ; d5 = rows after the wrap
        bra.s   .coll_run2
.coll_one_run:
        move.w  d3, d5
.coll_run2:
        subq.w  #1, d5
.coll_run2_loop:
        move.b  (a0), (a2)                                       ; plane A
        move.b  BLOCK_COLL_PLANE_SIZE(a0), TILE_CACHE_COLL_SIZE(a2) ; plane B
        lea     BLOCK_TILE_SIZE(a0), a0
        lea     TILE_CACHE_STRIDE(a2), a2
        dbf     d5, .coll_run2_loop
.done_coll:
        rts

; -----------------------------------------------
; Tile_Cache_Init — populate cache for initial viewport + margins
; Called at level init (display off).
; In:  none (reads Camera_X, Camera_Y, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Tile_Cache_Init:
        ; compute world tile bounds for initial fill
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera world tile col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .left_ok
        moveq   #0, d0
.left_ok:
        move.w  d0, (Cache_Left_Col).w
        addi.w  #TILE_CACHE_COLS-1, d0
        move.w  d0, (Cache_Head_Col).w
        clr.w   (Cache_Origin_Col).w
        clr.w   (Cache_Origin_Row).w
        move.w  #$FFFF, (Cache_Fill_Last_Frame).w
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w
        move.w  #$FFFF, (Cache_Fill_RowResume_Row).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera world tile row
        move.w  d0, (Cache_Prev_Cam_Row).w     ; init vertical prefetch baseline
        ; init horizontal prefetch baseline (else the first H-motion frame sees a
        ; huge spurious delta off Cache_Prev_Cam_X=0 and mis-latches the direction)
        move.l  (Camera_X).w, d1
        swap    d1
        move.w  d1, (Cache_Prev_Cam_X).w
        clr.w   (Cache_H_Pfx_Dir).w
        clr.w   (Cache_H_Pfx_Accum).w
        clr.w   (Cache_Pfx_Skip_Armed).w
        clr.w   (Cache_Pfx_Lag_Flag).w         ; trailing-lag gate baseline (no false skip on frame 1)
        subi.w  #TILE_CACHE_MARGIN_V, d0
        bpl.s   .top_ok
        moveq   #0, d0
.top_ok:
        andi.w  #$FFFE, d0                     ; keep Cache_Top_Row even (collision cell alignment)
        move.w  d0, (Cache_Top_Row).w
        addi.w  #TILE_CACHE_ROWS-1, d0
        move.w  d0, (Cache_Bottom_Row).w

        bsr.w   TileCache_InvalidateStaging

        bsr.s   TileCache_FillAll
        bsr.w   TileCache_WarmupBelowRow       ; (ii) cold-start: pre-stage the below-row
        rts

; -----------------------------------------------
; TileCache_FillAll — fill entire cache from block data
; Called at init and after full reinit.
; In:  none (reads Cache_Left_Col/Head_Col/Top_Row/Bottom_Row)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillAll:
        ; H6: hoist the CopyBlockColumn base leas — a5/a6 survive DecompressBlock,
        ; loop-invariant for the whole fill (mirrors FillColumn's hoist).
        lea     (Tile_Cache_Nametable).l, a5
        lea     (Tile_Cache_Collision).l, a6
        ; zero the cache first
        lea     (Tile_Cache_Nametable).l, a0
        move.w  #(TILE_CACHE_NT_SIZE/4)-1, d0
.zero_nt:
        clr.l   (a0)+
        dbf     d0, .zero_nt

        lea     (Tile_Cache_Collision).l, a0
        move.w  #(TILE_CACHE_COLL_SIZE*TILE_CACHE_COLL_PLANES/4)-1, d0
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
; TileCache_WarmupBelowRow — Wave-2 (ii) cold-start warmup
; Pre-stages the ENTIRE block-row just below the initial cache window so the
; FIRST downward crossing is warm — before (i)'s leftover-budget prefetch has
; had any quiet frames to work. Targets the cold-start regime (i) structurally
; can't cover (the first crossing has no prior quiet frames). Called once from
; Tile_Cache_Init after FillAll, display OFF: the ~5-6 extra synchronous
; decompresses ride Init's existing ~10-frame cost, no lag concern. Down-scroll
; assumption (the common level-entry direction); an up-scroll from spawn simply
; doesn't benefit — no correctness cost either way (staging is a decompress
; cache; unused pre-staged blocks evict harmlessly as scroll proceeds).
; Init-only by design: Reinit is mid-play recovery where the scroll direction
; is unknown, so the down assumption doesn't hold there.
; In:  none (reads Cache_Bottom_Row/Left_Col/Head_Col, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a4 (DecompressBlock's set + scan temps; a5/a6 preserved)
; -----------------------------------------------
TileCache_WarmupBelowRow:
        ; target = first world tile row of the block-row below cache bottom
        ; (mirrors the prefetch down-branch: align bottom to block start + one block)
        move.w  (Cache_Bottom_Row).w, d7
        andi.w  #~(BLOCK_TILE_SIZE-1), d7      ; align down to block start
        addi.w  #BLOCK_TILE_SIZE, d7           ; first row of the block below
        ; guard: sec_y = d7 >> 8 must be < grid_h (else below the world — nothing to warm)
        move.w  d7, d5
        lsr.w   #8, d5                         ; sec_y
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.b  Act_grid_h+1(a0), d0           ; grid_h (sections)
        cmp.w   d0, d5
        bcc.s   .done                          ; sec_y >= grid_h — below the world, skip

        ; scan block cols [Left..Head], stage EVERY unstaged block (no k=1 cap,
        ; no budget — display off). d6 = col cursor, d7 = target row; both are
        ; preserved regs, so DecompressBlock (clobbers d0-d7) needs them saved.
        move.w  (Cache_Left_Col).w, d6
        andi.w  #$FFF0, d6                     ; align to the first block col
.warm_scan:
        cmp.w   (Cache_Head_Col).w, d6
        bgt.s   .done                          ; whole below-row scanned
        ; decompose (col d6, row d7) -> sec_x=d0, sec_y=d1, block_index=d2
        move.w  d6, d0
        lsr.w   #8, d0                         ; sec_x = tile_col >> 8
        move.w  d7, d1
        lsr.w   #8, d1                         ; sec_y = tile_row >> 8
        move.w  d6, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x = (tile_col >> 4) & 15
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y = (tile_row >> 4) & 15
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; block_index = block_y*16 + block_x
        ; grid guard: sec_x < grid_w (cols past the act right edge decompress blank)
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d3
        move.b  Act_grid_w+1(a0), d3           ; grid_w (sections)
        cmp.w   d3, d0
        bcc.s   .warm_next                     ; sec_x >= grid_w — past world, skip col
        bsr.w   TileCache_FindStagedBlock      ; Z set on hit; d0-d2 preserved
        beq.s   .warm_next                     ; already staged — next col
        movem.l d6-d7, -(sp)                   ; DecompressBlock clobbers d0-d7
        bsr.w   TileCache_DecompressBlock      ; stage this block (d0/d1/d2 in)
        movem.l (sp)+, d6-d7
.warm_next:
        addi.w  #BLOCK_TILE_SIZE, d6           ; next block col
        bra.s   .warm_scan
.done:
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
        ; trailing-lag detect (consumed by the H4 gate below): Frame_Counter ticks once
        ; per VBlank on BOTH the normal (VInt_Level) and lag (VInt_Lag) paths, so it
        ; advancing by MORE than 1 since the last fill means a frame lagged in between.
        move.w  d0, d1
        sub.w   (Cache_Fill_Last_Frame).w, d1  ; frames since last fill
        subq.w  #1, d1                          ; 0 = on time, >0 = a frame lagged
        beq.s   .fg_on_time
        move.w  #1, (Cache_Pfx_Lag_Flag).w
        bra.s   .fg_lag_done
.fg_on_time:
        clr.w   (Cache_Pfx_Lag_Flag).w
.fg_lag_done:
        move.w  d0, (Cache_Fill_Last_Frame).w

        ; --- reset per-frame decompress budget + rows-this-frame cap ---
        ;     BEFORE the preambles: the column-partial bypass path jumps
        ;     straight to .v_section, which must see a fresh rows cap.
        move.w  #BLOCK_DECOMP_BUDGET, (Cache_Fill_Budget).w
        move.w  #VFILL_ROWS_PER_FRAME, (Cache_Fill_Rows_Left).w

        ; --- finish any pending partial ROW first (before the column
        ;     preamble's bypass can reach the v-loops): there is exactly
        ;     one row-resume slot, and the v-loops overwrite or clear it —
        ;     a still-occupied slot there orphans a half-filled row with
        ;     stale tiles AND stale collision (merge review C2a). ---
        move.w  (Cache_Fill_RowResume_Row).w, d5
        cmpi.w  #$FFFF, d5
        beq.s   .no_row_pending
        cmp.w   (Cache_Top_Row).w, d5
        blt.s   .row_pending_stale
        cmp.w   (Cache_Bottom_Row).w, d5
        bgt.s   .row_pending_stale
        move.w  d5, -(sp)                      ; FillRow clobbers d5
        bsr.w   TileCache_FillRow
        move.w  (sp)+, d5
        tst.w   d0
        bne.w   .fill_return                   ; budget out again — done this frame
        ; If the completed row IS the cache top, it was the first half of an
        ; up-fill pair whose budget-out orphaned the second half — fill it
        ; too (Top is always even; no other partial stores a row equal to
        ; Top; refilling a filled row is idempotent). Merge review C1.
        cmp.w   (Cache_Top_Row).w, d5
        bne.s   .no_row_pending
        addq.w  #1, d5
        cmp.w   (Cache_Bottom_Row).w, d5
        bgt.s   .no_row_pending
        bsr.w   TileCache_FillRow
        tst.w   d0
        bne.w   .fill_return
        bra.s   .no_row_pending
.row_pending_stale:
        move.w  #$FFFF, (Cache_Fill_RowResume_Row).w
.no_row_pending:

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
        move.w  d6, d0                         ; d0 = world tile col
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
        move.w  d6, d0                         ; d0 = world tile col
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
        bra.s   .v_section
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
        move.w  d6, d0                         ; d0 = world tile row
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
        move.w  d6, d0                         ; d0 = world tile row
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
        ; rows cap: (Cache_Fill_Rows_Left) counts down; stop when 0.
        ; commit Cache_Bottom_Row BEFORE fill so the resume preamble can
        ; safely resume a partial row using the committed tracker.
        move.w  (Cache_Bottom_Row).w, d5
        cmp.w   d7, d5
        bge.s   .v_bottom_done

.v_bottom_fill:
        tst.w   (Cache_Fill_Rows_Left).w       ; rows cap exhausted?
        beq.s   .v_bottom_done

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

        ; commit BEFORE fill (resume is keyed by row)
        move.w  d5, (Cache_Bottom_Row).w

        movem.l d5/d7, -(sp)
        bsr.w   TileCache_FillRow
        movem.l (sp)+, d5/d7

        tst.w   d0
        bne.s   .v_bottom_done                 ; partial — resume preamble finishes next frame
        subq.w  #1, (Cache_Fill_Rows_Left).w
        bra.s   .v_bottom_fill
.v_bottom_done:

        ; --- fill upward rows in pairs (evict 2 from bottom as needed) ---
        ; Only start a pair if rows_left >= 2 AND budget > 0.
        ; Cache_Top_Row is committed BEFORE fill (per existing precedent at .v_no_evict_up).
        ; On partial in either half of the pair, exit — resume preamble finishes next frame.
        move.w  (sp)+, d4                      ; d4 = desired_top (even)
        move.w  (Cache_Top_Row).w, d5
.v_top_fill:
        cmp.w   d4, d5
        ble.s   .v_top_done
        ; need 2 rows remaining to start a pair
        cmpi.w  #2, (Cache_Fill_Rows_Left).w
        blt.s   .v_top_done
        ; a bottom-fill partial leaves budget 0 — starting a pair here would
        ; clobber its resume slot and orphan the half-filled row (review C2b)
        tst.w   (Cache_Fill_Budget).w
        beq.s   .v_top_done

        subq.w  #2, d5                         ; 2-row step keeps Top even

        ; evict 2 rows from bottom if cache would exceed capacity
        move.w  (Cache_Bottom_Row).w, d0
        sub.w   d5, d0
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .v_no_evict_up
        moveq   #2, d0
        bsr.w   TileCache_VSlideUp             ; O(1) origin retreat — clobbers d0-d1 only
.v_no_evict_up:

        ; commit Cache_Top_Row BEFORE fills (resume keyed by row)
        move.w  d5, (Cache_Top_Row).w

        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillRow              ; new top row (d5)
        movem.l (sp)+, d4-d5
        tst.w   d0
        bne.s   .v_top_done                    ; partial — exit; resume finishes next frame
        subq.w  #1, (Cache_Fill_Rows_Left).w

        addq.w  #1, d5
        movem.l d4-d5, -(sp)
        bsr.w   TileCache_FillRow              ; second row of the pair (d5+1)
        movem.l (sp)+, d4-d5
        tst.w   d0
        bne.s   .v_top_done                    ; partial — exit; resume finishes next frame
        subq.w  #1, (Cache_Fill_Rows_Left).w
        subq.w  #1, d5                         ; restore d5 to even (pair base)
        bra.s   .v_top_fill
.v_top_done:
        ; ============ UNIFIED DIRECTION-AWARE PREFETCH (§4.7, design note) ============
        ; Leftover-budget speculation ordered row -> col -> corner. H4 deadline gate
        ; first: pure speculation must never push a late frame past VBlank. The demand
        ; fill above already ran and is NEVER gated.
        ; H4 (trailing-lag gate): Tile_Cache_Fill runs once/frame inside VBlank (V~=240,
        ; the same slot every frame), so a beam-position read cannot gauge frame load.
        ; Use the previous frame's outcome instead: Cache_Pfx_Lag_Flag was set at the
        ; frame gate above from the Frame_Counter delta (release-safe, unlike the DEBUG
        ; Lag_Frame_Count). If the frame just before this one lagged, skip this frame's
        ; speculation — but NEVER skip two running: a sustained-lag run must keep pre-
        ; warming or cold columns cascade back in (demand fill is never gated, so the
        ; bounded worst case is the pre-prefetch path).
        tst.w   (Cache_Pfx_Lag_Flag).w         ; did the previous frame lag?
        beq.s   .pfx_no_recent_lag
        tst.w   (Cache_Pfx_Skip_Armed).w
        bne.s   .pfx_gate_ok                   ; already skipped once -> run anyway (no cascade)
        move.w  #1, (Cache_Pfx_Skip_Armed).w   ; arm: skip this frame's speculation
        bra.w   .fill_return
.pfx_no_recent_lag:
        clr.w   (Cache_Pfx_Skip_Armed).w
.pfx_gate_ok:
        tst.w   (Cache_Fill_Budget).w
        beq.w   .fill_return                   ; demand fill spent the budget — no prefetch
        ; corner (H2) inputs: each axis scan records its target; $FFFF = axis inactive
        move.w  #$FFFF, (Cache_Pfx_Row_Target).w
        move.w  #$FFFF, (Cache_Pfx_Col_Target).w

        ; ---- ROW SCAN (vertical prefetch; NO hysteresis — gravity is decisive) ----
        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                         ; d0 = camera world tile row
        move.w  (Cache_Prev_Cam_Row).w, d1
        move.w  d0, (Cache_Prev_Cam_Row).w     ; update for next frame. If a frame is
                                               ; H4-gate-skipped or budget-0 this (and the
                                               ; Cache_Prev_Cam_X update below) don't run,
                                               ; so the next tail-run sees a DOUBLED delta —
                                               ; harmless: V uses the sign only, H nets px.
        sub.w   d1, d0                         ; d0 = delta (+down / -up / 0)
        beq.w   .row_done                      ; not moving vertically — no row target
        bmi.s   .pfx_up

        ; moving DOWN: target = block-row just below cache bottom
        move.w  (Cache_Bottom_Row).w, d7
        andi.w  #~(BLOCK_TILE_SIZE-1), d7      ; align down to block start
        addi.w  #BLOCK_TILE_SIZE, d7           ; first row of next block below
        move.w  d7, d5
        lsr.w   #8, d5                         ; sec_y
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.b  Act_grid_h+1(a0), d0           ; grid_h (sections)
        cmp.w   d0, d5
        bcc.s   .row_done                      ; sec_y >= grid_h — out of world
        bra.s   .pfx_go

.pfx_up:
        ; moving UP: target = block-row just above cache top
        move.w  (Cache_Top_Row).w, d7
        andi.w  #~(BLOCK_TILE_SIZE-1), d7      ; align down to block start (Top is even)
        tst.w   d7
        beq.s   .row_done                      ; top block-row IS world row 0 — nothing above
        subi.w  #BLOCK_TILE_SIZE, d7           ; first row of block above

.pfx_go:
        ; d7 = target world tile row. Scan block cols [Left..Head], stage the FIRST
        ; unstaged block k=1 (self-advancing across the ~8 quiet frames), sec_x per
        ; step, sec_y fixed (guarded at entry).
        move.w  d7, (Cache_Pfx_Row_Target).w   ; record for the corner (H2)
        move.w  (Cache_Left_Col).w, d6
        andi.w  #$FFF0, d6                     ; align to the first block col
.pfx_scan:
        cmp.w   (Cache_Head_Col).w, d6
        bgt.s   .row_done                      ; whole next row already staged
        ; decompose (col d6, row d7) -> sec_x=d0, sec_y=d1, block_index=d2
        move.w  d6, d0
        lsr.w   #8, d0                         ; sec_x = tile_col >> 8
        move.w  d7, d1
        lsr.w   #8, d1                         ; sec_y = tile_row >> 8
        move.w  d6, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2                        ; block_x = (tile_col >> 4) & 15
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3                        ; block_y = (tile_row >> 4) & 15
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; block_index = block_y*16 + block_x
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d3
        move.b  Act_grid_w+1(a0), d3
        cmp.w   d3, d0
        bcc.s   .pfx_next                      ; sec_x >= grid_w — out of world, skip col
        bsr.w   TileCache_FindStagedBlock      ; Z set on hit; d0-d2 preserved; clobbers d3-d4,a1
        beq.s   .pfx_next                      ; already staged — try next col
        subq.w  #1, (Cache_Fill_Budget).w
        bsr.w   TileCache_DecompressBlock      ; stage this block (d0/d1/d2 in) — k=1, then done
        bra.s   .row_done
.pfx_next:
        addi.w  #BLOCK_TILE_SIZE, d6           ; next block col
        bra.s   .pfx_scan

.row_done:
        ; ---- COL SCAN (horizontal prefetch; H3 direction hysteresis) ----
        ; Update the latch EVERY tail-run frame (accuracy), THEN gate the scan on
        ; budget. Camera px delta -> direction; the latch flips only after
        ; >= H_PFX_HYST px of NET opposite motion (players dither on column seams).
        move.l  (Camera_X).w, d0
        swap    d0                             ; d0.w = camera px (low word)
        move.w  (Cache_Prev_Cam_X).w, d1
        move.w  d0, (Cache_Prev_Cam_X).w       ; update for next frame
        sub.w   d1, d0                         ; d0 = delta px (+right / -left / 0)
        move.w  (Cache_H_Pfx_Dir).w, d3
        bne.s   .cs_have_latch
        ; no latch yet: establish from this frame's motion sign
        tst.w   d0
        beq.w   .fill_return                   ; never moved horizontally — no col, no corner
        bmi.s   .cs_first_left
        moveq   #1, d3
        bra.s   .cs_first_set
.cs_first_left:
        moveq   #-1, d3
.cs_first_set:
        move.w  d3, (Cache_H_Pfx_Dir).w
        clr.w   (Cache_H_Pfx_Accum).w
        bra.s   .cs_latched
.cs_have_latch:
        ; opp = motion opposite the latch; accumulate (clamp >=0); flip at threshold
        move.w  d0, d1                         ; d1 = delta px
        tst.w   d3
        bmi.s   .cs_opp_ready                  ; latch LEFT: opposite = +delta (keep sign)
        neg.w   d1                             ; latch RIGHT: opposite = -delta
.cs_opp_ready:
        add.w   d1, (Cache_H_Pfx_Accum).w
        tst.w   (Cache_H_Pfx_Accum).w
        bpl.s   .cs_accum_ok
        clr.w   (Cache_H_Pfx_Accum).w          ; net: with-latch motion cannot bank below 0
.cs_accum_ok:
        cmpi.w  #H_PFX_HYST, (Cache_H_Pfx_Accum).w
        blt.s   .cs_latched                    ; not enough opposite motion — keep latch
        neg.w   d3                             ; flip the latched direction
        move.w  d3, (Cache_H_Pfx_Dir).w
        clr.w   (Cache_H_Pfx_Accum).w
.cs_latched:
        ; d3 = latched direction (+1 right / -1 left). NOTE: the col scan runs whenever a
        ; direction is latched — INCLUDING purely-vertical frames (no H motion this frame)
        ; — so it keeps pre-warming the latched-side column. Probe-only cost when that
        ; column is already staged (FindStagedBlock hits, no decompress); intentional.
        tst.w   (Cache_Fill_Budget).w
        beq.w   .fill_return                   ; row scan spent the budget — no col this frame
        tst.w   d3
        bmi.s   .cs_left
        ; RIGHT: target = block-col just beyond cache head
        move.w  (Cache_Head_Col).w, d6
        andi.w  #~(BLOCK_TILE_SIZE-1), d6
        addi.w  #BLOCK_TILE_SIZE, d6
        bra.s   .cs_have_col
.cs_left:
        ; LEFT: target = block-col just before cache left
        move.w  (Cache_Left_Col).w, d6
        andi.w  #~(BLOCK_TILE_SIZE-1), d6
        beq.s   .col_done                      ; left block-col IS world col 0 — nothing left
        subi.w  #BLOCK_TILE_SIZE, d6
.cs_have_col:
        ; guard sec_x = d6 >> 8 < grid_w (FIXED for the whole col scan)
        move.w  d6, d5
        lsr.w   #8, d5                         ; sec_x
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d0
        move.b  Act_grid_w+1(a0), d0           ; grid_w (sections)
        cmp.w   d0, d5
        bcc.s   .col_done                      ; sec_x >= grid_w — out of world
        move.w  d6, (Cache_Pfx_Col_Target).w   ; record for the corner (H2)
        ; scan block rows [Top..Bottom]; sec_y per step (d6 fixed for the scan)
        move.w  (Cache_Top_Row).w, d7
        andi.w  #$FFF0, d7                     ; align to the first block row
.cs_scan:
        cmp.w   (Cache_Bottom_Row).w, d7
        bgt.s   .col_done                      ; whole next col already staged
        move.w  d7, d5
        lsr.w   #8, d5                         ; sec_y
        movea.l (Current_Act_Ptr).w, a0
        moveq   #0, d3
        move.b  Act_grid_h+1(a0), d3
        cmp.w   d3, d5
        bcc.s   .cs_next                       ; sec_y >= grid_h — skip this block row
        ; decompose (col d6, row d7) -> sec_x=d0, sec_y=d1, block_index=d2
        move.w  d6, d0
        lsr.w   #8, d0
        move.w  d7, d1
        lsr.w   #8, d1
        move.w  d6, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; block_index = block_y*16 + block_x
        bsr.w   TileCache_FindStagedBlock
        beq.s   .cs_next                       ; already staged — try next row
        subq.w  #1, (Cache_Fill_Budget).w
        bsr.w   TileCache_DecompressBlock      ; stage this block — k=1, then done
        bra.s   .col_done
.cs_next:
        addi.w  #BLOCK_TILE_SIZE, d7           ; next block row
        bra.s   .cs_scan

.col_done:
        ; ---- CORNER (H2): the (next-row x next-col) block is in NEITHER axis scan;
        ; stage it LAST, only when BOTH axes are actively crossing. Both targets were
        ; grid-guarded when recorded, so the corner section is in-grid by construction
        ; (sec_x<grid_w from the col, sec_y<grid_h from the row).
        tst.w   (Cache_Fill_Budget).w
        beq.s   .fill_return
        move.w  (Cache_Pfx_Row_Target).w, d7
        cmpi.w  #$FFFF, d7
        beq.s   .fill_return                   ; no vertical target — no corner
        move.w  (Cache_Pfx_Col_Target).w, d6
        cmpi.w  #$FFFF, d6
        beq.s   .fill_return                   ; no horizontal target — no corner
        ; decompose (col d6, row d7) -> sec_x=d0, sec_y=d1, block_index=d2
        move.w  d6, d0
        lsr.w   #8, d0
        move.w  d7, d1
        lsr.w   #8, d1
        move.w  d6, d2
        lsr.w   #BLOCK_TILE_SHIFT, d2
        andi.w  #$F, d2
        move.w  d7, d3
        lsr.w   #BLOCK_TILE_SHIFT, d3
        andi.w  #$F, d3
        lsl.w   #4, d3
        add.w   d2, d3
        move.w  d3, d2                         ; block_index = block_y*16 + block_x
        bsr.w   TileCache_FindStagedBlock
        beq.s   .fill_return                   ; already staged
        subq.w  #1, (Cache_Fill_Budget).w
        bsr.w   TileCache_DecompressBlock      ; stage the corner — k=1
.fill_return:
        rts

; -----------------------------------------------
; TileCache_FillColumn — fill one world column into cache (budget-limited)
; In:  d5.w = world tile col (must already be within cache bounds)
; Out: d0.w = 0 if column complete, nonzero if partial.
;      On partial, resume state (Cache_Fill_Resume_Col/Row) is stored;
;      Tile_Cache_Fill finishes it first next frame.
; Uses Cache_Fill_Budget — shared per-frame decompress allowance.
; In (H6): a5/a6 set at entry to the NT/collision bases (hoisted CopyBlockColumn leas).
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_FillColumn:
        ; H6: hoist the two loop-invariant base leas out of CopyBlockColumn — a5/a6
        ; are the only regs surviving DecompressBlock's clobber license (d0-d7/a0/a2-a4),
        ; so they carry the bases across the per-block decompress for the whole column.
        lea     (Tile_Cache_Nametable).l, a5
        lea     (Tile_Cache_Collision).l, a6
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

        movem.l d5, -(sp)              ; CopyBlockColumn clobbers d5 (saved); it preserves d7
        bsr.w   TileCache_CopyBlockColumn
        movem.l (sp)+, d5

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
; Out: d0.w = 0 complete / 1 budget-out (resume state stored in
;             Cache_Fill_RowResume_Row/Col).
;      On complete, Cache_Fill_RowResume_Row is set to $FFFF.
; Clobbers: d0-d7, a0-a6
;   a5/a6 hold the collision plane-A/plane-B DEST row bases for the WHOLE row
;   (step-5 hoist). They survive the per-block DecompressBlock call — its license
;   (d0-d7/a0/a2-a4) EXCLUDES a5/a6; a4 (NT dest base) + a2 (plane-B src base) ARE
;   clobbered by it, so re-set per block. (widened from a0-a4; sole caller
;   Tile_Cache_Fill already licenses a0-a6.)
; Note: collision is copied only on the odd row of each 16px cell (the row
;       that completes the cell). Cache_Top_Row is kept even, so cell
;       boundaries align with world block data.
; -----------------------------------------------
TileCache_FillRow:
        ; cache row offset (constant for all columns)
        move.w  d5, d2
        sub.w   (Cache_Top_Row).w, d2
        bmi.w   .fr_early_out

        ; remember logical row for the cell-parity test, then map to
        ; physical row via the circular origin (origin even → parity
        ; is preserved, but offsets must come from the physical row)
        move.w  d2, d4                         ; d4 = logical row
        add.w   (Cache_Origin_Row).w, d2
        cmpi.w  #TILE_CACHE_ROWS, d2
        blt.s   .fr_row_nowrap
        subi.w  #TILE_CACHE_ROWS, d2
.fr_row_nowrap:

        ; collision dest row offset (bytes); $FFFF = even row, skip collision
        move.w  #$FFFF, d3
        btst    #0, d4
        beq.s   .fr_no_coll
        move.w  d2, d3
        lsr.w   #1, d3                         ; physical collision row
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

        ; --- step-5 hoist: collision plane-A/B DEST row bases are loop-invariant;
        ;     hoist ONCE per row into a5/a6. LOAD-BEARING & INVISIBLE: relies on
        ;     a5/a6 surviving the per-block DecompressBlock call — its license
        ;     (d0-d7/a0/a2-a4) excludes them (S4LZ_DecompressDict verified a5/a6-
        ;     clean too). An edit making DecompressBlock touch a5/a6 corrupts the
        ;     collision planes SILENTLY (S2-D6 checked-clobbers lint would catch). ---
        lea     (Tile_Cache_Collision).l, a5           ; plane-A dest base (whole row)
        lea     (Tile_Cache_Collision+TILE_CACHE_COLL_SIZE).l, a6  ; plane-B dest base (whole row)

        ; resume: if this is the partially-filled row from last frame,
        ; restart the column walk from where we left off (not Cache_Left_Col).
        ; Clamp to Left_Col in case columns were evicted since the partial.
        move.w  (Cache_Left_Col).w, d7
        cmp.w   (Cache_Fill_RowResume_Row).w, d5
        bne.s   .fr_from_left
        move.w  (Cache_Fill_RowResume_Col).w, d7
        cmp.w   (Cache_Left_Col).w, d7        ; resume col < Left → evicted, use Left
        bge.s   .fr_from_left
        move.w  (Cache_Left_Col).w, d7
.fr_from_left:
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
        ; need decompress — check shared frame budget
        tst.w   (Cache_Fill_Budget).w
        beq.w   .fr_budget_out
        subq.w  #1, (Cache_Fill_Budget).w
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
        ; collision row base = (intra_row/2) * BLOCK_COLL_COLS via the parity-safe
        ; macro. FillRow copies collision only on the ODD (cell-completing) row,
        ; so the even-only intra_row*8 shortcut would land 64px off — the §5
        ; loop-arc wall bug (arc toe cells read as full-solid $01 → ground wall
        ; probe killed gsp). collSrcRowBase makes that misencoding impossible.
        collSrcRowBase d3                      ; (intra_row/2) * BLOCK_COLL_COLS
        lea     BLOCK_NT_SIZE(a1), a3
        adda.w  d3, a3

        ; step-5 hoist: a4 = NT DEST base, a2 = plane-B SRC base (a3 + 128). Both
        ; per-BLOCK — DecompressBlock clobbers a4 + a2, so they re-set here (a5/a6
        ; survive it, hoisted per-row above). Plane-B src can't be an indexed
        ; displacement: BLOCK_COLL_PLANE_SIZE = 128 > +127 (signed 8-bit).
        lea     (Tile_Cache_Nametable).l, a4
        lea     BLOCK_COLL_PLANE_SIZE(a3), a2

        ; === valid intra-block column run [ic_lo, ic_hi) ===
        ; The per-tile loop this replaced wrote a column iff it passed three
        ; monotone gates: world_col <= Head (else the block loop TERMINATES),
        ; world_col >= Left, and cache_col < COLS (the latter two SKIP the cell).
        ; world_col rises with the intra-col, so the surviving columns form one
        ; contiguous run — the prefix below Left and the suffix past Head/COLS are
        ; clamped off (never written, never zero-filled; FillRow always skipped
        ; out-of-range cells rather than zeroing them, so the clamp is inherent).
        ;   ic_lo = max(intra_start, Left - B)
        ;   ic_hi = min(BLOCK_TILE_SIZE, Head - B + 1, Left + COLS - B)   (B = block base)
        move.w  d7, d2
        andi.w  #$FFF0, d2                    ; d2 = block base B
        move.w  d7, d3
        andi.w  #$F, d3                       ; ic_lo = intra_start
        move.w  (Cache_Left_Col).w, d0
        sub.w   d2, d0                         ; Left - B
        cmp.w   d3, d0
        ble.s   .fr_iclo_done
        move.w  d0, d3                         ; ic_lo = Left - B
.fr_iclo_done:
        moveq   #BLOCK_TILE_SIZE, d4
        move.w  (Cache_Head_Col).w, d0
        sub.w   d2, d0
        addq.w  #1, d0                         ; Head - B + 1
        cmp.w   d4, d0
        bge.s   .fr_ichi_head
        move.w  d0, d4
.fr_ichi_head:
        move.w  (Cache_Left_Col).w, d0
        sub.w   d2, d0
        addi.w  #TILE_CACHE_COLS, d0           ; Left + COLS - B
        cmp.w   d4, d0
        bge.s   .fr_ichi_done
        move.w  d0, d4                         ; ic_hi = Left + COLS - B
.fr_ichi_done:
        cmp.w   d4, d3
        bge.s   .fr_nt_empty                  ; ic_lo >= ic_hi: nothing to copy

        ; === phase 1: nametable segment copy ===
        ; src words are contiguous (staging slot, intra_col * 2); dest columns are
        ; contiguous in the circular cache and wrap at most once at Origin_Col, so
        ; the run splits into <=2 straight move.w copies. d2=B still; d3=ic_lo,
        ; d4=ic_hi. a0 = NT staging row base (consumed here — DecompressBlock resets
        ; it per block, and phase 2 reads collision via a3/a2, not a0).
        move.w  d3, d0
        add.w   d0, d0
        adda.w  d0, a0                         ; a0 -> staging src at ic_lo
        move.w  d4, d1
        sub.w   d3, d1                         ; d1 = n_total (> 0)
        add.w   d3, d2
        sub.w   (Cache_Left_Col).w, d2        ; cache_col_lo (0..COLS-1)
        add.w   (Cache_Origin_Col).w, d2      ; phys_start (0..2*COLS-2)
        move.w  (sp), d4                       ; d4 = cache_row_offset_words
        cmpi.w  #TILE_CACHE_COLS, d2
        blt.s   .fr_nt_ncalc
        subi.w  #TILE_CACHE_COLS, d2           ; starts already wrapped: one run
        move.w  d1, d0                         ; n1 = n_total
        bra.s   .fr_nt_emit
.fr_nt_ncalc:
        move.w  #TILE_CACHE_COLS, d0
        sub.w   d2, d0                         ; cols_before_wrap = COLS - phys_start (>=1)
        cmp.w   d1, d0
        blt.s   .fr_nt_emit                   ; n1 = cols_before_wrap (< n_total)
        move.w  d1, d0                         ; n1 = n_total (whole run fits pre-wrap)
.fr_nt_emit:
        move.w  d1, d3
        sub.w   d0, d3                         ; d3 = n2 = n_total - n1
        move.w  d4, d1
        add.w   d2, d1
        add.w   d1, d1                         ; (row_off + phys_start) * 2
        lea     (a4, d1.w), a1                 ; run-1 dest
        subq.w  #1, d0
.fr_nt_run1:
        move.w  (a0)+, (a1)+
        dbf     d0, .fr_nt_run1
        tst.w   d3
        beq.s   .fr_nt_empty
        move.w  d4, d1
        add.w   d1, d1                         ; wrap dest starts at phys 0
        lea     (a4, d1.w), a1                 ; run-2 dest
        subq.w  #1, d3
.fr_nt_run2:
        move.w  (a0)+, (a1)+
        dbf     d3, .fr_nt_run2

.fr_nt_empty:
        ; === phase 2: collision planes A and B (cell-completing rows only) ===
        ; Segmented mirror of phase 1: the collision byte-copy walks the SAME valid run
        ; [ic_lo, ic_hi) with the SAME Origin_Col wrap-split as the nametable — RE-derived
        ; here, independent of phase 1, so the nametable half stays byte-for-byte as 1.1a
        ; and a fault in this block can only touch collision. Runs only on the ODD (cell-
        ; completing) row (2(sp) = $FFFF gates the whole phase — constant per row). Dest
        ; byte index = coll_row_offset + physical col; src byte = (plane base, intra_col),
        ; contiguous. a5/a6 = plane A/B DEST bases (per-row); a3/a2 = plane A/B SRC bases
        ; (per-block); a1/a4 = the run dest pointers (a4 = NT base, dead after phase 1).
        ; (move.b runs; move.w/move.l byte-pairing is the ledgered step-5 rider.)
        move.w  2(sp), d0
        cmpi.w  #$FFFF, d0
        beq.w   .fr_next_block                ; even row: no collision this row

        ; re-derive the valid run [ic_lo=d3, ic_hi=d4); d2 = block base B
        move.w  d7, d2
        andi.w  #$FFF0, d2
        move.w  d7, d3
        andi.w  #$F, d3                        ; ic_lo = intra_start
        move.w  (Cache_Left_Col).w, d0
        sub.w   d2, d0                         ; Left - B
        cmp.w   d3, d0
        ble.s   .fr_ci_iclo
        move.w  d0, d3                         ; ic_lo = Left - B
.fr_ci_iclo:
        moveq   #BLOCK_TILE_SIZE, d4
        move.w  (Cache_Head_Col).w, d0
        sub.w   d2, d0
        addq.w  #1, d0                         ; Head - B + 1
        cmp.w   d4, d0
        bge.s   .fr_ci_head
        move.w  d0, d4
.fr_ci_head:
        move.w  (Cache_Left_Col).w, d0
        sub.w   d2, d0
        addi.w  #TILE_CACHE_COLS, d0           ; Left + COLS - B
        cmp.w   d4, d0
        bge.s   .fr_ci_ichi
        move.w  d0, d4                         ; ic_hi = Left + COLS - B
.fr_ci_ichi:
        cmp.w   d4, d3
        bge.s   .fr_next_block                ; empty run

        ; advance plane-A/B src to ic_lo (byte index); n_total -> d1; phys_start -> d2
        move.w  d3, d0
        adda.w  d0, a3
        adda.w  d0, a2
        move.w  d4, d1
        sub.w   d3, d1
        add.w   d3, d2
        sub.w   (Cache_Left_Col).w, d2
        add.w   (Cache_Origin_Col).w, d2      ; phys_start (0..2*COLS-2)
        cmpi.w  #TILE_CACHE_COLS, d2
        blt.s   .fr_ci_ncalc
        subi.w  #TILE_CACHE_COLS, d2           ; starts already wrapped: one run
        move.w  d1, d0                         ; n1 = n_total
        bra.s   .fr_ci_emit
.fr_ci_ncalc:
        move.w  #TILE_CACHE_COLS, d0
        sub.w   d2, d0                         ; cols_before_wrap = COLS - phys_start (>=1)
        cmp.w   d1, d0
        blt.s   .fr_ci_emit                   ; n1 = cols_before_wrap (< n_total)
        move.w  d1, d0                         ; n1 = n_total (whole run fits pre-wrap)
.fr_ci_emit:
        move.w  d1, d3
        sub.w   d0, d3                         ; d3 = n2 = n_total - n1
        move.w  2(sp), d4
        add.w   d2, d4                         ; coll_row_offset + phys_start
        lea     (a5, d4.w), a1                 ; run-1 plane A dest
        lea     (a6, d4.w), a4                 ; run-1 plane B dest
        subq.w  #1, d0
.fr_ci_run1:
        move.b  (a3)+, (a1)+                   ; plane A
        move.b  (a2)+, (a4)+                   ; plane B
        dbf     d0, .fr_ci_run1
        tst.w   d3
        beq.s   .fr_next_block
        move.w  2(sp), d4                      ; wrap dest starts at phys 0
        lea     (a5, d4.w), a1                 ; run-2 plane A dest
        lea     (a6, d4.w), a4                 ; run-2 plane B dest
        subq.w  #1, d3
.fr_ci_run2:
        move.b  (a3)+, (a1)+
        move.b  (a2)+, (a4)+
        dbf     d3, .fr_ci_run2

.fr_next_block:
        move.w  d7, d0
        andi.w  #$FFF0, d0
        addi.w  #BLOCK_TILE_SIZE, d0
        move.w  d0, d7
        bra.w   .fr_block_loop

.fr_budget_out:
        ; Budget exhausted mid-row. Store resume state and return partial.
        ; Two words are on the stack (pushed above): pop them before exit.
        addq.l  #4, sp
        move.w  d5, (Cache_Fill_RowResume_Row).w
        move.w  d7, (Cache_Fill_RowResume_Col).w
        moveq   #1, d0
        rts

.fr_done:
        addq.l  #4, sp                         ; pop row offsets
        move.w  #$FFFF, (Cache_Fill_RowResume_Row).w
        moveq   #0, d0
        rts
.fr_early_out:
        moveq   #0, d0
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
; TileCache_VSlide — evict stale top rows (circular, O(1))
; Advances Cache_Origin_Row instead of moving data — the recycled
; physical rows are overwritten by TileCache_FillRow before they can
; become visible (same validity contract the old memmove had).
; Replaces the ~87k-cycle memmove (9.4KB NT + 2.3KB collision per
; 2-row evict) that caused lag during sustained vertical scroll.
; In:  d0.w = tile rows to evict from top (even)
; Out: none
; Clobbers: d0
; -----------------------------------------------
TileCache_VSlide:
        tst.w   d0
        ble.s   .vslide_done
        add.w   d0, (Cache_Top_Row).w
        add.w   (Cache_Origin_Row).w, d0
        cmpi.w  #TILE_CACHE_ROWS, d0
        blt.s   .vslide_nowrap
        subi.w  #TILE_CACHE_ROWS, d0
.vslide_nowrap:
        move.w  d0, (Cache_Origin_Row).w
.vslide_done:
        rts

; -----------------------------------------------
; TileCache_VSlideUp — evict stale bottom rows (circular, O(1))
; Mirror of TileCache_VSlide: retreats Cache_Origin_Row so new top
; rows map onto the recycled bottom rows' physical storage.
; In:  d0.w = tile rows to evict from bottom (even)
; Out: none
; Clobbers: d0-d1
; -----------------------------------------------
TileCache_VSlideUp:
        tst.w   d0
        ble.s   .vsu_done
        sub.w   d0, (Cache_Bottom_Row).w
        move.w  (Cache_Origin_Row).w, d1
        sub.w   d0, d1
        bpl.s   .vsu_nowrap
        addi.w  #TILE_CACHE_ROWS, d1
.vsu_nowrap:
        move.w  d1, (Cache_Origin_Row).w
.vsu_done:
        rts

; -----------------------------------------------
; TileCache_Reinit — full cache re-center + refill (recovery path)
; Costs ~10 frames synchronously (full FillAll) — recovery only, never
; on a hot path. Currently no callers; retained as the documented
; recovery mechanism for future cache-miss / debug-warp handling.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TileCache_Reinit:
        ; recompute cache bounds centered on camera
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera world tile col
        subi.w  #TILE_CACHE_MARGIN_H, d0
        bpl.s   .ri_left_ok
        moveq   #0, d0
.ri_left_ok:
        move.w  d0, (Cache_Left_Col).w
        addi.w  #TILE_CACHE_COLS-1, d0
        move.w  d0, (Cache_Head_Col).w
        clr.w   (Cache_Origin_Col).w
        clr.w   (Cache_Origin_Row).w
        move.w  #$FFFF, (Cache_Fill_Resume_Col).w
        move.w  #$FFFF, (Cache_Fill_RowResume_Row).w

        move.l  (Camera_Y).w, d0
        swap    d0
        lsr.w   #3, d0                         ; camera world tile row
        move.w  d0, (Cache_Prev_Cam_Row).w     ; reset vertical prefetch baseline on reinit
        move.l  (Camera_X).w, d1
        swap    d1
        move.w  d1, (Cache_Prev_Cam_X).w       ; reset horizontal prefetch baseline
        clr.w   (Cache_H_Pfx_Dir).w
        clr.w   (Cache_H_Pfx_Accum).w
        clr.w   (Cache_Pfx_Skip_Armed).w
        clr.w   (Cache_Pfx_Lag_Flag).w         ; trailing-lag gate baseline
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
