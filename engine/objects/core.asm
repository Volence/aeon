; Object system core — allocation, dispatch, deletion

; -----------------------------------------------
; InitObjectRAM — clear all slots, push addresses to free stacks
; Called at game state init (level start, etc.)
; In:  none
; Out: none
; Clobbers: d0-d1, a0-a1
; -----------------------------------------------
InitObjectRAM:
        ; Zero all Object RAM
        lea     (Object_RAM).w, a0
        move.w  #(Object_RAM_End-Object_RAM)/4-1, d0
        moveq   #0, d1
.clear:
        move.l  d1, (a0)+
        dbf     d0, .clear

        ; Init dynamic free stack — push addresses from last to first
        ; so first slot is popped first (LIFO order matches slot 2→41)
        lea     (Dynamic_Free_Stack).w, a0
        lea     (Dynamic_Slots).w, a1
        move.w  #NUM_DYNAMIC-1, d0
.push_dyn:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_dyn
        move.w  #Dynamic_Free_Stack+NUM_DYNAMIC*2, (Dynamic_Free_SP).w

        ; Init effect free stack
        lea     (Effect_Free_Stack).w, a0
        lea     (Effect_Slots).w, a1
        move.w  #NUM_EFFECTS-1, d0
.push_eff:
        move.w  a1, (a0)+
        lea     SST_len(a1), a1
        dbf     d0, .push_eff
        move.w  #Effect_Free_Stack+NUM_EFFECTS*2, (Effect_Free_SP).w

        ; Reset spawn counter (d1 still 0 from .clear loop)
        move.w  d1, (Spawn_Count).w
        rts

; -----------------------------------------------
; AllocDynamic — pop a free dynamic slot
; In:  none
; Out: a1 = SST address of allocated slot (d0=0/Z set on success)
;      d0=1/Z clear if pool exhausted
; Clobbers: d0
; -----------------------------------------------
AllocDynamic:
        cmpi.w  #Dynamic_Free_Stack, (Dynamic_Free_SP).w
        beq.s   .full
        movea.w (Dynamic_Free_SP).w, a1
        subq.w  #2, (Dynamic_Free_SP).w
        movea.w -(a1), a1
        moveq   #0, d0                  ; Z set = success
        rts
.full:
        moveq   #1, d0                  ; Z clear = pool exhausted
        rts

; -----------------------------------------------
; AllocEffect — pop a free effect slot
; In:  none
; Out: a1 = SST address of allocated slot (d0=0/Z set on success)
;      d0=1/Z clear if pool exhausted
; Clobbers: d0
; -----------------------------------------------
AllocEffect:
        cmpi.w  #Effect_Free_Stack, (Effect_Free_SP).w
        beq.s   .full
        movea.w (Effect_Free_SP).w, a1
        subq.w  #2, (Effect_Free_SP).w
        movea.w -(a1), a1
        moveq   #0, d0
        rts
.full:
        moveq   #1, d0
        rts

; -----------------------------------------------
; DeleteObject — push slot back to appropriate free stack, zero SST
; Pool detection (RAM order: Player | Dynamic | System | Effect):
;   addr < Dynamic_Slots           → player slot (no stack push)
;   addr >= Dynamic_Slots AND
;          addr < System_Slots     → dynamic pool
;   addr >= System_Slots AND
;          addr < Effect_Slots     → system slot (no stack push)
;   addr >= Effect_Slots AND
;          addr < Effect_Slots+
;                 SST_len*NUM_EFFECTS → effect pool
; In:  a0 = SST address of object to delete
; Out: none
; Clobbers: d0, a1
; -----------------------------------------------
DeleteObject:
        ; Check Effect pool first (highest address range)
        cmpa.w  #Effect_Slots, a0
        bhs.s   .check_effect

        ; Below Effect_Slots — check System_Slots
        cmpa.w  #System_Slots, a0
        bhs.s   .clear_slot             ; system slot: just clear, no push

        ; Below System_Slots — check Dynamic_Slots
        cmpa.w  #Dynamic_Slots, a0
        bhs.s   .dynamic_pool

        ; Below Dynamic_Slots — player slot: just clear, no push
        bra.s   .clear_slot

.check_effect:
        ; Past Effect_Slots — confirm it's within the effect range
        cmpa.w  #Effect_Slots+SST_len*NUM_EFFECTS, a0
        bhs.s   .clear_slot             ; out of effect range (shouldn't happen)
        ; Fall through: it's a valid effect slot

.effect_pool:
        movea.w (Effect_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Effect_Free_SP).w
        bra.s   .clear_slot

.dynamic_pool:
        movea.w (Dynamic_Free_SP).w, a1
        move.w  a0, (a1)+
        move.w  a1, (Dynamic_Free_SP).w

.clear_slot:
        ; Zero all $50 bytes of the SST entry
        moveq   #0, d0
        move.l  d0, (a0)+       ; $00
        move.l  d0, (a0)+       ; $04
        move.l  d0, (a0)+       ; $08
        move.l  d0, (a0)+       ; $0C
        move.l  d0, (a0)+       ; $10
        move.l  d0, (a0)+       ; $14
        move.l  d0, (a0)+       ; $18
        move.l  d0, (a0)+       ; $1C
        move.l  d0, (a0)+       ; $20
        move.l  d0, (a0)+       ; $24
        move.l  d0, (a0)+       ; $28
        move.l  d0, (a0)+       ; $2C
        move.l  d0, (a0)+       ; $30
        move.l  d0, (a0)+       ; $34
        move.l  d0, (a0)+       ; $38
        move.l  d0, (a0)+       ; $3C
        move.l  d0, (a0)+       ; $40
        move.l  d0, (a0)+       ; $44
        move.l  d0, (a0)+       ; $48
        move.l  d0, (a0)+       ; $4C
        lea     -SST_len(a0), a0 ; restore a0 to slot start
        rts

; -----------------------------------------------
; RunObjects — dispatch all active object slots
; Per-pool loops: players/system/effects always execute,
; dynamic pool is culled by distance from camera.
; Objects that want to die call DeleteObject directly.
;
; Convention: object routines receive a0 = self SST pointer.
; Object routines MUST preserve a0 and d7.
; In:  none
; Out: none
; Clobbers: d0-d6, a0-a6 (object code may clobber freely except a0/d7)
; -----------------------------------------------
RunObjects:
        moveq   #0, d0
        move.w  d0, (Spawn_Count).w

        tst.b   (Game_Paused).w
        bne.w   RunObjects_Frozen

        ; --- Player slots (always execute) ---
        lea     (Player_1).w, a0
        move.w  #NUM_PLAYERS-1, d7
        bsr.s   .run_always

        ; --- Dynamic slots (culled by distance) ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d7
        bsr.w   .run_culled

        ; --- System slots (always execute) ---
        lea     (System_Slots).w, a0
        move.w  #NUM_SYSTEM-1, d7
        bsr.s   .run_always

        ; --- Effect slots (always execute) ---
        lea     (Effect_Slots).w, a0
        move.w  #NUM_EFFECTS-1, d7
        bsr.s   .run_always
        rts

; Dispatch loop — no culling
.run_always:
.always_loop:
        moveq   #OBJ_CODE_BANK, d0
        swap    d0
        move.w  (a0), d0
        beq.s   .always_next
        movea.l d0, a1
        jsr     (a1)
        ; debug builds: catch object routines violating the a0/d7
        ; preservation contract at the source (caused the free-stack
        ; code-dispatch crash + intermittent RAM clobbers, 2026-06-10)
        ifdebug bsr.w Debug_AssertObjLoop
.always_next:
        lea     SST_len(a0), a0
        dbf     d7, .always_loop
        rts

; Dispatch loop — skip objects far from camera
.run_culled:
.culled_loop:
        tst.w   (a0)
        beq.s   .culled_next

        ; X distance check: abs(obj_x - camera_x)
        move.w  SST_x_pos(a0), d0
        sub.w   (Camera_X).w, d0
        bpl.s   .culled_xpos
        neg.w   d0
.culled_xpos:
        cmpi.w  #CULL_DISTANCE_X, d0
        bhi.s   .culled_next

        ; Y distance check: abs(obj_y - camera_y)
        move.w  SST_y_pos(a0), d0
        sub.w   (Camera_Y).w, d0
        bpl.s   .culled_ypos
        neg.w   d0
.culled_ypos:
        cmpi.w  #CULL_DISTANCE_Y, d0
        bhi.s   .culled_next

        ; Within range — dispatch
        moveq   #OBJ_CODE_BANK, d0
        swap    d0
        move.w  (a0), d0
        movea.l d0, a1
        jsr     (a1)
        ifdebug bsr.w Debug_AssertObjLoop
.culled_next:
        lea     SST_len(a0), a0
        dbf     d7, .culled_loop
        rts

    ifdef __DEBUG__
; -----------------------------------------------
; Debug_AssertObjLoop — verify the RunObjects loop contract after dispatch
; Object routines must return with a0 = own SST and d7 = loop counter
; intact. A violation here previously dispatched free-stack words as
; code offsets (intermittent RAM clobbers / ILLEGAL INSTRUCTION).
; In:  a0 = slot just dispatched, d7 = loop counter
; Out: none (raises debugger error on violation)
; Clobbers: none
; -----------------------------------------------
Debug_AssertObjLoop:
        assert.l a0, hs, #Object_RAM
        assert.l a0, lo, #Object_RAM_End
        assert.w d7, lo, #NUM_DYNAMIC
        rts
    endif

; -----------------------------------------------
; RunObjects_Frozen — render-only pass (player death, pause)
; Calls Draw_Sprite for each occupied slot, skips object logic
; In:  none
; Out: none
; Clobbers: d0-d6, a0-a6
; -----------------------------------------------
RunObjects_Frozen:
        lea     (Object_RAM).w, a0
        move.w  #NUM_TOTAL_SLOTS-1, d7
.loop:
        tst.w   (a0)
        beq.s   .next
        bsr.w   Draw_Sprite
.next:
        lea     SST_len(a0), a0
        dbf     d7, .loop
        rts

; -----------------------------------------------
; ObjectMove — apply velocity to position (X and Y)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMove:
        move.w  SST_x_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_x_pos(a0)
        move.w  SST_y_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_y_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveX — apply X velocity only
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveX:
        move.w  SST_x_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_x_pos(a0)
        rts

; -----------------------------------------------
; ObjectMoveY — apply Y velocity only (gravity, falling)
; In:  a0 = SST pointer
; Out: none
; Clobbers: d0
; -----------------------------------------------
ObjectMoveY:
        move.w  SST_y_vel(a0), d0
        ext.l   d0
        asl.l   #8, d0
        add.l   d0, SST_y_pos(a0)
        rts
