; data/parallax/effects/screen_shake.asm — reusable parallax effect
;
; Visual: brief, intense full-screen shake — explosions, impacts, heavy
; landings. Triangle wave on plane B per-line H-deform at high amplitude
; and fast phase advance. Combined with a per-column V-deform on the
; same plane gives a 2D wobble (X+Y), but the H-only variant is enough
; for most "thump" moments and saves the per-column path for fancier
; uses.
;
; Mechanism: BG H-deform triangle table sampled per scanline. AMPLITUDE
; 32, PERIOD 8 → tight high-frequency oscillation. deformSpeedBg high
; advances phase quickly across frames. Per-band shift=2 → effective
; ±8 px peak; user may want to bump shift to 1 (±16 px) for a heavier
; impact or 3 (±4 px) for a subtler tremor.
;
; Trigger pattern: gameplay event swaps Parallax_Current_Config to a
; ParallaxConfig_ScreenShake_* variant for N frames, then restores the
; previous config via Parallax_StartTransition. The transition=1 flag on
; the shake config makes entry/exit instant — no lerp slide. The shake
; is a one-shot, not a steady state.
;
; Tuning (screen_shake_config macro):
;   speed:  phase advance per frame.  3 = mild   8 = default   16 = violent
;   shift:  >> applied to sample.     1 = ±16 px   2 = ±8 px   3 = ±4 px

; -- shared deform table --
DeformTable_ScreenShake:
    deform_table_triangle AMPLITUDE=32, PERIOD=8

; ----------------------------------------------------------------------
; screen_shake_config — emit a screen-shake parallax_config record.
; ----------------------------------------------------------------------
screen_shake_config macro speed,shift
    if "speed" = ""
SS_SPEED := 8
    else
SS_SPEED := speed
    endif
    if "shift" = ""
SS_SHIFT := 2
    else
SS_SHIFT := shift
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     transition=1, \
                     deformBg=DeformTable_ScreenShake, \
                     deformSpeedBg=SS_SPEED, \
                     deformShiftDefault=SS_SHIFT
        band 0, FACTOR_1, FACTOR_1
    parallax_section_end
    endm

; -- pre-named intensity variants --
ParallaxConfig_ScreenShake_Mild:
    screen_shake_config speed=3, shift=3

ParallaxConfig_ScreenShake:
    screen_shake_config speed=8, shift=2          ; default

ParallaxConfig_ScreenShake_Violent:
    screen_shake_config speed=16, shift=1
