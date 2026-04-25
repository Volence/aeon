; Sonic animation scripts — walk cycle for animation test

Ani_Sonic:
        dc.w Ani_Sonic_Walk-Ani_Sonic           ; anim 0: walk

Ani_Sonic_Walk:
        dc.b 7                                  ; duration: 7 frames
        dc.b 7, 8, 1, 2, 3, 4, 5, 6            ; S2 walk cycle frame order
        dc.b AF_END                             ; loop
        align 2
