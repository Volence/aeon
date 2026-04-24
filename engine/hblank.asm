; HBlank dispatch — RAM-patched handler (§0.10)

; -----------------------------------------------
; HBlank_Dispatch — ROM stub, dispatches through RAM pointer
; Vectorman/Batman/Treasure pattern
; -----------------------------------------------
HBlank_Dispatch:
        movem.l d0-d1/a0, -(sp)
        movea.l (HBlank_Handler_Ptr).w, a0
        jsr     (a0)
        movem.l (sp)+, d0-d1/a0
        rte

; -----------------------------------------------
; HBlank_Null — default handler (no raster effects)
; -----------------------------------------------
HBlank_Null:
        rts
