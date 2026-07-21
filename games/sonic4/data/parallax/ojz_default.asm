; data/parallax/ojz_default.asm — Default parallax config for OJZ Act 1
;
; Bootstrap configuration used while later tasks add deform variants.
; 5 horizontal bands, no FG/BG H-deformation, whole-plane V-scroll.
; All Plane A bands use FACTOR_1 (gameplay scrolls 1:1 with camera);
; Plane B bands graduate from 1/8 (clouds, slowest) to 1 (ground, FG-sync).

; Zero-deform table — forces the PER-LINE HScroll pipeline (mode_set_3=$03,
; 224-line fill, 896-byte HScroll DMA). REQUIRED, not a perf accident.
;
; Why per-line is mandatory (verified on hardware via VDP-register
; read): a BG parallax band's on-screen boundary is (band_top_plane_row*8 − BG
; vertical scroll). With smooth per-pixel vertical parallax (vFactorBg), those
; boundaries land at ARBITRARY screen lines (measured one at line 22). Per-cell
; HScroll mode ($02) can only change the scroll every 8 px (cell-rows 0,8,16,…),
; so it physically cannot place a boundary at line 22 — it rounds to 16/24,
; misaligning each band by up to 7 px and TEARING the FG/BG at every band
; boundary during scroll. Per-line ($03) has 1-px precision → clean bands.
;
; NOTE: the previous "$0B shadow→register propagation" explanation here was a
; MISDIAGNOSIS. VDP reg $0B reads $02 correctly in per-cell — propagation is
; fine; the real cause is the band-boundary precision above. The ~20%/frame
; per-cell saving is NOT achievable without giving up smooth vertical parallax
; (see DEFERRED_WORK). With sample = 0 this table adds no visual deform.
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
    ; deformShiftDefault=15 marks every band's H-deform channel INACTIVE (shift 15
    ; = the runtime "flat" sentinel, parallax.asm .fg_inactive/.lp_flat), so each
    ; band skips the per-line deform sample loop on this all-zero table (~16k cy/f).
    ; Mode-select keys on the table POINTER being non-NULL, not the shift, so
    ; per-line HScroll mode ($03, 896-byte DMA, pixel-clean band boundaries) is
    ; retained — the emitted HScroll is byte-identical, just produced without the
    ; pointless (0 >> shift) = 0 math. Free lunch; no visual change.
    parallax_section layerMask=$1F, vFactorBg=3, vCenter=512, vOffset=0, \
                     deformBg=DeformTable_Zero, deformShiftDefault=15
        ; The ChatGPT Deep Forest BG is ONE continuous scene (trunks run the
        ; full plane height), not separate depth layers — so all bands must
        ; share a single BG scroll factor or the differential shears the trunks
        ; apart at each band boundary. Uniform 1/2 = coherent parallax depth
        ; (BG at half the 1:1 foreground). Tune the single factor to taste.
        band 0,  FACTOR_1, FACTOR_1_2       ; plane rows 0-7   canopy ceiling
        band 8,  FACTOR_1, FACTOR_1_2       ; plane rows 8-39  colonnade trunks
        band 40, FACTOR_1, FACTOR_1_2       ; plane rows 40-47 undergrowth + grass
        band 48, FACTOR_1, FACTOR_1_2       ; plane rows 48-63 roots + the dark below
    parallax_section_end

; Note: previous T12 fixtures (perspective floor, wave rocking) have been
; promoted to data/parallax/effects/ as reusable library entries.
