; Test object — animated Sonic walk cycle with DPLC art streaming

; Custom SST field offsets (inside sst_custom)
    ifndef _dplc_ptr
_dplc_ptr       = SST_sst_custom            ; long — DPLC table pointer (ROM)
_art_base       = SST_sst_custom+4          ; long — uncompressed art base (ROM)
    endif

; -----------------------------------------------
; TestAnimated — init routine
; In:  a0 = SST pointer (slot already allocated)
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestAnimated:
        move.l  #Map_Sonic, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_SONIC,0,0), SST_art_tile(a0)
        move.l  #Ani_Sonic, SST_anim_table(a0)
        move.l  #DPLC_Sonic, _dplc_ptr(a0)
        move.l  #Art_Sonic, _art_base(a0)
        move.b  #0, SST_anim(a0)
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        ori.b   #4<<RF_PRIORITY_SHIFT, SST_render_flags(a0)
        move.w  #objroutine(TestAnimated_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestAnimated_Main — per-frame update
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
TestAnimated_Main:
        jsr     AnimateSprite

        movea.l _dplc_ptr(a0), a2
        movea.l _art_base(a0), a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC

        jmp     Draw_Sprite
