; Plane B (background) drawing routines (§2 A.5)
;
; T1 (zone-wide):     BG_Init blits Act_act_bg_layout into Plane B once at level load.
; T2/T3 (per-section): BG_RedrawForSection blits the section's sec_bg_layout on
;                      teleport. NULL sec_bg_layout = T1 fallback (no redraw).
;
; Storage shape: each layout is a raw 64x32 nametable = 4096 bytes.
; Decision rationale: docs/research/per-section-background.md.

VRAM_PLANE_B_BYTES  = $E000             ; Plane B nametable VRAM byte address
BG_LAYOUT_SIZE      = 64*32*2           ; 4096 bytes (full Plane B nametable)

; -----------------------------------------------
; BG_Init — blit Act_act_bg_layout to Plane B nametable.
;
; In:  a0 = Act descriptor pointer
; Out: none
; Clobbers: d0, a0–a2
;
; Display assumed off (called from Level_LoadArt, before display enable).
; Writes 2048 nametable words via VDP DATA port; autoincrement = 2 bytes/word.
; -----------------------------------------------
BG_Init:
        movea.l Act_act_bg_layout(a0), a1
        cmpa.w  #0, a1
        beq.s   .skip                   ; no zone BG (defensive — shipping acts always set this)

        stopZ80                         ; required before VDP access
        ; -- set autoincrement = 2, then VDP write address to Plane B nametable --
        move.w  #$8F02, (VDP_CTRL).l
        move.l  #vdpComm(VRAM_PLANE_B_BYTES,VRAM,WRITE), (VDP_CTRL).l

        ; -- blit BG_LAYOUT_SIZE/2 words via VDP DATA port --
        lea     (VDP_DATA).l, a2
        move.w  #BG_LAYOUT_SIZE/2 - 1, d0
.copy:
        move.w  (a1)+, (a2)
        dbf     d0, .copy
        startZ80
.skip:
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
