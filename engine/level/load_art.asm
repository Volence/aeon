; Level art loader
; Blocking decompress → DMA pipeline. The act uses a single act-wide paged
; art pool that is fully resident in VRAM for the life of the act (loaded
; once at init).

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
        bra.w   S4LZ_Decompress                     ; S4LZ_Decompress reads its own wrapper
.zx0:
        addq.l  #ART_HDR_SIZE, a0                   ; ZX0 stream starts past wrapper
        bra.w   ZX0_Decompress

; -----------------------------------------------
; Level_LoadArt — load the WHOLE act art pool to VRAM, then init BG.
;
; In:  a0 = act descriptor pointer
; Out: none
; Clobbers: d0–d5, d7, a0–a3; d6/a4–a6 are movem-PRESERVED (the loop-live
;      registers below sit in them so both callees' licenses leave them alone)
;
; The act ships one paged art pool. Each page
; is a wrapped ZX0/S4LZ blob of up to ART_POOL_PAGE_TILES (256) tiles. We
; decompress each page into Art_Staging_Buffer (8192 B, the init-only view
; over the tile-cache RAM — free before the tile cache is populated) and
; queue a Critical DMA to its fixed VRAM slot (page_index * 8192 bytes =
; page_index << 13). The whole pool is then resident for the life of the
; act, so section streaming/teleport never reloads tile art.
;
; Runs at init with the display blanked OFF (caller's responsibility): with
; the display off, DMA runs at the full ~205 bytes/line rate on EVERY line
; (the active/blank distinction disappears), so each page's Critical DMA
; drains with wide margin inside its one VSync.
;
; Loop-live registers chosen to survive BOTH callees:
;   Art_Decompress    clobbers d0–d3, a2–a3 (a4/d4 preserved)
;   QueueDMA_Critical clobbers d0–d4, a1–a2
;   VSync_Wait        clobbers d0
; → a4 (act ptr), a5 (page table cursor), a6 (VRAM dest), d6 (page count-1)
;   are all untouched across the calls. d7 carries the page's byte length across
;   the queue attempt (QueueDMA_Critical clobbers d4, so a drop-retry can't
;   re-read the length from d4).
;
; Drop handling: QueueDMA_Critical's carry is consumed IMMEDIATELY
; (VSync_Wait, the next call, clobbers CCR and d0). A drop should never happen
; here — init runs display-off with an extended VBlank that drains Critical every
; VSync — so DEBUG asserts on it (RaiseError) and release honestly drains a frame
; and retries the same page (Art_Staging_Buffer still holds the decompressed
; data; VSync_Wait touches neither it nor a6). Both directions are testable:
; force the Critical queue full and confirm DEBUG halts / release retries + lands.
; -----------------------------------------------
Level_LoadArt:
        movem.l d6/a4-a6, -(sp)
        movea.l a0, a4                              ; a4 = act ptr (preserved)

        move.w  Act_act_art_pool_pages(a4), d6      ; d6.w = page count
        beq.s   .done                               ; empty pool → nothing to load
        subq.w  #1, d6                              ; d6 = count-1 (dbf counter)

        movea.l Act_act_art_pool_table(a4), a5      ; a5 = page-address table cursor
        suba.l  a6, a6                              ; a6 = VRAM byte dest, starts at 0

.page_loop:
        movea.l (a5)+, a0                           ; a0 = next page wrapper addr
        move.w  (a0), d4                            ; d4.w = uncompressed size (BE)
        beq.s   .next                               ; size 0 → skip (empty page stub)

        lea     (Art_Staging_Buffer).l, a1          ; a1 = decompress scratch
        bsr.s   Art_Decompress                      ; a4/d4 preserved across this. LOCKSTEP load_art.emp step 2: jbsr relaxes short (in-region backward reach)
        move.w  d4, d7                              ; d7 = byte length (survives QueueDMA/VSync for retry)

.queue_page:
        move.l  #Art_Staging_Buffer, d1             ; d1 = DMA source (RAM)
        moveq   #0, d2
        move.w  a6, d2                              ; d2.w = VRAM byte dest
        move.w  d7, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Critical
        bcs.s   .drop_page                         ; carry SET → dropped (rare; handled out of line)
        bsr.w   VSync_Wait

.next:
        lea     (ART_POOL_PAGE_TILES*32)(a6), a6    ; advance VRAM dest one page (8192 B)
        dbf     d6, .page_loop

.done:
        ; -- §2 A.5: blit zone-wide BG to Plane B nametable (T1) --
        movea.l a4, a0                              ; a0 = act ptr
        bsr.s   BG_Init                             ; LOCKSTEP load_art.emp step 2: jbsr relaxes short (BG_Init is the next placement)

        movem.l (sp)+, d6/a4-a6
        rts

; Out-of-line drop handler — kept out of the .page_loop body so the loop's
; forward .s branches (beq.s .done, beq.s .next) stay in range in BOTH shapes
; despite the DEBUG RaiseError expansion. Reached only on carry SET (queue full),
; which should never happen during blanked-init load (see the header note).
.drop_page:
    ifdef __DEBUG__
        RaiseError "Level_LoadArt: Critical DMA queue full during init art load"
    else
        bsr.w   VSync_Wait                         ; release: drain a frame, then retry this page
        bra.s   .queue_page                        ; Art_Staging_Buffer + a6 still valid
    endif
