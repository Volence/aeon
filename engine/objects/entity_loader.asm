; Entity loader — slot-tagged object despawn
; §4.9 camera-driven entity management

; -----------------------------------------------
; DespawnSlotObjects — delete all dynamic objects with matching slot tag
;
; In:  d0.b = quadrant entry index to match (0-3; see SLOT_TAG_* in constants.asm)
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
DespawnSlotObjects:
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d1

.scan_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .next_slot

        cmp.b   SST_slot_tag(a0), d0
        bne.s   .next_slot

        movem.l d0-d1/a0, -(sp)
        jsr     DeleteObject
        movem.l (sp)+, d0-d1/a0

.next_slot:
        lea     SST_len(a0), a0
        dbf     d1, .scan_loop
        rts
