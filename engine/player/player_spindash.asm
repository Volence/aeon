; Spindash — SHARED player ability state (all characters). Relocated out of
; sonic.asm: spindash is identical across the roster; the per-character part
; is only the spindash ANIMATION, which resolves through each character's own
; SST_anim_table via ANIM_SPINDASH. Entered from PState_Ground's trigger.
;
; Lives in the object code bank (reached via the shared Player_States table).

; -----------------------------------------------
; PState_Spindash — Sonic's spindash charge (a CHARACTER state BODY:
; character-specific state bodies live in character files like this
; one, but today the dispatch tables are shared and this row is
; hardwired — per-character dispatch-table indirection is future work
; for the second character (§11 closeout note); spec §3.1). Entered
; only from PState_Ground's trigger (down +
; jump-press at |gsp| < $100); the enter hook curled the box and zeroed
; gsp/velocities/charge.
;
; Classic S2 Obj01_Spindash semantics (order matters — decay FIRST,
; then rev with the clamp LAST, matching Sonic_ChargingSpindash):
;   down released → RELEASE: gsp = ±($800 + (charge>>8)·$80), $800-$C00
;   every frame   → decay: charge -= charge>>5 (asr floors — charge
;                   below $20 stops decaying; classic behavior, kept)
;   jump press    → rev: charge += $200, capped $800
; So a tap frame stores (old − old>>5) + $200: a single tap from 0
; stores exactly $200 (→ $900 release) and mashing holds $800 at frame
; boundaries (→ $C00 release).
; While charging the player is PINNED: no input/slope/gravity/wall
; probe and no Player_SlopeRepel (the classics skip it — a slip nudge
; would corrupt the pinned gsp). Only the floor pair runs (classic
; calls AnglePos and nothing else) so a floor yanked from under a
; charging player drops them — curled, charge discarded via the exit
; hook.
; In:  a0 = player SST, a4 = Player_Phys
; Out: none (release → PSTATE_ROLL and the roll frame runs NOW — the
;      classic launches on the release frame; floor loss → PSTATE_AIRBALL)
; Clobbers: d0-d7, a1-a2
; -----------------------------------------------
PState_Spindash:
        btst    #1, (Ctrl_1_Held).w             ; DOWN still held?
        beq.s   .release
        ; --- decay FIRST (classic order; runs on tap frames too, before
        ; the rev, so the rev's clamp is the last word) ---
        move.w  _pl_spindash(a0), d0
        beq.s   .rev
        move.w  d0, d1
        asr.w   #5, d1
        sub.w   d1, d0
        move.w  d0, _pl_spindash(a0)
.rev:
        ; --- rev: each buffered jump press adds $200, capped $800 (clamp
        ; last, classic — mashing holds exactly $800 at frame boundaries).
        ; Consuming Player_JumpBuffer (latched on the press edge) is the
        ; press test — the trigger consumed the initiating press, so a
        ; charge frame only sees fresh taps ---
        tst.b   (Player_JumpBuffer).w
        beq.s   .floor
        clr.b   (Player_JumpBuffer).w
        addi.w  #SPINDASH_CHARGE_STEP, _pl_spindash(a0)
      ifdef SOUND_DRIVER_ENABLED
        move.b  #SFXID_SPINDASH, d0
        jsr     Sound_PlaySFX
      endif
        cmpi.w  #SPINDASH_CHARGE_MAX, _pl_spindash(a0)
        bls.s   .floor
        move.w  #SPINDASH_CHARGE_MAX, _pl_spindash(a0)
.floor:
        ; --- floor maintenance (the classic AnglePos slot, reduced for
        ; zero speed: snap window = 0>>8 + 4 = 4, fixed −14 snap-up;
        ; mirrors PState_Ground's floor pair with speed = 0) ---
        jsr     Player_SensorFloor              ; d0 dist, d1 resolved angle
        cmpi.w  #-14, d0
        blt.s   .pinned                         ; embedded past the snap-up
                                                ; — classic ignores
        cmpi.w  #4, d0
        bgt.s   .floor_gone
        bsr.w   Player_SnapToSurface
        move.b  d1, SST_angle(a0)
.pinned:
        rts
.floor_gone:
        moveq   #PSTATE_AIRBALL, d0             ; still curled, not from a
        jmp     Player_SetState                 ; jump; exit hook discards
                                                ; the charge
.release:
        ; --- release: gsp = ±(SPINDASH_BASE + (charge>>8)·$80) — the
        ; closed form of the stock S2 table (research §8): charge 0 →
        ; $800, full $800 → $C00. Sign from facing. ---
        move.w  _pl_spindash(a0), d0
        lsr.w   #8, d0                          ; charge>>8 = 0..8
        lsl.w   #7, d0                          ; ·$80
        addi.w  #SPINDASH_BASE, d0
        btst    #ST_XFLIP, SST_status(a0)
        beq.s   .launch
        neg.w   d0
.launch:
        move.w  d0, _pl_gsp(a0)
        move.b  #16, (Camera_Spindash_Lag).w    ; classic 16-frame camera
                                                ; freeze — Task 10 wires the
                                                ; camera consume
        moveq   #PSTATE_ROLL, d0                ; release sfx; dust cleanup
                                                ; lives in exit hook when dust
      ifdef SOUND_DRIVER_ENABLED
        movem.l d0, -(sp)
        move.b  #SFXID_DASH, d0
        jsr     Sound_PlaySFX
        movem.l (sp)+, d0
      endif
        ; Drop any jump press buffered during the charge mash. The release
        ; frame runs .release (never .rev), so a jump press landing in the
        ; buffer window at release is NOT consumed — PState_Roll's jump-check
        ; (below) would then fire a spurious roll-jump: the jump SFX plays
        ; "in the air" right after launch AND collides with the dash SFX in
        ; the 1-byte mailbox (the quick-spindash "no follow-up noise"). A
        ; FRESH press after the launch still roll-jumps normally.
        clr.b   (Player_JumpBuffer).w
        bsr.w   Player_SetState
        jmp     PState_Roll                     ; classic: the release frame
                                                ; runs the full roll movement
                                                ; — the launch happens NOW
