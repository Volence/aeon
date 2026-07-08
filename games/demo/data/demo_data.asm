; Demo data — objdef, mapping, art, palette. TODO: your game's data starts here.
ObjDef_DemoBox:
        objdef code=DemoBox_Main, map=Map_DemoBox, art=vram_art(VRAM_DEMO_OBJ,0,0)

Map_DemoBox:
        dc.w    Map_DemoBox_F0 - Map_DemoBox
Map_DemoBox_F0:
        dc.b    -8, 8, -8, 8                    ; extents
        dc.w    1                               ; 1 piece
        dc.w    -8                              ; Y offset
        dc.b    sprSize(2,2)>>8, 0              ; 16x16
        dc.w    0                               ; tile 0
        dc.w    -8                              ; X offset

DemoObjectList:
        dc.l    ObjDef_DemoBox
        dc.w    160, 112, 0                     ; screen center
        dc.l    0                               ; end

DemoArt:                                        ; 4 tiles solid color 1 + 1 blank (ring slot)
        rept 4
        dc.l    $11111111, $11111111, $11111111, $11111111
        dc.l    $11111111, $11111111, $11111111, $11111111
        endr
        rept 8
        dc.l    0
        endr
DemoArt_End:

DemoPalette:                                    ; 16 colors: dark blue backdrop, white box
        dc.w    $0622, $0EEE, $0000, $0000, $0000, $0000, $0000, $0000
        dc.w    $0000, $0000, $0000, $0000, $0000, $0000, $0000, $0000

; Engine contract (engine/level/bg_anim.asm — BgAnim_Update): every game must
; supply BgAnim_Table; band_count=0 disables the whole system. Sonic 4 gets
; this from its generated act data (tools/inject_editor_bg.py); the demo has
; no BG animation, so it's just the disabled header.
BgAnim_Table:
        dc.w    0                               ; band_count = 0 (disabled)
