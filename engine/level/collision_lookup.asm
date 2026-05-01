; Collision lookup system (§4.7)
; Reads collision type from strip cache embedded bytes, then indexes
; into height map profiles and angle table for surface detection.
; Strip format: 128 bytes per column — bytes 0-95 nametable, 96-119 collision.

; -----------------------------------------------
; Collision_GetType — look up collision type for an engine-space position
; In:  d0.w = engine X pixel position (slot space, same domain as x_pos)
;      d1.w = Y pixel position
; Out: d0.b = collision type byte (0 = air)
; Clobbers: d0-d2, a0
; -----------------------------------------------
Collision_GetType:
        move.w  d1, d2                         ; save Y before Engine_To_World_Col clobbers d1
        lsr.w   #3, d0                         ; X pixels → tile col
        bsr.w   Engine_To_World_Col            ; d0.w = world tile col
        move.w  d2, d1                         ; restore Y

        cmp.w   (Strip_Cache_Left_Col).w, d0
        blt.s   .cgt_air
        cmp.w   (Strip_Cache_Head_Col).w, d0
        bgt.s   .cgt_air

        bsr.w   Strip_Cache_GetColumn          ; a0 = 128-byte strip

        lsr.w   #4, d1                         ; Y pixels → collision row (16px cells)
        cmpi.w  #STRIP_COLLISION_ROWS, d1
        bge.s   .cgt_air
        move.b  STRIP_COLLISION_OFFSET(a0,d1.w), d0
        rts

.cgt_air:
        moveq   #CTYPE_AIR, d0
        rts

; -----------------------------------------------
; Collision_GetFloorHeight — floor height at a specific position
; In:  d0.w = engine X pixel position
;      d1.w = Y pixel position
; Out: d0.w = signed floor distance (negative = above floor)
;      d1.b = surface angle
;      d2.b = collision type (0 = air)
; Clobbers: d0-d4, a0-a1
; -----------------------------------------------
Collision_GetFloorHeight:
        move.w  d0, d3                         ; save X
        move.w  d1, d4                         ; save Y
        bsr.w   Collision_GetType              ; d0.b = collision type
        move.b  d0, d2
        tst.b   d0
        beq.s   .cgf_air

        andi.w  #$FF, d0
        lsl.w   #4, d0                         ; type × 16
        move.w  d3, d1
        andi.w  #$F, d1                        ; sub-cell X (0-15)
        add.w   d1, d0
        lea     (HeightMaps).l, a1
        move.b  (a1, d0.w), d1                 ; height value (0-16)

        ext.w   d1                             ; d1 = height (0-16)
        move.w  d4, d0
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
; Out: d0.w = signed wall distance
;      d1.b = surface angle
;      d2.b = collision type (0 = air)
; Clobbers: d0-d4, a0-a1
; -----------------------------------------------
Collision_GetFloorHeight_Wall:
        move.w  d0, d3
        move.w  d1, d4
        bsr.w   Collision_GetType
        move.b  d0, d2
        tst.b   d0
        beq.s   .cgw_air

        andi.w  #$FF, d0
        lsl.w   #4, d0
        move.w  d4, d1                         ; sub-cell Y for rotated profiles
        andi.w  #$F, d1
        add.w   d1, d0
        lea     (HeightMapsRot).l, a1
        move.b  (a1, d0.w), d1

        ext.w   d1                             ; d1 = width (0-16)
        move.w  d3, d0
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
        move.w  SST_x_pos(a0), d3              ; engine X integer
        move.w  SST_y_pos(a0), d4              ; engine Y integer
        moveq   #0, d5
        move.b  SST_width_pixels(a0), d5
        lsr.w   #1, d5                         ; half width
        moveq   #0, d6
        move.b  SST_height_pixels(a0), d6
        lsr.w   #1, d6                         ; half height
        add.w   d6, d4                         ; foot Y = y + half_height

        ; left sensor
        move.w  d3, d0
        sub.w   d5, d0
        move.w  d4, d1
        movem.l d3-d6, -(sp)
        bsr.w   Collision_GetFloorHeight
        movem.l (sp)+, d3-d6
        move.w  d0, -(sp)                      ; left distance
        move.b  d1, -(sp)                      ; left angle
        move.b  d2, -(sp)                      ; left type

        ; right sensor
        move.w  d3, d0
        add.w   d5, d0
        move.w  d4, d1
        bsr.w   Collision_GetFloorHeight

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
