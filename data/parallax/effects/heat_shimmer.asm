; data/parallax/effects/heat_shimmer.asm — reusable parallax effect
;
; Visual: subtle horizontal wobble on plane B simulating hot air rising
; off the ground. Per-line H-deform with small amplitude, tight wavelength,
; and animated phase = "shimmering heat haze" (deserts, lava, magic forge).
;
; Mechanism: BG H-deform sine table sampled per scanline. Phase advances
; SPEED steps per frame for animation. PERIOD=32 → 8 wave cycles across
; the 256-byte table; adjacent lines sample ~12.5% out of phase, giving
; fine-grained vertical wobble. Plane A unaffected (FG-side untouched).
;
; -- Tuning knobs (heat_shimmer_config macro, camelCase per AS rules) --
;   speed:    phase advance per frame.  1 = lazy   3 = default   6 = frantic
;   shift:    >> applied to sample.     Higher = subtler.
;     Effective peak offset in pixels = AMPLITUDE >> shift.
;     Default 8 >> 2 = ±2 px. Try 8 >> 1 = ±4 px for a rougher haze.
;     (AMPLITUDE is baked into the shared deform table; if you want a
;     different table shape, define your own DeformTable_* + ParallaxConfig.)
;   fgFactor / bgFactor: per-band horizontal scroll factors.
;
; Usage:
;   1) include this file from main.asm
;   2) Either:
;        a) Point Sec_sec_parallax_config at a pre-named variant
;           (ParallaxConfig_HeatShimmer / _Slow / _Fast), OR
;        b) Define a custom config nearby:
;             ParallaxConfig_MyHotZone:
;                 heat_shimmer_config speed=2, shift=1
;           and point the section at ParallaxConfig_MyHotZone.

; -- shared deform table — all heat-shimmer variants reference this --
DeformTable_HeatShimmer:
    deform_table_sine AMPLITUDE=8, PERIOD=32

; ----------------------------------------------------------------------
; heat_shimmer_config — emit one heat-shimmer parallax_config record.
; AS macro params can't contain underscores, hence camelCase.
; All params optional (sane defaults).
; ----------------------------------------------------------------------
heat_shimmer_config macro speed,shift,fgFactor,bgFactor
    if "speed" = ""
HS_SPEED := 3
    else
HS_SPEED := speed
    endif
    if "shift" = ""
HS_SHIFT := 2
    else
HS_SHIFT := shift
    endif
    if "fgFactor" = ""
HS_FG := FACTOR_1
    else
HS_FG := fgFactor
    endif
    if "bgFactor" = ""
HS_BG := FACTOR_1_4
    else
HS_BG := bgFactor
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_HeatShimmer, \
                     deformSpeedBg=HS_SPEED, \
                     deformShiftDefault=HS_SHIFT
        band 0, HS_FG, HS_BG
    parallax_section_end
    endm

; -- pre-named variants for casual use --
ParallaxConfig_HeatShimmer_Slow:
    heat_shimmer_config speed=1

ParallaxConfig_HeatShimmer:
    heat_shimmer_config speed=3                 ; default (medium)

ParallaxConfig_HeatShimmer_Fast:
    heat_shimmer_config speed=6
