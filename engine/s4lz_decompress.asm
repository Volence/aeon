; S4LZ decompressor and tile-delta undo

; -----------------------------------------------
; S4LZ_Decompress — blocking S4LZ stream decompressor
;
; Word-aligned format — all fields are word-sized or padded.
;
; Header (4 bytes):
;   $00.w = uncompressed size (BE, bytes)
;   $02.b = flags (bit 0 = tile-delta)
;   $03.b = reserved (0)
;
; Per sequence (all word-aligned):
;   Token: byte + pad byte (2 bytes)
;     High nibble (7-4) = literal word count (0-14, 15 = read next word)
;     Low nibble  (3-0) = match word count   (0-14, 15 = read next word)
;     Token $00 = end of stream
;   If lit nibble == 15: literal count word (2 bytes)
;   Literal data: count × word
;   If match nibble > 0: match offset word (2 bytes)
;   If match nibble == 15: match count word (2 bytes)
;
; In:  a0 = source (compressed S4LZ data, word-aligned)
;      a1 = destination (word-aligned RAM buffer)
; Out: a0 = past end of compressed data
;      a1 = past end of decompressed data
; Clobbers: d0-d3, a2-a3
; -----------------------------------------------
S4LZ_Decompress:
        movea.l a1, a3                          ; a3 = dest start (for tile-delta)
        move.w  (a0)+, d3                       ; d3.w = uncompressed size
        move.b  (a0)+, d2                       ; d2.b = flags
        addq.l  #1, a0                          ; skip reserved byte

.token_loop:
        moveq   #0, d0
        move.b  (a0)+, d0                       ; read token byte
        beq.w   .stream_done                    ; token $00 = end of stream
        addq.l  #1, a0                          ; skip pad byte (word alignment)

    ; --- Extract literal count (high nibble) ---
        move.w  d0, d1
        lsr.w   #4, d1                          ; d1 = LIT_CNT (0-15)
        beq.s   .no_literals                    ; 0 literals -> skip

        cmpi.w  #15, d1
        beq.w   .lit_extended                   ; 15 = read count word

    ; --- Unrolled literal copy (1-14 words) ---
        add.w   d1, d1                          ; count * 2 bytes per move.w instruction
        neg.w   d1
        jmp     .lit_end(pc,d1.w)

        move.w  (a0)+, (a1)+                   ; entry 14
        move.w  (a0)+, (a1)+                   ; entry 13
        move.w  (a0)+, (a1)+                   ; entry 12
        move.w  (a0)+, (a1)+                   ; entry 11
        move.w  (a0)+, (a1)+                   ; entry 10
        move.w  (a0)+, (a1)+                   ; entry 9
        move.w  (a0)+, (a1)+                   ; entry 8
        move.w  (a0)+, (a1)+                   ; entry 7
        move.w  (a0)+, (a1)+                   ; entry 6
        move.w  (a0)+, (a1)+                   ; entry 5
        move.w  (a0)+, (a1)+                   ; entry 4
        move.w  (a0)+, (a1)+                   ; entry 3
        move.w  (a0)+, (a1)+                   ; entry 2
        move.w  (a0)+, (a1)+                   ; entry 1
.lit_end:

.no_literals:
    ; --- Extract match count (low nibble) ---
        andi.w  #$0F, d0                        ; d0 = MATCH_CNT (0-15)
        beq.s   .token_loop                     ; 0 matches -> next token

        cmpi.w  #15, d0
        beq.s   .match_extended                 ; 15 = read count word

    ; --- Read match offset and set source ---
        move.w  (a0)+, d1                       ; d1.w = match offset (bytes)
        movea.l a1, a2
        suba.w  d1, a2                          ; a2 = match source (dest - offset)

    ; --- Unrolled match copy (1-14 words) ---
        add.w   d0, d0
        neg.w   d0
        jmp     .match_end(pc,d0.w)

        move.w  (a2)+, (a1)+                   ; entry 14
        move.w  (a2)+, (a1)+                   ; entry 13
        move.w  (a2)+, (a1)+                   ; entry 12
        move.w  (a2)+, (a1)+                   ; entry 11
        move.w  (a2)+, (a1)+                   ; entry 10
        move.w  (a2)+, (a1)+                   ; entry 9
        move.w  (a2)+, (a1)+                   ; entry 8
        move.w  (a2)+, (a1)+                   ; entry 7
        move.w  (a2)+, (a1)+                   ; entry 6
        move.w  (a2)+, (a1)+                   ; entry 5
        move.w  (a2)+, (a1)+                   ; entry 4
        move.w  (a2)+, (a1)+                   ; entry 3
        move.w  (a2)+, (a1)+                   ; entry 2
        move.w  (a2)+, (a1)+                   ; entry 1
.match_end:
        bra.s   .token_loop

    ; --- Extended literal count ---
.lit_extended:
        move.w  (a0)+, d1                       ; literal count (word)
        subq.w  #1, d1                          ; adjust for dbf
.lit_dbf_loop:
        move.w  (a0)+, (a1)+
        dbf     d1, .lit_dbf_loop
        bra.w   .no_literals                    ; continue to match portion

    ; --- Extended match count ---
.match_extended:
        move.w  (a0)+, d1                       ; match offset (word)
        movea.l a1, a2
        suba.w  d1, a2                          ; a2 = match source

        move.w  (a0)+, d0                       ; match count (word)
        subq.w  #1, d0                          ; adjust for dbf
.match_dbf_loop:
        move.w  (a2)+, (a1)+
        dbf     d0, .match_dbf_loop
        bra.w   .token_loop

    ; --- Stream complete ---
.stream_done:
        btst    #0, d2                          ; tile-delta flag?
        beq.s   .return
        move.l  a0, -(sp)                       ; save compressed-end pointer
        movea.l a3, a0                          ; a0 = buffer start
        move.w  d3, d0                          ; d0.w = uncompressed size
        bsr.s   TileDelta_Undo
        movea.l (sp)+, a0                       ; restore compressed-end pointer

.return:
        rts

; -----------------------------------------------
; TileDelta_Undo — reverse tile-delta encoding in-place
; Each 32-byte tile is XOR'd against the previous tile.
; First tile (32 bytes) is unchanged.
; In:  a0 = buffer start (decompressed tile data)
;      d0.w = total size in bytes (must be multiple of 32)
; Out: none (buffer modified in-place)
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
TileDelta_Undo:
        lsr.w   #5, d0                          ; d0 = tile count
        subq.w  #1, d0                          ; subtract 1 for first tile (unchanged)
        ble.s   .done                           ; 0 or 1 tiles -> nothing to do
        subq.w  #1, d0                          ; adjust for dbf

        movea.l a0, a1
        adda.w  #TILE_SIZE, a1                  ; a1 = second tile

.tile_loop:
    ; XOR 8 longwords (32 bytes) from previous tile into current
    rept 8
        move.l  (a0)+, d1
        eor.l   d1, (a1)+
    endr
        dbf     d0, .tile_loop

.done:
        rts
