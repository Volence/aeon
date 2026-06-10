; Sonic animation scripts — walk, idle, roll for test player
; NOTE: S2 frame 0 has 0 mapping pieces and 0 DPLC entries (art pre-loaded
; in original engine). We use walk frame 5 as idle since it's a neutral pose.

Ani_Sonic:
        dc.w Ani_Sonic_Walk-Ani_Sonic           ; anim 0: walk
        dc.w Ani_Sonic_Idle-Ani_Sonic           ; anim 1: idle
        dc.w Ani_Sonic_Roll-Ani_Sonic           ; anim 2: roll/jump

Ani_Sonic_Walk:
        dc.b 7                                  ; duration: 7 frames
        dc.b 7, 8, 1, 2, 3, 4, 5, 6            ; S2 walk cycle frame order
        dc.b AF_END                             ; loop
        align 2

Ani_Sonic_Idle:
        dc.b 30                                 ; duration: hold for 30 frames
        dc.b 5                                  ; frame 5 = neutral walk pose (has valid DPLC)
        dc.b AF_END
        align 2

Ani_Sonic_Roll:
        dc.b 3                                  ; duration: fast spin
        dc.b 9, 10, 11, 12, 13                  ; rolling frames
        dc.b AF_END                             ; loop
        align 2

Ani_Sonic_End:
    if (Ani_Sonic_End-Ani_Sonic) > $7FFF
        error "Ani_Sonic exceeds signed word-offset range"
    endif
