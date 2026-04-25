; Sonic animation scripts — walk cycle + idle for test player

Ani_Sonic:
        dc.w Ani_Sonic_Walk-Ani_Sonic           ; anim 0: walk
        dc.w Ani_Sonic_Idle-Ani_Sonic           ; anim 1: idle

Ani_Sonic_Walk:
        dc.b 7                                  ; duration: 7 frames
        dc.b 7, 8, 1, 2, 3, 4, 5, 6            ; S2 walk cycle frame order
        dc.b AF_END                             ; loop
        align 2

Ani_Sonic_Idle:
        dc.b 7                                  ; duration (unused, single frame)
        dc.b 0                                  ; frame 0 = standing
        dc.b AF_END
        align 2
