; Camera system (§4)
; Tracks player with X deadzone (velocity-adaptive) and Y deadzone (fixed).

CAM_SCREEN_HALF_W   = 160
CAM_SCREEN_HALF_H   = 112

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
        rts

; -----------------------------------------------
; Camera_Update — follow Player_1 each frame
; In:  none (reads Player_1 SST and Camera_X)
; Out: none (updates Camera_X)
; Clobbers: d0–d3, a0
; -----------------------------------------------
Camera_Update:
        lea     (Player_1).w, a0

        ; -- X tracking with velocity-adaptive deadzone --
        move.l  SST_x_pos(a0), d0
        swap    d0                                 ; d0.w = player engine X
        move.l  (Camera_X).w, d1
        swap    d1                                 ; d1.w = camera X pixels
        addi.w  #CAM_SCREEN_HALF_W, d1            ; d1 = camera center X

        ; deadzone = base + |x_vel| >> 3
        move.w  (Camera_Deadzone_Base).w, d2
        move.w  SST_x_vel(a0), d3
        bpl.s   .vel_pos
        neg.w   d3
.vel_pos:
        lsr.w   #3, d3
        add.w   d3, d2

        ; dist = player_x - camera_center
        move.w  d0, d3
        sub.w   d1, d3

        ; check left boundary
        neg.w   d2
        cmp.w   d2, d3
        bge.s   .check_right
        sub.w   d2, d3                             ; overshoot amount
        bra.s   .apply_x

.check_right:
        neg.w   d2
        cmp.w   d2, d3
        ble.s   .no_move
        sub.w   d2, d3

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
        ;    BWD preview unreachable). Slot_Section_Map[0] = 0 ⇒ first pair.
        move.w  Act_cam_min_x(a0), d1
        tst.b   (Slot_Section_Map).w
        beq.s   .have_min                           ; at first pair → keep act default
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
        ;    view never shows the out-of-world region. --
        move.b  (Slot_Section_Map+2).w, d2          ; slot 1 sec_x
        cmpi.b  #SEC_VOID, d2
        bne.s   .max_x_in_grid
        move.w  #SLOT_ORIGIN_L+SECTION_SIZE-SCREEN_WIDTH, d1
        bra.s   .have_max
.max_x_in_grid:
        move.w  Act_cam_max_x(a0), d1
        moveq   #0, d3
        move.b  d2, d3
        addq.b  #1, d3                              ; next-FWD sec_x = slot 1 + 1
        cmp.b   Act_grid_w+1(a0), d3
        bcc.s   .have_max                           ; >= grid_w → at last pair, no FWD neighbour
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
        neg.w   d2
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
