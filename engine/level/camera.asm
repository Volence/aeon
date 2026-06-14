; Camera system (§4)
; Tracks player with a fixed classic-S3K X deadzone and a fixed Y deadzone.

CAM_SCREEN_HALF_W   = 160
CAM_SCREEN_HALF_H   = 112
CAM_MAX_X_STEP      = 16        ; max horizontal scroll px/frame (classic S2/CD;
                                ; S3K=24, imperceptible at the 6px/f player top
                                ; speed). Caps spring/teleport position jumps so
                                ; the camera can't outrun Section_UpdateColumns.

; -----------------------------------------------
; Camera_Init — initialise from act descriptor
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0, a0
; -----------------------------------------------
Camera_Init:
        ; Camera_X/Y are 16.16 fixed-point
        ; start X = SLOT_ORIGIN_L + start_local_x - CAM_SCREEN_HALF_W
        move.w  Act_start_local_x(a0), d0
        addi.w  #SLOT_ORIGIN_L, d0
        subi.w  #CAM_SCREEN_HALF_W, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w

        move.w  Act_start_local_y(a0), d0
        addi.w  #SLOT_ORIGIN_U, d0
        subi.w  #CAM_SCREEN_HALF_H, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_Y).w

        move.w  #0, (Camera_Pan_Offset).w
        move.w  #$10, (Camera_Deadzone_Base).w
        clr.b   (Camera_Spindash_Lag).w            ; spindash release writes it
                                                   ; (§5 Task 8); the camera
                                                   ; consumes it in Task 10
        rts

; -----------------------------------------------
; Camera_Update — follow Player_1 each frame
; In:  none (reads Player_1 SST and Camera_X)
; Out: none (updates Camera_X)
; Clobbers: d0–d4, a0   (d4 = spindash-freeze flag, set in the preamble and
;                        consumed at .y_track — see the reservation note there)
; -----------------------------------------------
Camera_Update:
        ; -- §5 Task 10.2: spindash launch freeze --
        ;    Camera_Spindash_Lag is set =16 on spindash release (Task 8).
        ;    While nonzero, hold the camera still (skip BOTH X and Y follow)
        ;    so the launch doesn't whip-scroll and the charge-frame backward
        ;    creep can't register. Classic "freeze camera 16 frames" (research
        ;    feel-modern §3). X is the load-bearing axis (spindash is
        ;    horizontal); Y is frozen too because the bounds clamps below still
        ;    run, and a section teleport rebase writes Camera_X/Y directly
        ;    (outside this follow), so a teleport during the freeze still
        ;    applies — the freeze only suppresses player-follow, not external
        ;    position writes. Decrement once per frame.
        moveq   #0, d4                              ; d4 = "frozen this frame"
        tst.b   (Camera_Spindash_Lag).w
        beq.s   .no_freeze
        subq.b  #1, (Camera_Spindash_Lag).w
        st      d4                                  ; survives to .y_track
        bra.w   .no_move                            ; X-clamp only; .y_track
                                                    ; tests d4 and skips Y follow
        ; NOTE: d4 is reserved as the freeze flag from here through the
        ; X-clamp path to .y_track — do not reuse d4 in .no_move/.check_max_x/
        ; .clamp_x or the Y freeze silently breaks.
.no_freeze:
        lea     (Player_1).w, a0

        ; -- X tracking: classic S3K fixed deadzone (screen-x 144..160) --
        ;    The old code widened the deadzone by |x_vel|>>3, but x_vel is
        ;    8.8 subpixels — at top speed ($600) that added 1536>>3 = 192px,
        ;    making the deadzone ~208px (wider than the 160px half-screen), so
        ;    Sonic ran clean off the screen edge before the camera scrolled.
        ;    Now matches S2/S3K ScrollHoriz: scroll-RIGHT boundary at dead
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
        bge.s   .no_move                           ; -deadzone <= dist < 0 → hold
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

.no_move:
        ; clamp to act bounds (always run regardless of deadzone)
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0

        ; -- §4.2: dynamic min_x — extend by PREVIEW_PIXELS into BWD preview
        ;    region unless we're at the first pair (Sec(-1) doesn't exist;
        ;    BWD preview unreachable ⇔ the BWD teleport is unavailable).
        ;    Edge predicate shared via Section_Edge_Flags: Section_Check
        ;    gates the teleport and Player_LevelBound places the playable
        ;    bound off the SAME bits. --
        move.w  Act_cam_min_x(a0), d1
        btst    #SEF_BWD_BLOCKED, (Section_Edge_Flags).w
        bne.s   .have_min                           ; at first pair → keep act default
        subi.w  #PREVIEW_PIXELS, d1                 ; allow scroll into BWD preview
.have_min:
        cmp.w   d1, d0
        bge.s   .check_max_x
        move.w  d1, d0
        bra.s   .clamp_x

.check_max_x:
        ; -- §4.2: dynamic max_x — extend by PREVIEW_PIXELS into FWD preview
        ;    region unless we're at the last pair (no next FWD section).
        ;    Void slot 1 (SEC_VOID, act edge on an odd-width grid): the
        ;    playable area is slot 0 only — clamp at its right edge so the
        ;    view never shows the out-of-world region. Same shared
        ;    Section_Edge_Flags predicate as .have_min above. --
        move.b  (Section_Edge_Flags).w, d2
        btst    #SEF_FWD_VOID, d2
        beq.s   .max_x_in_grid
        move.w  #SLOT_ORIGIN_L+SECTION_SIZE-SCREEN_WIDTH, d1
        bra.s   .have_max
.max_x_in_grid:
        move.w  Act_cam_max_x(a0), d1
        btst    #SEF_FWD_BLOCKED, d2
        bne.s   .have_max                           ; at last pair → no FWD preview
        addi.w  #PREVIEW_PIXELS, d1
.have_max:
        cmp.w   d1, d0
        ble.s   .y_track
        move.w  d1, d0

.clamp_x:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w

.y_track:
        tst.b   d4                                  ; spindash freeze active?
        bne.w   .clamp_y                            ; yes → hold Y, clamp only
        lea     (Player_1).w, a0

        move.l  SST_y_pos(a0), d0
        swap    d0                                 ; d0.w = player engine Y
        move.l  (Camera_Y).w, d1
        swap    d1                                 ; d1.w = camera Y pixels
        addi.w  #CAM_SCREEN_HALF_H, d1            ; d1 = camera center Y

        moveq   #32, d2                           ; fixed vertical deadzone

        move.w  d0, d3
        sub.w   d1, d3                             ; dist = player_y - camera_center

        neg.w   d2
        cmp.w   d2, d3
        bge.s   .check_down
        sub.w   d2, d3
        bra.s   .apply_y

.check_down:
        ; -- §5 Task 10.1: landing lock --
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
        move.b  (Player_1+_pl_state).w, d2
        cmpi.b  #PSTATE_JUMP, d2
        beq.s   .land_lock
        cmpi.b  #PSTATE_ROLLJUMP, d2
        bne.s   .down_ok
.land_lock:
        ; player is below focal point in a jump state — d3 still holds the raw
        ; signed dist (player_y - center). Lock only until the player reaches
        ; the bottom screen edge (CAM_SCREEN_HALF_H below center); past that a
        ; long post-apex fall must resume follow so it isn't left off-screen.
        cmpi.w  #CAM_SCREEN_HALF_H, d3              ; at/over bottom screen edge?
        bge.s   .down_ok                            ; → resume follow
        bra.w   .clamp_y                            ; locked → hold Y
.down_ok:
        moveq   #32, d2                             ; restore +deadzone (d2 clobbered)
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
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_Y).w, d0
        swap    d0

        ; -- dynamic min_y: apply only at top row (no section above) --
        tst.b   (Slot_Section_Map+1).w
        bne.s   .check_max_y                         ; sec_y > 0 → section above, skip min_y
        move.w  Act_cam_min_y(a0), d1
        cmp.w   d1, d0
        bge.s   .check_max_y
        move.w  d1, d0
        bra.s   .write_y

.check_max_y:
        ; -- dynamic max_y: apply only at bottom row (no section below) --
        moveq   #0, d2
        move.b  (Slot_Section_Map+1).w, d2
        addq.b  #1, d2
        cmp.b   Act_grid_h+1(a0), d2
        bcs.s   .y_done                              ; < grid_h → section below, skip max_y
        move.w  Act_cam_max_y(a0), d1
        cmp.w   d1, d0
        ble.s   .y_done
        move.w  d1, d0

.write_y:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_Y).w

.y_done:
        rts
