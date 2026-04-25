; Combined integration + stress test scene
; Tests all object subsystems at near-capacity: 35+ dynamic slots,
; 10+ effect slots, collision pressure, alloc/free cycling.
; Debug build captures per-frame profiling via VDP V counter.

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

        ; --- Level objects from list (25 objects: 10 enemies + 12 solids + 3 parents) ---
        lea     TestObjectList(pc), a0
        jsr     Load_ObjectList

        ; --- 8 fast emitters spread across screen (effect pool pressure) ---
        ; Each spawns every 8 frames; particles live 12 frames
        ; Steady state: ~12 effect slots occupied
        moveq   #8-1, d4
        lea     .emitter_positions(pc), a2
.spawn_emitters:
        jsr     AllocDynamic
        bne.s   .emitters_done
        move.w  #objroutine(TestStressEmitter), SST_code_addr(a1)
        move.w  (a2)+, d0
        swap    d0
        clr.w   d0
        move.l  d0, SST_x_pos(a1)
        move.w  (a2)+, d0
        swap    d0
        clr.w   d0
        move.l  d0, SST_y_pos(a1)
        dbf     d4, .spawn_emitters
.emitters_done:

        ; Enable display
        setVDPReg VDP_Shadow_vdp_mode2, #$74

        ; Switch to running loop
        move.l  #GameState_ObjectTest, (Game_State).w
        rts

.emitter_positions:
        ;       X,    Y
        dc.w    30,   30
        dc.w    70,   25
        dc.w    110,  30
        dc.w    150,  25
        dc.w    190,  30
        dc.w    230,  25
        dc.w    270,  30
        dc.w    300,  25

; -----------------------------------------------
; GameState_ObjectTest — per-frame update loop with profiling
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
GameState_ObjectTest:
    ifdef __DEBUG__
        move.w  (VDP_HV_COUNTER).l, -(sp)       ; save frame start on stack

        jsr     InitSpriteSystem

        ; --- Profile RunObjects ---
        move.w  (VDP_HV_COUNTER).l, -(sp)
        jsr     RunObjects
        move.w  (VDP_HV_COUNTER).l, d0
        move.w  (sp)+, d1
        sub.w   d1, d0
        lsr.w   #8, d0
        move.w  d0, (Prof_RunObjects).w
        cmp.w   (Prof_Peak_RunObjects).w, d0
        blo.s   .no_peak_run
        move.w  d0, (Prof_Peak_RunObjects).w
.no_peak_run:

        ; --- Profile TouchResponse ---
        move.w  (VDP_HV_COUNTER).l, -(sp)
        jsr     TouchResponse
        move.w  (VDP_HV_COUNTER).l, d0
        move.w  (sp)+, d1
        sub.w   d1, d0
        lsr.w   #8, d0
        move.w  d0, (Prof_TouchResponse).w
        cmp.w   (Prof_Peak_Touch).w, d0
        blo.s   .no_peak_touch
        move.w  d0, (Prof_Peak_Touch).w
.no_peak_touch:

        ; --- Profile Render_Sprites ---
        move.w  (VDP_HV_COUNTER).l, -(sp)
        jsr     Render_Sprites
        move.w  (VDP_HV_COUNTER).l, d0
        move.w  (sp)+, d1
        sub.w   d1, d0
        lsr.w   #8, d0
        move.w  d0, (Prof_RenderSprites).w
        cmp.w   (Prof_Peak_Render).w, d0
        blo.s   .no_peak_render
        move.w  d0, (Prof_Peak_Render).w
.no_peak_render:

        ; --- Total frame time ---
        move.w  (VDP_HV_COUNTER).l, d0
        move.w  (sp)+, d1                       ; frame start from stack
        sub.w   d1, d0
        lsr.w   #8, d0
        move.w  d0, (Prof_FrameTotal).w
        cmp.w   (Prof_Peak_Frame).w, d0
        blo.s   .no_peak_frame
        move.w  d0, (Prof_Peak_Frame).w
.no_peak_frame:

        ; --- Slot usage ---
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
; Object spawn list — stress layout
;
; 10 enemies + 12 solids + 3 parents = 25 from list
; + 8 emitters via AllocDynamic = 33 dynamic slots
; + 9 children from parents = 42 total at peak (overflows to 40 cap)
; + up to 16 effect slots from emitters
;
; dc.l definition_ptr
; dc.w x, y, subtype
; -----------------------------------------------
TestObjectList:
        ; --- 10 enemies across the scene ---
        dc.l    ObjDef_Enemy
        dc.w    50, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    100, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    150, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    200, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    250, STUB_FLOOR_Y, 0
        dc.l    ObjDef_Enemy
        dc.w    80, 155, 0
        dc.l    ObjDef_Enemy
        dc.w    160, 155, 0
        dc.l    ObjDef_Enemy
        dc.w    240, 155, 0
        dc.l    ObjDef_Enemy
        dc.w    120, 120, 0
        dc.l    ObjDef_Enemy
        dc.w    200, 120, 0

        ; --- 12 solid platforms ---
        ; Ground-level stepping stones
        dc.l    ObjDef_Solid
        dc.w    60, 175, 1
        dc.l    ObjDef_Solid
        dc.w    100, 175, 1
        dc.l    ObjDef_Solid
        dc.w    140, 175, 1
        dc.l    ObjDef_Solid
        dc.w    180, 175, 1
        dc.l    ObjDef_Solid
        dc.w    220, 175, 1
        dc.l    ObjDef_Solid
        dc.w    260, 175, 1
        ; Mid platforms
        dc.l    ObjDef_Solid
        dc.w    80, 140, 1
        dc.l    ObjDef_Solid
        dc.w    160, 140, 1
        dc.l    ObjDef_Solid
        dc.w    240, 140, 1
        ; High platforms
        dc.l    ObjDef_Solid
        dc.w    120, 105, 1
        dc.l    ObjDef_Solid
        dc.w    200, 105, 1
        dc.l    ObjDef_Solid
        dc.w    280, 105, 1

        ; --- 3 parents (each spawns 3 children = 9 more dynamic slots) ---
        dc.l    ObjDef_Parent
        dc.w    60, 70, 0
        dc.l    ObjDef_Parent
        dc.w    160, 60, 0
        dc.l    ObjDef_Parent
        dc.w    260, 70, 0

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
