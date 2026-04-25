; Test solid block — static platform with COLLISION_SOLID response
; No movement, just drawn and collidable

; -----------------------------------------------
; TestSolid — init routine
; In:  a0 = SST pointer (x_pos/y_pos already set by spawner)
; -----------------------------------------------
TestSolid:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #1, SST_mapping_frame(a0)       ; frame 1 = green square
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        move.b  #COLLISION_SOLID, SST_collision_resp(a0)
        move.w  #3, SST_priority(a0)
        move.w  #objroutine(TestSolid_Main), SST_code_addr(a0)

        ; Fall through to main for first frame
; -----------------------------------------------
; TestSolid_Main — per-frame update
; In:  a0 = SST pointer
; -----------------------------------------------
TestSolid_Main:
        jsr     Draw_Sprite
        rts
