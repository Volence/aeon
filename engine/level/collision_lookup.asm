; Collision lookup (§4.7) — collision attr byte from the 2D tile cache.
; Surface probing (heights/angles/solidity) lives in
; engine/player/player_sensors.asm, built on top of this lookup.
;
; REGISTER CONVENTION (all sensor entry points): d3.b = collision layer
; (0 = path A, 1 = path B — read from the querying object's SST_layer).
; Saved X/Y live in d4/d5. Set d3 before EVERY call — it is not
; preserved by contract. New sensor wrappers (§5) must follow this.

; -----------------------------------------------
; Collision_GetType — look up collision type for a world-space position
; In:  d0.w = world X pixel position (same domain as x_pos)
;      d1.w = world Y pixel position
;      d3.b = layer select (0 = path A, 1 = path B)
; Out: d0.b = collision type byte (0 = air)
; Clobbers: d0-d3, a0
; -----------------------------------------------
Collision_GetType:
        move.w  d1, d2                         ; save Y
        lsr.w   #3, d0                         ; X pixels → world tile col
        cmp.w   (Cache_Left_Col).w, d0
        blt.s   .cgt_air
        cmp.w   (Cache_Head_Col).w, d0
        bgt.s   .cgt_air
        move.w  d0, -(sp)                     ; push world col

        move.w  d2, d0
        lsr.w   #3, d0                         ; Y pixels → world tile row
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
