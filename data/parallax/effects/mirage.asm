; data/parallax/effects/mirage.asm — reusable parallax effect
;
; Visual: distant heat haze — extreme low-amplitude high-frequency
; horizontal wobble on plane B. Easy to mistake for "is it actually
; moving?" at a glance, but the eye registers the disturbance, giving
; the air-shimmering-over-asphalt feel without the obvious wobble of
; the heavier `haze` effect.
;
; Mechanism: BG H-deform sine table sampled per scanline. Tiny amplitude
; (4 in the table) + per-band shift 2 → effective ±1 px peak. Tight period
; (16) and high speed advance (4) make it feel like rapid air turbulence.
;
; Subtler cousin to `haze` — when haze would be too aggressive (e.g. for
; a far-distance vista where the player is looking at the horizon), use
; mirage. Plane A unaffected.
;
; Tuning (mirage_config macro):
;   speed: phase advance per frame.  2 = lazy   4 = default   8 = frantic

; -- shared deform table --
DeformTable_Mirage:
    deform_table_sine AMPLITUDE=4, PERIOD=16

; ----------------------------------------------------------------------
; mirage_config — emit a mirage parallax_config record.
; ----------------------------------------------------------------------
mirage_config macro speed
    if "speed" = ""
MG_SPEED := 4
    else
MG_SPEED := speed
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Mirage, \
                     deformSpeedBg=MG_SPEED, \
                     deformShiftDefault=2
        band 0, FACTOR_1, FACTOR_1_4
    parallax_section_end
    endm

; -- pre-named variants --
ParallaxConfig_Mirage_Slow:
    mirage_config speed=2

ParallaxConfig_Mirage:
    mirage_config speed=4              ; default

ParallaxConfig_Mirage_Fast:
    mirage_config speed=8
