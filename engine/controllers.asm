; Controller reading — 3-button joypad protocol

; -----------------------------------------------
; Read_Controllers — read P1 and P2 joypads (§9.4 simplified)
; Called from VBlank handler
; In:  none
; Out: Ctrl_1_Held/Press, Ctrl_2_Held/Press updated
; Clobbers: d0-d1, a0
; -----------------------------------------------
Read_Controllers:
        lea.l   (HW_PORT_1_DATA).l, a0
        bsr.s   .read_pad
        move.b  (Ctrl_1_Held).w, d1
        move.b  d0, (Ctrl_1_Held).w
        eor.b   d0, d1
        and.b   d0, d1
        move.b  d1, (Ctrl_1_Press).w

        lea.l   (HW_PORT_2_DATA).l, a0
        bsr.s   .read_pad
        move.b  (Ctrl_2_Held).w, d1
        move.b  d0, (Ctrl_2_Held).w
        eor.b   d0, d1
        and.b   d0, d1
        move.b  d1, (Ctrl_2_Press).w
        rts

; -----------------------------------------------
; .read_pad — read one 3-button pad
; In:  a0 = port data register address
; Out: d0.b = SACBRLDU (1 = pressed)
; Clobbers: d1
; -----------------------------------------------
.read_pad:
        move.b  #$40, (a0)                  ; TH = 1
        nop
        move.b  (a0), d0                    ; --CBRLDU
        move.b  #$00, (a0)                  ; TH = 0
        nop
        move.b  (a0), d1                    ; --SA00DU
        andi.b  #$3F, d0                    ; keep CBRLDU
        andi.b  #$30, d1                    ; keep SA
        lsl.b   #2, d1                      ; shift SA to bits 7-6
        or.b    d1, d0                      ; combine: SACBRLDU
        not.b   d0                          ; invert: 1 = pressed
        rts
