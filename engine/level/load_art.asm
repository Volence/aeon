; Level art loader (§2 Phase 2 A.1/A.2/A.3)
; Blocking decompress → DMA pipeline. A.3 reorganized loading around
; per-section pools (graph-colored) instead of global region pools.

; -----------------------------------------------
; Art_Decompress — version-dispatched blocking art decompressor.
;
; Every compressed art blob starts with the 4-byte wrapper
; [u16 BE uncompressed size][u8 flags][u8 version]:
;   version 1 (ART_VER_S4LZ) → S4LZ_Decompress (parses the wrapper itself)
;   version 2 (ART_VER_ZX0)  → ZX0_Decompress (wrapper skipped here)
; Callers must skip size-0 blobs BEFORE calling (empty stubs carry no
; decodable stream).
;
; In:  a0 = source ROM pointer (wrapper at start, word-aligned)
;      a1 = destination buffer
; Out: a0 = past end of compressed data
;      a1 = past end of decompressed data (S4LZ: see its odd-size note)
; Clobbers: d0–d3, a2–a3 (S4LZ path; ZX0 path only d0–d1)
;           a4/d4 untouched on both paths — callers keep them live
; -----------------------------------------------
Art_Decompress:
        cmpi.b  #ART_VER_ZX0, ART_HDR_VERSION(a0)
        beq.s   .zx0
        bra.w   S4LZ_Decompress                     ; v3 reads its own wrapper
.zx0:
        addq.l  #ART_HDR_SIZE, a0                   ; ZX0 stream starts past wrapper
        bra.w   ZX0_Decompress

; -----------------------------------------------
; LoadArt_Compressed — decompress an art blob and queue Critical DMA to VRAM.
;
; In:  a0 = source ROM pointer (wrapped art blob, word-aligned)
;      d0.w = VRAM byte destination (tile-slot * 32)
; Out: a0 = past end of compressed data (returned from Art_Decompress)
; Clobbers: d0–d3, a0–a3
;
; Uses Decomp_Buffer (32 KB transient at $FFFF0000). For loads exceeding
; one VBlank's DMA budget, the caller is responsible for running with
; the display blanked off so multiple Critical DMAs can drain across one
; extended VBlank.
; -----------------------------------------------
LoadArt_Compressed:
        movem.l d4-d6/a4, -(sp)
        move.w  d0, d6                              ; d6.w = VRAM dest
        movea.l a0, a4                              ; a4 = saved source ptr (size peek)
        move.w  (a4), d4                            ; d4.w = uncompressed size (BE)

        ; -- skip the entire decompress + DMA if size is zero (placeholder blob) --
        beq.s   .return

        lea     (Decomp_Buffer).l, a1               ; a1 = work buffer
        bsr.s   Art_Decompress                      ; decompress; a0 advances past stream

        move.l  #Decomp_Buffer, d1                  ; d1 = source (RAM, $FFFF0000)
        moveq   #0, d2
        move.w  d6, d2                              ; d2.w = VRAM dest
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical
        bsr.w   VSync_Wait

.return:
        movem.l (sp)+, d4-d6/a4
        rts

; -----------------------------------------------
; Section_LoadArt — load one section's tile art group.
;
; In:  a0 = Sec struct pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: each section has its own compressed art blob and VRAM dest.
; Sections in the same color class overlay each other in VRAM as the
; camera traverses; the leapfrog system guarantees that the two
; currently-resident slots hold ADJACENT sections, which by graph-
; coloring construction are in DIFFERENT colors → DIFFERENT VRAM ranges,
; so both render correctly simultaneously.
; -----------------------------------------------
Section_LoadArt:
        moveq   #0, d0
        move.w  Sec_sec_tile_art_vram(a0), d0       ; d0.w = VRAM byte dest
        movea.l Sec_sec_tile_art(a0), a0            ; a0 = compressed art source
        cmpa.w  #0, a0
        beq.s   .skip                               ; null pointer → no art for this section
        bra.w   LoadArt_Compressed                  ; tail call
.skip:
        rts

; -----------------------------------------------
; Level_LoadArt — load tile art for both initial slot sections.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d4, a0–a4
;
; A.3 behaviour: walks the slot section map and calls Section_LoadArt
; for each slot's currently-assigned section. At Section_Init time, both
; slots hold the starting section + its right neighbor (per leapfrog
; convention).
; -----------------------------------------------
Level_LoadArt:
        ; A.4 fix: read section IDs from act descriptor directly, NOT from
        ; Slot_Section_Map. Test state calls Level_LoadArt BEFORE Section_Init,
        ; so Slot_Section_Map is uninitialized at this point.
        ; LoadArt_Compressed saves/restores a4 internally, so a4 survives across
        ; nested calls — we use it to keep act ptr.
        move.l  a4, -(sp)                           ; save caller's a4
        movea.l a0, a4                              ; a4 = act ptr

        ; -- flat start id = start_sec_y * grid_w + start_sec_x.
        ;    Computed from the act descriptor (NOT Section_SlotFlatID):
        ;    this runs before Section_Init, so Current_Act_Ptr and
        ;    Slot_Section_Map are not valid yet. --
        moveq   #0, d6
        move.b  Act_start_sec_y(a4), d6
        beq.s   .flat_add_x
        move.w  d6, d0
        moveq   #0, d6
        subq.w  #1, d0
.flat_mul:
        add.w   Act_grid_w(a4), d6
        dbf     d0, .flat_mul
.flat_add_x:
        moveq   #0, d0
        move.b  Act_start_sec_x(a4), d0
        add.w   d0, d6                              ; d6 = flat start section_id

        ; -- slot 0 = start section --
        bsr.w   .compute_sec_ptr                    ; a0 = Sec ptr (from d6)
        bsr.w   Section_LoadArt                     ; clobbers a0/d0-d4; d6/a4 preserved
        lea     (Section_Stream_State).w, a1
        move.b  #SS_RESIDENT, (a1, d6.w)

        ; -- slot 1 = start + 1, same row (skip if at grid edge) --
        moveq   #0, d0
        move.b  Act_start_sec_x(a4), d0
        addq.b  #1, d0
        cmp.b   Act_grid_w+1(a4), d0
        bge.s   .skip_slot1
        addq.w  #1, d6                              ; right neighbor = flat id + 1
        bsr.w   .compute_sec_ptr                    ; a0 = Sec ptr
        bsr.w   Section_LoadArt
        lea     (Section_Stream_State).w, a1
        move.b  #SS_RESIDENT, (a1, d6.w)

.skip_slot1:
        ; -- §2 A.5: blit zone-wide BG to Plane B nametable (T1) --
        movea.l a4, a0                              ; a0 = act ptr
        bsr.w   BG_Init

        movea.l (sp)+, a4                           ; restore caller's a4
        rts

.compute_sec_ptr:
        ; In:  d6.w = flat section_id, a4 = act ptr
        ; Out: a0 = Sec ptr for that section
        ; Clobbers: d0-d1, a0
        movea.l Act_sec_grid_ptr(a4), a0
        moveq   #0, d0
        move.b  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0                              ; sec × 64
        lsl.w   #3, d1                              ; sec × 8
        add.w   d1, d0                              ; sec × 72 = Sec_len
        adda.w  d0, a0
        rts

; -----------------------------------------------
; Section_StreamArtGroup — preload one section's tile art via Deferrable DMA.
;
; In:  a0 = Sec struct pointer
;      a4 = Sec struct pointer (preserved copy; Art_Decompress clobbers a0)
;      d6.w = flat section_id (sec_y * grid_w + sec_x), used to index
;             Section_Stream_State
; Out: none
; Clobbers: d0–d4, a0–a3
;
; State machine:
;   SS_IDLE      → decompress to next streaming buffer (round-robin A/B),
;                  queue Deferrable DMA, mark SS_STREAMING.
;   SS_STREAMING → no-op (already in-flight)
;   SS_RESIDENT  → no-op (already in VRAM)
;
; A.4 model: run-to-completion decompress + queued Deferrable DMA.
; The queue drains across upcoming VBlanks. By the time camera reaches
; the teleport threshold (~85-170 frames after preload), tiles are in VRAM.
; -----------------------------------------------
Section_StreamArtGroup:
        ; -- check current state --
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0
        cmpi.b  #SS_IDLE, d0
        bne.s   .skip                               ; already STREAMING or RESIDENT

        ; -- bail if section has no tile art (null pointer) --
        movea.l Sec_sec_tile_art(a0), a2
        cmpa.w  #0, a2
        beq.s   .skip

        ; -- bail if uncompressed size is 0 (placeholder blob) --
        move.w  (a2), d4                            ; d4.w = uncompressed size
        beq.s   .skip

        ; -- pick next streaming buffer (round-robin via Streaming_Active_Buffer) --
        ; Active=0 → use buffer A, flip to 1 for next call
        ; Active=1 → use buffer B, flip to 0 for next call
        moveq   #0, d0
        move.b  (Streaming_Active_Buffer).w, d0
        bne.s   .use_buffer_b
        lea     (STREAMING_BUFFER_A).l, a3
        move.b  #1, (Streaming_Active_Buffer).w
        bra.s   .have_buffer
.use_buffer_b:
        lea     (STREAMING_BUFFER_B).l, a3
        move.b  #0, (Streaming_Active_Buffer).w
.have_buffer:

        ; -- decompress run-to-completion: a2 = source blob, a3 = dest buffer --
        movea.l a2, a0                              ; a0 = source
        movea.l a3, a1                              ; a1 = dest
        bsr.w   Art_Decompress                      ; clobbers d0-d3, a2-a3 (a3 = dest start — equals the buffer this routine already holds; ZX0 path leaves a3 alone)

        ; -- queue Deferrable DMA: streaming buffer → section's VRAM dest --
        move.l  a3, d1                              ; d1 = source (RAM addr)
        moveq   #0, d2
        move.w  Sec_sec_tile_art_vram(a4), d2       ; d2.w = VRAM dest (from saved Sec ptr)
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Deferrable

        ; -- mark section STREAMING --
        lea     (Section_Stream_State).w, a1
        move.b  #SS_STREAMING, (a1, d6.w)

.skip:
        rts
