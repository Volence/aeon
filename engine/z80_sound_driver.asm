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
        di
        im      1
        ld      sp, 1FFEh                ; stack top (see z80-ram-map sub-design)

        ; YM ready: wait for busy flag (bit7 of $4000) to clear, then DAC off
        ld      ix, SND_Z80_YM_A0        ; ix = $4000
.wait_ym:
        bit     7, (ix+0)
        jr      nz, .wait_ym
        ld      (ix+0), SND_REG_DAC_ENABLE   ; select reg $2B
        ld      (ix+1), 00h                  ; DAC mode OFF at init

        ; --- start YM Timer A as the scheduler timebase ---
        ld      (ix+0), SND_REG_TIMER_A_HI   ; reg $24 = Timer A high 8 bits
        ld      (ix+1), 0C0h                 ; value (research-tuned; controller measures)
        ld      (ix+0), SND_REG_TIMER_A_LO   ; reg $25 = Timer A low 2 bits
        ld      (ix+1), 000h
        ld      (ix+0), SND_REG_TIMER_CTRL   ; reg $27
        ld      (ix+1), 005h                 ; bit0 Load A | bit2 Enable-A flag

        ; clear mailbox + status region
        xor     a
        ld      (SND_MBX_CMD), a
        ld      (SND_MBX_PENDING), a
        ld      (SND_STAT_PING_ECHO), a
        ld      (SND_STAT_ACK_COUNT), a
        ld      (SND_STAT_TICK), a

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

; --- main loop: cooperative scheduler (poll between Timer A ticks) ---
; SndDrv_Init falls through to here. SndDrv_PollMailbox is defined AFTER this
; infinite loop (not between init and here) so init never falls into a `ret`-
; terminated routine with no matching `call` (that would return to $0000).
SndDrv_Main:
        call    SndDrv_PollMailbox       ; background work between ticks
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

; --- poll mailbox: consume AT MOST one pending command, then ret ---
; (Reached only via `call` from SndDrv_Main — never by fall-through.)
SndDrv_PollMailbox:
        ld      a, (SND_MBX_PENDING)
        or      a
        ret     z                        ; nothing pending -> done
        ; latch cmd + arg0, clear pending (ack), bump ack counter
        ld      a, (SND_MBX_CMD)
        ld      b, a                     ; b = cmd id
        ld      a, (SND_MBX_ARG0)
        ld      c, a                     ; c = arg0
        xor     a
        ld      (SND_MBX_PENDING), a     ; consume-ack: clear pending
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ; dispatch on cmd id
        ld      a, b
        cp      SND_CMD_PING
        ret     nz                       ; unknown cmd -> ack only
        ld      a, c
        ld      (SND_STAT_PING_ECHO), a  ; echo arg0
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
