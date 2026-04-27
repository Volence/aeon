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
        setVDPReg VDP_Shadow_vdp_mode2, #$64    ; display on, VBlank on, DMA on

        ; -- set VInt_Ptr to level handler --
        move.l  #VInt_Level, (VInt_Ptr).w

        ; -- transition to update loop --
        move.l  #GameState_OJZScroll_Update, (Game_State).w
        rts

; -----------------------------------------------
; GameState_OJZScroll_Update — per-frame update
; -----------------------------------------------
GameState_OJZScroll_Update:
        ; -- direct camera control via controller --
        moveq   #0, d0
        move.b  (Ctrl_1_Held).w, d0

        btst    #3, d0          ; bit 3 = RIGHT
        beq.s   .check_left
        addi.l  #6<<16, (Camera_X).w
        bra.s   .camera_done

.check_left:
        btst    #2, d0          ; bit 2 = LEFT
        beq.s   .camera_done
        subi.l  #6<<16, (Camera_X).w

.camera_done:
        ; -- clamp Camera_X to act bounds (prevent BWD teleport at section 0) --
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0
        cmp.w   Act_cam_min_x(a0), d0
        bge.s   .check_max_x
        move.w  Act_cam_min_x(a0), d0
        bra.s   .clamp_x
.check_max_x:
        cmp.w   Act_cam_max_x(a0), d0
        ble.s   .clamp_done
        move.w  Act_cam_max_x(a0), d0
.clamp_x:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w
.clamp_done:

        ; -- section teleport check --
        jsr     Section_Check

        ; -- per-column nametable streaming --
        jsr     Section_UpdateColumns

        ; -- update HScroll buffer --
        jsr     Hscroll_Update

        ; -- update vertical scroll (Camera_Y -> Vscroll_Factor) --
        move.l  (Camera_Y).w, d0
        swap    d0
        neg.w   d0
        move.w  d0, (Vscroll_Factor+2).w
        rts
