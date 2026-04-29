; data/parallax/effects/perspective.asm — reusable parallax effect
;
; Visual: animated floor distortion combining per-column V-scroll (edges
; sag relative to center) with per-line H-deform (horizontal shimmer on
; ground bands). The combined effect gives the ground a sense of depth
; and motion — more alive than either effect alone.
;
; Mechanism:
;   V-deform: v_column_floor table, animated (vDeformSpeedBg=1) so the
;     column shape drifts, creating a rolling/breathing floor.
;   H-deform (BG): sine wave with per-band amplitude — sky/clouds skip,
;     hills faint, ground full. Gives the floor a heat-shimmer quality.
;
; Plane B HScroll locked (factor_b = FACTOR_0) to avoid the documented
; Genesis VDP "leftmost partial column" silicon-level artifact.
;
; DEPENDENCY: requires DeformTable_Shimmer from effects/shimmer.asm.
;
; Tuning:
;   vShift:  V-column amplitude shift.  0 = dramatic  1 = default  2 = subtle
;   hSpeed:  H-deform speed.            1 = lazy      2 = default
;   vSpeed:  V-column animation speed.  0 = static    1 = default  2 = fast

; -- V-deform table (symmetric floor curve, max amplitude) --
DeformTable_Perspective:
    v_column_floor CENTER=20, maxOffset=24

; ----------------------------------------------------------------------
; perspective — combined V-column floor + H-deform ground shimmer
; ----------------------------------------------------------------------
perspective macro vShift,hSpeed,vSpeed
    if "vShift" = ""
PF_VSH := 0
    else
PF_VSH := vShift
    endif
    if "hSpeed" = ""
PF_HS := 2
    else
PF_HS := hSpeed
    endif
    if "vSpeed" = ""
PF_VS := 1
    else
PF_VS := vSpeed
    endif

    parallax_section layerMask=$1F, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Shimmer, deformSpeedBg=PF_HS, \
                     vDeformBg=DeformTable_Perspective, \
                     vDeformSpeedBg=PF_VS, \
                     vDeformShiftBg=PF_VSH
BAND_DSB := 15
        band 0,  FACTOR_1, FACTOR_0       ; rows 0-3   clouds (no H-deform, BG locked)
        band 4,  FACTOR_1, FACTOR_0       ; rows 4-9   far mountains
        band 10, FACTOR_1, FACTOR_0       ; rows 10-13 mid mountains
BAND_DSB := 4
        band 14, FACTOR_1, FACTOR_0       ; rows 14-19 hills (faint H shimmer)
BAND_DSB := 2
        band 20, FACTOR_1, FACTOR_0       ; rows 20-27 ground (strong H shimmer)
    parallax_section_end
    endm

; -- pre-named variants --
ParallaxConfig_Perspective_Subtle:
    perspective vShift=2, hSpeed=1, vSpeed=0

ParallaxConfig_Perspective:
    perspective vShift=0, hSpeed=2, vSpeed=1

ParallaxConfig_Perspective_Dramatic:
    perspective vShift=0, hSpeed=3, vSpeed=2
