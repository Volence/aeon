; ======================================================================
; DacSampleTable — 1-based DAC sample id -> 9-byte DacSample descriptor
; (struct in sound_constants.asm). ids: 1=temp_blip 2=kick 3=snare 4=hat,
; then the 6 S3K HCZ2 drums (5=s3k_kick .. 10=s3k_floortom, matching
; tools/smps_import.py HCZ2_DAC_REMAP). All bank/ptr/len values are the
; build-time SND_* constants from data/sound/dac_samples.asm. rate/loop_ofs
; are 0 (the 1B FILL loop drives the rate via the loop trip-time; one-shot:
; the producer exhausts into DRAINING_TAIL). ds_codec = 0 (raw 8-bit PCM;
; the reserved codec-selector slot).
;
; BANKED (budget A.2, 2026-07-02): co-located at the engine-table head of
; the song/SFX bank (main.asm `cpu z80 / phase 08000h` block), so it costs
; ZERO against the resident Z80-code ceiling. The label equals its $8000-
; window pointer (Snd_DacLookup's pointer math is unchanged).
;
; PLACEMENT CONSTRAINT — this table must be readable under the SONG bank,
; NOT a DAC sample bank: the descriptor fields are read by Snd_StartSample
; (z80_sound_driver.asm), whose $E2 call context runs MID-Sequencer_Frame
; where the window holds SND_SONG_BANK and MUST stay there (a switch would
; corrupt the rest of that frame's song-stream reads — the B2 stash-only
; rule). The DAC samples themselves span TWO banks (blip bank != drums
; bank, data/sound/dac_samples.asm), so there is no single "sample bank"
; to host the table anyway; each descriptor's ds_bank names its payload
; bank and the B1/B3/B4 brackets latch it for the FILL.
;
; BANK GUARANTEES at the read sites (both == THIS bank today):
;   * $E2 (Seq_HookDac -> Snd_StartSample): window = SND_SONG_BANK (B1),
;     and every song lives in this bank (song_table.asm asserts).
;   * mailbox SND_REQ_SAMPLE (SndDrv_PollMailbox -> Snd_StartSample): the
;     sample block does an explicit SetBank(SND_ENGINE_TABLE_BANK) before
;     the lookup (this path has no ambient guarantee — streaming ticks
;     leave the sample bank in the window, cold-boot ISRs bank 0).
; ======================================================================
DacSampleTable:
        ; id 1 = temp_blip
        db      SND_BLIP_BANK            ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (codec selector; 0 = raw 8-bit PCM)
        dw      SND_BLIP_PTR             ; ds_ptr (little-endian dw)
        dw      SND_BLIP_LEN             ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 2 = kick
        db      SND_KICK_BANK            ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_KICK_PTR             ; ds_ptr
        dw      SND_KICK_LEN             ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 3 = snare
        db      SND_SNARE_BANK           ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_SNARE_PTR            ; ds_ptr
        dw      SND_SNARE_LEN            ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 4 = hat
        db      SND_HAT_BANK             ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_HAT_PTR              ; ds_ptr
        dw      SND_HAT_LEN              ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; --- S3K HCZ2 drums (Phase 5; ids match tools/smps_import.py HCZ2_DAC_REMAP) ---
        ; id 5 = s3k_kick
        db      SND_S3K_KICK_BANK        ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_KICK_PTR         ; ds_ptr
        dw      SND_S3K_KICK_LEN         ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 6 = s3k_snare
        db      SND_S3K_SNARE_BANK       ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_SNARE_PTR        ; ds_ptr
        dw      SND_S3K_SNARE_LEN        ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 7 = s3k_hitom
        db      SND_S3K_HITOM_BANK       ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_HITOM_PTR        ; ds_ptr
        dw      SND_S3K_HITOM_LEN        ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 8 = s3k_midtom
        db      SND_S3K_MIDTOM_BANK      ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_MIDTOM_PTR       ; ds_ptr
        dw      SND_S3K_MIDTOM_LEN       ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 9 = s3k_lowtom
        db      SND_S3K_LOWTOM_BANK      ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_LOWTOM_PTR       ; ds_ptr
        dw      SND_S3K_LOWTOM_LEN       ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
        ; id 10 = s3k_floortom
        db      SND_S3K_FLOORTOM_BANK    ; ds_bank
        db      0                        ; ds_rate (reserved)
        db      0                        ; ds_codec (raw 8-bit PCM)
        dw      SND_S3K_FLOORTOM_PTR     ; ds_ptr
        dw      SND_S3K_FLOORTOM_LEN     ; ds_length
        dw      0                        ; ds_loop_ofs (reserved; 0 = one-shot)
DacSampleTable_End:

        if (DacSampleTable_End-DacSampleTable) <> DAC_SAMPLE_COUNT*DacSample_len
          fatal "DacSampleTable wrong size for DAC_SAMPLE_COUNT"
        endif
