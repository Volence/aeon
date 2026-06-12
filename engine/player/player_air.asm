; Player airborne states — AIR today; JUMP/ROLLJUMP/AIRBALL share the
; air body in Task 6 (§5). Reached only through the Player_States offset
; table in player_common.asm; shares its overlay equates, macros, and
; the (a4) physics-table convention.
;
; Lives in the object code bank, included from main.asm immediately
; after player_ground.asm.

; -----------------------------------------------
; PState_Air — minimal fall + flat landing. Full air physics (drag,
; release cap, ceiling/wall probes, landing banding) is Task 6.
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to PSTATE_GROUND)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Air:
        ; --- air control: x_vel directly — gsp is NOT authoritative
        ; airborne ---
        move.b  (Ctrl_1_Held).w, d2
        maskOpposingLR d2
        move.w  SST_x_vel(a0), d0
        btst    #2, d2                          ; LEFT
        bne.s   .air_left
        btst    #3, d2                          ; RIGHT
        beq.s   .air_input_done
        bclr    #ST_XFLIP, SST_status(a0)
        add.w   PPHYS_AIR_ACCEL(a4), d0
        ; TODO(Task 6): S3K back-out — preserve above-top launch speed;
        ; plain clamp until then
        move.w  PPHYS_TOP_SPEED(a4), d1
        cmp.w   d1, d0
        ble.s   .air_store
        move.w  d1, d0
        bra.s   .air_store
.air_left:
        bset    #ST_XFLIP, SST_status(a0)
        sub.w   PPHYS_AIR_ACCEL(a4), d0
        move.w  PPHYS_TOP_SPEED(a4), d1
        neg.w   d1
        cmp.w   d1, d0
        bge.s   .air_store
        move.w  d1, d0
.air_store:
        move.w  d0, SST_x_vel(a0)
.air_input_done:
        ; TODO(Task 6): air drag (x_vel -= x_vel>>5 while −$400 ≤ y_vel < 0)
        ; goes here, before gravity

        ; --- gravity + fall cap ---
        move.w  SST_y_vel(a0), d0
        add.w   PPHYS_GRAVITY(a4), d0
        cmpi.w  #PHYS_FALL_CAP, d0
        ble.s   .fall_capped
        move.w  #PHYS_FALL_CAP, d0
.fall_capped:
        move.w  d0, SST_y_vel(a0)

        jsr     ObjectMove

        ; TODO(Task 6): ceiling + wall air probes (motion-quadrant sensor
        ; activation) go here, post-move

        ; --- landing (falling only) ---
        tst.w   SST_y_vel(a0)
        bmi.s   .no_land
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        tst.w   d0
        bpl.s   .no_land                        ; must be embedded to land
        ; eligibility: dist ≥ −(y_vel>>8) − 8 — embed tolerance scales
        ; with fall speed (spec §6)
        move.w  SST_y_vel(a0), d2
        lsr.w   #8, d2
        addq.w  #8, d2
        neg.w   d2
        cmp.w   d2, d0
        blt.s   .no_land                        ; too deep — keep falling
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        add.l   d0, SST_y_pos(a0)
        move.b  d1, SST_angle(a0)
        ; landing speed conversion — FLAT subset; Task 6 adds the classic
        ; motion-quadrant + angle-band select
        move.w  SST_x_vel(a0), _pl_gsp(a0)
        clr.w   SST_y_vel(a0)
        moveq   #PSTATE_GROUND, d0
        jmp     Player_SetState
.no_land:
        rts
