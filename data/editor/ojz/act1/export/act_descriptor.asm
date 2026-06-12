ojz_act1_Descriptor:
    dc.l    ojz_act1_Sections       ; sec_grid_ptr
    dc.w    3                       ; grid_w
    dc.w    3                       ; grid_h
    dc.w    $0100                   ; start_local_x
    dc.w    $0100                   ; start_local_y
    dc.b    0                       ; start_sec_x
    dc.b    0                       ; start_sec_y
    dc.w    SLOT_ORIGIN_L           ; cam_min_x
    dc.w    SLOT_ORIGIN_L + (3 * SECTION_SIZE) - SCREEN_WIDTH ; cam_max_x
    dc.w    SLOT_ORIGIN_U           ; cam_min_y
    dc.w    SLOT_ORIGIN_U + (3 * SECTION_SIZE) - 224 ; cam_max_y
    dc.l    ojz_act1_BG_Layout      ; act_bg_layout
    dc.l    ojz_act1_BG_Tiles       ; act_bg_tiles
    dc.l    data/parallax/ojz_default.asm    ; act_parallax_config

; NOTE: non-zero sec_bg_layout entries reference editor BG-library
; binaries (data/editor/ojz_bg_{id}.bin). The build pipeline must
; BINCLUDE each referenced binary at its ojz_BG_{id} label.
ojz_act1_Sections:
; --- Section 0 (0,0) — flat_id 0 ---
ojz_Sec0:
    dc.l    ojz_Sec0_Blocks           ; sec_block_index
    dc.l    ojz_Sec0_Objects          ; sec_objects
    dc.l    ojz_Sec0_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    ojz_BG_deep_forest_v13_1781214524380  ; sec_bg_layout
    dc.l    ojz_Sec0_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec0_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC0_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 1 (1,0) — flat_id 1 ---
ojz_Sec1:
    dc.l    ojz_Sec1_Blocks           ; sec_block_index
    dc.l    ojz_Sec1_Objects          ; sec_objects
    dc.l    ojz_Sec1_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec1_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec1_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC1_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 2 (2,0) — flat_id 2 ---
ojz_Sec2:
    dc.l    ojz_Sec2_Blocks           ; sec_block_index
    dc.l    ojz_Sec2_Objects          ; sec_objects
    dc.l    ojz_Sec2_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec2_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec2_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC2_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 3 (0,1) — flat_id 3 ---
ojz_Sec3:
    dc.l    ojz_Sec3_Blocks           ; sec_block_index
    dc.l    ojz_Sec3_Objects          ; sec_objects
    dc.l    ojz_Sec3_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec3_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec3_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC3_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 4 (1,1) — flat_id 4 ---
ojz_Sec4:
    dc.l    ojz_Sec4_Blocks           ; sec_block_index
    dc.l    ojz_Sec4_Objects          ; sec_objects
    dc.l    ojz_Sec4_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec4_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec4_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC4_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 5 (2,1) — flat_id 5 ---
ojz_Sec5:
    dc.l    ojz_Sec5_Blocks           ; sec_block_index
    dc.l    ojz_Sec5_Objects          ; sec_objects
    dc.l    ojz_Sec5_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec5_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec5_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC5_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 6 (0,2) — flat_id 6 ---
ojz_Sec6:
    dc.l    ojz_Sec6_Blocks           ; sec_block_index
    dc.l    ojz_Sec6_Objects          ; sec_objects
    dc.l    ojz_Sec6_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec6_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec6_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC6_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 7 (1,2) — flat_id 7 ---
ojz_Sec7:
    dc.l    ojz_Sec7_Blocks           ; sec_block_index
    dc.l    ojz_Sec7_Objects          ; sec_objects
    dc.l    ojz_Sec7_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec7_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec7_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC7_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 8 (2,2) — flat_id 8 ---
ojz_Sec8:
    dc.l    ojz_Sec8_Blocks           ; sec_block_index
    dc.l    ojz_Sec8_Objects          ; sec_objects
    dc.l    ojz_Sec8_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    ojz_Palette  ; sec_pal
    dc.l    0  ; sec_parallax_config
    dc.l    0                         ; sec_raster_table
    dc.l    0  ; sec_bg_layout
    dc.l    ojz_Sec8_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    ojz_Sec8_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    ojz_SEC8_VRAM   ; sec_tile_art_vram
    dc.w    0                         ; pad