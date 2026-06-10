; Fast particle emitter for stress testing
; Spawns particles at STRESS_EMITTER_INTERVAL (8 frames) to flood the effect pool.

STRESS_EMITTER_INTERVAL = 8

_stress_timer           = SST_sst_custom

; -----------------------------------------------
; TestStressEmitter — init
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestStressEmitter:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #1, SST_mapping_frame(a0)
        ori.b   #7<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #8, SST_width_pixels(a0)
        move.b  #8, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        ; Direct-alloc + no animation: populate sprite_piece_count manually
        ; (Load_Object would have done this; AnimateSprite refresh won't fire.)
        movea.l a0, a2
        jsr     PopulateSpawnedPieceCount
        move.w  #STRESS_EMITTER_INTERVAL, _stress_timer(a0)
        move.w  #objroutine(TestStressEmitter_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestStressEmitter_Main — per-frame: countdown, spawn particle
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestStressEmitter_Main:
        subq.w  #1, _stress_timer(a0)
        bne.s   .draw
        move.w  #STRESS_EMITTER_INTERVAL, _stress_timer(a0)
        lea     .particle_desc(pc), a1
        jsr     CreateEffect_Normal
.draw:
        jmp     Draw_Sprite

.particle_desc:
        dc.w    objroutine(TestParticle)
        dc.b    0, 0
        dc.w    0
