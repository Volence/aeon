; Game state machine and main loop (§9.13)

; -----------------------------------------------
; GameLoop — master loop
; VSync → dispatch current state → repeat
; -----------------------------------------------
GameLoop:
        bsr.w   VSync_Wait
        movea.l (Game_State).w, a0
        jsr     (a0)
        bra.s   GameLoop

; -----------------------------------------------
; GameState_DMATest — §1 verification test
; Frame 1: load palette, DMA art, write nametable, enable display
; Frame 2+: idle (image stays on screen)
; -----------------------------------------------
GameState_DMATest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Copy palette to buffer line 0
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w           ; mark line 0 dirty

        ; Queue art DMA to Critical queue (display is off — no budget concern)
        move.l  #Test_TileArt, d1
        move.w  #0, d2
        move.w  #TEST_ART_SIZE, d3
        bsr.w   QueueDMA_Critical

        ; Write nametable to Plane A (direct CPU write, display is off)
        stopZ80
        lea     Test_Nametable(pc), a1
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), d0
        move.w  #TEST_MAP_WIDTH-1, d1
        move.w  #TEST_MAP_HEIGHT-1, d2
        bsr.w   PlaneMapToVRAM
        startZ80

        ; Enable display for next VBlank
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

; -----------------------------------------------
; GameState_S4LZTest — §2 compressed art verification
; Decompresses S4LZ title screen art to RAM buffer,
; DMAs to VRAM, writes nametable, enables display.
; -----------------------------------------------
GameState_S4LZTest:
        tst.b   (Game_State_Init).w
        bne.s   .update

        move.b  #1, (Game_State_Init).w

        ; Copy palette to buffer line 0
        lea     Test_Palette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w

        ; Decompress S4LZ art to buffer
        lea     Test_TileArt_S4LZ(pc), a0
        lea     (Decomp_Buffer).w, a1
        bsr.w   S4LZ_Decompress

        ; Queue DMA from buffer to VRAM tile 0
        move.l  #Decomp_Buffer, d1
        move.w  #0, d2
        move.w  #TEST_ART_SIZE, d3
        bsr.w   QueueDMA_Critical

        ; Write nametable (same as uncompressed test)
        stopZ80
        lea     Test_Nametable(pc), a1
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), d0
        move.w  #TEST_MAP_WIDTH-1, d1
        move.w  #TEST_MAP_HEIGHT-1, d2
        bsr.w   PlaneMapToVRAM
        startZ80

        ; Enable display
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

.update:
        rts

; -----------------------------------------------
; GameState_DPLCTest — §2 DPLC/sprite art verification
; Loads Sonic sprite art via DPLC, displays tiles on Plane A as
; a visual grid. Auto-cycles through animation frames.
; C button = advance frame, Start = pause auto-advance.
; -----------------------------------------------
DPLC_TEST_VRAM_DEST     = 0             ; load tiles to VRAM tile 0
DPLC_TEST_AUTO_DELAY    = 15            ; frames between auto-advance

GameState_DPLCTest:
        tst.b   (Game_State_Init).w
        bne.w   .update

        move.b  #1, (Game_State_Init).w

        ; Load Sonic palette to buffer line 0
        lea     DPLC_Test_Palette, a0
        lea     (Palette_Buffer).w, a1
        moveq   #(32/4)-1, d0
.pal_copy:
        move.l  (a0)+, (a1)+
        dbf     d0, .pal_copy
        move.b  #1, (Palette_Dirty).w

        ; Init frame counter
        clr.w   (DPLC_Test_Frame).w
        move.w  #1, (DPLC_Test_Timer).w

        ; Load frame 0 via DPLC (queues DMA for next VBlank)
        moveq   #0, d0
        lea     DPLC_Test_Table, a0
        lea     DPLC_Test_Art, a1
        move.w  #vram_bytes(DPLC_TEST_VRAM_DEST), d1
        bsr.w   Perform_DPLC

        ; Enable display (tiles will appear after next VBlank DMA)
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

        rts

.update:
        ; Timer-based auto-advance
        subq.w  #1, (DPLC_Test_Timer).w
        bne.s   .check_buttons
        move.w  #DPLC_TEST_AUTO_DELAY, (DPLC_Test_Timer).w

        ; Advance to next frame
        bsr.s   .next_frame
        bra.s   .load_frame

.check_buttons:
        ; C button = manual advance
        move.b  (Ctrl_1_Press).w, d0
        btst    #5, d0                          ; BUTTON_C
        beq.s   .write_nametable
        bsr.s   .next_frame

.load_frame:
        ; Load current frame via DPLC
        move.w  (DPLC_Test_Frame).w, d0
        lea     DPLC_Test_Table, a0
        lea     DPLC_Test_Art, a1
        move.w  #vram_bytes(DPLC_TEST_VRAM_DEST), d1
        bsr.w   Perform_DPLC

.write_nametable:
        ; Write a tile grid nametable showing all loaded tiles
        ; Frame's tiles are contiguous at VRAM tile 0, so just show tile 0,1,2,...
        stopZ80
        move.l  #vdpComm(VRAM_PLANE_A, VRAM, WRITE), (VDP_CTRL).l

        ; Show tiles in a 10-column grid (up to 30 tiles = 3 rows shown)
        lea     (VDP_DATA).l, a6
        moveq   #29, d0                         ; show 30 tiles max
        moveq   #0, d1                          ; tile counter
.tile_grid:
        move.w  d1, (a6)                        ; write tile index (pal 0, no flip)
        addq.w  #1, d1
        dbf     d0, .tile_grid

        startZ80
        rts

.next_frame:
        move.w  (DPLC_Test_Frame).w, d0
        addq.w  #1, d0
        cmpi.w  #DPLC_TEST_FRAMES, d0
        blo.s   .no_wrap
        moveq   #1, d0                          ; skip frame 0 (null frame)
.no_wrap:
        move.w  d0, (DPLC_Test_Frame).w
        rts

; -----------------------------------------------
; Compressed test data
; -----------------------------------------------
Test_TileArt_S4LZ:
        binclude "test/title_art.s4lz"
Test_TileArt_S4LZ_End:
        align 2

; -----------------------------------------------
; Test data — included in ROM
; -----------------------------------------------
TEST_MAP_WIDTH          = 40
TEST_MAP_HEIGHT         = 28

Test_TileArt:
        binclude "test/title_art.bin"
Test_TileArt_End:
TEST_ART_SIZE           = Test_TileArt_End-Test_TileArt

        align 2

Test_Palette:
        binclude "test/title_palette.bin"
        align 2

Test_Nametable:
    set .t, 0
    rept TEST_MAP_HEIGHT
    rept TEST_MAP_WIDTH
        dc.w    .t
    set .t, .t+1
    endr
    endr
Test_Nametable_End:
