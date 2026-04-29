; §4.2 Preview-zone copy routines.
;
; Preview is nametable-only edge regions on plane A and plane B (PREVIEW_COLS
; cols on left + right; PREVIEW_ROWS rows on top + bottom — vertical is stubbed).
; Cells reference resident slot art; no extra VRAM is allocated.
;
; FWD preview = leading PREVIEW_COLS cols of next-section nametable strip,
;               written at plane cols 0..PREVIEW_COLS-1 (= world cols 576-579 mod 64).
; BWD preview = trailing PREVIEW_COLS cols of previous-section nametable strip,
;               written at plane cols 60..63 (= world cols 60-63 mod 64).
;
; Triggers (see section.asm):
;   FWD copy fires when source section's art preload completes (Section_LoadArt).
;   BWD copy fires at every teleport (Section_TeleportFwd / _Bwd).

; -----------------------------------------------
; Section_CopyFwdPreview — write FWD preview region of plane A.
; In:  a0 = Sec ptr (the section whose leading PREVIEW_COLS we copy)
; Out: none
; Clobbers: d0–d3, a1–a2
; -----------------------------------------------
Section_CopyFwdPreview:
        movem.l d4-d5, -(sp)
        moveq   #PREVIEW_COLS-1, d4         ; loop 4 times (d4 = 3..0)
        moveq   #0, d5                      ; d5 = src section tile col (starts at 0)
.loop:
        move.w  d5, d0                      ; dest plane col = 0..PREVIEW_COLS-1
        move.w  d5, d1                      ; src section tile col = 0..PREVIEW_COLS-1
        movem.l d4-d5/a0, -(sp)
        bsr.w   Draw_TileColumn             ; clobbers d0–d3, a1–a2
        movem.l (sp)+, d4-d5/a0
        addq.w  #1, d5
        dbf     d4, .loop
        movem.l (sp)+, d4-d5
        rts
