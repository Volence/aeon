; ZX0 decompressor — load-time tile-art tier (modern/V2 bitstream, salvador-packed)

; -----------------------------------------------
; ZX0_Decompress — blocking ZX0 stream decompressor
;
; Decodes the modern (V2) ZX0 format as emitted by salvador's default
; mode (tools/salvador — do NOT pass -classic). Bitstream decoder:
; byte-granular output, interlaced elias-gamma lengths — Kosinski-class
; speed. Budgeted ONLY for load-time paths (section preload window,
; level init); never call this per-frame.
;
; The build wraps every compressed art blob in a 4-byte header
; [u16 BE uncompressed size][u8 flags][u8 version=2]. That wrapper is
; OURS, not ZX0's — the caller peeks size/version and passes a0 already
; advanced past it (see Art_Decompress in engine/level/load_art.asm).
;
; In:  a0 = compressed ZX0 stream (PAST the 4-byte wrapper)
;      a1 = destination buffer
; Out: a0 = past end of compressed data
;      a1 = past end of decompressed data
; Clobbers: d0-d1 (d2/a2 used but saved/restored)
;
; Adapted from unzx0_68000.S (88-byte V2 depacker) by Emmanuel Marty:
;   https://github.com/emmanuel-marty/unzx0_68000
; Changes from the original: movea.l/adda.l mnemonics for address-register
; moves, house header. Algorithm untouched.
;
; ZX0 compression (c) 2021 Einar Saukas, https://github.com/einar-saukas/ZX0
;
; Copyright (C) 2021 Emmanuel Marty
;
; This software is provided 'as-is', without any express or implied
; warranty.  In no event will the authors be held liable for any damages
; arising from the use of this software.
;
; Permission is granted to anyone to use this software for any purpose,
; including commercial applications, and to alter it and redistribute it
; freely, subject to the following restrictions:
;
; 1. The origin of this software must not be misrepresented; you must not
;    claim that you wrote the original software. If you use this software
;    in a product, an acknowledgment in the product documentation would be
;    appreciated but is not required.
; 2. Altered source versions must be plainly marked as such, and must not be
;    misrepresented as being the original software.
; 3. This notice may not be removed or altered from any source distribution.
; -----------------------------------------------
ZX0_Decompress:
        movem.l a2/d2, -(sp)            ; preserve registers
        moveq   #-128, d1               ; initialize empty bit queue
                                        ; plus bit to roll into carry
        moveq   #-1, d2                 ; initialize rep-offset to 1

.literals:
        bsr.s   .get_elias              ; read number of literals to copy
        subq.l  #1, d0                  ; dbf will loop until d0 is -1, not 0
.copy_lits:
        move.b  (a0)+, (a1)+            ; copy literal byte
        dbf     d0, .copy_lits          ; loop for all literal bytes

        add.b   d1, d1                  ; read 'match or rep-match' bit
        bcs.s   .get_offset             ; if 1: read offset, if 0: rep-match

.rep_match:
        bsr.s   .get_elias              ; read match length (starts at 1)
.do_copy:
        subq.l  #1, d0                  ; dbf will loop until d0 is -1, not 0
.do_copy_offs:
        movea.l a1, a2                  ; calculate backreference address
        adda.l  d2, a2                  ; (dest + negative match offset)
.copy_match:
        move.b  (a2)+, (a1)+            ; copy matched byte
        dbf     d0, .copy_match         ; loop for all matched bytes

        add.b   d1, d1                  ; read 'literal or match' bit
        bcc.s   .literals               ; if 0: go copy literals

.get_offset:
        moveq   #-2, d0                 ; initialize value to $fe
        bsr.s   .elias_loop             ; read high byte of match offset
        addq.b  #1, d0                  ; obtain negative offset high byte
        beq.s   .done                   ; exit if EOD marker
        move.w  d0, d2                  ; transfer negative high byte into d2
        lsl.w   #8, d2                  ; shift it to make room for low byte

        moveq   #1, d0                  ; initialize length value to 1
        move.b  (a0)+, d2               ; read low byte of offset + 1 bit of len
        asr.l   #1, d2                  ; shift len bit into carry/offset in place
        bcs.s   .do_copy_offs           ; if len bit is set, no need for more
        bsr.s   .elias_bt               ; read rest of elias-encoded match length
        bra.s   .do_copy_offs           ; go copy match

.get_elias:
        moveq   #1, d0                  ; initialize value to 1
.elias_loop:
        add.b   d1, d1                  ; shift bit queue, high bit into carry
        bne.s   .got_bit                ; queue not empty, bits remain
        move.b  (a0)+, d1               ; read 8 new bits
        addx.b  d1, d1                  ; shift bit queue, high bit into carry
                                        ; and shift 1 from carry into bit queue

.got_bit:
        bcs.s   .got_elias              ; done if control bit is 1
.elias_bt:
        add.b   d1, d1                  ; read data bit
        addx.l  d0, d0                  ; shift data bit into value in d0
        bra.s   .elias_loop             ; keep reading

.done:
        movem.l (sp)+, a2/d2            ; restore preserved registers
.got_elias:
        rts
