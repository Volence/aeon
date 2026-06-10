; Collision lookup system (§4.7)
; Reads collision type from 2D tile cache, then indexes
; into height map profiles and angle table for surface detection.

; -----------------------------------------------
; Collision_GetType — look up collision type for an engine-space position
; In:  d0.w = engine X pixel position (slot space, same domain as x_pos)
;      d1.w = Y pixel position
;      d3.b = layer select (0 = path A, 1 = path B)
; Out: d0.b = collision type byte (0 = air)
; Clobbers: d0-d3, a0
; -----------------------------------------------
Collision_GetType:
        move.w  d1, d2                         ; save Y
        lsr.w   #3, d0                         ; X pixels → tile col
        bsr.w   Engine_To_World_Col            ; d0.w = world tile col (clobbers d1)
        cmp.w   (Cache_Left_Col).w, d0
        blt.s   .cgt_air
        cmp.w   (Cache_Head_Col).w, d0
        bgt.s   .cgt_air
        move.w  d0, -(sp)                     ; push world col

        move.w  d2, d0
        lsr.w   #3, d0                         ; Y pixels → tile row
        bsr.w   Engine_To_World_Row            ; d0.w = world tile row (clobbers d1)
        move.w  d0, d1                         ; d1 = world row
        cmp.w   (Cache_Top_Row).w, d1
        blt.s   .cgt_air_pop
        cmp.w   (Cache_Bottom_Row).w, d1
        bgt.s   .cgt_air_pop

        move.w  (sp)+, d0                      ; d0 = world col, d1 = world row
        ; d3.b = layer (0/1) — passed through from caller to Tile_Cache_GetCollision
        bsr.w   Tile_Cache_GetCollision        ; d0.b = collision type
        rts

.cgt_air_pop:
        addq.l  #2, sp
.cgt_air:
        moveq   #CTYPE_AIR, d0
        rts

; -----------------------------------------------
; Collision_GetFloorHeight — floor height at a specific position
; In:  d0.w = engine X pixel position
;      d1.w = Y pixel position
;      d3.b = layer select (0 = path A, 1 = path B)
; Out: d0.w = signed floor distance (negative = above floor)
;      d1.b = surface angle
;      d2.b = collision type (0 = air)
; Clobbers: d0-d5, a0-a1
; Note: d3.b (layer) must survive until the bsr to Collision_GetType.
;       X is saved in d4, Y in d5 (instead of d3/d4) to leave d3 free for layer.
; -----------------------------------------------
Collision_GetFloorHeight:
        move.w  d0, d4                         ; save X
        move.w  d1, d5                         ; save Y
        bsr.w   Collision_GetType              ; d0.b = collision type (d3.b = layer threaded in)
        move.b  d0, d2
        tst.b   d0
        beq.s   .cgf_air

        andi.w  #$FF, d0
        lsl.w   #4, d0                         ; type × 16
        move.w  d4, d1
        andi.w  #$F, d1                        ; sub-cell X (0-15)
        add.w   d1, d0
        lea     (HeightMaps).l, a1
        move.b  (a1, d0.w), d1                 ; height value (0-16)

        ext.w   d1                             ; d1 = height (0-16)
        move.w  d5, d0
        andi.w  #$F, d0                        ; sub-cell Y (0-15)
        add.w   d0, d1                         ; d1 = height + sub_cell_Y
        moveq   #16, d0
        sub.w   d1, d0                         ; d0 = 16 - height - sub_cell_Y

        moveq   #0, d1
        move.b  d2, d1
        lea     (AngleTable).l, a1
        move.b  (a1, d1.w), d1                 ; surface angle
        rts

.cgf_air:
        moveq   #$7F, d0
        moveq   #0, d1
        rts

; -----------------------------------------------
; Collision_GetFloorHeight_Wall — wall sensor height (rotated profiles)
; In:  d0.w = engine X pixel position
;      d1.w = Y pixel position
;      d3.b = layer select (0 = path A, 1 = path B)
; Out: d0.w = signed wall distance
;      d1.b = surface angle
;      d2.b = collision type (0 = air)
; Clobbers: d0-d5, a0-a1
; Note: X saved to d4, Y saved to d5 (d3 reserved for layer, same convention as GetFloorHeight).
; -----------------------------------------------
Collision_GetFloorHeight_Wall:
        move.w  d0, d4                         ; save X
        move.w  d1, d5                         ; save Y
        bsr.w   Collision_GetType              ; d3.b = layer threaded in
        move.b  d0, d2
        tst.b   d0
        beq.s   .cgw_air

        andi.w  #$FF, d0
        lsl.w   #4, d0
        move.w  d5, d1                         ; sub-cell Y for rotated profiles
        andi.w  #$F, d1
        add.w   d1, d0
        lea     (HeightMapsRot).l, a1
        move.b  (a1, d0.w), d1

        ext.w   d1                             ; d1 = width (0-16)
        move.w  d4, d0
        andi.w  #$F, d0                        ; sub-cell X (0-15)
        add.w   d0, d1                         ; d1 = width + sub_cell_X
        moveq   #16, d0
        sub.w   d1, d0                         ; d0 = 16 - width - sub_cell_X

        moveq   #0, d1
        move.b  d2, d1
        lea     (AngleTable).l, a1
        move.b  (a1, d1.w), d1
        rts

.cgw_air:
        moveq   #$7F, d0
        moveq   #0, d1
        rts

; -----------------------------------------------
; Collision_FloorSensors — dual floor sensor query
; In:  a0 = SST pointer (player object)
; Out: d0.w = floor distance (from closer sensor)
;      d1.b = surface angle
;      d2.b = collision type
; Clobbers: d0-d6, a0-a1
; -----------------------------------------------
Collision_FloorSensors:
        moveq   #0, d3
        move.b  SST_layer(a0), d3              ; d3.b = layer (0=path A, 1=path B)
        move.w  SST_x_pos(a0), d4             ; engine X integer (was d3, shifted to d4)
        move.w  SST_y_pos(a0), d5             ; engine Y integer (was d4, shifted to d5)
        moveq   #0, d6
        move.b  SST_width_pixels(a0), d6
        lsr.w   #1, d6                         ; half width (was d5, shifted to d6)
        moveq   #0, d7
        move.b  SST_height_pixels(a0), d7
        lsr.w   #1, d7                         ; half height
        add.w   d7, d5                         ; foot Y = y + half_height

        ; left sensor: d3.b = layer is preserved across movem push/pop
        move.w  d4, d0
        sub.w   d6, d0
        move.w  d5, d1
        movem.l d3-d7, -(sp)
        bsr.w   Collision_GetFloorHeight       ; d3.b = layer threaded in
        movem.l (sp)+, d3-d7
        move.w  d0, -(sp)                      ; left distance
        move.b  d1, -(sp)                      ; left angle
        move.b  d2, -(sp)                      ; left type

        ; right sensor
        move.w  d4, d0
        add.w   d6, d0
        move.w  d5, d1
        bsr.w   Collision_GetFloorHeight       ; d3.b = layer still valid

        ; pick closer sensor
        move.b  (sp)+, d5                      ; left type
        move.b  (sp)+, d4                      ; left angle
        move.w  (sp)+, d3                      ; left distance

        cmp.w   d3, d0
        ble.s   .cfs_right_wins
        move.w  d3, d0
        move.b  d4, d1
        move.b  d5, d2
.cfs_right_wins:
        rts
