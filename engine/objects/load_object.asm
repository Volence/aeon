; Load_Object — data-driven object spawning from v2 archetype templates
;
; v2 Object definition format (ROM data block, 26 bytes):
;   +0:  dc.w  objroutine(Code)     ; code_addr
;   +2:  dc.w  x_vel, y_vel         ; $0A-$0D image
;   +6:  dc.b  render_flags, collision_resp  ; $0E-$0F image
;   +8:  dc.l  mappings             ; $10-$13 image
;   +12: dc.w  art_tile             ; $14-$15 image
;   +14: dc.b  width, height        ; $16-$17 image
;   +16: dc.b  anim, subtype        ; $18-$19 image
;   +18: dc.l  anim_table           ; $1A-$1D image
;   +22: dc.b  status, angle        ; $1E-$1F image
;   +24: dc.w  0                    ; $20-$21 pad (re-inited at spawn)
; Emitted by the objdef macro (macros.asm).

; -----------------------------------------------
; Load_Object — spawn one object from a v2 archetype template
; In:  a1 = ObjDef template (ROM, 26 bytes: code_addr.w + SST $0A-$21 image)
;      d0.w = X position (integer, engine coords)
;      d1.w = Y position (integer, engine coords)
;      d2.w = placement word: OEF flips in bits 13-14, subtype in low byte.
;             Direct spawns pass plain subtype (bits 13-15 clear).
; Out: Z set = success, a1 = new SST pointer
;      Z clear = allocation failed
; Clobbers: d0-d3, a1-a3
; -----------------------------------------------
Load_Object:
        movem.l d0-d2/a1, -(sp)
        jsr     AllocDynamic
        bne.w   .alloc_fail
        movem.l (sp)+, d0-d2/a2        ; a2 = template (saved a1), a1 = new SST
        move.l  d4, -(sp)              ; preserve d4 — caller (EntityWindow_TrySpawnObject) reads it after return

        ; --- burst copy: code_addr word + 24-byte template block ---
        move.w  (a2)+, SST_code_addr(a1)
        lea     SST_x_vel(a1), a3
        movem.l (a2)+, d3-d4
        movem.l d3-d4, (a3)            ; $0A-$11
        movem.l (a2)+, d3-d4
        movem.l d3-d4, 8(a3)           ; $12-$19
        movem.l (a2)+, d3-d4
        movem.l d3-d4, 16(a3)          ; $1A-$21 ($20-$21 re-inited below)

        ; --- per-placement patch ---
        swap    d0
        clr.w   d0
        move.l  d0, SST_x_pos(a1)
        swap    d1
        clr.w   d1
        move.l  d1, SST_y_pos(a1)
        move.b  d2, SST_subtype(a1)    ; placement subtype (low byte)
        move.w  d2, d3                 ; placement flips → render_flags + status
        rol.w   #4, d3                 ; bits 13/14 → RF_XFLIP(1)/RF_YFLIP(2)
        andi.b  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d3
        or.b    d3, SST_render_flags(a1)
        or.b    d3, SST_status(a1)

        ; --- runtime init ($20-$24: prev_anim $FF, frame/timer/mapframe 0, prev_frame $FF) ---
        move.l  #$FF000000, SST_prev_anim(a1)
        move.b  #$FF, SST_prev_frame(a1)

        ; --- initial sprite_piece_count from mappings frame 0 ---
        move.l  SST_mappings(a1), d3
        beq.s   .no_piece_count
        movea.l d3, a3
        move.w  (a3), d3                    ; offset to frame 0 data
        ; piece count is at FRAME_PIECE_COUNT (+4), after 4 bbox bytes
        move.w  FRAME_PIECE_COUNT(a3,d3.w), d3
        move.b  d3, SST_sprite_piece_count(a1)
.no_piece_count:
        move.l  (sp)+, d4
        moveq   #0, d0                 ; Z set = success
        rts

.alloc_fail:
        movem.l (sp)+, d0-d2/a1
        moveq   #1, d0                 ; Z clear = failed
        rts

; -----------------------------------------------
; Load_ObjectList — spawn objects from a definition list
;
; List format (10 bytes per entry, terminated by dc.l 0):
;   dc.l  ObjDef_XXX              ; definition pointer (0 = end)
;   dc.w  x_pos, y_pos            ; integer world coordinates
;   dc.w  subtype                  ; word for alignment (only low byte used;
;                                  ; bits 13-15 must be clear — v2 Load_Object
;                                  ; reads bits 13-14 as OEF flip flags)
;
; In:  a0 = object list pointer (ROM)
; Out: none (objects spawned, alloc failures silently skipped)
; Clobbers: d0-d3, a0-a2
; -----------------------------------------------
Load_ObjectList:
.loop:
        movea.l (a0)+, a1              ; a1 = definition pointer
        move.l  a1, d0
        beq.s   .done                  ; 0 = end of list
        move.w  (a0)+, d0              ; X position
        move.w  (a0)+, d1              ; Y position
        move.w  (a0)+, d2              ; subtype (low byte; bits 13-15 clear in sane list data)
        move.l  a0, -(sp)
        jsr     Load_Object
        movea.l (sp)+, a0
        bra.s   .loop
.done:
        rts
