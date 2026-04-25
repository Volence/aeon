; Test solid block — static platform with COLLISION_SOLID response
; Base fields set by Load_Object from ObjDef_Solid.
; Uses subtype as mapping_frame selector.

; -----------------------------------------------
; TestSolid_Init — set mapping frame from subtype
; In:  a0 = SST pointer (base fields set by Load_Object)
; Out: none
; Clobbers: none
; -----------------------------------------------
TestSolid_Init:
        move.b  SST_subtype(a0), SST_mapping_frame(a0)
        move.w  #objroutine(TestSolid_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestSolid_Main — display-only (collision handled by TouchResponse)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
TestSolid_Main:
        jmp     Draw_Sprite
