; Math helpers — sine/cosine lookup, angle math
;
; Sine_Table: 320 word entries covering one full cycle (256 angles)
; plus a quarter-cycle overlap so cos(angle) = SineTable[angle + $40].
; Output amplitude is $100 (so sin(0)=0, sin(90°)=$100, sin(180°)=0,
; sin(270°)=-$100). One angle unit = 360°/256 ≈ 1.41°.
;
; Borrowed format from S.C.E. / Sonic 2 disassembly.

; -----------------------------------------------
; GetSineCosine — get sin and cos of angle d0
; In:  d0.b = angle (0-255 = 0-360°)
; Out: d0.w = sin(angle) × $100 (signed word)
;      d1.w = cos(angle) × $100 (signed word)
; Clobbers: nothing else
; -----------------------------------------------
GetSineCosine:
        andi.w  #$FF, d0
        add.w   d0, d0
        addi.w  #$40*2, d0                  ; +90° for cosine
        move.w  Sine_Table(pc,d0.w), d1     ; cos
        subi.w  #$40*2, d0
        move.w  Sine_Table(pc,d0.w), d0     ; sin
        rts

Sine_Table:
        BINCLUDE "games/sonic4/data/misc/sine.bin"
