; Directional sensor probe cores + player sensor wrappers (§5 Task 4)
;
; Four specialized probe routines (down/up/right/left) stamped from ONE
; macro — direction inversions resolve at assembly time, no runtime mask
; plumbing. Each core implements the S.C.E. FindFloor/FindWall two-cell
; model — see docs/research/player-sensors-sce.md §1.4.
;
; Height semantics follow the generator contract (tools/
; collision_pipeline.py): per-column byte h = 0 empty, 1..16 solid from
; the cell bottom, $F0..$FF two's-complement = solid hanging from the
; cell top with depth 256−h. Rotated (wall) profiles: positive = run
; from the LEFT edge, negative = run from the RIGHT edge. The direction
; mappings below mirror S.C.E.'s eor-mask model (Down plain; Up = Down
; with sub-coordinate ^$F + height negation), BUT the horizontal pairing
; is SWAPPED relative to S.C.E.: their rotated array anchors positive
; widths at the right edge, ours at the left, so ProbeRight negates and
; ProbeLeft is plain (verified geometrically against OJZ slope profiles
; — see Task 4 report). Negative-height accept rule replicated from
; S.C.E. Find Floor.asm's bmi branch: inside the hanging run
; (sub + h < 0) → treat as full (back-probe); outside → treat as air
; (forward-probe).
;
; REGISTER CONVENTION (collision_lookup.asm header): d3.b = layer on
; every entry, X/Y saved in d4/d5, d3 NOT preserved.

; -----------------------------------------------
; probeSub — load the probe-axis sub-coordinate (0-15) into pdst
; -----------------------------------------------
probeSub macro paxreg, psubflip, pdst
        move.w  paxreg, pdst
        andi.w  #$F, pdst
    if psubflip
        eori.w  #$F, pdst              ; mirrored axis: sub' = 15 − sub
    endif
        endm

; -----------------------------------------------
; probeCore — stamp one directional probe routine
;   pname    routine label
;   ptable   HeightMaps (vertical) / HeightMapsRot (horizontal)
;   pcolreg  register holding the height-column coordinate (X=d4 / Y=d5)
;   paxreg   register holding the probe-axis coordinate   (Y=d5 / X=d4)
;   pstep    probe-direction cell step in px (+16 down/right, −16 up/left)
;   pnegate  1 = negate loaded height (Up, Right — far-edge anchor flips)
;   psubflip 1 = invert the probe-axis sub-coordinate (Up, Left)
;
; Contract (every stamped routine):
; In:  d0.w = engine X px, d1.w = engine Y px, d3.b = layer (0/1),
;      d6.b = sensor solidity-class mask (SOLID_TOP floor-class,
;             SOLID_LRB wall/ceiling-class)
; Out: d0.w = signed distance to surface along the probe direction
;             (>= 16 generally means "nothing close"; +32/0/0 = nothing
;             found at all)
;      d1.b = surface angle (RAW AngleTable byte — odd flag NOT resolved)
;      d2.b = attr byte of the cell that supplied the result (0 = none)
; Clobbers: d0-d5, a1. a0/d6/d7/a2-a6 PRESERVED (callers keep the player
; SST in a0 and reuse the class mask in d6 for the pair's second sensor).
; -----------------------------------------------
; {GLOBALSYMBOLS}: emit body labels as normal symbols — the stamped
; routine name leads each expansion, so the .dot locals scope under it
; (unique per stamp, standard AS dot-label rules)
probeCore macro pname, ptable, pcolreg, paxreg, pstep, pnegate, psubflip, {GLOBALSYMBOLS}
pname:
        move.l  a0, -(sp)              ; Collision_GetType clobbers a0
        move.w  d3, -(sp)              ; layer must survive for the extension
        move.w  d0, d4                 ; X (file convention: X in d4)
        move.w  d1, d5                 ; Y (file convention: Y in d5)
        bsr.s   .cell                  ; d0.w h_eff, d1.b angle, d2.b attr
        tst.w   d0
        beq.s   .empty_fwd
        cmpi.w  #16, d0
        beq.s   .full_back
        ; surface in the primary cell: dist = 16 − h − sub
        probeSub paxreg, psubflip, d3
        add.w   d0, d3
        moveq   #16, d0
        sub.w   d3, d0
.done:
        addq.l  #2, sp                 ; drop saved layer
        movea.l (sp)+, a0
        rts

.empty_fwd:
        ; primary empty → evaluate ONE cell forward; dist = dist2 + 16
        move.w  (sp), d3               ; reload layer
        addi.w  #pstep, paxreg
        bsr.s   .cell
        tst.w   d0
        beq.s   .nothing               ; forward empty too → sentinel
        probeSub paxreg, psubflip, d3  ; ±16 step keeps the low 4 bits
        add.w   d0, d3
        moveq   #32, d0                ; 16 − h_eff − sub, +16
        sub.w   d3, d0
        bra.s   .done

.nothing:
        moveq   #32, d0
        moveq   #0, d1
        moveq   #0, d2
        bra.s   .done

.full_back:
        ; primary full (or embedded in a hanging run) → evaluate ONE cell
        ; back; dist = dist2 − 16 = −(h_eff + sub). When the back cell is
        ; empty the PRIMARY cell supplied the surface (its top face) — keep
        ; its angle/attr, S.C.E.-style (their a4 write-then-overwrite order)
        move.w  d1, -(sp)              ; primary angle
        move.w  d2, -(sp)              ; primary attr
        move.w  4(sp), d3              ; reload layer (under the two stashes)
        subi.w  #pstep, paxreg
        bsr.s   .cell
        tst.b   d2
        bne.s   .back_supplied
        move.w  (sp), d2               ; back cell empty → primary's attr
        move.w  2(sp), d1              ; ... and angle
.back_supplied:
        addq.l  #4, sp
        probeSub paxreg, psubflip, d3
        add.w   d3, d0
        neg.w   d0
        bra.s   .done

; --- evaluate ONE cell -------------------------------------------------
; In:  d3.b layer, d4/d5 = X/Y (probe-axis reg pre-adjusted ±16 for
;      extension calls), d6.b class mask
; Out: d0.w = effective height: 0 empty/rejected, 1-15 partial,
;             16 full (incl. embedded-in-hanging — caller back-probes)
;      d1.b = raw angle, d2.b = attr (both 0 when d0 = 0)
; Clobbers: d0-d3, a1 (+ a0 via Collision_GetType — outer saved it)
.cell:
        move.w  d4, d0
        move.w  d5, d1
        bsr.w   Collision_GetType      ; d0.b = attr (clobbers d0-d3, a0)
        move.b  d0, d2
        beq.s   .cl_air
        moveq   #0, d3
        move.b  d2, d3                 ; attr index
        lea     (SolidityTable).l, a1
        move.b  (a1, d3.w), d0
        ; gate is "class == SOLID_ALL || (class & mask)"; ALL = TOP|LRB,
        ; so a single AND covers both cases for any nonzero mask
        and.b   d6, d0
        beq.s   .cl_air                ; wrong class for this sensor → air
        lea     (AngleTable).l, a1
        move.b  (a1, d3.w), d1         ; raw angle (odd flag passes through)
        lsl.w   #4, d3                 ; attr × 16
        move.w  pcolreg, d0
        andi.w  #$F, d0                ; height-column index
        add.w   d0, d3
        lea     (ptable).l, a1
        move.b  (a1, d3.w), d0
        ext.w   d0
    if pnegate
        neg.w   d0                     ; mirror anchor semantics (Up/Right)
    endif
        beq.s   .cl_air                ; height 0 → empty column
        bmi.s   .cl_hanging
        rts                            ; 1..15 partial / 16 full

.cl_hanging:
        ; near-edge-anchored run (h < 0, depth −h). S.C.E. bmi rule:
        ; probe sub-coordinate inside the run (sub + h < 0) → embedded,
        ; treat as full; outside → no surface this side, treat as air
        probeSub paxreg, psubflip, d3
        add.w   d3, d0
        bpl.s   .cl_air
        moveq   #16, d0
        rts

.cl_air:
        moveq   #0, d0
        moveq   #0, d1
        moveq   #0, d2
        rts
        endm

; -----------------------------------------------
; The four stamped cores
;          name                table          col axis step neg flip
; -----------------------------------------------
        probeCore Collision_ProbeDown,  HeightMaps,    d4, d5,  16, 0, 0
        probeCore Collision_ProbeUp,    HeightMaps,    d4, d5, -16, 1, 1
        probeCore Collision_ProbeRight, HeightMapsRot, d5, d4,  16, 1, 0
        probeCore Collision_ProbeLeft,  HeightMapsRot, d5, d4, -16, 0, 1

; -----------------------------------------------
; Player_SensorPair — run one probe core on a sensor pair, keep the closer
; In:  a2 = probe core (Collision_Probe*), d0.w/d1.w = sensor A engine X/Y,
;      d4.w/d5.w = sensor B engine X/Y, d3.b = layer, d6.b = class mask
; Out: d0.w dist, d1.b angle (raw), d2.b attr — A (first) wins ties
; Clobbers: d0-d5, a1 (d6/d7/a0/a2 preserved)
; -----------------------------------------------
Player_SensorPair:
        movem.w d3-d5, -(sp)           ; layer + B coords across probe A
        jsr     (a2)
        movem.w (sp)+, d3-d5
        move.w  d0, -(sp)              ; A dist
        move.w  d1, -(sp)              ; A angle
        move.w  d2, -(sp)              ; A attr
        move.w  d4, d0
        move.w  d5, d1
        jsr     (a2)                   ; B result in d0/d1/d2
        move.w  (sp)+, d3              ; A attr
        move.w  (sp)+, d4              ; A angle
        move.w  (sp)+, d5              ; A dist
        cmp.w   d0, d5                 ; A − B
        bgt.s   .b_wins
        move.w  d5, d0                 ; A ≤ B → A wins (ties → A)
        move.b  d4, d1
        move.b  d3, d2
.b_wins:
        rts

; -----------------------------------------------
; Player_SensorFloor — A/B floor pair, rotated by Player_Quadrant
; In:  a0 = player SST
; Out: d0.w = dist (closer sensor; A = the −cross-offset sensor wins ties)
;      d1.b = angle with resolution policy applied: odd flag OR
;             |angle − SST_angle| ≥ $20 (byte wraparound) → substitute the
;             quadrant cardinal (Player_Quadrant << 6)
;      d2.b = attr
; Clobbers: d0-d7, a1-a2
; Note: radii = SST_width/height_pixels >> 1. The player state hooks
;       store 2r+1 sizes (standing 19/39 → radii 9/19, the exact classic
;       values — resolved in Task 5); the wrappers just halve whatever
;       is there.
; -----------------------------------------------
Player_SensorFloor:
        ; On a solid object the object IS the floor — Touch_Solid snapped us
        ; onto its top and holds our position. Report flat & touching (dist 0,
        ; angle 0, solid) so EVERY grounded floor query behaves as on flat
        ; ground (spindash charge maintenance, etc.) instead of detaching when
        ; the terrain probe finds no tile under the object. The single
        ; chokepoint that makes "standing on a solid = standing on ground"
        ; hold for all grounded states. Ceiling probes enter at
        ; Player_SensorSurface (via Player_SensorCeiling) and are unaffected.
        btst    #ST_ON_OBJECT, SST_status(a0)
        beq.s   .terrain
        moveq   #0, d0                 ; dist = touching (Player_SnapToSurface no-op)
        moveq   #0, d1                 ; angle = flat
        moveq   #1, d2                 ; nonzero attr = floor present
        rts
.terrain:
        moveq   #SOLID_TOP, d6         ; floor class: top-only + all pass,
                                       ; lrb-only (jump-up-through) rejected
        moveq   #0, d7                 ; probe along the quadrant's "down"
        bra.s   Player_SensorSurface

; -----------------------------------------------
; Player_SensorCeiling — C/D pair (floor pair mirrored to the head side)
; Same contract as Player_SensorFloor, but the angle policy is S.C.E.'s
; ceiling rule (loc_F7E2): substitute the facing cardinal ONLY on the odd
; flag — an even slanted-ceiling angle passes through untouched, which
; ceiling re-attach requires.
; -----------------------------------------------
Player_SensorCeiling:
        moveq   #SOLID_LRB, d6         ; ceiling class: top-only rejected
        moveq   #2, d7                 ; probe opposite the quadrant
        ; fall through

; shared pair body — d6 = class mask, d7 = quadrant offset (0/2)
Player_SensorSurface:
        moveq   #0, d3
        move.b  SST_layer(a0), d3
        move.w  SST_x_pos(a0), d4      ; 16.16 high word = integer px
        move.w  SST_y_pos(a0), d5
        moveq   #0, d0
        move.b  SST_width_pixels(a0), d0
        lsr.w   #1, d0                 ; cross-axis radius (x_rad in floor mode)
        moveq   #0, d1
        move.b  SST_height_pixels(a0), d1
        lsr.w   #1, d1                 ; probe-axis radius (y_rad in floor mode)
        moveq   #0, d2
        move.b  (Player_Quadrant).w, d2
        add.b   d7, d2
        andi.w  #3, d2                 ; effective probe direction
        add.w   d2, d2
        move.w  .case_table(pc, d2.w), d2
        jmp     .case_table(pc, d2.w)
.case_table:
        dc.w    .probe_down-.case_table     ; quadrant 0: floor mode
        dc.w    .probe_left-.case_table     ; quadrant 1 ($40 surface)
        dc.w    .probe_up-.case_table       ; quadrant 2: ceiling mode
        dc.w    .probe_right-.case_table    ; quadrant 3 ($C0 surface)

.probe_down:
        add.w   d1, d5                 ; probe Y = y + y_rad (feet)
        move.w  d4, d1
        sub.w   d0, d1                 ; A x = x − x_rad
        add.w   d0, d4                 ; B x = x + x_rad
        move.w  d1, d0
        move.w  d5, d1                 ; d0/d1 = A coords; d4/d5 = B coords
        lea     Collision_ProbeDown(pc), a2
        bra.s   .pair
.probe_up:
        sub.w   d1, d5                 ; probe Y = y − y_rad (head)
        move.w  d4, d1
        sub.w   d0, d1
        add.w   d0, d4
        move.w  d1, d0
        move.w  d5, d1
        lea     Collision_ProbeUp(pc), a2
        bra.s   .pair
.probe_left:
        ; wall modes swap the radius roles: probe-axis offset = y_rad
        ; along X, pair spread = x_rad along Y
        sub.w   d1, d4                 ; probe X = x − y_rad
        move.w  d5, d1
        sub.w   d0, d1                 ; A y = y − x_rad
        add.w   d0, d5                 ; B y = y + x_rad
        move.w  d4, d0
        lea     Collision_ProbeLeft(pc), a2
        bra.s   .pair
.probe_right:
        add.w   d1, d4                 ; probe X = x + y_rad
        move.w  d5, d1
        sub.w   d0, d1
        add.w   d0, d5
        move.w  d4, d0
        lea     Collision_ProbeRight(pc), a2
.pair:
        bsr.w   Player_SensorPair      ; d0/d1/d2 = closer sensor (raw angle)

        ; angle resolution: cardinal = ((Player_Quadrant + d7) & 3) << 6
        move.b  (Player_Quadrant).w, d3
        add.b   d7, d3
        andi.b  #3, d3
        ror.b   #2, d3                 ; 0/1/2/3 → $00/$40/$80/$C0
        btst    #0, d1
        bne.s   .substitute            ; odd flag → no usable angle
        cmpi.b  #2, d7
        beq.s   .keep                  ; ceiling pair: odd-flag rule only
        move.b  d1, d4                 ; floor pair: divergence snap too
        sub.b   SST_angle(a0), d4      ; byte difference wraps naturally
        bpl.s   .diff_pos
        neg.b   d4
.diff_pos:
        cmpi.b  #$20, d4
        blo.s   .keep                  ; |Δ| < $20 → trust the surface angle
.substitute:
        move.b  d3, d1
.keep:
        rts

; -----------------------------------------------
; Player_SensorWallAt — push probe left/right at an explicit point (the
; airborne probes' d4-sign convention). Caller passes the PRE-OFFSET
; probe point (e.g. x ± PUSH_RADIUS) in d0/d1 plus the direction sign
; in d4 (< 0 → left, ≥ 0 → right); no SST position fetch, no further
; offsetting. Thin shim onto Player_SensorWallDir.
;
; Player_SensorWallDir — push probe in any of the four directions
; (quadrant-aware grounded wall check, Task 7).
; In:  a0 = player SST
;      d0.w/d1.w = probe point engine X/Y (pre-offset, caller's business
;             — incl. the grounded +8 at angle==0 / −5 rolling offsets)
;      d2.w = direction 0/1/2/3 = down/up/right/left (probe-core order)
; Out: d0.w dist, d1.b angle (facing cardinal substituted on odd flag),
;      d2.b attr
; Clobbers: d0-d6, a1 (d7/a0/a2+ preserved — Ground_Move keeps its
;      direction code in d7 across the call)
; -----------------------------------------------
Player_SensorWallAt:
        moveq   #2, d2                 ; right
        tst.w   d4
        bpl.s   Player_SensorWallDir
        moveq   #3, d2                 ; left
        ; fall through

Player_SensorWallDir:
        moveq   #SOLID_LRB, d6         ; wall class: jump-through rejected
        moveq   #0, d3
        move.b  SST_layer(a0), d3
        add.w   d2, d2
        move.w  .dir_table(pc,d2.w), d2
        jmp     .dir_table(pc,d2.w)
.dir_table:
        dc.w    .down-.dir_table
        dc.w    .up-.dir_table
        dc.w    .right-.dir_table
        dc.w    .left-.dir_table
.down:
        bsr.w   Collision_ProbeDown
        moveq   #0, d3                 ; floor-facing cardinal
        bra.s   .resolve
.up:
        bsr.w   Collision_ProbeUp
        move.b  #$80, d3               ; ceiling-facing cardinal
        bra.s   .resolve
.right:
        bsr.w   Collision_ProbeRight
        move.b  #$C0, d3               ; right-wall facing cardinal
        bra.s   .resolve
.left:
        bsr.w   Collision_ProbeLeft
        moveq   #$40, d3               ; left-wall facing cardinal
.resolve:
        btst    #0, d1
        beq.s   .keep
        move.b  d3, d1
.keep:
        rts

; -----------------------------------------------
; Player_AtLedgeEdge — true when the leading foot is over a ledge edge, for
; the idle balance/teeter animation. Probes the floor one foot-width toward
; the FACING direction (single downward probe via Player_SensorPair). If that
; probe finds no nearby ground while the body is still supported (caller gates
; on grounded-at-rest), the player is teetering.
; In:  a0 = player SST (grounded, at rest — caller gates this)
; Out: d0 = 0 and Z set (beq) = solidly supported; d0 = 1 and Z clear (bne)
;      = at an edge. (Z reflects d0 so the caller can branch on beq/bne.)
; Clobbers: d0-d5, a1-a2
; -----------------------------------------------
LEDGE_PROBE_REACH = PLAYER_X_RADIUS+2    ; just past the support foot
LEDGE_NO_GROUND   = 8                    ; floor dist beyond this = no ground
                                         ; under the leading foot (TUNE at the
                                         ; Task 10 visual pass if needed)

Player_AtLedgeEdge:
        moveq   #0, d3
        move.b  SST_layer(a0), d3                ; layer select for the probe
        moveq   #SOLID_TOP, d6                   ; floor class (matches Player_SensorFloor)
        ; foot Y = y + y_radius
        moveq   #0, d1
        move.b  SST_height_pixels(a0), d1
        lsr.w   #1, d1
        add.w   SST_y_pos(a0), d1                ; high word = integer px
        ; probe X = x offset toward facing
        move.w  SST_x_pos(a0), d0
        btst    #ST_XFLIP, SST_status(a0)
        bne.s   .face_left
        addi.w  #LEDGE_PROBE_REACH, d0           ; facing right
        bra.s   .single
.face_left:
        subi.w  #LEDGE_PROBE_REACH, d0           ; facing left
.single:
        move.w  d0, d4                           ; B = A (single-point probe)
        move.w  d1, d5
        lea     Collision_ProbeDown(pc), a2
        bsr.w   Player_SensorPair                ; d0 = floor distance at the foot
        cmpi.w  #LEDGE_NO_GROUND, d0
        bgt.s   .at_edge
        moveq   #0, d0                           ; supported -> Z set
        rts
.at_edge:
        moveq   #1, d0                           ; edge -> Z clear
        rts
