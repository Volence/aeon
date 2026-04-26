; OJZ Act 1 level descriptor and section tables (§4 Phase 1)
; Act struct defined in structs.asm. Strip data in data/generated/ojz/act1/ (gitignored).

; -----------------------------------------------
; OJZ Act 1 — descriptor and section table
; 9 sections (sec0–sec8) in a single horizontal row
; -----------------------------------------------
OJZ_Act1_Descriptor:
    dc.l    OJZ_Act1_Sections       ; sec_grid_ptr
    dc.w    9                       ; grid_w (9 sections wide)
    dc.w    1                       ; grid_h (1 section tall)
    dc.w    $0100                   ; start_local_x: 256px into section 0
    dc.w    $0060                   ; start_local_y: 96px down from top
    dc.b    0                       ; start_sec_x = 0
    dc.b    0                       ; start_sec_y = 0
    dc.w    SLOT_ORIGIN_L           ; cam_min_x ($200)
    dc.w    SLOT_ORIGIN_L + $4680   ; cam_max_x (approximate for 9 sections)
    dc.w    0                       ; cam_min_y
    dc.w    128                     ; cam_max_y
    align 2

; -----------------------------------------------
; Section definition table — 9 entries × $40 bytes (Sec_len)
; -----------------------------------------------
OJZ_Act1_Sections:

OJZ_Sec0:
    dc.l    OJZ_Sec0_Strips_A       ; sec_strips_a
    dc.l    0, 0, 0                 ; sec_objects, sec_rings, sec_plc
    dc.l    OJZ_Palette             ; sec_pal
    dc.l    0, 0                    ; sec_scroll, sec_raster_table
    dc.l    OJZ_Sec0_Strips_B       ; sec_strips_b
    dc.l    0, 0, 0, 0, 0, 0        ; sec_reserved, sec_pal_cycle, sec_sound_bank, sec_deform_table, sec_anim_blocks, sec_collision
    dc.w    0                       ; sec_flags
    dc.w    0                       ; sec_music
    dc.b    0, 0, 0, 0              ; sec_layer_mask, sec_camera_lookahead, sec_deform_speed, sec_transition_type
    align 2

OJZ_Sec1:
    dc.l    OJZ_Sec1_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec1_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec2:
    dc.l    OJZ_Sec2_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec2_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec3:
    dc.l    OJZ_Sec3_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec3_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec4:
    dc.l    OJZ_Sec4_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec4_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec5:
    dc.l    OJZ_Sec5_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec5_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec6:
    dc.l    OJZ_Sec6_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec6_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec7:
    dc.l    OJZ_Sec7_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec7_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

OJZ_Sec8:
    dc.l    OJZ_Sec8_Strips_A
    dc.l    0, 0, 0
    dc.l    OJZ_Palette
    dc.l    0, 0
    dc.l    OJZ_Sec8_Strips_B
    dc.l    0, 0, 0, 0, 0, 0
    dc.w    0, 0
    dc.b    0, 0, 0, 0
    align 2

; -----------------------------------------------
; Generated strip data (binary includes from build tool)
; -----------------------------------------------
OJZ_Sec0_Strips_A: BINCLUDE "data/generated/ojz/act1/sec0_strips_a.bin"
    align 2
OJZ_Sec0_Strips_B: BINCLUDE "data/generated/ojz/act1/sec0_strips_b.bin"
    align 2

OJZ_Sec1_Strips_A: BINCLUDE "data/generated/ojz/act1/sec1_strips_a.bin"
    align 2
OJZ_Sec1_Strips_B: BINCLUDE "data/generated/ojz/act1/sec1_strips_b.bin"
    align 2

OJZ_Sec2_Strips_A: BINCLUDE "data/generated/ojz/act1/sec2_strips_a.bin"
    align 2
OJZ_Sec2_Strips_B: BINCLUDE "data/generated/ojz/act1/sec2_strips_b.bin"
    align 2

OJZ_Sec3_Strips_A: BINCLUDE "data/generated/ojz/act1/sec3_strips_a.bin"
    align 2
OJZ_Sec3_Strips_B: BINCLUDE "data/generated/ojz/act1/sec3_strips_b.bin"
    align 2

OJZ_Sec4_Strips_A: BINCLUDE "data/generated/ojz/act1/sec4_strips_a.bin"
    align 2
OJZ_Sec4_Strips_B: BINCLUDE "data/generated/ojz/act1/sec4_strips_b.bin"
    align 2

OJZ_Sec5_Strips_A: BINCLUDE "data/generated/ojz/act1/sec5_strips_a.bin"
    align 2
OJZ_Sec5_Strips_B: BINCLUDE "data/generated/ojz/act1/sec5_strips_b.bin"
    align 2

OJZ_Sec6_Strips_A: BINCLUDE "data/generated/ojz/act1/sec6_strips_a.bin"
    align 2
OJZ_Sec6_Strips_B: BINCLUDE "data/generated/ojz/act1/sec6_strips_b.bin"
    align 2

OJZ_Sec7_Strips_A: BINCLUDE "data/generated/ojz/act1/sec7_strips_a.bin"
    align 2
OJZ_Sec7_Strips_B: BINCLUDE "data/generated/ojz/act1/sec7_strips_b.bin"
    align 2

OJZ_Sec8_Strips_A: BINCLUDE "data/generated/ojz/act1/sec8_strips_a.bin"
    align 2
OJZ_Sec8_Strips_B: BINCLUDE "data/generated/ojz/act1/sec8_strips_b.bin"
    align 2

OJZ_Palette: BINCLUDE "data/generated/ojz/act1/ojz_palette.bin"
    align 2
