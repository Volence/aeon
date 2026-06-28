; Particle animation scripts — short flash → auto-despawn

Ani_Particle:
        dc.w Ani_Particle_Flash-Ani_Particle    ; anim 0: flash then die

Ani_Particle_Flash:
        dc.b 4                                  ; duration: 4 frames per frame
        dc.b 2, 2, 2                            ; frame 2 (8x8 particle) × 3 cycles
        dc.b AF_DELETE                          ; auto-despawn
        align 2

Ani_Particle_End:
    if (Ani_Particle_End-Ani_Particle) > $7FFF
        error "Ani_Particle exceeds signed word-offset range"
    endif
