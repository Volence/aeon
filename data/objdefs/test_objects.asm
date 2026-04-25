; Object definitions for test objects
; Format: code_addr, format_byte, pad, mappings, art_tile, [conditional fields]

; -----------------------------------------------
; ObjDef_Static — display-only, no collision or priority
; -----------------------------------------------
ObjDef_Static:
        dc.w    objroutine(TestStatic_Main)
        dc.b    OBJ_FMT_MINIMAL
        dc.b    0
        dc.l    Map_TestObj
        dc.w    vram_art(VRAM_TEST_OBJ,0,0)

; -----------------------------------------------
; ObjDef_Solid — static platform with collision
; Format: OBJ_FMT_STATIC = collision + priority
; -----------------------------------------------
ObjDef_Solid:
        dc.w    objroutine(TestSolid_Init)
        dc.b    OBJ_FMT_STATIC|(1<<ODF_SUBTYPE)
        dc.b    0
        dc.l    Map_TestObj
        dc.w    vram_art(VRAM_TEST_OBJ,0,0)
        ; ODF_COLLISION:
        dc.b    16, 16
        dc.b    COLLISION_SOLID, 0
        ; ODF_PRIORITY:
        dc.w    3

; -----------------------------------------------
; ObjDef_Enemy — patrolling enemy with velocity + collision
; Format: OBJ_FMT_MOVING = velocity + collision + priority
; -----------------------------------------------
ObjDef_Enemy:
        dc.w    objroutine(TestEnemy_Init)
        dc.b    OBJ_FMT_MOVING
        dc.b    0
        dc.l    Map_TestObj
        dc.w    vram_art(VRAM_TEST_OBJ,0,0)
        ; ODF_VELOCITY:
        dc.w    ENEMY_PATROL_SPEED, 0
        ; ODF_COLLISION:
        dc.b    16, 16
        dc.b    COLLISION_HURT, 0
        ; ODF_PRIORITY:
        dc.w    4

; -----------------------------------------------
; ObjDef_Parent — multi-part object (spawns children on init)
; Format: OBJ_FMT_MINIMAL + priority
; -----------------------------------------------
ObjDef_Parent:
        dc.w    objroutine(TestParent)
        dc.b    (1<<ODF_PRIORITY)
        dc.b    0
        dc.l    Map_TestObj
        dc.w    vram_art(VRAM_TEST_OBJ,0,0)
        ; ODF_PRIORITY:
        dc.w    3
