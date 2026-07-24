; Camera system (§4)
; Tracks player with a fixed classic-S3K X deadzone and a fixed Y deadzone.

CAM_SCREEN_HALF_W   = 160
CAM_SCREEN_HALF_H   = 112
CAM_X_DEADZONE_INIT = $10       ; Camera_Deadzone_Base seed: the classic 16px
                                ; asymmetric X window (variable at runtime —
                                ; game code may widen it; Y's stays fixed)
CAM_Y_DEADZONE      = 32        ; fixed vertical deadzone half-window (px)
CAM_MAX_X_STEP      = 16        ; max horizontal scroll px/frame (classic S2/CD;
                                ; S3K=24, imperceptible at the 6px/f player top
                                ; speed). Caps large player position jumps (e.g.
                                ; springs) so the camera can't outrun
                                ; Section_UpdateColumns.

; -----------------------------------------------
; Camera_Init — initialise from act descriptor
; In:  a0 = act descriptor pointer (read only — preserved)
; Out: none
; Clobbers: d0
; -----------------------------------------------
Camera_Init:
        ; Camera_X/Y are 16.16 fixed-point, WORLD coordinates (continuous-scroll).
        ; start X = (start_sec_x << SECTION_SIZE_SHIFT) + start_local_x - CAM_SCREEN_HALF_W
        moveq   #0, d0
        move.b  Act_start_sec_x(a0), d0
        lsl.l   #8, d0                             ; sec_x << SECTION_SIZE_SHIFT,
        lsl.l   #SECTION_SIZE_SHIFT-8, d0          ; split 8+rest: max shift is 8/op
        add.w   Act_start_local_x(a0), d0          ; section world origin (px) + local
        subi.w  #CAM_SCREEN_HALF_W, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w

        ; start Y = (start_sec_y << SECTION_SIZE_SHIFT) + start_local_y - CAM_SCREEN_HALF_H
        moveq   #0, d0
        move.b  Act_start_sec_y(a0), d0
        lsl.l   #8, d0                             ; sec_y << SECTION_SIZE_SHIFT,
        lsl.l   #SECTION_SIZE_SHIFT-8, d0          ; split 8+rest: max shift is 8/op
        add.w   Act_start_local_y(a0), d0          ; section world origin (px) + local
        subi.w  #CAM_SCREEN_HALF_H, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_Y).w

        move.w  #0, (Camera_Pan_Offset).w
        move.w  #CAM_X_DEADZONE_INIT, (Camera_Deadzone_Base).w
        clr.b   (Camera_Hold_Frames).w            ; spindash release writes it;
                                                   ; Camera_Update consumes it
        rts

; -----------------------------------------------
; Camera_Update — follow Player_1 each frame
; In:  none (reads Player_1 SST and Camera_X/Camera_Y)
; Out: none (updates Camera_X and Camera_Y)
; Clobbers: d0–d4, a0   (d4 = spindash-freeze flag, set in the preamble and
;                        consumed at .y_track — see the reservation note there)
; -----------------------------------------------
Camera_Update:
        ; -- spindash launch freeze --
        ;    Camera_Hold_Frames is set =16 on spindash release.
        ;    While nonzero, hold the camera still (skip BOTH X and Y follow)
        ;    so the launch doesn't whip-scroll and the charge-frame backward
        ;    creep can't register. Classic "freeze camera 16 frames" (research
        ;    feel-modern §3). X is the load-bearing axis (spindash is
        ;    horizontal); Y is frozen too because the bounds clamps below still
        ;    run. The freeze only suppresses player-follow, not external
        ;    position writes (continuous-scroll: there are no section teleport
        ;    rebases — the camera tracks the player in world space). Decrement
        ;    once per frame.
        moveq   #0, d4                              ; d4 = "frozen this frame"
        tst.b   (Camera_Hold_Frames).w
        beq.s   .no_freeze
        subq.b  #1, (Camera_Hold_Frames).w
        st      d4                                  ; survives to .y_track
        bra.s   .x_done                             ; X-clamp only; .y_track
                                                    ; tests d4 and skips Y follow
        ; NOTE: d4 is reserved as the freeze flag from here through the
        ; X-clamp path to .y_track — do not reuse d4 between here and
        ; .y_track or the Y freeze silently breaks.
.no_freeze:
        lea     (Player_1).w, a0

        ; -- X tracking: classic S3K fixed deadzone (screen-x 144..160) --
        ;    Matches S2/S3K ScrollHoriz: scroll-RIGHT boundary at dead
        ;    centre (Sonic centred while advancing), scroll-LEFT boundary
        ;    Camera_Deadzone_Base px to its left — an asymmetric 16px window.
        ;    Step capped at CAM_MAX_X_STEP px/frame.
        move.l  SST_x_pos(a0), d0
        swap    d0                                 ; d0.w = player engine X
        move.l  (Camera_X).w, d1
        swap    d1                                 ; d1.w = camera X (screen left edge)
        addi.w  #CAM_SCREEN_HALF_W, d1            ; d1 = camera centre X (screen 160)

        move.w  d0, d3
        sub.w   d1, d3                             ; d3 = dist = screen_x - 160

        tst.w   d3
        bge.s   .x_scroll_right                    ; dist >= 0 → at/past centre → scroll right
        ; left: hold until the player passes the left boundary (-deadzone)
        move.w  (Camera_Deadzone_Base).w, d2
        neg.w   d2                                 ; d2 = -deadzone (left boundary)
        cmp.w   d2, d3
        bge.s   .x_done                            ; -deadzone <= dist < 0 → hold
        sub.w   d2, d3                             ; overshoot = dist + deadzone (<0)
        cmpi.w  #-CAM_MAX_X_STEP, d3               ; cap leftward step
        bge.s   .apply_x
        move.w  #-CAM_MAX_X_STEP, d3
        bra.s   .apply_x
.x_scroll_right:
        cmpi.w  #CAM_MAX_X_STEP, d3                ; overshoot = dist; cap rightward step
        ble.s   .apply_x
        move.w  #CAM_MAX_X_STEP, d3

.apply_x:
        ext.l   d3
        lsl.l   #8, d3
        lsl.l   #8, d3                             ; to 16.16 fixed (lsl.l #16 split for AS)
        add.l   d3, (Camera_X).w

.x_done:
        ; -- continuous-scroll X clamp: [0, level_width − SCREEN_WIDTH] --
        ;    level_width = grid_w << SECTION_SIZE_SHIFT. No more Section_Edge_Flags
        ;    / PREVIEW_PIXELS branches — the world camera spans the whole act.
        ;    ALL X paths converge here — .x_done is the branch target for the
        ;    deadzone hold and the spindash freeze, and .apply_x falls through;
        ;    control continues into .y_track below.
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0
        tst.w   d0
        bge.s   .min_ok
        moveq   #0, d0
.min_ok:
        moveq   #0, d1
        move.w  Act_grid_w(a0), d1
        lsl.l   #8, d1                              ; grid_w << SECTION_SIZE_SHIFT
        lsl.l   #SECTION_SIZE_SHIFT-8, d1           ;   = level_width (px); split 8+rest
        ; MEGA-ACT CEILING: the right-bound clamp below is WORD arithmetic
        ; (subi.w/cmp.w), so a level_width above $FFFF px — grid_w > 31 sections —
        ; word-wraps. Guarded today by act_descriptor's
        ; (GRID_W << SECTION_SIZE_SHIFT) <= $8000 ensure (grid_w <= 16, tighter than
        ; 31). Floating-origin Phase 4 removes the word truncation.
        subi.w  #SCREEN_WIDTH, d1
        cmp.w   d1, d0
        ble.s   .clamp_x
        move.w  d1, d0
.clamp_x:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w

.y_track:
        tst.b   d4                                  ; spindash freeze active?
        bne.s   .clamp_y                            ; yes → hold Y, clamp only
        lea     (Player_1).w, a0

        move.l  SST_y_pos(a0), d0
        swap    d0                                 ; d0.w = player engine Y
        move.l  (Camera_Y).w, d1
        swap    d1                                 ; d1.w = camera Y pixels
        addi.w  #CAM_SCREEN_HALF_H, d1            ; d1 = camera center Y

        moveq   #CAM_Y_DEADZONE, d2               ; fixed vertical deadzone

        move.w  d0, d3
        sub.w   d1, d3                             ; dist = player_y - camera_center

        neg.w   d2
        cmp.w   d2, d3
        bge.s   .check_down
        sub.w   d2, d3
        bra.s   .apply_y

.check_down:
        ; -- landing lock (game-declared GAME_CAMERA_JUMP_LOCK gate) --
        ;    While airborne FROM A JUMP (PSTATE_JUMP / PSTATE_ROLLJUMP — the
        ;    upward-launched states, classic's jump flag) the camera must NOT
        ;    scroll down to chase a rising/hanging player. We reach here only
        ;    in the down-scroll case (player below focal point), so the lock
        ;    is just: in those states, suppress the down catch-up entirely.
        ;    Upward scroll (the branch above) is untouched — following a high
        ;    jump up is fine. AIR/AIRBALL (falls, walk-offs, roll-offs) scroll
        ;    normally. Lock lifts automatically on landing (state→GROUND/ROLL)
        ;    or once the player reaches the bottom screen edge WHILE STILL in
        ;    a jump state: there we DO resume so a long fall after the apex
        ;    isn't left off-screen. Debug-fly forces PSTATE_AIR (not a jump
        ;    state), so it follows as before. (research feel-modern §3; spec §7)
        ;    Requires game-defined _pl_state/PSTATE_JUMP/PSTATE_ROLLJUMP; games
        ;    without them set GAME_CAMERA_JUMP_LOCK=0 for plain deadzone follow
        ;    (falls straight from .check_down to .down_ok below).
    if GAME_CAMERA_JUMP_LOCK
        move.b  (Player_1+_pl_state).w, d2
        cmpi.b  #PSTATE_JUMP, d2
        beq.s   .jump_state
        cmpi.b  #PSTATE_ROLLJUMP, d2
        bne.s   .down_ok
.jump_state:
        ; Gate the lock on vertical velocity: only hold while RISING/HANGING —
        ; exactly the stated intent ("must NOT scroll down to chase a rising/
        ; hanging player"). The jump state persists through the whole arc incl.
        ; the descent, so without this the lock froze Y while the player sank to
        ; the bottom edge, then alternated 16-px catch-up steps with hold frames
        ; (Sonic riding the edge, jittering). Once y_vel goes positive the player
        ; is falling: release so the descent follows like a walk-off (32-px
        ; deadzone, 16 px/frame) and settles back to the focal point. Short hops
        ; still don't scroll (their descent never exceeds the deadzone).
        tst.w   (Player_1+SST_y_vel).w             ; falling? (y_vel > 0)
        bgt.s   .down_ok                           ; yes → normal deadzone follow
.land_lock:
        ; rising/hanging, below focal point — d3 still holds the raw signed dist
        ; (player_y - center). Failsafe: if the player somehow reaches the bottom
        ; screen edge (CAM_SCREEN_HALF_H below center) while still rising, resume
        ; follow so it isn't left off-screen; otherwise hold Y.
        cmpi.w  #CAM_SCREEN_HALF_H, d3              ; at/over bottom screen edge?
        bge.s   .down_ok                            ; → resume follow
        bra.s   .clamp_y                            ; locked → hold Y
    endif
.down_ok:
        moveq   #CAM_Y_DEADZONE, d2                 ; restore +deadzone (d2 clobbered)
        cmp.w   d2, d3
        ble.s   .clamp_y
        sub.w   d2, d3

.apply_y:
        cmpi.w  #CAM_MAX_Y_STEP, d3
        ble.s   .y_step_hi_ok
        move.w  #CAM_MAX_Y_STEP, d3
.y_step_hi_ok:
        cmpi.w  #-CAM_MAX_Y_STEP, d3
        bge.s   .y_step_lo_ok
        move.w  #-CAM_MAX_Y_STEP, d3
.y_step_lo_ok:
        ext.l   d3
        lsl.l   #8, d3
        lsl.l   #8, d3
        add.l   d3, (Camera_Y).w

.clamp_y:
        ; -- continuous-scroll Y clamp: [0, level_height − SCREEN_HEIGHT] --
        ;    level_height = grid_h << SECTION_SIZE_SHIFT. Grid-derived, fully
        ;    symmetric with .clamp_x — no act-supplied camera bounds. External
        ;    entry (spindash freeze, .land_lock, fall-through from
        ;    .y_step_lo_ok); must keep the .clamp_y label and the trailing rts.
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_Y).w, d0
        swap    d0
        tst.w   d0
        bge.s   .y_min_ok
        moveq   #0, d0
.y_min_ok:
        moveq   #0, d1
        move.w  Act_grid_h(a0), d1
        lsl.l   #8, d1                              ; grid_h << SECTION_SIZE_SHIFT
        lsl.l   #SECTION_SIZE_SHIFT-8, d1           ;   = level_height (px); split 8+rest
        ; MEGA-ACT CEILING: word clamp below (subi.w/cmp.w) word-wraps for a
        ; level_height above $FFFF px — grid_h > 31 sections. Guarded today by
        ; act_descriptor's (GRID_H << SECTION_SIZE_SHIFT) <= $8000 ensure
        ; (grid_h <= 16). Floating-origin Phase 4 removes the word truncation.
        subi.w  #SCREEN_HEIGHT, d1
        cmp.w   d1, d0
        ble.s   .y_write
        move.w  d1, d0
.y_write:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_Y).w
        rts
