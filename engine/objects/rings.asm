; Ring system — buffer ops, draw, collide
; §4.9 camera-driven entity window

    include "engine/objects/aabb.inc"

; -----------------------------------------------
; RingBuffer_Add — append a ring to the unified buffer
;
; In:  d0.w = engine-space X
;      d1.w = engine-space Y
;      d2.b = section_id
;      d3.b = list_index (index in section's ROM ring list)
; Out: carry clear = success, carry set = buffer full
; Side effects: updates Ring_HighWater (success path);
;               increments Ring_Add_Dropped + DEBUG-fatal assert (.full)
; Clobbers: d4, a0
; -----------------------------------------------
RingBuffer_Add:
        moveq   #0, d4
        move.b  (Ring_Count).w, d4
        cmpi.b  #MAX_RING_BUFFER, d4
        bhs.s   .full

        ; a0 = &Ring_Buffer[count * 6]
        move.w  d4, -(sp)
        add.w   d4, d4                  ; ×2
        add.w   (sp)+, d4               ; ×3
        add.w   d4, d4                  ; ×6
        lea     (Ring_Buffer).w, a0
        adda.w  d4, a0

        move.w  d0, (a0)+              ; engine_X
        move.w  d1, (a0)+              ; engine_Y
        move.b  d2, (a0)+              ; section_id
        move.b  d3, (a0)+              ; list_index

        addq.b  #1, (Ring_Count).w
        move.b  (Ring_Count).w, d4
        cmp.b   (Ring_HighWater).w, d4
        bls.s   .not_record
        move.b  d4, (Ring_HighWater).w
.not_record:
        andi.b  #$FE, ccr              ; clear carry
        rts

.full:
        addq.b  #1, (Ring_Add_Dropped).w
    ifdef __DEBUG__
        ; register comparand — the assert macro's message expansion can't
        ; take a parenthesised memory operand (assembles to error #1300)
        move.b  (Ring_Add_Dropped).w, d4        ; d4 = declared clobber
        assert.b d4, eq, #0                     ; drop = content bug, fatal in DEBUG
    endif
        ori.b   #1, ccr                ; set carry
        rts

; -----------------------------------------------
; RingBuffer_Remove — remove ring at index by swapping with last
;
; In:  d0.w = index to remove (0-based)
; Out: none
; Clobbers: d1-d2, a0-a1
; -----------------------------------------------
RingBuffer_Remove:
        moveq   #0, d1
        move.b  (Ring_Count).w, d1
        subq.b  #1, d1
        bmi.s   .done                   ; count was 0

        move.b  d1, (Ring_Count).w      ; decrement count

        cmp.w   d1, d0
        beq.s   .done                   ; removing last entry, nothing to swap

        ; dest = &Ring_Buffer[remove_index × 6]
        move.w  d0, d2
        add.w   d2, d2
        add.w   d0, d2
        add.w   d2, d2                  ; d2 = remove_index × 6
        lea     (Ring_Buffer).w, a0
        lea     (a0, d2.w), a0

        ; source = &Ring_Buffer[last_index × 6]
        move.w  d1, d2
        add.w   d2, d2
        add.w   d1, d2
        add.w   d2, d2                  ; d2 = last_index × 6
        lea     (Ring_Buffer).w, a1
        lea     (a1, d2.w), a1

        move.l  (a1)+, (a0)+           ; X + Y (4 bytes)
        move.w  (a1), (a0)             ; section_id + list_index (2 bytes)

.done:
        rts

; -----------------------------------------------
; RingBuffer_Clear — zero the ring count
; -----------------------------------------------
RingBuffer_Clear:
        clr.b   (Ring_Count).w
        clr.b   (Ring_HighWater).w
        clr.b   (Ring_Add_Dropped).w
        rts

; -----------------------------------------------
; DrawRings — render rings from unified buffer to sprite table
;
; In:  a4 = SAT buffer write pointer (from Render_Sprites)
;      d5.w = current VDP sprite count (from Render_Sprites)
; Out: a4 advanced past emitted ring sprites
;      d5 incremented per ring sprite emitted
; Clobbers: d0-d4, d6-d7, a0
; -----------------------------------------------
DrawRings:
        ; --- Animation timer ---
        move.b  (Ring_Anim_Timer).w, d0
        subq.b  #1, d0
        bpl.s   .no_anim_tick
        move.b  #RING_ANIM_SPEED-1, d0
        move.b  (Ring_Anim_Frame).w, d1
        addq.b  #1, d1
        cmpi.b  #RING_ANIM_FRAMES, d1
        blo.s   .frame_ok
        moveq   #0, d1
.frame_ok:
        move.b  d1, (Ring_Anim_Frame).w
.no_anim_tick:
        move.b  d0, (Ring_Anim_Timer).w

        ; Cache camera position
        move.w  (Camera_X).w, d6
        move.w  (Camera_Y).w, d7

        lea     (Ring_Buffer).w, a0
        moveq   #0, d1
        move.b  (Ring_Count).w, d1
        beq.s   .done
        subq.w  #1, d1                  ; dbf adjust

.ring_loop:
        cmpi.w  #MAX_VDP_SPRITES, d5
        bhs.s   .done

        ; On-screen culling — X
        move.w  (a0), d2                ; engine X
        sub.w   d6, d2                  ; screen X
        move.w  d2, d0
        addi.w  #16, d0
        cmpi.w  #336, d0               ; 320 + 16
        bhi.s   .skip_ring

        ; On-screen culling — Y
        move.w  2(a0), d3              ; engine Y
        sub.w   d7, d3                  ; screen Y
        move.w  d3, d0
        addi.w  #16, d0
        cmpi.w  #240, d0               ; 224 + 16
        bhi.s   .skip_ring

        ; --- Write SAT entry (8 bytes) ---
        subi.w  #8, d3
        addi.w  #VDP_SPRITE_Y_OFFSET, d3
        move.w  d3, (a4)+              ; +0: Y position
        move.b  #$05, (a4)+            ; +2: size 2×2 (16×16 px)
        addq.b  #1, d5
        move.b  d5, (a4)+              ; +3: link (next sprite index)
        move.w  #VRAM_RING_PLACEHOLDER, (a4)+  ; +4: tile attrs (placeholder ring art)
        subi.w  #8, d2
        addi.w  #VDP_SPRITE_X_OFFSET, d2
        bne.s   .x_ok
        moveq   #1, d2                 ; avoid X=0 (VDP sprite masking)
.x_ok:
        move.w  d2, (a4)+              ; +6: X position

.skip_ring:
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
        dbf     d1, .ring_loop

.done:
        rts

; -----------------------------------------------
; RingCollision — test player(s) vs rings in unified buffer
;
; Iterates backward so swap-with-last removal doesn't skip entries.
;
; In:  none (reads Player_1/2, Ring_Buffer, Ring_Count)
; Out: none
; Clobbers: d0-d7, a0-a3
; -----------------------------------------------
RingCollision:
        lea     (Player_1).w, a2
        move.w  #NUM_PLAYERS-1, d7

.player_loop:
        tst.w   SST_code_addr(a2)
        beq.w   .next_player

        move.w  SST_x_pos(a2), d4       ; cache player X
        move.w  SST_y_pos(a2), d5       ; cache player Y

        ; Iterate backward: index = Ring_Count - 1 down to 0
        moveq   #0, d6
        move.b  (Ring_Count).w, d6
        subq.w  #1, d6
        bmi.s   .next_player            ; no rings

.ring_loop:
        ; Compute buffer pointer: a0 = &Ring_Buffer[d6 * 6]
        move.w  d6, d0
        add.w   d0, d0
        add.w   d6, d0
        add.w   d0, d0                  ; d0 = d6 × 6
        lea     (Ring_Buffer).w, a0
        lea     (a0, d0.w), a0

        ; X axis: player width vs ring 16px
        moveq   #0, d0
        move.b  SST_width_pixels(a2), d0
        moveq   #RING_WIDTH, d1

        aabb_axis_test d4,(a0),d0,d1,d0,d1,d2,.no_hit,rx

        ; Y axis: player height vs ring 16px
        moveq   #0, d0
        move.b  SST_height_pixels(a2), d0
        moveq   #RING_HEIGHT, d1

        aabb_axis_test d5,2(a0),d0,d1,d0,d1,d2,.no_hit,ry

        ; Overlap — collect this ring
        ; a0 points to ring entry: +4 = section_id, +5 = list_index
        move.b  4(a0), d2               ; section_id
        move.b  5(a0), d3               ; list_index
        bsr.w   Collected_MarkRing      ; clobbers d0-d1, a0 — d2/d3 survive

        ; Clear the loaded bit too — keeps ring bits == buffer census.
        ; (Collected bit already blocks respawn; this is mask hygiene.)
        move.b  d2, d0                  ; section_id
        bsr.w   EntityWindow_EntryForSection
        tst.w   d0
        bmi.s   .no_loaded_bit          ; section untracked — no loaded bits
        moveq   #0, d1
        move.b  d3, d1                  ; list_index
        moveq   #0, d2                  ; ring bits
        bsr.w   EntityLoaded_Clear
.no_loaded_bit:

        addq.w  #1, (Ring_Counter).w
      ifdef SOUND_DRIVER_ENABLED
        bsr.w   Sound_PlayRing                  ; L/R-alternating ring SFX ($33/$34)
      endif

        ; Remove from buffer (swap-with-last)
        move.w  d6, d0
        bsr.w   RingBuffer_Remove

.no_hit:
        dbf     d6, .ring_loop

.next_player:
        lea     SST_len(a2), a2
        dbf     d7, .player_loop
        rts
