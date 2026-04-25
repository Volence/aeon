; Test emitter — spawns particles at a fixed interval
; Placed in the test scene to demonstrate effect pool lifecycle.

_emitter_timer          = SST_sst_custom        ; word — countdown to next spawn
EMITTER_INTERVAL        = 30                    ; frames between spawns

; -----------------------------------------------
; TestEmitter_Init — set up emitter (called as first-frame code_addr)
; In:  a0 = SST pointer (position set by spawn list)
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestEmitter:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #1, SST_mapping_frame(a0)       ; frame 1 (color 2 square)
        move.w  #5, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #EMITTER_INTERVAL, _emitter_timer(a0)
        move.w  #objroutine(TestEmitter_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestEmitter_Main — per-frame: countdown, spawn particle, draw self
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestEmitter_Main:
        subq.w  #1, _emitter_timer(a0)
        bne.s   .draw

        ; Timer expired — spawn particle (particle sets its own velocity)
        move.w  #EMITTER_INTERVAL, _emitter_timer(a0)
        lea     .particle_desc(pc), a1
        jsr     CreateEffect_Normal

.draw:
        jmp     Draw_Sprite

; Descriptor: one particle at emitter position (0,0 offset)
.particle_desc:
        dc.w    objroutine(TestParticle)
        dc.b    0, 0                            ; x_off, y_off = centered
        dc.w    0                               ; terminator
