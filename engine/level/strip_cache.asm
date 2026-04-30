; World-space strip cache (§4.7)
; 80-column circular buffer in lower RAM ($FFFF0000).
; Decompressed on-demand as camera scrolls.

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
        move.w  (Strip_Cache_Head_Col).w, d1
        sub.w   d0, d1
        move.w  (Strip_Cache_Head_Idx).w, d0
        sub.w   d1, d0
        bpl.s   .no_wrap
        addi.w  #STRIP_CACHE_COLS, d0
.no_wrap:
        lsl.w   #5, d0
        move.w  d0, d1
        add.w   d0, d0
        add.w   d1, d0
        lea     (Strip_Cache).l, a0
        adda.w  d0, a0
        rts

; -----------------------------------------------
; Strip_Cache_Init — populate cache for initial viewport + margins
; Called at level init (display off, after Level_LoadArt).
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
        clr.w   (Strip_Cache_Head_Idx).w

        move.w  d0, d7
        move.w  d7, d1
        lsr.w   #8, d1

        movea.l (Current_Act_Ptr).w, a5
        move.w  d1, d0
        bsr.w   StripCache_InitSectionStream

        moveq   #STRIP_CACHE_COLS-1, d5
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
        move.w  d4, d0
        bsr.w   StripCache_RingAddr
        moveq   #0, d0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress

        addq.w  #1, d7
        addq.w  #1, d4
        dbf     d5, .fill_loop

        subq.w  #1, d7
        move.w  d7, (Strip_Cache_Head_Col).w
        subq.w  #1, d4
        move.w  d4, (Strip_Cache_Head_Idx).w

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
; StripCache_RingAddr — helper: ring buffer address for index d0.w
; In:  d0.w = ring index (0..79)
; Out: a2   = cache address
; Clobbers: d0-d1
; -----------------------------------------------
StripCache_RingAddr:
        lsl.w   #5, d0
        move.w  d0, d1
        add.w   d0, d0
        add.w   d1, d0
        lea     (Strip_Cache).l, a2
        adda.w  d0, a2
        rts

; -----------------------------------------------
; Strip_Cache_Fill — decompress new strips as camera scrolls
; Called each frame after Camera_Update, before Section_UpdateColumns.
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
Strip_Cache_Fill:
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
        move.w  (Strip_Cache_Head_Idx).w, d0
        addq.w  #1, d0
        cmpi.w  #STRIP_CACHE_COLS, d0
        blt.s   .no_wrap_fill
        moveq   #0, d0
.no_wrap_fill:
        move.w  d0, (Strip_Cache_Head_Idx).w

        bsr.w   StripCache_RingAddr
        moveq   #0, d0
        move.w  #STRIP_BYTE_SIZE, d1
        bsr.w   S4LZ_Stream_Decompress

        move.w  d5, (Strip_Cache_Head_Col).w
        move.w  d5, d0
        subi.w  #STRIP_CACHE_COLS-1, d0
        cmp.w   (Strip_Cache_Left_Col).w, d0
        ble.s   .right_loop
        move.w  d0, (Strip_Cache_Left_Col).w
        bra.s   .right_loop

.right_done:
        rts
