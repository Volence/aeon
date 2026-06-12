; Player grounded states — GROUND + Player_Jump today; ROLL/SPINDASH
; land here in Tasks 7-8 (§5). Player_Jump lives in this file because
; it is invoked only from grounded states (its tail jumps into the air
; body in player_air.asm — the bug #4 press-frame fix). Reached only
; through the Player_States offset table in player_common.asm; shares
; its overlay equates, macros, and the (a4) physics-table convention.
;
; Lives in the object code bank, included from main.asm immediately
; after player_common.asm.

; -----------------------------------------------
; PState_Ground — standing/running. FLAT subset: slope factor, quadrant-
; generalized snap axis, and the S3K wall-probe angle gates are Task 7.
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to PSTATE_AIR)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Ground:
        ; TODO(Task 8): spindash check goes here (first, classic order)
        ; --- jump check (classic order: after spindash, before slope/
        ; input). Player_JumpBuffer covers fresh press AND buffered —
        ; latched on the press edge in Player_Main; consumed only on a
        ; successful launch, so a headroom rejection leaves it live and
        ; the classic retry happens next frame while the buffer lasts ---
        tst.b   (Player_JumpBuffer).w
        beq.s   .no_jump
        jsr     Player_SensorCeiling            ; headroom: d0 = clearance
                                                ; (≥16 sentinel = open sky)
        cmpi.w  #6, d0
        bge.w   Player_Jump                     ; classic CalcRoomOverHead
                                                ; ≥6px rule; does not return
.no_jump:
        ; TODO(Task 7): slope factor on gsp goes here — BEFORE input,
        ;               using last frame's angle (classic order)
        bsr.w   Ground_Move
        jsr     ObjectMove

        ; --- floor pair: snap / angle update / ledge detach ---
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        ; adaptive snap-down window: min(|gsp|>>8 + 4, 14)
        ; TODO(Task 7): window should use speed along the probe axis
        ; (gsp·cos) per the plan, and the AIR landing snap should fold
        ; into the same quadrant-axis helper
        move.w  _pl_gsp(a0), d2
        bpl.s   .speed_pos
        neg.w   d2
.speed_pos:
        lsr.w   #8, d2
        addq.w  #4, d2
        cmpi.w  #14, d2
        bls.s   .window_ok
        moveq   #14, d2
.window_ok:
        cmp.w   d2, d0
        bgt.s   .airborne                       ; surface beyond snap reach —
                                                ; covers both-sensors-nothing
                                                ; (dist ≥16 from the pair)
                                                ; and a ledge run-off
        cmpi.w  #-14, d0
        blt.s   .too_deep                       ; embedded past the fixed
                                                ; snap-up — classic ignores
        ; snap along the floor axis (floor mode; Task 7 selects the axis
        ; by quadrant)
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        add.l   d0, SST_y_pos(a0)
        move.b  d1, SST_angle(a0)
.too_deep:
        rts
.airborne:
        moveq   #PSTATE_AIR, d0                 ; velocities kept — gravity
        jmp     Player_SetState                 ; takes over next frame

; -----------------------------------------------
; Ground_Move — input → ground_speed, projection, ground wall probe
; Classic accel/decel/friction semantics with the S3K back-out top-speed
; rule and the turnaround kick (research physics-classics §1).
; In:  a0 = player SST, a4 = Player_Phys
; Out: none
; Clobbers: d0-d6, a1
; -----------------------------------------------
Ground_Move:
        move.w  _pl_gsp(a0), d0
        tst.w   _pl_move_lock(a0)
        bne.s   .friction                       ; slip/spring input freeze:
                                                ; friction still runs (S3K);
                                                ; decrement is Task 7's
                                                ; SlopeRepel business
        move.b  (Ctrl_1_Held).w, d2
        maskOpposingLR d2
        btst    #2, d2                          ; LEFT
        bne.s   .move_left
        btst    #3, d2                          ; RIGHT
        bne.s   .move_right
.friction:
        move.w  PPHYS_FRICTION(a4), d1
        tst.w   d0
        beq.s   .cap
        bmi.s   .friction_neg
        sub.w   d1, d0
        bcc.s   .cap                            ; borrow = crossed zero
        moveq   #0, d0
        bra.s   .cap
.friction_neg:
        add.w   d1, d0
        bcc.s   .cap                            ; carry = crossed zero
        moveq   #0, d0
        bra.s   .cap

.move_left:
        tst.w   d0
        ble.s   .accel_left
        ; decelerating against rightward motion
        sub.w   PPHYS_DECEL(a4), d0
        bcc.s   .cap
        moveq   #-$80, d0                       ; turnaround kick (.w use only)
        bra.s   .cap
.accel_left:
        bset    #ST_XFLIP, SST_status(a0)
        move.w  PPHYS_TOP_SPEED(a4), d1
        neg.w   d1
        cmp.w   d1, d0
        ble.s   .cap                            ; at/beyond −top already:
                                                ; preserve (S3K back-out —
                                                ; input never curtails
                                                ; earned overspeed)
        sub.w   PPHYS_ACCEL(a4), d0
        cmp.w   d1, d0
        bge.s   .cap
        move.w  d1, d0                          ; crossed top this frame → clamp
        bra.s   .cap

.move_right:
        tst.w   d0
        bge.s   .accel_right
        add.w   PPHYS_DECEL(a4), d0
        bcc.s   .cap
        move.w  #$80, d0                        ; turnaround kick (+$80 exceeds
                                                ; moveq's signed-byte range)
        bra.s   .cap
.accel_right:
        bclr    #ST_XFLIP, SST_status(a0)
        move.w  PPHYS_TOP_SPEED(a4), d1
        cmp.w   d1, d0
        bge.s   .cap                            ; S3K back-out (see .accel_left)
        add.w   PPHYS_ACCEL(a4), d0
        cmp.w   d1, d0
        ble.s   .cap
        move.w  d1, d0

.cap:
        ; GSp tunneling guard ±$1000. FEEL DEVIATION coupling (spec §2.1):
        ; raising it requires CAM_MAX_Y_STEP, VFILL_ROWS_PER_FRAME, and
        ; sensor reach to rise together.
        cmpi.w  #PHYS_GSP_CAP, d0
        ble.s   .cap_pos_ok
        move.w  #PHYS_GSP_CAP, d0
.cap_pos_ok:
        cmpi.w  #-PHYS_GSP_CAP, d0
        bge.s   .cap_neg_ok
        move.w  #-PHYS_GSP_CAP, d0
.cap_neg_ok:
        move.w  d0, _pl_gsp(a0)

        ; --- inertia → velocity projection ---
        ; angle 0 fast path: x_vel = gsp exactly, y_vel = 0 (skips two
        ; muls — the flat common case)
        tst.b   SST_angle(a0)
        bne.s   .project_slope
        move.w  d0, SST_x_vel(a0)
        clr.w   SST_y_vel(a0)
        bra.s   .wall_probe
.project_slope:
        ; classic Traction: x_vel = cos·gsp>>8, y_vel = sin·gsp>>8 — NO
        ; negation: the angle convention (down-right slope = +$10) and the
        ; sine table (sin($10) = +$61) already agree with screen-down-
        ; positive Y. Verified against data/misc/sine.bin + the sensor
        ; self-check slope (attr $04, angle $10, heights falling rightward).
        move.w  d0, d2                          ; capped gsp — survives
                                                ; GetSineCosine (d0/d1 only)
        moveq   #0, d0
        move.b  SST_angle(a0), d0
        jsr     GetSineCosine                   ; d0 = sin·$100, d1 = cos·$100
        ; variable×variable product — no table/shift form exists; one
        ; player, slope frames only (flat fast path above), classic does
        ; exactly this in Traction
        muls.w  d2, d1                          ; lint: disable=E002
        asr.l   #8, d1
        move.w  d1, SST_x_vel(a0)
        muls.w  d2, d0                          ; lint: disable=E002
        asr.l   #8, d0
        move.w  d0, SST_y_vel(a0)

.wall_probe:
        ; --- ground wall probe at next-frame position ---
        ; TODO(Task 7): S3K gates — skip when angle is non-cardinal in the
        ; upper half; quadrant-rotated probe axis; −5px offset rolling.
        ; Flat-ground-only form below (angle 0, foot-level +8px).
        move.w  _pl_gsp(a0), d4                 ; direction sign for the probe
        beq.s   .clear_push
        move.w  SST_x_vel(a0), d0
        asr.w   #8, d0
        add.w   SST_x_pos(a0), d0               ; projected engine X
        tst.w   d4
        bmi.s   .probe_left
        addi.w  #PUSH_RADIUS, d0
        bra.s   .probe_go
.probe_left:
        subi.w  #PUSH_RADIUS, d0
.probe_go:
        move.w  SST_y_vel(a0), d1
        asr.w   #8, d1
        add.w   SST_y_pos(a0), d1               ; projected engine Y
        addq.w  #8, d1                          ; flat-ground foot-level offset
        jsr     Player_SensorWallAt             ; d0 dist (clobbers d0-d6)
        tst.w   d0
        bmi.s   .wall_hit
.clear_push:
        bclr    #ST_PUSHING, SST_status(a0)
        rts
.wall_hit:
        ; back the blocked distance into x_vel — the player advances
        ; exactly to the wall face this frame; inertia dies
        asl.w   #8, d0                          ; dist → 8.8
        tst.w   _pl_gsp(a0)
        bmi.s   .hit_left
        add.w   d0, SST_x_vel(a0)
        clr.w   _pl_gsp(a0)
        ; facing-aware push bit (S3K): only when facing the wall
        btst    #ST_XFLIP, SST_status(a0)
        bne.s   .clear_push
        bra.s   .set_push
.hit_left:
        sub.w   d0, SST_x_vel(a0)
        clr.w   _pl_gsp(a0)
        btst    #ST_XFLIP, SST_status(a0)
        beq.s   .clear_push
.set_push:
        bset    #ST_PUSHING, SST_status(a0)
        rts

; -----------------------------------------------
; Player_Jump — launch from a grounded state (headroom already verified
; by the caller, buffer consumed here). Perpendicular ADD along the
; surface normal, angle − $40 (research §3): running speed is preserved
; — gsp is NOT zeroed, it's already projected into x_vel/y_vel.
; In:  a0 = player SST, a4 = Player_Phys
; Out: DOES NOT return to the ground flow — transitions to PSTATE_JUMP
;      and runs the air body THIS frame, returning to Player_Main's
;      dispatch.
;      bug #4 fix: the classic aborts the press frame with
;      `addq.l #4,sp` (no movement until the next frame); we complete
;      the frame airborne so movement happens on the press frame.
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Player_Jump:
        clr.b   (Player_JumpBuffer).w           ; consume the buffered press
        move.w  PPHYS_JUMP_FORCE(a4), d2
        move.b  SST_angle(a0), d0
        beq.s   .flat
        subi.b  #$40, d0                        ; surface normal
        jsr     GetSineCosine                   ; d0 sin·$100, d1 cos·$100
                                                ; (d2 survives — clobbers
                                                ; nothing else)
        ; variable×variable product — one-shot event, classic Sonic_Jump
        ; does exactly this
        muls.w  d2, d1                          ; lint: disable=E002
        asr.l   #8, d1
        add.w   d1, SST_x_vel(a0)
        muls.w  d2, d0                          ; lint: disable=E002
        asr.l   #8, d0
        add.w   d0, SST_y_vel(a0)
        bra.s   .launched
.flat:
        ; angle 0 fast path: cos(−$40) = 0, sin(−$40) = −$100 →
        ; x_vel += 0, y_vel −= jump_force (from rest: exactly −$680).
        ; Same algebra as the muls path under the engine's UNNEGATED
        ; y_vel = +sin convention (see Ground_Move .project_slope)
        sub.w   d2, SST_y_vel(a0)
.launched:
        clr.b   _pl_stick_convex(a0)
        moveq   #PSTATE_JUMP, d0
        ; TODO(Task 7): from PSTATE_ROLL → PSTATE_ROLLJUMP instead
        bsr.w   Player_SetState
        ; bug #4 fix: run the full air body on the press frame
        jmp     PState_Jump
