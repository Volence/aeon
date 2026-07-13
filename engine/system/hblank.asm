; HBlank dispatch — RAM-patched handler (§0.10)

; -----------------------------------------------
; HBlank_Dispatch — ROM stub, dispatches through RAM pointer
; RAM-indirect dispatch for per-line raster effects
;
; HANDLER CONTRACT (item 8): the dispatch saves/restores ONLY d0-d1/a0 around
; the jsr, so the installed HBlank handler may clobber ONLY d0-d1/a0. Every
; other register (d2-d7/a1-a6) MUST survive — this runs mid-frame in interrupt
; context and the interrupted main-line code expects them intact.
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
