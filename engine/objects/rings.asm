; Ring system — expand, draw, collide
; §4.9 section-local entity management

    include "engine/objects/aabb.inc"

; -----------------------------------------------
; Ring spacing lookup table (3-bit index → pixel spacing)
; Index: 0=$10, 1=$14, 2=$18, 3=$1C, 4=$20, 5=$24, 6=$28, 7=$30
; -----------------------------------------------
RingSpacingTable:
        dc.w    $10, $14, $18, $1C, $20, $24, $28, $30

; -----------------------------------------------
; ExpandRings — expand pattern-encoded ring layout into slot buffer
;
; Reads 4-byte pattern entries from ROM, expands lines into
; individual x,y pairs, converts section-local coords to
; engine-space by adding slot origin X/Y.
;
; In:  a0 = ring layout pointer (ROM, dc.l 0 terminated)
;           NULL = no rings, returns count 0
;      a1 = ring buffer pointer (RAM, slot's Ring_Buffer_N)
;      d0.w = slot origin X (engine-space pixels)
;      d1.w = slot origin Y (engine-space pixels)
; Out: d0.b = expanded ring count
; Clobbers: d0-d6, a0-a2
; -----------------------------------------------
ExpandRings:
        move.l  a0, d2
        beq.w   .no_rings

        movea.l a1, a2                  ; a2 = write cursor
        moveq   #0, d6                  ; d6 = total ring count

.entry_loop:
        move.l  (a0)+, d2               ; read 32-bit pattern entry
        beq.w   .done                   ; dc.l 0 = terminator

        cmpi.w  #MAX_RINGS_PER_SLOT, d6
        bhs.w   .done                   ; buffer full

        ; --- Extract X: bits 29-20 ---
        move.l  d2, d3
        swap    d3                      ; d3.w = original bits 31-16
        lsr.w   #4, d3                  ; bits 29-20 → bits 9-0
        andi.w  #$3FF, d3
        add.w   d0, d3                  ; d3 = engine-space X

        ; --- Extract Y: bits 19-10 ---
        move.l  d2, d4
        lsr.l   #8, d4
        lsr.w   #2, d4                  ; total right-shift 10
        andi.w  #$3FF, d4
        add.w   d1, d4                  ; d4 = engine-space Y

        ; --- Type: bits 31-30 ---
        btst    #31, d2
        bne.s   .type_hi
        btst    #30, d2
        bne.s   .is_line                ; %01 = h-line

        ; --- Individual (%00) ---
        move.w  d3, (a2)+              ; X
        move.w  d4, (a2)+              ; Y
        addq.w  #1, d6
        bra.w   .entry_loop

.type_hi:
        btst    #30, d2
        bne.w   .entry_loop            ; %11 = reserved, skip

        ; %10 = v-line, fall through

.is_line:
        ; Count: bits 9-5 → (entry.w >> 5) & $1F, then +1
        move.w  d2, d5
        lsr.w   #5, d5
        andi.w  #$1F, d5
        addq.w  #1, d5                 ; d5 = actual count (1-32)

        ; Spacing: bits 4-2 → table lookup
        ; d2 high word preserved through word-only operations
        lsr.w   #2, d2
        andi.w  #7, d2
        add.w   d2, d2                 ; word offset
        lea     RingSpacingTable(pc), a1
        move.w  (a1, d2.w), d2         ; d2.w = spacing pixels

        ; H-line or V-line? Original bit 31 still in d2 high word
        btst    #31, d2
        bne.s   .vline_loop

        ; --- H-line loop ---
.hline_loop:
        cmpi.w  #MAX_RINGS_PER_SLOT, d6
        bhs.s   .done
        move.w  d3, (a2)+              ; X
        move.w  d4, (a2)+              ; Y
        addq.w  #1, d6
        add.w   d2, d3                 ; X += spacing
        subq.w  #1, d5
        bne.s   .hline_loop
        bra.w   .entry_loop

        ; --- V-line loop ---
.vline_loop:
        cmpi.w  #MAX_RINGS_PER_SLOT, d6
        bhs.s   .done
        move.w  d3, (a2)+              ; X
        move.w  d4, (a2)+              ; Y
        addq.w  #1, d6
        add.w   d2, d4                 ; Y += spacing
        subq.w  #1, d5
        bne.s   .vline_loop
        bra.w   .entry_loop

.done:
        move.b  d6, d0
        rts

.no_rings:
        moveq   #0, d0
        rts

; -----------------------------------------------
; DrawRings — render uncollected rings to sprite table
;
; Called from Render_Sprites after all priority bands are emitted.
; Iterates both slot ring buffers, skips collected via bitmask,
; culls off-screen, writes SAT entries directly.
;
; In:  a4 = SAT buffer write pointer (from Render_Sprites)
;      d5.w = current VDP sprite count (from Render_Sprites)
; Out: a4 advanced past emitted ring sprites
;      d5 incremented per ring sprite emitted
; Clobbers: d0-d4, d6-d7, a0-a1
; -----------------------------------------------
DrawRings:
        ; --- Animation timer ---
        move.b  (Ring_Anim_Timer).w, d0
        subq.b  #1, d0
        bpl.s   .no_anim_tick
        move.b  #RING_ANIM_SPEED-1, d0
        move.b  (Ring_Anim_Frame).w, d1
        addq.b  #1, d1
        cmpi.b  #RING_ANIM_FRAMES, d1
        blo.s   .frame_ok
        moveq   #0, d1
.frame_ok:
        move.b  d1, (Ring_Anim_Frame).w
.no_anim_tick:
        move.b  d0, (Ring_Anim_Timer).w

        ; Cache camera position
        move.w  (Camera_X).w, d6
        move.w  (Camera_Y).w, d7

        ; Slot 0
        lea     (Ring_Buffer_0).w, a0
        lea     (Ring_Bitmask_0).w, a1
        moveq   #0, d1
        move.b  (Ring_Count_0).w, d1
        bsr.s   .draw_slot

        ; Slot 1 — fall through to .draw_slot (tail call via rts)
        lea     (Ring_Buffer_1).w, a0
        lea     (Ring_Bitmask_1).w, a1
        moveq   #0, d1
        move.b  (Ring_Count_1).w, d1

.draw_slot:
        tst.w   d1
        beq.s   .slot_done
        subq.w  #1, d1                  ; dbf adjust
        moveq   #0, d4                  ; d4 = ring index (for bitmask)

.ring_loop:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bhs.s   .slot_done

        ; Bitmask check: byte = index>>3, bit = index & 7 (implicit mod 8)
        move.w  d4, d0
        lsr.w   #3, d0
        btst    d4, (a1, d0.w)
        bne.s   .skip_ring              ; collected

        ; On-screen culling — X
        move.w  (a0), d2                ; engine X
        sub.w   d6, d2                  ; screen X
        move.w  d2, d0
        addi.w  #16, d0                 ; shift for unsigned range check
        cmpi.w  #336, d0               ; 320 + 16
        bhi.s   .skip_ring

        ; On-screen culling — Y
        move.w  2(a0), d3              ; engine Y
        sub.w   d7, d3                  ; screen Y
        move.w  d3, d0
        addi.w  #16, d0
        cmpi.w  #240, d0               ; 224 + 16
        bhi.s   .skip_ring

        ; --- Write SAT entry (8 bytes) ---
        ; Center 16×16 sprite on ring position (VDP draws from top-left)
        subi.w  #8, d3
        addi.w  #VDP_SPRITE_Y_OFFSET, d3
        move.w  d3, (a4)+              ; +0: Y position
        move.b  #$05, (a4)+            ; +2: size 2×2 (16×16 px)
        addq.b  #1, d5
        move.b  d5, (a4)+              ; +3: link (next sprite index)
        move.w  #VRAM_TEST_OBJ, (a4)+  ; +4: tile attrs (placeholder art)
        subi.w  #8, d2
        addi.w  #VDP_SPRITE_X_OFFSET, d2
        bne.s   .x_ok
        moveq   #1, d2                 ; avoid X=0 (VDP sprite masking)
.x_ok:
        move.w  d2, (a4)+              ; +6: X position

.skip_ring:
        addq.w  #4, a0                 ; next ring buffer entry
        addq.w  #1, d4                 ; next ring index
        dbf     d1, .ring_loop

.slot_done:
        rts

; -----------------------------------------------
; RingCollision — test player(s) vs uncollected rings
;
; Iterates both slot ring buffers, skips collected via bitmask,
; uses aabb_axis_test macro for overlap detection.
;
; In:  none (reads Player_1/2, ring buffers, bitmasks)
; Out: none
; Clobbers: d0-d7, a0-a2
; -----------------------------------------------
RingCollision:
        lea     (Player_1).w, a2
        move.w  #NUM_PLAYERS-1, d7

.player_loop:
        tst.w   SST_code_addr(a2)
        beq.w   .next_player

        move.w  SST_x_pos(a2), d4       ; cache player X
        move.w  SST_y_pos(a2), d5       ; cache player Y

        ; Slot 0
        lea     (Ring_Buffer_0).w, a0
        lea     (Ring_Bitmask_0).w, a1
        moveq   #0, d6
        move.b  (Ring_Count_0).w, d6
        bsr.s   .check_slot

        ; Slot 1
        lea     (Ring_Buffer_1).w, a0
        lea     (Ring_Bitmask_1).w, a1
        moveq   #0, d6
        move.b  (Ring_Count_1).w, d6
        bsr.s   .check_slot

.next_player:
        lea     SST_len(a2), a2
        dbf     d7, .player_loop
        rts

.check_slot:
        tst.w   d6
        beq.s   .slot_done
        subq.w  #1, d6                  ; dbf adjust
        moveq   #0, d3                  ; d3 = ring index (for bitmask)

.ring_loop:
        ; Bitmask check: byte = index >> 3, bit = index & 7 (implicit mod 8)
        move.w  d3, d0
        lsr.w   #3, d0
        btst    d3, (a1, d0.w)
        bne.s   .skip_ring              ; collected

        ; X axis: player width vs ring 16px
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #RING_WIDTH, d1

        aabb_axis_test d4,(a0),d0,d1,d0,d1,d2,.skip_ring,rx

        ; Y axis: player height vs ring 16px
        moveq   #0, d0
        move.b  SST_height_pixels(a2), d0
        moveq   #RING_HEIGHT, d1

        aabb_axis_test d5,2(a0),d0,d1,d0,d1,d2,.skip_ring,ry

        ; Overlap confirmed
        bsr.s   CollectRing

.skip_ring:
        addq.w  #4, a0                  ; next ring buffer entry
        addq.w  #1, d3                  ; next ring index
        dbf     d6, .ring_loop

.slot_done:
        rts

; -----------------------------------------------
; CollectRing — mark ring collected, increment counter
;
; In:  a1 = bitmask pointer (slot's Ring_Bitmask_N)
;      d3.w = ring index
; Out: none
; Clobbers: d0
; -----------------------------------------------
CollectRing:
        move.w  d3, d0
        lsr.w   #3, d0
        bset    d3, (a1, d0.w)          ; set bit = collected
        addq.w  #1, (Ring_Counter).w
        rts
