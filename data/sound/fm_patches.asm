; ======================================================================
; data/sound/fm_patches.asm — FM patch table (FmPatch records).
;
; TASK-1 STUB. Task 3 fills this with real FmPatch records (26 bytes each,
; per the FmPatch struct + operator ordering documented in sound_constants.asm)
; and bumps PATCH_COUNT to match. Until then the table is empty so the build is
; clean and downstream `dc.w FmPatchTable` references resolve.
;
; CONTRACT: PATCH_COUNT = number of FmPatch records between FmPatchTable and
; FmPatchTable_End; the size assert ties them together.
; ======================================================================

PATCH_COUNT = 0

FmPatchTable:
        ; (no patches yet — Task 3)
FmPatchTable_End:

        if (FmPatchTable_End-FmPatchTable) <> PATCH_COUNT*FmPatch_len
          error "FM patch table size \{FmPatchTable_End-FmPatchTable} != PATCH_COUNT*FmPatch_len"
        endif

        align 2
