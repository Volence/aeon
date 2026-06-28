; ======================================================================
; data/sound/dac_samples.asm — ROM-resident DAC sample data (Phase 1B)
; TEMP placeholder sample for 1B engine bring-up. Real sample content is
; TBD (user-driven) — these are raw 8-bit unsigned PCM (centered $80). The
; Z80 streams them through its $8000-$FFFF window, selected by the 9-bit
; bank latch at $6000.
; ======================================================================

        ; Bank-aligned so the sample never crosses a 32KB boundary, so a single
        ; bank id covers the whole blob and the Z80 never re-banks mid-sample.
        ; `align $8000` snaps the PC to a 32KB (bank) start; wastes <32KB once.
        ; (AS in this build does not provide `cnop`; `align <pow2>` is the
        ; codebase-standard alignment directive — see `align 2` in main.asm.)
        align   $8000                                     ; align to a bank start (no boundary cross)
Dac_Temp_Blip:
        BINCLUDE "data/sound/temp_blip.bin"
Dac_Temp_Blip_End:

        if (Dac_Temp_Blip >> 15) <> ((Dac_Temp_Blip_End-1) >> 15)
          fatal "Dac_Temp_Blip crosses a 32KB bank boundary"
        endif

; --- build-time constants the driver uses directly (single 1B sample) ---
; bank id    = (addr & $7F8000) >> 15   — the 9-bit value latched at $6000
; window ptr = (addr & $7FFF) | $8000   — Z80 address within the $8000 window
SND_BLIP_BANK           = (Dac_Temp_Blip & $7F8000) >> 15
SND_BLIP_PTR            = (Dac_Temp_Blip & $7FFF) | $8000
SND_BLIP_LEN            = Dac_Temp_Blip_End - Dac_Temp_Blip

        ; DAC sample length must be > 0 and fit the $8000 window. The 1:1 FILL reads
        ; ONE byte/pass and decrements ds_length by 1, exhausting at exactly 0 for ANY
        ; length (odd or even) — so there is no even-length requirement. A ZERO length
        ; would run away ~64KB; this catches it at build.
        if (SND_BLIP_LEN = 0) || (SND_BLIP_LEN >= $8000)
          fatal "DAC sample length (\{SND_BLIP_LEN}) must be > 0 and < $8000"
        endif

; ======================================================================
; Shared RAW 8-bit PCM drum payload bank
; All drums (the 3 original kick/snare/hat + the 6 S3K HCZ2 drums = 9 samples,
; ~30908 bytes) are packed into one $8000-aligned bank so a single bank
; id covers the whole region and FILL never re-banks mid-sample. Payload is
; RAW 8-bit unsigned PCM (the YM2612 DAC is 8-bit, $80 = silence) — the DPCM
; codec was dropped for drums (the shared bank made compression moot; raw is
; higher-rate + cleaner; see the 2026-06-25 spec amendment). ds_length is the
; raw byte count = sample count; the 1:1 FILL reads 1 byte/pass and exhausts at
; len==0 for ANY length (odd or even) — so no even-length requirement, just
; 0 < len < $8000 (asserted below).
; ======================================================================
        align   $8000
Dac_SharedBank_Start:
Dac_Kick:
        BINCLUDE "data/sound/dac/kick.pcm"
Dac_Kick_End:
Dac_Snare:
        BINCLUDE "data/sound/dac/snare.pcm"
Dac_Snare_End:
Dac_Hat:
        BINCLUDE "data/sound/dac/hat.pcm"
Dac_Hat_End:
; --- S3K HCZ2 drums (Phase 5) — raw 8-bit PCM, pitch baked in at the engine's
; fixed ~18356 Hz DAC rate (tools/import_s3k_dac.py). The 4 toms are 82-85.wav at
; the REAL S3K rate multipliers (1.0/0.80/0.67/0.58 from sonic3k.macros.asm
; DAC_82..DAC_85_Setup), so they pitch distinctly. They share this $8000 bank with
; the existing kick/snare/hat (9 samples total = 30908 bytes < $8000, fits). ---
Dac_S3K_Snare:
        BINCLUDE "data/sound/dac/s3k_snare.pcm"
Dac_S3K_Snare_End:
Dac_S3K_HiTom:
        BINCLUDE "data/sound/dac/s3k_hitom.pcm"
Dac_S3K_HiTom_End:
Dac_S3K_MidTom:
        BINCLUDE "data/sound/dac/s3k_midtom.pcm"
Dac_S3K_MidTom_End:
Dac_S3K_LowTom:
        BINCLUDE "data/sound/dac/s3k_lowtom.pcm"
Dac_S3K_LowTom_End:
Dac_S3K_FloorTom:
        BINCLUDE "data/sound/dac/s3k_floortom.pcm"
Dac_S3K_FloorTom_End:
Dac_S3K_Kick:
        BINCLUDE "data/sound/dac/s3k_kick.pcm"
Dac_S3K_Kick_End:

        ; No sample may straddle a 32KB window boundary (FILL never re-banks mid-sample).
        ; The whole shared bank spans Dac_Kick .. the LAST sample's end.
        if (Dac_Kick >> 15) <> ((Dac_S3K_Kick_End-1) >> 15)
          fatal "shared DAC bank crosses a 32KB boundary"
        endif

SND_KICK_BANK   = (Dac_Kick  & $7F8000) >> 15
SND_KICK_PTR    = (Dac_Kick  & $7FFF) | $8000
SND_KICK_LEN    = Dac_Kick_End  - Dac_Kick

SND_SNARE_BANK  = (Dac_Snare & $7F8000) >> 15
SND_SNARE_PTR   = (Dac_Snare & $7FFF) | $8000
SND_SNARE_LEN   = Dac_Snare_End - Dac_Snare

SND_HAT_BANK    = (Dac_Hat   & $7F8000) >> 15
SND_HAT_PTR     = (Dac_Hat   & $7FFF) | $8000
SND_HAT_LEN     = Dac_Hat_End  - Dac_Hat

; --- S3K HCZ2 drum constants (same bank/ptr/len convention as above) ---
SND_S3K_SNARE_BANK     = (Dac_S3K_Snare    & $7F8000) >> 15
SND_S3K_SNARE_PTR      = (Dac_S3K_Snare    & $7FFF) | $8000
SND_S3K_SNARE_LEN      = Dac_S3K_Snare_End    - Dac_S3K_Snare

SND_S3K_HITOM_BANK     = (Dac_S3K_HiTom    & $7F8000) >> 15
SND_S3K_HITOM_PTR      = (Dac_S3K_HiTom    & $7FFF) | $8000
SND_S3K_HITOM_LEN      = Dac_S3K_HiTom_End    - Dac_S3K_HiTom

SND_S3K_MIDTOM_BANK    = (Dac_S3K_MidTom   & $7F8000) >> 15
SND_S3K_MIDTOM_PTR     = (Dac_S3K_MidTom   & $7FFF) | $8000
SND_S3K_MIDTOM_LEN     = Dac_S3K_MidTom_End   - Dac_S3K_MidTom

SND_S3K_LOWTOM_BANK    = (Dac_S3K_LowTom   & $7F8000) >> 15
SND_S3K_LOWTOM_PTR     = (Dac_S3K_LowTom   & $7FFF) | $8000
SND_S3K_LOWTOM_LEN     = Dac_S3K_LowTom_End   - Dac_S3K_LowTom

SND_S3K_FLOORTOM_BANK  = (Dac_S3K_FloorTom & $7F8000) >> 15
SND_S3K_FLOORTOM_PTR   = (Dac_S3K_FloorTom & $7FFF) | $8000
SND_S3K_FLOORTOM_LEN   = Dac_S3K_FloorTom_End - Dac_S3K_FloorTom

SND_S3K_KICK_BANK      = (Dac_S3K_Kick     & $7F8000) >> 15
SND_S3K_KICK_PTR       = (Dac_S3K_Kick     & $7FFF) | $8000
SND_S3K_KICK_LEN       = Dac_S3K_Kick_End     - Dac_S3K_Kick

        ; Each drum length must be > 0 and fit the $8000 window (the 1:1 FILL handles
        ; any length; a zero length would run away, which this catches at build).
        if (SND_KICK_LEN = 0) || (SND_KICK_LEN >= $8000) || (SND_SNARE_LEN = 0) || (SND_SNARE_LEN >= $8000) || (SND_HAT_LEN = 0) || (SND_HAT_LEN >= $8000)
          fatal "raw DAC drum length must be > 0 and < $8000"
        endif

        if (SND_S3K_SNARE_LEN = 0) || (SND_S3K_SNARE_LEN >= $8000) || (SND_S3K_HITOM_LEN = 0) || (SND_S3K_HITOM_LEN >= $8000) || (SND_S3K_MIDTOM_LEN = 0) || (SND_S3K_MIDTOM_LEN >= $8000) || (SND_S3K_LOWTOM_LEN = 0) || (SND_S3K_LOWTOM_LEN >= $8000) || (SND_S3K_FLOORTOM_LEN = 0) || (SND_S3K_FLOORTOM_LEN >= $8000) || (SND_S3K_KICK_LEN = 0) || (SND_S3K_KICK_LEN >= $8000)
          fatal "S3K DAC drum length must be > 0 and < $8000"
        endif
