ojz_Sec0_Rings:
    dc.w $0080, $0060
    dc.w $0090, $0060
    dc.w $00A0, $0060
    dc.w $00B0, $0060
    dc.w $00C0, $0060
    dc.w $0180, $0080
    dc.w $01A0, $0080
    dc.l 0               ; terminator

ojz_Sec0_TypeTable:
    dc.b 1       ; count
    dc.b 0           ; pad
    dc.l ObjDef_Solid    ; Solid Block

ojz_Sec0_Objects:
    dc.l $2002C000   ; X=$200, Y=$0B0, Solid Block:0
    dc.l 0                                 ; terminator

ojz_Sec1_Rings:
    dc.w $0100, $0040
    dc.w $0100, $0050
    dc.w $0100, $0060
    dc.w $0180, $0050
    dc.w $01C0, $0050
    dc.w $0200, $0050
    dc.l 0               ; terminator

ojz_Sec1_TypeTable:
    dc.b 1       ; count
    dc.b 0           ; pad
    dc.l ObjDef_Solid    ; Solid Block

ojz_Sec1_Objects:
    dc.l $1002C000   ; X=$100, Y=$0B0, Solid Block:0
    dc.l 0                                 ; terminator

ojz_Sec2_Rings:
    dc.w $00C0, $0050
    dc.w $00D4, $0050
    dc.w $00E8, $0050
    dc.w $00FC, $0050
    dc.w $0200, $0070
    dc.w $0300, $0030
    dc.w $0300, $0040
    dc.w $0300, $0050
    dc.l 0               ; terminator

ojz_Sec2_TypeTable:
    dc.b 2       ; count
    dc.b 0           ; pad
    dc.l ObjDef_Solid    ; Solid Block
    dc.l ObjDef_Static    ; Static

ojz_Sec2_Objects:
    dc.l $1002C000   ; X=$100, Y=$0B0, Solid Block:0
    dc.l $30018020   ; X=$300, Y=$060, Static:0
    dc.l 0                                 ; terminator

ojz_Sec3_Rings:
    dc.l 0               ; terminator

ojz_Sec3_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec3_Objects:
    dc.l 0                                 ; terminator

ojz_Sec4_Rings:
    dc.l 0               ; terminator

ojz_Sec4_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec4_Objects:
    dc.l 0                                 ; terminator

ojz_Sec5_Rings:
    dc.l 0               ; terminator

ojz_Sec5_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec5_Objects:
    dc.l 0                                 ; terminator

ojz_Sec6_Rings:
    dc.l 0               ; terminator

ojz_Sec6_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec6_Objects:
    dc.l 0                                 ; terminator

ojz_Sec7_Rings:
    dc.l 0               ; terminator

ojz_Sec7_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec7_Objects:
    dc.l 0                                 ; terminator

ojz_Sec8_Rings:
    dc.l 0               ; terminator

ojz_Sec8_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec8_Objects:
    dc.l 0                                 ; terminator