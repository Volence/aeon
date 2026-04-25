; Test enemy — simple patrol object that walks left/right within boundaries
; collision_resp = COLLISION_HURT — damages player on contact

; Custom SST fields (overlay on sst_custom at $2C)
_enemy_patrol_left      = SST_sst_custom        ; $2C — word, left X boundary
_enemy_patrol_right     = SST_sst_custom+2      ; $2E — word, right X boundary
_enemy_direction        = SST_sst_custom+4      ; $30 — byte, 0 = right, 1 = left

ENEMY_PATROL_SPEED      = $100                  ; horizontal patrol velocity
ENEMY_PATROL_RANGE      = 48                    ; pixels each side of spawn point

; -----------------------------------------------
; TestEnemy — init routine
; In:  a0 = SST pointer (x_pos/y_pos already set by spawner)
; -----------------------------------------------
TestEnemy:
        move.l  #Map_TestObj, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_OBJ,0,0), SST_art_tile(a0)
        move.b  #0, SST_mapping_frame(a0)       ; frame 0 = red square
        move.b  #16, SST_width_pixels(a0)
        move.b  #16, SST_height_pixels(a0)
        move.b  #COLLISION_HURT, SST_collision_resp(a0)
        move.w  #4, SST_priority(a0)
        move.w  #ENEMY_PATROL_SPEED, SST_x_vel(a0)

        ; Set patrol boundaries from current X position
        move.w  SST_x_pos(a0), d0               ; integer X
        move.w  d0, d1
        subi.w  #ENEMY_PATROL_RANGE, d0
        move.w  d0, _enemy_patrol_left(a0)
        addi.w  #ENEMY_PATROL_RANGE, d1
        move.w  d1, _enemy_patrol_right(a0)
        clr.b   _enemy_direction(a0)            ; start moving right

        move.w  #objroutine(TestEnemy_Main), SST_code_addr(a0)

        ; Fall through to main for first frame
; -----------------------------------------------
; TestEnemy_Main — per-frame update
; In:  a0 = SST pointer
; -----------------------------------------------
TestEnemy_Main:
        jsr     ObjectMoveX

        ; Check patrol boundaries
        move.w  SST_x_pos(a0), d0               ; integer X

        tst.b   _enemy_direction(a0)
        bne.s   .moving_left

        ; Moving right — check right boundary
        cmp.w   _enemy_patrol_right(a0), d0
        blt.s   .draw
        ; Crossed right boundary — reverse to left
        neg.w   SST_x_vel(a0)
        move.b  #1, _enemy_direction(a0)
        bset    #RF_XFLIP, SST_render_flags(a0)
        bra.s   .draw

.moving_left:
        ; Moving left — check left boundary
        cmp.w   _enemy_patrol_left(a0), d0
        bgt.s   .draw
        ; Crossed left boundary — reverse to right
        neg.w   SST_x_vel(a0)
        clr.b   _enemy_direction(a0)
        bclr    #RF_XFLIP, SST_render_flags(a0)

.draw:
        jsr     Draw_Sprite
        rts
