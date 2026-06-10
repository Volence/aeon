; Child creation — data-driven parent-child object spawning

; -----------------------------------------------
; PopulateSpawnedPieceCount — refresh sprite_piece_count for newly-spawned
; SST in a2. Called from each CreateChild_*/CreateEffect_* site after
; mappings have been inherited. Direct-alloc path that bypasses Load_Object.
;
; In:  a2 = newly-spawned SST (with mappings + mapping_frame already set)
; Out: SST_sprite_piece_count(a2) populated from current frame data
; Preserves: all caller registers
; -----------------------------------------------
PopulateSpawnedPieceCount:
        movem.l d0/a0-a1, -(sp)
        movea.l SST_mappings(a2), a0
        move.l  a0, d0
        beq.s   .skip
        moveq   #0, d0
        move.b  SST_mapping_frame(a2), d0
        add.w   d0, d0                  ; word offset
        move.w  (a0,d0.w), d0           ; offset to frame data
        move.w  (a0,d0.w), d0           ; first word = piece count
        move.b  d0, SST_sprite_piece_count(a2)
.skip:
        movem.l (sp)+, d0/a0-a1
        rts

; -----------------------------------------------
; CreateChild_Normal — spawn children from a descriptor table
; Allocates from Dynamic pool. Each child inherits parent's
; mappings and art_tile. Chains children via sibling_ptr.
;
; Descriptor format (4 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(ChildCode)   ; child code_addr (0 = end)
;   dc.b x_offset_signed         ; signed byte, relative to parent X
;   dc.b y_offset_signed         ; signed byte, relative to parent Y
;
; In:  a0 = parent SST pointer
;      a1 = descriptor table pointer (ROM)
; Out: none (children allocated, or silently skipped if pool full)
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateChild_Normal:
        move.w  SST_sibling_ptr(a0), d3 ; d3 = chain tail (0 if no children yet)
.child_loop:
        move.w  (a1)+, d2               ; d2 = child code_addr
        beq.s   .done                   ; 0 = end of table

        movem.l d3/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = child SST
        movem.l (sp)+, d3/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position = parent + signed byte offset (16.16)
        move.b  (a1)+, d0               ; x_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0               ; y_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Link: child -> parent
        move.w  a0, SST_parent_ptr(a2)

        ; Chain into sibling list (prepend)
        move.w  d3, SST_sibling_ptr(a2) ; child points to previous head
        move.w  a2, d3                  ; new head = this child
        move.w  a2, SST_sibling_ptr(a0) ; parent always points to newest child

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .child_loop

.alloc_fail:
        movem.l (sp)+, d3/a0-a1
        ; Skip remaining descriptor bytes (code_addr already consumed)
        addq.w  #2, a1                  ; skip x_off, y_off
        tst.w   (a1)                    ; check next entry
        bne.s   .alloc_fail_skip        ; more entries to skip
.done:
        rts
.alloc_fail_skip:
        addq.w  #4, a1                  ; skip code_addr + offsets
        tst.w   (a1)
        bne.s   .alloc_fail_skip
        rts

; -----------------------------------------------
; CreateChild_Complex — spawn children with velocity and animation
;
; Descriptor format (14 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(ChildCode)   ; code_addr (0 = end)
;   dc.b x_offset, y_offset      ; signed bytes
;   dc.w x_velocity, y_velocity  ; child velocities
;   dc.l anim_table_ptr          ; child anim_table (ROM)
;   dc.b anim_id, pad            ; starting animation + alignment
;
; In:  a0 = parent SST, a1 = descriptor table (ROM)
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateChild_Complex:
        move.w  SST_sibling_ptr(a0), d3
.child_loop:
        move.w  (a1)+, d2
        beq.w   .done

        movem.l d3/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2
        movem.l (sp)+, d3/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position
        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Velocity
        move.w  (a1)+, SST_x_vel(a2)
        move.w  (a1)+, SST_y_vel(a2)

        ; Animation
        move.l  (a1)+, SST_anim_table(a2)
        move.b  (a1)+, SST_anim(a2)
        move.b  #$FF, SST_prev_anim(a2)
        addq.w  #1, a1                  ; skip pad byte

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Parent link + sibling chain
        move.w  a0, SST_parent_ptr(a2)
        move.w  d3, SST_sibling_ptr(a2)
        move.w  a2, d3
        move.w  a2, SST_sibling_ptr(a0)

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .child_loop

.alloc_fail:
        movem.l (sp)+, d3/a0-a1
        lea     12(a1), a1              ; skip remaining 12 bytes of failed entry
.skip_rest:
        tst.w   (a1)
        beq.s   .done
        lea     14(a1), a1              ; skip full 14-byte entry
        bra.s   .skip_rest
.done:
        rts

; -----------------------------------------------
; CreateChild_FlipAware — Complex + mirror for parent X-flip
;
; In:  a0 = parent SST, a1 = descriptor table (ROM)
; Out: none
; Clobbers: d0-d4, a1-a2
; -----------------------------------------------
CreateChild_FlipAware:
        moveq   #0, d4                  ; d4 = flip flag
        btst    #RF_XFLIP, SST_render_flags(a0)
        beq.s   .no_flip
        moveq   #1, d4
.no_flip:
        move.w  SST_sibling_ptr(a0), d3
.child_loop:
        move.w  (a1)+, d2
        beq.w   .done

        movem.l d3-d4/a0-a1, -(sp)
        jsr     AllocDynamic
        bne.w   .alloc_fail
        movea.l a1, a2
        movem.l (sp)+, d3-d4/a0-a1

        move.w  d2, SST_code_addr(a2)

        ; X position (negate offset if flipped)
        move.b  (a1)+, d0
        ext.w   d0
        tst.w   d4
        beq.s   .x_no_flip
        neg.w   d0
.x_no_flip:
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        ; Y position (never flipped)
        move.b  (a1)+, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; X velocity (negate if flipped)
        move.w  (a1)+, d0
        tst.w   d4
        beq.s   .xv_no_flip
        neg.w   d0
.xv_no_flip:
        move.w  d0, SST_x_vel(a2)
        move.w  (a1)+, SST_y_vel(a2)

        ; Animation
        move.l  (a1)+, SST_anim_table(a2)
        move.b  (a1)+, SST_anim(a2)
        move.b  #$FF, SST_prev_anim(a2)
        addq.w  #1, a1

        ; Inherit + flip child render_flags if parent is flipped
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)
        tst.w   d4
        beq.s   .rf_no_flip
        bset    #RF_XFLIP, SST_render_flags(a2)
.rf_no_flip:

        ; Links
        move.w  a0, SST_parent_ptr(a2)
        move.w  d3, SST_sibling_ptr(a2)
        move.w  a2, d3
        move.w  a2, SST_sibling_ptr(a0)

        bsr.w   PopulateSpawnedPieceCount

        bra.w   .child_loop

.alloc_fail:
        movem.l (sp)+, d3-d4/a0-a1
        lea     12(a1), a1              ; skip remaining 12 bytes of failed entry
.skip_rest:
        tst.w   (a1)
        beq.s   .done
        lea     14(a1), a1              ; skip full 14-byte entry
        bra.s   .skip_rest
.done:
        rts

; -----------------------------------------------
; CreateChild_Linked — spawn a chain of identical children
;
; In:  a0 = parent SST
;      d0.w = child code_addr (objroutine value)
;      d1.w = number of children to spawn
;      d2.b = X spacing between children (signed byte)
;      d3.b = Y spacing between children (signed byte)
; Out: none
; Clobbers: d0-d5, a1-a2
; -----------------------------------------------
CreateChild_Linked:
        subq.w  #1, d1                  ; adjust for dbf
        bmi.s   .done
        move.w  d0, d4                  ; d4 = code_addr (preserved)
        move.w  d1, d5                  ; d5 = counter (preserved)
        moveq   #0, d1                  ; d1 = previous child addr

        ; Start position = parent position
        move.l  SST_x_pos(a0), -(sp)    ; save running X on stack
        move.l  SST_y_pos(a0), -(sp)    ; save running Y on stack

.spawn_loop:
        movem.l d1-d5/a0, -(sp)
        jsr     AllocDynamic
        bne.s   .link_fail
        movea.l a1, a2                  ; a2 = child SST
        movem.l (sp)+, d1-d5/a0

        move.w  d4, SST_code_addr(a2)

        ; Position from running coordinates on stack
        ; Stack layout: [running_Y][running_X] at sp+0 and sp+4
        move.l  4(sp), SST_x_pos(a2)   ; running X
        move.l  (sp), SST_y_pos(a2)    ; running Y

        ; Advance running position by spacing
        move.b  d2, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   d0, 4(sp)              ; advance running X

        move.b  d3, d0
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   d0, (sp)               ; advance running Y

        ; Inherit from parent
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)
        move.w  a0, SST_parent_ptr(a2)

        ; Chain: previous child's sibling_ptr -> this child
        tst.w   d1
        beq.s   .first_child
        movea.w d1, a1
        move.w  a2, SST_sibling_ptr(a1)
        bra.s   .linked
.first_child:
        move.w  a2, SST_sibling_ptr(a0) ; parent -> first child
.linked:
        move.w  a2, d1                  ; this child becomes previous

        bsr.w   PopulateSpawnedPieceCount

        dbf     d5, .spawn_loop
        addq.w  #8, sp                  ; clean running position from stack
.done:
        rts

.link_fail:
        movem.l (sp)+, d1-d5/a0
        addq.w  #8, sp                  ; clean running position
        rts

; -----------------------------------------------
; DeleteChildren — walk sibling chain from parent and delete each child
;
; In:  a0 = parent SST
; Out: parent's sibling_ptr cleared
; Clobbers: d0-d1, a1-a2
; -----------------------------------------------
DeleteChildren:
        move.w  SST_sibling_ptr(a0), d0
        beq.s   .done                   ; no children

        move.w  #0, SST_sibling_ptr(a0) ; disconnect from parent

.walk_chain:
        movea.w d0, a1                  ; a1 = current child
        move.w  SST_sibling_ptr(a1), d0 ; d0 = next child (save before delete)

        ; Delete this child
        movem.l d0/a0, -(sp)
        movea.l a1, a0                  ; DeleteObject expects a0
        jsr     DeleteObject
        movem.l (sp)+, d0/a0

        tst.w   d0                      ; more children?
        bne.s   .walk_chain
.done:
        rts

; -----------------------------------------------
; CreateEffect_Normal — spawn effect children from a descriptor table
; Allocates from Effect pool (not Dynamic). Children are NOT linked
; into the parent's sibling chain — effects are fire-and-forget.
;
; Descriptor format (4 bytes per child, terminated by dc.w 0):
;   dc.w objroutine(EffectCode)   ; child code_addr (0 = end)
;   dc.b x_offset_signed          ; signed byte, relative to parent X
;   dc.b y_offset_signed          ; signed byte, relative to parent Y
;
; In:  a0 = parent SST pointer
;      a1 = descriptor table pointer (ROM)
; Out: none (effects allocated, or silently skipped if pool full)
; Clobbers: d0-d2, a1-a2
; -----------------------------------------------
CreateEffect_Normal:
.effect_loop:
        move.w  (a1)+, d2               ; d2 = effect code_addr
        beq.s   .done                   ; 0 = end of table

        movem.l a0-a1, -(sp)
        jsr     AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST
        movem.l (sp)+, a0-a1

        move.w  d2, SST_code_addr(a2)

        ; Position = parent + signed byte offset (16.16)
        move.b  (a1)+, d0               ; x_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_x_pos(a0), d0
        move.l  d0, SST_x_pos(a2)

        move.b  (a1)+, d0               ; y_offset signed byte
        ext.w   d0
        swap    d0
        clr.w   d0
        add.l   SST_y_pos(a0), d0
        move.l  d0, SST_y_pos(a2)

        ; Inherit mappings, art_tile from parent
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Set parent_ptr so effect can reference parent if needed
        move.w  a0, SST_parent_ptr(a2)

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .effect_loop

.alloc_fail:
        movem.l (sp)+, a0-a1
        addq.w  #2, a1                  ; skip x_off, y_off of failed entry
.skip_rest:
        tst.w   (a1)                    ; check next entry
        beq.s   .done
        addq.w  #4, a1                  ; skip full 4-byte entry
        bra.s   .skip_rest
.done:
        rts

; -----------------------------------------------
; CreateEffect_Simple — spawn N copies of the same effect at parent position
; Allocates from Effect pool. Fire-and-forget (no sibling chain).
;
; In:  a0 = parent SST pointer
;      d0.w = effect code_addr (objroutine value)
;      d1.w = number of copies to spawn
; Out: none (silently stops if pool exhausted)
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
CreateEffect_Simple:
        subq.w  #1, d1                  ; adjust for dbf
        bmi.s   .done
        move.w  d0, d2                  ; d2 = code_addr (preserved)
        move.w  d1, d3                  ; d3 = counter (preserved)

.spawn_loop:
        movem.l d2-d3/a0, -(sp)
        jsr     AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST
        movem.l (sp)+, d2-d3/a0

        move.w  d2, SST_code_addr(a2)

        ; Position = parent position
        move.l  SST_x_pos(a0), SST_x_pos(a2)
        move.l  SST_y_pos(a0), SST_y_pos(a2)

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        move.w  a0, SST_parent_ptr(a2)

        bsr.w   PopulateSpawnedPieceCount

        dbf     d3, .spawn_loop
.done:
        rts

.alloc_fail:
        movem.l (sp)+, d2-d3/a0
        rts
