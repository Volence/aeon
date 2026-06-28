; Test parent — multi-part object that spawns children, then self-destructs
; Demonstrates CreateChild_Normal lifecycle + DeleteChildren cascade.
; Now also demos moving-parent-children-follow via stored child offsets.

; Parent custom layout
TParentV struct
life_timer      ds.w 1                  ; countdown to self-destruct
x_dir           ds.b 1                  ; 0 = right, 1 = left
TParentV endstruct
        objvarsCheck TParentV_len
_parent_life_timer      = SST_sst_custom+TParentV_life_timer
_parent_x_dir           = SST_sst_custom+TParentV_x_dir

; Child custom layout (same SST_sst_custom region, different fields):
TOrbitChildV struct
angle           ds.b 1                  ; current orbit angle (0-255)
phase_offset    ds.b 1                  ; initial phase (per-child)
radius          ds.w 1                  ; orbit radius in pixels
TOrbitChildV endstruct
        objvarsCheck TOrbitChildV_len
_child_angle            = SST_sst_custom+TOrbitChildV_angle
_child_phase_offset     = SST_sst_custom+TOrbitChildV_phase_offset
_child_radius           = SST_sst_custom+TOrbitChildV_radius

PARENT_LIFETIME         = 180                   ; frames before self-destruct (3 seconds)
PARENT_SPEED            = 1                     ; px/frame swing rate
PARENT_SWING_RANGE      = 60                    ; pixels each side from start
CHILD_ORBIT_SPEED       = 4                     ; angle units per frame (4 = ~90°/sec)
CHILD_ORBIT_RADIUS      = 32                    ; pixels

; -----------------------------------------------
; TestChildPart — child init: derive starting angle from spawn offset,
; advance to orbit loop. Children orbit the parent at fixed radius,
; phase-offset 120° apart so they form an equilateral triangle.
; In:  a0 = SST pointer (position, mappings, art_tile set by CreateChild_Normal)
; Out: none
; Clobbers: d0-d2, a1
; -----------------------------------------------
TestChildPart:
        ori.b   #3<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)

        ; Derive initial phase from spawn offset.
        ; CreateChild_Normal places us at parent.pos + (x_off, y_off):
        ;   left:  (-24,   0) → angle 192 (270° or -X axis)
        ;   right: ( 24,   0) → angle  64 (90° or +X axis)
        ;   above: (  0, -24) → angle   0 (0° or -Y axis upward)
        ; We use a simple lookup: sign of (sx, sy) determines which 90° quadrant.
        movea.w SST_parent_ptr(a0), a1
        move.w  SST_x_pos(a0), d1
        sub.w   SST_x_pos(a1), d1               ; d1 = signed dx
        move.w  SST_y_pos(a0), d2
        sub.w   SST_y_pos(a1), d2               ; d2 = signed dy

        ; Quadrant lookup using sign of dx, dy.
        ; Angle byte: 0=up, 64=right, 128=down, 192=left.
        moveq   #0, d0                          ; default: above (-Y)
        tst.w   d2
        bmi.s   .save_angle                     ; dy negative → above → keep 0
        tst.w   d1
        bmi.s   .set_left
        moveq   #64, d0                         ; right (+X)
        bra.s   .save_angle
.set_left:
        move.w  #192, d0                        ; left (-X)
.save_angle:
        move.b  d0, _child_phase_offset(a0)
        move.b  d0, _child_angle(a0)
        move.w  #CHILD_ORBIT_RADIUS, _child_radius(a0)

        move.w  #objroutine(TestChildPart_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestChildPart_Main — orbit parent each frame
; (Draw_Sprite early-returns because parent has RF_MULTISPRITE; the
;  sibling walk in Render_Sprites picks up our updated x_pos/y_pos.)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
TestChildPart_Main:
        movea.w SST_parent_ptr(a0), a1
        move.l  a1, d0
        beq.s   .orphan_delete

        ; Advance angle
        move.b  _child_angle(a0), d0
        addq.b  #CHILD_ORBIT_SPEED, d0
        move.b  d0, _child_angle(a0)

        ; sin/cos at d0 → d0=sin*$100, d1=cos*$100
        andi.w  #$FF, d0
        movem.l d2-d3/a1, -(sp)
        jsr     GetSineCosine
        movem.l (sp)+, d2-d3/a1

        ; Scale: sine amplitude = $100 = 256, radius = 32 = 2^5.
        ; offset = (sin × 32) / 256 = sin >> 3. Constant shift, no multiply.
        ; (Stored _child_radius is informational; the shift is hard-coded.)
        ; Negate cos so angle 0 puts the child above parent (screen -Y is up).
        asr.w   #3, d0                          ; d0.w = scaled X offset
        neg.w   d1
        asr.w   #3, d1                          ; d1.w = scaled Y offset

        ; Apply: child.pos = parent.pos + (dx, dy)
        add.w   SST_x_pos(a1), d0
        move.w  d0, SST_x_pos(a0)
        add.w   SST_y_pos(a1), d1
        move.w  d1, SST_y_pos(a0)

        jmp     Draw_Sprite

.orphan_delete:
        jmp     DeleteObject

; -----------------------------------------------
; TestParent — init routine
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        moveq   #0, d0
        move.b  d0, SST_mapping_frame(a0)       ; frame 0 (color 1 square)
        ori.b   #3<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        bset    #RF_MULTISPRITE, SST_render_flags(a0)   ; batched render
        move.w  #PARENT_LIFETIME, _parent_life_timer(a0)

        ; Spawn 3 children around parent
        lea     .child_desc(pc), a1
        jsr     CreateChild_Normal

        move.w  #objroutine(TestParent_Main), SST_code_addr(a0)
        bra.s   TestParent_Main

; Child descriptor: 3 children at offsets around parent
.child_desc:
        dc.w    objroutine(TestChildPart)
        dc.b    -24, 0                          ; left of parent
        dc.w    objroutine(TestChildPart)
        dc.b    24, 0                           ; right of parent
        dc.w    objroutine(TestChildPart)
        dc.b    0, -24                          ; above parent
        dc.w    0                               ; terminator

; -----------------------------------------------
; TestParent_Main — per-frame: countdown, oscillate horizontally,
; eventually self-destruct with children
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent_Main:
        subq.w  #1, _parent_life_timer(a0)
        bne.s   .move

        ; Timer expired — kill children then self
        jsr     DeleteChildren
        jmp     DeleteObject

.move:
        ; Oscillate parent X. Use lifetime as a phase counter.
        ; Direction byte at _parent_x_dir; 0 = right, 1 = left.
        tst.b   _parent_x_dir(a0)
        bne.s   .moving_left
        addq.w  #PARENT_SPEED, SST_x_pos(a0)
        move.w  _parent_life_timer(a0), d0
        cmpi.w  #PARENT_LIFETIME-PARENT_SWING_RANGE, d0
        bge.s   .draw
        move.b  #1, _parent_x_dir(a0)
        bra.s   .draw

.moving_left:
        subq.w  #PARENT_SPEED, SST_x_pos(a0)
        move.w  _parent_life_timer(a0), d0
        cmpi.w  #PARENT_LIFETIME-(2*PARENT_SWING_RANGE), d0
        bge.s   .draw
        move.b  #0, _parent_x_dir(a0)
        ; reset phase: bump life timer back so we swing right again
        move.w  #PARENT_LIFETIME, _parent_life_timer(a0)

.draw:
        jmp     Draw_Sprite
