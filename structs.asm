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
