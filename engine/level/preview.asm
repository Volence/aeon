; §4.2 Preview-zone copy routines (direct VDP write).
;
; Preview is nametable-only edge regions on plane A. Cells reference resident
; slot art; no extra VRAM is allocated.
;
; FWD preview = leading PREVIEW_COLS cols of next-section nametable strip,
;               written at plane cols 0..PREVIEW_COLS-1.
; BWD preview = trailing PREVIEW_COLS cols of previous-section nametable strip,
;               written at plane cols (64-PREVIEW_COLS)..63.
;
; Direct-VDP writes (bypass Plane_Buffer) so PREVIEW_COLS can exceed the
; plane buffer's ~14-col single-frame ceiling. Same approach as
; Section_RedrawPlanes — writes during active display, completes in <1ms,
; visually clean.
;
; Triggers (see section.asm):
;   FWD copy fires from .preload_fwd when the source section's art is queued.
;   BWD copy fires at every teleport (Section_TeleportFwd / _Bwd).

; -----------------------------------------------
; Section_CopyFwdPreview — write FWD preview region of plane A via direct VDP.
; In:  a0 = Sec ptr (the section whose leading PREVIEW_COLS we copy)
; Out: none
; Clobbers: d0–d4, a1–a2, a5–a6
; -----------------------------------------------
Section_CopyFwdPreview:
        lea     (VDP_CTRL).l, a5
        lea     (VDP_DATA).l, a6
        move.w  #$8F80, (a5)                        ; autoincrement $80 (col-major)

        movea.l Sec_sec_strips_a(a0), a1            ; a1 = strip array (col 0 base)
        moveq   #PREVIEW_COLS-1, d4                 ; outer loop: cols 0..PREVIEW_COLS-1
        moveq   #0, d3                              ; plane col counter
.loop:
        moveq   #0, d2
        move.w  d3, d2
        add.w   d2, d2                              ; d2 = plane_col * 2 (byte offset)
        addi.l  #VRAM_PLANE_A, d2                   ; d2 = full byte address
        vdpCommReg d2, VRAM, WRITE, 1               ; build VDP CTRL command
        move.l  d2, (a5)                            ; set write address
        moveq   #STRIP_TILE_HEIGHT/2-1, d2          ; 24 longwords - 1
.copy:
        move.l  (a1)+, (a6)                         ; write nametable longword
        dbf     d2, .copy
        addq.w  #1, d3
        dbf     d4, .loop

        ; Restore default autoincrement (matches VInt_DrawLevel cleanup)
        move.w  #$8F02, (a5)
        rts

; -----------------------------------------------
; Section_CopyBwdPreview — write BWD preview region of plane A via direct VDP.
; In:  a0 = Sec ptr (the section whose trailing PREVIEW_COLS we copy)
; Out: none
; Clobbers: d0–d4, a1–a2, a5–a6
;
; Source: section tile cols (SECTION_TILE_WIDTH-PREVIEW_COLS)..(SECTION_TILE_WIDTH-1)
; Dest:   plane cols (64-PREVIEW_COLS)..63
; -----------------------------------------------
Section_CopyBwdPreview:
        lea     (VDP_CTRL).l, a5
        lea     (VDP_DATA).l, a6
        move.w  #$8F80, (a5)                        ; autoincrement $80

        ; Advance strip ptr to first of trailing PREVIEW_COLS cols.
        movea.l Sec_sec_strips_a(a0), a1
        adda.l  #(SECTION_TILE_WIDTH-PREVIEW_COLS)*STRIP_BYTE_SIZE, a1

        moveq   #PREVIEW_COLS-1, d4
        move.w  #64-PREVIEW_COLS, d3                ; plane col starts at 64-PREVIEW_COLS
.loop:
        moveq   #0, d2
        move.w  d3, d2
        add.w   d2, d2
        addi.l  #VRAM_PLANE_A, d2
        vdpCommReg d2, VRAM, WRITE, 1
        move.l  d2, (a5)
        moveq   #STRIP_TILE_HEIGHT/2-1, d2
.copy:
        move.l  (a1)+, (a6)
        dbf     d2, .copy
        addq.w  #1, d3
        dbf     d4, .loop

        move.w  #$8F02, (a5)
        rts
