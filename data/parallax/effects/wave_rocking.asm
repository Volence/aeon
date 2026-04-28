; data/parallax/effects/wave_rocking.asm — reusable parallax effect
;
; Visual: plane B rocks/sways like a boat deck or floating platform. A
; sine wave traveling across the 20 screen columns produces a continuous
; rolling motion. Good for ocean horizons, levitating arenas, or anything
; that needs a feeling of unsteady ground.
;
; Mechanism: per-column V-scroll sampling a 256-byte sine table. Each of
; the 20 columns gets its own V-offset; vDeformSpeedBg=1 advances the
; phase one step per frame so the wave appears to travel sideways.
;
; AMPLITUDE=20, PERIOD=64 → ±20 px peak shift, 4 wave cycles across the
; table (visible columns sweep through ~5/16 of one cycle). vDeformShiftBg=0
; means full amplitude pass-through.
;
; Plane B HScroll locked (factor_b = FACTOR_0) to avoid the documented
; Genesis VDP "leftmost partial column" artifact (see parallax.asm
; Vscroll_Write header for the silicon-level explanation).
;
; Plane A unaffected (no deform_table_fg, no v_deform applied to FG since
; per-column V uses camY for FG_V).
;
; DEPENDENCY: requires DeformTable_Zero from data/parallax/ojz_default.asm
; as the H-deform shim that forces per-line pipeline mode (workaround for
; the §4.6 VDP register $0B propagation bug — see DEFERRED_WORK.md).
;
; Usage: include this file from main.asm AFTER ojz_default.asm, then point
; a section's sec_parallax_config at ParallaxConfig_WaveRocking.

DeformTable_WaveRocking:
    deform_table_sine AMPLITUDE=20, PERIOD=64

ParallaxConfig_WaveRocking:
    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_Zero, \
                     vDeformBg=DeformTable_WaveRocking, vDeformSpeedBg=1, \
                     vDeformShiftBg=0
        band 0, FACTOR_1, FACTOR_0      ; BG H-locked (kills leftmost-column artifact)
    parallax_section_end
