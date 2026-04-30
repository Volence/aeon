; Streaming S4LZ decompressor (§4.7)
; Pause/resume at token boundaries. Each call decompresses N bytes,
; saves bookmark, returns. The blocking S4LZ_Decompress in
; s4lz_decompress.asm remains for tile art (run-to-completion loads).

; -----------------------------------------------
; S4LZ_Stream_Init — initialize a streaming decompressor slot
; In:  d0.w = slot index (0-3)
;      a0   = ROM pointer to S4LZ compressed data (at header start)
; Out: none
; Clobbers: d0-d1, a1
; -----------------------------------------------
S4LZ_Stream_Init:
        move.w  d0, d1
        lsl.w   #3, d1
        lsl.w   #2, d0
        add.w   d0, d1
        lea     (S4LZ_Stream_States).l, a1
        adda.w  d1, a1

        lea     4(a0), a0
        move.l  a0, StreamState_ss_src(a1)
        clr.l   StreamState_ss_output_pos(a1)
        clr.w   StreamState_ss_xor_prev(a1)
        clr.w   StreamState_ss_pending(a1)
        rts

; -----------------------------------------------
; S4LZ_Stream_Decompress — decompress N bytes from a stream
; In:  d0.w = slot index (0-3)
;      a2   = output destination (RAM, word-aligned)
;      d1.w = byte count to produce (must be even, > 0)
; Out: d0.b = 0 if more data available, $FF if stream ended
; Clobbers: d0-d5, a0-a4
; -----------------------------------------------
S4LZ_Stream_Decompress:
        move.w  d0, d2
        lsl.w   #3, d2
        lsl.w   #2, d0
        add.w   d0, d2
        lea     (S4LZ_Stream_States).l, a3
        adda.w  d2, a3

        movea.l StreamState_ss_src(a3), a0
        movea.l a2, a1
        adda.w  d1, a2

        move.w  StreamState_ss_pending(a3), d2
        beq.s   .sd_token
        adda.w  d2, a1
        clr.w   StreamState_ss_pending(a3)

.sd_token:
        moveq   #0, d0
        move.b  (a0)+, d0
        beq.s   .sd_stream_end
        addq.l  #1, a0

        move.w  d0, d3
        lsr.w   #4, d3
        beq.s   .sd_no_lits

        cmpi.w  #15, d3
        beq.s   .sd_lit_ext

        subq.w  #1, d3
.sd_lit_copy:
        move.w  (a0)+, (a1)+
        dbf     d3, .sd_lit_copy
        bra.s   .sd_no_lits

.sd_lit_ext:
        move.w  (a0)+, d3
        subq.w  #1, d3
.sd_lit_ext_copy:
        move.w  (a0)+, (a1)+
        dbf     d3, .sd_lit_ext_copy

.sd_no_lits:
        andi.w  #$0F, d0
        beq.s   .sd_check_target

        cmpi.w  #15, d0
        beq.s   .sd_match_ext

        move.w  (a0)+, d4
        move.l  a1, d2
        sub.w   d4, d2
        movea.l d2, a4

        subq.w  #1, d0
.sd_match_copy:
        move.w  (a4)+, (a1)+
        dbf     d0, .sd_match_copy
        bra.s   .sd_check_target

.sd_match_ext:
        move.w  (a0)+, d4
        move.l  a1, d2
        sub.w   d4, d2
        movea.l d2, a4

        move.w  (a0)+, d0
        subq.w  #1, d0
.sd_match_ext_copy:
        move.w  (a4)+, (a1)+
        dbf     d0, .sd_match_ext_copy

.sd_check_target:
        cmpa.l  a2, a1
        blt.s   .sd_token

        move.l  a0, StreamState_ss_src(a3)
        move.l  a1, d0
        sub.l   a2, d0
        move.w  d0, StreamState_ss_pending(a3)
        moveq   #0, d0
        rts

.sd_stream_end:
        move.l  a0, StreamState_ss_src(a3)
        moveq   #-1, d0
        rts
