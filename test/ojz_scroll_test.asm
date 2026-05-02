; OJZ horizontal scroll test state (§4 Phase 1, §2 A.1 wired)
; Drives camera directly via controller input (no player physics).
; Left/right pad: 6px/frame camera movement.
; Section teleport fires automatically at X thresholds.

; -----------------------------------------------
; GameState_OJZScroll_Init — one-shot setup
; -----------------------------------------------
GameState_OJZScroll_Init:
        ; -- per-8-row HScroll mode (reg $0B bits 1:0 = %10) --
        setVDPReg VDP_Shadow_vdp_mode3, #$02

        ; -- load BGND palette (32 bytes, "SonicAndTails") into CRAM line 0 --
        ; -- load OJZ palette (96 bytes, 3 pages) into CRAM lines 1-3 --
        ; sonic_hack runtime layout: PalPtr_BGND -> line 0, PalPtr_OJZ -> line 1.
        ; The BGND palette is what gives OJZ's clouds + grass band their real
        ; (magenta/pink) colors — chunk-source nametable words use palette bits
        ; 0 to reference these entries. Without BGND loaded, palette-0 BG tiles
        ; render against an empty CRAM line 0 = black.
        lea     BGND_Palette, a0
        lea     (Palette_Buffer).w, a1              ; CRAM line 0 base
        moveq   #32/4-1, d0
.copy_bgnd:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_bgnd

        lea     OJZ_Palette, a0
        lea     (Palette_Buffer+$20).w, a1          ; CRAM line 1 base
        moveq   #96/4-1, d0
.copy_ojz:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_ojz
        move.b  #$0F, (Palette_Dirty).w

        ; -- load deduped FG tile pool via S4LZ → VRAM (display still off) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Level_LoadArt

        ; -- initialise camera first (Section_FillInitial reads Camera_X) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Camera_Init

        ; -- init object system (must precede Player_1 setup and Section_Init) --
        jsr     InitObjectRAM

        ; -- initialise Player_1 at camera-center position so Camera_Update's
        ;    deadzone tracking begins at rest (no jolt on first frame).
        ;    Player_1.x_pos = Camera_X + CAM_SCREEN_HALF_W; same for Y. --
        move.w  (Camera_X).w, d0                ; high word of camera_x (16.16 → integer pixels)
        addi.w  #CAM_SCREEN_HALF_W, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Player_1+SST_x_pos).w
        move.w  (Camera_Y).w, d0
        addi.w  #CAM_SCREEN_HALF_H, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Player_1+SST_y_pos).w
        clr.w   (Player_1+SST_x_vel).w
        clr.w   (Player_1+SST_y_vel).w

        ; -- set up Player_1 as TestPlayer (physics + debug toggle).
        ;    Start in debug mode (yellow square) for free-flight testing. --
        move.b  #1, (Player_1+_debug_flag).w
        move.w  #objroutine(TestPlayer_Main), (Player_1+SST_code_addr).w
        move.l  #Map_TestObj, (Player_1+SST_mappings).w
        move.w  #$A0FA, (Player_1+SST_art_tile).w
        move.w  #7, (Player_1+SST_priority).w
        move.b  #1, (Player_1+SST_sprite_piece_count).w
        move.b  #16, (Player_1+SST_width_pixels).w
        move.b  #16, (Player_1+SST_height_pixels).w
        move.l  #DPLC_Sonic, (Player_1+_dplc_ptr).w
        move.l  #Art_Sonic, (Player_1+_art_base).w
        move.l  #Ani_Sonic, (Player_1+SST_anim_table).w

        ; -- write 4 marker tiles to VRAM (16×16 sprite = 2×2 tiles).
        ;    Tile 250 ($FA, = byte $1F40) sits between section art and the
        ;    BG region ($500+). All pixels colour 12 = solid block.
        stopZ80
        move.l  #vdpComm($1F40,VRAM,WRITE), (VDP_CTRL).l
        lea     PlayerMarkerTile(pc), a0
        moveq   #128/4-1, d0
.copy_marker:
        move.l  (a0)+, (VDP_DATA).l
        dbf     d0, .copy_marker
        startZ80

        ; -- initialise section streaming (fills nametable over 3 VBlanks) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Section_Init

        ; -- §4.7: populate tile cache (must run AFTER Camera_Init +
        ;    Section_Init so Camera_X, Current_Act_Ptr, and Slot_Section_Map
        ;    are valid) --
        jsr     Tile_Cache_Init

        ; -- synchronous plane fill: trigger Section_RedrawPlanes before
        ;    display on so the nametable is fully populated from frame 1.
        ;    Without this, Section_UpdateColumns gradually fills over ~3
        ;    frames, causing a visible snap when starting at non-zero X. --
        st      (Section_Plane_Dirty).w
        stopZ80
        jsr     Section_UpdateColumns
        startZ80

        ; -- §4.6 parallax init: pull start section's parallax_config --
        lea     OJZ_Act1_Descriptor, a0
        movea.l Act_sec_grid_ptr(a0), a1        ; a1 = sec table base
        moveq   #0, d0
        move.b  Act_start_sec_x(a0), d0         ; flat section_id (sec_y=0 for OJZ)
        move.w  d0, d1
        lsl.w   #6, d0                          ; sec_id × 64
        lsl.w   #3, d1                          ; sec_id × 8
        add.w   d1, d0                          ; sec_id × 72 = Sec_len
        adda.w  d0, a1                          ; a1 = start section ptr
        movea.l Sec_sec_parallax_config(a1), a0 ; a0 = parallax_config* (NULL = act default)
        cmpa.w  #0, a0
        bne.s   .init_have_config
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
.init_have_config:
        jsr     Parallax_Init

        ; -- prime HScroll/VScroll buffers so the first frame displays
        ;    with correct scroll offsets (otherwise HScroll=0 for one frame) --
        jsr     Parallax_Update

        ; -- enable display now that VRAM and nametable are populated --
        setVDPReg VDP_Shadow_vdp_mode2, #$74    ; display on, VBlank on, DMA on, M5 on

        ; -- set VInt_Ptr to level handler --
        move.l  #VInt_Level, (VInt_Ptr).w

        ; -- transition to update loop --
        move.l  #GameState_OJZScroll_Update, (Game_State).w
        rts

; -----------------------------------------------
; GameState_OJZScroll_Update — per-frame update
; -----------------------------------------------
GameState_OJZScroll_Update:
        ; -- initialize sprite system for this frame --
        jsr     InitSpriteSystem

        ; -- execute all objects (TestPlayer handles its own movement) --
        jsr     RunObjects

        ; -- camera follows Player_1 (deadzone + preview-aware clamp) --
        jsr     Camera_Update

        ; -- §4.7: fill tile cache with new blocks as camera scrolls --
        jsr     Tile_Cache_Fill

        ; -- section teleport check (reads Player_1.x_pos via .check entry below) --
        jsr     Section_Check

        ; -- §4.9: camera-driven entity scan (load/despawn rings + objects) --
        jsr     EntityWindow_Scan

        ; -- per-column nametable streaming --
        jsr     Section_UpdateColumns

        ; -- collision detection --
        jsr     TouchResponse
        jsr     RingCollision

        ; -- build sprite table from priority bands + ring sprites --
        jsr     Render_Sprites
        move.b  #1, (Sprite_Table_Dirty).w

        ; -- Derive active flat section_id (2D-correct) for T14 + T15 --
        ; flat_id = sec_y * grid_w + sec_x, computed once and reused.
        ; Vertical half: if Camera_Y >= SLOT_ORIGIN_U + SECTION_SIZE ($A00),
        ; the camera is in the lower section of the vertical pair → sec_y += 1.
        ; (Mirrors horizontal slot detection at SLOT_ORIGIN_R for Camera_X.)
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0                              ; d0.w = Camera_X high word
        moveq   #0, d2                          ; assume slot 0
        cmpi.w  #SLOT_ORIGIN_R, d0
        blt.s   .slot_resolved
        moveq   #1, d2                          ; X >= $A00 → slot 1
.slot_resolved:
        add.w   d2, d2                          ; d2 = slot * 2 byte offset
        lea     (Slot_Section_Map).w, a3
        moveq   #0, d0
        move.b  1(a3, d2.w), d0                 ; d0 = sec_y (from slot map)
        ; vertical half detection: camera in lower section?
        move.l  (Camera_Y).w, d1
        swap    d1                              ; d1.w = Camera_Y high word
        cmpi.w  #SLOT_ORIGIN_U+SECTION_SIZE, d1
        blt.s   .vert_resolved
        addq.w  #1, d0                          ; Camera_Y >= $A00 → lower section
.vert_resolved:
        tst.w   d0
        beq.s   .flat_add_x                     ; sec_y=0 → skip multiply
        move.w  Act_grid_w(a0), d1              ; d1 = grid_w
        move.w  d0, d3
        moveq   #0, d0
        subq.w  #1, d3
.flat_mul:
        add.w   d1, d0
        dbf     d3, .flat_mul
.flat_add_x:
        moveq   #0, d1
        move.b  (a3, d2.w), d1                  ; d1 = sec_x
        add.w   d1, d0                          ; d0 = flat section_id
        move.w  d0, d6                          ; save flat_id for T14 + T15

        ; -- §4.6 T14: parallax follows active slot --
        tst.b   (Parallax_Snap_Pending).w
        bne.s   .skip_t14
        movea.l Act_sec_grid_ptr(a0), a1
        move.w  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0                          ; flat_id × 64
        lsl.w   #3, d1                          ; flat_id × 8
        add.w   d1, d0                          ; flat_id × 72 = Sec_len
        adda.w  d0, a1                          ; a1 = active sec entry
        movea.l Sec_sec_parallax_config(a1), a0 ; a0 = active config
        cmpa.w  #0, a0
        bne.s   .t14_have_config
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
.t14_have_config:
        jsr     Parallax_StartTransition
.skip_t14:

        ; -- T15 diagnostic: per-section sky-color marker --
        move.w  d6, d0                          ; flat section_id
        cmpi.b  #9, d0                          ; clamp to grid size (3×3 = 9 sections)
        blo.s   .marker_id_ok
        moveq   #0, d0
.marker_id_ok:
        lea     OJZ_SectionMarkerColors(pc), a3
        add.w   d0, d0
        move.w  (a3, d0.w), d1                  ; d1 = section's marker color
        move.w  d1, (Palette_Buffer).w          ; CRAM[0] = backdrop tint
        ori.b   #1, (Palette_Dirty).w           ; flag palette line 0 dirty

        ; -- §4.6 fix: force VDP mode_set_3 every frame from the active
        ;    config. Without this, Parallax_StartTransition's same-config
        ;    short-circuit can leave mode_set_3 stuck at a previous
        ;    section's setting. During a smooth transition (T14) the
        ;    "active" config is Target_Config — buffer is built from it
        ;    so register must match its mode bits.
        tst.b   (Parallax_Transition_Frames).w
        beq.s   .mode_use_current
        movea.l (Parallax_Target_Config).w, a0
        bra.s   .mode_have_config
.mode_use_current:
        movea.l (Parallax_Current_Config).w, a0
.mode_have_config:
        cmpa.w  #0, a0
        beq.s   .mode_default
        cmpi.l  #$00400000, a0
        bhs.s   .mode_default
        moveq   #%10, d0                     ; per-cell H baseline
        move.l  parallax_config_pcfg_deform_table_fg(a0), d1
        or.l    parallax_config_pcfg_deform_table_bg(a0), d1
        beq.s   .mode_h_done
        moveq   #%11, d0                     ; per-line if any H-deform
.mode_h_done:
        move.l  parallax_config_pcfg_v_deform_table_bg(a0), d1
        beq.s   .mode_set
        ori.b   #%100, d0                    ; bit 2 = per-column V-scroll
        bra.s   .mode_set
.mode_default:
        moveq   #%10, d0                     ; default per-cell H
.mode_set:
        setVDPReg VDP_Shadow_vdp_mode3, d0
        ; Also force VDP register $0B directly with proper Z80-stop wrap.
        ; First read VDP_CTRL to reset the command state machine — otherwise
        ; a half-finished 32-bit address command from upstream code (e.g.
        ; Section_UpdateColumns) would consume our $8B?? as its second word,
        ; corrupting the VDP and leaving reg $0B unchanged.
        andi.w  #$00FF, d0
        ori.w   #$8B00, d0                   ; d0 = $8B?? = "set reg $0B = ??"
        stopZ80
        move.w  (VDP_CTRL).l, d1             ; reset command state machine
        move.w  d0, (VDP_CTRL).l
        startZ80

        ; -- update HScroll buffer + Vscroll (§4.6 parallax) --
        jsr     Parallax_Update
        rts

; -----------------------------------------------
; Per-section sky tint table — referenced by the marker code in Update.
; CRAM colors (BGR, 9-bit). Section_id indexes into this array, so the
; backdrop visibly differs per section. T15 diagnostic only.
; -----------------------------------------------
OJZ_SectionMarkerColors:
        dc.w    $000E           ; Sec0 (0,0): bright red
        dc.w    $00E0           ; Sec1 (1,0): bright green
        dc.w    $0E00           ; Sec2 (2,0): bright blue
        dc.w    $00EE           ; Sec3 (0,1): yellow
        dc.w    $0E0E           ; Sec4 (1,1): magenta
        dc.w    $0EE0           ; Sec5 (2,1): cyan
        dc.w    $0EEE           ; Sec6 (0,2): white
        dc.w    $0888           ; Sec7 (1,2): gray
        dc.w    $060E           ; Sec8 (2,2): orange

; -----------------------------------------------
; PlayerMarkerTile — 4 × 8×8 tiles, all pixels colour 12 (128 bytes).
; Pal 1 entry 12 = $00EE = bright yellow. DMA'd to VRAM tile 250
; ($1F40) at level init. 2×2 layout matches Map_TestObj_F0 (16×16).
; -----------------------------------------------
PlayerMarkerTile:
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
