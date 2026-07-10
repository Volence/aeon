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
; Clobbers: d0-d3, a0 (d2/a0 via the Tile_Cache_GetCollision tail call)
; -----------------------------------------------
Collision_GetType:
        lsr.w   #3, d0                         ; X pixels → world tile col
        cmp.w   (Cache_Left_Col).w, d0
        blt.s   .cgt_air
        cmp.w   (Cache_Head_Col).w, d0
        bgt.s   .cgt_air
        lsr.w   #3, d1                         ; Y pixels → world tile row, in place
        cmp.w   (Cache_Top_Row).w, d1
        blt.s   .cgt_air
        cmp.w   (Cache_Bottom_Row).w, d1
        bgt.s   .cgt_air

        ; d0 = world col, d1 = world row
        ; d3.b = layer (0/1) — passed through from caller to Tile_Cache_GetCollision
        bra.w   Tile_Cache_GetCollision        ; tail call — d0.b = collision type

.cgt_air:
        moveq   #CTYPE_AIR, d0
        rts
