; TouchResponse — player-vs-object AABB collision detection and dispatch

; -----------------------------------------------
; TouchResponse — check player(s) against all collidable objects
; Iterates dynamic + effect slots. For each with collision_resp != 0,
; performs AABB overlap test against each player. On overlap, dispatches
; to per-type handler via jump table.
;
; In:  none (reads Object_RAM directly)
; Out: none
; Clobbers: d0-d6, a0-a3
; -----------------------------------------------
TouchResponse:
        lea     (Player_1).w, a2
        move.w  #NUM_PLAYERS-1, d7

.player_loop:
        tst.w   SST_code_addr(a2)
        beq.w   .next_player

        ; Preload player position and dimensions for inner loop
        move.w  SST_x_pos(a2), d4       ; player X integer
        move.w  SST_y_pos(a2), d5       ; player Y integer

        ; Scan dynamic + system + effect slots (system slots with
        ; collision_resp=0 are rejected by tst.b fast path)
        lea     (Dynamic_Slots).w, a3
        move.w  #NUM_DYNAMIC+NUM_SYSTEM+NUM_EFFECTS-1, d6

.object_loop:
        tst.w   SST_code_addr(a3)
        beq.s   .next_object
        tst.b   SST_collision_resp(a3)
        beq.s   .next_object

        ; --- X axis overlap ---
        ; combined_w = player.width + target.width (byte add, extend to word)
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1
        add.w   d1, d0                  ; d0 = combined_w

        ; delta_x = abs(player.x - target.x), then double it
        move.w  d4, d1                  ; player X
        sub.w   SST_x_pos(a3), d1       ; signed delta
        bpl.s   .x_pos
        neg.w   d1
.x_pos:
        add.w   d1, d1                  ; doubled distance
        cmp.w   d0, d1
        bhs.s   .next_object            ; no X overlap

        ; --- Y axis overlap ---
        moveq   #0, d0
        move.b  SST_height_pixels(a2), d0
        moveq   #0, d2
        move.b  SST_height_pixels(a3), d2
        add.w   d2, d0                  ; d0 = combined_h

        move.w  d5, d2                  ; player Y
        sub.w   SST_y_pos(a3), d2       ; signed delta
        bpl.s   .y_pos
        neg.w   d2
.y_pos:
        add.w   d2, d2                  ; doubled distance
        cmp.w   d0, d2
        bhs.s   .next_object            ; no Y overlap

        ; --- Overlap confirmed: dispatch to handler ---
        moveq   #0, d0
        move.b  SST_collision_resp(a3), d0
        cmpi.b  #COLLISION_TOUCH, d0
        bhi.s   .next_object            ; reject invalid types

        ; Save loop state across handler call
        movem.l d6-d7/a2-a3, -(sp)

        add.w   d0, d0
        add.w   d0, d0                  ; type * 4 (bra.w entry size)
        jsr     .handler_table(pc, d0.w)

        movem.l (sp)+, d6-d7/a2-a3

        ; Reload player position (handler may have changed it)
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
; a2 = player SST, a3 = target SST on entry
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
; Stub handlers — all return immediately until implemented
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
; Player invincibility check will be added when
; the player object and damage system exist.
;
; In:  a2 = player SST, a3 = target SST
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
; Out: none
; Clobbers: d0-d5
; -----------------------------------------------
Touch_Solid:
        ; Compute half-widths (combined)
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #0, d1
        move.b  SST_width_pixels(a3), d1
        add.w   d1, d0
        lsr.w   #1, d0                  ; d0 = combined_half_w

        ; Signed X delta: player - target
        move.w  SST_x_pos(a2), d1
        sub.w   SST_x_pos(a3), d1       ; d1 = signed delta_x
        move.w  d1, d4                  ; d4 = signed delta_x (preserved for direction)

        ; abs(delta_x)
        bpl.s   .solid_ax_pos
        neg.w   d1
.solid_ax_pos:
        ; pen_x = combined_half_w - abs(delta_x)
        sub.w   d1, d0                  ; d0 = pen_x
        ble.s   .solid_done             ; no X penetration (shouldn't happen, but guard)

        ; Compute half-heights (combined)
        moveq   #0, d2
        move.b  SST_height_pixels(a2), d2
        moveq   #0, d3
        move.b  SST_height_pixels(a3), d3
        add.w   d3, d2
        lsr.w   #1, d2                  ; d2 = combined_half_h

        ; Signed Y delta: player - target
        move.w  SST_y_pos(a2), d3
        sub.w   SST_y_pos(a3), d3       ; d3 = signed delta_y
        move.w  d3, d5                  ; d5 = signed delta_y (preserved for direction)

        ; abs(delta_y)
        bpl.s   .solid_ay_pos
        neg.w   d3
.solid_ay_pos:
        ; pen_y = combined_half_h - abs(delta_y)
        sub.w   d3, d2                  ; d2 = pen_y
        ble.s   .solid_done             ; no Y penetration

        ; Minimum penetration axis: pen_x vs pen_y
        cmp.w   d2, d0
        blo.s   .solid_side             ; pen_x < pen_y → side contact

        ; --- Vertical contact (pen_y <= pen_x) ---
        tst.w   d5
        bmi.s   .solid_top              ; player above target (delta_y < 0)

        ; Player below target — snap below, zero y_vel if rising
.solid_bottom:
        ; Compute combined_half_h fresh from d2 + abs_delta_y
        ; Actually: snap player.y = target.y + combined_half_h
        ; combined_half_h is in the original sum before pen_y subtraction
        ; Recompute: combined_half_h = pen_y + abs(delta_y) = d2 + d3
        add.w   d3, d2                  ; d2 = combined_half_h (restored)
        move.w  SST_y_pos(a3), d1
        add.w   d2, d1                  ; target.y + combined_half_h
        move.w  d1, SST_y_pos(a2)       ; snap player Y below
        ; Zero y_vel only if player was rising
        tst.w   SST_y_vel(a2)
        bpl.s   .solid_done
        clr.w   SST_y_vel(a2)
        rts

.solid_top:
        ; Player above target — snap above, zero y_vel
        ; Restore combined_half_h = d2 + d3
        add.w   d3, d2                  ; d2 = combined_half_h
        move.w  SST_y_pos(a3), d1
        sub.w   d2, d1                  ; target.y - combined_half_h
        move.w  d1, SST_y_pos(a2)       ; snap player Y above
        clr.w   SST_y_vel(a2)
        rts

.solid_side:
        ; Push player horizontally by pen_x in direction away from target
        tst.w   d4
        bmi.s   .solid_push_left

        ; Player is right of target — push right
        add.w   d0, SST_x_pos(a2)       ; x += pen_x
        clr.w   SST_x_vel(a2)
        rts

.solid_push_left:
        ; Player is left of target — push left
        sub.w   d0, SST_x_pos(a2)       ; x -= pen_x
        clr.w   SST_x_vel(a2)

.solid_done:
        rts
