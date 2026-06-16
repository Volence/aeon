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

; --- main loop (Phase 1 shell: nothing yet) ---
SndDrv_Main:
        jr      SndDrv_Main

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
