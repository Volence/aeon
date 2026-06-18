; ======================================================================
; data/sound/fm_patches.inc — RAW FmPatch byte records (SINGLE SOURCE).
;
; Just the patch data for each FmPatch (26 bytes/record), emitted through the
; self-contained `pbyte` macro below. NO labels, NO enum, NO size assert — those
; live in the includer. This file is included in TWO places so the patch bytes
; have ONE source of truth (no inline/ROM drift):
;   1. data/sound/fm_patches.asm — between FmPatchTable / FmPatchTable_End
;      (68k ROM copy, for Task 6's banked loader).
;   2. engine/z80_sound_driver.asm — between FmPatchInlineTable /
;      FmPatchInlineTable_End, INSIDE the `cpu z80 / phase 0` blob, so the FM
;      writer reads it with direct Z80 addressing.
;
; WHY THE `pbyte` MACRO: AS's byte directives are NOT CPU-agnostic — `dc.b` is
; rejected in the Z80 context and `db` is rejected in the 68k context (both:
; "unknown instruction"), AND the literal prefixes differ ($NN works in 68k but
; means the location counter in Z80; 0NNh works in Z80 but not 68k). The only
; literal that assembles identically in BOTH contexts is DECIMAL, forwarded
; through a macro that picks `db`/`dc.b` per the current CPU (MOMCPUNAME). So the
; values below are decimal with the hex in the comment. The macro is defined ONCE
; (ifndef-guarded) even though this file is included twice. Verified: both
; includers emit byte-identical data ($35,$C0,$00,$01,$13,...).
;
        ifndef pbyte_defined
pbyte_defined = 1
pbyte   macro                           ; emit data byte(s); CPU-correct directive
        if MOMCPUNAME="Z80"
        db      ALLARGS                  ; Z80 phase-0 blob context
        else
        dc.b    ALLARGS                  ; 68k ROM context
        endif
        endm
        endif
;
; Record layout (FmPatch struct; see sound_constants.asm): fp_alg_fb=$B0,
; fp_lr_ams_fms=$B4, then 6 four-byte per-op arrays for regs $30/$40/$50/$60/
; $70/$80, with array index 0..3 = PHYSICAL register offset +0/+4/+8/+C =
; operators S1,S3,S2,S4.
;
; --- CONTENT PROVENANCE (TEMP BRING-UP) ----------------------------------
; DATA-ONLY translation of two Emerald Hill Zone SMPS voices (S2; the same
; voice data shipped in sonic_hack's music blobs, here in readable form from
; the S2 disassembly). The SMPS voice fields are stored op1..op4 (operator-
; natural order); they are reordered here into our physical-register order
; [op1,op3,op2,op4] = reg offsets [+0,+4,+8,+C]. The $B4 L/R bits are forced to
; 11 (both speakers) so the channel is audible (an SMPS voice carries no L/R).
; These are CLEARLY-TEMP placeholders for FM bring-up — final instrument
; sourcing is the user's call. No SMPS code was copied; only voice byte values.
; ======================================================================

; --- PATCH_BASS (index 0) — EHZ SMPS voice, algorithm 5, feedback 6 -------
        pbyte   53                      ; fp_alg_fb     $35 = (fb6<<3)|alg5
        pbyte   192                     ; fp_lr_ams_fms $C0 = L/R=11, AMS=0, FMS=0
        pbyte   0,   1,   19,  1        ; fp_dt_mul  $30  [S1,S3,S2,S4] = $00,$01,$13,$01
        pbyte   0,   0,   3,   30       ; fp_tl      $40              = $00,$00,$03,$1E
        pbyte   25,  29,  24,  31       ; fp_rs_ar   $50              = $19,$1D,$18,$1F
        pbyte   13,  9,   6,   0        ; fp_am_d1r  $60              = $0D,$09,$06,$00
        pbyte   3,   0,   2,   0        ; fp_d2r     $70              = $03,$00,$02,$00
        pbyte   22,  6,   21,  0        ; fp_d1l_rr  $80              = $16,$06,$15,$00

; --- PATCH_LEAD (index 1) — EHZ SMPS voice, algorithm 7, feedback 0 -------
; Algorithm 7 = all four operators are carriers -> the simplest "always audible"
; voice (every op outputs directly), ideal for first-light FM verification.
        pbyte   7                       ; fp_alg_fb     $07 = (fb0<<3)|alg7
        pbyte   192                     ; fp_lr_ams_fms $C0 = L/R=11, AMS=0, FMS=0
        pbyte   2,   0,   1,   5        ; fp_dt_mul  $30  [S1,S3,S2,S4] = $02,$00,$01,$05
        pbyte   0,   0,   0,   0        ; fp_tl      $40              = $00,$00,$00,$00
        pbyte   31,  31,  31,  31       ; fp_rs_ar   $50              = $1F,$1F,$1F,$1F
        pbyte   14,  14,  14,  14       ; fp_am_d1r  $60              = $0E,$0E,$0E,$0E
        pbyte   2,   2,   2,   2        ; fp_d2r     $70              = $02,$02,$02,$02
        pbyte   84,  85,  85,  85       ; fp_d1l_rr  $80              = $54,$55,$55,$55
