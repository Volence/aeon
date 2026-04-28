; data/parallax/ojz_default.asm — Default parallax config for OJZ Act 1
;
; Bootstrap configuration used while later tasks add deform variants.
; 5 horizontal bands, no FG/BG H-deformation, whole-plane V-scroll.
; All Plane A bands use FACTOR_1 (gameplay scrolls 1:1 with camera);
; Plane B bands graduate from 1/8 (clouds, slowest) to 1 (ground, FG-sync).

ParallaxConfig_OJZ_Default:
    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0
        band 0,  FACTOR_1, FACTOR_1_8       ; rows 0-3   clouds
        band 4,  FACTOR_1, FACTOR_1_4       ; rows 4-9   far mountains
        band 10, FACTOR_1, FACTOR_3_8       ; rows 10-13 mid mountains
        band 14, FACTOR_1, FACTOR_1_2       ; rows 14-19 hills
        band 20, FACTOR_1, FACTOR_1         ; rows 20-27 ground (FG-sync)
    parallax_section_end

; --- T12 fixture: pseudo-3D perspective floor (per-column V-scroll demo) ---
; Static perspective ramp (vDeformSpeedBg=0): outer columns shifted up to
; ±16 px relative to FOCAL=20 (screen center). vDeformShiftBg=0 means
; full amplitude pass-through.
DeformTable_OJZ_Floor:
    v_column_perspective FOCAL=20, maxOffset=64

ParallaxConfig_OJZ_Floor:
    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     vDeformBg=DeformTable_OJZ_Floor, vDeformSpeedBg=0, vDeformShiftBg=0
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
