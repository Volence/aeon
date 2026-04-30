; Sprite rendering — priority-banded display list + VDP SAT builder

; -----------------------------------------------
; Screen dimensions and sprite coordinate offsets
; -----------------------------------------------
SCREEN_HEIGHT           = 224
VDP_SPRITE_Y_OFFSET     = 128           ; VDP adds 128 to sprite Y
VDP_SPRITE_X_OFFSET     = 128           ; VDP adds 128 to sprite X
SPRITE_MARGIN_X         = 32            ; off-screen margin for partial sprites
SPRITE_MARGIN_Y         = 32
MAX_VDP_SPRITES         = 80

; Sprite X=0 masking — VDP size code for mask sprites (1×4 cells = 8×32 pixels)
SPRITE_MASK_SIZE        = %00000011     ; width=1, height=4 (32 scanlines per mask)
SPRITE_MASK_HEIGHT      = 32

; -----------------------------------------------
; InitSpriteSystem — clear priority band counts and sprite counters
; Called at frame start, before RunObjects.
; In:  none
; Out: none
; Clobbers: d0, a0
; -----------------------------------------------
InitSpriteSystem:
        ; Clear all band counts (8 bytes, padded to even = 8 bytes)
        lea     (Sprite_Band_Counts).w, a0
        moveq   #0, d0
        move.l  d0, (a0)+              ; bands 0-3
        move.l  d0, (a0)+              ; bands 4-7 + pad byte

        ; Clear scanline band sprite counters (8 bytes: 7 bands + 1 pad)
        lea     (Scanline_Band_Sprites).w, a0
        move.l  d0, (a0)+
        move.l  d0, (a0)

        ; Reset counters
        move.w  d0, (Sprites_Rendered).w
        move.w  d0, (Sprite_Link_Next).w
        rts

; -----------------------------------------------
; Draw_Sprite — add an object to its priority band's display list
; Performs on-screen check against camera viewport with margins.
; Sets/clears RF_ONSCREEN in render_flags.
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
Draw_Sprite:
        ; --- Child-skip guard for multi-sprite parents ---
        ; If our parent has RF_MULTISPRITE set, we render via the parent's
        ; sibling walk in Render_Sprites — don't register independently.
        move.w  SST_parent_ptr(a0), d0
        beq.s   .no_parent
        movea.w d0, a1
        btst    #RF_MULTISPRITE, SST_render_flags(a1)
        bne.s   .offscreen              ; parent batches — clear ONSCREEN, don't register
.no_parent:

        ; Check if object has mappings — skip if null
        tst.l   SST_mappings(a0)
        beq.s   .offscreen

        ; --- Check coordinate mode ---
        btst    #RF_COORDMODE, SST_render_flags(a0)
        bne.s   .screen_coords          ; screen-relative objects are always on-screen

        ; --- World coordinate on-screen check ---
        ; X check: object_x - camera_x must be in [-MARGIN, SCREEN_WIDTH+MARGIN)
        move.w  SST_x_pos(a0), d0      ; object X integer (high word of 16.16)
        move.w  (Camera_X).w, d1       ; camera X integer (high word of 16.16)
        sub.w   d1, d0                 ; d0 = screen-relative X
        addi.w  #SPRITE_MARGIN_X, d0   ; shift range to [0, WIDTH+2*MARGIN)
        cmpi.w  #SCREEN_WIDTH+SPRITE_MARGIN_X*2, d0
        bhs.s   .offscreen             ; unsigned compare catches negative

        ; Y check: object_y - camera_y must be in [-MARGIN, SCREEN_HEIGHT+MARGIN)
        move.w  SST_y_pos(a0), d0      ; object Y integer
        move.w  (Camera_Y).w, d1       ; camera Y integer
        sub.w   d1, d0                 ; d0 = screen-relative Y
        addi.w  #SPRITE_MARGIN_Y, d0
        cmpi.w  #SCREEN_HEIGHT+SPRITE_MARGIN_Y*2, d0
        bhs.s   .offscreen

.screen_coords:
        ; --- Object is on-screen ---
        bset    #RF_ONSCREEN, SST_render_flags(a0)

        ; Get priority band index
        move.w  SST_priority(a0), d0   ; 0-7
        andi.w  #PRIORITY_BANDS-1, d0  ; clamp to valid range

        ; Check band overflow — cascade to lower bands if full
        lea     (Sprite_Band_Counts).w, a1
        move.b  (a1,d0.w), d1
        cmpi.b  #SPRITES_PER_BAND, d1
        blo.s   .band_has_room

.cascade:
        subq.w  #1, d0
        bmi.s   .all_bands_full         ; all bands full, truly drop
        move.b  (a1,d0.w), d1
        cmpi.b  #SPRITES_PER_BAND, d1
        bhs.s   .cascade

.band_has_room:
        ; Compute slot index in Sprite_Bands:
        ; offset = band * SPRITES_PER_BAND * 2 + count * 2
        move.w  d0, d2
        lsl.w   #6, d2                 ; d2 = band * 64 (SPRITES_PER_BAND=32, *2 bytes)
        move.w  d1, d3
        add.w   d3, d3                 ; d3 = count * 2
        add.w   d3, d2                 ; d2 = byte offset into Sprite_Bands

        ; Store object address in band list
        lea     (Sprite_Bands).w, a1
        move.w  a0, (a1,d2.w)         ; store SST address (RAM = .w addressable)

        ; Increment band count
        lea     (Sprite_Band_Counts).w, a1
        addq.b  #1, (a1,d0.w)

.all_bands_full:
        rts

.offscreen:
        bclr    #RF_ONSCREEN, SST_render_flags(a0)
        rts

; -----------------------------------------------
; Render_Sprites — build VDP SAT from priority bands (7 to 0)
; Walks bands front-to-back (7=front, 0=back), reads each
; queued object's mappings, and writes VDP SAT entries into
; Sprite_Table_Buffer.
;
; VDP SAT entry format (8 bytes per hardware sprite):
;   +0 word: Y position (screen Y + 128)
;   +2 byte: size code (bits 3-2=width-1, bits 1-0=height-1)
;   +3 byte: link (next sprite index)
;   +4 word: tile attributes (priority|palette|flip|tile)
;   +6 word: X position (screen X + 128)
;
; Mapping format per piece (VDP-order, 8 bytes):
;   +0 word: Y offset (signed, relative to object center)
;   +2 byte: VDP size code
;   +3 byte: padding (overwritten with link)
;   +4 word: tile attributes (relative — added to art_tile)
;   +6 word: X offset (signed, relative to object center)
;
; Mapping table: word offsets from table base, indexed by mapping_frame.
;
; In:  none
; Out: none
; Clobbers: d0-d7, a0-a6
; -----------------------------------------------
Render_Sprites:
        addq.w  #1, (Sprite_Cycle_Counter).w

        lea     (Sprite_Table_Buffer).w, a4  ; a4 = SAT buffer write pointer
        moveq   #0, d5                      ; d5 = VDP sprite index (0-based)

        ; Use a5 as band counter (7 down to 0) to avoid d6 conflicts
        movea.w #PRIORITY_BANDS-1, a5       ; a5 = band counter (7)

.band_loop:
        move.w  a5, d6                      ; d6 = current band index
        lea     (Sprite_Band_Counts).w, a1
        moveq   #0, d7
        move.b  (a1,d6.w), d7              ; d7.w = number of objects in this band
        beq.w   .next_band                  ; skip empty bands

        ; Get base of this band's object list
        move.w  d6, d0
        lsl.w   #6, d0                     ; d0 = band * 64 (SPRITES_PER_BAND=32, *2 bytes)
        lea     (Sprite_Bands).w, a2
        adda.w  d0, a2                     ; a2 = pointer to this band's list

        subq.w  #1, d7                     ; adjust for dbf (must be .w — dbf uses full word)

        ; --- Link-order cycling: reverse intra-band order on odd frames ---
        btst    #0, (Sprite_Cycle_Counter+1).w
        bne.s   .reverse_band
        move.w  #2, -(sp)                  ; even frame: forward step
        bra.s   .object_loop
.reverse_band:
        move.w  d7, d0
        add.w   d0, d0                     ; d0 = (count-1) * 2
        adda.w  d0, a2                     ; a2 → last entry in band
        move.w  #-2, -(sp)                 ; odd frame: reverse step

.object_loop:
        ; Check VDP sprite limit
        cmpi.w  #MAX_VDP_SPRITES, d5
        bge.w   .band_limit_pop            ; pop step, then done

        ; Get object SST address (step direction from stack)
        movea.w (a2), a0
        adda.w  (sp), a2                   ; advance by +2 or -2

        ; --- Total-piece overflow pre-check (§1.2) ---
        ; Skip whole object if its cached piece count would push us past
        ; the 80-piece SAT cap. For uncached objects (sprite_piece_count=0),
        ; this is a no-op since d5 + 0 can never exceed the cap that the
        ; outer .object_loop check (above) already guarded.
        moveq   #0, d0
        move.b  SST_sprite_piece_count(a0), d0
        add.w   d5, d0
        cmpi.w  #MAX_VDP_SPRITES, d0
        bhi.w   .next_object               ; would overflow — skip whole object

        ; Guard: skip objects deleted mid-frame (slot zeroed after Draw_Sprite)
        movea.l SST_mappings(a0), a3       ; a3 = mapping table base
        move.l  a3, d0
        beq.w   .next_object

        ; Get frame offset from mapping table
        moveq   #0, d0
        move.b  SST_mapping_frame(a0), d0  ; d0 = frame index
        add.w   d0, d0                     ; d0 = frame * 2 (word offset table)
        move.w  (a3,d0.w), d0             ; d0 = word offset to frame data
        lea     (a3,d0.w), a3             ; a3 = pointer to frame data

        ; First word of frame data = piece count
        move.w  (a3)+, d4                  ; d4 = piece count
        beq.w   .next_object               ; skip if zero pieces

        ; Compute screen position from world coords
        ; Object render_flags bit 3 = coordinate mode
        btst    #RF_COORDMODE, SST_render_flags(a0)
        bne.s   .screen_pos

        ; World coords: screen_pos = object_pos - camera_pos
        move.w  SST_x_pos(a0), d2         ; object X integer
        sub.w   (Camera_X).w, d2           ; d2 = screen-relative X
        move.w  SST_y_pos(a0), d3         ; object Y integer
        sub.w   (Camera_Y).w, d3           ; d3 = screen-relative Y
        bra.s   .have_pos

.screen_pos:
        ; Screen coords: position IS the screen position
        move.w  SST_x_pos(a0), d2
        move.w  SST_y_pos(a0), d3

.have_pos:
        move.w  SST_art_tile(a0), d6

        ; --- Scanline band budget check ---
        ; Skip entirely when total pieces < limit — no band can overflow yet
        cmpi.w  #SCANLINE_SPRITE_LIMIT, d5
        blo.s   .budget_ok
        move.w  d3, d0                     ; d0 = screen-relative Y
        bmi.s   .budget_ok                 ; above screen — allow
        lsr.w   #5, d0                     ; d0 = screen_y >> 5 = band index (0-6)
        cmpi.w  #SCANLINE_BANDS, d0
        bhs.s   .budget_ok                 ; below screen — allow
        lea     (Scanline_Band_Sprites).w, a1
        move.b  (a1,d0.w), d1
        add.b   d4, d1                     ; d1 = current count + this object's pieces
        cmpi.b  #SCANLINE_SPRITE_LIMIT, d1
        bhs.w   .next_object               ; band overloaded — skip object
        move.b  d1, (a1,d0.w)             ; commit updated count
.budget_ok:

        ; Determine flip variant from render_flags bits 1-2
        move.b  SST_render_flags(a0), d0
        andi.w  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d0

        ; --- Multi-sprite branch (Approach 1 + semantic C) ---
        btst    #RF_MULTISPRITE, SST_render_flags(a0)
        bne.s   .multi_sprite

        ; Single-sprite: emit pieces and continue to next band entry
        bsr.w   Emit_ObjectPieces
        bra.w   .next_object

.multi_sprite:
        ; Save band-pointer a2; repurpose a2 = parent SST throughout sibling walk
        move.l  a2, -(sp)
        movea.l a0, a2
        bsr.w   Emit_ObjectPieces       ; emit parent's pieces

        move.w  SST_sibling_ptr(a2), d0
.sibling_loop:
        tst.w   d0
        beq.w   .multi_done

        movea.w d0, a0                  ; a0 = current child SST

        ; Read child's mappings; index using PARENT's mapping_frame (semantic C)
        move.l  SST_mappings(a0), d1
        beq.s   .sibling_advance
        movea.l d1, a3
        moveq   #0, d1
        move.b  SST_mapping_frame(a2), d1   ; PARENT's mapping_frame
        add.w   d1, d1
        move.w  (a3,d1.w), d1
        lea     (a3,d1.w), a3                ; a3 = child's frame data
        move.w  (a3)+, d4                    ; piece count for this child's frame
        beq.s   .sibling_advance

        ; Just-in-time overflow pre-check (uses live count, not cache)
        move.w  d5, d1
        add.w   d4, d1
        cmpi.w  #MAX_VDP_SPRITES, d1
        bhi.s   .sibling_advance             ; would overflow — skip just this child

        ; Compute child screen position
        btst    #RF_COORDMODE, SST_render_flags(a0)
        bne.s   .child_screen_pos
        move.w  SST_x_pos(a0), d2
        sub.w   (Camera_X).w, d2
        move.w  SST_y_pos(a0), d3
        sub.w   (Camera_Y).w, d3
        bra.s   .child_have_pos
.child_screen_pos:
        move.w  SST_x_pos(a0), d2
        move.w  SST_y_pos(a0), d3
.child_have_pos:
        move.w  SST_art_tile(a0), d6
        move.b  SST_render_flags(a0), d0
        andi.b  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d0

        ; Save child SST across Emit (a0 clobbered by subroutine)
        move.l  a0, -(sp)
        bsr.w   Emit_ObjectPieces
        movea.l (sp)+, a0

.sibling_advance:
        move.w  SST_sibling_ptr(a0), d0
        bra.s   .sibling_loop

.multi_done:
        movea.l (sp)+, a2               ; restore band-pointer

.next_object:
        dbf     d7, .object_loop
        addq.w  #2, sp                    ; pop step value after band complete

.next_band:
        ; --- Sprite X=0 mask insertion at band boundary ---
        move.w  a5, d0                    ; d0 = band we just finished (or about to start)
        cmp.b   (SpriteMask_After_Band).w, d0
        bne.s   .no_mask_insert
        tst.w   (SpriteMask_Y).w
        beq.s   .no_mask_insert
        bsr.w   InsertSpriteMasks
.no_mask_insert:

        ; Decrement band counter
        subq.w  #1, a5
        move.w  a5, d0
        bpl.w   .band_loop                ; continue while band >= 0

        bsr.w   DrawRings                 ; emit ring sprites (§4.9)

.done:
        ; Fix up last sprite's link to 0 (end of chain)
        tst.w   d5
        beq.s   .no_sprites               ; nothing rendered
        move.b  #0, -5(a4)               ; overwrite last sprite's link byte with 0

.no_sprites:
        ; Store count
        move.w  d5, (Sprites_Rendered).w

        ; If any sprites rendered, mark SAT dirty
        tst.w   d5
        beq.s   .skip_dirty
        move.b  #1, (Sprite_Table_Dirty).w
.skip_dirty:
        rts

.band_limit_pop:
        addq.w  #2, sp                    ; pop step value before done
        bra.s   .done

; -----------------------------------------------
; Flip offset lookup table (indexed by raw VDP size byte)
; VDP size byte: bits 3-2 = width-1, bits 1-0 = height-1
; -----------------------------------------------

; Width adjustment for X-flipped sprites
; Returns pixel width: (((size>>2)&3)+1)*8
CellOffsets_XFlip:
        dc.b  8,  8,  8,  8            ; width=1 (8px)
        dc.b 16, 16, 16, 16            ; width=2 (16px)
        dc.b 24, 24, 24, 24            ; width=3 (24px)
        dc.b 32, 32, 32, 32            ; width=4 (32px)
        align 2

; -----------------------------------------------
; Emit_ObjectPieces — emit one object's mapping pieces to the SAT buffer
; Reusable across single-object render path and multi-sprite sibling walk
; (Task 8). Four flip variants kept inline (zero JSR per piece).
;
; In:  a3 = pointer to first piece data (after piece-count word)
;      a4 = SAT buffer write pointer
;      d2.w = screen X (camera-adjusted)
;      d3.w = screen Y (camera-adjusted)
;      d4.w = piece count (raw, not yet dbf-adjusted)
;      d5.w = running sprite total (in/out, incremented per piece)
;      d6.w = art_tile (palette/priority/tile base)
;      d0.b = flip variant (RF_XFLIP|RF_YFLIP bits, ALREADY MASKED)
; Out: a3 advanced past consumed pieces
;      a4 advanced past emitted SAT entries
;      d5 incremented per emitted piece (capped at MAX_VDP_SPRITES)
;      d4 = -1 (consumed by dbf)
; Clobbers: d0, d1, a0 (repurposed for flip-table), a1, a6
; Preserves: d2, d3, d6, d7
; -----------------------------------------------
Emit_ObjectPieces:
        lea     CellOffsets_XFlip(pc), a0  ; a0 = flip-table base for variants
        tst.b   d0
        beq.s   .pieces_unflipped
        cmpi.b  #1<<RF_XFLIP, d0
        beq.w   .pieces_xflip
        cmpi.b  #1<<RF_YFLIP, d0
        beq.w   .pieces_yflip
        bra.w   .pieces_xyflip

        ; --- Unflipped piece loop ---
.pieces_unflipped:
        subq.w  #1, d4
.piece_loop:
        move.w  (a3)+, d0               ; Y offset (signed)
        move.b  (a3)+, d1               ; VDP size code
        addq.w  #1, a3                  ; skip padding byte
        move.w  (a3)+, a6              ; tile attrs (relative)
        move.w  (a3)+, a1              ; X offset (signed)

        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+              ; SAT +0: Y

        move.b  d1, (a4)+              ; SAT +2: size code
        addq.b  #1, d5
        move.b  d5, (a4)+              ; SAT +3: link

        move.w  a6, d0
        add.w   d6, d0
        move.w  d0, (a4)+              ; SAT +4: tile attrs

        move.w  a1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok
        moveq   #1, d0
.x_ok:
        move.w  d0, (a4)+              ; SAT +6: X

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop
        rts

        ; --- X-flipped piece loop ---
.pieces_xflip:
        subq.w  #1, d4
.piece_loop_xf:
        move.w  (a3)+, d0
        move.b  (a3)+, d1
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        move.w  a6, d0
        eori.w  #$0800, d0              ; toggle X flip bit
        add.w   d6, d0
        move.w  d0, (a4)+

        move.w  a1, d0
        neg.w   d0
        moveq   #0, d1
        move.b  -6(a3), d1              ; re-read VDP size code
        move.b  (a0,d1.w), d1           ; X-flip width from CellOffsets_XFlip
        sub.w   d1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_xf
        moveq   #1, d0
.x_ok_xf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_xf
        rts

        ; --- Y-flipped piece loop ---
.pieces_yflip:
        subq.w  #1, d4
.piece_loop_yf:
        move.w  (a3)+, d0
        move.b  (a3)+, d1
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        neg.w   d0
        andi.w  #3, d1                  ; height-1 from VDP size code low 2 bits
        addq.w  #1, d1
        lsl.w   #3, d1                  ; height in pixels
        sub.w   d1, d0
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  -6(a3), d1
        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        move.w  a6, d0
        eori.w  #$1000, d0              ; toggle Y flip bit
        add.w   d6, d0
        move.w  d0, (a4)+

        move.w  a1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_yf
        moveq   #1, d0
.x_ok_yf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_yf
        rts

        ; --- XY-flipped piece loop ---
.pieces_xyflip:
        subq.w  #1, d4
.piece_loop_xyf:
        move.w  (a3)+, d0
        move.b  (a3)+, d1
        addq.w  #1, a3
        move.w  (a3)+, a6
        move.w  (a3)+, a1

        neg.w   d0
        andi.w  #3, d1
        addq.w  #1, d1
        lsl.w   #3, d1
        sub.w   d1, d0
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+

        move.b  -6(a3), d1
        move.b  d1, (a4)+
        addq.b  #1, d5
        move.b  d5, (a4)+

        move.w  a6, d0
        eori.w  #$1800, d0              ; toggle both flip bits
        add.w   d6, d0
        move.w  d0, (a4)+

        move.w  a1, d0
        neg.w   d0
        moveq   #0, d1
        move.b  -6(a3), d1
        move.b  (a0,d1.w), d1
        sub.w   d1, d0
        add.w   d2, d0
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_xyf
        moveq   #1, d0
.x_ok_xyf:
        move.w  d0, (a4)+

        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop_xyf
        rts

; -----------------------------------------------
; InsertSpriteMasks — write X=0 mask sprites into the SAT buffer
; Inserts enough 8×32 mask sprites to cover SpriteMask_Height scanlines
; starting at SpriteMask_Y. Sprites after these in the link chain are
; hidden on the covered scanlines (VDP hardware feature).
;
; In:  a4 = SAT buffer write pointer (current position)
;      d5 = current VDP sprite index
; Out: a4 = advanced past mask entries
;      d5 = updated sprite index
; Clobbers: d0-d1
; -----------------------------------------------
InsertSpriteMasks:
        move.w  (SpriteMask_Y).w, d0       ; d0 = VDP Y start position
        move.w  (SpriteMask_Height).w, d1  ; d1 = remaining scanlines to cover
        ble.s   .masks_done

.mask_loop:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bge.s   .masks_done

        move.w  d0, (a4)+                 ; SAT +0: Y position
        move.b  #SPRITE_MASK_SIZE, (a4)+  ; SAT +2: size (1×4 = 8×32px)
        addq.b  #1, d5
        move.b  d5, (a4)+                 ; SAT +3: link to next sprite
        move.w  #0, (a4)+                 ; SAT +4: tile 0 (transparent)
        move.w  #0, (a4)+                 ; SAT +6: X = 0 (triggers masking)

        addi.w  #SPRITE_MASK_HEIGHT, d0   ; advance Y by 32 scanlines
        subi.w  #SPRITE_MASK_HEIGHT, d1   ; subtract covered height
        bgt.s   .mask_loop                ; continue if scanlines remain

.masks_done:
        rts
