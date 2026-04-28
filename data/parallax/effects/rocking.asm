; data/parallax/effects/rocking.asm — reusable parallax effect
;
; Visual: plane B rocks/sways like a boat deck or floating platform. A
; sine wave traveling across the 20 screen columns produces a continuous
; rolling motion. Good for ocean horizons, levitating arenas, or anything
; that needs a feeling of unsteady ground.
;
; Mechanism: per-column V-scroll sampling a 256-byte sine table. Each of
; the 20 screen columns gets its own V-offset; vDeformSpeedBg=N advances
; the phase N steps per frame so the wave appears to travel sideways.
;
; AMPLITUDE=20, PERIOD=64 → ±20 px peak shift, 4 wave cycles across the
; table; 20 visible columns sweep through ~5/16 of one cycle.
;
; Plane B HScroll locked (factor_b = FACTOR_0) to avoid the documented
; Genesis VDP "leftmost partial column" silicon-level artifact (see
; engine/level/parallax.asm Vscroll_Write header). Plane A unaffected
; (per-column V uses camY for FG_V regardless).
;
; DEPENDENCY: requires DeformTable_Zero from data/parallax/ojz_default.asm
; as the H-deform shim that forces per-line pipeline mode (workaround for
; the §4.6 VDP register $0B propagation bug — see DEFERRED_WORK.md).
;
; Tuning (rocking macro):
;   speed: phase advance per frame.  1 = default   3 = stormy   0 = static tilt

; -- shared deform table --
DeformTable_Rocking:
    deform_table_sine AMPLITUDE=20, PERIOD=64

; ----------------------------------------------------------------------
; rocking — emit a per-column V-scroll rocking config
; ----------------------------------------------------------------------
rocking macro speed,shift
    if "speed" = ""
RK_SPEED := 1
    else
RK_SPEED := speed
    endif
    if "shift" = ""
RK_SHIFT := 0
    else
RK_SHIFT := shift
    endif

    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Zero, \
                     vDeformBg=DeformTable_Rocking, \
                     vDeformSpeedBg=RK_SPEED, \
                     vDeformShiftBg=RK_SHIFT
        band 0, FACTOR_1, FACTOR_0       ; BG H-locked (kills leftmost-column artifact)
    parallax_section_end
    endm

; -- pre-named variants --
ParallaxConfig_Rocking_Slow:
    rocking speed=0                      ; static tilt (no animation)

ParallaxConfig_Rocking:
    rocking speed=1                      ; default

ParallaxConfig_Rocking_Fast:
    rocking speed=3                      ; stormy
