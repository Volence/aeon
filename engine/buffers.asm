; Buffer initialization, static DMA entries, and plane utilities

; -----------------------------------------------
; Init_SpriteTable — pre-init sprite link chain 0->1->2->...->79->0
; Y positions = 0 (off-screen), size = 0, tiles = 0
; In:  none
; Out: none
; Clobbers: d0-d2, a0
; -----------------------------------------------
Init_SpriteTable:
        lea     (Sprite_Table_Buffer).w, a0
        moveq   #0, d0
        moveq   #1, d1
        moveq   #79-1, d2
.loop:
        move.w  d0, (a0)+                      ; Y = 0
        move.b  d0, (a0)+                      ; size = 0
        move.b  d1, (a0)+                      ; link -> next
        move.l  d0, (a0)+                      ; tile = 0, X = 0
        addq.b  #1, d1
        dbf     d2, .loop
        move.w  d0, (a0)+                      ; entry 79: Y = 0
        move.b  d0, (a0)+                      ; size = 0
        move.b  d0, (a0)+                      ; link = 0 (terminate)
        move.l  d0, (a0)+                      ; tile = 0, X = 0
        rts

; -----------------------------------------------
; BuildStaticDMA — pre-compute the 5 static DMA entries
; (4 palette lines + 1 sprite table)
; Called once at boot after Init_DMA_Queue.
; In:  none
; Out: none
; Clobbers: d0-d3, d5, a0
; -----------------------------------------------
BuildStaticDMA:
        moveq   #-$6C, d0                      ; $94 sign-extended
        move.l  #$93979695, d5

        ; Palette line 0: Palette_Buffer+$00 -> CRAM $0000, 32 bytes
        lea     (Static_Pal_Line0).w, a0
        move.l  #dmaSource(Palette_Buffer), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm(0, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 1: Palette_Buffer+$20 -> CRAM $0020, 32 bytes
        lea     (Static_Pal_Line1).w, a0
        move.l  #dmaSource(Palette_Buffer+$20), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($20, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 2: Palette_Buffer+$40 -> CRAM $0040, 32 bytes
        lea     (Static_Pal_Line2).w, a0
        move.l  #dmaSource(Palette_Buffer+$40), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($40, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Palette line 3: Palette_Buffer+$60 -> CRAM $0060, 32 bytes
        lea     (Static_Pal_Line3).w, a0
        move.l  #dmaSource(Palette_Buffer+$60), d1
        move.w  #dmaLength(32), d3
        move.l  #vdpComm($60, CRAM, DMA), d2
        bsr.s   .build_entry

        ; Sprite table: Sprite_Table_Buffer -> VRAM $D800, 640 bytes
        lea     (Static_Sprite_DMA).w, a0
        move.l  #dmaSource(Sprite_Table_Buffer), d1
        move.w  #dmaLength(640), d3
        move.l  #vdpComm(VRAM_SPRITE_TABLE, VRAM, DMA), d2

.build_entry:
        move.b  d0, DMAEntry_Reg94(a0)
        movep.l d5, DMAEntry_Reg93(a0)
        movep.l d1, DMAEntry_SizeL(a0)          ; source -> offsets 3,5,7,9
        movep.w d3, DMAEntry_SizeH(a0)          ; length -> offsets 1,3
        move.l  d2, DMAEntry_Command(a0)
        rts

; -----------------------------------------------
; PlaneMapToVRAM — CPU-based row-by-row nametable writer
; For one-shot plane loads (title screens, menus, level init).
; Use during display-off or VBlank only.
; In:  a1   = source nametable data (VDP-ready words)
;      d0.l = VDP write command for top-left cell
;      d1.w = width in cells - 1
;      d2.w = height in rows - 1
; Out: none
; Clobbers: d0-d4, a1, a5-a6
; -----------------------------------------------
PlaneMapToVRAM:
        move.l  #vdpCommDelta(planeLoc(PLANE_H_CELLS,0,1)), d4
        lea     (VDP_DATA).l, a6
        lea     VDP_CTRL-VDP_DATA(a6), a5
.row:
        move.l  d0, (a5)                        ; set VRAM write address
        move.w  d1, d3
.cell:
        move.w  (a1)+, (a6)                     ; write one nametable word
        dbf     d3, .cell
        add.l   d4, d0                          ; advance to next row
        dbf     d2, .row
        rts

; -----------------------------------------------
; Enqueue_Dirty_Buffers — enqueue dirty palette lines and sprite table
; Called from VBlank handlers (Z80 already stopped).
; In:  none
; Out: none
; Clobbers: d0, a1-a2 (d0 zeroed as side effect)
; -----------------------------------------------
Enqueue_Dirty_Buffers:
        move.b  (Palette_Dirty).w, d0
        beq.w   .no_pal
        btst    #0, d0
        beq.s   .skip_pal0
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line0
.skip_pal0:
        btst    #1, d0
        beq.s   .skip_pal1
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line1
.skip_pal1:
        btst    #2, d0
        beq.s   .skip_pal2
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line2
.skip_pal2:
        btst    #3, d0
        beq.s   .skip_pal3
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Pal_Line3
.skip_pal3:
        moveq   #0, d0
        move.b  d0, (Palette_Dirty).w
.no_pal:
        tst.b   (Sprite_Table_Dirty).w
        beq.s   .no_spr
        queueStaticDMA DMA_Critical_Slot, DMA_Critical_End, Static_Sprite_DMA
        move.b  d0, (Sprite_Table_Dirty).w
.no_spr:
        rts
