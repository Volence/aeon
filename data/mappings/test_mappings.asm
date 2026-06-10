; Test sprite mappings — 16x16 colored square + 8x8 particle
; VDP-order format: Y offset, size|pad, tile attrs, X offset (8 bytes per piece)
; Mapping table: word offsets from table start
;
; Frame header: dc.b x_min, x_max, y_min, y_max (signed extents), dc.w piece_count
; Extents are far edges: x_max = x_off + width_px, y_max = y_off + height_px.
; Extents are FLIP-INVARIANT (union of flipped/unflipped extents) — see convert_s2_mappings.py.
; These test frames are all symmetric so values are unchanged by symmetrization.

Map_TestObj:
        dc.w    Map_TestObj_F0 - Map_TestObj    ; frame 0
        dc.w    Map_TestObj_F1 - Map_TestObj    ; frame 1
        dc.w    Map_TestObj_F2 - Map_TestObj    ; frame 2 — 8x8 particle

Map_TestObj_F0:
        ; bbox: 1 piece at (-8,-8), 2x2 cells (16x16px) → x_min=-8, x_max=-8+16=8, y_min=-8, y_max=8
        dc.b    -8, 8, -8, 8                    ; x_min, x_max, y_min, y_max
        dc.w    1                               ; 1 piece
        dc.w    -8                              ; Y offset (centered)
        dc.b    sprSize(2,2)>>8, 0              ; 2x2 cells (16x16), link placeholder
        dc.w    0                               ; tile 0 (relative to art_tile)
        dc.w    -8                              ; X offset (centered)

Map_TestObj_F1:
        ; bbox: 1 piece at (-8,-8), 2x2 cells (16x16px) → same as F0
        dc.b    -8, 8, -8, 8                    ; x_min, x_max, y_min, y_max
        dc.w    1                               ; 1 piece
        dc.w    -8
        dc.b    sprSize(2,2)>>8, 0
        dc.w    4                               ; tile 4 (second color)
        dc.w    -8

Map_TestObj_F2:
        ; bbox: 1 piece at (-4,-4), 1x1 cell (8x8px) → x_min=-4, x_max=-4+8=4, y_min=-4, y_max=4
        dc.b    -4, 4, -4, 4                    ; x_min, x_max, y_min, y_max
        dc.w    1                               ; 1 piece
        dc.w    -4                              ; Y offset (centered 8x8)
        dc.b    sprSize(1,1)>>8, 0              ; 1x1 cell (8x8), link placeholder
        dc.w    0                               ; tile 0 (color index 1)
        dc.w    -4                              ; X offset (centered 8x8)
