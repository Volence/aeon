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
DeformTable_Zero:
    rept 256
        dc.b 0
    endr

ParallaxConfig_OJZ_Default:
    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Zero
        band 0,  FACTOR_1, FACTOR_1_8       ; rows 0-3   clouds
        band 4,  FACTOR_1, FACTOR_1_4       ; rows 4-9   far mountains
        band 10, FACTOR_1, FACTOR_3_8       ; rows 10-13 mid mountains
        band 14, FACTOR_1, FACTOR_1_2       ; rows 14-19 hills
        band 20, FACTOR_1, FACTOR_1         ; rows 20-27 ground (FG-sync)
    parallax_section_end

; Note: previous T12 fixtures (perspective floor, wave rocking) have been
; promoted to data/parallax/effects/ as reusable library entries.
