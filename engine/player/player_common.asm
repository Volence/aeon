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
; (current expansions: Ground_Move, PState_AirShared — one each).
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
; Player_Display — anim select from state + gsp, then the shared tail
; (AnimateSprite → per-character DPLC immediates → Draw_Sprite)
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
Player_Display:
        cmpi.b  #PSTATE_JUMP, _pl_state(a0)
        bhs.s   .anim_ball                      ; JUMP/ROLLJUMP/AIRBALL curled
        ; grounded states + uncurled AIR: walk/idle by gsp (the classic
        ; keeps the walk cycle while falling uncurled; gsp holds the
        ; last ground speed through AIR)
        ; TODO(Task 8): PSTATE_ROLL wants the ball anim — grounded states
        ; all read walk/idle until rolling exists
        tst.w   _pl_gsp(a0)
        bne.s   .anim_walk
        move.b  #ANIM_IDLE, SST_anim(a0)
        bra.s   .animate
.anim_walk:
        clr.b   SST_anim(a0)                    ; ANIM_WALK (= 0)
        bra.s   .animate
.anim_ball:
        move.b  #ANIM_BALL, SST_anim(a0)
.animate:
        jsr     AnimateSprite
        jmp     Sonic_LoadArt                   ; character dispatch when the
                                                ; roster exists (Tails/Knux)

Player_States:
        dc.w    PState_Ground-Player_States     ; PSTATE_GROUND
        dc.w    PState_Ground-Player_States     ; PSTATE_ROLL — TODO(Task 8)
        dc.w    PState_Ground-Player_States     ; PSTATE_SPINDASH — TODO(Task 8)
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
        dc.w    PHook_Null-PState_EnterHooks        ; ROLL — TODO(Task 8): ball radii + curl y-shift
        dc.w    PHook_Null-PState_EnterHooks        ; SPINDASH — TODO(Task 8)
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
        dc.w    PHook_Null-PState_ExitHooks         ; SPINDASH — TODO(Task 8): dust cleanup
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
                                                ; roll landings are Task 8)
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

; bug #5 fix (structural): the collision box lives ONLY here — every
; curled state gets ball radii with the symmetric ±CURL_Y_SHIFT
; feet-planted shift, so the classic roll-jump 5px size mismatch cannot
; exist. Enter-hook-owns-it pattern: each enter hook ENSURES its size,
; keyed on the current height byte — idempotent and correct for every
; transition path (GROUND→JUMP curls, any curled→GROUND/AIR uncurls,
; curled→curled is a no-op).
PHook_EnsureStanding:
        cmpi.b  #BALL_Y_RADIUS*2+1, SST_height_pixels(a0)
        bne.s   .keep                           ; not curled (incl. debug 16)
        setStandingSize
        subi.l  #CURL_Y_SHIFT<<16, SST_y_pos(a0)
.keep:
        rts

PHook_EnsureBall:
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
; (PHYS_FALL_CAP = 16px) so a pending down-teleport (Section_Check runs
; AFTER RunObjects) can never trip the guard transiently.
PBOUND_LEFT_MARGIN   = 16
PBOUND_RIGHT_MARGIN  = 24
PBOUND_BOTTOM_MARGIN = 48
    if PBOUND_BOTTOM_MARGIN <= (PHYS_FALL_CAP>>8)
      error "PBOUND_BOTTOM_MARGIN must exceed the per-frame fall cap"
    endif

; -----------------------------------------------
; Player_LevelBound — clamp the player to the act's playable bounds
; (classic Sonic_LevelBound, adapted to the slot-window coordinates)
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
; Engine X/Y are window coordinates (2 sections per axis from
; SLOT_ORIGIN_L/_U, rebased by Section_Teleport*). A playable bound
; only EXISTS where the matching teleport is unavailable — clamping at
; a live teleport edge would hold the player below the threshold
; (Section_Check reads Player_1's position AFTER RunObjects) and
; freeze streaming. So each clamp mirrors Section_Check's skip
; conditions exactly:
;   left  — slot 0 holds sec_x 0 (BWD teleport skipped): bound =
;           Act_cam_min_x. Same act field the camera clamps to, minus
;           its §4.2 PREVIEW_PIXELS extension, which is camera-only:
;           the preview region is render-ahead, not playable ground.
;   right — FWD teleport skipped, two cases (same split as the
;           camera's .check_max_x): slot 1 void (act edge on an
;           odd-width grid) → bound = slot 0's right edge
;           (SLOT_ORIGIN_L+SECTION_SIZE); slot 1 is the last grid
;           column → bound = the window's right edge
;           (SLOT_ORIGIN_L+SECTION_SHIFT). NOT Act_cam_max_x: that
;           field is camera-space slop ("approximate" — $1880 for OJZ
;           act 1, past the $1200 window, so it never binds) and a
;           bound past the window edge is the void-walk failure this
;           routine guards. The window edge IS the act's right
;           playable bound whenever the last column sits in slot 1.
;   bottom — playable bottom = Act_cam_max_y + SCREEN_HEIGHT (the act
;           data's own statement of the bottom edge; the camera stops
;           one screen above it). Checked UNCONDITIONALLY: when a down
;           teleport is available the player can only be transiently
;           below the window bottom by one frame's fall (≤16px <
;           margin), so a trip always means a real collision/streaming
;           bug — including "the teleport that should have caught this
;           never fired".
;   top   — NO clamp (classic allows above-screen travel).
;
; On X clamp: integer x written with subpixel zeroed, x_vel and gsp
; cleared (classic). On bottom trip: DEBUG builds RaiseError — a
; player below the world during §5 development is always a bug we
; want loud; release builds clamp y and zero y_vel as a placeholder
; until death/respawn exists.
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
Player_LevelBound:
        movea.l (Current_Act_Ptr).w, a1
        move.w  SST_x_pos(a0), d0               ; integer X (16.16 high word)

        ; --- left bound: only where BWD teleport is unavailable ---
        tst.b   (Slot_Section_Map).w
        bne.s   .left_open                      ; slot 0 sec_x > 0 → teleport owns the edge
        move.w  Act_cam_min_x(a1), d1
        addi.w  #PBOUND_LEFT_MARGIN, d1
        cmp.w   d1, d0
        blt.s   .clamp_x
.left_open:
        ; --- right bound: only where FWD teleport is unavailable ---
        move.b  (Slot_Section_Map+2).w, d2      ; slot 1 sec_x
        cmpi.b  #SEC_VOID, d2
        bne.s   .right_in_grid
        move.w  #SLOT_ORIGIN_L+SECTION_SIZE-PBOUND_RIGHT_MARGIN, d1
        bra.s   .right_test
.right_in_grid:
        addq.b  #1, d2                          ; next-FWD sec_x
        cmp.b   Act_grid_w+1(a1), d2            ; grid_w is a word; low byte at +1
        bcs.s   .x_done                         ; < grid_w → FWD teleport owns the edge
        move.w  #SLOT_ORIGIN_L+SECTION_SHIFT-PBOUND_RIGHT_MARGIN, d1
.right_test:
        cmp.w   d1, d0
        ble.s   .x_done
.clamp_x:
        move.w  d1, SST_x_pos(a0)
        clr.w   SST_x_pos+2(a0)                 ; subpixel zeroed (classic)
        clr.w   SST_x_vel(a0)
        clr.w   _pl_gsp(a0)
.x_done:
        ; --- bottom guard (no top clamp) ---
        move.w  SST_y_pos(a0), d0               ; integer Y
        move.w  Act_cam_max_y(a1), d1
        addi.w  #SCREEN_HEIGHT, d1              ; d1 = playable bottom edge
        move.w  d1, d2
        addi.w  #PBOUND_BOTTOM_MARGIN, d2
        cmp.w   d2, d0
        ble.s   .y_ok
    ifdef __DEBUG__
        RaiseError "Player below world: y=%<.w d0> bottom=%<.w d1> (collision/streaming bug)"
    else
        move.w  d1, SST_y_pos(a0)               ; placeholder until death/respawn exists
        clr.w   SST_y_pos+2(a0)
        clr.w   SST_y_vel(a0)
    endif
.y_ok:
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
