; OJZ Act 1 entity data — flat X-sorted ring lists + object placements + type tables
; §4.9 camera-driven entity window

; -----------------------------------------------
; Sec0 Type Table — 2 types (count prefix + longword array)
; -----------------------------------------------
OJZ_Sec0_TypeTable:
        dc.b    2, 0                    ; count, pad
        dc.l    ObjDef_Static           ; type 0 — static test object
        dc.l    ObjDef_Solid            ; type 1 — solid block

; -----------------------------------------------
; Sec0 Object Layout
;   [2-bit reserved][10-bit X][10-bit Y][5-bit type][5-bit subtype]
;   X-sorted ascending. Terminated by dc.l 0
; -----------------------------------------------
OJZ_Sec0_Objects:
        ; Solid block at section-local X=$200, Y=$0B0 (type 1, subtype 0)
        dc.l    ($200<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(1<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec0 Ring Layout — flat X-sorted (dc.w X, dc.w Y per ring)
; Expanded from: H-line 5@($080,$060) sp=$10; individual ($180,$080); ($1A0,$080)
; Terminated by dc.l 0
; -----------------------------------------------
OJZ_Sec0_Rings:
        dc.w    $080, $060
        dc.w    $090, $060
        dc.w    $0A0, $060
        dc.w    $0B0, $060
        dc.w    $0C0, $060
        dc.w    $180, $080
        dc.w    $1A0, $080
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Type Table — 1 type
; -----------------------------------------------
OJZ_Sec1_TypeTable:
        dc.b    1, 0                    ; count, pad
        dc.l    ObjDef_Solid            ; type 0 — solid block

; -----------------------------------------------
; Sec1 Object Layout
; -----------------------------------------------
OJZ_Sec1_Objects:
        ; Solid block at X=$100, Y=$0B0 (type 0, subtype 0)
        dc.l    ($100<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(0<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec1 Ring Layout — flat X-sorted
; Expanded from: V-line 3@($100,$040) sp=$10; individual ($180,$050); ($1C0,$050); ($200,$050)
; -----------------------------------------------
OJZ_Sec1_Rings:
        dc.w    $100, $040
        dc.w    $100, $050
        dc.w    $100, $060
        dc.w    $180, $050
        dc.w    $1C0, $050
        dc.w    $200, $050
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec2 Type Table — 2 types
; -----------------------------------------------
OJZ_Sec2_TypeTable:
        dc.b    2, 0                    ; count, pad
        dc.l    ObjDef_Static           ; type 0 — static display object
        dc.l    ObjDef_Solid            ; type 1 — solid block

; -----------------------------------------------
; Sec2 Object Layout
; -----------------------------------------------
OJZ_Sec2_Objects:
        ; Solid block at X=$100, Y=$0B0 (type 1)
        dc.l    ($100<<OBJ_ENTRY_X_SHIFT)|($0B0<<OBJ_ENTRY_Y_SHIFT)|(1<<OBJ_ENTRY_TYPE_SHIFT)|0
        ; Static object at X=$300, Y=$060 (type 0)
        dc.l    ($300<<OBJ_ENTRY_X_SHIFT)|($060<<OBJ_ENTRY_Y_SHIFT)|(0<<OBJ_ENTRY_TYPE_SHIFT)|0
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec2 Ring Layout — flat X-sorted
; Expanded from: H-line 4@($0C0,$050) sp=$14; individual ($200,$070); V-line 3@($300,$030) sp=$10
; -----------------------------------------------
OJZ_Sec2_Rings:
        dc.w    $0C0, $050
        dc.w    $0D4, $050
        dc.w    $0E8, $050
        dc.w    $0FC, $050
        dc.w    $200, $070
        dc.w    $300, $030
        dc.w    $300, $040
        dc.w    $300, $050
        dc.l    0                       ; terminator

; -----------------------------------------------
; Sec3–Sec8 — empty entity data (editor has no placements yet)
; -----------------------------------------------
OJZ_Sec3_TypeTable:
        dc.b    0, 0
OJZ_Sec3_Objects:
        dc.l    0
OJZ_Sec3_Rings:
        dc.l    0

OJZ_Sec4_TypeTable:
        dc.b    0, 0
OJZ_Sec4_Objects:
        dc.l    0
OJZ_Sec4_Rings:
        dc.l    0

OJZ_Sec5_TypeTable:
        dc.b    0, 0
OJZ_Sec5_Objects:
        dc.l    0
OJZ_Sec5_Rings:
        dc.l    0

OJZ_Sec6_TypeTable:
        dc.b    0, 0
OJZ_Sec6_Objects:
        dc.l    0
OJZ_Sec6_Rings:
        dc.l    0

OJZ_Sec7_TypeTable:
        dc.b    0, 0
OJZ_Sec7_Objects:
        dc.l    0
OJZ_Sec7_Rings:
        dc.l    0

OJZ_Sec8_TypeTable:
        dc.b    0, 0
OJZ_Sec8_Objects:
        dc.l    0
OJZ_Sec8_Rings:
        dc.l    0
