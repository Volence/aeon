; Sprite rendering — priority-banded display list + VDP SAT builder

; -----------------------------------------------
; Screen dimensions and sprite coordinate offsets
; -----------------------------------------------
SCREEN_WIDTH            = 320
SCREEN_HEIGHT           = 224
VDP_SPRITE_Y_OFFSET     = 128           ; VDP adds 128 to sprite Y
VDP_SPRITE_X_OFFSET     = 128           ; VDP adds 128 to sprite X
SPRITE_MARGIN_X         = 32            ; off-screen margin for partial sprites
SPRITE_MARGIN_Y         = 32
MAX_VDP_SPRITES         = 80

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

        ; Check band overflow
        lea     (Sprite_Band_Counts).w, a1
        move.b  (a1,d0.w), d1
        cmpi.b  #SPRITES_PER_BAND, d1
        beq.s   .band_full             ; band is full, silently drop

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

.band_full:
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
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
Render_Sprites:
        lea     (Sprite_Table_Buffer).w, a4  ; a4 = SAT buffer write pointer
        moveq   #0, d5                      ; d5 = VDP sprite index (0-based)

        ; Use a5 as band counter (7 down to 0) to avoid d6 conflicts
        movea.w #PRIORITY_BANDS-1, a5       ; a5 = band counter (7)

.band_loop:
        move.w  a5, d6                      ; d6 = current band index
        lea     (Sprite_Band_Counts).w, a1
        move.b  (a1,d6.w), d7              ; d7 = number of objects in this band
        beq.w   .next_band                  ; skip empty bands

        ; Get base of this band's object list
        move.w  d6, d0
        lsl.w   #6, d0                     ; d0 = band * 64 (SPRITES_PER_BAND=32, *2 bytes)
        lea     (Sprite_Bands).w, a2
        adda.w  d0, a2                     ; a2 = pointer to this band's list

        subq.b  #1, d7                     ; adjust for dbf

.object_loop:
        ; Check VDP sprite limit
        cmpi.w  #MAX_VDP_SPRITES, d5
        bge.w   .done                      ; hard limit reached

        ; Get object SST address
        movea.w (a2)+, a0                  ; a0 = SST pointer

        ; Load mappings pointer
        movea.l SST_mappings(a0), a3       ; a3 = mapping table base

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
        ; Load object art_tile for combining with piece tile attrs
        move.w  SST_art_tile(a0), d6       ; d6 = base art_tile (reuse d6 here safely)

        ; Check object-level X-flip
        btst    #RF_XFLIP, SST_render_flags(a0)
        bne.s   .pieces_flipped

        ; --- Unflipped piece loop ---
        subq.w  #1, d4                     ; adjust for dbf
.piece_loop:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bge.w   .done

        ; Read mapping piece (8 bytes)
        move.w  (a3)+, d0                  ; Y offset (signed)
        move.b  (a3)+, d1                  ; VDP size code
        addq.l  #1, a3                     ; skip padding byte
        move.w  (a3)+, a6                  ; tile attributes (relative) — stash in a6
        move.w  (a3)+, a1                  ; X offset (signed) — stash in a1

        ; Compute VDP Y: screen_y + y_offset + 128
        add.w   d3, d0                     ; d0 = screen Y + Y offset
        addi.w  #VDP_SPRITE_Y_OFFSET, d0   ; d0 = VDP Y position
        move.w  d0, (a4)+                 ; SAT +0: Y position

        ; SAT +2: size | link
        move.b  d1, (a4)+                 ; size code
        ; Link: this sprite links to next index
        move.w  d5, d0
        addq.w  #1, d0                    ; next sprite index
        move.b  d0, (a4)+                 ; link byte

        ; SAT +4: tile attributes (base art_tile + piece relative tile)
        move.w  a6, d0                    ; retrieve piece tile attrs
        add.w   d6, d0                     ; combine with base art_tile
        move.w  d0, (a4)+                 ; tile + palette + priority + flip

        ; SAT +6: X position
        move.w  a1, d0                    ; retrieve X offset
        add.w   d2, d0                     ; screen X + X offset
        addi.w  #VDP_SPRITE_X_OFFSET, d0   ; VDP X position
        bne.s   .x_ok                      ; guard: X=0 masks lower sprites
        moveq   #1, d0
.x_ok:
        move.w  d0, (a4)+                 ; X position

        addq.w  #1, d5                     ; increment sprite index
        dbf     d4, .piece_loop

        bra.s   .next_object

        ; --- X-flipped piece loop ---
.pieces_flipped:
        subq.w  #1, d4                     ; adjust for dbf
.piece_loop_flip:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bge.w   .done

        ; Read mapping piece (8 bytes)
        move.w  (a3)+, d0                  ; Y offset (signed)
        move.b  (a3)+, d1                  ; VDP size code
        addq.l  #1, a3                     ; skip padding byte
        move.w  (a3)+, a6                  ; tile attributes (relative)
        move.w  (a3)+, a1                  ; X offset (signed)

        ; Compute VDP Y: screen_y + y_offset + 128
        add.w   d3, d0
        addi.w  #VDP_SPRITE_Y_OFFSET, d0
        move.w  d0, (a4)+                 ; SAT +0: Y position

        ; SAT +2: size | link
        move.b  d1, (a4)+                 ; size code
        move.w  d5, d0
        addq.w  #1, d0
        move.b  d0, (a4)+                 ; link byte

        ; SAT +4: tile attributes — flip X bit and combine
        move.w  a6, d0                    ; piece tile attrs
        eori.w  #$0800, d0                ; toggle horizontal flip bit (bit 11)
        add.w   d6, d0                     ; combine with base art_tile
        move.w  d0, (a4)+

        ; SAT +6: X position — negate X offset for horizontal flip
        move.w  a1, d0                    ; X offset
        neg.w   d0                         ; negate for flip
        ; Adjust for sprite width: d1 still has VDP size code from piece read
        ; Width in cells = ((size >> 2) & 3) + 1, pixel width = cells * 8
        lsr.b   #2, d1                    ; shift width bits down
        andi.w  #3, d1                    ; mask to 2 bits (width - 1)
        addq.w  #1, d1                    ; width in cells
        lsl.w   #3, d1                    ; width in pixels
        sub.w   d1, d0                     ; adjust flipped X offset
        add.w   d2, d0                     ; screen X
        addi.w  #VDP_SPRITE_X_OFFSET, d0
        bne.s   .x_ok_flip                 ; guard: X=0 masks lower sprites
        moveq   #1, d0
.x_ok_flip:
        move.w  d0, (a4)+                 ; X position

        addq.w  #1, d5
        dbf     d4, .piece_loop_flip

.next_object:
        dbf     d7, .object_loop

.next_band:
        ; Decrement band counter
        suba.w  #1, a5
        move.w  a5, d0
        bpl.w   .band_loop                ; continue while band >= 0

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
