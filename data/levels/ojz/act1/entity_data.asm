; OJZ Act 1 entity data — flat X-sorted ring lists + object placements + type tables
; §4.9 camera-driven entity window

; -----------------------------------------------
; Sec0 Type Table — 2 types (count prefix + longword array)
; -----------------------------------------------
OJZ_Sec0_TypeTable:
        dc.b    3, 0                    ; count, pad
        dc.l    ObjDef_Static           ; type 0 — static test object
        dc.l    ObjDef_Solid            ; type 1 — solid block
        dc.l    ObjDef_Enemy            ; type 2 — patrolling enemy (±48px)

; -----------------------------------------------
; Sec0 Object Layout — v2 format via objentry (x, y, type [, sub] [, oflags])
; X-sorted ascending, build-enforced. objend emits the dc.w -1 terminator.
; -----------------------------------------------
OJZ_Sec0_Objects:
        ; Solid block at section-local X=$200, Y=$0B0 (type 1, subtype 0)
        objentry $200, $0B0, 1
        objentry $300, $090, 2          ; patrolling enemy on the ground band
        objend

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
        objentry $100, $0B0, 0
        objend

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
        objentry $100, $0B0, 1
        ; Static object at X=$300, Y=$060 (type 0)
        objentry $300, $060, 0
        ; Regression object at X=$600, Y=$0B0 — right-half address inexpressible in old 10-bit format (type 0)
        objentry $600, $0B0, 0
        objend

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
        objend
OJZ_Sec3_Rings:
        dc.l    0

OJZ_Sec4_TypeTable:
        dc.b    0, 0
OJZ_Sec4_Objects:
        objend
OJZ_Sec4_Rings:
        dc.l    0

OJZ_Sec5_TypeTable:
        dc.b    0, 0
OJZ_Sec5_Objects:
        objend
OJZ_Sec5_Rings:
        dc.l    0

OJZ_Sec6_TypeTable:
        dc.b    0, 0
OJZ_Sec6_Objects:
        objend
OJZ_Sec6_Rings:
        dc.l    0

OJZ_Sec7_TypeTable:
        dc.b    0, 0
OJZ_Sec7_Objects:
        objend
OJZ_Sec7_Rings:
        dc.l    0

OJZ_Sec8_TypeTable:
        dc.b    0, 0
OJZ_Sec8_Objects:
        objend
OJZ_Sec8_Rings:
        dc.l    0
