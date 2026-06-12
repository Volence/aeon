; Player frame skeleton — state machine, dispatch, shared movement (§5 Task 5)
;
; Owns the entire player frame: debug-fly escape → physics table (a4) →
; quadrant → jump buffer → state dispatch → history rings → display tail.
; Characters contribute asset/physics data + ability states (sonic.asm) —
; never forks inside shared routines (spec §3.1 inversion of the
; sonic_hack split).
;
; Lives in the object code bank: Player_Main is dispatched through
; SST_code_addr via objroutine().

; -----------------------------------------------
; SST overlay (research structure-refs §2.2 budget: 12 of 34 bytes)
; -----------------------------------------------
PlayerV struct
ground_speed     ds.w 1      ; inertia — single source of truth on ground
player_state     ds.b 1      ; PSTATE_* (jump-table byte offset)
status_secondary ds.b 1      ; reserved condition bits (speedshoes etc.) — 0 for now
move_lock        ds.w 1      ; input-freeze frames (slip/spring channel; Task 7 consumes)
spindash_charge  ds.w 1      ; Task 8
flip_angle       ds.b 1      ; reserved (visual rotation)
air_left         ds.b 1      ; reserved (no water yet)
invuln_time      ds.b 1      ; reserved
stick_convex     ds.b 1      ; flag: full terrain adherence (objects will set)
debug_flag       ds.b 1      ; nonzero = debug-fly (suspends state dispatch)
PlayerV endstruct
        objvarsCheck PlayerV_len
_pl_gsp          = SST_sst_custom+PlayerV_ground_speed
_pl_state        = SST_sst_custom+PlayerV_player_state
_pl_status2      = SST_sst_custom+PlayerV_status_secondary
_pl_move_lock    = SST_sst_custom+PlayerV_move_lock
_pl_spindash     = SST_sst_custom+PlayerV_spindash_charge
_pl_flip_angle   = SST_sst_custom+PlayerV_flip_angle
_pl_air_left     = SST_sst_custom+PlayerV_air_left
_pl_invuln       = SST_sst_custom+PlayerV_invuln_time
_pl_stick_convex = SST_sst_custom+PlayerV_stick_convex
_pl_debug        = SST_sst_custom+PlayerV_debug_flag

; (a4) physics-table offsets — movement code reads physics ONLY through
; these, never PHYS_* directly (per-section modifiers compose in
; Player_RefreshPhysics; spec §3.4)
PPHYS_ACCEL       = Phys_accel-Player_Phys
PPHYS_DECEL       = Phys_decel-Player_Phys
PPHYS_FRICTION    = Phys_friction-Player_Phys
PPHYS_TOP_SPEED   = Phys_top_speed-Player_Phys
PPHYS_GRAVITY     = Phys_gravity-Player_Phys
PPHYS_JUMP_FORCE  = Phys_jump_force-Player_Phys
PPHYS_AIR_ACCEL   = Phys_air_accel-Player_Phys
PPHYS_RELEASE_CAP = Phys_release_cap-Player_Phys

; Jump press sources: A and C only — B is the debug-fly toggle (joins
; this mask when debug-fly moves behind a build flag)
BUTTON_JUMP_MASK  = BUTTON_A|BUTTON_C

PLAYER_DEBUG_FLY_SPEED = 16     ; px/frame — matched to CAM_MAX_Y_STEP

; -----------------------------------------------
; Player_Init — set up a player slot as Sonic (called from level state
; init; caller writes x_pos/y_pos first). Boots in DEBUG-FLY to preserve
; the streaming-test workflow — B drops into physics.
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d1, a1-a2
; -----------------------------------------------
Player_Init:
        bsr.w   Sonic_InitAssets
        move.b  #1, SST_anim(a0)                ; idle (Player_Display re-selects per frame)
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        ori.b   #4<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        ; sizes are 2r+1; sensors halve by lsr → 19/2=9, 39/2=19 — the
        ; exact classic standing radii
        move.b  #PLAYER_X_RADIUS*2+1, SST_width_pixels(a0)
        move.b  #PLAYER_Y_RADIUS*2+1, SST_height_pixels(a0)
        move.b  #COLLISION_NONE, SST_collision_resp(a0)
        clr.b   SST_status(a0)
        clr.b   SST_angle(a0)
        clr.b   SST_layer(a0)
        clr.w   _pl_gsp(a0)
        clr.w   _pl_move_lock(a0)
        clr.w   _pl_spindash(a0)
        clr.b   _pl_status2(a0)
        clr.b   _pl_stick_convex(a0)
        clr.b   _pl_state(a0)                   ; defined start for SetState's exit lookup
        moveq   #PSTATE_AIR, d0                 ; drop to ground on frame 1
        bsr.w   Player_SetState
        bsr.w   Player_RefreshPhysics
        move.w  #objroutine(Player_Main), SST_code_addr(a0)
        bra.w   Player_DebugEnter

; -----------------------------------------------
; Player_RefreshPhysics — recompute the effective physics table in RAM
; Identity modifier today: straight copy of the character base row.
; Section/water/speed-shoes modifiers compose HERE later — called on
; section change and status events, NEVER per-frame (spec §3.4).
; In:  none (character = Sonic until the roster exists)
; Out: none
; Clobbers: a1-a2
; -----------------------------------------------
Player_RefreshPhysics:
        lea     (PhysTable_Sonic).l, a1
        lea     (Player_Phys).w, a2
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        rts

; -----------------------------------------------
; Player_Main — per-frame player update (RunObjects entry)
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d6, a1-a4 (a0/d7 preserved — RunObjects loop contract)
; -----------------------------------------------
Player_Main:
        ; --- debug-fly toggle (B press) ---
        move.b  (Ctrl_1_Press).w, d0
        btst    #4, d0                          ; BUTTON_B
        beq.s   .no_toggle
        tst.b   _pl_debug(a0)
        bne.s   .toggle_exit
        bsr.w   Player_DebugEnter
        bra.s   .no_toggle
.toggle_exit:
        bsr.w   Player_DebugExit
.no_toggle:
        tst.b   _pl_debug(a0)
        bne.w   Player_DebugMove                ; obj_control escape hatch:
                                                ; skips physics, dispatch,
                                                ; rings, and display tail

        lea     (Player_Phys).w, a4             ; physics table convention

        ; quadrant = (angle+$20)>>6 — first-class derived value; computed
        ; from LAST frame's angle (classic: angle updates at the floor pair)
        move.b  SST_angle(a0), d0
        addi.b  #$20, d0
        rol.b   #2, d0
        andi.b  #3, d0
        move.b  d0, (Player_Quadrant).w

        ; jump buffer: latch PHYS_JUMP_BUFFER on a press edge, else tick
        ; down. Maintained here; Task 6's jump check CONSUMES it.
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_JUMP_MASK, d0
        beq.s   .no_latch
        move.b  #PHYS_JUMP_BUFFER, (Player_JumpBuffer).w
        bra.s   .buffer_done
.no_latch:
        tst.b   (Player_JumpBuffer).w
        beq.s   .buffer_done
        subq.b  #1, (Player_JumpBuffer).w
.buffer_done:

        ; --- state dispatch. d7 saved across: Player_SensorFloor
        ; legitimately clobbers it inside the handlers ---
        move.w  d7, -(sp)
        lea     Player_States(pc), a1
        moveq   #0, d0
        move.b  _pl_state(a0), d0
        move.w  (a1,d0.w), d1
        jsr     (a1,d1.w)
        move.w  (sp)+, d7

        ; --- position history rings (recorded unconditionally — a
        ; "follower active?" branch costs more than the writes) ---
        move.w  (Player_Ring_Index).w, d0
        lea     (Player_Pos_Ring).w, a1
        move.w  SST_x_pos(a0), (a1,d0.w)
        move.w  SST_y_pos(a0), 2(a1,d0.w)
        lea     (Player_Stat_Ring).w, a1
        move.b  (Ctrl_1_Held).w, d1
        lsl.w   #8, d1
        move.b  (Ctrl_1_Press).w, d1
        move.w  d1, (a1,d0.w)                   ; input word (Held<<8|Press)
        move.b  SST_status(a0), 2(a1,d0.w)      ; +pad byte left untouched
        addq.b  #4, (Player_Ring_Index+1).w     ; low-byte wrap — rings are
                                                ; 256-aligned (ram.asm assert)
        ; fall through to the shared display tail

; -----------------------------------------------
; Player_Display — anim select from state + gsp, then the shared tail
; (AnimateSprite → per-character DPLC immediates → Draw_Sprite)
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
Player_Display:
        cmpi.b  #PSTATE_AIR, _pl_state(a0)
        bhs.s   .anim_air                       ; AIR/JUMP/ROLLJUMP/AIRBALL
        ; TODO(Task 7): PSTATE_ROLL wants the ball anim — grounded states
        ; all read walk/idle until rolling exists
        tst.w   _pl_gsp(a0)
        bne.s   .anim_walk
        move.b  #1, SST_anim(a0)                ; idle
        bra.s   .animate
.anim_walk:
        clr.b   SST_anim(a0)                    ; walk
        bra.s   .animate
.anim_air:
        move.b  #2, SST_anim(a0)                ; roll/jump ball
.animate:
        jsr     AnimateSprite
        jmp     Sonic_LoadArt                   ; character dispatch when the
                                                ; roster exists (Tails/Knux)

Player_States:
        dc.w    PState_Ground-Player_States     ; PSTATE_GROUND
        dc.w    PState_Ground-Player_States     ; PSTATE_ROLL — TODO(Task 7)
        dc.w    PState_Ground-Player_States     ; PSTATE_SPINDASH — TODO(Task 8)
        dc.w    PState_Air-Player_States        ; PSTATE_AIR
        dc.w    PState_Air-Player_States        ; PSTATE_JUMP — TODO(Task 6)
        dc.w    PState_Air-Player_States        ; PSTATE_ROLLJUMP — TODO(Task 6)
        dc.w    PState_Air-Player_States        ; PSTATE_AIRBALL — TODO(Task 6)

; -----------------------------------------------
; Player_SetState — THE one transition writer for player_state
; Old state's exit hook → write state byte → new state's enter hook.
; In:  a0 = player SST, d0.w = new PSTATE_* (byte offset, word-clean)
; Out: none
; Clobbers: d1, a1 (+ hook clobbers: d2, a2)
; Hooks contract: preserve a0/d0/d7
; -----------------------------------------------
Player_SetState:
        lea     PState_ExitHooks(pc), a1
        moveq   #0, d1
        move.b  _pl_state(a0), d1
        move.w  (a1,d1.w), d1
        jsr     (a1,d1.w)
        move.b  d0, _pl_state(a0)               ; written BEFORE the enter hook
        lea     PState_EnterHooks(pc), a1
        move.w  (a1,d0.w), d1
        jmp     (a1,d1.w)

PState_EnterHooks:
        dc.w    PHook_GroundEnter-PState_EnterHooks ; GROUND
        dc.w    PHook_Null-PState_EnterHooks        ; ROLL — TODO(Task 7): ball radii + curl y-shift
        dc.w    PHook_Null-PState_EnterHooks        ; SPINDASH — TODO(Task 8)
        dc.w    PHook_AirEnter-PState_EnterHooks    ; AIR
        dc.w    PHook_AirEnter-PState_EnterHooks    ; JUMP — TODO(Task 6): ball radii + curl y-shift
        dc.w    PHook_AirEnter-PState_EnterHooks    ; ROLLJUMP — TODO(Task 6)
        dc.w    PHook_AirEnter-PState_EnterHooks    ; AIRBALL — TODO(Task 6)

PState_ExitHooks:
        dc.w    PHook_Null-PState_ExitHooks         ; GROUND
        dc.w    PHook_Null-PState_ExitHooks         ; ROLL
        dc.w    PHook_Null-PState_ExitHooks         ; SPINDASH — TODO(Task 8): dust cleanup
        dc.w    PHook_Null-PState_ExitHooks         ; AIR
        dc.w    PHook_Null-PState_ExitHooks         ; JUMP
        dc.w    PHook_Null-PState_ExitHooks         ; ROLLJUMP
        dc.w    PHook_Null-PState_ExitHooks         ; AIRBALL

; ===== Enter/exit hooks — the ONE writer for width/height, curl
; y-shift, collision-mode resets, and anim latches (spec §3.3).
; NOTHING outside these hooks may touch those fields — the sole tolerated
; exception is the debug-fly art swap, which sits outside the state
; machine entirely. Hooks preserve a0/d0/d7.
PHook_Null:
        rts

PHook_GroundEnter:
        ; standing radii (idempotent until curl exists — Task 7 uncurl
        ; restores these + the −CURL_Y_SHIFT y-shift)
        move.b  #PLAYER_X_RADIUS*2+1, SST_width_pixels(a0)
        move.b  #PLAYER_Y_RADIUS*2+1, SST_height_pixels(a0)
        bclr    #ST_IN_AIR, SST_status(a0)
        rts

PHook_AirEnter:
        bset    #ST_IN_AIR, SST_status(a0)
        rts

; -----------------------------------------------
; PState_Ground — standing/running. FLAT subset: slope factor, quadrant-
; generalized snap axis, and the S3K wall-probe angle gates are Task 7.
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (may transition to PSTATE_AIR)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Ground:
        ; TODO(Task 8): spindash check goes here (first, classic order)
        ; TODO(Task 6): jump check goes here (consumes Player_JumpBuffer;
        ;               jump-delay fix: fall through into air movement)
        ; TODO(Task 7): slope factor on gsp goes here — BEFORE input,
        ;               using last frame's angle (classic order)
        bsr.w   Ground_Move
        jsr     ObjectMove

        ; --- floor pair: snap / angle update / ledge detach ---
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        cmpi.w  #16, d0
        bge.s   .airborne                       ; closer sensor ≥16 ⇒ both
                                                ; found nothing — ran off a ledge
        ; adaptive snap-down window: min(|gsp|>>8 + 4, 14)
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
        bgt.s   .airborne                       ; surface beyond snap reach
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
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, d2
        cmpi.b  #BUTTON_LEFT|BUTTON_RIGHT, d2
        bne.s   .lr_masked
        moveq   #0, d2                          ; L+R together = neither (bug #10)
.lr_masked:
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
        move.w  #-$80, d0                       ; turnaround kick
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
        move.w  #$80, d0                        ; turnaround kick
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
        moveq   #0, d0
        move.b  SST_angle(a0), d0
        jsr     GetSineCosine                   ; d0 = sin·$100, d1 = cos·$100
        ; variable×variable product — no table/shift form exists; one
        ; player, slope frames only (flat fast path above), classic does
        ; exactly this in Traction
        muls.w  _pl_gsp(a0), d1                 ; lint: disable=E002
        asr.l   #8, d1
        move.w  d1, SST_x_vel(a0)
        muls.w  _pl_gsp(a0), d0                 ; lint: disable=E002
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
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, d2
        cmpi.b  #BUTTON_LEFT|BUTTON_RIGHT, d2
        bne.s   .lr_masked
        moveq   #0, d2                          ; L+R together = neither (bug #10)
.lr_masked:
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

; -----------------------------------------------
; Debug-fly — suspends the state machine (the obj_control escape hatch).
; Enter swaps to the yellow marker square; exit restores Sonic and drops
; into PSTATE_AIR with velocities cleared. The art/size writes here are
; the one tolerated exception to the hook one-writer rule (outside the
; state machine by design).
; -----------------------------------------------
; In:  a0 = player SST.  Clobbers: none
Player_DebugEnter:
        st      _pl_debug(a0)
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art($FA,1,1), SST_art_tile(a0)    ; PlayerMarkerTile
                                                ; (written by the level
                                                ; state init)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        move.b  #1, SST_sprite_piece_count(a0)  ; debug path skips
                                                ; AnimateSprite's refresh
        clr.b   SST_mapping_frame(a0)
        clr.w   SST_x_vel(a0)
        clr.w   SST_y_vel(a0)
        clr.w   _pl_gsp(a0)
        rts

; In:  a0 = player SST.  Clobbers: d0-d2, a1-a2
Player_DebugExit:
        sf      _pl_debug(a0)
        bsr.w   Sonic_InitAssets
        ; standing radii until the AIR frame lands and hooks take over
        move.b  #PLAYER_X_RADIUS*2+1, SST_width_pixels(a0)
        move.b  #PLAYER_Y_RADIUS*2+1, SST_height_pixels(a0)
        clr.b   SST_mapping_frame(a0)
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        clr.w   SST_x_vel(a0)
        clr.w   SST_y_vel(a0)
        clr.w   _pl_gsp(a0)
        moveq   #PSTATE_AIR, d0
        jmp     Player_SetState

; D-pad free flight at PLAYER_DEBUG_FLY_SPEED px/frame (camera Y clamp
; caps effective follow speed), draw only.
; In:  a0 = player SST.  Clobbers: d0-d3, a1 (a0/d7 preserved)
Player_DebugMove:
        move.b  (Ctrl_1_Held).w, d0
        moveq   #PLAYER_DEBUG_FLY_SPEED, d1
        swap    d1                              ; px → 16.16
        btst    #2, d0                          ; LEFT
        beq.s   .check_right
        sub.l   d1, SST_x_pos(a0)
.check_right:
        btst    #3, d0                          ; RIGHT
        beq.s   .check_up
        add.l   d1, SST_x_pos(a0)
.check_up:
        btst    #0, d0                          ; UP
        beq.s   .check_down
        sub.l   d1, SST_y_pos(a0)
.check_down:
        btst    #1, d0                          ; DOWN
        beq.s   .draw
        add.l   d1, SST_y_pos(a0)
.draw:
        jmp     Draw_Sprite
