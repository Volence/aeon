; Sonic 4 Engine — main assembly file
    cpu 68000
    padding off

; -----------------------------------------------
; Definitions (no ROM output)
; -----------------------------------------------
    include "constants.asm"
    include "structs.asm"
    include "macros.asm"
    include "ram.asm"

; -----------------------------------------------
; ROM starts here
; -----------------------------------------------
    org 0

    dc.l    SYSTEM_STACK
    dc.l    Entry
Entry:
    bra.s   Entry

    END
