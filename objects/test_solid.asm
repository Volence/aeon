; Test solid block — static platform with COLLISION_SOLID response
; Base fields set by Load_Object from ObjDef_Solid.
; Uses subtype as mapping_frame selector.

TestSolid_Init:
        move.b  SST_subtype(a0), SST_mapping_frame(a0)
        move.w  #objroutine(TestSolid_Main), SST_code_addr(a0)

TestSolid_Main:
        jsr     Draw_Sprite
        rts
