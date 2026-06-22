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

        ; -- test object + ring placeholder art (9 tiles at VRAM_TEST_OBJ;
        ;    the last tile is VRAM_RING_PLACEHOLDER for DrawRings) --
        move.l  #TestArt, d1
        move.w  #vram_bytes(VRAM_TEST_OBJ), d2
        move.w  #TestArt_End-TestArt, d3
        jsr     QueueDMA_Critical

        ; -- initialise camera first (Section_FillInitial reads Camera_X) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Camera_Init

        ; -- init object system (must precede Player_1 setup and Section_Init) --
        jsr     InitObjectRAM

        ; -- initialise Player_1 at camera-center position so Camera_Update's
        ;    deadzone tracking begins at rest (no jolt on first frame).
        ;    Player_1.x_pos = Camera_X + CAM_SCREEN_HALF_W; same for Y.
        ;    Camera_X/Y are now WORLD coords (continuous-scroll, Task 2), and
        ;    the spawn derives purely from Camera_X — no SLOT_ORIGIN bias — so
        ;    it is already world-correct; no change needed here. --
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

        ; -- set up Player_1 as the §5 player (Sonic). Player_Init boots
        ;    in debug-fly (yellow square) so the streaming-test workflow
        ;    is unchanged — B drops into physics. --
        lea     (Player_1).w, a0
        jsr     Player_Init

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
        ;    Section_Init so Camera_X and Current_Act_Ptr are valid) --
        jsr     Tile_Cache_Init

        ; -- synchronous plane fill: trigger Section_RedrawPlanes before
        ;    display on so the nametable is fully populated from frame 1.
        ;    Without this, Section_UpdateColumns gradually fills over ~3
        ;    frames, causing a visible snap when starting at non-zero X. --
        st      (Section_Plane_Dirty).w
        stopZ80
        jsr     Section_UpdateColumns
        startZ80

        ; (The PlayerSensors self-check is gone: its expectations were hardcoded
        ; from the STOCK sonic_hack collision, which the engine no longer uses —
        ; collision is now the imported S&K shape set + editor-authored level
        ; data, so the check can never be valid. The dead PlayerSensors_SelfCheck
        ; + _RowFill routines were deleted in the leapfrog teardown.)

        ; -- §4.6 parallax init: pull start section's parallax_config --
        ; Section_GetSecPtrXY handles the full grid math (sec_y included);
        ; runs after Section_Init so Current_Act_Ptr is valid.
        lea     OJZ_Act1_Descriptor, a2
        move.b  Act_start_sec_x(a2), d2
        move.b  Act_start_sec_y(a2), d3
        jsr     Section_GetSecPtrXY             ; a0 = start Sec ptr (Z set = none)
        beq.s   .init_use_act_config
        movea.l Sec_sec_parallax_config(a0), a0 ; a0 = parallax_config* (NULL = act default)
        cmpa.w  #0, a0
        bne.s   .init_have_config
.init_use_act_config:
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_act_parallax_config(a0), a0
.init_have_config:
        jsr     Parallax_Init
        jsr     BgAnim_Init

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

        ; -- execute all objects (Player_Main handles its own movement) --
        jsr     RunObjects

    ifdef SOUND_LOADTEST
        ; DEBUG: force continuous rightward scroll to exercise the streaming-DMA
        ; load (Tile_Cache_Fill / Section_UpdateColumns) for sound-rate VGM
        ; measurement. +6px/frame in the x_pos integer (high) word.
        move.l  (Player_1+SST_x_pos).w, d0
        addi.l  #$00060000, d0
        move.l  d0, (Player_1+SST_x_pos).w
    endif

        ; -- camera follows Player_1 (deadzone + preview-aware clamp) --
        jsr     Camera_Update

        ; -- §4.7: fill tile cache with new blocks as camera scrolls --
        jsr     Tile_Cache_Fill

        ; -- continuous scroll: no per-frame teleport check. Camera/player/
        ;    section streaming run in WORLD space; the level scrolls live with
        ;    no section rebases. (Section_Check + teleport machinery removed in
        ;    a later task.)

        ; -- §4.9: camera-driven entity scan (load/despawn rings + objects) --
        jsr     EntityWindow_Scan

        ; -- per-column nametable streaming --
        jsr     Section_UpdateColumns

        ; -- collision detection --
        jsr     TouchResponse
        jsr     RingCollision

        ; -- build sprite table from priority bands + ring sprites --
        ; (Render_Sprites manages Sprite_Table_Dirty itself, including
        ; the zero-sprite terminator case — no forced dirty needed)
        jsr     Render_Sprites

        ; -- Derive active flat section_id (2D-correct) for T14 + T15 --
        ; flat_id = sec_y * grid_w + sec_x, computed once and reused.
        ; Continuous-scroll: Camera_X/Y are WORLD px, so the active section is
        ; the one under the camera CENTER — derive it straight from the world
        ; camera (camX+160 / camY+112 >> SECTION_SIZE_SHIFT), no slot map or
        ; SLOT_ORIGIN bias. Always in-grid (camera is clamped to the act), so
        ; Section_FlatIDXY needs no range check.
        movea.l (Current_Act_Ptr).w, a0
        move.w  (Camera_X).w, d2               ; world X px
        addi.w  #SCREEN_WIDTH/2, d2
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d2                         ; d2 = sec_x of the camera center
        move.w  (Camera_Y).w, d3              ; world Y px
        addi.w  #SCREEN_HEIGHT/2, d3
        asr.w   d0, d3                         ; d3 = sec_y of the camera center
        movea.l a0, a2                         ; Section_FlatIDXY wants act ptr in a2
        jsr     Section_FlatIDXY               ; d0.w = flat section_id (cross-module: jsr, not bsr.w)
        move.w  d0, d6                         ; save flat_id for T14 + T15

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
        ; -- camera-driven BG tile animation (trunk cores) --
        jsr     BgAnim_Update
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
