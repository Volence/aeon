; Plane B (background) drawing routines (§2 A.5)
;
; T1 (zone-wide):     BG_Init loads act_bg_tiles into the shared BG VRAM region
;                     (slots 1280-1535, $A000-$BFFF), then blits act_bg_layout
;                     into Plane B nametable. Both happen once at level load.
; T2/T3 (per-section): BG_RedrawForSection blits the section's sec_bg_layout on
;                      teleport. NULL sec_bg_layout = T1 fallback (no redraw).
;
; Layout shape: each nametable layout is a raw 64x32 = 4096 bytes.
; Tile-blob shape: 2-byte big-endian length header + raw deduped tile bytes
;   (mirrors S4LZ blob shape so engine can read length without a separate field).
; Decision rationale: docs/research/per-section-background.md (Q4 + Q5).

VRAM_PLANE_B_BYTES  = $E000             ; Plane B nametable VRAM byte address
BG_LAYOUT_SIZE      = 64*32*2           ; 4096 bytes (full Plane B nametable)

; -----------------------------------------------
; BG_Init — load shared BG tiles + blit Plane B nametable.
;
; In:  a0 = Act descriptor pointer
; Out: none
; Clobbers: d0, d1, a0–a2
;
; Display assumed off (called from Level_LoadArt, before display enable).
; Both writes are blocking via VDP DATA port; autoincrement = 2 bytes/word.
; -----------------------------------------------
BG_Init:
        movem.l a3, -(sp)
        movea.l a0, a3                  ; a3 = act ptr (preserve)

        ; --- load BG tile blob into shared region at BG_TILE_BASE_VRAM ---
        movea.l Act_act_bg_tiles(a3), a1
        cmpa.w  #0, a1
        beq.s   .skip_tiles
        move.w  (a1)+, d1               ; d1.w = tile-bytes length (uncompressed)
        beq.s   .skip_tiles
        stopZ80
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(BG_TILE_BASE_VRAM,VRAM,WRITE), (VDP_CTRL).l
        lea     (VDP_DATA).l, a2
        lsr.w   #1, d1                  ; word count = bytes/2
        subq.w  #1, d1
.tile_copy:
        move.w  (a1)+, (a2)
        dbf     d1, .tile_copy
        startZ80
.skip_tiles:

        ; --- blit BG nametable to Plane B ---
        movea.l Act_act_bg_layout(a3), a1
        cmpa.w  #0, a1
        beq.s   .skip_nt
        stopZ80
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l
        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0
.nt_copy:
        move.w  (a1)+, (a2)
        dbf     d0, .nt_copy
        startZ80
.skip_nt:
        movem.l (sp)+, a3
        rts

; -----------------------------------------------
; BG_RedrawForSection — replace Plane B nametable from a section's BG layout.
;
; In:  a0 = Sec ptr
; Out: none
; Clobbers: d0, a0–a2
;
; T1 (sec_bg_layout = NULL): no redraw — Plane B keeps the zone-wide content
; placed there by BG_Init at level load.
; T2/T3 (sec_bg_layout != NULL): blit the section's layout to Plane B.
;
; Per docs/research/per-section-background.md: layouts are full-coverage 64x32,
; so no pre-clear needed — the new data fully overwrites prior contents.
; -----------------------------------------------
BG_RedrawForSection:
        move.l  Sec_sec_bg_layout(a0), d0
        beq.s   .skip                   ; T1 — no per-section override
        movea.l d0, a1

        stopZ80
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l

        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0
.copy:
        move.w  (a1)+, (a2)
        dbf     d0, .copy
        startZ80
.skip:
        rts
