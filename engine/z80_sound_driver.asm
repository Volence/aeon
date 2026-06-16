; ======================================================================
; engine/z80_sound_driver.asm — Z80-autonomous sound driver (Phase 1)
; Assembled inline in 68k ROM via cpu z80 / phase 0. Loaded into Z80 RAM
; over the idle program at boot when SOUND_DRIVER_ENABLED is defined.
; ======================================================================
Z80_Sound_Start:
        save
        cpu z80
        phase 0

; --- entry ---
SndDrv_Init:
        ; Interrupt-free driver: `di` held forever. The 68k does not pulse the Z80
        ; /INT, and the YM2612 timer overflow is NOT wired to the Z80 interrupt line
        ; on the Genesis (timers can only be polled) — so no `im`/`ei` is needed.
        di
        ld      sp, 1FFEh                ; stack top (see z80-ram-map sub-design)

        ; YM ready: wait for busy flag (bit7 of $4000) to clear, then DAC off
        ld      ix, SND_Z80_YM_A0        ; ix = $4000
.wait_ym:
        bit     7, (ix+0)
        jr      nz, .wait_ym
        ld      (ix+0), SND_REG_DAC_ENABLE   ; select reg $2B
        ld      (ix+1), 00h                  ; DAC mode OFF at init

        ; --- start YM Timer A as the scheduler timebase ---
        ; Value computed at build time from SND_TEMPO_TPF (ticks/frame). reg $24 =
        ; N>>2 (bits 9..2), reg $25 = N&3 (bits 1..0) of the 10-bit Timer A value.
        ld      (ix+0), SND_REG_TIMER_A_HI   ; reg $24
        ld      (ix+1), SND_TIMERA_HI
        ld      (ix+0), SND_REG_TIMER_A_LO   ; reg $25
        ld      (ix+1), SND_TIMERA_LO
        ld      (ix+0), SND_REG_TIMER_CTRL   ; reg $27
        ld      (ix+1), 005h                 ; bit0 Load A | bit2 Enable-A flag

        ; clear request slots + status region
        xor     a
        ld      (SND_REQ_PING), a
        ld      (SND_REQ_SAMPLE), a
        ld      (SND_REQ_MUSIC), a
        ld      (SND_REQ_SFX), a
        ld      (SND_STAT_PING_ECHO), a
        ld      (SND_STAT_ACK_COUNT), a
        ld      (SND_STAT_TICK), a

        ; --- generate a 256-byte sawtooth test sample at SND_TEST_SAMPLE ---
        ld      hl, SND_TEST_SAMPLE
        ld      b, 0                     ; 0 -> 256 iterations via djnz
        xor     a
.gen_sample:
        ld      (hl), a
        inc     hl
        add     a, 8                     ; sawtooth step
        djnz    .gen_sample
        xor     a
        ld      (SND_STAT_DAC_ACTIVE), a ; DAC-active status = 0

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

; --- main loop: cooperative scheduler (poll between Timer A ticks) ---
; SndDrv_Init falls through to here. SndDrv_PollMailbox is defined AFTER this
; infinite loop (not between init and here) so init never falls into a `ret`-
; terminated routine with no matching `call` (that would return to $0000).
SndDrv_Main:
        call    SndDrv_PollMailbox       ; background work between ticks
        call    SndDrv_FeedDAC           ; feed one DAC byte if a sample is active
        ld      a, (ix+0)                ; read YM status ($4000)
        bit     0, a                     ; Timer A overflow?
        jr      z, SndDrv_Main           ; not yet -> keep polling
        ; --- timer tick ---
        ld      (ix+0), SND_REG_TIMER_CTRL   ; reg $27
        ld      (ix+1), 015h                 ; bit4 Reset-A flag | reload (Load|Enable)
        ld      a, (SND_STAT_TICK)
        inc     a
        ld      (SND_STAT_TICK), a
        jr      SndDrv_Main

; --- poll the per-type request slots; act on any nonzero slot, then clear it ---
; (Reached only via `call` from SndDrv_Main — never by fall-through.)
SndDrv_PollMailbox:
        ; --- ping request? echo the value back ---
        ld      a, (SND_REQ_PING)
        or      a
        jr      z, .no_ping
        ld      (SND_STAT_PING_ECHO), a  ; echo the request value
        xor     a
        ld      (SND_REQ_PING), a        ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_ping:
        ; --- sample request? (Phase 1: any nonzero id -> the test tone) ---
        ld      a, (SND_REQ_SAMPLE)
        or      a
        ret     z                        ; nothing else pending
        ld      hl, SND_TEST_SAMPLE
        ld      (SND_PLAY_PTR), hl
        ld      hl, SND_TEST_SAMPLE_LEN
        ld      (SND_PLAY_LEN), hl
        ld      (ix+0), SND_REG_DAC_ENABLE   ; reg $2B
        ld      (ix+1), 80h                  ; DAC mode ON (bit7)
        ld      a, 1
        ld      (SND_PLAY_ACTIVE), a
        ld      (SND_STAT_DAC_ACTIVE), a
        xor     a
        ld      (SND_REQ_SAMPLE), a      ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; --- feed one DAC byte if a sample is active; loops the sample (test tone) ---
; (Reached only via `call` from SndDrv_Main — never by fall-through.)
SndDrv_FeedDAC:
        ld      a, (SND_PLAY_ACTIVE)
        or      a
        ret     z                        ; not playing
        ld      hl, (SND_PLAY_PTR)
        ld      a, (hl)
        inc     hl
        ld      (ix+0), SND_REG_DAC_DATA ; reg $2A
        ld      (ix+1), a                ; write sample byte
        ld      (SND_PLAY_PTR), hl
        ld      b, SND_DAC_RATE          ; per-sample rate delay
.dac_delay:
        djnz    .dac_delay
        ld      hl, (SND_PLAY_LEN)
        dec     hl
        ld      (SND_PLAY_LEN), hl
        ld      a, h
        or      l
        ret     nz                       ; more samples remain
        ld      hl, SND_TEST_SAMPLE      ; exhausted -> loop (continuous test tone)
        ld      (SND_PLAY_PTR), hl
        ld      hl, SND_TEST_SAMPLE_LEN
        ld      (SND_PLAY_LEN), hl
        ret

        ; Pad the blob to an EVEN length. The boot loader copies it byte-wise
        ; then does word/long (a5)+ reads on the data that follows; an odd-length
        ; blob leaves a5 on an odd address -> 68000 address error at boot.
        ; Under `phase 0`, `$` is the current blob length.
        if ($ & 1) <> 0
          db 0
        endif

        dephase
        restore
Z80_Sound_End:

Z80_SOUND_SIZE = Z80_Sound_End - Z80_Sound_Start

        ; code must not grow into the playback-state region
        if Z80_SOUND_SIZE > SND_STATE_BASE
          fatal "Z80 sound driver code (\{Z80_SOUND_SIZE} bytes) overruns state region at \{SND_STATE_BASE}"
        endif
