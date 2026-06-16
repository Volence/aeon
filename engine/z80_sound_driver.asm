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

        ; --- fill the ring with a sawtooth (interim: RAM source until Task 4) ---
        ld      hl, SND_RING_BASE
        ld      b, 0                     ; 256 bytes
        xor     a
.gen_ring:
        ld      (hl), a
        inc     hl
        add     a, 8                     ; sawtooth step
        djnz    .gen_ring
        xor     a
        ld      (SND_RING_RD), a         ; ring read ptr low byte = 0 -> $1700
        ld      (SND_STAT_DAC_ACTIVE), a ; start with DAC inactive (play request enables)

        ; --- generate a 1KB source waveform at $1800 (interim RAM source) ---
        ; A slower ramp than the 256B ring so the waveform spans >ring -> proves
        ; the producer genuinely streams from a source longer than the ring.
        ld      hl, 1800h
        ld      bc, 0400h                ; 1024 bytes
        xor     a
.gen_src:
        ld      (hl), a
        inc     hl
        add     a, 2                     ; slower ramp than the 256B ring
        ld      d, a                     ; preserve ramp value across the bc test
        dec     bc                       ; advance count (does not set flags)
        ld      a, b
        or      c                        ; Z set when bc == 0 (last flag op before jr)
        ld      a, d                     ; restore ramp value (ld does not touch flags)
        jr      nz, .gen_src
        ; init stream pointers: source ptr=$1800, remaining=1024, fill ptr=0
        ld      hl, 1800h
        ld      (SND_ROM_PTR), hl
        ld      hl, 0400h
        ld      (SND_ROM_LEN), hl
        xor     a
        ld      (SND_RING_WR), a

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

; --- main loop: cooperative scheduler (poll between Timer A ticks) ---
; SndDrv_Init falls through to here. SndDrv_PollMailbox is defined AFTER this
; infinite loop (not between init and here) so init never falls into a `ret`-
; terminated routine with no matching `call` (that would return to $0000).
SndDrv_Main:
        call    SndDrv_PollMailbox       ; background work between ticks
        call    SndDrv_DrainDAC          ; drain one ring byte to the DAC if active
        call    SndDrv_FillRing          ; top up the ring from the RAM source (2:1)
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
        ; sample request -> enable DAC mode, start draining the ring
        ld      (ix+0), SND_REG_DAC_ENABLE   ; reg $2B
        ld      (ix+1), 80h                  ; DAC mode ON
        ld      a, 1
        ld      (SND_STAT_DAC_ACTIVE), a
        xor     a
        ld      (SND_REQ_SAMPLE), a          ; clear slot
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; --- drain one ring byte to the DAC (cycle-balanced); ring read ptr in RAM ---
; (Reached only via `call` from SndDrv_Main — never by fall-through.)
SndDrv_DrainDAC:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ret     z
        ld      a, (SND_RING_RD)         ; ring read low byte
        ld      l, a
        ld      h, SND_RING_PAGE         ; hl = $17xx
        ld      a, (hl)                  ; sample byte
        ld      (ix+0), SND_REG_DAC_DATA ; reg $2A
        ld      (ix+1), a                ; -> DAC
        inc     l                        ; advance (wraps within page)
        ld      a, l
        ld      (SND_RING_RD), a
        ld      b, SND_DAC_RATE          ; balanced rate delay (controller tunes)
.rate:  djnz    .rate
        ret

; --- top up the ring from the RAM source; ~2:1 ahead, never lap read ptr ---
; (Reached only via `call` from SndDrv_Main — never by fall-through.)
; Page-aligned ring (MegaPCM trick): RD/WR are low bytes, the high byte is the
; page, so distance math is a single byte op mod 256. Guard: stop when the free
; gap (rd - wr) & $FF drops below the guard band, so WR can never lap RD (which
; would clobber un-drained samples). When WR==RD the gap reads 0 -> we wait for
; the drain to open a gap (correct: ring is full of the pre-fill at boot).
SndDrv_FillRing:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ret     z                        ; idle -> nothing to stream
        ld      b, 2                     ; try to add up to 2 bytes (2:1 fill-ahead)
.fill1:
        ; ring-full guard: free = (rd - wr) & $FF ; if free <= guard, stop
        ld      a, (SND_RING_RD)
        ld      c, a
        ld      a, (SND_RING_WR)
        sub     c                        ; a = (wr - rd) & $FF
        neg                              ; a = (rd - wr) & $FF  = free space mod 256
        cp      4                        ; guard band (tune)
        ret     c                        ; free < 4 -> too full -> done
        ; read one source byte
        ld      hl, (SND_ROM_PTR)
        ld      a, (hl)
        inc     hl
        ld      (SND_ROM_PTR), hl
        ; write to ring[wr]
        push    af
        ld      a, (SND_RING_WR)
        ld      l, a
        ld      h, SND_RING_PAGE
        pop     af
        ld      (hl), a
        ld      a, (SND_RING_WR)
        inc     a
        ld      (SND_RING_WR), a
        ; advance source length; loop source when exhausted
        ld      hl, (SND_ROM_LEN)
        dec     hl
        ld      (SND_ROM_LEN), hl
        ld      a, h
        or      l
        jr      nz, .next
        ld      hl, 1800h                ; loop source: reset ptr + remaining
        ld      (SND_ROM_PTR), hl
        ld      hl, 0400h
        ld      (SND_ROM_LEN), hl
.next:
        djnz    .fill1
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
