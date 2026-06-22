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
; Template block $0A-$1F: burst-copied from ObjDef at spawn (Task 4).
; Runtime block $20+: initialized individually at spawn, mutated each frame.
; -----------------------------------------------

SST struct
code_addr       ds.w 1      ; $00 — object code offset from ObjCodeBase (0 = empty) [template word]
x_pos           ds.l 1      ; $02 — 16.16 subpixel X position [patched at spawn]
y_pos           ds.l 1      ; $06 — 16.16 subpixel Y position [patched at spawn]
; --- template block $0A-$1F: copied verbatim from ObjDef at spawn (Task 4) ---
x_vel           ds.w 1      ; $0A — horizontal velocity (8.8 fixed-point)
y_vel           ds.w 1      ; $0C — vertical velocity (8.8 fixed-point)
render_flags    ds.b 1      ; $0E — bit 0 = on-screen, 1 = x-flip, 2 = y-flip, 3 = coordinate mode,
                            ;       bit 4 = multi-sprite, bits 5-7 = priority band (was word at $16)
collision_resp  ds.b 1      ; $0F — collision type dispatch (0 = none)
mappings        ds.l 1      ; $10 — sprite mapping pointer (ROM)
art_tile        ds.w 1      ; $14 — VRAM tile index + palette + priority
width_pixels    ds.b 1      ; $16 — collision width (full, not half)
height_pixels   ds.b 1      ; $17 — collision height (full, not half)
anim            ds.b 1      ; $18 — desired animation ID
subtype         ds.b 1      ; $19 — object subtype
anim_table      ds.l 1      ; $1A — animation table pointer (ROM)
status          ds.b 1      ; $1E — player/object status bits (ST_* constants)
angle           ds.b 1      ; $1F — terrain angle (player, slope-aligned objects)
; --- end template; runtime-initialized block follows ---
prev_anim       ds.b 1      ; $20 — previous anim ID (change detection; $FF at spawn)
anim_frame      ds.b 1      ; $21 — byte offset within animation script
anim_timer      ds.b 1      ; $22 — frame duration countdown
mapping_frame   ds.b 1      ; $23 — current mapping frame index
prev_frame      ds.b 1      ; $24 — previous mapping_frame (DPLC change detection; $FF at spawn)
sprite_piece_count ds.b 1   ; $25 — current frame's piece count (overflow prediction)
parent_ptr      ds.w 1      ; $26 — parent object RAM address
sibling_ptr     ds.w 1      ; $28 — sibling link (multi-part objects)
slot_tag        ds.b 1      ; $2A — entity window quadrant entry index 0-3 ($FF = untagged)
entity_section_id ds.b 1    ; $2B — spawning section's flat id (despawn bookkeeping)
entity_list_index ds.b 1    ; $2C — index in section's ROM object list (killed bitmask)
layer           ds.b 1      ; $2D — collision layer select (0 = path A, 1 = path B)
sst_custom      ds.b 34     ; $2E-$4F — per-object custom data overlay
SST endstruct

        if SST_len <> $50
          error "SST struct is \{SST_len} bytes, expected $50"
        endif
        if SST_sst_custom <> $2E
          error "SST template/metadata block moved — sst_custom expected at $2E, got \{SST_sst_custom}"
        endif
        if SST_len-SST_sst_custom <> SST_CUSTOM_SIZE
          error "sst_custom size out of sync with SST_CUSTOM_SIZE — got \{SST_len-SST_sst_custom}"
        endif
        if SST_x_vel <> SST_TEMPLATE_START
          error "template block start moved — got \{SST_x_vel}"
        endif
        if SST_anim_timer-SST_x_vel <> SST_TEMPLATE_SIZE
          error "template copy size out of sync — got \{SST_anim_timer-SST_x_vel}"
        endif

; -----------------------------------------------
; Section Definition (§4) — 72 bytes, ROM table
; All fields: 0 = keep current / no change
; -----------------------------------------------
Sec struct
sec_block_index     ds.l 1          ; $00 — pointer to 256-entry block index table (ROM; §4.7 2D)
sec_objects         ds.l 1          ; $04 — 6-byte object entries (objentry format, dc.w -1 terminated)
sec_rings           ds.l 1          ; $08 — flat X-sorted ring entries (dc.w X, Y; dc.l 0 terminated)
sec_plc             ds.l 1          ; $0C — S4LZ art PLC list
sec_pal             ds.l 1          ; $10 — 128-byte palette (4 lines × 32 bytes)
sec_parallax_config ds.l 1          ; $14 — ROM ptr to parallax_config (0 = inherit; §4.6)
sec_raster_table    ds.l 1          ; $18 — raster command table (§7.2)
sec_bg_layout       ds.l 1          ; $1C — plane B layout pointer (NULL = use Act_act_bg_layout, T1)
sec_type_table      ds.l 1          ; $20 — type table (ROM): dc.b count,pad; dc.l ObjDef×N (§4.9)
sec_pal_cycle       ds.l 1          ; $24 — palette cycling script (Phase 4)
sec_sound_bank      ds.l 1          ; $28 — DAC sample bank pointer
sec_block_dict      ds.l 1          ; $2C — ptr to raw block dictionary (block blob + index size; LZ window pre-seed)
sec_anim_blocks     ds.l 1          ; $30 — animated tile script (Phase 4)
sec_collision_s4lz  ds.l 1          ; $34 — reserved (collision embedded in strip data; §4.7)
sec_flags           ds.w 1          ; $38 — SF_* bitmask
sec_music           ds.w 1          ; $3A — music track (0 = keep current)
sec_pcfg_pad_3C     ds.b 1          ; $3C — RESERVED (was sec_layer_mask; in parallax_config)
sec_camera_lookahead ds.b 1         ; $3D — lookahead pixels (0 = zone default)
sec_pcfg_pad_3E     ds.b 1          ; $3E — RESERVED (was sec_deform_speed)
sec_pcfg_pad_3F     ds.b 1          ; $3F — RESERVED (was sec_transition_type)
; sec_tile_art / sec_tile_art_vram removed (Act Art Streaming Phase 1):
; per-section art replaced by the act-wide paged art pool carried on the Act
; descriptor (act_art_pool_table / act_art_pool_pages).
sec_block_dict_len  ds.w 1          ; $40 — dict bytes (768×K, K≤3, word-even; 0 = no dict)
Sec endstruct

    if Sec_len <> $42
      error "Sec struct is \{Sec_len} bytes, expected $42"
    endif

; -----------------------------------------------
; Parallax band entry (§4.6) — 10 bytes per band, ROM data
; -----------------------------------------------
band_entry struct
band_top_cell        ds.b 1   ; first cell row of band (0..27)
band_factor_a_s1     ds.b 1   ; Plane A shift1 (15 = whole-factor zero "locked")
band_factor_a_s2     ds.b 1   ; Plane A shift2 (15 = single-term factor)
band_factor_a_op     ds.b 1   ; bit 0: 0=ADD second term, 1=SUB
band_factor_b_s1     ds.b 1   ; Plane B shift1
band_factor_b_s2     ds.b 1   ; Plane B shift2
band_factor_b_op     ds.b 1   ; bit 0: 0=ADD, 1=SUB
band_deform_shift_a  ds.b 1   ; Plane A deform amplitude shift (15 = no FG deform)
band_deform_shift_b  ds.b 1   ; Plane B deform amplitude shift
band_phase_offset    ds.b 1   ; 0..255, added to deform sample index for desync
band_entry endstruct

    if band_entry_len <> 10
      error "band_entry struct is \{band_entry_len} bytes, expected 10"
    endif

; -----------------------------------------------
; Parallax config (§4.6) — 22-byte header + N × band_entry, ROM data
; Pointed-to by Sec.sec_parallax_config; one config per section (or shared).
; -----------------------------------------------
parallax_config struct
pcfg_band_count        ds.b 1
pcfg_v_factor_bg       ds.b 1   ; whole-plane Plane B vshift (used when v_deform_table_bg = 0)
pcfg_v_factor_fg       ds.b 1   ; RESERVED — v1 pipeline always sets fg_vscroll = camY
pcfg_layer_mask        ds.b 1   ; bit per band; 1 = active
pcfg_v_center_y        ds.w 1   ; section's "natural" camera Y
pcfg_v_offset          ds.w 1   ; vscroll BG value at center_y
pcfg_transition        ds.b 1   ; 0 = smooth lerp (default), 1 = instant snap
pcfg_deform_speed_fg   ds.b 1   ; FG H-deform table phase increment per frame
pcfg_deform_speed_bg   ds.b 1   ; BG H-deform table phase increment per frame
pcfg_pad               ds.b 1
pcfg_deform_table_fg   ds.l 1   ; ROM ptr to 256-byte signed FG H-deform (0 = none)
pcfg_deform_table_bg   ds.l 1   ; ROM ptr to 256-byte signed BG H-deform (0 = none)
pcfg_v_deform_table_bg ds.l 1   ; ROM ptr to 256-byte signed BG V-column (0 = whole-plane)
pcfg_v_deform_speed_bg ds.b 1   ; 0 = static column shape, >0 = animated
pcfg_v_deform_shift_bg ds.b 1   ; amplitude shift on V-column samples
pcfg_pad2              ds.b 2
; pcfg_bands inline follows: band_entry × pcfg_band_count
parallax_config endstruct

    if parallax_config_len <> 28
      error "parallax_config header is \{parallax_config_len} bytes, expected 28"
    endif

; -----------------------------------------------
; Act Descriptor (§4) — 40 bytes ($28), ROM table
; Fields prefixed with Act_ to match access pattern Act_fieldname(reg).
; -----------------------------------------------
Act struct
sec_grid_ptr        ds.l 1          ; $00 — pointer to section definition array
grid_w              ds.w 1          ; $04 — sections wide
grid_h              ds.w 1          ; $06 — sections tall
start_local_x       ds.w 1          ; $08 — player start X within section (0–$7FF)
start_local_y       ds.w 1          ; $0A — player start Y within section
start_sec_x         ds.b 1          ; $0C — starting section X index
start_sec_y         ds.b 1          ; $0D — starting section Y index
cam_min_x           ds.w 1          ; $0E — camera X lower bound (pixels)
cam_max_x           ds.w 1          ; $10 — camera X upper bound (pixels)
cam_min_y           ds.w 1          ; $12 — camera Y lower bound (pixels)
cam_max_y           ds.w 1          ; $14 — camera Y upper bound (pixels)
act_bg_layout       ds.l 1          ; $16 — zone-wide Plane B layout pointer (T1 default)
act_bg_tiles        ds.l 1          ; $1A — zone-wide Plane B tile blob (raw, loaded into shared BG region)
act_parallax_config ds.l 1          ; $1E — default parallax config (fallback when section's is NULL)
act_art_pool_table  ds.l 1          ; $22 — ptr to page-address table (OJZ_Act_Pool_PageTable; Act Art Streaming Phase 1)
act_art_pool_pages  ds.w 1          ; $26 — number of pool pages (OJZ_ACT_POOL_PAGES)
Act endstruct

    if Act_len <> $28
      error "Act struct is \{Act_len} bytes, expected $28"
    endif

; -----------------------------------------------
; Per-section entity scan state (§4.9 camera-driven window)
; One per tracked window cell (camera-envelope-derived 2×2 — see EntityWindow_DeriveWindow)
; -----------------------------------------------
EntityScanState struct
ess_ring_right_idx   ds.w 1      ; $00 — next unloaded ring index (scanning right)
ess_ring_left_idx    ds.w 1      ; $02 — next unloaded ring index (scanning left)
ess_obj_right_idx    ds.w 1      ; $04 — next unloaded object index (scanning right)
ess_obj_left_idx     ds.w 1      ; $06 — next unloaded object index (scanning left)
ess_rom_ring_ptr     ds.l 1      ; $08 — pointer to section's ROM ring list
ess_rom_obj_ptr      ds.l 1      ; $0C — pointer to section's ROM object list
ess_rom_type_tbl_ptr ds.l 1      ; $10 — pointer to section's ROM type table
ess_origin_x         ds.w 1      ; $14 — section's engine-space X origin
ess_section_id       ds.b 1      ; $16 — section grid index (sec_y * grid_w + sec_x)
ess_entry_idx        ds.b 1      ; $17 — this entry's index (0-3) — loaded-mask base derives from it
ess_origin_y         ds.w 1      ; $18 — section's engine-space Y origin (§4.9 phase 2)
EntityScanState endstruct

    if EntityScanState_len <> $1A
      error "EntityScanState struct is \{EntityScanState_len} bytes, expected $1A"
    endif
