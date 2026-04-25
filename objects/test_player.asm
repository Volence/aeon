; Test player — controllable character with movement, gravity, jumping
; Uses Sonic sprite art (DPLC-loaded), reads P1 controller input

; -----------------------------------------------
; Physics constants (S2/S.C.E. reference values)
; -----------------------------------------------
GRAVITY                 = $38           ; vertical acceleration per frame
JUMP_VELOCITY           = -$680         ; initial jump impulse (negative = up)
JUMP_CAP                = -$400         ; variable jump — cap y_vel when button released
ACCELERATION            = $C           ; ground horizontal acceleration
DECELERATION            = $80           ; ground horizontal deceleration (braking)
TOP_SPEED               = $600          ; maximum horizontal velocity
TERMINAL_VELOCITY       = $1000         ; maximum falling velocity
AIR_ACCEL               = $18           ; air horizontal acceleration
STUB_FLOOR_Y            = 192           ; pixel Y for stub ground plane

; -----------------------------------------------
; TestPlayer — init routine
; In:  a0 = SST pointer (slot already allocated)
; -----------------------------------------------
TestPlayer:
        move.l  #Map_Sonic, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_SONIC,0,0), SST_art_tile(a0)
        move.l  #Ani_Sonic, SST_anim_table(a0)
        move.l  #DPLC_Sonic, _dplc_ptr(a0)
        move.l  #Art_Sonic, _art_base(a0)
        move.b  #1, SST_anim(a0)               ; idle
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        move.w  #4, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #32, SST_height_pixels(a0)
        move.b  #COLLISION_NONE, SST_collision_resp(a0)
        clr.b   SST_status(a0)                 ; start grounded (in_air clear)
        move.w  #objroutine(TestPlayer_Main), SST_code_addr(a0)

        ; Fall through to main for first frame
; -----------------------------------------------
; TestPlayer_Main — per-frame update
; In:  a0 = SST pointer
;
; Ground detection: "grounded" = on_object was set by Touch_Solid
; last frame, OR player is on the stub floor. ST_ON_OBJECT is
; cleared each frame and re-set by Touch_Solid if still overlapping.
; This gives 1 frame of grace when walking off an edge (coyote time).
; -----------------------------------------------
TestPlayer_Main:
        ; --- Snapshot on_object, then clear it (Touch_Solid re-sets if needed) ---
        move.b  SST_status(a0), d5             ; d5 = status snapshot
        bclr    #ST_ON_OBJECT, SST_status(a0)

        ; --- Determine grounded state into d5 bit 7 (1 = grounded) ---
        ; Grounded if: on_object was set, OR on stub floor
        btst    #ST_ON_OBJECT, d5
        bne.s   .is_grounded
        cmpi.w  #STUB_FLOOR_Y, SST_y_pos(a0)
        bge.s   .is_grounded
        ; Airborne
        bset    #ST_IN_AIR, SST_status(a0)
        bra.s   .grounded_done
.is_grounded:
        bclr    #ST_IN_AIR, SST_status(a0)
.grounded_done:

        ; --- Read controller ---
        move.b  (Ctrl_1_Held).w, d6             ; d6 = held buttons
        move.b  (Ctrl_1_Press).w, d7            ; d7 = newly pressed

        ; --- Jump check (only if grounded) ---
        btst    #ST_IN_AIR, SST_status(a0)
        bne.s   .no_jump_start
        move.b  d7, d0
        andi.b  #BUTTON_B|BUTTON_C, d0
        beq.s   .no_jump_start
        move.w  #JUMP_VELOCITY, SST_y_vel(a0)
        bset    #ST_IN_AIR, SST_status(a0)
        bclr    #ST_ON_OBJECT, SST_status(a0)
.no_jump_start:

        ; --- Horizontal movement ---
        move.w  SST_x_vel(a0), d0               ; d0 = current x_vel

        ; Determine accel/decel values based on ground state
        move.w  #ACCELERATION, d2               ; d2 = accel
        move.w  #DECELERATION, d3               ; d3 = decel
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .have_phys
        move.w  #AIR_ACCEL, d2                  ; air: use air accel for both
        move.w  #AIR_ACCEL, d3
.have_phys:

        ; Check LEFT
        btst    #2, d6                          ; bit 2 = LEFT
        beq.s   .check_right

        ; LEFT held
        tst.w   d0
        ble.s   .accel_left
        sub.w   d3, d0
        bpl.s   .clamp_vel
        clr.w   d0
        bra.s   .clamp_vel
.accel_left:
        sub.w   d2, d0
        cmpi.w  #-TOP_SPEED, d0
        bge.s   .set_flip_left
        move.w  #-TOP_SPEED, d0
.set_flip_left:
        bset    #RF_XFLIP, SST_render_flags(a0)
        bra.s   .clamp_vel

.check_right:
        btst    #3, d6                          ; bit 3 = RIGHT
        beq.s   .no_input

        ; RIGHT held
        tst.w   d0
        bge.s   .accel_right
        add.w   d3, d0
        bmi.s   .clamp_vel
        clr.w   d0
        bra.s   .clamp_vel
.accel_right:
        add.w   d2, d0
        cmpi.w  #TOP_SPEED, d0
        ble.s   .set_flip_right
        move.w  #TOP_SPEED, d0
.set_flip_right:
        bclr    #RF_XFLIP, SST_render_flags(a0)
        bra.s   .clamp_vel

.no_input:
        ; No direction held — apply friction toward 0
        tst.w   d0
        beq.s   .clamp_vel
        bmi.s   .friction_neg
        sub.w   d3, d0
        bpl.s   .clamp_vel
        clr.w   d0
        bra.s   .clamp_vel
.friction_neg:
        add.w   d3, d0
        bmi.s   .clamp_vel
        clr.w   d0

.clamp_vel:
        move.w  d0, SST_x_vel(a0)

        ; --- Variable jump (cut short if button released while rising) ---
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .skip_var_jump
        move.w  SST_y_vel(a0), d0
        cmpi.w  #JUMP_CAP, d0
        bge.s   .skip_var_jump                  ; y_vel >= cap — not rising fast enough
        move.b  d6, d1
        andi.b  #BUTTON_B|BUTTON_C, d1
        bne.s   .skip_var_jump                  ; still held, maintain full jump
        move.w  #JUMP_CAP, SST_y_vel(a0)
.skip_var_jump:

        ; --- Gravity (only if airborne) ---
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .skip_gravity
        move.w  SST_y_vel(a0), d0
        addi.w  #GRAVITY, d0
        cmpi.w  #TERMINAL_VELOCITY, d0
        ble.s   .set_yvel
        move.w  #TERMINAL_VELOCITY, d0
.set_yvel:
        move.w  d0, SST_y_vel(a0)
.skip_gravity:

        ; --- Apply velocity to position ---
        jsr     ObjectMove

        ; --- Stub floor collision ---
        move.w  SST_y_pos(a0), d0               ; integer Y (high word of 16.16)
        cmpi.w  #STUB_FLOOR_Y, d0
        ble.s   .no_floor
        move.l  #STUB_FLOOR_Y<<16, SST_y_pos(a0)
        clr.w   SST_y_vel(a0)
        bclr    #ST_IN_AIR, SST_status(a0)
.no_floor:

        ; --- Animation selection ---
        btst    #ST_IN_AIR, SST_status(a0)
        bne.s   .anim_air
        tst.w   SST_x_vel(a0)
        beq.s   .anim_idle
        move.b  #0, SST_anim(a0)               ; walk
        bra.s   .do_anim
.anim_air:
        move.b  #2, SST_anim(a0)               ; roll/jump
        bra.s   .do_anim
.anim_idle:
        move.b  #1, SST_anim(a0)               ; idle
.do_anim:
        jsr     AnimateSprite

        ; --- DPLC art streaming ---
        movea.l _dplc_ptr(a0), a2
        movea.l _art_base(a0), a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC

        ; --- Draw ---
        jsr     Draw_Sprite
        rts
