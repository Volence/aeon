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
