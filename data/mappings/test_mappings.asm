; Test sprite mappings — 16x16 colored square
; VDP-order format: Y offset, size|pad, tile attrs, X offset (8 bytes per piece)
; Mapping table: word offsets from table start

Map_TestObj:
        dc.w    Map_TestObj_F0 - Map_TestObj    ; frame 0
        dc.w    Map_TestObj_F1 - Map_TestObj    ; frame 1

Map_TestObj_F0:
        dc.w    1                               ; 1 piece
        dc.w    -8                              ; Y offset (centered)
        dc.b    sprSize(2,2)>>8, 0              ; 2x2 cells (16x16), link placeholder
        dc.w    0                               ; tile 0 (relative to art_tile)
        dc.w    -8                              ; X offset (centered)

Map_TestObj_F1:
        dc.w    1                               ; 1 piece
        dc.w    -8
        dc.b    sprSize(2,2)>>8, 0
        dc.w    4                               ; tile 4 (second color)
        dc.w    -8
