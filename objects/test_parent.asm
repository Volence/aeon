; Test parent — multi-part object that spawns children, then self-destructs
; Demonstrates CreateChild_Normal lifecycle + DeleteChildren cascade.

_parent_life_timer      = SST_sst_custom        ; word — countdown to self-destruct

PARENT_LIFETIME         = 180                   ; frames before self-destruct (3 seconds)

; -----------------------------------------------
; TestChildPart — child init (sets display fields, transitions to draw-only)
; In:  a0 = SST pointer (position, mappings, art_tile set by CreateChild_Normal)
; Out: none
; Clobbers: none
; -----------------------------------------------
TestChildPart:
        move.w  #3, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #objroutine(TestChildPart_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestChildPart_Main — display-only
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1
; -----------------------------------------------
TestChildPart_Main:
        jmp     Draw_Sprite

; -----------------------------------------------
; TestParent — init routine
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        moveq   #0, d0
        move.b  d0, SST_mapping_frame(a0)
        move.w  #3, SST_priority(a0)
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        bset    #RF_COORDMODE, SST_render_flags(a0)
        move.w  #PARENT_LIFETIME, _parent_life_timer(a0)

        lea     .ChildDesc(pc), a1
        jsr     CreateChild_Normal

        move.w  #objroutine(TestParent_Main), SST_code_addr(a0)
        bra.s   TestParent_Main

.ChildDesc:
        dc.w    objroutine(TestChildPart)
        dc.b    -24, 0
        dc.w    objroutine(TestChildPart)
        dc.b    24, 0
        dc.w    objroutine(TestChildPart)
        dc.b    0, -24
        dc.w    0

; -----------------------------------------------
; TestParent_Main — per-frame: countdown, then self-destruct with children
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d3, a1-a2
; -----------------------------------------------
TestParent_Main:
        subq.w  #1, _parent_life_timer(a0)
        bne.s   .draw

        jsr     DeleteChildren
        jmp     DeleteObject

.draw:
        jmp     Draw_Sprite
