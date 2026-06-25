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

        ; DAC sample lengths MUST be even: the FILL producer
        ; (engine/z80_sound_driver.asm) reads 2 ROM bytes/pass and decrements
        ; ds_length by 2, testing `h or l == 0` for exhaustion. An ODD length steps
        ; ...3 -> 1 -> $FFFF and NEVER hits zero, so it reads ~64KB past the sample.
        ; (Generalize this to every DacSample ds_length when the descriptor table
        ; grows beyond the single blip — see DEFERRED_WORK "DAC format revision".)
        if (SND_BLIP_LEN & 1) <> 0
          fatal "DAC sample length (\{SND_BLIP_LEN}) must be EVEN (FILL decrements by 2, tests ==0)"
        endif

; ======================================================================
; Shared RAW 8-bit PCM drum payload bank
; All three drums are packed into one $8000-aligned bank so a single bank
; id covers the whole region and FILL never re-banks mid-sample. Payload is
; RAW 8-bit unsigned PCM (the YM2612 DAC is 8-bit, $80 = silence) — the DPCM
; codec was dropped for drums (the shared bank made compression moot; raw is
; higher-rate + cleaner; see the 2026-06-25 spec amendment). ds_length is the
; raw byte count = sample count; the FILL copies 2 bytes/pass and exhausts at
; len==0, so every length MUST be EVEN (asserted below).
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

        ; No sample may straddle a 32KB window boundary (FILL never re-banks mid-sample).
        if (Dac_Kick >> 15) <> ((Dac_Hat_End-1) >> 15)
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

        ; Raw FILL copies 2 bytes/pass and tests len==0 -> every drum length must be EVEN.
        if ((SND_KICK_LEN | SND_SNARE_LEN | SND_HAT_LEN) & 1) <> 0
          fatal "raw DAC drum length must be EVEN (FILL copies 2 bytes/pass, tests ==0)"
        endif
