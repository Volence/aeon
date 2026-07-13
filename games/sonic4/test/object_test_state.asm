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

; ===============================================
; GameState_ObjectTestChurn — dynamic-pool CHURN variant (A2 soak vehicle)
;
; Unlike GameState_ObjectTest (churn lives in the EFFECT pool; dynamic pool
; static 40/40), this fills the dynamic pool to capacity with self-replacing
; TestChurnObj stressors (test_churn.asm). Under this churn Dynamic_Live_Count
; rides at NUM_DYNAMIC while deletions free stack slots mid-walk — the exact
; precondition for AllocDynamic's compact-on-full firing during a live-list
; walk (the A2 hazard the DEBUG Dynamic_Live_Walking rail guards).
;
; Entered at runtime by writing GameState_ObjectTestChurn_Init to Game_State
; (the OJZ scroll test owns Game_Entry). Per-frame it also calls
; EntityWindow_Scan so the fourth live-list walker (DespawnObjects) is
; exercised over the churning pool for the churn profile — the window is left
; inactive (Entity_Window_Active=0) so Scan early-outs to Despawn{Rings,Objects}
; only; the churners are UNTAGGED so DespawnObjects walks and skips them.
; ===============================================
GameState_ObjectTestChurn_Init:
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

        ; Entity-window safe-idle: clear the ring buffer and mark the window
        ; inactive. EntityWindow_Scan then early-outs (Active=0) to
        ; DespawnRings (no-op on the empty buffer) + DespawnObjects (walks the
        ; live list; UNTAGGED churners are skipped, never wrongly deleted).
        jsr     RingBuffer_Clear
        clr.b   (Entity_Window_Active).w

        ; Clear camera
        move.l  #0, (Camera_X).w
        move.l  #0, (Camera_Y).w

        ; --- Player (physics target for TouchResponse; rests on stub floor,
        ;     placed clear of the churner grid so it is not culled/hurt) ---
        lea     (Player_1).w, a1
        move.w  #objroutine(TestPlayer), SST_code_addr(a1)
        move.l  #300<<16, SST_x_pos(a1)
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a1)

        ; --- Fill the dynamic pool to capacity with churn stressors ---
        moveq   #NUM_DYNAMIC-1, d4
        moveq   #0, d5                  ; grid index
.spawn_churn:
        jsr     AllocDynamic
        bne.s   .churn_done             ; pool full — stop
        move.w  #objroutine(TestChurnObj), SST_code_addr(a1)
        ; x = 20 + (i & 7)*36 ; y = 20 + (i>>3)*40  (8-wide grid on screen)
        move.w  d5, d0
        andi.w  #7, d0
        mulu.w  #36, d0
        addi.w  #20, d0
        swap    d0
        clr.w   d0
        move.l  d0, SST_x_pos(a1)
        move.w  d5, d0
        lsr.w   #3, d0
        mulu.w  #40, d0
        addi.w  #20, d0
        swap    d0
        clr.w   d0
        move.l  d0, SST_y_pos(a1)
        addq.w  #1, d5
        dbf     d4, .spawn_churn
.churn_done:

        ; Enable display
        setVDPReg VDP_Shadow_vdp_mode2, #$74

        move.l  #GameState_ObjectTestChurn, (Game_State).w
        rts

; -----------------------------------------------
; GameState_ObjectTestChurn — per-frame update (both build shapes)
; -----------------------------------------------
GameState_ObjectTestChurn:
        jsr     InitSpriteSystem
        jsr     RunObjects              ; DEBUG: A2 assert fires here on the trigger frame
        jsr     TouchResponse
        jsr     EntityWindow_Scan       ; exercises DespawnObjects walk over the churn pool
        jsr     Render_Sprites
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
; Ring art — S3K ring, 4 spin frames × 4 tiles (2×2) = 16 tiles, at
; VRAM_RING_PLACEHOLDER (= VRAM_TEST_OBJ+8). Ported from skdisasm Ring.bin
; (Nemesis, 14 tiles): F0 full / F1 narrower / F2 thin-edge (centred) /
; F3 narrower-mirrored, in VDP 2×2 column-major order per frame; the S3K
; line-0 gold indices remapped to sonic.bin line-0 (E/F gold, 6 white glint).
; DrawRings picks a frame with base + Ring_Anim_Frame×4.
        BINCLUDE "games/sonic4/test/ring_art.bin"
TestArt_End:

; -----------------------------------------------
; Test palette — 16 colors for CRAM line 0
; -----------------------------------------------
TestPalette:
        BINCLUDE "art/palettes/sonic.bin"
