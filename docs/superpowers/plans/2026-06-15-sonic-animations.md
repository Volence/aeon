# Sonic Animations + Shared Spindash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author Sonic's full normal-play animation set, add generalized speed-scaled animation timing, relocate spindash into shared (all-character) player code, and build a debug anim-viewer for visual verification.

**Architecture:** A new character-agnostic `Player_Animate` read-only classifier writes one shared `ANIM_*` id per frame; each character's `SST_anim_table` resolves the id to its own frames. Speed-scaled timing is generalized into the animation format via a byte-0 duration sentinel (`DUR_DYNAMIC`) whose value the player supplies in `d3`. Spindash state moves from `sonic.asm` to shared `player_spindash.asm`. A `DEBUG`-gated viewer freezes the player and steps through every `ANIM_*` id for screenshot verification.

**Tech Stack:** Motorola 68000 assembly, AS Macro Assembler (`asw`), Exodus emulator via MCP. "Tests" in this codebase are build-time `error` asserts + a clean `./build.sh` + emulator MCP inspection — there is no unit-test runner. Each task ends with a build and a concrete check.

**Pre-flight (do once before Task 1):**
- Create a feature branch: `git checkout -b feat/sonic-animations`
- Confirm baseline builds: `./build.sh` then `ls -la s4.bin` (expect a fresh `s4.bin`, no `ERROR` lines in `s4.log`).

**Key facts established during design (do not re-derive):**
- DPLC worst-case among referenced frames = **16 tiles**; reservation gap `VRAM_TEST_OBJ - VRAM_TEST_SONIC` = `$03E0-$03C0` = **32 tiles**. No VRAM reshuffle needed.
- `AnimateSprite` (`engine/objects/animate.asm`) reloads the per-anim duration at exactly two sites: line ~71 (frame advance) and line ~93 (anim changed), both `move.b (a1), SST_anim_timer(a0)`.
- `AnimateSprite` clobbers `d0-d2, a1-a2`. We add `d3` as a new **input** (dynamic hold); it is read only on the sentinel path, which only player scripts ever trigger.
- `PlayerV` overlay (`player_common.asm:16-38`) uses 13 of 34 bytes — room for new fields.
- `ST_PUSHING` is already set/cleared correctly (`player_ground.asm`). `PHYS_SKID_MIN = $400` exists but is unused today.

---

## Task 1: `ANIM_*` id contract + constants

**Files:**
- Modify: `constants.asm:262-265` (ANIM ids), `constants.asm` near `:235` (add `ANIM_RUN_THRESHOLD`, `DUR_DYNAMIC`)

- [ ] **Step 1: Replace the three ANIM ids with the full set**

In `constants.asm`, replace lines 262-265:

```
; Player animation ids — SHARED CONTRACT across all characters.
; Each character's Ani_<char> script table is ordered by these ids
; (sonic_anims.asm asserts its entry count == ANIM_COUNT). Player_Animate
; only ever writes these ids; it never knows which character it animates.
ANIM_WALK               = 0
ANIM_RUN                = 1
ANIM_ROLL               = 2         ; also the air ball (jump/airball)
ANIM_BALL               = ANIM_ROLL ; explicit alias for air states
ANIM_SPINDASH           = 3
ANIM_PUSH               = 4
ANIM_IDLE               = 5         ; wait/idle (neutral hold -> foot-tap tail)
ANIM_BALANCE            = 6
ANIM_LOOKUP             = 7
ANIM_DUCK               = 8
ANIM_SKID               = 9
ANIM_GETUP              = 10
ANIM_COUNT              = 11        ; sonic_anims.asm asserts entry count == this
```

- [ ] **Step 2: Add the run threshold and the duration sentinel**

In `constants.asm`, immediately after `PHYS_SKID_MIN = $400` (line 235), add:

```
ANIM_RUN_THRESHOLD      = $600      ; |gsp| at/above which walk -> run anim (S3K)
```

And after `SPINDASH_CHARGE_MAX` (line 239), add:

```
; Animation byte-0 duration sentinel: when an animation script's duration
; byte == DUR_DYNAMIC, AnimateSprite takes the per-anim hold from d3 (caller
; supplies it). Only player walk/run/roll scripts use this; generic objects
; never set it, so they never read d3. Value is high so it can't collide with
; a real frame-hold (real holds are small: idle 30, wait 5, etc.).
DUR_DYNAMIC             = $FF
```

- [ ] **Step 3: Build and verify clean**

Run: `./build.sh`
Expected: `s4.bin` rebuilt; `grep -c ERROR s4.log` prints `0`. (Existing references to `ANIM_IDLE`/`ANIM_BALL` still resolve — `ANIM_BALL` is now an alias of `ANIM_ROLL`=2, and `ANIM_IDLE` moved to 5; `Player_Init` and the old `Player_Display` chain still assemble. They are rewritten in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add constants.asm
git commit -m "feat(anim): shared ANIM_* id contract + run threshold + DUR_DYNAMIC sentinel"
```

---

## Task 2: Speed-scaled duration in `AnimateSprite`

**Files:**
- Modify: `engine/objects/animate.asm` (the two duration-reload sites + header)

- [ ] **Step 1: Document the new input in the header**

In `engine/objects/animate.asm`, update the `AnimateSprite` header comment block (lines ~47-52) to add an input line:

```
; In:  a0 = SST pointer (anim_table must be set)
;      d3.b = dynamic per-anim hold, used ONLY when a script's duration byte
;             == DUR_DYNAMIC (speed-scaled anims). Callers without DUR_DYNAMIC
;             scripts need not set d3.
```

- [ ] **Step 2: Define a duration-reload macro at the top of the file**

At the top of `engine/objects/animate.asm` (after any existing equates, before `AnimateSprite:`), add:

```
; Reload SST_anim_timer from the script duration byte at (srcReg), substituting
; the caller's d3 when the byte is the DUR_DYNAMIC sentinel. srcReg points at
; the script's byte 0. Clobbers d2.
reloadAnimTimer macro srcReg
        move.b  (srcReg), d2
        cmpi.b  #DUR_DYNAMIC, d2
        bne.s   .rt_static\@
        move.b  d3, d2
.rt_static\@:
        move.b  d2, SST_anim_timer(a0)
        endm
```

(`\@` gives the macro a unique local-label scope per expansion. `d2` is already in `AnimateSprite`'s clobber list.)

- [ ] **Step 3: Use the macro at the frame-advance reload (line ~71)**

Replace line 71 (`move.b (a1), SST_anim_timer(a0)`) with:

```
        reloadAnimTimer a1
```

- [ ] **Step 4: Use the macro at the anim-changed reload (line ~93)**

Replace line 93 (`move.b (a1), SST_anim_timer(a0)`) with:

```
        reloadAnimTimer a1
```

- [ ] **Step 5: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. Behavior is unchanged for all existing callers (no script uses `DUR_DYNAMIC` yet, so the static path always runs).

- [ ] **Step 6: Commit**

```bash
git add engine/objects/animate.asm
git commit -m "feat(anim): AnimateSprite honors DUR_DYNAMIC duration via d3 (speed-scaling hook)"
```

---

## Task 3: Author the full Sonic animation data

**Files:**
- Modify: `data/animations/sonic_anims.asm` (full rewrite)

Frame indices are verified present in `data/dplc/optimized/sonic.bin` (224 frames; all referenced frames ≤ 16 tiles).

- [ ] **Step 1: Rewrite the animation script table**

Replace the entire contents of `data/animations/sonic_anims.asm` with:

```
; Sonic animation scripts — ordered by the shared ANIM_* ids (constants.asm).
; Walk/Run/Roll use DUR_DYNAMIC: AnimateSprite takes the hold from d3, which
; Player_Animate computes from ground speed (speed-scaled timing).

Ani_Sonic:
        dc.w Ani_Sonic_Walk-Ani_Sonic           ; ANIM_WALK     = 0
        dc.w Ani_Sonic_Run-Ani_Sonic            ; ANIM_RUN      = 1
        dc.w Ani_Sonic_Roll-Ani_Sonic           ; ANIM_ROLL     = 2
        dc.w Ani_Sonic_Spindash-Ani_Sonic       ; ANIM_SPINDASH = 3
        dc.w Ani_Sonic_Push-Ani_Sonic           ; ANIM_PUSH     = 4
        dc.w Ani_Sonic_Wait-Ani_Sonic           ; ANIM_IDLE     = 5
        dc.w Ani_Sonic_Balance-Ani_Sonic        ; ANIM_BALANCE  = 6
        dc.w Ani_Sonic_LookUp-Ani_Sonic         ; ANIM_LOOKUP   = 7
        dc.w Ani_Sonic_Duck-Ani_Sonic           ; ANIM_DUCK     = 8
        dc.w Ani_Sonic_Skid-Ani_Sonic           ; ANIM_SKID     = 9
        dc.w Ani_Sonic_GetUp-Ani_Sonic          ; ANIM_GETUP    = 10
Ani_Sonic_TableEnd:
    if (Ani_Sonic_TableEnd-Ani_Sonic)/2 <> ANIM_COUNT
        error "Ani_Sonic entry count out of sync with ANIM_COUNT"
    endif

Ani_Sonic_Walk:
        dc.b DUR_DYNAMIC                        ; hold from d3 (speed-scaled)
        dc.b 7, 8, 1, 2, 3, 4, 5, 6
        dc.b AF_END
        align 2
Ani_Sonic_Run:
        dc.b DUR_DYNAMIC
        dc.b $21, $22, $23, $24
        dc.b AF_END
        align 2
Ani_Sonic_Roll:
        dc.b DUR_DYNAMIC
        dc.b $96, $97, $96, $98, $96, $99, $96, $9A
        dc.b AF_END
        align 2
Ani_Sonic_Spindash:
        dc.b 0                                  ; advance every frame (fast rev)
        dc.b $86, $87, $86, $88, $86, $89, $86, $8A, $86, $8B
        dc.b AF_END
        align 2
Ani_Sonic_Push:
        dc.b 6
        dc.b $B6, $B7, $B8, $B9
        dc.b AF_END
        align 2
Ani_Sonic_Wait:
        dc.b 7                                  ; neutral stand
        dc.b $BA, $BA, $BA, $BA, $BA, $BA, $BA, $BA
        dc.b $BB, $BC, $BD                      ; lean into foot-tap
        dc.b $BE, $BF, $C0, $BF, $BE            ; tap loop body
        dc.b AF_BACK, 5                         ; loop the tap (5 frames back)
        align 2
Ani_Sonic_Balance:
        dc.b 9
        dc.b $A4, $A5, $A6
        dc.b AF_END
        align 2
Ani_Sonic_LookUp:
        dc.b 5
        dc.b $C3, $C4
        dc.b AF_BACK, 1                         ; hold last frame
        align 2
Ani_Sonic_Duck:
        dc.b 5
        dc.b $9B, $9C
        dc.b AF_BACK, 1                         ; hold last frame
        align 2
Ani_Sonic_Skid:
        dc.b 3
        dc.b $9D, $9E, $9F, $A0
        dc.b AF_BACK, 1                         ; hold the braced pose
        align 2
Ani_Sonic_GetUp:
        dc.b 8
        dc.b $8F
        dc.b AF_END
        align 2

Ani_Sonic_End:
    if (Ani_Sonic_End-Ani_Sonic) > $7FFF
        error "Ani_Sonic exceeds signed word-offset range"
    endif
```

- [ ] **Step 2: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. The `Ani_Sonic entry count` assert passing proves the table matches `ANIM_COUNT`.

- [ ] **Step 3: Commit**

```bash
git add data/animations/sonic_anims.asm
git commit -m "feat(anim): full Sonic animation set ordered by ANIM_* contract"
```

---

## Task 4: Player overlay fields for skid latch + get-up + look seam

**Files:**
- Modify: `engine/player/player_common.asm:16-38` (PlayerV struct + `_pl_*` equates), `engine/player/player_common.asm:112-133` (`Player_Init` clears)

- [ ] **Step 1: Add three fields to the PlayerV struct**

In `engine/player/player_common.asm`, inside `PlayerV struct` (before `PlayerV endstruct` at line 27), add after `debug_flag`:

```
skid_latch       ds.b 1      ; nonzero = hold the skid pose (display latch)
getup_timer      ds.b 1      ; >0 = play ANIM_GETUP one-shot, counts down
look_offset      ds.b 1      ; camera look/duck pan seam — stays 0 this pass
```

- [ ] **Step 2: Add the matching `_pl_*` equates**

After line 38 (`_pl_debug = ...`), add:

```
_pl_skid_latch   = SST_sst_custom+PlayerV_skid_latch
_pl_getup        = SST_sst_custom+PlayerV_getup_timer
_pl_look_offset  = SST_sst_custom+PlayerV_look_offset
```

- [ ] **Step 3: Clear the new fields in `Player_Init`**

In `Player_Init` (after line 127 `clr.b _pl_stick_convex(a0)`), add:

```
        clr.b   _pl_skid_latch(a0)
        clr.b   _pl_getup(a0)
        clr.b   _pl_look_offset(a0)
```

- [ ] **Step 4: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. `objvarsCheck PlayerV_len` (line 28) passing proves the overlay still fits in 34 bytes (now 16 of 34 used).

- [ ] **Step 5: Commit**

```bash
git add engine/player/player_common.asm
git commit -m "feat(player): skid-latch, get-up, look-offset overlay fields"
```

---

## Task 5: Balance ledge-edge sensor

**Files:**
- Modify: `engine/player/player_sensors.asm` (add `Player_AtLedgeEdge`)

This helper is consumed by `Player_Animate` (Task 6). It checks whether the player is standing at/over a ledge edge — i.e. a floor probe offset toward the facing direction finds no nearby ground.

- [ ] **Step 1: Read the existing floor-probe interface**

Read `engine/player/player_sensors.asm` to confirm the name/signature of the single-point floor probe used by the ground floor pair (the routine `Player_SensorFloor`/`Player_SensorFloorAt` calls). Use the existing point-probe entry; do not add a new probing primitive. The helper below assumes a point-probe `Player_SensorFloorAt` taking `d0.w=x`, `d1.w=y`, returning `d0.w=distance` (negative = embedded, large positive = no ground). If the actual name/signature differs, adapt the two `jsr` calls and the register usage to match — the logic is unchanged.

- [ ] **Step 2: Add the edge-detect helper**

Append to `engine/player/player_sensors.asm`:

```
; -----------------------------------------------
; Player_AtLedgeEdge — true when the support is at/over a ledge edge, for
; the idle balance/teeter animation. Probes the floor one body-width toward
; the FACING direction; if that probe finds no nearby ground while the body
; centre is still supported, the player is teetering.
; In:  a0 = player SST (grounded, at rest — caller gates on this)
; Out: Z clear (bne) = at an edge; Z set (beq) = solidly supported
; Clobbers: d0-d2
; -----------------------------------------------
LEDGE_PROBE_REACH = PLAYER_X_RADIUS+2   ; just past the support foot
LEDGE_NO_GROUND   = 12                  ; dist beyond this = nothing under foot

Player_AtLedgeEdge:
        move.w  SST_x_pos(a0), d0
        btst    #ST_XFLIP, SST_status(a0)
        bne.s   .face_left
        addi.w  #LEDGE_PROBE_REACH, d0           ; facing right: probe ahead-right
        bra.s   .probe
.face_left:
        subi.w  #LEDGE_PROBE_REACH, d0           ; facing left: probe ahead-left
.probe:
        move.w  SST_y_pos(a0), d1
        jsr     Player_SensorFloorAt             ; d0.w = distance to ground
        cmpi.w  #LEDGE_NO_GROUND, d0
        ; bgt => no ground under the leading foot => at an edge.
        ; Caller branches on Z: set the flag accordingly.
        bgt.s   .at_edge
        moveq   #0, d0                            ; supported -> Z set
        rts
.at_edge:
        moveq   #1, d0                            ; edge -> Z clear
        rts
```

- [ ] **Step 3: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. (Helper is defined but not yet called — confirms it assembles and the floor-probe symbol resolved.)

- [ ] **Step 4: Commit**

```bash
git add engine/player/player_sensors.asm
git commit -m "feat(player): Player_AtLedgeEdge sensor for balance animation"
```

---

## Task 6: `Player_Animate` selection routine

**Files:**
- Modify: `engine/player/player_common.asm:249-276` (replace the inline `Player_Display` anim chain)

- [ ] **Step 1: Replace the `Player_Display` body**

In `engine/player/player_common.asm`, replace the `Player_Display` routine (lines 249-276, from `Player_Display:` through the `jmp Sonic_LoadArt` and its trailing comment) with:

```
; -----------------------------------------------
; Player_Display — classify the animation, advance it, stream art, draw.
; In:  a0 = player SST
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
Player_Display:
        bsr.w   Player_Animate                  ; sets SST_anim + d3 (dyn hold)
        jsr     AnimateSprite
        jmp     Sonic_LoadArt                   ; character dispatch (Tails/Knux
                                                ; replace via roster later)

; -----------------------------------------------
; Player_Animate — read-only animation classifier. Reads state/status/input/
; (at rest) one ledge sensor; writes ONE ANIM_* id to SST_anim and the
; speed-scaled hold to d3. Mutates only the display transients skid_latch and
; getup_timer. Priority order: high -> low (see the table in the design spec).
; In:  a0 = player SST
; Out: SST_anim set; d3.b = dynamic per-anim hold (for DUR_DYNAMIC scripts)
; Clobbers: d0-d2, d4, a1-a2 (d3 is an output)
; -----------------------------------------------
Player_Animate:
        ; speed-scaled hold for walk/run/roll: hold = max(0,($800-|gsp|)>>8)
        ; (research/animation-system.md baseline; roll reuses the same curve).
        move.w  _pl_gsp(a0), d0
        bpl.s   .absok
        neg.w   d0
.absok:
        move.w  #$800, d4
        sub.w   d0, d4
        bpl.s   .holdok
        moveq   #0, d4
.holdok:
        lsr.w   #8, d4
        move.b  d4, d3                           ; d3 = dynamic hold (output)

        move.b  _pl_state(a0), d0

        ; (1) spindash
        cmpi.b  #PSTATE_SPINDASH, d0
        bne.s   .not_spindash
        move.b  #ANIM_SPINDASH, SST_anim(a0)
        rts
.not_spindash:
        ; (2) ball states: roll + all curled air (>= PSTATE_JUMP)
        cmpi.b  #PSTATE_JUMP, d0
        bhs.s   .ball
        cmpi.b  #PSTATE_ROLL, d0
        bne.s   .uncurled
.ball:
        move.b  #ANIM_ROLL, SST_anim(a0)
        rts

.uncurled:
        ; airborne uncurled keeps the walk/run cycle from carried gsp; the
        ; grounded-only conditions (skid/push/duck/lookup/balance) are gated
        ; on being grounded.
        btst    #ST_IN_AIR, SST_status(a0)
        bne.w   .walk_or_run

        ; (3) skid — grounded, |gsp| >= PHYS_SKID_MIN, input opposes inertia.
        ; Latch holds the pose through the brake; cleared at rest/reversal.
        move.w  _pl_gsp(a0), d1
        beq.s   .skid_clear                     ; stopped -> drop the latch
        move.w  d1, d2
        bpl.s   .moving_right
        ; moving left: skid if RIGHT held
        btst    #BUTTON_RIGHT_BIT, (Ctrl_1_Held).w
        bne.s   .skid_test
        bra.s   .skid_maybe_clear
.moving_right:
        ; moving right: skid if LEFT held
        btst    #BUTTON_LEFT_BIT, (Ctrl_1_Held).w
        beq.s   .skid_maybe_clear
.skid_test:
        ; opposing input present; require speed over the skid floor to ARM,
        ; but once latched keep it until stop/reverse.
        cmpi.w  #PHYS_SKID_MIN, d2
        bge.s   .skid_set
        neg.w   d2
        cmpi.w  #PHYS_SKID_MIN, d2
        bge.s   .skid_set
.skid_maybe_clear:
        tst.b   _pl_skid_latch(a0)
        beq.s   .not_skid
.skid_set:
        st      _pl_skid_latch(a0)
        move.b  #ANIM_SKID, SST_anim(a0)
        rts
.skid_clear:
        clr.b   _pl_skid_latch(a0)
.not_skid:
        clr.b   _pl_skid_latch(a0)

        ; (4) push — grounded, ST_PUSHING (facing-aware bit set by ground code)
        btst    #ST_PUSHING, SST_status(a0)
        beq.s   .not_push
        move.b  #ANIM_PUSH, SST_anim(a0)
        rts
.not_push:
        ; conditions (5)-(10) split on "at rest" vs "moving"
        tst.w   _pl_gsp(a0)
        bne.s   .walk_or_run

        ; --- at rest ---
        ; get-up one-shot: if armed, play it until it expires
        tst.b   _pl_getup(a0)
        beq.s   .rest_input
        subq.b  #1, _pl_getup(a0)
        move.b  #ANIM_GETUP, SST_anim(a0)
        rts
.rest_input:
        ; (5) duck — DOWN held
        btst    #BUTTON_DOWN_BIT, (Ctrl_1_Held).w
        beq.s   .not_duck
        move.b  #ANIM_DUCK, SST_anim(a0)
        rts
.not_duck:
        ; (6) look up — UP held
        btst    #BUTTON_UP_BIT, (Ctrl_1_Held).w
        beq.s   .not_lookup
        move.b  #ANIM_LOOKUP, SST_anim(a0)
        rts
.not_lookup:
        ; (9) balance — at a ledge edge
        bsr.w   Player_AtLedgeEdge              ; Z clear = at edge
        beq.s   .idle
        move.b  #ANIM_BALANCE, SST_anim(a0)
        rts
.idle:
        ; (10) idle/wait
        move.b  #ANIM_IDLE, SST_anim(a0)
        rts

.walk_or_run:
        ; (7)/(8) run vs walk by |gsp|. d0 still holds |gsp| from the top.
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
```

- [ ] **Step 2: Confirm the button-bit constant names**

The code uses `BUTTON_LEFT_BIT`, `BUTTON_RIGHT_BIT`, `BUTTON_UP_BIT`, `BUTTON_DOWN_BIT` for `btst`. `constants.asm:86-93` defines `BUTTON_UP=1<<0 … BUTTON_DOWN=1<<1 … BUTTON_LEFT=1<<2 … BUTTON_RIGHT=1<<3` (masks, not bit numbers). Add the bit-number equates in `constants.asm` after line 93:

```
BUTTON_UP_BIT           = 0
BUTTON_DOWN_BIT         = 1
BUTTON_LEFT_BIT         = 2
BUTTON_RIGHT_BIT        = 3
```

- [ ] **Step 3: Arm get-up when leaving duck/spindash back to rest**

Get-up should fire when the player was ducking or spindashing and returns to standing rest. The simplest correct trigger that needs no state-machine change: arm it in the spindash exit hook and when duck is released. In `engine/player/player_common.asm`, find `PHook_SpindashExit` (the exit hook, ~line 378-382) and add, after its existing charge-clear:

```
        move.b  #6, _pl_getup(a0)               ; brief get-up after spindash
```

Duck has no state, so its get-up is handled implicitly: while DOWN is held `Player_Animate` returns `ANIM_DUCK`; on release the next frame falls to balance/idle. A duck->getup flourish is optional polish and is intentionally NOT added here (YAGNI — spindash is the visible get-up case).

- [ ] **Step 4: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. All labels (`Player_Animate`, `Player_AtLedgeEdge`, button bits, `ANIM_*`) resolve.

- [ ] **Step 5: Commit**

```bash
git add engine/player/player_common.asm constants.asm
git commit -m "feat(player): Player_Animate classifier — skid/push/duck/lookup/balance/run + speed-scaling"
```

---

## Task 7: Relocate spindash into shared player code

**Files:**
- Create: `engine/player/player_spindash.asm`
- Modify: `engine/player/sonic.asm` (remove `PState_Spindash`), `main.asm` (include the new file)

- [ ] **Step 1: Find the include site and the source span**

Confirm in `main.asm` where the player files are included (search for `player_ground.asm` / `sonic.asm`). The new file must be included in the **same object code bank** as the other player state bodies so `Player_States` reaches it.

- [ ] **Step 2: Create `player_spindash.asm` with the relocated state**

Create `engine/player/player_spindash.asm` containing the `PState_Spindash` routine — copy it verbatim from `engine/player/sonic.asm:31-125` (the header comment block through the `jmp PState_Roll`). Replace the file/scope header comment with:

```
; Spindash — SHARED player ability state (all characters). Relocated out of
; sonic.asm: spindash is identical across the roster; the per-character part
; is only the spindash ANIMATION, which resolves through each character's own
; SST_anim_table via ANIM_SPINDASH. Entered from PState_Ground's trigger.
;
; Lives in the object code bank (reached via the shared Player_States table).
```

Keep the routine body (`PState_Spindash:` … `jmp PState_Roll`) exactly as it was — physics, charge curve, release formula, and camera freeze are unchanged.

- [ ] **Step 3: Remove `PState_Spindash` from `sonic.asm`**

In `engine/player/sonic.asm`, delete lines 31-125 (the entire `PState_Spindash` block including its header comment). `sonic.asm` now ends after `Sonic_LoadArt` and continues to `PhysTable_Sonic`. Leave `Sonic_InitAssets`, `Sonic_LoadArt`, and `PhysTable_Sonic` intact.

- [ ] **Step 4: Add the include to `main.asm`**

Add `include "engine/player/player_spindash.asm"` adjacent to the other player state-body includes (next to `player_ground.asm` / `player_air.asm`), so it sits in the same bank.

- [ ] **Step 5: Build and verify clean**

Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`. `Player_States` (which references `PState_Spindash`) resolves to the new file; no duplicate-symbol error (proves it was removed from `sonic.asm`).

- [ ] **Step 6: Verify spindash byte-for-byte unchanged**

Run: `git log -p -1 -- engine/player/player_spindash.asm engine/player/sonic.asm | grep -E '^\+|^-' | grep -iE 'SPINDASH_|\$800|asr|Player_SensorFloor|Camera_Spindash' | head`
Expected: the spindash physics lines appear as additions in `player_spindash.asm` and deletions in `sonic.asm`, identical text. (Confirms a pure move, not a rewrite.)

- [ ] **Step 7: Commit**

```bash
git add engine/player/player_spindash.asm engine/player/sonic.asm main.asm
git commit -m "refactor(player): relocate spindash to shared player_spindash.asm (all-character)"
```

---

## Task 8: Debug anim viewer (DEBUG-gated)

**Files:**
- Modify: `engine/player/player_common.asm` (`Player_Main` toggle + a viewer update path), `constants.asm` (a viewer RAM byte if needed — prefer reusing an overlay field)

The viewer freezes the player, forces `SST_anim` to a stepped id, injects a fixed `gsp` so speed-scaled anims animate, and still runs the display tail.

- [ ] **Step 1: Add a viewer-id overlay field**

In `engine/player/player_common.asm` `PlayerV struct`, add (alongside the Task 4 fields):

```
viewer_id        ds.b 1      ; DEBUG anim-viewer: forced ANIM_* id (DEBUG only)
```

and the equate after the others:

```
_pl_viewer_id    = SST_sst_custom+PlayerV_viewer_id
```

Clear it in `Player_Init` with the other new fields: `clr.b _pl_viewer_id(a0)`.

- [ ] **Step 2: Add the viewer toggle + update inside `Player_Main`, gated on DEBUG**

In `Player_Main`, the debug-fly toggle reads press bits into `d6` (line 163). Reuse `_pl_debug` as the "frozen" flag but branch to a viewer path when a viewer sub-mode is active. Add, immediately after the existing `.no_toggle` resolution (after line 173, before `tst.b _pl_debug(a0)` at 174), wrapped in `DEBUG`:

```
    if DEBUG
        ; Anim viewer: START toggles viewer sub-mode (only meaningful while
        ; debug-frozen). When active, Up/Down step the forced anim id.
        btst    #7, d6                          ; BUTTON_START press
        beq.s   .vw_no_toggle
        bchg    #0, (Anim_Viewer_Active).w
.vw_no_toggle:
        tst.b   (Anim_Viewer_Active).w
        beq.s   .vw_off
        ; step id on Up/Down press
        btst    #BUTTON_UP_BIT, d6
        beq.s   .vw_no_up
        addq.b  #1, _pl_viewer_id(a0)
        cmpi.b  #ANIM_COUNT, _pl_viewer_id(a0)
        blo.s   .vw_no_up
        clr.b   _pl_viewer_id(a0)
.vw_no_up:
        btst    #BUTTON_DOWN_BIT, d6
        beq.s   .vw_no_dn
        subq.b  #1, _pl_viewer_id(a0)
        bpl.s   .vw_no_dn
        move.b  #ANIM_COUNT-1, _pl_viewer_id(a0)
.vw_no_dn:
        bra.w   Player_ViewerUpdate
.vw_off:
    endif
```

- [ ] **Step 3: Add the `Player_ViewerUpdate` routine**

Add near `Player_Display` (still inside, or guarded by, `if DEBUG`):

```
    if DEBUG
; -----------------------------------------------
; Player_ViewerUpdate — frozen anim preview. Forces the viewer-selected
; ANIM_* id, injects a fixed gsp so speed-scaled anims animate, runs the
; display tail. No physics, no collision, no state dispatch.
; In:  a0 = player SST
; -----------------------------------------------
Player_ViewerUpdate:
        move.w  #$600, _pl_gsp(a0)              ; mid speed -> scaled anims move
        bsr.w   Player_Animate                  ; computes d3 from the gsp above
        move.b  _pl_viewer_id(a0), SST_anim(a0) ; OVERRIDE the classifier
        jsr     AnimateSprite
        jmp     Sonic_LoadArt
    endif
```

- [ ] **Step 4: Reserve the `Anim_Viewer_Active` RAM byte**

Add `Anim_Viewer_Active` as a 1-byte RAM global in the appropriate RAM map file (search for where `Player_JumpBuffer` / `Player_Quadrant` are declared — likely `ram.asm` — and add a `ds.b 1` next to the player scratch globals). Gate its declaration with `if DEBUG` if the RAM map supports conditional fields; otherwise leave it unconditional (1 byte).

- [ ] **Step 5: Build with DEBUG on and verify clean**

Confirm how `DEBUG` is set for this project (search `S4.asm`/`main.asm` for `DEBUG =`). Build the DEBUG configuration.
Run: `./build.sh`
Expected: `grep -c ERROR s4.log` prints `0`.

- [ ] **Step 6: Commit**

```bash
git add engine/player/player_common.asm constants.asm ram.asm
git commit -m "feat(debug): anim viewer — freeze + step ANIM_* ids for verification"
```

---

## Task 9: Documentation sync

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§5), `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Update ENGINE_ARCHITECTURE §5**

In `docs/ENGINE_ARCHITECTURE.md` §5 (player/character), document: the shared `ANIM_*` id contract; `Player_Animate` as the read-only classifier (priority order + the display-condition treatment of skid/duck/lookup); generalized speed-scaled timing via `DUR_DYNAMIC` + `d3`; spindash relocated to shared `player_spindash.asm`; `Player_AtLedgeEdge` for balance; the `Player_LookOffset` zero-seam for future camera pan.

- [ ] **Step 2: Update DEFERRED_WORK §5**

Mark "spindash shared across all 3 characters" as **done**. Keep deferred and note dependencies: dropdash, insta-shield, look/duck camera pan (now has the `_pl_look_offset` seam), get-up flourish on duck-release.

- [ ] **Step 3: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§5): anim classifier, speed-scaling, shared spindash"
```

---

## Task 10: Visual verification via Exodus MCP (acceptance)

**Prerequisite:** the Exodus MCP socket must be live (it returned `No such file or directory` during design — confirm with `mcp__exodus__emulator_status` first; if down, ask the user to (re)launch Exodus/the MCP bridge).

**Files:** none (verification only).

- [ ] **Step 1: Load the freshly built DEBUG ROM**

Use `mcp__exodus__emulator_reload_rom` (or have the user load `s4.bin`), then `mcp__exodus__emulator_load_symbols` if needed. Confirm `mcp__exodus__emulator_status` shows running.

- [ ] **Step 2: Enter the viewer and freeze**

Drive input to enter debug-freeze (B) then viewer sub-mode (START). Confirm via `mcp__exodus__emulator_player_state` that the player is frozen and `_pl_viewer_id` reads 0.

- [ ] **Step 3: Step through every ANIM_* id, screenshot each**

For each id 0..ANIM_COUNT-1: press Up to advance, let a few frames run, `mcp__exodus__emulator_screenshot path=/tmp/anim_<id>.png`. Inspect each PNG.

Expected per id:
- WALK/RUN/ROLL: cycle visibly animates (the injected `$600` gsp drives the speed-scaled hold).
- SPINDASH: fast rev ball.
- PUSH/BALANCE/LOOKUP/DUCK/SKID/GETUP/IDLE(wait): correct static or short-cycle pose.
- **No torn/garbage tiles** in any frame (proves DPLC tile counts ≤ reservation and VRAM dest correct).

- [ ] **Step 4: Spot-check normal play (viewer off)**

Exit viewer, drop into physics (B). Verify in real play: walk→run splits at speed and the cycle speeds up with velocity; roll spins faster at speed; push triggers on a wall; skid triggers braking against input and holds; duck/look-up on the d-pad at rest; balance at a ledge edge; wait/foot-tap after idling. Spindash charges and launches identically to before.

- [ ] **Step 5: Final verification note**

Record results (pass/fail per animation, any artifacts) in the commit message or a short note. If any animation shows wrong frames or artifacts, file the specific frame id + symptom and return to the relevant data/code task — do not mark the plan complete with known artifacts.

---

## Self-review notes (completed by plan author)

- **Spec coverage:** §1 contract → Task 1; §2 selection + skid latch + getup + look seam → Tasks 4/5/6; §3 speed-scaling → Tasks 2/6; §4 shared spindash → Task 7; §5 data → Task 3; §6 DPLC/VRAM → resolved at design (16≤32) + the `Ani_Sonic`/overlay asserts; §7 viewer → Task 8; verification → Task 10; docs → Task 9. All sections covered.
- **Placeholder scan:** no TBD/TODO-as-work; the one "adapt if signature differs" (Task 5 Step 1) is an explicit instruction to verify a real interface, with a concrete fallback assumption stated.
- **Type/name consistency:** `ANIM_*`, `ANIM_COUNT`, `DUR_DYNAMIC`, `_pl_skid_latch/_pl_getup/_pl_look_offset/_pl_viewer_id`, `Player_Animate`, `Player_AtLedgeEdge`, `Player_ViewerUpdate`, `BUTTON_*_BIT`, `Anim_Viewer_Active` are used consistently across tasks. `Player_AtLedgeEdge` returns Z (beq=supported) and Task 6 branches `beq .idle` — consistent.
- **Open verification items flagged for the implementer (not placeholders):** exact floor point-probe symbol name (Task 5), the project's `DEBUG` switch location and RAM-map file (Task 8), and the `PHook_SpindashExit` line for the get-up arm (Task 6 Step 3). Each names what to confirm and where.
```
