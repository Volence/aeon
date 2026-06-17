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
