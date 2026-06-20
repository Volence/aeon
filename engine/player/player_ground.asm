; Player grounded states — PState_Ground (slope factor, quadrant-rotated
; floor adherence, S3K slip), PState_Roll (rolling physics; shares the
; cap/projection/probe via Ground_Move.cap and the movement tail via
; Ground_PostMove), + Player_Jump. PState_Spindash lives in sonic.asm
; (character state). Player_Jump lives in this file because it is
; invoked only from grounded states (its tail jumps into the air body in
; player_air.asm — the bug #4 press-frame fix). Reached only through the
; Player_States offset table in player_common.asm; shares its overlay
; equates, macros, and the (a4) physics-table convention.
;
; Lives in the object code bank, included from main.asm immediately
; after player_common.asm.

    if PHYS_SLOPE_WALK <> $20
        error "slope-factor shift form (sin asr 3) assumes PHYS_SLOPE_WALK = $20"
    endif
    if PHYS_SLOPE_ROLL_DOWN <> $50
        error "roll slope-factor shift form (5·sin asr 4) assumes PHYS_SLOPE_ROLL_DOWN = $50"
    endif
    if PHYS_SLOPE_ROLL_UP <> $14
        error "roll uphill factor (downhill asr 2) assumes PHYS_SLOPE_ROLL_UP = $14"
    endif

; -----------------------------------------------
; PState_Ground — standing/running. Classic frame order (research
; physics-classics §1): spindash check → jump check → slope factor →
; input/projection/wall probe (Ground_Move) → roll start check →
; integrate → floor pair snap → slip check (fall-through into
; Player_SlopeRepel).
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to PSTATE_AIR/ROLL/SPINDASH or jump)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Ground:
        ; --- spindash trigger (classic order: FIRST — a down+jump press
        ; while near-stationary charges instead of jumping). S2's gate is
        ; "ducking" (down held at ~rest); we have no duck state, so the
        ; gate is down held + |gsp| < PHYS_ROLL_START_MIN — the same
        ; threshold that separates duck from roll in S3K. At rolling
        ; speed the press falls through to the jump check instead. ---
        btst    #1, (Ctrl_1_Held).w             ; DOWN held
        beq.s   .no_spindash
        tst.b   (Player_JumpBuffer).w
        beq.s   .no_spindash
        move.w  _pl_gsp(a0), d0
        bpl.s   .sd_abs
        neg.w   d0
.sd_abs:
        cmpi.w  #PHYS_ROLL_START_MIN, d0
        bge.s   .no_spindash
        clr.b   (Player_JumpBuffer).w           ; consume — this press is rev 0
        moveq   #PSTATE_SPINDASH, d0
        bsr.w   Player_SetState                 ; hook curls + zeroes motion/charge
        jmp     PState_Spindash                 ; run the charge frame now —
                                                ; the floor pair keeps running
                                                ; (sonic.asm). Rev SFX fired per-tap in player_spindash.asm
.no_spindash:
        ; --- jump check (classic order: after spindash, before slope/
        ; input). Player_JumpBuffer covers fresh press AND buffered —
        ; latched on the press edge in Player_Main; consumed only on a
        ; successful launch, so a headroom rejection leaves it live and
        ; the classic retry happens next frame while the buffer lasts ---
        tst.b   (Player_JumpBuffer).w
        beq.s   .no_jump
        jsr     Player_SensorCeiling            ; headroom: d0 = clearance
                                                ; (≥16 sentinel = open sky)
        cmpi.w  #PHYS_JUMP_HEADROOM, d0
        bge.w   Player_Jump                     ; classic CalcRoomOverHead
                                                ; ≥6px rule; does not return
.no_jump:
        ; --- slope factor on gsp — BEFORE input, with LAST frame's angle
        ; (classic Sonic_SlopeResist, research physics-classics §2).
        ; Applied on floor and both wall quadrants; skipped in the
        ; ceiling band: apply only when (angle+$60)&$FF < $C0 unsigned
        ; (band $60-$9F skips). Ground_Move's ±PHYS_GSP_CAP runs after
        ; this AND after input, so the cap bounds the post-slope sum.
        ; (ROLL applies its own $50/$14 asymmetric factor — PState_Roll.) ---
        move.b  SST_angle(a0), d0
        beq.s   .no_slope                       ; flat: factor 0 (fast path)
        move.b  d0, d1
        addi.b  #$60, d1
        cmpi.b  #$C0, d1
        bhs.s   .no_slope                       ; ceiling band $60-$9F
        jsr     GetSineCosine                   ; d0.w = sin(angle)·$100
        asr.w   #3, d0                          ; factor = ($20·sin)>>8 ≡
                                                ; sin asr 3 — exact, no muls
                                                ; (PHYS_SLOPE_WALK = 2^5,
                                                ; asserted at file top)
        tst.w   _pl_gsp(a0)
        bne.s   .slope_apply
        ; S3K standing gate: from rest, only slopes steep enough to beat
        ; the minimum start a slide (|factor| ≥ $D ≈ asin(13/32) ≈ 24°);
        ; shallower slopes hold the player still — no micro-creep
        move.w  d0, d1
        bpl.s   .factor_abs
        neg.w   d1
.factor_abs:
        cmpi.w  #PHYS_SLOPE_STAND_MIN, d1
        blt.s   .no_slope
.slope_apply:
        add.w   d0, _pl_gsp(a0)
.no_slope:
        bsr.w   Ground_Move
        ; --- roll start (the classic Sonic_Roll slot: after Move, before
        ; integration — this frame already moved with standing semantics,
        ; exactly like the classics): down held, L/R NOT held (raw bits —
        ; any sideways intent vetoes the curl), |gsp| ≥ $100 (S3K
        ; threshold). Forced rolls (S-tunnel objects) are a future object
        ; contract: they bypass this gate and use PHYS_ROLL_FORCE_MIN
        ; ($200) when curling at rest — see PState_Roll's keep-roll note.
        move.b  (Ctrl_1_Held).w, d0
        btst    #1, d0                          ; DOWN
        beq.s   Ground_PostMove
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, d0
        bne.s   Ground_PostMove
        move.w  _pl_gsp(a0), d0
        bpl.s   .roll_abs
        neg.w   d0
.roll_abs:
        cmpi.w  #PHYS_ROLL_START_MIN, d0
        blt.s   Ground_PostMove
        moveq   #PSTATE_ROLL, d0
        bsr.w   Player_SetState                 ; hook curls (+5px y-shift)
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_ROLL, d0
        jsr     Sound_PlaySFX
      endif
        ; fall through — the frame completes below as a roll

; -----------------------------------------------
; Ground_PostMove — shared grounded movement tail: integrate → floor
; pair snap → slip check (falls through into Player_SlopeRepel).
; Entered by falling through from PState_Ground and by PState_Roll's
; tail branch (and via it the unroll/keep-rolling paths). NOT a
; subroutine — control returns to Player_Main's dispatch.
; In:  a0 = player SST (x_vel/y_vel projected by Ground_Move)
; Out: none (may transition to PSTATE_AIR/AIRBALL via Ground_DetachState)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Ground_PostMove:
        jsr     ObjectMove

        ; --- on-object: the player is grounded on a solid object (set by
        ; LAST tick's TouchResponse, still live this frame — Player_Main
        ; clears it AFTER dispatch). The object holds our Y/position, so
        ; skip BOTH the terrain floor pair AND SlopeRepel: a floor pair
        ; here finds no terrain under us and detaches to AIR (the bug).
        ; Force angle 0 (flat object top) and return to the dispatch — the
        ; same exit point SlopeRepel's rts reaches. GROUND and ROLL share
        ; this tail; ROLL's unroll check runs in PState_Roll BEFORE here,
        ; so rolling-to-stop on the object still uncurls. ---
        btst    #ST_ON_OBJECT, SST_status(a0)
        beq.s   .terrain
        clr.b   SST_angle(a0)
        rts
.terrain:

        ; --- floor pair: quadrant-rotated probe, snap along the probe
        ; axis, angle update, ledge detach. Angle continuity: the pair
        ; wrapper already substitutes the quadrant cardinal on the odd
        ; flag OR |Δangle| ≥ $20 — that IS the "reject angle jumps > $20
        ; between frames" loop fall-through guard; nothing more needed
        ; at this site. ---
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        ; adaptive snap-down window: min(|speed along probe axis|>>8 + 4,
        ; 14) — S2+ rule (research feel-modern §2): Y-probe modes
        ; (quadrant 0/2) use x_vel, X-probe wall modes (1/3) use y_vel
        move.w  SST_x_vel(a0), d2
        btst    #0, (Player_Quadrant).w         ; sets Z only — N at
        beq.s   .axis_sel                       ; .axis_sel is still the
        move.w  SST_y_vel(a0), d2               ; loaded value's sign on
.axis_sel:                                      ; both paths
        bpl.s   .speed_pos
        neg.w   d2
.speed_pos:
        lsr.w   #8, d2
        addq.w  #4, d2
        cmpi.w  #14, d2
        bls.s   .window_ok
        moveq   #14, d2
.window_ok:
        cmpi.w  #-14, d0
        blt.s   .no_snap                        ; embedded past the fixed
                                                ; snap-up — classic ignores
        tst.b   _pl_stick_convex(a0)
        bne.s   .snap                           ; full adherence: snap-down
                                                ; window bypassed (research
                                                ; physics-classics §7)
        cmp.w   d2, d0
        ble.s   .snap
        ; surface beyond snap reach — covers both-sensors-nothing (≥16
        ; sentinel) and a ledge run-off. Velocities kept — gravity takes
        ; over next frame. Roll-aware: a roll-off stays curled (AIRBALL),
        ; spec §3.3 / verification matrix item 7
        bra.w   Ground_DetachState              ; does not return
.snap:
        bsr.w   Player_SnapToSurface            ; probe-axis snap per
                                                ; quadrant (helper mirrors
                                                ; the sensor case table;
                                                ; clobbers d0/d2 — d1 angle
                                                ; survives)
        move.b  d1, SST_angle(a0)
.no_snap:
        ; fall through — classic order step 9. SEAM GUARD: this
        ; fall-through is shared by GROUND and ROLL (both reach it via
        ; Ground_PostMove — roll uses the same slip rules, classic).
        ; Player_SlopeRepel must stay IMMEDIATELY below, and nothing
        ; state-specific may be inserted here. SPINDASH deliberately
        ; never reaches this seam (its floor maintenance lives in
        ; PState_Spindash — the classics skip SlopeRepel while charging).

; -----------------------------------------------
; Player_SlopeRepel — S3K slip/detach (research physics-classics §7
; "S3K slip rework", feel-modern §1 Slopes). Runs ONLY via the grounded
; fall-through above. move_lock semantics: the lock ticks down HERE —
; grounded frames only, frozen while airborne; while nonzero the slip
; check is skipped entirely this frame (Ground_Move separately skips
; INPUT — friction and slope factor still run).
;   band:   slip when angle is ≥ $18 from flat either way —
;           (angle+$18)&$FF ≥ $30 — AND |gsp| < $280
;   slip:   gsp ±= $80 shoved downhill, move_lock = 30 (gsp NOT zeroed)
;   detach: additionally when (angle+$30)&$FF ≥ $60 (≈ |angle| ≥ $30)
;           → Ground_DetachState (AIR, or AIRBALL from a roll) with gsp
;           kept (S3K "slide, don't fall")
; In:  a0 = player SST
; Out: none (may transition to PSTATE_AIR/AIRBALL)
; Clobbers: d0-d1 (+ Player_SetState tail clobbers on detach)
; -----------------------------------------------
Player_SlopeRepel:
        move.w  _pl_move_lock(a0), d0
        beq.s   .lock_idle
        subq.w  #1, d0
        move.w  d0, _pl_move_lock(a0)
        rts
.lock_idle:
        tst.b   _pl_stick_convex(a0)
        bne.s   .done                           ; loop adherence: no slip
        move.b  SST_angle(a0), d0
        addi.b  #PHYS_SLIP_ANGLE, d0
        cmpi.b  #PHYS_SLIP_ANGLE*2, d0
        blo.s   .done                           ; inside the flat band ±$17
        move.w  _pl_gsp(a0), d1
        bpl.s   .speed_abs
        neg.w   d1
.speed_abs:
        cmpi.w  #PHYS_SLIP_SPEED, d1
        bge.s   .done                           ; fast enough to hold on
        ; downhill nudge: sign = sign of sin(angle). Under our convention
        ; positive sin (angle bit 7 clear) = right-descending surface →
        ; downhill is +gsp; bit 7 set mirrors. sin ≥ 0 exactly on 0-$80,
        ; and the flat band already excluded |angle| < $18, so bit 7 is
        ; a faithful sign proxy across the whole slip band
        move.w  #PHYS_SLIP_NUDGE, d1
        tst.b   SST_angle(a0)
        bpl.s   .nudge
        neg.w   d1
.nudge:
        add.w   d1, _pl_gsp(a0)
        move.w  #PHYS_MOVE_LOCK_TIME, _pl_move_lock(a0)
        ; moderate band ($18-$2F from flat) slides grounded; detach only
        ; when steeper
        move.b  SST_angle(a0), d0
        addi.b  #PHYS_FALL_ANGLE, d0
        cmpi.b  #PHYS_FALL_ANGLE*2, d0
        blo.s   .done
        bra.s   Ground_DetachState              ; roll-aware (gsp kept — S3K
                                                ; "slide, don't fall")
.done:
        rts

; -----------------------------------------------
; Ground_DetachState — the ONE decision for leaving the ground without
; a jump (mirrors Air_LandState's one-decision pattern, from the other
; side of the seam): detaching from ROLL stays curled → PSTATE_AIRBALL
; (spec §3.3 state table — rolled off a ledge keeps ST_ROLLING and the
; ball box; Task 9's path swap reads ST_ROLLING for curled detection,
; and uncurling here would skip the clearance check — the wall-clip
; hazard class); detaching from GROUND → PSTATE_AIR. Keyed on
; _pl_state, the transition authority, rather than ST_ROLLING — same
; cost (one byte compare), and it names the exact state this seam can
; carry. SPINDASH never reaches either call site (its body skips
; Ground_PostMove/SlopeRepel entirely — see the seam guard above), so
; GROUND/ROLL is the complete case split. The AIRBALL enter hook
; (PHook_EnsureBall) is idempotent — curled→curled is a no-op.
; Called from: Ground_PostMove (run-off / both-sensors-nothing) and
; Player_SlopeRepel (steep-slope detach).
; In:  a0 = player SST (_pl_state = PSTATE_GROUND or PSTATE_ROLL)
; Out: DOES NOT return — tail-jumps Player_SetState with d0 = the
;      detach state; control returns to Player_Main's dispatch
; Clobbers: d0 (+ Player_SetState tail clobbers)
; -----------------------------------------------
Ground_DetachState:
        moveq   #PSTATE_AIR, d0
        cmpi.b  #PSTATE_ROLL, _pl_state(a0)
        bne.s   .set
        moveq   #PSTATE_AIRBALL, d0
.set:
        jmp     Player_SetState

; -----------------------------------------------
; PState_Roll — grounded, curled. Classic Obj01_MdRoll order (research
; physics-classics §1): jump check (→ ROLLJUMP via Player_Jump) → roll
; slope factor ($50 downhill / $14 uphill) → roll speed (friction
; always, $20 fixed brake, NO input accel) → unroll check → shared
; cap/projection/wall probe (Ground_Move.cap) → shared movement tail
; (Ground_PostMove: integrate → floor pair → SlopeRepel fall-through —
; rolling slips and detaches by the same rules as walking).
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to GROUND/ROLLJUMP/AIRBALL — a roll-off or
;      steep detach stays curled via Ground_DetachState)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Roll:
        ; --- jump check — same gate as PState_Ground. Player_Jump reads
        ; _pl_state and launches into ROLLJUMP from here (air-control
        ; lockout); ball radii are KEPT by the hooks — bug #5 fix is
        ; structural, no size pop on a roll-jump ---
        tst.b   (Player_JumpBuffer).w
        beq.s   .no_jump
        jsr     Player_SensorCeiling            ; d0 = headroom
        cmpi.w  #PHYS_JUMP_HEADROOM, d0
        bge.w   Player_Jump                     ; does not return
.no_jump:
        ; --- roll slope factor (classic Sonic_RollRepel): $50·sin>>8,
        ; quartered to $14·sin>>8 when the factor's sign opposes gsp
        ; (rolling uphill). NEVER gsp==0-gated (research §2) — gsp == 0
        ; counts as positive, the exact classic sign test. Same ceiling-
        ; band skip as walking. Shift forms (no muls): 5·sin asr 4 ≡
        ; ($50·sin)>>8 exactly, one more asr 2 ≡ ($14·sin)>>8 exactly —
        ; consecutive arithmetic shifts compose; constants asserted at
        ; file top ---
        move.b  SST_angle(a0), d0
        beq.s   .no_slope                       ; flat: factor 0 (fast path)
        move.b  d0, d1
        addi.b  #$60, d1
        cmpi.b  #$C0, d1
        bhs.s   .no_slope                       ; ceiling band $60-$9F
        jsr     GetSineCosine                   ; d0.w = sin(angle)·$100
        move.w  d0, d1
        asl.w   #2, d0
        add.w   d1, d0                          ; 5·sin (≤ ±$500 — no overflow)
        asr.w   #4, d0                          ; downhill factor ($50 form)
        tst.w   _pl_gsp(a0)
        bmi.s   .gsp_neg
        tst.w   d0
        bpl.s   .slope_apply
        bra.s   .uphill
.gsp_neg:
        tst.w   d0
        bmi.s   .slope_apply
.uphill:
        asr.w   #2, d0                          ; quartered ($14 form)
.slope_apply:
        add.w   d0, _pl_gsp(a0)
.no_slope:
        ; --- roll speed: NO input accel ever. Opposing direction = $20
        ; FIXED brake (PHYS_ROLL_DECEL — the classic uses the constant,
        ; NOT decel/4 of the live stat; research §5), crossing zero under
        ; the brake kicks ∓$80 like walking. Friction = walk friction/2
        ; ($6) ALWAYS, even holding forward — read through the phys table
        ; so future water/shoes modifiers compose ($3 underwater, the
        ; classic value). Brake + friction stack: $26/frame opposing.
        ; move_lock freezes the input (brake/facing) only — friction and
        ; the slope factor still run (S3K, same as walking) ---
        move.w  _pl_gsp(a0), d0
        tst.w   _pl_move_lock(a0)
        bne.s   .friction
        move.b  (Ctrl_1_Held).w, d2
        maskOpposingLR d2
        tst.w   d0
        beq.s   .friction                       ; no motion — nothing to brake
        bmi.s   .moving_left
        btst    #2, d2                          ; LEFT opposes rightward roll
        bne.s   .brake_left
        btst    #3, d2                          ; RIGHT with the motion:
        beq.s   .friction                       ; facing only (classic
        bclr    #ST_XFLIP, SST_status(a0)       ; Obj01_RollRight)
        bra.s   .friction
.brake_left:
        subi.w  #PHYS_ROLL_DECEL, d0
        bcc.s   .friction                       ; borrow = crossed zero
        moveq   #-$80, d0                       ; turnaround kick
        bra.s   .friction
.moving_left:
        btst    #3, d2                          ; RIGHT opposes leftward roll
        bne.s   .brake_right
        btst    #2, d2
        beq.s   .friction
        bset    #ST_XFLIP, SST_status(a0)       ; facing only (classic)
        bra.s   .friction
.brake_right:
        addi.w  #PHYS_ROLL_DECEL, d0
        bcc.s   .friction                       ; carry = crossed zero
        move.w  #$80, d0                        ; (+$80 exceeds moveq range)
.friction:
        move.w  PPHYS_FRICTION(a4), d1
        asr.w   #1, d1                          ; roll friction = friction/2
        tst.w   d0
        beq.s   .unroll_check
        bmi.s   .fric_neg
        sub.w   d1, d0
        bcc.s   .unroll_check
        moveq   #0, d0                          ; crossed zero → stop
        bra.s   .unroll_check
.fric_neg:
        add.w   d1, d0
        bcc.s   .unroll_check
        moveq   #0, d0

.unroll_check:
        ; --- unroll below |gsp| < $80 (S3K). The standing box is 5px
        ; taller per radius and uncurling lifts the center 5px, so the
        ; head rises (PLAYER_Y_RADIUS-BALL_Y_RADIUS)+CURL_Y_SHIFT = 10px
        ; — unrolling under a low ceiling would clip into it (spec §5
        ; wall-clip class). Verify clearance first; blocked → KEEP
        ; ROLLING at ±PHYS_KEEP_ROLL_MIN (classic Sonic_KeepRolling's
        ; forced inertia = ±$400, the roll-tunnel rule reused for the
        ; blocked-unroll case; sign of gsp, rest counts positive) ---
        move.w  d0, _pl_gsp(a0)                 ; bank gsp — the ceiling
                                                ; sensor below clobbers d0
        move.w  d0, d1
        bpl.s   .uabs
        neg.w   d1
.uabs:
        cmpi.w  #PHYS_UNROLL_MAX, d1
        bge.s   .shared_move                    ; d0 = gsp, still rolling
        jsr     Player_SensorCeiling            ; d0 = head clearance (ball box)
        cmpi.w  #(PLAYER_Y_RADIUS-BALL_Y_RADIUS)+CURL_Y_SHIFT, d0
        blt.s   .keep_rolling
        moveq   #PSTATE_GROUND, d0              ; unroll — the hook restores
        bsr.w   Player_SetState                 ; standing radii, −5px y-shift
        move.w  _pl_gsp(a0), d0
        bra.s   .shared_move                    ; frame completes as GROUND
                                                ; from the cap (wall probe
                                                ; picks standing offsets off
                                                ; the new state)
.keep_rolling:
        move.w  #PHYS_KEEP_ROLL_MIN, d0
        tst.w   _pl_gsp(a0)
        bpl.s   .shared_move
        neg.w   d0
.shared_move:
        bsr.w   Ground_Move.cap                 ; shared cap → projection →
                                                ; wall probe (see the entry-
                                                ; point note at .cap; the
                                                ; probe raises −5px while
                                                ; _pl_state == ROLL)
        bra.w   Ground_PostMove                 ; integrate → floor pair →
                                                ; SlopeRepel fall-through

; -----------------------------------------------
; Ground_Move — input → ground_speed, projection, ground wall probe
; Classic accel/decel/friction semantics with the S3K back-out top-speed
; rule and the turnaround kick (research physics-classics §1).
; In:  a0 = player SST, a4 = Player_Phys
; Out: none
; Clobbers: d0-d7, a1
; -----------------------------------------------
Ground_Move:
        move.w  _pl_gsp(a0), d0
        tst.w   _pl_move_lock(a0)
        bne.s   .friction                       ; slip/spring input freeze:
                                                ; friction still runs (S3K);
                                                ; the decrement lives in
                                                ; Player_SlopeRepel
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
        ; ENTRY POINT — PState_Roll bsr's here with d0 = its post-friction
        ; gsp (also after its unroll/keep-rolling paths). Everything from
        ; the cap through the wall probe is shared between walking and
        ; rolling; do not reorder, and any walk-only addition below must
        ; be gated on _pl_state.
        ; GSp tunneling guard ±$1000, applied after slope factor (added
        ; to gsp in PState_Ground/PState_Roll before this point) AND
        ; after input.
        ; FEEL DEVIATION coupling (spec §2.1): raising it requires
        ; CAM_MAX_Y_STEP, VFILL_ROWS_PER_FRAME, and sensor reach to rise
        ; together.
        cmpi.w  #PHYS_GSP_CAP, d0
        ble.s   .cap_pos_ok
        move.w  #PHYS_GSP_CAP, d0
.cap_pos_ok:
        cmpi.w  #-PHYS_GSP_CAP, d0
        bge.s   .cap_neg_ok
        move.w  #-PHYS_GSP_CAP, d0
.cap_neg_ok:
        move.w  d0, _pl_gsp(a0)
        move.w  d0, d4                          ; capped gsp rides to the wall
                                                ; probe in d4 — survives both
                                                ; projection paths (GetSineCosine
                                                ; clobbers d0/d1 only)

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
        ; --- ground wall probe at the next-frame position, in the
        ; quadrant-relative "ahead" direction (the quadrant form of the
        ; classic angle±$40 CalcRoomInFront probe). S3K gates (research
        ; physics-classics §1): skip when the angle is a NON-cardinal in
        ; the upper half $41-$BF — no false wall hits on steep curved
        ; terrain / no pushing on loop tops; exact cardinals stay
        ; enabled (feel-modern §2 "disabled outside −90°..90°,
        ; re-enabled at exact multiples of 90°") ---
        tst.w   d4                              ; capped gsp from .cap —
        beq.s   .clear_push                     ; probe direction sign
        move.b  SST_angle(a0), d1
        move.b  d1, d2
        andi.b  #$3F, d2
        beq.s   .gate_ok                        ; exact cardinal: always probe
        addi.b  #$40, d1
        bmi.s   .clear_push                     ; non-cardinal upper half
.gate_ok:
        ; "ahead" per quadrant — derived from the projection at the
        ; cardinals (x_vel = cos·gsp, y_vel = sin·gsp): gsp>0 moves
        ; right/down/left/up in quadrants 0/1/2/3; gsp<0 mirrors
        moveq   #0, d2
        move.b  (Player_Quadrant).w, d2
        tst.w   d4
        bpl.s   .dir_fwd
        addq.w  #4, d2
.dir_fwd:
        lea     .dir_table(pc), a1              ; (beyond d8(pc,Xn) reach)
        move.b  (a1,d2.w), d7                   ; probe-core direction code
                                                ; (0/1/2/3 = down/up/right/
                                                ; left) — d7 survives the
                                                ; sensor call
        move.w  SST_x_vel(a0), d0
        asr.w   #8, d0
        add.w   SST_x_pos(a0), d0               ; projected engine X
        move.w  SST_y_vel(a0), d1
        asr.w   #8, d1
        add.w   SST_y_pos(a0), d1               ; projected engine Y
        cmpi.b  #PSTATE_ROLL, _pl_state(a0)
        bne.s   .not_rolling
        subq.w  #5, d1                          ; rolling: probe raised 5px —
                                                ; the curl shifted y_pos +5,
                                                ; so −5 restores the STANDING
                                                ; center height (SPG/spec §5;
                                                ; applies at every angle)
        bra.s   .probe_y_set
.not_rolling:
        tst.b   SST_angle(a0)
        bne.s   .probe_y_set
        addq.w  #8, d1                          ; foot-level probe ONLY at
                                                ; angle == 0 exactly (SPG:
                                                ; low steps push instead of
                                                ; snap-up; slopes/walls use
                                                ; center height)
.probe_y_set:
        move.w  d7, d2                          ; offset PUSH_RADIUS along
        subq.w  #2, d2                          ; the probe direction
        bmi.s   .off_vert                       ; 0/1 = probe along Y
        beq.s   .off_right
        subi.w  #PUSH_RADIUS, d0                ; 3: left
        bra.s   .probe_go
.off_right:
        addi.w  #PUSH_RADIUS, d0                ; 2: right
        bra.s   .probe_go
.off_vert:
        tst.w   d7
        bne.s   .off_up
        addi.w  #PUSH_RADIUS, d1                ; 0: down
        bra.s   .probe_go
.off_up:
        subi.w  #PUSH_RADIUS, d1                ; 1: up
.probe_go:
        move.w  d7, d2
        jsr     Player_SensorWallDir            ; d0 dist (d7 preserved)
        tst.w   d0
        bmi.s   .wall_hit
.clear_push:
        bclr    #ST_PUSHING, SST_status(a0)
        rts
.wall_hit:
        ; back the blocked distance into the velocity along the probe
        ; axis — the player advances exactly to the wall face this
        ; frame; inertia dies
        asl.w   #8, d0                          ; dist → 8.8
        move.w  d7, d2
        subq.w  #2, d2
        bmi.s   .cancel_vert
        beq.s   .cancel_right
        sub.w   d0, SST_x_vel(a0)               ; 3 left: dist<0 → vel rises
        bra.s   .gsp_kill                       ; toward zero
.cancel_right:
        add.w   d0, SST_x_vel(a0)
        bra.s   .gsp_kill
.cancel_vert:
        tst.w   d7
        bne.s   .cancel_up
        add.w   d0, SST_y_vel(a0)               ; 0 down
        bra.s   .gsp_kill
.cancel_up:
        sub.w   d0, SST_y_vel(a0)               ; 1 up
.gsp_kill:
        move.w  _pl_gsp(a0), d1                 ; sign needed below — nonzero
                                                ; (gated at .wall_probe)
        clr.w   _pl_gsp(a0)
        ; facing-aware push bit (S3K): only when facing the wall. Track-
        ; space rule, quadrant-independent: input→gsp mapping never
        ; rotates, so gsp>0 is always the "facing right" travel direction
        tst.w   d1
        bmi.s   .hit_back
        btst    #ST_XFLIP, SST_status(a0)
        bne.s   .clear_push                     ; moving fwd, facing away
        bra.s   .set_push
.hit_back:
        btst    #ST_XFLIP, SST_status(a0)
        beq.s   .clear_push
.set_push:
        bset    #ST_PUSHING, SST_status(a0)
        rts
.dir_table:
        dc.b    2, 0, 3, 1                      ; gsp>0: right/down/left/up
        dc.b    3, 1, 2, 0                      ; gsp<0: mirrored
        align 2

; -----------------------------------------------
; Player_Jump — launch from a grounded state (headroom already verified
; by the caller, buffer consumed here). Perpendicular ADD along the
; surface normal, angle − $40 (research §3): running speed is preserved
; — gsp is NOT zeroed, it's already projected into x_vel/y_vel.
; In:  a0 = player SST, a4 = Player_Phys
; Out: DOES NOT return to the ground flow — transitions to PSTATE_JUMP
;      (PSTATE_ROLLJUMP from a roll) and runs the air body THIS frame,
;      returning to Player_Main's dispatch.
;      bug #4 fix: the classic aborts the press frame with
;      `addq.l #4,sp` (no movement until the next frame); we complete
;      the frame airborne so movement happens on the press frame.
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
Player_Jump:
        clr.b   (Player_JumpBuffer).w           ; consume the buffered press
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_JUMP, d0
        jsr     Sound_PlaySFX
      endif
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
        ; leaving the object: clear on_object NOW so the same-frame air
        ; body (jmp PState_Jump below) does not see it still set and
        ; immediately "land" again, cancelling the jump. Touch_Solid won't
        ; re-set it while rising (.solid_top requires y_vel >= 0).
        bclr    #ST_ON_OBJECT, SST_status(a0)
        ; from a roll → ROLLJUMP (classic lockout: no air control; ball
        ; radii simply KEPT by the hooks — bug #5 fix is structural).
        ; SPINDASH never calls here (its body has no jump check).
        moveq   #PSTATE_JUMP, d0
        cmpi.b  #PSTATE_ROLL, _pl_state(a0)
        bne.s   .from_stand
        moveq   #PSTATE_ROLLJUMP, d0
.from_stand:
        bsr.w   Player_SetState                 ; preserves d0 (hook contract)
        ; bug #4 fix: run the full air body on the press frame — through
        ; the state's own preamble so ROLLJUMP locks input on this frame
        ; too
        cmpi.w  #PSTATE_ROLLJUMP, d0
        beq.w   PState_RollJump
        jmp     PState_Jump
