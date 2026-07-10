; Test particle — short-lived effect with velocity + gravity + auto-despawn
; Allocated from effect pool by emitters via CreateEffect_Normal/Simple.
; Sets its own velocity on init — emitter only controls spawn position.

PARTICLE_GRAVITY        = $20           ; lighter than player gravity ($38)
PARTICLE_X_VEL          = -$100         ; initial horizontal velocity (leftward)
PARTICLE_Y_VEL          = -$300         ; initial vertical velocity (upward)

; -----------------------------------------------
; TestParticle — init routine (called as first-frame code_addr)
; In:  a0 = SST pointer (position, mappings, art_tile set by CreateEffect)
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestParticle:
        move.l  #Ani_Particle, SST_anim_table(a0)
        clr.b   SST_anim(a0)                    ; anim 0: flash
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        ori.b   #6<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #8, SST_width_pixels(a0)
        move.b  #8, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0) ; screen coords (no camera)
        move.w  #PARTICLE_X_VEL, SST_x_vel(a0)
        move.w  #PARTICLE_Y_VEL, SST_y_vel(a0)
        move.w  #objroutine(TestParticle_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestParticle_Main — per-frame update
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestParticle_Main:
        ; Apply gravity (read-modify-write — no register round-trip)
        addi.w  #PARTICLE_GRAVITY, SST_y_vel(a0)

        ; Move
        jsr     ObjectMove

        ; Animate (AF_DELETE handles despawn)
        jsr     AnimateSprite

        ; Draw
        jmp     Draw_Sprite
