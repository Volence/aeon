; Test object — static display at fixed position
; Init state: set mappings, art_tile, transition to main
; Main state: call Draw_Sprite each frame

TestStatic:
        ; Init: set up display fields
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #0, SST_mapping_frame(a0)
        ; Transition to main state
        move.w  #objroutine(TestStatic_Main), SST_code_addr(a0)

TestStatic_Main:
        jsr     Draw_Sprite
        rts
