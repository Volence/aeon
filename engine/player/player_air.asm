; Player airborne states — AIR/JUMP/ROLLJUMP/AIRBALL share one body
; (§5 Task 6); tiny preambles set the two behavior bits. Reached only
; through the Player_States offset table in player_common.asm; shares
; its overlay equates, macros, and the (a4) physics-table convention.
;
; Lives in the object code bank, included from main.asm immediately
; after player_ground.asm.

; Air behavior flag bits, carried in d6.b through body steps 1-2 only —
; the sensor layer clobbers d6, but nothing after the input block reads
; the flags
AIRF_RELEASE_CAP        = 0     ; variable jump height (JUMP/ROLLJUMP)
AIRF_INPUT_LOCK         = 1     ; air-input block skipped (ROLLJUMP)

; -----------------------------------------------
; PState_Air / PState_Jump / PState_RollJump / PState_AirBall —
; per-state preambles → shared air body.
;   AIR      uncurled fall (ledge walk-off, springs): no cap, no lock
;   JUMP     curled from a jump: release cap
;   ROLLJUMP as JUMP + the classic air-control lockout (research §5:
;            the WHOLE input block is skipped — drag still runs)
;   AIRBALL  curled, not from a jump (rolled off a ledge): no cap
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to PSTATE_GROUND)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Air:
PState_AirBall:                                 ; same flags as AIR today;
                                                ; restack if they ever diverge
        moveq   #0, d6
        bra.s   PState_AirShared
PState_RollJump:
        moveq   #(1<<AIRF_RELEASE_CAP)|(1<<AIRF_INPUT_LOCK), d6
        bra.s   PState_AirShared
PState_Jump:
        moveq   #1<<AIRF_RELEASE_CAP, d6
        ; fall through

; NOT a dispatch target — enter ONLY via a preamble above that sets the
; AIRF_* flags in d6. Pointing a state table row here directly would run
; with whatever d6 holds at dispatch time.
PState_AirShared:
        ; --- 1. variable jump height: while rising faster than the
        ; release cap with no jump button held, cut to the cap ---
        btst    #AIRF_RELEASE_CAP, d6
        beq.s   .no_cap
        move.w  SST_y_vel(a0), d0
        cmp.w   PPHYS_RELEASE_CAP(a4), d0
        bge.s   .no_cap                         ; not rising past the cap
        move.b  (Ctrl_1_Held).w, d1
        andi.b  #BUTTON_JUMP_MASK, d1
        bne.s   .no_cap                         ; still held → full arc
        move.w  PPHYS_RELEASE_CAP(a4), SST_y_vel(a0)
.no_cap:

        ; --- 2. air input: x_vel directly — gsp is NOT authoritative
        ; airborne. ROLLJUMP lockout skips the whole block (no accel,
        ; no facing change) ---
        btst    #AIRF_INPUT_LOCK, d6
        bne.s   .input_done
        move.b  (Ctrl_1_Held).w, d2
        maskOpposingLR d2
        move.w  SST_x_vel(a0), d0
        btst    #2, d2                          ; LEFT
        bne.s   .air_left
        btst    #3, d2                          ; RIGHT
        beq.s   .input_done
        bclr    #ST_XFLIP, SST_status(a0)
        move.w  PPHYS_TOP_SPEED(a4), d1
        cmp.w   d1, d0
        bge.s   .input_done                     ; S3K back-out: speed already
                                                ; at/above top is preserved —
                                                ; input never curtails it
        add.w   PPHYS_AIR_ACCEL(a4), d0
        cmp.w   d1, d0
        ble.s   .air_store
        move.w  d1, d0                          ; crossed top this frame → clamp
        bra.s   .air_store
.air_left:
        bset    #ST_XFLIP, SST_status(a0)
        move.w  PPHYS_TOP_SPEED(a4), d1
        neg.w   d1
        cmp.w   d1, d0
        ble.s   .input_done                     ; S3K back-out (mirror)
        sub.w   PPHYS_AIR_ACCEL(a4), d0
        cmp.w   d1, d0
        bge.s   .air_store
        move.w  d1, d0
.air_store:
        move.w  d0, SST_x_vel(a0)
.input_done:

        ; --- 3. air drag — ALL air states, lockout included. Exact
        ; classic band: −$400 ≤ y_vel ≤ −1 (apex, rising slowly). The
        ; asr supplies the sign work: x_vel in −$1F..−$1 still drags −1
        ; toward zero while +0..+$1F drags 0; subtraction direction is
        ; automatic for both signs and can't cross zero (|x>>5| ≤ |x|) ---
        move.w  SST_y_vel(a0), d0
        bpl.s   .no_drag                        ; falling/level → no drag
        cmpi.w  #-$400, d0
        blt.s   .no_drag                        ; rising faster than $400
        move.w  SST_x_vel(a0), d0
        move.w  d0, d1
        asr.w   #5, d1
        beq.s   .no_drag
        sub.w   d1, d0
        move.w  d0, SST_x_vel(a0)
.no_drag:

        ; --- 4. integrate, THEN gravity (classic order, research §4:
        ; old y_vel moves you this frame, gravity sets up the next —
        ; resolves Task 5's noted gravity-first deviation) ---
        jsr     ObjectMove
        move.w  SST_y_vel(a0), d0
        add.w   PPHYS_GRAVITY(a4), d0
        cmpi.w  #PHYS_FALL_CAP, d0
        ble.s   .fall_capped
        move.w  #PHYS_FALL_CAP, d0
.fall_capped:
        ; FEEL DEVIATION (spec §2.1): classic non-jump up-velocity cap
        ; (y_vel clamped to -$FC0) deliberately REMOVED — PHYS_GSP_CAP
        ; ($1000) already bounds launches; if launches ever feel
        ; truncated, the knob is PHYS_GSP_CAP, coupled to CAM_MAX_Y_STEP,
        ; VFILL_ROWS_PER_FRAME, and the 32px sensor reach. Do not
        ; re-add silently.
        move.w  d0, SST_y_vel(a0)

        ; --- 5. airborne angle decay: 2/frame toward 0, both directions
        ; (research §3 end). Angles here are always even (the odd-flag
        ; sensors substitute cardinals), so ±2 lands exactly on 0 ---
        move.b  SST_angle(a0), d0
        beq.s   .angle_done
        bpl.s   .angle_pos
        addq.b  #2, d0
        bra.s   .angle_set
.angle_pos:
        subq.b  #2, d0
.angle_set:
        move.b  d0, SST_angle(a0)
.angle_done:

        ; --- 6. collision by motion class. |x_vel| vs |y_vel| compare +
        ; signs ≡ the classic CalcAngle(x_vel,y_vel)−$20 & $C0 quadrant
        ; for non-boundary vectors (each class spans the ±45° cone
        ; around its axis). On the exact 45° diagonals (|x| == |y|) the
        ; classic's octant boundaries split asymmetrically per CalcAngle
        ; rounding; our tie rule: ties go to the VERTICAL class, so the
        ; down class keeps landing authority on perfect diagonal
        ; launches ---
        move.w  SST_x_vel(a0), d1
        bpl.s   .ax_pos
        neg.w   d1
.ax_pos:
        move.w  SST_y_vel(a0), d2
        bpl.s   .ay_pos
        neg.w   d2
.ay_pos:
        cmp.w   d2, d1                          ; |x_vel| − |y_vel|
        bls.s   .vertical
        tst.w   SST_x_vel(a0)
        bmi.s   .mostly_left

        ; --- mostly RIGHT: right wall → ceiling bump → flat-rule floor ---
        bsr.w   Air_WallProbeRight
        tst.w   d4
        beq.s   .right_no_wall
        ; wall-run engage (classic HitRightWall): gsp picks up the fall
        ; speed so a wall-quadrant attach can continue the motion
        move.w  SST_y_vel(a0), _pl_gsp(a0)
.right_no_wall:
        bsr.w   Air_CeilingBump
        bra.w   Air_FloorLandFlat

.mostly_left:
        bsr.w   Air_WallProbeLeft
        tst.w   d4
        beq.s   .left_no_wall
        move.w  SST_y_vel(a0), _pl_gsp(a0)
.left_no_wall:
        bsr.w   Air_CeilingBump
        bra.w   Air_FloorLandFlat

.vertical:
        tst.w   SST_y_vel(a0)
        bmi.s   .mostly_up
        ; --- mostly DOWN: both walls, then banded floor landing ---
        bsr.w   Air_WallProbeLeft
        bsr.w   Air_WallProbeRight
        bra.w   Air_FloorLandBanded

.mostly_up:
        ; --- mostly UP: both walls, then ceiling — bump or reattach ---
        bsr.w   Air_WallProbeLeft
        bsr.w   Air_WallProbeRight
        jsr     Player_SensorCeiling            ; d0 dist, d1 angle (slanted
                                                ; ceiling angles pass through
                                                ; — the wrapper substitutes a
                                                ; cardinal only on odd flags)
        tst.w   d0
        bpl.s   .up_done                        ; clear of the ceiling
        move.b  d1, d3                          ; ceiling angle
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        sub.l   d0, SST_y_pos(a0)               ; up-probe dist < 0 = head
                                                ; embedded → snap DOWN (the
                                                ; opposite of the floor snap)
        ; flat-ceiling band → head bump; steeper ceiling slope while
        ; moving mostly up → reattach grounded. Band test is the classic
        ; (angle+$20)&$40: zero for angles $60-$9F — the flat-ceiling
        ; range of the feel-modern §1 landing table (91°-225°, hex
        ; $60-$A0); nonzero = steep ceiling slope ($20-$5F / $A0-$DF)
        move.b  d3, d0
        addi.b  #$20, d0
        andi.b  #$40, d0
        bne.s   .reattach
        clr.w   SST_y_vel(a0)                   ; bump (y_vel < 0 in this class)
.up_done:
        rts
.reattach:
        ; research §2 "Ceiling contact": gsp = ±y_vel by the angle's
        ; sign bit, angle = ceiling angle, grounded. y_vel survives —
        ; the next ground frame's projection rebuilds both velocities
        ; from gsp, preserving the upward motion along the surface
        move.b  d3, SST_angle(a0)
        bclr    #ST_PUSHING, SST_status(a0)
        bsr.w   Air_GspFromYvel
        moveq   #PSTATE_GROUND, d0
        jmp     Player_SetState

; -----------------------------------------------
; Air_FloorLandBanded — down-class floor landing with the classic angle
; banding (research physics-classics §2 "Landing", S2 s2.asm:37570-37613;
; S3K is byte-identical — axis-select, NOT vector projection)
; In:  a0 = player SST
; Out: none (transitions to PSTATE_GROUND on landing)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Air_FloorLandBanded:
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        tst.w   d0
        bpl.s   .no_land                        ; must be embedded to land
        ; eligibility: dist ≥ −(y_vel>>8) − 8 — embed tolerance scales
        ; with fall speed; prevents snagging walls as floors (spec §6)
        move.w  SST_y_vel(a0), d2
        lsr.w   #8, d2
        addq.w  #8, d2
        neg.w   d2
        cmp.w   d2, d0
        blt.s   .no_land                        ; too deep — keep falling
        move.b  d1, d3                          ; floor angle for the bands
        bsr.w   Air_TouchFloor
        ; band select on d3 (classic mask tests):
        ;   steep ±$20-$3F: (d3+$20)&$40 ≠ 0
        ;   mid   ±$10-$1F: (d3+$10)&$20 ≠ 0
        ;   flat  ±$00-$0F: neither
        move.b  d3, d0
        addi.b  #$20, d0
        andi.b  #$40, d0
        bne.s   .steep
        move.b  d3, d0
        addi.b  #$10, d0
        andi.b  #$20, d0
        bne.s   .mid
        ; flat: full conversion to the ground axis
        move.w  SST_x_vel(a0), _pl_gsp(a0)
        clr.w   SST_y_vel(a0)
        bra.s   .grounded
.mid:
        ; halve the fall speed, convert by angle sign. x_vel and the
        ; halved y_vel are left as-is — the next ground frame's
        ; projection overwrites both from gsp (classic)
        asr.w   SST_y_vel(a0)
        bsr.s   Air_GspFromYvel
        bra.s   .grounded
.steep:
        clr.w   SST_x_vel(a0)
        ; landing-conversion fall cap $FC0 — part of the classic steep
        ; conversion, NOT the removed airborne up-cap (that one is the
        ; FEEL DEVIATION note in PState_AirShared)
        cmpi.w  #$FC0, SST_y_vel(a0)
        ble.s   .steep_capped
        move.w  #$FC0, SST_y_vel(a0)
.steep_capped:
        bsr.s   Air_GspFromYvel
.grounded:
        moveq   #PSTATE_GROUND, d0              ; curled states uncurl in
                                                ; the GROUND enter hook;
                                                ; roll landings are Task 7
        jmp     Player_SetState
.no_land:
        rts

; -----------------------------------------------
; Air_FloorLandFlat — horizontal-class floor landing: gsp = x_vel
; regardless of slope (classic Sonic_HitFloor, s2.asm:37641-37654);
; requires falling (y_vel ≥ 0) and an embedded floor hit
; In:  a0 = player SST
; Out: none (transitions to PSTATE_GROUND on landing)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Air_FloorLandFlat:
        tst.w   SST_y_vel(a0)
        bmi.s   .no_land                        ; rising — can't land
        jsr     Player_SensorFloor
        tst.w   d0
        bpl.s   .no_land
        bsr.s   Air_TouchFloor
        move.w  SST_x_vel(a0), _pl_gsp(a0)
        clr.w   SST_y_vel(a0)
        moveq   #PSTATE_GROUND, d0
        jmp     Player_SetState
.no_land:
        rts

; -----------------------------------------------
; Air_TouchFloor — snap onto the floor surface + landing housekeeping
; In:  a0 = player SST, d0.w = floor dist (< 0), d1.b = resolved angle
; Out: none
; Clobbers: d0
; -----------------------------------------------
Air_TouchFloor:
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        add.l   d0, SST_y_pos(a0)
        move.b  d1, SST_angle(a0)
        bclr    #ST_PUSHING, SST_status(a0)
        rts

; -----------------------------------------------
; Air_GspFromYvel — gsp = ±y_vel by the surface angle's sign bit
; (classic shared landing/reattach rule, s2.asm:37608-37612). Direction
; check under our angle convention (positive angle = surface descending
; rightward): falling (+y_vel) onto steep +$30 → gsp = +y_vel =
; rightward = downhill; onto −$30 (bit7 set) → gsp = −y_vel = leftward
; = downhill. Rising (−y_vel) into ceiling slope $40 → gsp = y_vel
; (negative), projection sin($40)·gsp re-yields the upward motion.
; In:  a0 = player SST, d3.b = surface angle
; Out: none
; Clobbers: d0
; -----------------------------------------------
Air_GspFromYvel:
        move.w  SST_y_vel(a0), d0
        tst.b   d3
        bpl.s   .store
        neg.w   d0
.store:
        move.w  d0, _pl_gsp(a0)
        rts

; -----------------------------------------------
; Air_WallProbeRight / Air_WallProbeLeft — post-move airborne push-out
; at (x ± PUSH_RADIUS, y). On a hit (dist < 0): snap |dist| back out of
; the wall and kill x_vel (classic: every airborne class zeroes x_vel
; on a wall hit, regardless of motion direction)
; In:  a0 = player SST
; Out: d4.w = 0 no hit / −1 hit (the horizontal classes use it to
;      engage the wall-run gsp)
; Clobbers: d0-d6, a1
; -----------------------------------------------
Air_WallProbeRight:
        move.w  SST_x_pos(a0), d0
        addi.w  #PUSH_RADIUS, d0
        move.w  SST_y_pos(a0), d1
        moveq   #1, d4                          ; probe rightward
        jsr     Player_SensorWallAt
        tst.w   d0
        bpl.s   .no_hit
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        add.l   d0, SST_x_pos(a0)               ; dist < 0 → pushes left
        clr.w   SST_x_vel(a0)
        moveq   #-1, d4
        rts
.no_hit:
        moveq   #0, d4
        rts

Air_WallProbeLeft:
        move.w  SST_x_pos(a0), d0
        subi.w  #PUSH_RADIUS, d0
        move.w  SST_y_pos(a0), d1
        moveq   #-1, d4                         ; probe leftward
        jsr     Player_SensorWallAt
        tst.w   d0
        bpl.s   .no_hit
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16 (along −X)
        sub.l   d0, SST_x_pos(a0)               ; dist < 0 → pushes right
        clr.w   SST_x_vel(a0)
        moveq   #-1, d4
        rts
.no_hit:
        moveq   #0, d4
        rts

; -----------------------------------------------
; Air_CeilingBump — horizontal-class ceiling check: snap out + kill
; upward velocity. No reattach outside the mostly-up class (classic)
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Air_CeilingBump:
        jsr     Player_SensorCeiling
        tst.w   d0
        bpl.s   .clear
        ext.l   d0
        swap    d0
        clr.w   d0                              ; dist<<16
        sub.l   d0, SST_y_pos(a0)               ; embedded → snap DOWN
        tst.w   SST_y_vel(a0)
        bpl.s   .clear
        clr.w   SST_y_vel(a0)
.clear:
        rts
