; Exporter output (raw dc.w — documents the wire format). Hand-authored lists should use the objentry/objend macros instead.
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
    dc.b 2       ; count
    dc.b 0           ; pad
    dc.l ObjDef_Static   ; Static
    dc.l ObjDef_Solid    ; Solid Block

ojz_Sec0_Objects:
    dc.w $0200, $00B0, (1<<OEF_TYPE_SHIFT)|0   ; X=$200, Y=$0B0, Solid Block:0
    dc.w -1                                     ; terminator

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
    dc.w $0100, $00B0, (0<<OEF_TYPE_SHIFT)|0   ; X=$100, Y=$0B0, Solid Block:0
    dc.w -1                                     ; terminator

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
    dc.l ObjDef_Static   ; Static
    dc.l ObjDef_Solid    ; Solid Block

ojz_Sec2_Objects:
    dc.w $0100, $00B0, (1<<OEF_TYPE_SHIFT)|0   ; X=$100, Y=$0B0, Solid Block:0
    dc.w $0300, $0060, (0<<OEF_TYPE_SHIFT)|0   ; X=$300, Y=$060, Static:0
    dc.w -1                                     ; terminator

ojz_Sec3_Rings:
    dc.l 0               ; terminator

ojz_Sec3_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec3_Objects:
    dc.w -1                                     ; terminator

ojz_Sec4_Rings:
    dc.l 0               ; terminator

ojz_Sec4_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec4_Objects:
    dc.w -1                                     ; terminator

ojz_Sec5_Rings:
    dc.l 0               ; terminator

ojz_Sec5_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec5_Objects:
    dc.w -1                                     ; terminator

ojz_Sec6_Rings:
    dc.l 0               ; terminator

ojz_Sec6_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec6_Objects:
    dc.w -1                                     ; terminator

ojz_Sec7_Rings:
    dc.l 0               ; terminator

ojz_Sec7_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec7_Objects:
    dc.w -1                                     ; terminator

ojz_Sec8_Rings:
    dc.l 0               ; terminator

ojz_Sec8_TypeTable:
    dc.b 0       ; count
    dc.b 0           ; pad

ojz_Sec8_Objects:
    dc.w -1                                     ; terminator
