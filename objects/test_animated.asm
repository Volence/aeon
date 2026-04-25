; Test object — animated Sonic walk cycle with DPLC art streaming

; Custom SST field offsets (inside sst_custom)
_dplc_ptr       = SST_sst_custom            ; long — DPLC table pointer (ROM)
_art_base       = SST_sst_custom+4          ; long — uncompressed art base (ROM)

TestAnimated:
        move.l  #Map_Sonic, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_SONIC,0,0), SST_art_tile(a0)
        move.l  #Ani_Sonic, SST_anim_table(a0)
        move.l  #DPLC_Sonic, _dplc_ptr(a0)
        move.l  #Art_Sonic, _art_base(a0)
        move.b  #0, SST_anim(a0)
        move.b  #$FF, SST_prev_anim(a0)
        move.b  #$FF, SST_prev_frame(a0)
        move.w  #4, SST_priority(a0)
        move.w  #objroutine(TestAnimated_Main), SST_code_addr(a0)

TestAnimated_Main:
        jsr     AnimateSprite

        move.b  SST_mapping_frame(a0), d0
        cmp.b   SST_prev_frame(a0), d0
        beq.s   .no_dplc
        move.b  d0, SST_prev_frame(a0)

        movea.l a0, a3

        moveq   #0, d0
        move.b  SST_mapping_frame(a3), d0
        movea.l _dplc_ptr(a3), a0
        movea.l _art_base(a3), a1
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC

        movea.l a3, a0

.no_dplc:
        jsr     Draw_Sprite
        rts
