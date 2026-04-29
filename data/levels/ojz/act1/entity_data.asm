; OJZ Act 1 entity data — ring patterns + object placements + type tables
; §4.9 test fixtures

; -----------------------------------------------
; Sec0 Type Table — 2 types
; -----------------------------------------------
OJZ_Sec0_TypeCount = 2
OJZ_Sec0_Types:
        dc.l    ObjDef_Static           ; type 0 — static test object
        dc.l    ObjDef_Solid            ; type 1 — solid block

; -----------------------------------------------
; Sec0 Object Layout
;   [2-bit reserved][10-bit X][10-bit Y][5-bit type][5-bit subtype]
;   Terminated by dc.l 0
; -----------------------------------------------
OJZ_Sec0_Objects:
        ; Solid block at section-local X=$200, Y=$0B0 (type 1, subtype 0)
        dc.l    ($200<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(1<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec0 Ring Layout
;   [2-bit type][10-bit X][10-bit Y][5-bit count-1][3-bit spacing][2-bit reserved]
;   Terminated by dc.l 0
; -----------------------------------------------
OJZ_Sec0_Rings:
        ; H-line: X=$080, Y=$060, 5 rings (count field=4), spacing 0 ($10 px)
        dc.l    RING_TYPE_HLINE|($080<<RING_X_SHIFT)|($060<<RING_Y_SHIFT)|(4<<RING_COUNT_SHIFT)|(0<<RING_SPACING_SHIFT)
        ; Individual at X=$180, Y=$080
        dc.l    RING_TYPE_INDIVIDUAL|($180<<RING_X_SHIFT)|($080<<RING_Y_SHIFT)
        ; Individual at X=$1A0, Y=$080
        dc.l    RING_TYPE_INDIVIDUAL|($1A0<<RING_X_SHIFT)|($080<<RING_Y_SHIFT)
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Type Table — 1 type
; -----------------------------------------------
OJZ_Sec1_TypeCount = 1
OJZ_Sec1_Types:
        dc.l    ObjDef_Solid            ; type 0 — solid block

; -----------------------------------------------
; Sec1 Object Layout
; -----------------------------------------------
OJZ_Sec1_Objects:
        ; Solid block at X=$100, Y=$0B0 (type 0, subtype 0)
        dc.l    ($100<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(0<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Ring Layout
; -----------------------------------------------
OJZ_Sec1_Rings:
        ; V-line: X=$100, Y=$040, 3 rings (count field=2), spacing 0 ($10 px)
        dc.l    RING_TYPE_VLINE|($100<<RING_X_SHIFT)|($040<<RING_Y_SHIFT)|(2<<RING_COUNT_SHIFT)|(0<<RING_SPACING_SHIFT)
        ; Individual at X=$180, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($180<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        ; Individual at X=$1C0, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($1C0<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        ; Individual at X=$200, Y=$050
        dc.l    RING_TYPE_INDIVIDUAL|($200<<RING_X_SHIFT)|($050<<RING_Y_SHIFT)
        dc.l    0                       ; terminator
