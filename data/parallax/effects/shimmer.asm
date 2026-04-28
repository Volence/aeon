; data/parallax/effects/shimmer.asm — reusable parallax effect
;
; Visual: subtle horizontal wobble simulating heat haze / mirage / hot air.
; Per-line H-deform with small amplitude, tight wavelength, animated phase.
; Works on either plane:
;   shimmer_fg → plane A wobbles (FG terrain shimmers)
;   shimmer_bg → plane B wobbles (sky/clouds shimmer)
;
; Mechanism: H-deform sine table sampled per scanline. Phase advances
; SPEED steps per frame. PERIOD=32 → 8 wave cycles across the 256-byte
; table; adjacent lines sample ~12.5% out of phase, giving fine-grained
; vertical wobble. AMPLITUDE=8 baked into the table; per-band shift
; (defaultShift=2) downscales to ±2 px.
;
; Tuning (shimmer_fg / shimmer_bg macros):
;   speed: phase advance per frame.  1 = lazy   3 = default   6 = frantic
;   shift: >> applied to sample.     Higher = subtler.
;     Effective peak = AMPLITUDE >> shift. Default 8 >> 2 = ±2 px.
;
; Variants pre-defined for BG plane (most common use). For FG plane,
; either use shimmer_fg macro directly or define a custom variant.

; -- shared deform table --
DeformTable_Shimmer:
    deform_table_sine AMPLITUDE=8, PERIOD=32

; ----------------------------------------------------------------------
; shimmer_bg — apply shimmer to plane B (BG H-deform)
; ----------------------------------------------------------------------
shimmer_bg macro speed,shift,fgFactor,bgFactor
    if "speed" = ""
SH_SPEED := 3
    else
SH_SPEED := speed
    endif
    if "shift" = ""
SH_SHIFT := 2
    else
SH_SHIFT := shift
    endif
    if "fgFactor" = ""
SH_FG := FACTOR_1
    else
SH_FG := fgFactor
    endif
    if "bgFactor" = ""
SH_BG := FACTOR_1_4
    else
SH_BG := bgFactor
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Shimmer, \
                     deformSpeedBg=SH_SPEED, \
                     deformShiftDefault=SH_SHIFT
        band 0, SH_FG, SH_BG
    parallax_section_end
    endm

; ----------------------------------------------------------------------
; shimmer_fg — apply shimmer to plane A (FG H-deform)
; ----------------------------------------------------------------------
shimmer_fg macro speed,shift,fgFactor,bgFactor
    if "speed" = ""
SH_SPEED := 3
    else
SH_SPEED := speed
    endif
    if "shift" = ""
SH_SHIFT := 2
    else
SH_SHIFT := shift
    endif
    if "fgFactor" = ""
SH_FG := FACTOR_1
    else
SH_FG := fgFactor
    endif
    if "bgFactor" = ""
SH_BG := FACTOR_1_4
    else
SH_BG := bgFactor
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformFg=DeformTable_Shimmer, \
                     deformSpeedFg=SH_SPEED, \
                     deformShiftDefault=SH_SHIFT
        band 0, SH_FG, SH_BG
    parallax_section_end
    endm

; -- pre-named BG variants (canonical heat-shimmer use) --
ParallaxConfig_Shimmer_Slow:
    shimmer_bg speed=1

ParallaxConfig_Shimmer:
    shimmer_bg speed=3                ; default (medium)

ParallaxConfig_Shimmer_Fast:
    shimmer_bg speed=6
