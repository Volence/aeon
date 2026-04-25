; TouchResponse — player-vs-object AABB collision detection and dispatch

; -----------------------------------------------
; TouchResponse — check player(s) against all collidable objects
; Iterates dynamic + system + effect slots. For each with
; collision_resp != 0, performs AABB overlap test against each
; player. On overlap, dispatches to per-type handler via jump table.
;
; Handler register convention (d0-d3 set before dispatch):
;   d0.w = combined_w (player.width + target.width)
;   d1.w = signed delta_x (player.x - target.x)
;   d2.w = combined_h (player.height + target.height)
;   d3.w = signed delta_y (player.y - target.y)
;   a2   = player SST
;   a3   = target SST
;
; In:  none (reads Object_RAM directly)
; Out: none
; Clobbers: d0-d7, a0-a3
; -----------------------------------------------
TouchResponse:
        lea     (Player_1).w, a2
        move.w  #NUM_PLAYERS-1, d7

.player_loop:
        tst.w   SST_code_addr(a2)
        beq.w   .next_player

        move.w  SST_x_pos(a2), d4       ; cache player X integer
        move.w  SST_y_pos(a2), d5       ; cache player Y integer

        lea     (Dynamic_Slots).w, a3
        move.w  #NUM_DYNAMIC+NUM_SYSTEM+NUM_EFFECTS-1, d6

.object_loop:
        tst.w   SST_code_addr(a3)
        beq.s   .next_object
        tst.b   SST_collision_resp(a3)
        beq.s   .next_object

        ; --- X axis overlap ---
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1
        add.w   d1, d0                  ; d0 = combined_w

        move.w  d4, d1                  ; player X
        sub.w   SST_x_pos(a3), d1       ; d1 = signed delta_x

        move.w  d1, d2
        bpl.s   .x_pos
        neg.w   d2
.x_pos:
        add.w   d2, d2                  ; abs(delta_x) * 2
        cmp.w   d0, d2
        bhs.s   .next_object

        ; Stash X results in address registers
        movea.w d0, a0                  ; a0 = combined_w
        movea.w d1, a1                  ; a1 = signed delta_x

        ; --- Y axis overlap ---
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3
        add.w   d3, d2                  ; d2 = combined_h

        move.w  d5, d3                  ; player Y
        sub.w   SST_y_pos(a3), d3       ; d3 = signed delta_y

        move.w  d3, d0                  ; scratch for abs
        bpl.s   .y_pos
        neg.w   d0
.y_pos:
        add.w   d0, d0                  ; abs(delta_y) * 2
        cmp.w   d2, d0
        bhs.s   .next_object

        ; --- Overlap confirmed: set up handler registers ---
        move.w  a0, d0                  ; d0 = combined_w
        move.w  a1, d1                  ; d1 = signed delta_x
                                        ; d2 = combined_h (already set)
                                        ; d3 = signed delta_y (already set)

        ; Dispatch via collision_resp jump table
        moveq   #0, d4
        move.b  SST_collision_resp(a3), d4
        cmpi.b  #COLLISION_TOUCH, d4
        bhi.s   .overlap_done

        movem.l d6-d7/a2-a3, -(sp)

        add.w   d4, d4
        add.w   d4, d4                  ; type * 4 (bra.w entry size)
        jsr     .handler_table(pc, d4.w)

        movem.l (sp)+, d6-d7/a2-a3

.overlap_done:
        ; Reload cached player position (handler may have moved player)
        move.w  SST_x_pos(a2), d4
        move.w  SST_y_pos(a2), d5

.next_object:
        lea     SST_len(a3), a3
        dbf     d6, .object_loop

.next_player:
        lea     SST_len(a2), a2
        dbf     d7, .player_loop
        rts

; -----------------------------------------------
; Handler jump table — bra.w entries, 4 bytes each
; Type 0 (COLLISION_NONE) through 12 (COLLISION_TOUCH)
;
; On entry: d0 = combined_w, d1 = signed delta_x,
;           d2 = combined_h, d3 = signed delta_y,
;           a2 = player SST, a3 = target SST
; -----------------------------------------------
.handler_table:
        bra.w   Touch_None              ; 0 — COLLISION_NONE
        bra.w   Touch_Enemy             ; 1 — COLLISION_ENEMY
        bra.w   Touch_Boss              ; 2 — COLLISION_BOSS
        bra.w   Touch_Hurt              ; 3 — COLLISION_HURT
        bra.w   Touch_Monitor           ; 4 — COLLISION_MONITOR
        bra.w   Touch_Ring              ; 5 — COLLISION_RING
        bra.w   Touch_Bubble            ; 6 — COLLISION_BUBBLE
        bra.w   Touch_Projectile        ; 7 — COLLISION_PROJECTILE
        bra.w   Touch_Solid             ; 8 — COLLISION_SOLID
        bra.w   Touch_SolidBreak        ; 9 — COLLISION_SOLID_BREAK
        bra.w   Touch_Spring            ; 10 — COLLISION_SPRING
        bra.w   Touch_SolidHurt         ; 11 — COLLISION_SOLID_HURT
        bra.w   Touch_Touch             ; 12 — COLLISION_TOUCH

; -----------------------------------------------
; Stub handlers — return immediately until implemented
; -----------------------------------------------
Touch_None:
Touch_Enemy:
Touch_Boss:
Touch_Monitor:
Touch_Ring:
Touch_Bubble:
Touch_Projectile:
Touch_SolidBreak:
Touch_Spring:
Touch_SolidHurt:
Touch_Touch:
        rts

; -----------------------------------------------
; Touch_Hurt — damage the player (stub)
; In:  a2 = player SST, a3 = target SST, d0-d3 = overlap data
; Out: none
; Clobbers: none (currently)
; -----------------------------------------------
Touch_Hurt:
        rts

; -----------------------------------------------
; Touch_Solid — AABB solid object collision response
; Determines contact face via minimum-penetration-axis,
; then pushes the player out and zeroes the relevant velocity.
;
; In:  a2 = player SST, a3 = target SST
;      d0.w = combined_w, d1.w = signed delta_x
;      d2.w = combined_h, d3.w = signed delta_y
; Out: none
; Clobbers: d0-d5
; -----------------------------------------------
Touch_Solid:
        lsr.w   #1, d0                  ; d0 = combined_half_w
        lsr.w   #1, d2                  ; d2 = combined_half_h

        ; pen_x = combined_half_w - abs(delta_x)
        move.w  d1, d4                  ; d4 = signed delta_x (for direction)
        bpl.s   .solid_ax_pos
        neg.w   d1
.solid_ax_pos:
        sub.w   d1, d0                  ; d0 = pen_x
        ble.s   .solid_done

        ; pen_y = combined_half_h - abs(delta_y)
        move.w  d3, d5                  ; d5 = signed delta_y (for direction)
        bpl.s   .solid_ay_pos
        neg.w   d3
.solid_ay_pos:
        sub.w   d3, d2                  ; d2 = pen_y
        ble.s   .solid_done

        ; Minimum penetration axis: pen_x vs pen_y
        cmp.w   d2, d0
        blo.s   .solid_side             ; pen_x < pen_y → side contact

        ; --- Vertical contact (pen_y <= pen_x) ---
        tst.w   d5
        bmi.s   .solid_top              ; player above target

        ; Player below target — snap below, zero y_vel if rising
        ; +1/-1 offsets keep 1px overlap so next frame's AABB check still passes
        add.w   d3, d2                  ; restore combined_half_h
        move.w  SST_y_pos(a3), d1
        add.w   d2, d1                  ; target.y + combined_half_h
        subq.w  #1, d1                  ; maintain contact
        move.w  d1, SST_y_pos(a2)
        tst.w   SST_y_vel(a2)
        bpl.s   .solid_done
        clr.w   SST_y_vel(a2)
        rts

.solid_top:
        ; Player above target — snap above, zero y_vel, set grounded
        add.w   d3, d2                  ; restore combined_half_h
        move.w  SST_y_pos(a3), d1
        sub.w   d2, d1                  ; target.y - combined_half_h
        addq.w  #1, d1                  ; maintain contact
        move.w  d1, SST_y_pos(a2)
        clr.w   SST_y_vel(a2)
        bclr    #ST_IN_AIR, SST_status(a2)
        bset    #ST_ON_OBJECT, SST_status(a2)
        bset    #ST_P1_STANDING, SST_status(a3)
        rts

.solid_side:
        ; Push player horizontally — subtract 1 from pen to maintain contact
        subq.w  #1, d0
        tst.w   d4
        bmi.s   .solid_push_left

        add.w   d0, SST_x_pos(a2)       ; push right
        clr.w   SST_x_vel(a2)
        rts

.solid_push_left:
        sub.w   d0, SST_x_pos(a2)       ; push left
        clr.w   SST_x_vel(a2)

.solid_done:
        rts
