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
; Animation block at $1A-$23 grouped for move.l init.
; -----------------------------------------------

SST struct
code_addr       ds.w 1      ; $00 — object code offset from ObjCodeBase (0 = empty)
x_pos           ds.l 1      ; $02 — 16.16 subpixel X position
y_pos           ds.l 1      ; $06 — 16.16 subpixel Y position
x_vel           ds.w 1      ; $0A — horizontal velocity (8.8 fixed-point)
y_vel           ds.w 1      ; $0C — vertical velocity (8.8 fixed-point)
render_flags    ds.b 1      ; $0E — display flags (bit 0 = on-screen, bit 1 = x-flip, bit 2 = y-flip, bit 3 = coordinate mode, bit 7 = delete)
collision_resp  ds.b 1      ; $0F — collision type dispatch (0 = none)
mappings        ds.l 1      ; $10 — sprite mapping pointer (ROM)
art_tile        ds.w 1      ; $14 — VRAM tile index + palette + priority
priority        ds.w 1      ; $16 — sprite priority band (0-7, 0 = back)
width_pixels    ds.b 1      ; $18 — collision width (full, not half)
height_pixels   ds.b 1      ; $19 — collision height (full, not half)
; --- animation block (clr.l $1A + clr.w $1E + move.l $20 inits all) ---
anim            ds.b 1      ; $1A — desired animation ID
prev_anim       ds.b 1      ; $1B — previous anim ID (change detection)
anim_frame      ds.b 1      ; $1C — byte offset within animation script
anim_timer      ds.b 1      ; $1D — frame duration countdown
mapping_frame   ds.b 1      ; $1E — current mapping frame index
prev_frame      ds.b 1      ; $1F — previous mapping_frame (DPLC change detection)
anim_table      ds.l 1      ; $20 — animation table pointer (ROM)
; --- end animation block ---
subtype         ds.b 1      ; $24 — object subtype
respawn_index   ds.b 1      ; $25 — respawn tracking
parent_ptr      ds.w 1      ; $26 — parent object RAM address
sibling_ptr     ds.w 1      ; $28 — sibling link (multi-part objects)
wait_timer      ds.w 1      ; $2A — Obj_Wait countdown
status          ds.b 1      ; $2C — player/object status bits (ST_* constants)
                ds.b 1      ; $2D — pad
anim_callback   ds.l 1      ; $2E — callback pointer for AF_CALLBACK animation event
sst_custom      ds.b 30     ; $32-$4F — per-object custom data overlay
SST endstruct

        if SST_len <> $50
          error "SST struct is \{SST_len} bytes, expected $50"
        endif

; -----------------------------------------------
; Section Definition (§4) — 64 bytes, ROM table
; All fields: 0 = keep current / no change
; -----------------------------------------------
Sec struct
sec_strips_a        ds.l 1          ; $00 — plane A nametable strip array ptr (ROM)
sec_objects         ds.l 1          ; $04 — compact 4-byte object entries
sec_rings           ds.l 1          ; $08 — pattern-encoded ring entries
sec_plc             ds.l 1          ; $0C — S4LZ art PLC list
sec_pal             ds.l 1          ; $10 — 128-byte palette (4 lines × 32 bytes)
sec_scroll          ds.l 1          ; $14 — parallax layer table (Phase 4)
sec_raster_table    ds.l 1          ; $18 — raster command table (§7.2)
sec_strips_b        ds.l 1          ; $1C — plane B nametable strip array ptr (ROM)
sec_reserved        ds.l 1          ; $20 — reserved
sec_pal_cycle       ds.l 1          ; $24 — palette cycling script (Phase 4)
sec_sound_bank      ds.l 1          ; $28 — DAC sample bank pointer
sec_deform_table    ds.l 1          ; $2C — deformation table (Phase 4)
sec_anim_blocks     ds.l 1          ; $30 — animated tile script (Phase 4)
sec_collision       ds.l 1          ; $34 — flat 128×128 collision map
sec_flags           ds.w 1          ; $38 — SF_* bitmask
sec_music           ds.w 1          ; $3A — music track (0 = keep current)
sec_layer_mask      ds.b 1          ; $3C — parallax layer enable (Phase 4)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_deform_speed    ds.b 1          ; $3E — deformation rate (Phase 4)
sec_transition_type ds.b 1          ; $3F — transition type (Phase 4)
Sec endstruct

    if Sec_len <> $40
      error "Sec struct is \{Sec_len} bytes, expected $40"
    endif
