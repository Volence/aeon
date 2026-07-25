; Child creation - data-driven parent-child object spawning
;
; THE SIBLING-CHAIN CONTRACT (read before adding a creator or a caller).
; `sibling_ptr` is OVERLOADED: on a PARENT it is the head of that parent's
; child list; on a CHILD it is the next sibling in that list. One field, two
; meanings, so:
;   * A parent may not itself be a linked child. An object that is already in
;     someone's chain has its own `sibling_ptr` spoken for; letting it spawn
;     children overwrites that link and orphans every sibling behind it.
;     ONE LEVEL of nesting only. ASSERT COVERAGE IS DELIBERATELY PARTIAL:
;     the DEBUG rail rides CreateChild_Normal (the only chaining creator with
;     call sites) and CreateChild_Linked (its own childless-parent
;     constraint); Complex and FlipAware carry the constraint in their
;     headers ONLY. Chosen, not overlooked - an assert on a zero-caller proc
;     can never fire, while its message blob costs debug bytes that are not
;     free at the system level (past a threshold they push engine symbols
;     across $8000 and relocate the whole debug object bank). When either
;     creator gains a caller, it gains the assert in the same change.
;   * `DeleteChildren` is therefore NOT recursive by contract, not by
;     omission: a child cannot have children, so there is nothing to recurse
;     into. It also leaves each deleted child's `parent_ptr` alone - the slot
;     is zeroed wholesale by DeleteObject, so the stale value is unreachable.
;   * Chain SHAPE differs by creator, deliberately: Normal/Complex/FlipAware
;     PREPEND (each new child points at the old head, so the parent always
;     points at the NEWEST child), while Linked APPENDS (each child points at
;     the next one spawned). Both terminate only because a freshly allocated
;     slot's `sibling_ptr` is zero - DeleteObject zeroes the whole SST on
;     release and the pools start zeroed, so an allocated slot's links are
;     always clear. A future allocator that hands back dirty slots must zero
;     `sibling_ptr` or every walk here runs off into garbage.

; -----------------------------------------------
; PopulateSpawnedPieceCount - refresh sprite_piece_count for newly-spawned
; SST in a2. Called from each CreateChild_*/CreateEffect_* site after
; mappings have been inherited. Direct-alloc path that bypasses Load_Object.
;
; In:  a2 = newly-spawned SST - `mappings` must already be inherited.
;      `mapping_frame` is read as-is: every creator here spawns into a
;      freshly-zeroed slot, so it is ALWAYS frame 0 at this point (no call
;      site sets it). A null `mappings` leaves the field untouched.
; Out: SST_sprite_piece_count(a2) populated from that frame's header
; Preserves: all caller registers
; -----------------------------------------------
PopulateSpawnedPieceCount:
        movem.l d0/a0, -(sp)            ; a1 is never touched here - the shared
                                        ; template works in a0/d0
        movea.l SST_mappings(a2), a0
        move.l  a0, d0
        beq.s   .no_mappings
        moveq   #0, d0
        move.b  SST_mapping_frame(a2), d0
        add.w   d0, d0                  ; frame index -> word offset
        move.w  (a0,d0.w), d0           ; offset to this frame's data
        ; frame header: 4 signed bbox bytes (FRAME_BBOX_*), then the
        ; piece-count word at FRAME_PIECE_COUNT, then pieces at FRAME_PIECES
        move.w  FRAME_PIECE_COUNT(a0,d0.w), d0
        move.b  d0, SST_sprite_piece_count(a2)
.no_mappings:
        movem.l (sp)+, d0/a0
        rts

; -----------------------------------------------
; CreateChild_Normal - spawn children from a descriptor table
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
    ifdef __DEBUG__
        move.w  SST_parent_ptr(a0), d0
        assert.w d0, eq, #0             ; chain contract: a parent may not itself
                                        ; be a linked child (its sibling_ptr is
                                        ; the grandparent's link)
    endif
        move.w  SST_sibling_ptr(a0), d3 ; d3 = current chain head (newest child, 0 if no children yet)
.child_loop:
        move.w  (a1)+, d2               ; d2 = child code_addr
        beq.s   .done                   ; 0 = end of table

        ; ALLOC SAVE: the descriptor cursor is the ONLY register at risk.
        ; AllocDynamic's license is `clobbers(d0) out(a1 if eq) preserves(a0)`
        ; - an EXHAUSTIVE license, so d3/d4/a0 are contractually intact - and
        ; a1 is written on BOTH outcomes (the slot on success, the pop-rollback
        ; path on latch-full).
        move.l  a1, -(sp)
        bsr.w   AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = child SST
        movea.l (sp)+, a1

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

    ifdef __DEBUG__
        bsr.w   PopulateSpawnedPieceCount   ; debug: the chain-contract
                                        ; assert blob pushes this call out of .s reach
    else
        bsr.s   PopulateSpawnedPieceCount
    endif

        bra.s   .child_loop

.alloc_fail:
        ; Drop the saved cursor and stop. Walking the rest of the descriptor
        ; table would only advance a1, which is a declared clobber no caller
        ; reads - dead work on the failure path.
        addq.l  #4, sp
.done:
        ; Parent points at the newest child - ONE write per call, not one per
        ; child. Safe because the only reader of a PARENT's chain head outside
        ; this file is Render_Sprites' multi-sprite walk (sprites.asm:321; its
        ; second read at :371 walks a CHILD's next-sibling, not a head), and
        ; Render_Sprites runs in the game state's main loop AFTER RunObjects
        ; returns - the creators cannot be preempted by it. No interrupt path
        ; reads the field either: VInt_Level only DMAs the sprite buffer that
        ; the previous Render_Sprites already built. And where the original
        ; wrote the head every iteration, a mid-call observer would have seen a
        ; PARTIALLY linked chain; deferring means the head only ever points at
        ; a completed run. On the failure paths d3 still holds the head that
        ; survived, so they write back exactly what was already there.
        move.w  d3, SST_sibling_ptr(a0)
        rts

; -----------------------------------------------
; CreateChild_Complex - spawn children with velocity and animation
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
        beq.s   .done

        ; ALLOC SAVE: only the descriptor cursor (see CreateChild_Normal -
        ; AllocDynamic's exhaustive license leaves d3/d4/a0 intact).
        move.l  a1, -(sp)
        bsr.w   AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2
        movea.l (sp)+, a1

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
        move.b  #$FF, SST_prev_anim(a2) ; $FF = "no previous anim" (forces the
                                       ; animator's change detection on frame 1)
        addq.w  #1, a1                  ; skip pad byte

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; Parent link + sibling chain
        move.w  a0, SST_parent_ptr(a2)
        move.w  d3, SST_sibling_ptr(a2)
        move.w  a2, d3

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .child_loop

.alloc_fail:
        addq.l  #4, sp                  ; drop the saved cursor (see CreateChild_Normal)
.done:
        move.w  d3, SST_sibling_ptr(a0) ; deferred head write - see CreateChild_Normal
        rts

; -----------------------------------------------
; CreateChild_FlipAware - Complex + mirror for parent X-flip
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
        beq.s   .done

        ; ALLOC SAVE: only the descriptor cursor (see CreateChild_Normal -
        ; AllocDynamic's exhaustive license leaves d3/d4/a0 intact).
        move.l  a1, -(sp)
        bsr.w   AllocDynamic
        bne.s   .alloc_fail
        movea.l a1, a2
        movea.l (sp)+, a1

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
        move.b  #$FF, SST_prev_anim(a2) ; $FF = "no previous anim" (forces the
                                       ; animator's change detection on frame 1)
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

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .child_loop

.alloc_fail:
        addq.l  #4, sp                  ; drop the saved cursor (see CreateChild_Normal)
.done:
        move.w  d3, SST_sibling_ptr(a0) ; deferred head write - see CreateChild_Normal
        rts

; -----------------------------------------------
; CreateChild_Linked - spawn a chain of identical children
;
; CONSTRAINT: the parent must be CHILDLESS. This creator APPENDS, so it
; overwrites the parent's chain head with its first child; any children the
; parent already had are orphaned (they stay allocated and running, but
; DeleteChildren can no longer reach them - a dynamic-slot leak until the
; entity window despawns the parent's section). Asserted in DEBUG.
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
    ifdef __DEBUG__
        move.w  SST_sibling_ptr(a0), d4
        assert.w d4, eq, #0             ; this creator APPENDS over the chain head:
                                        ; a pre-existing chain would be orphaned
    endif
        subq.w  #1, d1                  ; adjust for dbf
        bmi.s   .done
        move.w  d0, d4                  ; d4 = code_addr, parked (d0 is the alloc's scratch)
        move.w  d1, d5                  ; d5 = dbf counter
        moveq   #0, d1                  ; d1 = previous child addr

        ; Start position = parent position
        move.l  SST_x_pos(a0), -(sp)    ; save running X on stack
        move.l  SST_y_pos(a0), -(sp)    ; save running Y on stack

.spawn_loop:
        ; No alloc save at all here: AllocDynamic's exhaustive license leaves
        ; d1-d5/a0 intact, and a1 is its OUTPUT (nothing of ours lives in it).
        bsr.w   AllocDynamic
        bne.s   .link_fail
        movea.l a1, a2                  ; a2 = child SST

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
        movea.w d1, a1                  ; RAM lives in the sign-extending
                                        ; $FFFFxxxx window, so a bare word IS
                                        ; the pointer (SST links are u16)
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
        addq.w  #8, sp                  ; clean running position
        rts

; -----------------------------------------------
; DeleteChildren - walk sibling chain from parent and delete each child
;
; In:  a0 = parent SST
; Out: parent's sibling_ptr cleared; each child's slot released whole (its
;      parent_ptr is not cleared separately - DeleteObject zeroes the SST)
; Clobbers: d0-d1, a1 (d1 comes from DeleteObject's license); a0 is
;           movem-preserved across every delete
; -----------------------------------------------
DeleteChildren:
        move.w  SST_sibling_ptr(a0), d2
        beq.s   .done                   ; no children

        clr.w   SST_sibling_ptr(a0)     ; disconnect from parent

        ; The parent is parked ONCE for the whole cascade (a0 is DeleteObject's
        ; argument register, so the walk needs it); the next link rides d2,
        ; which DeleteObject's clobbers(d0-d1) leaves alone.
        movem.l a0, -(sp)
.walk_chain:
        movea.w d2, a0                  ; a0 = current child
        move.w  SST_sibling_ptr(a0), d2 ; d2 = next child (read before the delete
                                        ; zeroes this slot)
        bsr.w   DeleteObject
        tst.w   d2                      ; more children?
        bne.s   .walk_chain
        movem.l (sp)+, a0
.done:
        rts

; -----------------------------------------------
; CreateEffect_Normal - spawn effect children from a descriptor table
; Allocates from Effect pool (not Dynamic). Children are NOT linked
; into the parent's sibling chain - effects are fire-and-forget.
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

        ; ALLOC SAVE: only the descriptor cursor. AllocEffect is
        ; `clobbers(d0) out(a1 if eq)` - an exhaustive license, so a0 is intact.
        move.l  a1, -(sp)
        bsr.w   AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST
        movea.l (sp)+, a1

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

        ; parent_ptr: NO effect code reads this today. It is not free -
        ; Draw_Sprite dereferences a non-zero parent_ptr every frame to test
        ; the parent's RF_MULTISPRITE. Removing it is an open decision
        ; (it also decides whether an effect spawned by a multisprite parent
        ; can ever be drawn); until then the write stands as the documented
        ; parent back-reference for effect code that wants it.
        move.w  a0, SST_parent_ptr(a2)

        bsr.w   PopulateSpawnedPieceCount

        bra.s   .effect_loop

.alloc_fail:
        addq.l  #4, sp                  ; drop the saved cursor (see CreateChild_Normal)
.done:
        rts

; -----------------------------------------------
; CreateEffect_Simple - spawn N copies of the same effect at parent position
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
        move.w  d0, d2                  ; d2 = code_addr, parked (d0 is the alloc's scratch)
        move.w  d1, d3                  ; d3 = dbf counter

.spawn_loop:
        ; No alloc save: AllocEffect's exhaustive license leaves d2/d3/a0
        ; intact and a1 is its output.
        bsr.w   AllocEffect
        bne.s   .alloc_fail
        movea.l a1, a2                  ; a2 = effect SST

        move.w  d2, SST_code_addr(a2)

        ; Position = parent position
        move.l  SST_x_pos(a0), SST_x_pos(a2)
        move.l  SST_y_pos(a0), SST_y_pos(a2)

        ; Inherit mappings, art_tile
        move.l  SST_mappings(a0), SST_mappings(a2)
        move.w  SST_art_tile(a0), SST_art_tile(a2)

        ; parent_ptr: see CreateEffect_Normal - no effect code reads it and
        ; Draw_Sprite pays for it every frame.
        move.w  a0, SST_parent_ptr(a2)

        bsr.w   PopulateSpawnedPieceCount

        dbf     d3, .spawn_loop
.done:
        rts

.alloc_fail:
        rts
