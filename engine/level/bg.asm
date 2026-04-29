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
; BG_RedrawForSection — queue Plane B nametable replacement via DMA queue (§4.2).
;
; In:  a0 = Sec ptr, a2 = Act ptr (for T1 fallback to act_bg_layout)
; Out: none (silently no-ops if no BG layout available)
; Clobbers: d0–d4, a1–a2 (per QueueDMA_Important contract)
;
; §4.2 change: previously this routine did a 4096-byte VDP-direct poke during
; active display, producing a top-down tear visible at every section transition.
; New behaviour: queue an Important-tier DMA. The transfer drains during VBlank
; only — no active-display tear, by construction.
;
; T1 (sec_bg_layout = NULL): fall back to act-level zone BG.
; T2/T3 (sec_bg_layout != NULL): use the section's layout.
;
; Layouts are full-coverage 64x32 (4096 bytes); the DMA fully overwrites prior
; contents, so no pre-clear is needed.
; -----------------------------------------------
BG_RedrawForSection:
        move.l  Sec_sec_bg_layout(a0), d0
        bne.s   .have_layout
        move.l  Act_act_bg_layout(a2), d0
        beq.s   .skip                       ; no BG at all → nothing to do
.have_layout:
        move.l  d0, d1                      ; d1.l = source ROM addr
        move.w  #VRAM_PLANE_B_BYTES, d2     ; d2.w = dest VRAM byte addr
        move.w  #BG_LAYOUT_SIZE, d3         ; d3.w = transfer length (4096 bytes)
        bra.w   QueueDMA_Important
.skip:
        rts
