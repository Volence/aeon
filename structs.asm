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

; -----------------------------------------------
; Sprite Status Table entry (§3.1)
; Object system per-slot data structure.
; Fields grouped logically; anim_cursor at $1C (even) for longword alignment.
; -----------------------------------------------

SST struct
code_addr       ds.w 1      ; $00 — object code offset from ObjCodeBase (0 = empty)
x_pos           ds.l 1      ; $02 — 16.16 subpixel X position
y_pos           ds.l 1      ; $06 — 16.16 subpixel Y position
x_vel           ds.w 1      ; $0A — horizontal velocity
y_vel           ds.w 1      ; $0C — vertical velocity
render_flags    ds.b 1      ; $0E — display flags (bit 0 = on-screen, bit 1 = x-flip, bit 2 = y-flip, bit 3 = coordinate mode)
collision_resp  ds.b 1      ; $0F — collision type dispatch (0 = none)
mappings        ds.l 1      ; $10 — sprite mapping pointer (ROM)
art_tile        ds.w 1      ; $14 — VRAM tile index + palette + priority
priority        ds.w 1      ; $16 — sprite priority band (0-7, 0 = back)
width_pixels    ds.b 1      ; $18 — collision width (full, not half)
height_pixels   ds.b 1      ; $19 — collision height (full, not half)
anim            ds.b 1      ; $1A — current animation ID
mapping_frame   ds.b 1      ; $1B — current mapping index
anim_cursor     ds.l 1      ; $1C — self-advancing animation ROM pointer
subtype         ds.b 1      ; $20 — object subtype
respawn_index   ds.b 1      ; $21 — respawn tracking
parent_ptr      ds.w 1      ; $22 — parent object RAM address
sibling_ptr     ds.w 1      ; $24 — sibling link (multi-part objects)
anim_table      ds.l 1      ; $26 — animation table pointer (ROM)
wait_timer      ds.w 1      ; $2A — Obj_Wait countdown
sst_custom      ds.b 36     ; $2C-$4F — per-object custom data overlay
SST endstruct

        if SST_len <> $50
          error "SST struct is \{SST_len} bytes, expected $50"
        endif
