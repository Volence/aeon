; HScroll update — Phase 1 minimal (per-8-row mode)
; Plane A = -camera_x. Plane B = -(camera_x >> 1) half-speed parallax.
; Per-8-row: 28 entries × 4 bytes = 112 bytes.

HSCROLL_BANDS       = 28            ; 224px / 8px = 28

; -----------------------------------------------
; Hscroll_Update — recompute HScroll buffer for current camera
; In:  none (reads Camera_X)
; Out: none (updates Hscroll_Buffer, sets dirty range)
; Clobbers: d0–d2, a0
; -----------------------------------------------
Hscroll_Update:
        move.l  (Camera_X).w, d0
        swap    d0                                 ; d0.w = camera X pixels
        neg.w   d0                                 ; VDP scroll = negated camera pos

        move.w  d0, d1
        asr.w   #1, d1                             ; d1 = Plane B scroll (half speed)

        lea     (Hscroll_Buffer).w, a0
        moveq   #HSCROLL_BANDS-1, d2
.fill:
        move.w  d0, (a0)+                          ; Plane A
        move.w  d1, (a0)+                          ; Plane B
        dbf     d2, .fill

        move.b  #0, (Hscroll_Dirty_Start).w
        move.b  #HSCROLL_BANDS-1, (Hscroll_Dirty_End).w
        rts
