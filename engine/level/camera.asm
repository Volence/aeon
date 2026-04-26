; Camera system (§4 Phase 1)
; Tracks player with X deadzone and velocity-adaptive width.
; Y is clamped to 0 (no vertical scroll in Phase 1).

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
        add.w   d2, d3                             ; overshoot amount
        bra.s   .apply_x

.check_right:
        neg.w   d2
        cmp.w   d2, d3
        ble.s   .y_track
        sub.w   d2, d3

.apply_x:
        ext.l   d3
        lsl.l   #8, d3
        lsl.l   #8, d3                             ; to 16.16 fixed (lsl.l #16 split for AS)
        add.l   d3, (Camera_X).w

        ; clamp to act bounds
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0
        cmp.w   Act_cam_min_x(a0), d0
        bge.s   .check_max_x
        move.w  Act_cam_min_x(a0), d0
        bra.s   .clamp_x
.check_max_x:
        cmp.w   Act_cam_max_x(a0), d0
        ble.s   .y_track
        move.w  Act_cam_max_x(a0), d0
.clamp_x:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w

.y_track:
        ; Phase 1: camera Y fixed at 0 — leave Camera_Y unchanged
        rts
