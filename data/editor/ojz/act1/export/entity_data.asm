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
    dc.w $0200, $00B0, $0000   ; X=$0200, Y=$00B0, Solid Block:0
    dc.w -1                                 ; terminator

ojz_Sec1_Rings:
    dc.w $0100, $0040
    dc.w $0100, $0050
    dc.w $0100, $0060
    dc.w $0180, $0050
    dc.w $01C0, $0050
    dc.w $0200, $0050
    dc.w $07A9, $079E
    dc.w $07AE, $078A
    dc.w $07BC, $079C
    dc.l 0               ; terminator

ojz_Sec1_TypeTable:
    dc.b 1       ; count
    dc.b 0           ; pad
    dc.l ObjDef_Solid    ; Solid Block

ojz_Sec1_Objects:
    dc.w $0100, $00B0, $0000   ; X=$0100, Y=$00B0, Solid Block:0
    dc.w -1                                 ; terminator

ojz_Sec2_Rings:
    dc.w $003E, $07B9
    dc.w $003E, $07D1
    dc.w $0056, $07B9
    dc.w $0056, $07D1
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
    dc.w $0100, $00B0, $0000   ; X=$0100, Y=$00B0, Solid Block:0
    dc.w $0300, $0060, $0100   ; X=$0300, Y=$0060, Static:0
    dc.w -1                                 ; terminator

ojz_Sec3_Rings:
    dc.l 0               ; terminator

ojz_Sec3_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec3_Objects:
    dc.w -1                                 ; terminator

ojz_Sec4_Rings:
    dc.w $079D, $0033
    dc.w $07A8, $001A
    dc.w $07A8, $004C
    dc.w $07AE, $07BB
    dc.w $07C1, $000F
    dc.w $07C1, $0057
    dc.w $07C6, $07BB
    dc.w $07DA, $001A
    dc.w $07DA, $004C
    dc.w $07DE, $07BB
    dc.w $07E5, $0033
    dc.w $07F6, $07BB
    dc.l 0               ; terminator

ojz_Sec4_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec4_Objects:
    dc.w -1                                 ; terminator

ojz_Sec5_Rings:
    dc.w $0037, $005A
    dc.w $003E, $07B4
    dc.w $003E, $07CC
    dc.w $003E, $07E4
    dc.w $003E, $07FC
    dc.w $004F, $0042
    dc.w $004F, $005A
    dc.w $0067, $005A
    dc.l 0               ; terminator

ojz_Sec5_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec5_Objects:
    dc.w -1                                 ; terminator

ojz_Sec6_Rings:
    dc.l 0               ; terminator

ojz_Sec6_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec6_Objects:
    dc.w -1                                 ; terminator

ojz_Sec7_Rings:
    dc.w $0781, $004C
    dc.w $078C, $0033
    dc.w $078C, $0065
    dc.w $07A5, $0028
    dc.w $07A5, $0070
    dc.w $07BE, $0033
    dc.w $07BE, $0065
    dc.w $07C9, $004C
    dc.l 0               ; terminator

ojz_Sec7_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec7_Objects:
    dc.w -1                                 ; terminator

ojz_Sec8_Rings:
    dc.w $003E, $004D
    dc.w $0056, $0035
    dc.w $0056, $004D
    dc.w $006E, $004D
    dc.l 0               ; terminator

ojz_Sec8_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec8_Objects:
    dc.w -1                                 ; terminator