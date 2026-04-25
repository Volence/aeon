; Combined integration + stress test scene
; Tests all object subsystems under load: animation, collision, effects,
; children, DPLC, alloc/free cycling. Debug build captures per-frame
; profiling via VDP V counter.

; -----------------------------------------------
; GameState_ObjectTest_Init — one-shot setup
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

        ; DMA test art to VRAM
        move.l  #TestArt, d1
        move.w  #vram_bytes(VRAM_TEST_OBJ), d2
        move.w  #TestArt_End-TestArt, d3
        jsr     QueueDMA_Critical

        ; Init object and sprite systems
        jsr     InitObjectRAM
        jsr     Init_SpriteTable

        ; Clear camera
        move.l  #0, (Camera_X).w
        move.l  #0, (Camera_Y).w

        ; --- Player ---
        lea     (Player_1).w, a1
        move.w  #objroutine(TestPlayer), SST_code_addr(a1)
        move.l  #40<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)

        ; --- Level objects from list ---
        lea     TestObjectList(pc), a0
        jsr     Load_ObjectList

        ; --- Emitter 1: left side, continuous particle shower ---
        jsr     AllocDynamic
        bne.s   .no_em1
        move.w  #objroutine(TestEmitter), SST_code_addr(a1)
        move.l  #60<<16, SST_x_pos(a1)
        move.l  #40<<16, SST_y_pos(a1)
.no_em1:

        ; --- Emitter 2: center ---
        jsr     AllocDynamic
        bne.s   .no_em2
        move.w  #objroutine(TestEmitter), SST_code_addr(a1)
        move.l  #160<<16, SST_x_pos(a1)
        move.l  #40<<16, SST_y_pos(a1)
.no_em2:

        ; --- Emitter 3: right side ---
        jsr     AllocDynamic
        bne.s   .no_em3
        move.w  #objroutine(TestEmitter), SST_code_addr(a1)
        move.l  #260<<16, SST_x_pos(a1)
        move.l  #40<<16, SST_y_pos(a1)
.no_em3:

        ; --- Parent 1: left cluster ---
        jsr     AllocDynamic
        bne.s   .no_par1
        move.w  #objroutine(TestParent), SST_code_addr(a1)
        move.l  #80<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
.no_par1:

        ; --- Parent 2: right cluster ---
        jsr     AllocDynamic
        bne.s   .no_par2
        move.w  #objroutine(TestParent), SST_code_addr(a1)
        move.l  #240<<16, SST_x_pos(a1)
        move.l  #80<<16, SST_y_pos(a1)
.no_par2:

        ; Enable display
        setVDPReg VDP_Shadow_vdp_mode2, #$74

        ; Switch to running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

; -----------------------------------------------
; GameState_ObjectTest — per-frame update loop with profiling
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
GameState_ObjectTest:
    ifdef __DEBUG__
        move.w  (VDP_HV_COUNTER).l, d7  ; frame start V counter

        jsr     InitSpriteSystem

        move.w  (VDP_HV_COUNTER).l, d6  ; before RunObjects
        jsr     RunObjects
        move.w  (VDP_HV_COUNTER).l, d5
        sub.w   d6, d5
        andi.w  #$FF00, d5
        lsr.w   #8, d5
        move.w  d5, (Prof_RunObjects).w
        cmp.w   (Prof_Peak_RunObjects).w, d5
        blo.s   .no_peak_run
        move.w  d5, (Prof_Peak_RunObjects).w
.no_peak_run:

        move.w  (VDP_HV_COUNTER).l, d6  ; before TouchResponse
        jsr     TouchResponse
        move.w  (VDP_HV_COUNTER).l, d5
        sub.w   d6, d5
        andi.w  #$FF00, d5
        lsr.w   #8, d5
        move.w  d5, (Prof_TouchResponse).w
        cmp.w   (Prof_Peak_Touch).w, d5
        blo.s   .no_peak_touch
        move.w  d5, (Prof_Peak_Touch).w
.no_peak_touch:

        move.w  (VDP_HV_COUNTER).l, d6  ; before Render_Sprites
        jsr     Render_Sprites
        move.w  (VDP_HV_COUNTER).l, d5
        sub.w   d6, d5
        andi.w  #$FF00, d5
        lsr.w   #8, d5
        move.w  d5, (Prof_RenderSprites).w
        cmp.w   (Prof_Peak_Render).w, d5
        blo.s   .no_peak_render
        move.w  d5, (Prof_Peak_Render).w
.no_peak_render:

        ; Total frame time
        move.w  (VDP_HV_COUNTER).l, d5
        sub.w   d7, d5
        andi.w  #$FF00, d5
        lsr.w   #8, d5
        move.w  d5, (Prof_FrameTotal).w
        cmp.w   (Prof_Peak_Frame).w, d5
        blo.s   .no_peak_frame
        move.w  d5, (Prof_Peak_Frame).w
.no_peak_frame:

        ; Slot usage: count = (stack_base - SP) / 2
        move.w  #Dynamic_Free_Stack+NUM_DYNAMIC*2, d0
        sub.w   (Dynamic_Free_SP).w, d0
        lsr.w   #1, d0
        move.w  d0, (Prof_Dynamic_Used).w

        move.w  #Effect_Free_Stack+NUM_EFFECTS*2, d0
        sub.w   (Effect_Free_SP).w, d0
        lsr.w   #1, d0
        move.w  d0, (Prof_Effect_Used).w

    else

        jsr     InitSpriteSystem
        jsr     RunObjects
        jsr     TouchResponse
        jsr     Render_Sprites

    endif
        rts

; -----------------------------------------------
; Object spawn list — mini platforming playground
;
; Layout (320x224 screen, floor at Y=192):
;
;   Emitters rain particles from top (spawned via AllocDynamic)
;   Parents with children orbit at Y=80 (spawned via AllocDynamic)
;
;       [S]     [S]         <- floating platforms (Y=100, Y=80)
;         [S]               <- mid platform (Y=130)
;   [E]     [S]     [E]     <- ground-level staircase + enemies
;     [S] [S] [S]   [S] [E] <- low platforms (Y=160, Y=170) + enemies
;   P___________________________[E]__[E]___  <- floor (Y=192)
;   0   40  80 120 160 200 240 280
;
; dc.l definition_ptr
; dc.w x, y, subtype
; -----------------------------------------------
TestObjectList:
        ; Ground enemies — patrol across floor
        dc.l    ObjDef_Enemy
        dc.w    100, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    200, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    280, STUB_FLOOR_Y, 0

        ; Elevated enemies — patrol on platforms
        dc.l    ObjDef_Enemy
        dc.w    60, 160, 0
        dc.l    ObjDef_Enemy
        dc.w    260, 160, 0

        ; Low platforms — stepping stones (Y=170)
        dc.l    ObjDef_Solid
        dc.w    70, 170, 1
        dc.l    ObjDef_Solid
        dc.w    110, 170, 1
        dc.l    ObjDef_Solid
        dc.w    150, 170, 1
        dc.l    ObjDef_Solid
        dc.w    250, 170, 1

        ; Mid platforms — staircase up (Y=150, Y=130)
        dc.l    ObjDef_Solid
        dc.w    130, 150, 1
        dc.l    ObjDef_Solid
        dc.w    180, 130, 1

        ; High platforms (Y=100, Y=80)
        dc.l    ObjDef_Solid
        dc.w    100, 100, 1
        dc.l    ObjDef_Solid
        dc.w    220, 80, 1

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
