; data/parallax/effects/haze.asm — reusable parallax effect (T13 fixture)
;
; Visual: horizontal wobble across the screen, applied to either plane.
; Two intensity profiles: "uniform" (whole screen wobbles same amount) or
; "gradient" (sky steady, hills faint, ground full — like heat rising
; from a hot floor distorting only the lower view).
;
; Works on either plane:
;   haze_fg → plane A wobbles
;   haze_bg → plane B wobbles
;
; Tuning (haze_fg / haze_bg macros):
;   speed:    phase advance per frame.  1 = lazy   2 = default   4 = frantic
;   gradient: 1 (default — top steady, bottom strong)
;             0 (uniform across all bands)
;
; The graduated mode uses per-band shift_x (BAND_DSA for FG, BAND_DSB for BG):
;   sky / far / mid mtns:  shift = 15  (skip — sentinel)
;   hills:                  shift = 4   (faint, ±1 px)
;   ground:                 shift = 3   (full, ±2 px)
;
; The uniform mode sets shift = 3 on every band (±2 px everywhere).

; -- shared deform table --
DeformTable_Haze:
    deform_table_sine AMPLITUDE=16, PERIOD=64

; ----------------------------------------------------------------------
; haze_fg — apply haze to plane A (FG H-deform)
; ----------------------------------------------------------------------
haze_fg macro speed,gradient
    if "speed" = ""
HZ_SPEED := 2
    else
HZ_SPEED := speed
    endif
    if "gradient" = ""
HZ_GRAD := 1
    else
HZ_GRAD := gradient
    endif

    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformFg=DeformTable_Haze, \
                     deformSpeedFg=HZ_SPEED
    if HZ_GRAD
BAND_DSA := 15
        band 0,  FACTOR_1, FACTOR_1_8       ; rows 0-3   clouds
        band 4,  FACTOR_1, FACTOR_1_4       ; rows 4-9   far mountains
        band 10, FACTOR_1, FACTOR_3_8       ; rows 10-13 mid mountains
BAND_DSA := 4
        band 14, FACTOR_1, FACTOR_1_2       ; rows 14-19 hills (±1 px)
BAND_DSA := 3
        band 20, FACTOR_1, FACTOR_1         ; rows 20-27 ground (±2 px)
    else
BAND_DSA := 3
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    endif
    parallax_section_end
    endm

; ----------------------------------------------------------------------
; haze_bg — apply haze to plane B (BG H-deform)
; ----------------------------------------------------------------------
haze_bg macro speed,gradient
    if "speed" = ""
HZ_SPEED := 2
    else
HZ_SPEED := speed
    endif
    if "gradient" = ""
HZ_GRAD := 1
    elseif "gradient" = "on"
HZ_GRAD := 1
    elseif "gradient" = "off"
HZ_GRAD := 0
    else
        fatal "haze_bg: gradient must be 'on' or 'off'"
    endif

    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Haze, \
                     deformSpeedBg=HZ_SPEED
    if HZ_GRAD
BAND_DSB := 15
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
BAND_DSB := 4
        band 14, FACTOR_1, FACTOR_1_2
BAND_DSB := 3
        band 20, FACTOR_1, FACTOR_1
    else
BAND_DSB := 3
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    endif
    parallax_section_end
    endm

; -- pre-named FG variants (canonical ground-haze use) --
ParallaxConfig_Haze_Slow:
    haze_fg speed=1                       ; gradient default

ParallaxConfig_Haze:
    haze_fg speed=2                       ; gradient default

ParallaxConfig_Haze_Fast:
    haze_fg speed=4                       ; gradient default

ParallaxConfig_Haze_Uniform:
    haze_fg speed=2, gradient=0           ; whole FG plane wobbles same amount
