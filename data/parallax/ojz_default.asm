; data/parallax/ojz_default.asm — Default parallax config for OJZ Act 1
;
; Bootstrap configuration used while later tasks add deform variants.
; 5 horizontal bands, no FG/BG H-deformation, whole-plane V-scroll.
; All Plane A bands use FACTOR_1 (gameplay scrolls 1:1 with camera);
; Plane B bands graduate from 1/8 (clouds, slowest) to 1 (ground, FG-sync).

; Zero-deform table — forces per-line pipeline (mode_set_3=$03, 224-line
; fill, 896-byte HScroll DMA) so the buffer is correct regardless of which
; mode VDP reg $0B happens to be in. The shadow→register propagation has
; been intermittently leaving $0B at $03 (per-line) even when shadow says
; $02; rather than chase that, we sidestep by always producing a per-line
; buffer. With sample = 0 there is no visual deform.
;
; LOAD-BEARING — re-confirmed live 2026-06-23. Dropping this to NULL (per-cell,
; the ~20%/frame HScroll saving) renders fine AT REST but breaks Plane A (FG)
; HScroll DURING SCROLL: the register sticks at $03 while the buffer is per-cell,
; so the FG draws strips at wrong horizontal offsets over the art instead of
; streaming continuously. The $0B bug is LIVE, not stale. Do NOT remove this
; without first fixing the $0B shadow→register propagation (see DEFERRED_WORK).
DeformTable_Zero:
    rept 256
        dc.b 0
    endr

ParallaxConfig_OJZ_Default:
    ; Vertical parallax: BG_y = (camY-512)/8 over the full 512px-tall
    ; wrapping plane. vFactorBg=3 is rebase-proof: the vertical section
    ; rebase shifts camY by $1000, and $1000>>3 = 512 = exactly one plane
    ; height — the wrap is seamless, no per-section compensation needed.
    ; Band tops below are PLANE B cell rows (0..63), converted to screen
    ; cells per frame by Step 4a in Parallax_Update.
    parallax_section layerMask=$1F, vFactorBg=3, vCenter=512, vOffset=0, \
                     deformBg=DeformTable_Zero
        ; Deep Forest tuning: the colonnade band scrolls at 1/8 line-scroll
        ; + camera/4 tile animation = 3/8 apparent, keeping the depth stack
        ; monotonic: 1/16 canopy, 3/8 trunks, 1/2 undergrowth, 5/8 roots, 1 FG.
        band 0,  FACTOR_1, FACTOR_1_16      ; plane rows 0-7   canopy ceiling
        band 8,  FACTOR_1, FACTOR_1_8       ; plane rows 8-39  marching colonnade
        band 40, FACTOR_1, FACTOR_1_2       ; plane rows 40-47 undergrowth + grass
        band 48, FACTOR_1, FACTOR_5_8       ; plane rows 48-63 roots + the dark below
    parallax_section_end

; Note: previous T12 fixtures (perspective floor, wave rocking) have been
; promoted to data/parallax/effects/ as reusable library entries.
