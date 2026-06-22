; data/parallax/scenes/caves.asm — F4 fixture: section-pair transition test
;
; Slow BG parallax mimicking the feel of an underground cavern: the further
; bands barely move (FACTOR_1_16) while the foreground stays full speed.
; Used as a contrast to Sec1's Windy config — crossing the Sec1↔Sec2
; boundary should visibly lerp the BG scroll factors over 16 frames.
;
; v-anchor uses the lock sentinel (vFactorBg=15) like the other configs:
; OJZ Phase 1 starts Camera_Y near $01F0. With non-lock vFactorBg, FG plane V-scroll
; would equal camY, which on plane A rolls over into the sprite-table-
; overlapped rows at $D800 → garbage tiles render as a pink bar at the top
; of screen. Lock keeps FG V-scroll = 0 → plane row 0 (cloud area) at top.
; The V-anchor lerp path can be re-tested once player physics drive Camera_Y.
;
; Layout: identical 5-band shape to OJZ_Default; only H-factors differ.

ParallaxConfig_OJZ_Caves:
    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     transition=1, deformBg=DeformTable_Zero
        band 0,  FACTOR_1, FACTOR_1_16      ; rows 0-3   distant cave ceiling
        band 4,  FACTOR_1, FACTOR_1_16      ; rows 4-9   far walls
        band 10, FACTOR_1, FACTOR_1_8       ; rows 10-13 mid walls
        band 14, FACTOR_1, FACTOR_1_4       ; rows 14-19 close walls
        band 20, FACTOR_1, FACTOR_1         ; rows 20-27 floor (FG-sync)
    parallax_section_end
