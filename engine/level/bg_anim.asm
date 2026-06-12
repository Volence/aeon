; -----------------------------------------------
; BgAnim — driver-keyed BG tile-band animation (HCZ-pillar technique,
; modeled on S3K's AnimateTiles_HCZ2). Table-driven: up to
; BGANIM_MAX_BANDS independent animated strips per act.
;
; Each band is a horizontally-periodic pattern held in a contiguous
; range of BG tile slots, column-major (a pattern column's tiles are
; contiguous in VRAM). The engine translates the pattern by 1 pixel
; per (1 << rate_shift) units of the band's driver value:
;   fine  (step & 7)  — selects one of 8 art banks pre-shifted 1px each
;   coarse (step >> 3) — whole-column rotation done by splitting the
;                        bank DMA into two wrapped pieces (S3K's
;                        word_27AB8 trick), no extra art needed
; Composite rule: art layers inside the banks whose x-period divides
; 8px are invariant under the rotation and stay glued to the plane
; (or may slide at an integer px/step rate within their own wrap);
; non-periodic layers translate at the full step rate.
;
; BgAnim_Table is emitted by tools/inject_editor_bg.py into the act
; data block (runtime-read — act data assembles after engine code,
; so nothing here may conditionally assemble on its symbols).
;
; Table format:
;   dc.w band_count                      (0 = system disabled)
;   then per band, a 44-byte record:
;   $00 dc.w driver       0 = Camera_X, 1 = Camera_Y, 2 = Frame_Counter
;   $02 dc.w rate_shift   step = driver_value >> rate_shift
;   $04 dc.w step_mask    pattern width in px, minus 1
;   $06 dc.w col_shift    log2 of column stride in bytes (rows*32)
;   $08 dc.w tile_count
;   $0A dc.w vram_dest    VRAM byte address of the band's first slot
;   $0C dc.l bank0..bank7 pre-shifted art, 1px per bank
; -----------------------------------------------

BGANIM_MAX_BANDS = 4

; -----------------------------------------------
; BgAnim_Init — force a bank DMA on each band's first Update.
; In: none. Clobbers: d0
; -----------------------------------------------
BgAnim_Init:
        moveq   #-1, d0
        move.l  d0, (BgAnim_LastStep).w
        move.l  d0, (BgAnim_LastStep+4).w
        rts

; -----------------------------------------------
; BgAnim_Update — call once per frame from the main loop (after
; Parallax_Update). Per changed band, queues one or two deferrable
; DMAs (tile_count*32 bytes total).
; In: none. Clobbers: d0-d7, a1-a4
; -----------------------------------------------
BgAnim_Update:
        movem.l a3-a4, -(sp)
        lea     (BgAnim_Table).l, a3
        lea     (BgAnim_LastStep).w, a4
        move.w  (a3)+, d7                       ; band count
        beq.w   .exit
        subq.w  #1, d7
.band_loop:
        ; -- step = (driver value >> rate_shift) & step_mask --
        move.w  (a3)+, d0                       ; driver select
        beq.s   .cam_x
        subq.w  #1, d0
        beq.s   .cam_y
        move.w  (Frame_Counter).w, d0
        bra.s   .have_value
.cam_x:
        move.w  (Camera_X).w, d0                ; integer px (16.16 high word)
        bra.s   .have_value
.cam_y:
        move.w  (Camera_Y).w, d0
.have_value:
        move.w  (a3)+, d1                       ; rate_shift
        lsr.w   d1, d0
        and.w   (a3)+, d0                       ; step_mask
        cmp.w   (a4), d0
        beq.s   .skip_band                      ; unchanged this frame
        move.w  d0, d5                          ; d5 = step (commit on success)

        ; -- fine phase: bank pointer (record offset: banks at a3+6) --
        move.w  d0, d1
        and.w   #7, d1
        add.w   d1, d1
        add.w   d1, d1
        move.l  6(a3,d1.w), d6                  ; d6 = bank base

        ; -- coarse: whole-column rotation in bytes --
        lsr.w   #3, d0
        move.w  (a3)+, d1                       ; col_shift
        lsl.w   d1, d0                          ; d0 = shift bytes
        move.w  (a3)+, d3                       ; tile_count
        lsl.w   #5, d3                          ; total bytes
        move.w  (a3)+, d2                       ; vram dest
        sub.w   d0, d3                          ; d3 = piece 1 length (> 0)
        move.w  d0, -(sp)                       ; piece 2 length (= shift bytes)
        move.w  d2, -(sp)                       ; dest base
        move.w  d3, -(sp)                       ; piece 1 length

        ; -- DMA 1: art columns coarse..end -> band base --
        moveq   #0, d1
        move.w  d0, d1
        add.l   d6, d1                          ; src = bank + shift bytes
        jsr     QueueDMA_Deferrable
        bcs.s   .queue_full                     ; full — retry next frame

        ; -- DMA 2: art columns 0..coarse-1 -> base + piece 1 (wrap) --
        move.w  (sp)+, d4                       ; piece 1 length
        move.w  (sp)+, d2                       ; dest base
        move.w  (sp)+, d3                       ; piece 2 length
        beq.s   .commit                         ; no rotation this step
        add.w   d4, d2
        move.l  d6, d1
        jsr     QueueDMA_Deferrable
        bcs.s   .next_band                      ; partial — redo both next frame
.commit:
        move.w  d5, (a4)
        bra.s   .next_band
; ---------------------------------------------------------------
.queue_full:
        addq.w  #6, sp
        bra.s   .next_band
.skip_band:
        addq.w  #6, a3                          ; col_shift + count + dest
.next_band:
        lea     32(a3), a3                      ; past the 8 bank pointers
        addq.w  #2, a4
        dbf     d7, .band_loop
.exit:
        movem.l (sp)+, a3-a4
        rts
