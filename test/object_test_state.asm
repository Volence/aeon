; Object system test — init objects, load palette+art, spawn test objects, run loop

GameState_ObjectTest_Init:
        ; Load test palette to CRAM line 0
        lea     TestPalette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #32/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        ; DMA test art to VRAM
        move.l  #TestArt, d1
        move.w  #vram_bytes(VRAM_TEST_OBJ), d2
        move.w  #TestArt_End-TestArt, d3
        jsr     QueueDMA_Critical

        ; Init object and sprite systems
        jsr     InitObjectRAM
        jsr     Init_SpriteTable

        ; Clear camera
        clr.l   (Camera_X).w
        clr.l   (Camera_Y).w

        ; Spawn 3 test objects at different positions and priorities
        jsr     AllocDynamic
        bcs.s   .skip1
        move.w  #objroutine(TestStatic), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #112<<16, SST_y_pos(a1)
        move.w  #4, SST_priority(a1)
.skip1:

        jsr     AllocDynamic
        bcs.s   .skip2
        move.w  #objroutine(TestStatic), SST_code_addr(a1)
        move.l  #80<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
        move.w  #2, SST_priority(a1)
.skip2:

        jsr     AllocDynamic
        bcs.s   .skip3
        move.w  #objroutine(TestStatic), SST_code_addr(a1)
        move.l  #240<<16, SST_x_pos(a1)
        move.l  #144<<16, SST_y_pos(a1)
        move.w  #6, SST_priority(a1)
        move.b  #1, SST_mapping_frame(a1)   ; different frame (color 2)
.skip3:

        ; Spawn animated Sonic walk cycle
        jsr     AllocDynamic
        bcs.s   .skip4
        move.w  #objroutine(TestAnimated), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #160<<16, SST_y_pos(a1)
.skip4:

        ; Enable display (VDP reg $01 bit 6)
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

        ; Switch to running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

GameState_ObjectTest:
        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     Render_Sprites
        rts

; -----------------------------------------------
; Test art — two 16x16 colored squares (4 tiles each = 128 bytes each)
; -----------------------------------------------
TestArt:
; Square 1 — palette 0, color index 1 (solid fill)
        rept 4
        dc.l    $11111111, $11111111, $11111111, $11111111
        dc.l    $11111111, $11111111, $11111111, $11111111
        endr
; Square 2 — palette 0, color index 2
        rept 4
        dc.l    $22222222, $22222222, $22222222, $22222222
        dc.l    $22222222, $22222222, $22222222, $22222222
        endr
TestArt_End:

; -----------------------------------------------
; Test palette — 16 colors for CRAM line 0
; Color 1=red, 2=green for static test squares.
; Sonic's palette loaded at CRAM line 0 (overwritten at init).
; -----------------------------------------------
TestPalette:
        BINCLUDE "art/palettes/sonic.bin"
