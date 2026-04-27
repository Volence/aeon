; engine/parallax_macros.inc — Authoring API for §4.6 parallax
;
; Usage:
;   ParallaxConfig_Foo:
;     parallax_section LAYER_MASK=$1F, V_FACTOR_BG=3, V_CENTER=0, V_OFFSET=0
;       band 0,  FACTOR_1, FACTOR_1_8        ; top_cell, factor_a, factor_b
;       band 4,  FACTOR_1, FACTOR_1_4
;     parallax_section_end
;
; Per-band optional fields read from globals (set via :=) before each band:
;   BAND_DSA, BAND_DSB    — deform amplitude shifts (15 = no deform on band)
;   BAND_PHASE            — 0..255, sample-index offset for desync
; parallax_section seeds these to defaults from DEFORM_SHIFT_DEFAULT and 0.
;
; Factor encoding (24-bit packed):
;   bits 0-3: shift1 (0..14, 15 = "term zero" → factor = 0 / locked)
;   bits 4-7: shift2 (0..14, 15 = "single-term factor")
;   bit  8:   op    (0 = ADD second term, 1 = SUB)

; ----------------------------------------------------------------------
; packed — build-time factor encoder (used to define FACTOR_* equates)
; ----------------------------------------------------------------------
packed function s1,s2,op, ((op&1)<<8) | ((s2&15)<<4) | (s1&15)

; ----------------------------------------------------------------------
; Pre-defined factor equates — fractions p/q where q is a power of 2
; and decomposition uses ≤2 shift-add ops.
; ----------------------------------------------------------------------
FACTOR_LOCKED equ $0FF                  ; s1=15 → factor = 0 ("locked layer")
FACTOR_0      equ FACTOR_LOCKED         ; alias
FACTOR_1      equ packed(0,15,0)        ; camX
FACTOR_1_2    equ packed(1,15,0)        ; camX>>1
FACTOR_1_4    equ packed(2,15,0)        ; camX>>2
FACTOR_1_8    equ packed(3,15,0)        ; camX>>3
FACTOR_1_16   equ packed(4,15,0)        ; camX>>4
FACTOR_1_32   equ packed(5,15,0)        ; camX>>5
FACTOR_3_4    equ packed(0,2,1)         ; camX - camX>>2
FACTOR_3_8    equ packed(2,3,0)         ; camX>>2 + camX>>3
FACTOR_3_16   equ packed(3,4,0)         ; camX>>3 + camX>>4
FACTOR_5_8    equ packed(1,3,0)         ; camX>>1 + camX>>3
FACTOR_5_16   equ packed(2,4,0)         ; camX>>2 + camX>>4
FACTOR_7_8    equ packed(0,3,1)         ; camX - camX>>3
FACTOR_7_16   equ packed(1,4,1)         ; camX>>1 - camX>>4
FACTOR_15_16  equ packed(0,4,1)         ; camX - camX>>4

; ----------------------------------------------------------------------
; parallax_section — open a parallax_config record
;
; AS rejects underscores in macro parameter names, so the user-facing
; keyword form uses camelCase. Required: layerMask, vFactorBg, vCenter,
; vOffset. Optional with defaults: vFactorFg=0, transition=0, deformFg=0,
; deformBg=0, deformSpeedFg=1, deformSpeedBg=1, vDeformBg=0,
; vDeformSpeedBg=0, vDeformShiftBg=4, deformShiftDefault=4.
;
; Example:
;   parallax_section layerMask=$1F, vFactorBg=3, vCenter=128, vOffset=0, \
;                    deformBg=DeformTable_OJZ_Calm, deformSpeedBg=1
; ----------------------------------------------------------------------
parallax_section macro layerMask,vFactorBg,vCenter,vOffset,vFactorFg,transition,deformFg,deformBg,deformSpeedFg,deformSpeedBg,vDeformBg,vDeformSpeedBg,vDeformShiftBg,deformShiftDefault
    ; required fields — empty string check
    if "layerMask" = ""
        fatal "parallax_section: layerMask required"
    endif
    if "vFactorBg" = ""
        fatal "parallax_section: vFactorBg required"
    endif
    if "vCenter" = ""
        fatal "parallax_section: vCenter required"
    endif
    if "vOffset" = ""
        fatal "parallax_section: vOffset required"
    endif

    ; defaults for optional fields
    if "vFactorFg" = ""
P_VFG := 0
    else
P_VFG := vFactorFg
    endif
    if "transition" = ""
P_TRANS := 0
    else
P_TRANS := transition
    endif
    if "deformFg" = ""
P_DFG := 0
    else
P_DFG := deformFg
    endif
    if "deformBg" = ""
P_DBG := 0
    else
P_DBG := deformBg
    endif
    if "deformSpeedFg" = ""
P_DSPDFG := 1
    else
P_DSPDFG := deformSpeedFg
    endif
    if "deformSpeedBg" = ""
P_DSPDBG := 1
    else
P_DSPDBG := deformSpeedBg
    endif
    if "vDeformBg" = ""
P_VDBG := 0
    else
P_VDBG := vDeformBg
    endif
    if "vDeformSpeedBg" = ""
P_VDSPDBG := 0
    else
P_VDSPDBG := vDeformSpeedBg
    endif
    if "vDeformShiftBg" = ""
P_VDSHIFTBG := 4
    else
P_VDSHIFTBG := vDeformShiftBg
    endif
    if "deformShiftDefault" = ""
P_DSDEFAULT := 4
    else
P_DSDEFAULT := deformShiftDefault
    endif

    ; section state
pscBandCount := 0
pscLastCellY   := -1
pscStart      := *

    ; per-band defaults (caller can override before each band via :=)
BAND_DSA   := P_DSDEFAULT
BAND_DSB   := P_DSDEFAULT
BAND_PHASE := 0

    ; emit 28-byte header (band_count patched by parallax_section_end)
    dc.b 0
    dc.b vFactorBg, P_VFG, layerMask
    dc.w vCenter, vOffset
    dc.b P_TRANS, P_DSPDFG, P_DSPDBG, 0
    dc.l P_DFG, P_DBG
    dc.l P_VDBG
    dc.b P_VDSPDBG, P_VDSHIFTBG
    dc.b 0, 0
    endm

; ----------------------------------------------------------------------
; band — emit one band_entry record
; Positional: top_cell, factor_a, factor_b (named-equate FACTOR_* values)
; Reads BAND_DSA, BAND_DSB, BAND_PHASE from globals (settable via :=)
; ----------------------------------------------------------------------
band macro cellY,factA,factB
    if pscBandCount >= MAX_PARALLAX_BANDS
        fatal "parallax: more than \{MAX_PARALLAX_BANDS} bands"
    endif
    if (cellY) < 0
        fatal "parallax band: cellY=\{cellY} negative"
    endif
    if (cellY) > 27
        fatal "parallax band: cellY=\{cellY} out of range 0..27"
    endif
    if (cellY) <= pscLastCellY
        fatal "parallax band: cellY=\{cellY} not strictly after previous cellY=\{pscLastCellY}"
    endif
pscLastCellY := (cellY)

    dc.b cellY
    dc.b (factA) & 15                          ; s1
    dc.b ((factA) >> 4) & 15                   ; s2
    dc.b ((factA) >> 8) & 1                    ; op
    dc.b (factB) & 15
    dc.b ((factB) >> 4) & 15
    dc.b ((factB) >> 8) & 1
    dc.b BAND_DSA
    dc.b BAND_DSB
    dc.b BAND_PHASE

pscBandCount := pscBandCount + 1
    endm

; ----------------------------------------------------------------------
; parallax_section_end — close a parallax_config record
; Patches the band_count byte at the start of the header.
; ----------------------------------------------------------------------
parallax_section_end macro
    if pscBandCount = 0
        fatal "parallax: section has no bands"
    endif
    if pscLastCellY > 27
        fatal "parallax: last band TOP=\{pscLastCellY} exceeds 27"
    endif

    ; patch band_count byte at offset 0 of the section header
pscEndPos := *
    org pscStart
    dc.b pscBandCount
    org pscEndPos
    endm

; ----------------------------------------------------------------------
; Self-test (gated by __PARALLAX_MACRO_SELFTEST__)
; ----------------------------------------------------------------------
    ifdef __PARALLAX_MACRO_SELFTEST__
ParallaxConfig_SelfTest:
    parallax_section layerMask=$1F, vFactorBg=3, vCenter=128, vOffset=0
        band 0,  FACTOR_1, FACTOR_1_8
        band 4,  FACTOR_1, FACTOR_1_4
        band 10, FACTOR_1, FACTOR_3_8
        band 14, FACTOR_1, FACTOR_1_2
        band 20, FACTOR_1, FACTOR_1
    parallax_section_end

    ; Expected: 28 (header) + 5 × 10 (bands) = 78 bytes
    if (* - ParallaxConfig_SelfTest) <> 78
        error "parallax_section selftest size mismatch: got \{*-ParallaxConfig_SelfTest}, expected 78"
    endif
    endif
