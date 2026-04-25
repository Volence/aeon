; Object system test — controllable player, enemies, solid blocks

GameState_ObjectTest_Init:
        ; Load test palette to CRAM line 0
        lea     TestPalette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #32/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        ; DMA test art to VRAM (colored squares for enemies/solids)
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

        ; --- Init test player in Player_1 slot (TouchResponse checks player slots) ---
        lea     (Player_1).w, a1
        move.w  #objroutine(TestPlayer), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)

        ; --- Spawn test enemy at (100, STUB_FLOOR_Y) ---
        jsr     AllocDynamic
        bcs.s   .skip_enemy1
        move.w  #objroutine(TestEnemy), SST_code_addr(a1)
        move.l  #100<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)
.skip_enemy1:

        ; --- Spawn test enemy at (240, STUB_FLOOR_Y) ---
        jsr     AllocDynamic
        bcs.s   .skip_enemy2
        move.w  #objroutine(TestEnemy), SST_code_addr(a1)
        move.l  #240<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)
.skip_enemy2:

        ; --- Spawn solid blocks (platforms above floor) ---
        jsr     AllocDynamic
        bcs.s   .skip_solid1
        move.w  #objroutine(TestSolid), SST_code_addr(a1)
        move.l  #120<<16, SST_x_pos(a1)
        move.l  #150<<16, SST_y_pos(a1)
.skip_solid1:

        jsr     AllocDynamic
        bcs.s   .skip_solid2
        move.w  #objroutine(TestSolid), SST_code_addr(a1)
        move.l  #200<<16, SST_x_pos(a1)
        move.l  #130<<16, SST_y_pos(a1)
.skip_solid2:

        jsr     AllocDynamic
        bcs.s   .skip_solid3
        move.w  #objroutine(TestSolid), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #100<<16, SST_y_pos(a1)
.skip_solid3:

        ; Enable display (VDP reg $01 bit 6)
        SetVDPReg VDP_Shadow_vdp_mode2, #$74

        ; Switch to running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

GameState_ObjectTest:
        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     TouchResponse
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
