; Test enemy — simple patrol object that walks left/right within boundaries
; Base fields (mappings, art_tile, velocity, collision, priority) set by
; Load_Object from ObjDef_Enemy. This code handles behavior-specific init only.
;
; Patrol is counter-driven — no absolute world coordinates stored in sst_custom.
; (Convention: see CODING_CONVENTIONS.md §7.8 and ENGINE_ARCHITECTURE.md §3.)
; steps_remaining counts pixels left before reversing; direction byte sets sign.

; Custom SST fields (overlay on sst_custom)
TEnemyV struct
steps_remaining ds.w 1                  ; pixels remaining before turn
direction       ds.b 1                  ; 0 = moving right, 1 = moving left
TEnemyV endstruct
        objvarsCheck TEnemyV_len
_enemy_steps    = SST_sst_custom+TEnemyV_steps_remaining
_enemy_direction = SST_sst_custom+TEnemyV_direction

ENEMY_PATROL_SPEED      = $100
ENEMY_PATROL_RANGE      = 48            ; pixels each side from spawn centre

; -----------------------------------------------
; TestEnemy_Init — behavior-specific init (called as first-frame code_addr)
; In:  a0 = SST pointer (base fields already set by Load_Object)
; Out: none
; Clobbers: d0, a1
; -----------------------------------------------
TestEnemy_Init:
        move.w  #ENEMY_PATROL_RANGE, _enemy_steps(a0)
        clr.b   _enemy_direction(a0)

        move.w  #objroutine(TestEnemy_Main), SST_code_addr(a0)

; -----------------------------------------------
; TestEnemy_Main — per-frame update
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0-d1, a1
; -----------------------------------------------
TestEnemy_Main:
        jsr     ObjectMoveX

        ; Decrement steps counter.  One step = one pixel (speed $100 = 1 px/frame).
        move.w  _enemy_steps(a0), d0
        subq.w  #1, d0
        bne.s   .steps_ok

        ; Steps exhausted — reverse direction and reload counter.
        neg.w   SST_x_vel(a0)
        move.w  #ENEMY_PATROL_RANGE*2, d0      ; full leg: 2× range each way
        tst.b   _enemy_direction(a0)
        beq.s   .was_right
        clr.b   _enemy_direction(a0)
        bclr    #RF_XFLIP, SST_render_flags(a0)
        bra.s   .steps_ok
.was_right:
        move.b  #1, _enemy_direction(a0)
        bset    #RF_XFLIP, SST_render_flags(a0)

.steps_ok:
        move.w  d0, _enemy_steps(a0)

.draw:
        jmp     Draw_Sprite
