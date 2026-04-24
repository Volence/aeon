; Data structure definitions

; -----------------------------------------------
; VDP Shadow Table (§0.4)
; RAM mirror of VDP registers $00-$12
; Registers $13-$17 (DMA) are NOT shadowed
; -----------------------------------------------

VDP_Shadow struct
vdp_mode1               ds.b 1          ; reg $00
vdp_mode2               ds.b 1          ; reg $01
vdp_plane_a             ds.b 1          ; reg $02
vdp_window              ds.b 1          ; reg $03
vdp_plane_b             ds.b 1          ; reg $04
vdp_sprite              ds.b 1          ; reg $05
vdp_sprite_gen          ds.b 1          ; reg $06
vdp_bgcolor             ds.b 1          ; reg $07
vdp_unused08            ds.b 1          ; reg $08
vdp_unused09            ds.b 1          ; reg $09
vdp_hint_rate           ds.b 1          ; reg $0A
vdp_mode3               ds.b 1          ; reg $0B
vdp_mode4               ds.b 1          ; reg $0C
vdp_hscroll             ds.b 1          ; reg $0D
vdp_nametable_gen       ds.b 1          ; reg $0E
vdp_increment           ds.b 1          ; reg $0F
vdp_plane_size          ds.b 1          ; reg $10
vdp_window_h            ds.b 1          ; reg $11
vdp_window_v            ds.b 1          ; reg $12
VDP_Shadow endstruct

        if VDP_Shadow_len <> 19
          error "VDP_Shadow struct is \{VDP_Shadow_len} bytes, expected 19"
        endif

; -----------------------------------------------
; DMA Queue Entry (§1.2)
; VDP reg numbers at even offsets, data at odd offsets.
; movep writes interleave naturally.
; -----------------------------------------------

DMAEntry struct
Reg94           ds.b 1          ; +0  VDP reg $14 marker
SizeH           ds.b 1          ; +1  DMA length high byte
Reg93           ds.b 1          ; +2  VDP reg $13 marker
SizeL           ds.b 1          ; +3  DMA length low byte
Reg97           ds.b 1          ; +4  VDP reg $17 marker
SrcH            ds.b 1          ; +5  source address bits 22-16
Reg96           ds.b 1          ; +6  VDP reg $16 marker
SrcM            ds.b 1          ; +7  source address bits 15-8
Reg95           ds.b 1          ; +8  VDP reg $15 marker
SrcL            ds.b 1          ; +9  source address bits 7-0
Command         ds.l 1          ; +10 VDP command (destination + DMA trigger)
DMAEntry endstruct

        if DMAEntry_len <> 14
          error "DMAEntry struct is \{DMAEntry_len} bytes, expected 14"
        endif
