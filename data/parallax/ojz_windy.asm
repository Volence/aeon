; data/parallax/ojz_windy.asm — F3 fixture: BG H-deformation enabled
;
; Same band layout as the default OJZ config but with BG sine deformation.
; Clouds (band 0) wave at full amplitude; far/mid mountains (bands 1-2)
; wave more subtly (larger amplitude shift); hills + ground (bands 3-4)
; don't wave at all.
;
; Per-band PHASE offsets desync the cloud and mountain bands so they wave
; out of lockstep — gives a more natural "wind moving across the sky" feel
; instead of synchronised pulsing.

; Sine table: ±96 px amplitude. PERIOD=64 → half-cycle across 32-line cloud band
; (clouds form a ramping "bulge" rather than wavy zigzag).
DeformTable_OJZ_Calm:
    deform_table_sine AMPLITUDE=96, PERIOD=64

ParallaxConfig_OJZ_Windy:
    parallax_section layerMask=$1F, vFactorBg=3, vCenter=496, vOffset=0, \
                     deformBg=DeformTable_OJZ_Calm, deformSpeedBg=1
        ; clouds — full amplitude (±96 px), phase 0
BAND_PHASE := 0
BAND_DSB := 0
        band 0,  FACTOR_1, FACTOR_1_8
        ; far mountains — half (±16), phase 64
BAND_PHASE := 64
BAND_DSB := 1
        band 4,  FACTOR_1, FACTOR_1_4
        ; mid mountains — quarter (±8), phase 128
BAND_PHASE := 128
BAND_DSB := 2
        band 10, FACTOR_1, FACTOR_3_8
        ; hills — eighth (±4), phase 192
BAND_PHASE := 192
BAND_DSB := 3
        band 14, FACTOR_1, FACTOR_1_2
        ; ground — no deform
BAND_DSB := 15
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
