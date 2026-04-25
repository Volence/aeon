; Test object — static display at fixed position
; Fields set by Load_Object from ObjDef_Static

; -----------------------------------------------
; TestStatic_Main — display-only (no logic)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
TestStatic_Main:
        jmp     Draw_Sprite
