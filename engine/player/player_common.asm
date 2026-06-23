; Player frame skeleton — state machine, dispatch, shared services (§5 Task 5)
;
; Owns the player frame: debug-fly escape → physics table (a4) →
; quadrant → jump buffer → state dispatch → history rings → display tail.
; The state bodies live in player_ground.asm / player_air.asm (reached
; only via the Player_States offset table below); characters contribute
; asset/physics data + ability states (sonic.asm) — never forks inside
; shared routines (spec §3.1 inversion of the sonic_hack split).
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
skid_latch       ds.b 1      ; nonzero = hold the skid pose (display latch)
getup_timer      ds.b 1      ; >0 = play ANIM_GETUP one-shot, counts down
look_offset      ds.b 1      ; camera look/duck pan seam — stays 0 this pass
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
_pl_skid_latch   = SST_sst_custom+PlayerV_skid_latch
_pl_getup        = SST_sst_custom+PlayerV_getup_timer
_pl_look_offset  = SST_sst_custom+PlayerV_look_offset

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
; setStandingSize / setBallSize — the two collision boxes (sizes are
; 2r+1; sensors halve by lsr → standing 9/19, ball 7/14 — the exact
; classic radii). The enter hooks are the ONE writer of these fields
; and of the paired ±CURL_Y_SHIFT y-shift (spec §3.3) — see
; PHook_EnsureStanding/PHook_EnsureBall.
; In: a0 = player SST
; -----------------------------------------------
setStandingSize macro
        move.b  #PLAYER_X_RADIUS*2+1, SST_width_pixels(a0)
        move.b  #PLAYER_Y_RADIUS*2+1, SST_height_pixels(a0)
        endm

setBallSize macro
        move.b  #BALL_X_RADIUS*2+1, SST_width_pixels(a0)
        move.b  #BALL_Y_RADIUS*2+1, SST_height_pixels(a0)
        endm

; -----------------------------------------------
; maskOpposingLR — L+R held together = neither (bug #10).
; In: heldReg = data register holding the held-button bits (modified:
;     masked to LEFT|RIGHT, zeroed when both are down)
; Fixed internal label: expand at most once per global-label scope
; (current expansions: Ground_Move, PState_Roll, PState_AirShared —
; one each).
; -----------------------------------------------
maskOpposingLR macro heldReg
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, heldReg
        cmpi.b  #BUTTON_LEFT|BUTTON_RIGHT, heldReg
        bne.s   .lr_masked
        moveq   #0, heldReg
.lr_masked:
        endm

; -----------------------------------------------
; distToFix — widen a signed pixel distance (.w) into a 16.16 delta
; (dist<<16) for adding to the SST_x_pos/SST_y_pos longwords
; In:  dreg.w = signed px distance
; Out: dreg.l = dist<<16
; -----------------------------------------------
distToFix macro dreg
        ext.l   dreg
        swap    dreg
        clr.w   dreg
        endm

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
        move.b  #ANIM_IDLE, SST_anim(a0)        ; Player_Display re-selects per frame
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        ori.b   #4<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        setStandingSize
        move.b  #COLLISION_NONE, SST_collision_resp(a0)
        clr.b   SST_status(a0)
        clr.b   SST_angle(a0)
        clr.b   SST_layer(a0)
        clr.w   _pl_gsp(a0)
        clr.w   _pl_move_lock(a0)
        clr.w   _pl_spindash(a0)
        clr.b   _pl_status2(a0)
        clr.b   _pl_stick_convex(a0)
        clr.b   _pl_skid_latch(a0)
        clr.b   _pl_getup(a0)
        clr.b   _pl_look_offset(a0)
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
        ; press bits read ONCE for the frame — d6 survives the debug
        ; toggle calls (DebugEnter clobbers none, DebugExit d0-d2/a1-a2)
        ; and feeds both the B-toggle and the jump-buffer latch
        move.b  (Ctrl_1_Press).w, d6
        ; --- debug-fly toggle (B press) ---
        btst    #4, d6                          ; BUTTON_B
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
        andi.b  #BUTTON_JUMP_MASK, d6
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

        ; --- on-object bit: 1-frame-lagged (TouchResponse runs AFTER this
        ; frame and SETS it; the states above read the LIVE bit set by
        ; LAST tick's TouchResponse). Clear it every normal frame so a
        ; walk-off works: this tick's TouchResponse re-sets it only if the
        ; player is still standing on the solid. Debug-fly never reaches
        ; here (it returns via Player_DebugMove before the dispatch), so
        ; the bit is only ever touched in the physics path. a0 is the
        ; Player_1 SST throughout (states preserve a0 — RunObjects/display
        ; contract). ---
        bclr    #ST_ON_OBJECT, SST_status(a0)

        bsr.w   Player_LevelBound               ; classic LevelBound, post-
                                                ; dispatch (placement rationale
                                                ; at the routine header)

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
; Player_Display — classify the animation, advance it, stream art, draw.
; In:  a0 = player SST
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
Player_Display:
        bsr.w   Player_Animate                  ; sets SST_anim + d3 (dyn hold)
        jsr     AnimateSprite
        jmp     Sonic_LoadArt                   ; character dispatch (Tails/Knux
                                                ; replace via roster later)

; -----------------------------------------------
; Player_Animate — read-only animation classifier. Reads state/status/input
; and (at rest) one ledge sensor; writes ONE ANIM_* id to SST_anim and the
; speed-scaled hold to d3. Mutates only the display transient skid_latch.
; Priority: spindash > ball > skid > push > (rest: getup > duck > lookup >
; balance > idle) > run/walk.
; In:  a0 = player SST
; Out: SST_anim set; d3.b = dynamic per-anim hold (for DUR_DYNAMIC scripts)
; Clobbers: d0-d2, d4, a1-a2 (d3 is an output). The balance path additionally
;           trashes d5-d6 via Player_AtLedgeEdge — caller (Player_Display, a
;           frame-tail routine) keeps no live d5/d6 across this call.
; -----------------------------------------------
Player_Animate:
        ; speed-scaled hold for DUR_DYNAMIC scripts (walk/run/roll):
        ; hold = max(0,($800-|gsp|)>>8). Computed up front; only the ball and
        ; walk/run paths consume d3 and neither clobbers it. The balance path
        ; clobbers d3 (sensor) but leads to a FIXED-duration anim, so it's moot.
        move.w  _pl_gsp(a0), d0
        bpl.s   .abs_ok
        neg.w   d0
.abs_ok:
        move.w  #$800, d4
        sub.w   d0, d4
        bpl.s   .hold_ok
        moveq   #0, d4
.hold_ok:
        lsr.w   #8, d4
        move.b  d4, d3

        move.b  _pl_state(a0), d0
        ; (1) spindash
        cmpi.b  #PSTATE_SPINDASH, d0
        bne.s   .not_spindash
        move.b  #ANIM_SPINDASH, SST_anim(a0)
        rts
.not_spindash:
        ; (2) ball: ROLL + curled air (JUMP/ROLLJUMP/AIRBALL >= PSTATE_JUMP)
        cmpi.b  #PSTATE_JUMP, d0
        bhs.s   .ball
        cmpi.b  #PSTATE_ROLL, d0
        bne.s   .uncurled
.ball:
        move.b  #ANIM_ROLL, SST_anim(a0)
        rts
.uncurled:
        ; GROUND or uncurled AIR. Airborne keeps the walk/run cycle; the
        ; grounded-only conditions are gated below.
        btst    #ST_IN_AIR, SST_status(a0)
        bne.w   .walk_or_run

        ; (3) skid — grounded, opposing input held, |gsp| >= PHYS_SKID_MIN.
        ; Latch holds the pose through the brake WHILE opposing input is held;
        ; cleared at rest or when the opposing input is released.
        move.w  _pl_gsp(a0), d1
        beq.s   .skid_drop                      ; stopped -> clear latch
        move.b  (Ctrl_1_Held).w, d2
        tst.w   d1
        bmi.s   .skid_left
        btst    #BUTTON_LEFT_BIT, d2            ; moving right: opposing = LEFT
        beq.s   .skid_drop
        bra.s   .skid_opposing
.skid_left:
        btst    #BUTTON_RIGHT_BIT, d2           ; moving left: opposing = RIGHT
        beq.s   .skid_drop
.skid_opposing:
        tst.b   _pl_skid_latch(a0)
        bne.s   .skid_show                      ; already latched -> keep (no new sfx)
        move.w  d1, d2
        bpl.s   .skid_abs
        neg.w   d2
.skid_abs:
        cmpi.w  #PHYS_SKID_MIN, d2
        blo.s   .not_skid                       ; opposing but too slow to arm
        ; fresh-arm edge — fire the skid SFX once before latching
      ifdef SOUND_DRIVER_ENABLED
        moveq   #SFXID_SKID, d0
        jsr     Sound_PlaySFX
      endif
.skid_show:
        st      _pl_skid_latch(a0)
        move.b  #ANIM_SKID, SST_anim(a0)
        rts
.skid_drop:
        clr.b   _pl_skid_latch(a0)
.not_skid:

        ; (4) push — grounded, ST_PUSHING (facing-aware bit from ground code)
        btst    #ST_PUSHING, SST_status(a0)
        beq.s   .not_push
        move.b  #ANIM_PUSH, SST_anim(a0)
        rts
.not_push:
        ; rest vs moving
        tst.w   _pl_gsp(a0)
        bne.s   .walk_or_run

        ; --- at rest ---
        ; get-up one-shot: mechanism in place; nothing arms _pl_getup in
        ; gameplay this pass (in-game get-up trigger deferred).
        tst.b   _pl_getup(a0)
        beq.s   .rest_input
        subq.b  #1, _pl_getup(a0)
        move.b  #ANIM_GETUP, SST_anim(a0)
        rts
.rest_input:
        ; (5) duck
        btst    #BUTTON_DOWN_BIT, (Ctrl_1_Held).w
        beq.s   .not_duck
        move.b  #ANIM_DUCK, SST_anim(a0)
        rts
.not_duck:
        ; (6) look up
        btst    #BUTTON_UP_BIT, (Ctrl_1_Held).w
        beq.s   .not_lookup
        move.b  #ANIM_LOOKUP, SST_anim(a0)
        rts
.not_lookup:
        ; (9) balance at a ledge edge — (7)/(8) in the priority table are
        ; run/walk, handled below in .walk_or_run (the moving branch)
        jsr     Player_AtLedgeEdge              ; beq = supported
        beq.s   .idle
        move.b  #ANIM_BALANCE, SST_anim(a0)
        rts
.idle:
        move.b  #ANIM_IDLE, SST_anim(a0)
        rts

.walk_or_run:
        move.w  _pl_gsp(a0), d1
        bpl.s   .wr_abs
        neg.w   d1
.wr_abs:
        cmpi.w  #ANIM_RUN_THRESHOLD, d1
        blt.s   .walk
        move.b  #ANIM_RUN, SST_anim(a0)
        rts
.walk:
        move.b  #ANIM_WALK, SST_anim(a0)
        rts

Player_States:
        dc.w    PState_Ground-Player_States     ; PSTATE_GROUND
        dc.w    PState_Roll-Player_States       ; PSTATE_ROLL (player_ground.asm)
        dc.w    PState_Spindash-Player_States   ; PSTATE_SPINDASH (sonic.asm —
                                                ; character state; cross-file is
                                                ; fine, same object code bank)
        dc.w    PState_Air-Player_States        ; PSTATE_AIR
        dc.w    PState_Jump-Player_States       ; PSTATE_JUMP
        dc.w    PState_RollJump-Player_States   ; PSTATE_ROLLJUMP
        dc.w    PState_AirBall-Player_States    ; PSTATE_AIRBALL
Player_States_End:
    if (Player_States_End-Player_States)/2 <> PSTATE_COUNT
        error "Player_States table out of sync with PSTATE_*"
    endif

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
        dc.w    PHook_RollEnter-PState_EnterHooks   ; ROLL
        dc.w    PHook_SpindashEnter-PState_EnterHooks ; SPINDASH
        dc.w    PHook_AirEnter-PState_EnterHooks    ; AIR (uncurled)
        dc.w    PHook_AirBallEnter-PState_EnterHooks ; JUMP
        dc.w    PHook_AirBallEnter-PState_EnterHooks ; ROLLJUMP
        dc.w    PHook_AirBallEnter-PState_EnterHooks ; AIRBALL
PState_EnterHooks_End:
    if (PState_EnterHooks_End-PState_EnterHooks)/2 <> PSTATE_COUNT
        error "PState_EnterHooks table out of sync with PSTATE_*"
    endif

PState_ExitHooks:
        dc.w    PHook_Null-PState_ExitHooks         ; GROUND
        dc.w    PHook_Null-PState_ExitHooks         ; ROLL
        dc.w    PHook_SpindashExit-PState_ExitHooks ; SPINDASH
        dc.w    PHook_Null-PState_ExitHooks         ; AIR
        dc.w    PHook_Null-PState_ExitHooks         ; JUMP
        dc.w    PHook_Null-PState_ExitHooks         ; ROLLJUMP
        dc.w    PHook_Null-PState_ExitHooks         ; AIRBALL
PState_ExitHooks_End:
    if (PState_ExitHooks_End-PState_ExitHooks)/2 <> PSTATE_COUNT
        error "PState_ExitHooks table out of sync with PSTATE_*"
    endif

; ===== Enter/exit hooks — the ONE writer for width/height, curl
; y-shift, collision-mode resets, and anim latches (spec §3.3).
; NOTHING outside these hooks may touch those fields — the sole tolerated
; exception is the debug-fly art swap, which sits outside the state
; machine entirely. Hooks preserve a0/d0/d7.
PHook_Null:
        rts

PHook_GroundEnter:
        bsr.s   PHook_EnsureStanding            ; uncurl (jump/ball landings;
                                                ; down-held landings go straight
                                                ; to ROLL via Air_LandState — no
                                                ; uncurl flicker)
        bclr    #ST_IN_AIR, SST_status(a0)
        rts

PHook_AirEnter:                                 ; uncurled airborne
        bsr.s   PHook_EnsureStanding
        bset    #ST_IN_AIR, SST_status(a0)
        rts

PHook_AirBallEnter:                             ; JUMP / ROLLJUMP / AIRBALL
        bsr.s   PHook_EnsureBall
        bset    #ST_IN_AIR, SST_status(a0)
        rts

PHook_RollEnter:                                ; grounded ball — entered from
        bsr.s   PHook_EnsureBall                ; GROUND (roll start), SPINDASH
        bclr    #ST_IN_AIR, SST_status(a0)      ; (release), or a curled/down-
        rts                                     ; held landing (air → cleared)

PHook_SpindashEnter:                            ; entered only from GROUND —
        bsr.s   PHook_EnsureBall                ; the player is pinned charging
        bclr    #ST_IN_AIR, SST_status(a0)
        clr.w   _pl_gsp(a0)
        clr.w   SST_x_vel(a0)
        clr.w   SST_y_vel(a0)
        clr.w   _pl_spindash(a0)                ; the initiating press is rev 0
        rts                                     ; TODO: dust object. Rev SFX fired per-tap in player_spindash.asm

PHook_SpindashExit:
        clr.w   _pl_spindash(a0)                ; release converts charge→gsp
        rts                                     ; BEFORE SetState; an aborted
                                                ; charge (floor crumbled) just
                                                ; drops it. TODO: dust cleanup

; bug #5 fix (structural): the collision box lives ONLY here — every
; curled state gets ball radii with the symmetric ±CURL_Y_SHIFT
; feet-planted shift, so the classic roll-jump 5px size mismatch cannot
; exist. Enter-hook-owns-it pattern: each enter hook ENSURES its size,
; keyed on the current height byte — idempotent and correct for every
; transition path (GROUND→JUMP curls, any curled→GROUND/AIR uncurls,
; curled→curled is a no-op).
;
; ST_ROLLING is tied to the SAME pair so the "in ball form" bit can
; never desync from the radii (objects will read it; nothing does yet).
; It is set/cleared UNCONDITIONALLY — outside the height-keyed guard —
; because the debug-fly art swap writes a third height (16) outside the
; state machine: a debug round-trip re-enters via SetState and the hook
; must repair the bit even when the height byte needs no curl work.
PHook_EnsureStanding:
        bclr    #ST_ROLLING, SST_status(a0)
        cmpi.b  #BALL_Y_RADIUS*2+1, SST_height_pixels(a0)
        bne.s   .keep                           ; not curled (incl. debug 16)
        setStandingSize
        subi.l  #CURL_Y_SHIFT<<16, SST_y_pos(a0)
.keep:
        rts

PHook_EnsureBall:
        bset    #ST_ROLLING, SST_status(a0)
        cmpi.b  #BALL_Y_RADIUS*2+1, SST_height_pixels(a0)
        beq.s   .keep                           ; already curled
        setBallSize
        addi.l  #CURL_Y_SHIFT<<16, SST_y_pos(a0)
.keep:
        rts

; -----------------------------------------------
; Player_SnapToSurface — move the player a signed pixel distance along
; the floor pair's PROBE axis. Mirrors Player_SensorFloor's case table
; EXACTLY (player_sensors.asm Player_SensorSurface .case_table — probe
; direction per quadrant), so a pair distance feeds straight back in:
;   quadrant 0: Collision_ProbeDown  → y_pos += dist
;   quadrant 1: Collision_ProbeLeft  → x_pos −= dist
;   quadrant 2: Collision_ProbeUp    → y_pos −= dist
;   quadrant 3: Collision_ProbeRight → x_pos += dist
; In:  a0 = player SST, d0.w = signed surface distance (px)
; Out: none
; Clobbers: d0, d2
; -----------------------------------------------
Player_SnapToSurface:
        distToFix d0
        move.b  (Player_Quadrant).w, d2
        beq.s   .down                           ; floor mode — common case
        subq.b  #2, d2
        bmi.s   .left                           ; quadrant 1
        beq.s   .up                             ; quadrant 2
        add.l   d0, SST_x_pos(a0)               ; quadrant 3
        rts
.down:
        add.l   d0, SST_y_pos(a0)
        rts
.left:
        sub.l   d0, SST_x_pos(a0)
        rts
.up:
        sub.l   d0, SST_y_pos(a0)
        rts

; Classic Sonic_LevelBound margins: the player center may approach the
; left playable edge to 16px and the right edge to 24px (asymmetric in
; the originals — kept verbatim). Bottom margin: detection slack below
; the playable bottom; must exceed the per-frame fall cap
; (PHYS_FALL_CAP = 16px) so a single frame's fall can never overshoot
; the guard transiently.
PBOUND_LEFT_MARGIN   = 16
PBOUND_RIGHT_MARGIN  = 24
PBOUND_BOTTOM_MARGIN = 48
    if PBOUND_BOTTOM_MARGIN <= (PHYS_FALL_CAP>>8)
      error "PBOUND_BOTTOM_MARGIN must exceed the per-frame fall cap"
    endif

; -----------------------------------------------
; Player_LevelBound — clamp the player to the act's playable bounds
; (classic Sonic_LevelBound, adapted to world coordinates)
;
; PLACEMENT: called once from Player_Main right after the state
; dispatch, before the history rings. The classics run LevelBound
; inside each movement state; a single post-dispatch call clamps the
; same end-of-frame position without per-state duplication, and the
; history rings then record the CLAMPED position. Debug-fly never
; reaches this (Player_Main branches to Player_DebugMove before the
; dispatch) — bounds are deliberately SKIPPED in debug-fly, which is
; for inspecting anywhere, including off-world.
;
; Continuous-scroll: X/Y are world coordinates spanning the whole act,
; so the bounds are the act's world extents directly (no teleport-edge
; conditioning — the camera spans the level and there are no window
; seams to clamp around):
;   left  — world origin: bound = PBOUND_LEFT_MARGIN (x ≥ 0 + margin).
;   right — level_width − PBOUND_RIGHT_MARGIN, where
;           level_width = grid_w << SECTION_SIZE_SHIFT (px).
;   bottom — playable bottom = (grid_h << SECTION_SIZE_SHIFT) −
;           SCREEN_HEIGHT (the camera stops one screen above the world
;           floor). Phase 1 conservative clamp.
;   top   — NO clamp (classic allows above-screen travel).
;
; On X clamp: integer x written with subpixel zeroed, x_vel and gsp
; cleared (classic). On bottom trip: y is clamped to the playable bottom
; edge and y_vel zeroed (a placeholder until death/respawn exists) — with
; editor-authored / S&K collision a fall through air or an erased floor is
; by design (pits, WIP levels), not a bug.
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
Player_LevelBound:
        movea.l (Current_Act_Ptr).w, a1
        move.w  SST_x_pos(a0), d0               ; integer X (16.16 high word)

        ; --- left bound: world [0, level_width) ---
        move.w  #PBOUND_LEFT_MARGIN, d1
        cmp.w   d1, d0
        blt.s   .clamp_x
        ; --- right bound: world level_width − margin ---
        ;     level_width = grid_w << SECTION_SIZE_SHIFT (split 8+3 for AS).
        moveq   #0, d1
        move.w  Act_grid_w(a1), d1
        lsl.l   #8, d1
        lsl.l   #3, d1                          ; grid_w × 2048 = level_width (px)
        subi.w  #PBOUND_RIGHT_MARGIN, d1
        cmp.w   d1, d0
        ble.s   .x_done
.clamp_x:
        move.w  d1, SST_x_pos(a0)
        clr.w   SST_x_pos+2(a0)                 ; subpixel zeroed (classic)
        clr.w   SST_x_vel(a0)
        clr.w   _pl_gsp(a0)
.x_done:
        ; --- bottom guard (no top clamp) ---
        ;     playable bottom = (grid_h << SECTION_SIZE_SHIFT) − SCREEN_HEIGHT
        ;     (camera stops one screen above the world floor; split 8+3 for AS).
        move.w  SST_y_pos(a0), d0               ; integer Y
        moveq   #0, d1
        move.w  Act_grid_h(a1), d1
        lsl.l   #8, d1
        lsl.l   #3, d1
        subi.w  #SCREEN_HEIGHT, d1              ; d1 = playable bottom edge (world)
        move.w  d1, d2
        addi.w  #PBOUND_BOTTOM_MARGIN, d2
        cmp.w   d2, d0
        ble.s   .y_ok                           ; above the bottom guard → done
        ; --- player tripped the bottom edge: dispatch on the act's edge_mode ---
        move.b  Act_edge_mode(a1), d2
        cmpi.b  #EDGE_WRAP_V, d2
        beq.s   .edge_wrap
        cmpi.b  #EDGE_KILL, d2
        beq.s   .edge_kill
        ; EDGE_CLAMP (default) — clamp to the bottom edge (unchanged behavior).
        ; With editor-authored / S&K collision the player can fall through air or
        ; an unpainted/erased floor by design (pits, a WIP level with no ground
        ; yet), so this is expected, not a bug — just clamp (placeholder until
        ; death/respawn exists).
.edge_clamp:
        move.w  d1, SST_y_pos(a0)               ; d1 still = playable bottom edge
        clr.w   SST_y_pos+2(a0)
        clr.w   SST_y_vel(a0)
.y_ok:
        rts
.edge_wrap:
        ; EDGE_WRAP_V — vertical "fall-forever" wrap (not implemented; current
        ; build uses EDGE_CLAMP). A correct wrap is NOT a player-side clamp swap: it
        ; is an atomic live-set shift by ±level_height (Camera_Y + Player y_pos +
        ; every active object y_pos + every active ring engine_Y + the tile-cache
        ; world-row cursors, then re-derive the entity window) — AND it requires the
        ; camera Y clamp (camera.asm .clamp_y) to become edge-mode-aware, with the
        ; wrap triggered on Camera_Y >= level_height (NOT the player) so every world
        ; coordinate stays >= 0 and the section lookup needs no mod. Full design +
        ; shift-list: spec §10 (continuous-scroll-traversal-design). Until built: clamp.
        bra.s   .edge_clamp
.edge_kill:
        ; EDGE_KILL — death pit. No death/respawn system exists yet, so this records
        ; intent and clamps meanwhile (the player can't fall into void with nothing
        ; to catch them). When the death system exists it consumes Player_Death_Pending
        ; and owns the kill/respawn; this stays the single trigger point. Architected
        ; from the start, not faked.
        st      (Player_Death_Pending).w        ; set the death-pending flag ($FF)
        bra.s   .edge_clamp                     ; clamp until the death system exists

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
        setStandingSize
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

