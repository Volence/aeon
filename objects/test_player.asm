; Test player — controllable character with movement, gravity, jumping
; Uses Sonic sprite art (DPLC-loaded), reads P1 controller input

; Custom SST field offsets (shared layout with TestAnimated)
    ifndef _dplc_ptr
; MUST stay byte-identical to the guarded copy in the other DPLC user
; (test_animated.asm / test_player.asm) — only the first include assembles.
DplcV struct
dplc_ptr        ds.l 1                  ; DPLC table pointer (ROM)
art_base        ds.l 1                  ; uncompressed art base (ROM)
DplcV endstruct
        objvarsCheck DplcV_len
_dplc_ptr       = SST_sst_custom+DplcV_dplc_ptr
_art_base       = SST_sst_custom+DplcV_art_base
    endif
; Player-only layout: reserves the shared DPLC prefix, then debug_flag
TPlayerV struct
dplc_pair       ds.b DplcV_len          ; shared DPLC overlay prefix (see DplcV)
debug_flag      ds.b 1
TPlayerV endstruct
        objvarsCheck TPlayerV_len
_debug_flag     = SST_sst_custom+TPlayerV_debug_flag

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
DEBUG_FLY_SPEED         = 16            ; pixels per frame in debug mode
DEBUG_FLY_SPEED_FAST    = 48            ; pixels per frame when A held
STUB_FLOOR_Y            = 192           ; pixel Y for stub ground plane (used by object_test_state)

; -----------------------------------------------
; TestPlayer — init routine
; In:  a0 = SST pointer (slot already allocated)
; Out: none
; Clobbers: d0-d7, a0-a6
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
        ori.b   #4<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #32, SST_height_pixels(a0)
        move.b  #COLLISION_NONE, SST_collision_resp(a0)
        clr.b   SST_status(a0)                 ; start grounded (in_air clear)
        move.w  #objroutine(TestPlayer_Main), SST_code_addr(a0)

        ; Fall through to main for first frame
; -----------------------------------------------
; TestPlayer_Main — per-frame update
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
TestPlayer_Main:
        ; --- B press toggles debug free-flight mode ---
        ; d4 NOT d7: object routines must preserve a0/d7 (RunObjects loop
        ; contract). A d7.b clobber here overran the player slot loop by
        ; up to 255 slots — executing free-stack words as code offsets
        ; (the intermittent RAM-clobber / ILLEGAL INSTRUCTION root cause).
        move.b  (Ctrl_1_Press).w, d4
        btst    #4, d4                          ; BUTTON_B
        beq.s   .no_toggle
        tst.b   _debug_flag(a0)
        bne.s   .exit_debug
        ; Enter debug mode
        move.b  #1, _debug_flag(a0)
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #$A0FA, SST_art_tile(a0)
        move.b  #16, SST_height_pixels(a0)
        clr.b   SST_mapping_frame(a0)
        clr.w   SST_x_vel(a0)
        clr.w   SST_y_vel(a0)
        bra.s   .no_toggle
.exit_debug:
        clr.b   _debug_flag(a0)
        move.l  #Map_Sonic, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_SONIC,0,0), SST_art_tile(a0)
        move.b  #32, SST_height_pixels(a0)
        clr.b   SST_mapping_frame(a0)
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        bset    #ST_IN_AIR, SST_status(a0)
.no_toggle:

        tst.b   _debug_flag(a0)
        bne.w   TestPlayer_Debug
        ; Fall through to normal physics

        ; --- Snapshot on_object, then clear it ---
        move.b  SST_status(a0), d5
        bclr    #ST_ON_OBJECT, SST_status(a0)

        ; --- Read controller (d4 = press: d7 is the RunObjects counter) ---
        move.b  (Ctrl_1_Held).w, d6
        move.b  (Ctrl_1_Press).w, d4

        ; --- Jump check (C only, grounded only) ---
        btst    #ST_IN_AIR, SST_status(a0)
        bne.s   .no_jump_start
        btst    #5, d4                          ; BUTTON_C
        beq.s   .no_jump_start
        move.w  #JUMP_VELOCITY, SST_y_vel(a0)
        bset    #ST_IN_AIR, SST_status(a0)
        bclr    #ST_ON_OBJECT, SST_status(a0)
.no_jump_start:

        ; --- Horizontal movement ---
        move.w  SST_x_vel(a0), d0

        move.w  #ACCELERATION, d2
        move.w  #DECELERATION, d3
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .have_phys
        move.w  #AIR_ACCEL, d2
        move.w  #AIR_ACCEL, d3
.have_phys:

        btst    #2, d6                          ; LEFT
        beq.s   .check_right

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
        bset    #ST_XFLIP, SST_status(a0)
        bra.s   .clamp_vel

.check_right:
        btst    #3, d6                          ; RIGHT
        beq.s   .no_input

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
        bclr    #ST_XFLIP, SST_status(a0)
        bra.s   .clamp_vel

.no_input:
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

        ; --- Variable jump (cut short if C released while rising) ---
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .skip_var_jump
        move.w  SST_y_vel(a0), d0
        cmpi.w  #JUMP_CAP, d0
        bge.s   .skip_var_jump
        btst    #5, d6                          ; BUTTON_C held
        bne.s   .skip_var_jump
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

        ; --- Floor collision via tile cache ---
        ; Skip when rising — only check when falling or grounded.
        ; Stub collision marks sky tiles as solid, so checking while
        ; rising would snap the player into sky cells.
        btst    #ST_IN_AIR, SST_status(a0)
        beq.s   .do_floor
        tst.w   SST_y_vel(a0)
        bmi.s   .no_floor
.do_floor:
        movem.l a0, -(sp)
        jsr     Collision_FloorSensors
        movem.l (sp)+, a0
        tst.b   d2
        beq.s   .no_floor                      ; air tile — no surface
        tst.w   d0
        bgt.s   .no_floor
        cmpi.w  #-16, d0
        blt.s   .no_floor                      ; too deep — ignore
        ext.l   d0
        lsl.l   #8, d0
        lsl.l   #8, d0                         ; distance → 16.16
        add.l   d0, SST_y_pos(a0)
        clr.w   SST_y_vel(a0)
        bclr    #ST_IN_AIR, SST_status(a0)
        bra.s   .floor_done
.no_floor:
        bset    #ST_IN_AIR, SST_status(a0)
.floor_done:

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
        jmp     Draw_Sprite

; -----------------------------------------------
; TestPlayer_Debug — free-flight debug mode (yellow square)
; D-pad moves at DEBUG_FLY_SPEED px/frame, B to exit
; -----------------------------------------------
TestPlayer_Debug:
        move.b  (Ctrl_1_Held).w, d0
        moveq   #DEBUG_FLY_SPEED, d1
        btst    #6, d0                          ; BUTTON_A = turbo
        beq.s   .dbg_speed_ok
        moveq   #DEBUG_FLY_SPEED_FAST, d1
.dbg_speed_ok:
        swap    d1                              ; d1 = speed<<16

        btst    #2, d0                          ; LEFT
        beq.s   .dbg_check_right
        sub.l   d1, SST_x_pos(a0)
.dbg_check_right:
        btst    #3, d0                          ; RIGHT
        beq.s   .dbg_check_up
        add.l   d1, SST_x_pos(a0)
.dbg_check_up:
        btst    #0, d0                          ; UP
        beq.s   .dbg_check_down
        sub.l   d1, SST_y_pos(a0)
.dbg_check_down:
        btst    #1, d0                          ; DOWN
        beq.s   .dbg_draw
        add.l   d1, SST_y_pos(a0)
.dbg_draw:
        jmp     Draw_Sprite
