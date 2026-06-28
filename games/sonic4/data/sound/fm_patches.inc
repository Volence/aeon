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
; --- CONTENT PROVENANCE (TEMP BRING-UP / DEMO) ---------------------------
; Two HAND-TUNED mellow placeholder voices, both ALGORITHM 0 (operators in
; series S1->S2->S3->S4, carrier = S4 only) so each is a single soft carrier
; shaped by attenuated modulators — far gentler than the original alg-7
; (all-four-carriers) bring-up voice that sounded harsh. The earlier records
; were a data-only translation of two EHZ SMPS voices; these are tuned by ear
; for the demo tune (song_test.py). Array index 0..3 = PHYSICAL reg offset
; +0/+4/+8/+C = operators S1,S3,S2,S4; the carrier (S4) is array index 3, so
; its TL=0 (full) and Fm_SetVolume scales only it (alg-0 carrier mask = $08).
; $B4 L/R forced to 11 (both speakers). CLEARLY-TEMP — final instrument
; sourcing is the user's call. No code copied.
; ======================================================================

; --- PATCH_BASS (index 0) — round FM bass, algorithm 0, feedback 4 --------
; Single carrier (S4) with heavily-attenuated series modulators = a warm,
; rounded bass with little buzz. Slight decay, long sustain.
        pbyte   32                      ; fp_alg_fb     $20 = (fb4<<3)|alg0
        pbyte   192                     ; fp_lr_ams_fms $C0 = L/R=11, AMS=0, FMS=0
        pbyte   1,   1,   1,   1        ; fp_dt_mul  $30  [S1,S3,S2,S4] = MUL 1 (fundamental)
        pbyte   64,  48,  40,  0        ; fp_tl      $40  mods attenuated ($40/$30/$28), carrier $00
        pbyte   31,  31,  31,  31       ; fp_rs_ar   $50  fast attack (AR=$1F)
        pbyte   10,  10,  10,  10       ; fp_am_d1r  $60  gentle first decay (D1R=$0A)
        pbyte   2,   2,   2,   2        ; fp_d2r     $70  slow sustain decay (D2R=$02)
        pbyte   24,  24,  24,  24       ; fp_d1l_rr  $80  D1L=1,RR=8 ($18) clean release
        pbyte   0,   0,   0,   0        ; fp_ssg_eg  $90  SSG-EG off (all operators)
        pbyte   0,   0                  ; fp_reserved      pad to 32 bytes

; --- PATCH_LEAD (index 1) — soft FM lead, algorithm 0, feedback 2 ---------
; Single carrier (S4, MUL 2 for a touch more presence) with moderate series
; modulation = a soft, sustained lead. Low feedback keeps it clean (not buzzy).
        pbyte   16                      ; fp_alg_fb     $10 = (fb2<<3)|alg0
        pbyte   192                     ; fp_lr_ams_fms $C0 = L/R=11, AMS=0, FMS=0
        pbyte   1,   1,   1,   2        ; fp_dt_mul  $30  [S1,S3,S2,S4] = MUL 1,1,1, carrier 2
        pbyte   56,  40,  32,  0        ; fp_tl      $40  mods moderate ($38/$28/$20), carrier $00
        pbyte   31,  31,  31,  31       ; fp_rs_ar   $50  fast attack (AR=$1F)
        pbyte   8,   8,   8,   8        ; fp_am_d1r  $60  slow first decay (D1R=$08)
        pbyte   0,   0,   0,   0        ; fp_d2r     $70  no sustain decay (held tone)
        pbyte   10,  10,  10,  10       ; fp_d1l_rr  $80  D1L=0,RR=$0A clean release
        pbyte   0,   0,   0,   0        ; fp_ssg_eg  $90  SSG-EG off (all operators)
        pbyte   0,   0                  ; fp_reserved      pad to 32 bytes
