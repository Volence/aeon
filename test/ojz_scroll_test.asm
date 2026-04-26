; OJZ horizontal scroll test state (§4 Phase 1)
; Drives camera directly via controller input (no player physics).
; Left/right pad: 6px/frame camera movement.
; Section teleport fires automatically at X thresholds.

; -----------------------------------------------
; GameState_OJZScroll_Init — one-shot setup
; -----------------------------------------------
GameState_OJZScroll_Init:
        ; -- enable display --
        setVDPReg VDP_Shadow_vdp_mode2, #$64    ; display on, VBlank on, DMA on

        ; -- per-8-row HScroll mode (reg $0B bits 1:0 = %10) --
        setVDPReg VDP_Shadow_vdp_mode3, #$02

        ; -- load OJZ palette into Palette_Buffer --
        lea     OJZ_Palette, a0
        lea     (Palette_Buffer).w, a1
        moveq   #128/4-1, d0
.copy_pal:
        move.l  (a0)+, (a1)+
        dbf     d0, .copy_pal
        move.b  #$0F, (Palette_Dirty).w

        ; -- initialise section streaming --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Section_Init

        ; -- initialise camera --
        lea     OJZ_Act1_Descriptor, a0
        jsr     Camera_Init

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

        btst    #BUTTON_RIGHT, d0
        beq.s   .check_left
        addi.l  #6<<16, (Camera_X).w
        bra.s   .camera_done

.check_left:
        btst    #BUTTON_LEFT, d0
        beq.s   .camera_done
        subi.l  #6<<16, (Camera_X).w

.camera_done:
        ; -- section teleport check --
        jsr     Section_Check

        ; -- update HScroll buffer --
        jsr     Hscroll_Update

        ; -- update vertical scroll (Camera_Y -> Vscroll_Factor) --
        move.l  (Camera_Y).w, d0
        swap    d0
        neg.w   d0
        move.w  d0, (Vscroll_Factor+2).w
        rts
