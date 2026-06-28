; Object definitions for test objects — v2 archetype templates (see objdef macro)

ObjDef_Static:
        objdef code=TestStatic_Main, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0)

ObjDef_Solid:
        objdef code=TestSolid_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
               zpri=3, wdth=16, hght=16, col=COLLISION_SOLID
ObjDef_Enemy:
        objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
               zpri=4, xvel=ENEMY_PATROL_SPEED, wdth=16, hght=16, col=COLLISION_HURT
ObjDef_Parent:
        objdef code=TestParent, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), zpri=3

