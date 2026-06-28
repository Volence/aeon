; ======================================================================
; data/sound/fm_patches.asm — FM patch table (FmPatch records, 26 bytes each).
;
; The ROM-resident patch table the song format references by index (Task 6
; wires the banked-ROM access). Each record is an FmPatch (see the struct +
; operator ordering in sound_constants.asm): fp_alg_fb=$B0, fp_lr_ams_fms=$B4,
; then 6 four-byte per-op arrays for regs $30/$40/$50/$60/$70/$80, with array
; index 0..3 = PHYSICAL register offset +0/+4/+8/+C = operators S1,S3,S2,S4.
;
; --- SINGLE SOURCE OF PATCH BYTES ----------------------------------------
; The raw patch records live in data/sound/fm_patches.inc and are included by
; BOTH this file (the 68k ROM copy, for Task 6's banked loader) and the inline
; Z80-blob copy in engine/z80_sound_driver.asm (FmPatchInlineTable, read by the
; FM writer with direct Z80 addressing). Editing the bytes in ONE place updates
; both physical copies — no drift trap. The .inc emits each byte through a
; self-contained `pbyte` macro that picks `dc.b`/`db` for the current CPU.
; (See the .inc header for WHY a macro is needed + content provenance.)
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
        include "games/sonic4/data/sound/fm_patches.inc"
FmPatchTable_End:

        if (FmPatchTable_End-FmPatchTable)/FmPatch_len <> PATCH_COUNT
          error "FM patch table count mismatch"
        endif

        if (FmPatchTable_End-FmPatchTable) <> PATCH_COUNT*FmPatch_len
          error "FM patch table size \{FmPatchTable_End-FmPatchTable} != PATCH_COUNT*FmPatch_len"
        endif

        align 2
