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
; flag — an even slanted-ceiling angle passes through untouched (Task 5's
; ceiling re-attach needs it).
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

    ifdef __DEBUG__
; -----------------------------------------------
; PlayerSensors_SelfCheck — probe known cells, compare against
; generator-computed expectations. Runs once from the OJZ scroll-test
; init (DEBUG builds, after Tile_Cache_Init has filled the cache).
; Expectations are SECTION-LOCAL pixel coordinates of the boot section,
; composed to engine space via the slot-0 origin. Every expected value
; below was produced by tools/collision_pipeline.py --probe (commands in
; the table comments) plus the distance formulas of this file.
; In:  none
; Out: none (RaiseError on any mismatch)
; Clobbers: d0-d7, a1-a3
; -----------------------------------------------
PlayerSensors_SelfCheck:
        ; boot init puts the act's start section in slot 0; this table is
        ; data for OJZ act 1 section (0,0) — bail loudly if remapped
        tst.w   (Slot_Section_Map).w
        beq.s   .slot0_ok
        RaiseError "PlayerSensors self-check: slot 0 is not section (0,0)"
.slot0_ok:
        lea     PlayerSensors_CheckTable(pc), a2
        move.w  (a2)+, d7              ; entry count − 1
.loop:
        move.w  (a2)+, d0              ; section-local X
        add.w   (Slot_Origins).w, d0   ; + slot-0 origin X (16.16 high word)
        move.w  (a2)+, d1              ; section-local Y
        ; Slot_Origins[0] origin_y is initialised to 0 and read nowhere;
        ; the collision domain's Y mapping authority is Engine_To_World_Row
        ; (SLOT_ORIGIN_U + sec_y*2048) — compose Y with the constant
        addi.w  #SLOT_ORIGIN_U, d1
        moveq   #0, d3
        move.b  (a2)+, d3              ; layer
        move.b  (a2)+, d6              ; solidity-class mask
        moveq   #0, d2
        move.b  (a2)+, d2              ; direction 0/1/2/3 = down/up/right/left
        addq.l  #1, a2                 ; pad byte
        add.w   d2, d2
        add.w   d2, d2
        lea     PlayerSensors_CheckDispatch(pc), a3
        movea.l (a3, d2.w), a3
        jsr     (a3)                   ; d0 dist, d1 angle, d2 attr
        move.w  (a2)+, d3              ; expected dist
        cmp.w   d0, d3
        bne.s   .fail_dist
        move.b  (a2)+, d3              ; expected angle
        cmp.b   d1, d3
        bne.s   .fail_angle
        move.b  (a2)+, d3              ; expected attr
        cmp.b   d2, d3
        bne.w   .fail_attr             ; .w: jumps two RaiseError strings — out of short range
        dbf     d7, .loop
        rts
; d7 is the dbf COUNTDOWN (N−1−i); report the table's 0-based entry order
; as i = (N−1) − d7, re-reading N−1 from the table's count word. d4 is
; free here (clobbered by the probe jsr every iteration anyway).
.fail_dist:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4                 ; d4 = ascending 0-based entry index
        RaiseError "PlayerSensors self-check: entry %<.w d4> dist %<.w d0>, expected %<.w d3>"
.fail_angle:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4
        RaiseError "PlayerSensors self-check: entry %<.w d4> angle %<.b d1>, expected %<.b d3>"
.fail_attr:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4
        RaiseError "PlayerSensors self-check: entry %<.w d4> attr %<.b d2>, expected %<.b d3>"

PlayerSensors_CheckDispatch:
        dc.l    Collision_ProbeDown
        dc.l    Collision_ProbeUp
        dc.l    Collision_ProbeRight
        dc.l    Collision_ProbeLeft

; -----------------------------------------------
; PlayerSensors_SelfCheck_RowFill — exercise the ROW fill path, then re-probe.
;
; WHY: PlayerSensors_SelfCheck above probes cells that Tile_Cache_Init filled
; via the COLUMN path (TileCache_CopyBlockColumn). It therefore CANNOT catch a
; bug in TileCache_FillRow — the vertical-streaming path — which is exactly how
; the §5 +64px collision-shift bug (FillRow used intra_row*8, valid only on even
; rows; FillRow copies collision on ODD rows) reached live play unnoticed.
;
; This routine force-fills, via TileCache_FillRow, the two ODD world tile rows
; that COMPLETE the 16px collision cells the check table reads (ground/wall at
; section-local y=384..415 → world rows 49 and 51 for boot section (0,0)), then
; re-runs the same table. A row-path collision-addressing regression corrupts
; those re-filled cells and trips a RaiseError that NAMES the row path.
;
; BOOT-SAFETY: both target rows already lie inside the initial cache window
; [Cache_Top_Row=2 .. Cache_Bottom_Row=61] (camera start_local_y=$100), so
; FillRow re-fills them IN PLACE with identical data — idempotent. It touches
; no camera state and no cursor except Cache_Fill_RowResume_Row, which we
; restore to $FFFF (its post-Init value) afterward. Cache_Fill_Budget is
; topped up before each call so any evicted staging block re-decompresses
; (decompress is a pure ROM→slot copy — idempotent). Normal play starts in the
; exact state Tile_Cache_Init left it. Runs LAST, after the column self-check.
; In:  none (assumes Tile_Cache_Init + PlayerSensors_SelfCheck have run)
; Out: none (RaiseError on any mismatch)
; Clobbers: d0-d7, a1-a3
; -----------------------------------------------
SENSCHK_ROW_LO = 49             ; odd world tile row completing cell y=384..399
SENSCHK_ROW_HI = 51             ; odd world tile row completing cell y=400..415
PlayerSensors_SelfCheck_RowFill:
        ; assert both target rows sit inside the current cache window — if a
        ; future camera-start change moves the window, the in-place exercise
        ; would silently fill out-of-window (no-op) and stop testing anything.
        move.w  (Cache_Top_Row).w, d0
        cmpi.w  #SENSCHK_ROW_LO, d0
        bls.s   .win_top_ok
        RaiseError "RowFill self-check: probe row 49 above cache top %<.w d0>"
.win_top_ok:
        move.w  (Cache_Bottom_Row).w, d0
        cmpi.w  #SENSCHK_ROW_HI, d0
        bhs.s   .win_bot_ok
        RaiseError "RowFill self-check: probe row 51 below cache bottom %<.w d0>"
.win_bot_ok:
        ; force ROW fills of the two cell-completing rows (budget reset per
        ; call: a single row can span up to ~6 blocks = BLOCK_DECOMP_BUDGET)
        move.w  #BLOCK_DECOMP_BUDGET, (Cache_Fill_Budget).w
        move.w  #SENSCHK_ROW_LO, d5
        bsr.w   TileCache_FillRow
        move.w  #BLOCK_DECOMP_BUDGET, (Cache_Fill_Budget).w
        move.w  #SENSCHK_ROW_HI, d5
        bsr.w   TileCache_FillRow
        ; restore the row-resume slot to its post-Init idle value
        move.w  #$FFFF, (Cache_Fill_RowResume_Row).w

        ; re-run the same table; mismatches now indict the ROW path
        lea     PlayerSensors_CheckTable(pc), a2
        move.w  (a2)+, d7
.loop:
        move.w  (a2)+, d0
        add.w   (Slot_Origins).w, d0
        move.w  (a2)+, d1
        addi.w  #SLOT_ORIGIN_U, d1
        moveq   #0, d3
        move.b  (a2)+, d3              ; layer
        move.b  (a2)+, d6             ; solidity mask
        moveq   #0, d2
        move.b  (a2)+, d2             ; direction
        addq.l  #1, a2               ; pad
        add.w   d2, d2
        add.w   d2, d2
        lea     PlayerSensors_CheckDispatch(pc), a3
        movea.l (a3, d2.w), a3
        jsr     (a3)
        move.w  (a2)+, d3
        cmp.w   d0, d3
        bne.s   .fail_dist
        move.b  (a2)+, d3
        cmp.b   d1, d3
        bne.s   .fail_angle
        move.b  (a2)+, d3
        cmp.b   d2, d3
        bne.w   .fail_attr
        dbf     d7, .loop
        rts
.fail_dist:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4
        RaiseError "RowFill self-check: entry %<.w d4> dist %<.w d0>, expected %<.w d3>"
.fail_angle:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4
        RaiseError "RowFill self-check: entry %<.w d4> angle %<.b d1>, expected %<.b d3>"
.fail_attr:
        move.w  PlayerSensors_CheckTable(pc), d4
        sub.w   d7, d4
        RaiseError "RowFill self-check: entry %<.w d4> attr %<.b d2>, expected %<.b d3>"

; one expectation: x.w, y.w (section-local), layer.b, mask.b, dir.b,
; pad.b, dist.w, angle.b, attr.b — 12 bytes
SENSCHK_DOWN  = 0
SENSCHK_UP    = 1
SENSCHK_RIGHT = 2
SENSCHK_LEFT  = 3
senschk macro px, py, pllayer, pmask, pdir, pdist, pangle, pattr
        dc.w    px, py
        dc.b    pllayer, pmask, pdir, 0
        dc.w    pdist
        dc.b    pangle, pattr
        endm

; Cell facts below: tools/collision_pipeline.py --probe 0 X Y (section 0;
; run dated 2026-06-12 — "data/collision/*.bin match this walk").
; Ground row: full attr $01 (sol 3, angle $FF odd) at y=384..; air above.
; Platform row at y=208..223 exists on path A only (sol 1 = top-only):
; attr $04 = slope angle $10, heights [15,14,13,13,12,11,11,10,10,9,...].
; Wall/ceiling block: attr $01 fills (112..143, 400..415) and
; (96..143, 384..399); (96..111, 400..415) and (144..159, 400..415) air.
PlayerSensors_CheckTable:
        dc.w    (PlayerSensors_CheckTable_End-PlayerSensors_CheckTable-2)/12-1
        ; 0: --probe 0 256 384: full $01 / sub_y 0; cell above air →
        ;    back-probe; primary supplies angle/attr; dist = −sub_y = 0
        senschk 256, 384, 0, SOLID_TOP, SENSCHK_DOWN,    0, $FF, $01
        ; 1: --probe 0 256 376: air / sub_y 8; forward cell full →
        ;    dist = 32 − 16 − 8 = 8
        senschk 256, 376, 0, SOLID_TOP, SENSCHK_DOWN,    8, $FF, $01
        ; 2: --probe 0 256 388: full / sub_y 4, embedded; back cell air →
        ;    dist = −4, primary's angle/attr
        senschk 256, 388, 0, SOLID_TOP, SENSCHK_DOWN,   -4, $FF, $01
        ; 3: --probe 0 256 300 (+ 0 256 316): both cells air → sentinel
        senschk 256, 300, 0, SOLID_TOP, SENSCHK_DOWN,   32, $00, $00
        ; 4: --probe 0 136 212: slope attr $04, h[sub_x=8] = 10, sub_y 4 →
        ;    dist = 16 − 10 − 4 = 2, angle $10 (even — raw passthrough)
        senschk 136, 212, 0, SOLID_TOP, SENSCHK_DOWN,    2, $10, $04
        ; 5: same cell, layer B: --probe shows path B air here AND in the
        ;    forward cell (0 136 228) → sentinel. Proves A/B plumbing.
        senschk 136, 212, 1, SOLID_TOP, SENSCHK_DOWN,   32, $00, $00
        ; 6: same cell, wall-class mask: sol 1 (top-only) fails the
        ;    SOLID_LRB gate in BOTH cells (fwd attr $02 is sol 1 too) →
        ;    sentinel. Proves the solidity gate.
        senschk 136, 212, 0, SOLID_LRB, SENSCHK_DOWN,   32, $00, $00
        ; 7: right probe at (104,408): cell air, fwd cell (112,400) full →
        ;    wall face at x=112; dist = 112 − 104 = 8 (= 32 − 16 − sub_x 8)
        senschk 104, 408, 0, SOLID_LRB, SENSCHK_RIGHT,   8, $FF, $01
        ; 8: up probe at (104,408): cell air, fwd cell (96,384) full →
        ;    ceiling bottom pixel y=399; dist = 408 − 399 = 9
        ;    (= 32 − 16 − (sub_y 8 ^ $F))
        senschk 104, 408, 0, SOLID_LRB, SENSCHK_UP,      9, $FF, $01
        ; 9: left probe at (152,408): cell air, fwd cell (128,400) full →
        ;    wall right face pixel x=143; dist = 152 − 143 = 9
        senschk 152, 408, 0, SOLID_LRB, SENSCHK_LEFT,    9, $FF, $01
PlayerSensors_CheckTable_End:

        if (PlayerSensors_CheckTable_End-PlayerSensors_CheckTable-2) <> ((PlayerSensors_CheckTable_End-PlayerSensors_CheckTable-2)/12)*12
          error "PlayerSensors_CheckTable entries are not 12 bytes each"
        endif
    endif ; __DEBUG__
