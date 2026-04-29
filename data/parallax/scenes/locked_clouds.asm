; data/parallax/scenes/locked_clouds.asm — F6 fixture: layer-mask test
;
; layerMask=$1E (binary 11110) disables band 0 — bit 0 cleared. Disabled
; bands fall through to the band-inheritance path in Parallax_Update:
;
;     .band_disabled:
;             ; inherit previous-band scroll
;             move.w  d3, (a2)
;             move.w  d4, (a3)
;
; For band 0 there's no previous band, so d3/d4 are still 0 from init.
; Result: band 0 (cloud rows 0-3) scroll = 0 = locked. Mountains, hills,
; ground (bands 1-4) parallax normally per their factors.
;
; Verifies the inheritance code path. Visual: clouds frozen while the
; rest of plane B drifts past underneath as camera moves. Useful pattern
; for "still sky" sections (boss arenas, story-beat moments).
;
; The band 0 factors (FACTOR_1, FACTOR_1_8) are still emitted for the
; struct layout but are ignored at runtime because layer_mask bit 0 = 0.

ParallaxConfig_OJZ_LockedClouds:
    parallax_section layerMask=$1E, vFactorBg=15, vCenter=0, vOffset=0, \
                     transition=1, deformBg=DeformTable_Zero
        band 0,  FACTOR_1, FACTOR_1_8       ; rows 0-3   DISABLED → inherits 0 → locked
        band 4,  FACTOR_1, FACTOR_1_4       ; rows 4-9   far mountains
        band 10, FACTOR_1, FACTOR_3_8       ; rows 10-13 mid mountains
        band 14, FACTOR_1, FACTOR_1_2       ; rows 14-19 hills
        band 20, FACTOR_1, FACTOR_1         ; rows 20-27 ground
    parallax_section_end
