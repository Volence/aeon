; data/parallax/scenes/sky_haze.asm — composite scene using parallax_combine_split
;
; Demo of the 2-band split macro:
;   - Top band (rows 0..13): BG windy (clouds + mountains wave), FG steady.
;   - Bottom band (rows 14..27): FG haze (ground/grass wobbles), BG steady.
;
; Each effect is restricted to the half of the screen where it makes
; visual sense. Splits at row 14 — the canonical boundary between OJZ
; "sky/mountain" zones and "hills/ground" zones.
;
; This is a regional split, NOT a falloff gradient. Within the top band
; the windy wave amplitude is uniform; within the bottom band the haze
; wobble is uniform. For per-band gradient falloffs (windy's clouds-full
; / mountains-half / hills-faint / ground-none shape), hand-author with
; parallax_section directly — see scenes/windy_haze.asm.

ParallaxConfig_SkyHaze:
    parallax_combine_split splitRow=14, \
                            fgTable=DeformTable_Haze,     fgSpeed=2, fgWhere=PARALLAX_BOTTOM, \
                            bgTable=DeformTable_OJZ_Calm, bgSpeed=1, bgWhere=PARALLAX_TOP, \
                            shift=2
