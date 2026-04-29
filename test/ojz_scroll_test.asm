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
        ; Camera_Init's start_local_y formula leaves Camera_Y at $1F0 which
        ; is outside the cam_min_y/cam_max_y range we use for diagnostic
        ; vertical scroll (0..152). Force Y=0 so we start at top of filled
        ; plane A and Up/Down moves stay within plane rows 0..47.
        clr.l   (Camera_Y).w

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

        ; -- write a marker tile to VRAM so the player has a visible sprite.
        ;    Tile 250 ($FA, = byte $1F40) sits between section art (0-225) and
        ;    the BG region ($500+). 32 bytes of $CC = solid colour-12 8x8 block.
        stopZ80
        move.l  #vdpComm($1F40,VRAM,WRITE), (VDP_CTRL).l
        lea     PlayerMarkerTile(pc), a0
        moveq   #32/4-1, d0
.copy_marker:
        move.l  (a0)+, (VDP_DATA).l
        dbf     d0, .copy_marker
        startZ80

        ; -- initialise section streaming (fills nametable over 3 VBlanks) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Section_Init

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
        movea.l Sec_sec_parallax_config(a1), a0 ; a0 = parallax_config* (NULL = inert)
        jsr     Parallax_Init

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
        ; -- player input drives Player_1 motion; Camera_Update follows. --
        moveq   #0, d0
        move.b  (Ctrl_1_Held).w, d0

        btst    #3, d0          ; bit 3 = RIGHT
        beq.s   .check_left
        addi.l  #6<<16, (Player_1+SST_x_pos).w
        bra.s   .player_x_done

.check_left:
        btst    #2, d0          ; bit 2 = LEFT
        beq.s   .player_x_done
        subi.l  #6<<16, (Player_1+SST_x_pos).w

.player_x_done:
        ; -- vertical input: bits 0/1 of Ctrl_1_Held = UP/DOWN --
        btst    #1, d0          ; bit 1 = DOWN
        beq.s   .check_up
        addi.l  #6<<16, (Player_1+SST_y_pos).w
        bra.s   .player_y_done

.check_up:
        btst    #0, d0          ; bit 0 = UP
        beq.s   .player_y_done
        subi.l  #6<<16, (Player_1+SST_y_pos).w

.player_y_done:
        ; -- camera follows Player_1 (deadzone + preview-aware clamp) --
        jsr     Camera_Update

        ; -- section teleport check (reads Player_1.x_pos via .check entry below) --
        jsr     Section_Check

        ; -- per-column nametable streaming --
        jsr     Section_UpdateColumns

        ; -- write marker sprite at Player_1's screen position. Sprite slot 0,
        ;    link = 0 (terminate list). Tile 300 = solid colour-15 8x8 block,
        ;    palette 1 (OJZ palette), priority 1 (renders on top of plane B). --
        move.w  (Player_1+SST_x_pos).w, d0     ; engine-pixel X
        sub.w   (Camera_X).w, d0               ; screen X = player - camera
        addi.w  #128, d0                       ; sprite X = screen + 128
        move.w  (Player_1+SST_y_pos).w, d1
        sub.w   (Camera_Y).w, d1
        addi.w  #128, d1                       ; sprite Y = screen + 128

        lea     (Sprite_Table_Buffer).w, a0
        move.w  d1, (a0)+                      ; Y position
        move.b  #$00, (a0)+                    ; size (0 = 8x8)
        move.b  #$00, (a0)+                    ; link = 0 (terminate)
        move.w  #$A0FA, (a0)+                  ; tile $FA = 250 (= byte $1F40), pal 1, priority 1
        move.w  d0, (a0)+                      ; X position
        move.b  #1, (Sprite_Table_Dirty).w

        ; -- §4.6 T14: parallax follows ACTIVE slot, not just slot 0.
        ;    Compute which slot the camera is currently inside (slot 0 if
        ;    Camera_X < SLOT_ORIGIN_R, else slot 1) and call
        ;    Parallax_StartTransition with that slot's parallax_config.
        ;    StartTransition is idempotent (no-ops if Current or Target
        ;    already matches) so per-frame calls cost ~1 register read +
        ;    a comparison branch when nothing has changed. When the user
        ;    crosses the slot boundary, the smooth lerp begins.
        move.l  (Camera_X).w, d0
        swap    d0                              ; d0.w = Camera_X high word
        moveq   #0, d2                          ; assume slot 0
        cmpi.w  #SLOT_ORIGIN_R, d0
        blt.s   .slot_resolved
        moveq   #1, d2                          ; X >= $A00 → slot 1
.slot_resolved:
        movea.l (Current_Act_Ptr).w, a0
        movea.l Act_sec_grid_ptr(a0), a1
        add.w   d2, d2                          ; d2 *= 2 (byte offset in Slot_Section_Map)
        lea     (Slot_Section_Map).w, a3
        moveq   #0, d0
        move.b  (a3, d2.w), d0                  ; sec_id at active slot
        move.w  d0, d1
        lsl.w   #6, d0                          ; sec_id × 64
        lsl.w   #3, d1                          ; sec_id × 8
        add.w   d1, d0                          ; sec_id × 72 = Sec_len
        adda.w  d0, a1                          ; a1 = active sec entry
        movea.l Sec_sec_parallax_config(a1), a0 ; a0 = active config
        jsr     Parallax_StartTransition

        ; -- T15 diagnostic: per-section sky-color marker --
        ; Re-derive active slot section_id, look up a tint color, write to
        ; CRAM[0] via Palette_Buffer + dirty flag. CRAM[0] is the backdrop
        ; shown behind transparent BG pixels — visible as the "sky" tint.
        ; Lets the user see at a glance which section they're in.
        move.l  (Camera_X).w, d0
        swap    d0
        moveq   #0, d2
        cmpi.w  #SLOT_ORIGIN_R, d0
        blt.s   .marker_slot_resolved
        moveq   #1, d2
.marker_slot_resolved:
        add.w   d2, d2                          ; d2 = slot * 2 byte offset
        lea     (Slot_Section_Map).w, a3
        moveq   #0, d0
        move.b  (a3, d2.w), d0                  ; d0 = active section_id
        cmpi.b  #9, d0                          ; clamp to table size (9 OJZ sections)
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
        dc.w    $0000           ; Sec0: black (default)
        dc.w    $000E           ; Sec1: bright red
        dc.w    $00E0           ; Sec2: bright green
        dc.w    $0E00           ; Sec3: bright blue
        dc.w    $00EE           ; Sec4: yellow
        dc.w    $0E0E           ; Sec5: magenta
        dc.w    $0EE0           ; Sec6: cyan
        dc.w    $0888           ; Sec7: gray
        dc.w    $0EEE           ; Sec8: white

; -----------------------------------------------
; PlayerMarkerTile — 8×8 tile, all pixels colour 12 (4bpp, 32 bytes).
; Pal 1 entry 12 = $00EE = bright yellow (vs entry 15 = sky-blue, invisible
; against the OJZ sky). DMA'd to VRAM tile 250 ($1F40) at level init —
; matches the $A0FA art_tile in the sprite write.
; -----------------------------------------------
PlayerMarkerTile:
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
        dc.l    $CCCCCCCC, $CCCCCCCC, $CCCCCCCC, $CCCCCCCC
