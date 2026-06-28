; VDP shadow table management

; -----------------------------------------------
; VDP_Shadow_Init — copy boot VDP register values into shadow table
; In:  none (reads from BootData VDP register values)
; Out: none
; Clobbers: d0, a0-a1
; -----------------------------------------------
VDP_Shadow_Init:
        lea.l   BootData_VDPRegs(pc), a0
        lea.l   (VDP_Shadow_Table).w, a1
        moveq   #VDP_Shadow_len-1, d0
.copy:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy
        moveq   #0, d0
        move.l  d0, (VDP_Dirty_Mask).w
        rts

; -----------------------------------------------
; Flush_VDP_Shadow — write only dirty registers to VDP (§0.4)
; Called during VBlank
; In:  none
; Out: none
; Clobbers: d0-d3, a0-a1
; -----------------------------------------------
Flush_VDP_Shadow:
        move.l  (VDP_Dirty_Mask).w, d1
        beq.s   .done                       ; fast path: nothing dirty
        lea.l   (VDP_Shadow_Table).w, a0
        lea.l   (VDP_CTRL).l, a1
        move.w  #$8000, d0                  ; VDP command base (reg 0)
        moveq   #0, d2                      ; register index (counts up)
        moveq   #VDP_Shadow_len-1, d3       ; loop counter (counts down)
.loop:
        btst    d2, d1
        beq.s   .skip
        move.b  (a0,d2.w), d0              ; load shadow value into low byte
        move.w  d0, (a1)                    ; write $8X00+val to VDP
.skip:
        addi.w  #$0100, d0                  ; next register command
        addq.w  #1, d2                      ; next register index
        dbf     d3, .loop
        moveq   #0, d0
        move.l  d0, (VDP_Dirty_Mask).w
.done:
        rts
