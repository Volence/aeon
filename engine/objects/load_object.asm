; Load_Object — data-driven object spawning from type definitions
;
; Object definition format (ROM data block):
;   +0: dc.w  objroutine(Code)     ; code_addr (always present)
;   +2: dc.b  format_byte, 0       ; ODF_* bit flags + pad
;   +4: dc.l  mappings             ; sprite mappings pointer (0 = invisible)
;   +8: dc.w  art_tile             ; TEMPORARY — VRAM tile + palette (replaced by AllocVRAM later)
;   Then conditional fields in bit order:
;     ODF_VELOCITY (0):     dc.w x_vel, y_vel
;     ODF_COLLISION (1):    dc.b width, height, collision_type, pad
;     ODF_ANIMATION (2):    dc.l anim_table
;     ODF_SUBTYPE (3):      (no data — copies d2.b to SST_subtype)
;     ODF_RENDER_FLAGS (4): dc.b render_flags, pad
;     ODF_PRIORITY (5):     dc.w priority

; -----------------------------------------------
; Load_Object — spawn one object from a type definition
;
; In:  a1 = object definition pointer (ROM)
;      d0.w = X position (integer, world coords)
;      d1.w = Y position (integer, world coords)
;      d2.b = subtype (0 if unused)
; Out: Z set = success, a1 = new SST pointer
;      Z clear = allocation failed
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
Load_Object:
        movem.l d0-d2/a1, -(sp)
        jsr     AllocDynamic
        bne.w   .alloc_fail
        movea.l a1, a2                  ; a2 = new SST
        movem.l (sp)+, d0-d2/a1        ; restore X, Y, subtype, definition
        exg     a1, a2                  ; a1 = SST, a2 = definition

        ; code_addr
        move.w  (a2)+, SST_code_addr(a1)

        ; format byte (save in d3 for bit testing)
        move.b  (a2)+, d3
        addq.w  #1, a2                  ; skip pad

        ; mappings (always present)
        move.l  (a2)+, SST_mappings(a1)

        ; art_tile (TEMPORARY — always present until AllocVRAM)
        move.w  (a2)+, SST_art_tile(a1)

        ; X position → 16.16
        swap    d0
        clr.w   d0
        move.l  d0, SST_x_pos(a1)

        ; Y position → 16.16
        swap    d1
        clr.w   d1
        move.l  d1, SST_y_pos(a1)

        ; --- conditional fields (test format bits in order) ---

        btst    #ODF_VELOCITY, d3
        beq.s   .no_velocity
        move.w  (a2)+, SST_x_vel(a1)
        move.w  (a2)+, SST_y_vel(a1)
.no_velocity:

        btst    #ODF_COLLISION, d3
        beq.s   .no_collision
        move.b  (a2)+, SST_width_pixels(a1)
        move.b  (a2)+, SST_height_pixels(a1)
        move.b  (a2)+, SST_collision_resp(a1)
        addq.w  #1, a2                  ; skip pad
.no_collision:

        btst    #ODF_ANIMATION, d3
        beq.s   .no_animation
        move.l  (a2)+, SST_anim_table(a1)
        move.b  #$FF, SST_prev_anim(a1)
        move.b  #$FF, SST_prev_frame(a1)
.no_animation:

        btst    #ODF_SUBTYPE, d3
        beq.s   .no_subtype
        move.b  d2, SST_subtype(a1)
.no_subtype:

        btst    #ODF_RENDER_FLAGS, d3
        beq.s   .no_render_flags
        move.b  (a2)+, SST_render_flags(a1)
        addq.w  #1, a2                  ; skip pad
.no_render_flags:

        btst    #ODF_PRIORITY, d3
        beq.s   .no_priority
        move.w  (a2)+, SST_priority(a1)
.no_priority:

        moveq   #0, d0                  ; Z set = success
        rts

.alloc_fail:
        movem.l (sp)+, d0-d2/a1
        moveq   #1, d0                  ; Z clear = failed
        rts

; -----------------------------------------------
; Load_ObjectList — spawn objects from a definition list
;
; List format (10 bytes per entry, terminated by dc.l 0):
;   dc.l  ObjDef_XXX              ; definition pointer (0 = end)
;   dc.w  x_pos, y_pos            ; integer world coordinates
;   dc.w  subtype                  ; word for alignment (only low byte used)
;
; In:  a0 = object list pointer (ROM)
; Out: none (objects spawned, alloc failures silently skipped)
; Clobbers: d0-d3, a0-a2
; -----------------------------------------------
Load_ObjectList:
.loop:
        movea.l (a0)+, a1              ; a1 = definition pointer
        move.l  a1, d0
        beq.s   .done                  ; 0 = end of list
        move.w  (a0)+, d0              ; X position
        move.w  (a0)+, d1              ; Y position
        move.w  (a0)+, d2              ; subtype (low byte)
        move.l  a0, -(sp)
        jsr     Load_Object
        movea.l (sp)+, a0
        bra.s   .loop
.done:
        rts
