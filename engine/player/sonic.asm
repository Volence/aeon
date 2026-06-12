; Sonic — character data + per-character code (§5). Asset wiring, physics
; base table, DPLC immediates. Spindash + ability states arrive Task 8.

; -----------------------------------------------
; Sonic_InitAssets — point a player SST at Sonic's art set
; In:  a0 = player SST
; Out: none
; Clobbers: none
; -----------------------------------------------
Sonic_InitAssets:
        move.l  #Map_Sonic, SST_mappings(a0)
        move.w  #vram_art(VRAM_TEST_SONIC,0,0), SST_art_tile(a0)
        move.l  #Ani_Sonic, SST_anim_table(a0)
        rts

; -----------------------------------------------
; Sonic_LoadArt — DPLC stream + draw (the player display tail).
; DPLC table / art base are per-character code immediates, NOT SST
; fields (spec §3.2 — keeps 10 bytes of sst_custom headroom).
; In:  a0 = player SST (mapping_frame current)
; Out: none
; Clobbers: d0-d4, a1-a3 (a0/d7 preserved)
; -----------------------------------------------
Sonic_LoadArt:
        lea     (DPLC_Sonic).l, a2
        lea     (Art_Sonic).l, a3
        move.w  #vram_bytes(VRAM_TEST_SONIC), d1
        jsr     Perform_DPLC
        jmp     Draw_Sprite

; -----------------------------------------------
; Sonic's physics base table — block-copied into Player_Phys by
; Player_RefreshPhysics (the per-CHARACTER base row; section modifiers
; compose there later, NEVER per-frame). Field order is bound to the
; Player_Phys RAM layout (ram.asm) — the assert below enforces size.
; -----------------------------------------------
PhysTable_Sonic:
        dc.w    PHYS_ACCEL
        dc.w    PHYS_DECEL
        dc.w    PHYS_FRICTION
        dc.w    PHYS_TOP_SPEED
        dc.w    PHYS_GRAVITY
        dc.w    PHYS_JUMP_FORCE
        dc.w    PHYS_AIR_ACCEL
        dc.w    PHYS_JUMP_RELEASE_CAP
PhysTable_Sonic_End:
    if (PhysTable_Sonic_End-PhysTable_Sonic) <> (Player_Phys_End-Player_Phys)
      error "PhysTable_Sonic out of sync with Player_Phys layout"
    endif
