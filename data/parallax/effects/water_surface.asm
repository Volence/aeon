; data/parallax/effects/water_surface.asm — reusable parallax effect
;
; Visual: ambient water surface — gently swelling waves combined with
; per-column vertical sway. Plane B reads as a moving body of water that
; you can see through to a horizon. Hydrocity-zone-style ambient water,
; not the sharp underwater-line effect of Sonic 1's Labyrinth.
;
; Mechanism stacks two deform sources on plane B:
;   1. BG H-deform sine — horizontal wave per scanline (waves rolling left/right)
;   2. BG per-column V-scroll sine — vertical column shift (water rising/falling)
;
; Both run simultaneously; the pipeline supports them via Parallax_Update's
; combined fill (per-line H mode + bit-2 per-column V). Two separate sine
; tables are used so they animate at independent phases, breaking the
; lock-step regularity that would betray a "single oscillator" feel.
;
; The H sine has wide period (64) for slow rolling; the V sine has narrow
; period (32) for tighter ripple. Both at modest amplitude — water isn't
; a violent wave, it's a gentle surface.
;
; HARDWARE QUIRK: per-column V-scroll on plane B with non-zero plane B
; HScroll garbles the leftmost 16 px (silicon-level VDP bug). Either
; lock plane B HScroll (factor_b = FACTOR_0, used here by default) or
; add a sprite mask (deferred work). With FACTOR_0 the BG doesn't
; scroll horizontally — fine for ambient water layers behind a steadier
; foreground.
;
; Tuning (water_surface_config macro):
;   speed:  H-deform speed per frame.  1 = calm   2 = default   4 = stormy
;   vSpeed: V-deform speed per frame.  1 = calm   2 = default   4 = stormy

; -- shared deform tables: H wave and V sway --
DeformTable_Water_H:
    deform_table_sine AMPLITUDE=12, PERIOD=64

DeformTable_Water_V:
    deform_table_sine AMPLITUDE=8, PERIOD=32

; ----------------------------------------------------------------------
; water_surface_config — emit a water-surface parallax_config record.
; ----------------------------------------------------------------------
water_surface_config macro speed,vSpeed
    if "speed" = ""
WS_SPEED := 2
    else
WS_SPEED := speed
    endif
    if "vSpeed" = ""
WS_VSPEED := 2
    else
WS_VSPEED := vSpeed
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Water_H, deformSpeedBg=WS_SPEED, \
                     vDeformBg=DeformTable_Water_V, vDeformSpeedBg=WS_VSPEED, \
                     vDeformShiftBg=1, \
                     deformShiftDefault=2
        band 0, FACTOR_1, FACTOR_0       ; BG H-locked (kills leftmost-column V-scroll quirk)
    parallax_section_end
    endm

; -- pre-named variants --
ParallaxConfig_WaterSurface_Calm:
    water_surface_config speed=1, vSpeed=1

ParallaxConfig_WaterSurface:
    water_surface_config speed=2, vSpeed=2          ; default

ParallaxConfig_WaterSurface_Stormy:
    water_surface_config speed=4, vSpeed=4
