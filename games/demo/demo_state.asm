; GameState_Demo_Init — one-shot setup: palette, art, one object.
GameState_Demo_Init:
        lea     DemoPalette(pc), a0
        lea     (Palette_Buffer).w, a1
        moveq   #32/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        move.l  #DemoArt, d1
        move.w  #vram_bytes(VRAM_DEMO_OBJ), d2
        move.w  #DemoArt_End-DemoArt, d3
        jsr     QueueDMA_Critical

        jsr     InitObjectRAM
        jsr     Init_SpriteTable
        move.l  #0, (Camera_X).w
        move.l  #0, (Camera_Y).w

        lea     DemoObjectList(pc), a0
        jsr     Load_ObjectList
        ; TODO: your game starts here — spawn objects, load level data, add states

        setVDPReg VDP_Shadow_vdp_mode2, #$74    ; display on

        move.l  #GameState_Demo, (Game_State).w
        rts

; GameState_Demo — per-frame: run + render the object system.
GameState_Demo:
        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     TouchResponse
        jsr     Render_Sprites
        rts
