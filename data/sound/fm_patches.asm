; ======================================================================
; data/sound/fm_patches.asm — FM patch table (FmPatch records, 26 bytes each).
;
; The ROM-resident patch table the song format references by index (Task 6
; wires the banked-ROM access). Each record is an FmPatch (see the struct +
; operator ordering in sound_constants.asm): fp_alg_fb=$B0, fp_lr_ams_fms=$B4,
; then 6 four-byte per-op arrays for regs $30/$40/$50/$60/$70/$80, with array
; index 0..3 = PHYSICAL register offset +0/+4/+8/+C = operators S1,S3,S2,S4.
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
;
; CONTRACT: PATCH_COUNT = number of FmPatch records between FmPatchTable and
; FmPatchTable_End; the count assert ties them together (Task-3 spec form).
; ======================================================================

; --- Patch-index enum (the song format / test stream references these) ---
; (The Task-2 DEBUG test stream does `MEV_PATCH, 1` -> PATCH_LEAD: alg 7, all
; four operators are carriers, so it is loud and obvious for FM bring-up.)
PATCH_BASS = 0          ; EHZ voice (alg 5, fb 6)
PATCH_LEAD = 1          ; EHZ voice (alg 7, fb 0 — all carriers, bright)
PATCH_COUNT = 2

FmPatchTable:

; --- PATCH_BASS (index 0) — EHZ SMPS voice, algorithm 5, feedback 6 -------
        dc.b    $35                     ; fp_alg_fb     = (fb6<<3)|alg5
        dc.b    $C0                     ; fp_lr_ams_fms = L/R=11, AMS=0, FMS=0
        dc.b    $00, $01, $13, $01      ; fp_dt_mul  $30  [S1,S3,S2,S4]
        dc.b    $00, $00, $03, $1E      ; fp_tl      $40
        dc.b    $19, $1D, $18, $1F      ; fp_rs_ar   $50
        dc.b    $0D, $09, $06, $00      ; fp_am_d1r  $60
        dc.b    $03, $00, $02, $00      ; fp_d2r     $70
        dc.b    $16, $06, $15, $00      ; fp_d1l_rr  $80

; --- PATCH_LEAD (index 1) — EHZ SMPS voice, algorithm 7, feedback 0 -------
; Algorithm 7 = all four operators are carriers -> the simplest "always audible"
; voice (every op outputs directly), ideal for first-light FM verification.
        dc.b    $07                     ; fp_alg_fb     = (fb0<<3)|alg7
        dc.b    $C0                     ; fp_lr_ams_fms = L/R=11, AMS=0, FMS=0
        dc.b    $02, $00, $01, $05      ; fp_dt_mul  $30  [S1,S3,S2,S4]
        dc.b    $00, $00, $00, $00      ; fp_tl      $40
        dc.b    $1F, $1F, $1F, $1F      ; fp_rs_ar   $50
        dc.b    $0E, $0E, $0E, $0E      ; fp_am_d1r  $60
        dc.b    $02, $02, $02, $02      ; fp_d2r     $70
        dc.b    $54, $55, $55, $55      ; fp_d1l_rr  $80

FmPatchTable_End:

        if (FmPatchTable_End-FmPatchTable)/FmPatch_len <> PATCH_COUNT
          error "FM patch table count mismatch"
        endif

        if (FmPatchTable_End-FmPatchTable) <> PATCH_COUNT*FmPatch_len
          error "FM patch table size \{FmPatchTable_End-FmPatchTable} != PATCH_COUNT*FmPatch_len"
        endif

        align 2
