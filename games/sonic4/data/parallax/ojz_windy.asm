; data/parallax/ojz_windy.asm — F3 fixture: single-band BG H-deformation
;
; Whole plane B waves at full sine amplitude (±96 px). Single band layout
; matches SkyHaze's BG factor (FACTOR_1_4) so transitioning between Sec0
; (SkyHaze) and Sec1 (this) doesn't slide the BG horizontally — only the
; deform amplitude lerps.

; Sine table: ±96 px amplitude. PERIOD=64 → half-cycle across 32 lines.
DeformTable_OJZ_Calm:
    deform_table_sine AMPLITUDE=96, PERIOD=64

ParallaxConfig_OJZ_Windy:
    parallax_section layerMask=$01, vFactorBg=15, vCenter=0, vOffset=0, \
                     deformBg=DeformTable_OJZ_Calm, deformSpeedBg=1
BAND_DSB := 0                          ; full ±96 px wave (no shift)
        band 0, FACTOR_1, FACTOR_1_4   ; FG full speed, BG quarter (matches SkyHaze)
    parallax_section_end
