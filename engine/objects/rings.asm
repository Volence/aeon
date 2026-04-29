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
        beq.s   .no_rings

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
; DrawRings — render uncollected rings to sprite table (stub)
; -----------------------------------------------
DrawRings:
        rts

; -----------------------------------------------
; RingCollision — test player vs uncollected rings (stub)
; -----------------------------------------------
RingCollision:
        rts

; -----------------------------------------------
; CollectRing — mark ring collected, increment counter (stub)
; -----------------------------------------------
CollectRing:
        rts
