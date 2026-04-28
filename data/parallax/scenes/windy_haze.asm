; data/parallax/scenes/windy_haze.asm — composite scene config
;
; Stacks two effects in one section:
;   - BG: windy multi-band gradient (DeformTable_OJZ_Calm from ojz_windy.asm)
;     clouds wave at full amplitude, mountains progressively less, ground none.
;   - FG: uniform haze (DeformTable_Haze from effects/haze.asm)
;     entire plane A wobbles ±2 px regardless of row.
;
; This is a hand-authored composite — the per-band BAND_DSA / BAND_DSB
; gradients can't be expressed via the single-band parallax_combine sugar.
; For simpler stacks (uniform across the screen), use parallax_combine.
;
; Why this lives here: scenes/ holds section-specific composite configs
; that mix multiple effects with custom band layouts. effects/ holds
; reusable single-effect building blocks.

ParallaxConfig_WindyHaze:
    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformFg=DeformTable_Haze, deformSpeedFg=2, \
                     deformBg=DeformTable_OJZ_Calm, deformSpeedBg=1
        ; clouds — full BG wave (±96), uniform FG haze (±2)
BAND_PHASE := 0
BAND_DSA := 3
BAND_DSB := 0
        band 0,  FACTOR_1, FACTOR_1_8
        ; far mountains — half BG wave (±16), uniform FG haze
BAND_PHASE := 64
BAND_DSA := 3
BAND_DSB := 1
        band 4,  FACTOR_1, FACTOR_1_4
        ; mid mountains — quarter BG wave (±8), uniform FG haze
BAND_PHASE := 128
BAND_DSA := 3
BAND_DSB := 2
        band 10, FACTOR_1, FACTOR_3_8
        ; hills — eighth BG wave (±4), uniform FG haze
BAND_PHASE := 192
BAND_DSA := 3
BAND_DSB := 3
        band 14, FACTOR_1, FACTOR_1_2
        ; ground — no BG wave, uniform FG haze
BAND_PHASE := 0
BAND_DSA := 3
BAND_DSB := 15
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end
