; Test enemy — simple patrol object that walks left/right within boundaries
; Base fields (mappings, art_tile, velocity, collision, priority) set by
; Load_Object from ObjDef_Enemy. This code handles behavior-specific init only.

; Custom SST fields (overlay on sst_custom)
_enemy_patrol_left      = SST_sst_custom
_enemy_patrol_right     = SST_sst_custom+2
_enemy_direction        = SST_sst_custom+4

ENEMY_PATROL_SPEED      = $100
ENEMY_PATROL_RANGE      = 48

; -----------------------------------------------
; TestEnemy_Init — behavior-specific init (called as first-frame code_addr)
; In:  a0 = SST pointer (base fields already set by Load_Object)
; -----------------------------------------------
TestEnemy_Init:
        move.w  SST_x_pos(a0), d0
        move.w  d0, d1
        subi.w  #ENEMY_PATROL_RANGE, d0
        move.w  d0, _enemy_patrol_left(a0)
        addi.w  #ENEMY_PATROL_RANGE, d1
        move.w  d1, _enemy_patrol_right(a0)
        clr.b   _enemy_direction(a0)

        move.w  #objroutine(TestEnemy_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestEnemy_Main — per-frame update
; In:  a0 = SST pointer
; -----------------------------------------------
TestEnemy_Main:
        jsr     ObjectMoveX

        move.w  SST_x_pos(a0), d0

        tst.b   _enemy_direction(a0)
        bne.s   .moving_left

        cmp.w   _enemy_patrol_right(a0), d0
        blt.s   .draw
        neg.w   SST_x_vel(a0)
        move.b  #1, _enemy_direction(a0)
        bset    #RF_XFLIP, SST_render_flags(a0)
        bra.s   .draw

.moving_left:
        cmp.w   _enemy_patrol_left(a0), d0
        bgt.s   .draw
        neg.w   SST_x_vel(a0)
        clr.b   _enemy_direction(a0)
        bclr    #RF_XFLIP, SST_render_flags(a0)

.draw:
        jsr     Draw_Sprite
        rts
