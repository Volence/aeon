; Object system test — controllable player + data-driven object spawning

; -----------------------------------------------
; GameState_ObjectTest_Init — one-shot setup for object test scene
; In:  none
; Out: none
; Clobbers: d0-d3, a0-a2
; -----------------------------------------------
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

        ; --- Player goes in reserved slot (not via Load_Object) ---
        lea     (Player_1).w, a1
        move.w  #objroutine(TestPlayer), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)

        ; --- Spawn level objects from list ---
        lea     TestObjectList(pc), a0
        jsr     Load_ObjectList

        ; --- Spawn test emitter (effect pool demo) ---
        jsr     AllocDynamic
        bne.s   .no_emitter
        move.w  #objroutine(TestEmitter), SST_code_addr(a1)
        move.l  #60<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
.no_emitter:

        ; Enable display (VDP reg $01 bit 6)
        setVDPReg VDP_Shadow_vdp_mode2, #$74

        ; Switch to running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

; -----------------------------------------------
; GameState_ObjectTest — per-frame update loop
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
GameState_ObjectTest:
        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     TouchResponse
        jsr     Render_Sprites
        rts

; -----------------------------------------------
; Test object spawn list (10 bytes per entry, dc.l 0 terminator)
;   dc.l  definition_pointer
;   dc.w  x, y, subtype
; -----------------------------------------------
TestObjectList:
        dc.l    ObjDef_Enemy
        dc.w    100, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    240, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Solid
        dc.w    120, 150, 1
        dc.l    ObjDef_Solid
        dc.w    200, 130, 1
        dc.l    ObjDef_Solid
        dc.w    160, 100, 1
        dc.l    0                       ; end

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
; -----------------------------------------------
TestPalette:
        BINCLUDE "art/palettes/sonic.bin"
