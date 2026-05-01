; World-space strip cache (§4.7)
; Linear buffer in lower RAM ($FFFF0000), 120 strips physical capacity.
; Decompressed on-demand as camera scrolls; checkpoint seeking for backward.
; Batched memmove slide evicts stale left-side strips when buffer fills.

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
; Strip_Cache_GetColumn — get strip data pointer for a world tile col
; In:  d0.w = world tile col (must be within valid cache range)
; Out: a0   = pointer to 96-byte strip in cache
; Clobbers: d0-d1
; -----------------------------------------------
Strip_Cache_GetColumn:
        sub.w   (Strip_Cache_Left_Col).w, d0
        lsl.w   #STRIP_BYTE_SHIFT, d0
        lea     (Strip_Cache).l, a0
        adda.w  d0, a0
        rts

; -----------------------------------------------
; Strip_Cache_Init — populate cache for initial viewport + left margin
; Called at level init (display off, after Level_LoadArt).
; Fills STRIP_CACHE_INIT_COLS strips; right margin is populated by
; Strip_Cache_Fill on the first game loop frame.
; In:  none (reads Camera_X, Slot_Section_Map, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Strip_Cache_Init:
        movem.l a5-a6, -(sp)

        move.l  (Camera_X).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        subi.w  #STRIP_CACHE_MARGIN, d0
        bpl.s   .clamp_ok
        moveq   #0, d0
.clamp_ok:
        move.w  d0, (Strip_Cache_Left_Col).w
        clr.w   (Strip_Cache_Write_Pos).w

        move.w  d0, d7
        move.w  d7, d1
        lsr.w   #8, d1

        movea.l (Current_Act_Ptr).w, a5
        move.w  d1, d0
        bsr.w   StripCache_InitSectionStream

        moveq   #STRIP_CACHE_INIT_COLS-1, d5
        moveq   #0, d4

.fill_loop:
        move.w  d7, d0
        andi.w  #$FF, d0
        bne.s   .same_section
        tst.w   d4
        beq.s   .same_section
        move.w  d7, d1
        lsr.w   #8, d1
        move.w  d1, d0
        bsr.w   StripCache_InitSectionStream

.same_section:
        lea     (Strip_Cache).l, a2
        adda.w  (Strip_Cache_Write_Pos).w, a2
        movem.l d4-d5, -(sp)
        moveq   #0, d0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress
        movem.l (sp)+, d4-d5
        addi.w  #STRIP_BYTE_SIZE, (Strip_Cache_Write_Pos).w

        addq.w  #1, d7
        addq.w  #1, d4
        dbf     d5, .fill_loop

        subq.w  #1, d7
        move.w  d7, (Strip_Cache_Head_Col).w

        move.w  d7, d0
        lsr.w   #8, d0
        move.b  d0, (Strip_Cache_Fwd_Stream).w

        movem.l (sp)+, a5-a6
        rts

; -----------------------------------------------
; StripCache_InitSectionStream — helper: init stream for section d0.w
; In:  d0.w = section_x, a5 = act descriptor
; Out: none
; Clobbers: d0-d2, a0-a1
; -----------------------------------------------
StripCache_InitSectionStream:
        movea.l Act_sec_grid_ptr(a5), a0
        move.w  d0, d1
        lsl.w   #6, d1
        move.w  d0, d2
        lsl.w   #3, d2
        add.w   d2, d1
        adda.w  d1, a0
        movea.l Sec_sec_strips_s4lz(a0), a0
        moveq   #0, d0
        bra.w   S4LZ_Stream_Init

; -----------------------------------------------
; Strip_Cache_Fill — decompress new strips as camera scrolls
; Called each frame after Camera_Update, before Section_UpdateColumns.
; Handles both rightward extension and leftward cache-miss reinit.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Strip_Cache_Fill:
        ; --- leftward cache miss check ---
        move.l  (Camera_X).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        subi.w  #STRIP_CACHE_MARGIN, d0
        bpl.s   .left_clamp_ok
        moveq   #0, d0
.left_clamp_ok:
        cmp.w   (Strip_Cache_Left_Col).w, d0
        bge.s   .no_reinit
        bsr.w   StripCache_Reinit
.no_reinit:

        ; --- rightward fill ---
        move.l  (Camera_X).w, d6
        swap    d6
        addi.w  #327, d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        addi.w  #STRIP_CACHE_MARGIN, d0
        move.w  d0, d7

        move.w  (Strip_Cache_Head_Col).w, d5
.right_loop:
        cmp.w   d7, d5
        bge.s   .right_done
        addq.w  #1, d5

        move.w  d5, d0
        andi.w  #$FF, d0
        bne.s   .right_same_sec
        move.w  d5, d0
        lsr.w   #8, d0
        move.b  d0, (Strip_Cache_Fwd_Stream).w
        movea.l (Current_Act_Ptr).w, a5
        bsr.w   StripCache_InitSectionStream

.right_same_sec:
        move.w  (Strip_Cache_Write_Pos).w, d0
        cmpi.w  #STRIP_CACHE_PHYS_SIZE, d0
        blt.s   .no_slide
        movem.l d5/d7, -(sp)
        bsr.w   StripCache_Slide
        movem.l (sp)+, d5/d7
.no_slide:

        lea     (Strip_Cache).l, a2
        adda.w  (Strip_Cache_Write_Pos).w, a2
        move.w  d5, -(sp)
        moveq   #0, d0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress
        move.w  (sp)+, d5

        addi.w  #STRIP_BYTE_SIZE, (Strip_Cache_Write_Pos).w
        move.w  d5, (Strip_Cache_Head_Col).w
        bra.s   .right_loop

.right_done:
        rts

; -----------------------------------------------
; StripCache_Reinit — re-center cache via checkpoint seeking
; Called when leftward scroll needs strips behind Left_Col.
; Seeks to nearest checkpoint, decompresses forward, keeps all strips
; (checkpoint prefix provides extra left margin — no memmove needed).
; In:  none (reads Camera_X, Slot_Section_Map, Current_Act_Ptr)
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
StripCache_Reinit:
        movem.l a5-a6, -(sp)

        ; compute target left col
        move.l  (Camera_X).w, d6
        swap    d6
        lsr.w   #3, d6
        move.w  d6, d0
        bsr.w   Engine_To_World_Col
        subi.w  #STRIP_CACHE_MARGIN, d0
        bpl.s   .ri_clamp_ok
        moveq   #0, d0
.ri_clamp_ok:
        ; d0 = target_left_col

        ; ckpt_world_col = target_left & $FFC0 (round down to 64-strip checkpoint boundary)
        move.w  d0, d7
        andi.w  #$FFC0, d7              ; d7 = ckpt_world_col (will become Left_Col)

        ; total = (target_left - ckpt_world) + INIT_COLS, capped at PHYS_COLS
        move.w  d0, d5
        sub.w   d7, d5
        addi.w  #STRIP_CACHE_INIT_COLS, d5
        cmpi.w  #STRIP_CACHE_PHYS_COLS, d5
        ble.s   .ri_total_ok
        move.w  #STRIP_CACHE_PHYS_COLS, d5
.ri_total_ok:

        ; ckpt_idx for checkpoint table lookup
        move.w  d0, d4
        lsr.w   #6, d4
        andi.w  #3, d4

        ; section descriptor: sec_grid_ptr + section_x * 72
        move.w  d0, d1
        lsr.w   #8, d1
        movea.l (Current_Act_Ptr).w, a5
        movea.l Act_sec_grid_ptr(a5), a6
        move.w  d1, d0
        move.w  d0, d2
        lsl.w   #6, d2
        lsl.w   #3, d0
        add.w   d0, d2
        adda.w  d2, a6

        ; checkpoint byte offset
        movea.l Sec_sec_strip_checkpoints(a6), a0
        move.w  d4, d0
        add.w   d0, d0
        move.w  (a0, d0.w), d6

        ; init stream at checkpoint
        movea.l Sec_sec_strips_s4lz(a6), a0
        adda.w  d6, a0
        moveq   #0, d0
        bsr.w   S4LZ_Stream_Init

        ; decompress d5 strips starting from world col d7
        clr.w   (Strip_Cache_Write_Pos).w
        move.w  d7, -(sp)               ; save ckpt_world_col for Left_Col
        move.w  d5, d4
        subq.w  #1, d4

.ri_decomp_loop:
        move.w  d7, d0
        andi.w  #$FF, d0
        bne.s   .ri_same_sec
        tst.w   (Strip_Cache_Write_Pos).w
        beq.s   .ri_same_sec
        move.w  d7, d1
        lsr.w   #8, d1
        move.w  d1, d0
        bsr.w   StripCache_InitSectionStream

.ri_same_sec:
        lea     (Strip_Cache).l, a2
        adda.w  (Strip_Cache_Write_Pos).w, a2
        move.w  d4, -(sp)
        moveq   #0, d0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress
        move.w  (sp)+, d4
        addi.w  #STRIP_BYTE_SIZE, (Strip_Cache_Write_Pos).w
        addq.w  #1, d7
        dbf     d4, .ri_decomp_loop

        ; metadata: Head_Col = last decompressed col
        subq.w  #1, d7
        move.w  d7, (Strip_Cache_Head_Col).w

        move.w  d7, d0
        lsr.w   #8, d0
        move.b  d0, (Strip_Cache_Fwd_Stream).w

        ; Left_Col = ckpt_world_col (checkpoint prefix provides extra left margin)
        move.w  (sp)+, d0
        move.w  d0, (Strip_Cache_Left_Col).w

        st.b    (Section_Plane_Dirty).w

        movem.l (sp)+, a5-a6
        rts

; -----------------------------------------------
; StripCache_Slide — evict stale left-side strips, shift data left
; Evicts all strips left of the viewport's left margin.
; In:  none (reads Camera_X, Left_Col, Write_Pos)
; Out: none
; Clobbers: d0-d3, a0-a1, a3
; -----------------------------------------------
StripCache_Slide:
        ; compute safe left bound = viewport_left_tile (world) - margin
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0
        move.w  d0, d1
        subi.w  #SLOT_ORIGIN_L/8, d1
        moveq   #0, d2
        move.b  (Slot_Section_Map).w, d2
        lsl.w   #8, d2
        add.w   d2, d1
        subi.w  #STRIP_CACHE_SLIDE_KEEP, d1     ; d1.w = safe_left (world col, wider margin for backward scroll headroom)

        ; evict_count = safe_left - Left_Col
        move.w  (Strip_Cache_Left_Col).w, d0
        sub.w   d0, d1                          ; d1.w = evict_count
        ble.s   .slide_skip                     ; nothing to evict

        ; d2 = evict_bytes = evict_count * 128
        move.w  d1, d2
        lsl.w   #STRIP_BYTE_SHIFT, d2           ; d2.w = evict_bytes

        ; copy_len = Write_Pos + pending - evict_bytes
        move.w  (Strip_Cache_Write_Pos).w, d3
        lea     (S4LZ_Stream_States).l, a3
        add.w   StreamState_ss_pending(a3), d3
        sub.w   d2, d3                          ; d3.w = bytes to copy
        ble.s   .slide_skip

        ; set up pointers: a0 = source, a1 = dest
        lea     (Strip_Cache).l, a1
        lea     (a1, d2.w), a0

        ; copy in longwords (round up)
        addq.w  #3, d3
        lsr.w   #2, d3
        subq.w  #1, d3
.slide_copy:
        move.l  (a0)+, (a1)+
        dbf     d3, .slide_copy

        ; update metadata
        add.w   d1, (Strip_Cache_Left_Col).w
        sub.w   d2, (Strip_Cache_Write_Pos).w

.slide_skip:
        rts
