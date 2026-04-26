; OJZ horizontal scroll test state (§4 Phase 1)
; Drives camera directly via controller input (no player physics).
; Left/right pad: 6px/frame camera movement.
; Section teleport fires automatically at X thresholds.

; Tile art DMA split: 322 tiles = 10304 bytes > NTSC budget (7200).
; Load in two Critical DMA batches so each fits within one VBlank.
OJZ_TILES_SIZE   = 322 * 32     ; 10304 bytes raw
OJZ_TILES_BATCH1 = 160 * 32     ; 5120 bytes — first batch
OJZ_TILES_BATCH2 = OJZ_TILES_SIZE - OJZ_TILES_BATCH1   ; 5184 bytes — second batch

; -----------------------------------------------
; GameState_OJZScroll_Init — one-shot setup
; -----------------------------------------------
GameState_OJZScroll_Init:
        ; -- per-8-row HScroll mode (reg $0B bits 1:0 = %10) --
        setVDPReg VDP_Shadow_vdp_mode3, #$02

        ; -- load OJZ palette into Palette_Buffer (drained by first VBlank) --
        lea     OJZ_Palette, a0
        lea     (Palette_Buffer).w, a1
        moveq   #96/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        ; -- DMA tile art: batch 1 (tiles 0-159 → VRAM $0000) --
        move.l  #OJZ_Tiles, d1
        moveq   #0, d2
        move.w  #OJZ_TILES_BATCH1, d3
        jsr     QueueDMA_Critical
        jsr     VSync_Wait

        ; -- DMA tile art: batch 2 (tiles 160-321 → VRAM OJZ_TILES_BATCH1) --
        move.l  #OJZ_Tiles+OJZ_TILES_BATCH1, d1
        move.w  #OJZ_TILES_BATCH1, d2
        move.w  #OJZ_TILES_BATCH2, d3
        jsr     QueueDMA_Critical
        jsr     VSync_Wait

        ; -- initialise camera first (Section_FillInitial reads Camera_X) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Camera_Init

        ; -- initialise section streaming (fills nametable over 3 VBlanks) --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Section_Init

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
