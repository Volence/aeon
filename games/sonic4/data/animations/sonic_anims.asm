; Sonic animation scripts — ordered by the shared ANIM_* ids (constants.asm).
; Walk/Run/Roll use DUR_DYNAMIC: AnimateSprite takes the hold from d3, which
; Player_Animate computes from ground speed (speed-scaled timing).

Ani_Sonic:
        dc.w Ani_Sonic_Walk-Ani_Sonic           ; ANIM_WALK     = 0
        dc.w Ani_Sonic_Run-Ani_Sonic            ; ANIM_RUN      = 1
        dc.w Ani_Sonic_Roll-Ani_Sonic           ; ANIM_ROLL     = 2
        dc.w Ani_Sonic_Spindash-Ani_Sonic       ; ANIM_SPINDASH = 3
        dc.w Ani_Sonic_Push-Ani_Sonic           ; ANIM_PUSH     = 4
        dc.w Ani_Sonic_Wait-Ani_Sonic           ; ANIM_IDLE     = 5
        dc.w Ani_Sonic_Balance-Ani_Sonic        ; ANIM_BALANCE  = 6
        dc.w Ani_Sonic_LookUp-Ani_Sonic         ; ANIM_LOOKUP   = 7
        dc.w Ani_Sonic_Duck-Ani_Sonic           ; ANIM_DUCK     = 8
        dc.w Ani_Sonic_Skid-Ani_Sonic           ; ANIM_SKID     = 9
        dc.w Ani_Sonic_GetUp-Ani_Sonic          ; ANIM_GETUP    = 10
Ani_Sonic_TableEnd:
    if (Ani_Sonic_TableEnd-Ani_Sonic)/2 <> ANIM_COUNT
        error "Ani_Sonic entry count out of sync with ANIM_COUNT"
    endif

Ani_Sonic_Walk:
        dc.b DUR_DYNAMIC                        ; hold from d3 (speed-scaled)
        dc.b 7, 8, 1, 2, 3, 4, 5, 6
        dc.b AF_END
        align 2
Ani_Sonic_Run:
        dc.b DUR_DYNAMIC
        dc.b $21, $22, $23, $24
        dc.b AF_END
        align 2
Ani_Sonic_Roll:
        dc.b DUR_DYNAMIC
        dc.b $96, $97, $96, $98, $96, $99, $96, $9A
        dc.b AF_END
        align 2
Ani_Sonic_Spindash:
        dc.b 0                                  ; advance every frame (fast rev)
        dc.b $86, $87, $86, $88, $86, $89, $86, $8A, $86, $8B
        dc.b AF_END
        align 2
Ani_Sonic_Push:
        dc.b 6
        dc.b $B6, $B7, $B8, $B9
        dc.b AF_END
        align 2
Ani_Sonic_Wait:
        dc.b 7                                  ; neutral stand
        dc.b $BA, $BA, $BA, $BA, $BA, $BA, $BA, $BA
        dc.b $BB, $BC, $BD                      ; lean into foot-tap
        dc.b $BE, $BF, $C0, $BF, $BE            ; tap loop body
        dc.b AF_BACK, 5                         ; loop the tap (5 frames back)
        align 2
Ani_Sonic_Balance:
        dc.b 9
        dc.b $A4, $A5, $A6
        dc.b AF_END
        align 2
Ani_Sonic_LookUp:
        dc.b 5
        dc.b $C3, $C4
        dc.b AF_BACK, 1                         ; hold last frame
        align 2
Ani_Sonic_Duck:
        dc.b 5
        dc.b $9B, $9C
        dc.b AF_BACK, 1                         ; hold last frame
        align 2
Ani_Sonic_Skid:
        dc.b 3
        dc.b $9D, $9E, $9F, $A0
        dc.b AF_BACK, 1                         ; hold the braced pose
        align 2
Ani_Sonic_GetUp:
        dc.b 8
        dc.b $8F
        dc.b AF_END
        align 2

Ani_Sonic_End:
    if (Ani_Sonic_End-Ani_Sonic) > $7FFF
        error "Ani_Sonic exceeds signed word-offset range"
    endif
