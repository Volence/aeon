; DEBUG boot self-test — 68000 decompressors verified against the build encoders

    ifdef __DEBUG__

; -----------------------------------------------
; CompressionSelfTest — decode golden vectors, assert checksums
;
; The build emits one fixed payload compressed three ways (S4LZ v3 plain,
; S4LZ v3 + dictionary, ZX0) plus its expected 16-bit additive word
; checksum (tools/gen_compression_vectors.py — the generator PROVES at
; build time which decoder paths each vector exercises). This routine
; decompresses each vector into Decomp_Buffer at cold boot — before the
; buffer's first real use — and asserts the checksum. Any divergence
; between a 68000 decompressor and its encoder halts on the assert screen.
;
; The buffer is poisoned between vectors: all three share one payload, so
; a no-op decode would otherwise pass on the previous vector's output.
;
; In:  none
; Out: none
; Clobbers: d0-d4, a0-a4
; -----------------------------------------------
CompressionSelfTest:
        ; --- S4LZ v3, no dictionary ---
        bsr.w   .poison
        lea     (CSelf_S4LZ_Plain).l, a0
        lea     (Decomp_Buffer).l, a1
        bsr.w   S4LZ_Decompress
        bsr.w   .checksum
        assert.w d0, eq, #CSELF_PAYLOAD_SUM

        ; --- S4LZ v3 + dictionary (window rebase path) ---
        bsr.w   .poison
        lea     (CSelf_S4LZ_Dict).l, a0
        lea     (Decomp_Buffer).l, a1
        lea     (CSelf_Dict_Blob).l, a4
        move.w  #CSELF_DICT_LEN, d4
        bsr.w   S4LZ_DecompressDict
        bsr.w   .checksum
        assert.w d0, eq, #CSELF_PAYLOAD_SUM

        ; --- ZX0 through the version-dispatch wrapper (Art_Decompress) ---
        bsr.w   .poison
        lea     (CSelf_ZX0).l, a0
        lea     (Decomp_Buffer).l, a1
        bsr.w   Art_Decompress
        bsr.w   .checksum
        assert.w d0, eq, #CSELF_PAYLOAD_SUM
        rts

.poison:
        lea     (Decomp_Buffer).l, a1
        move.w  #CSELF_PAYLOAD_SIZE/2-1, d1
        move.w  #$A5A5, d0                  ; must match generator POISON_WORD
.poison_loop:
        move.w  d0, (a1)+
        dbf     d1, .poison_loop
        rts

.checksum:
        ; Out: d0.w = additive word checksum over the payload region
        ; Clobbers: d1, a1
        lea     (Decomp_Buffer).l, a1
        move.w  #CSELF_PAYLOAD_SIZE/2-1, d1
        moveq   #0, d0
.sum_loop:
        add.w   (a1)+, d0
        dbf     d1, .sum_loop
        rts

; Generated vectors + expected constants (BINCLUDEs, DEBUG builds only)
    include "data/generated/test/vectors.asm"

    endif ; __DEBUG__
