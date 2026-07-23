; HBlank dispatch — RAM jmp-slot trampoline (§0.10)
;
; The IRQ4 (HBlank) vector points DIRECTLY at HBlank_Vector_Slot (a 6-byte
; executable slot in RAM). The slot holds either an idle rte ($4E73) when no
; raster handler is installed, or `jmp handler.l` ($4EF9 + 4-byte target) when
; HBlank_Install arms one. No ROM stub, no indirect call: the interrupt reaches
; the handler through one jmp, and the handler owns its save/restore + rte.

HBLANK_IE1_BIT   = $10          ; VDP reg $00 bit 4 (IE1 — H-interrupt enable)
HBLANK_SLOT_RTE  = $4E73        ; idle: bare rte
HBLANK_SLOT_JMP  = $4EF9        ; armed: jmp xxx.l (4-byte target follows)

; -----------------------------------------------
; HBlank_Install — arm the RAM slot with a raster handler and enable HInt.
;   a0 = handler (rte-terminated, interrupt-transparent)
;   d0.b = HInt line counter (VDP reg $0A)
; All register writes go through the VDP shadow so the enable survives the next
; Flush_VDP_Shadow; the slot write is a direct RAM store (instant).
; Clobbers: d1
; -----------------------------------------------
HBlank_Install:
        move.w  #HBLANK_SLOT_JMP, (HBlank_Vector_Slot).w    ; jmp.l opcode
        move.l  a0, (HBlank_Vector_Slot+2).w                ; handler target
        move.b  d0, (VDP_Shadow_Table+VDP_Shadow_vdp_hint_rate).w
        ori.l   #(1<<VDP_Shadow_vdp_hint_rate), (VDP_Dirty_Mask).w
        move.b  (VDP_Shadow_Table+VDP_Shadow_vdp_mode1).w, d1
        ori.b   #HBLANK_IE1_BIT, d1
        move.b  d1, (VDP_Shadow_Table+VDP_Shadow_vdp_mode1).w
        ori.l   #(1<<VDP_Shadow_vdp_mode1), (VDP_Dirty_Mask).w
        rts

; -----------------------------------------------
; HBlank_Uninstall — disarm the raster handler and disable HInt.
; Returns the slot to the idle rte first (instant) so a late HInt no-ops, then
; clears IE1 through the shadow.
; Clobbers: d0
; -----------------------------------------------
HBlank_Uninstall:
        move.w  #HBLANK_SLOT_RTE, (HBlank_Vector_Slot).w    ; idle rte
        move.b  (VDP_Shadow_Table+VDP_Shadow_vdp_mode1).w, d0
        andi.b  #~HBLANK_IE1_BIT, d0            ; clear IE1, keep the rest
        move.b  d0, (VDP_Shadow_Table+VDP_Shadow_vdp_mode1).w
        ori.l   #(1<<VDP_Shadow_vdp_mode1), (VDP_Dirty_Mask).w
        rts
