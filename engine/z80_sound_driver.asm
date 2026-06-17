; ======================================================================
; engine/z80_sound_driver.asm — Z80-autonomous sound driver (Phase 1)
; Assembled inline in 68k ROM via cpu z80 / phase 0. Loaded into Z80 RAM
; over the idle program at boot when SOUND_DRIVER_ENABLED is defined.
; ======================================================================
Z80_Sound_Start:
        save
        cpu z80
        phase 0

; --- reset vector + IM1 VBlank vector ---
; $0000: jump over the vector region into init.
; $0038: the Genesis hardware asserts the Z80 /INT once per VBlank; with `im 1`
; the CPU does RST 38h, vectoring here. We can't use a *nested* `phase 38h` block
; (AS `phase` only relocates label addresses, it does NOT emit the gap bytes, so
; the vector would land physically right after the jp, not at $0038). Nor does
; `ds.b` work — it's not a Z80 mnemonic in AS (error #1200). Instead we stay in
; `phase 0` and zero-fill the gap with a `rept`/`db 0`, which emits real bytes
; into the blob so the boot loader copies them and $0038 is physically the
; VBlank handler. ($ under phase 0 == the current blob offset.)
        jp      SndDrv_Init              ; $0000-$0002

        ; Zero-fill $0003..$0037 with real bytes ($00 = NOP) so the boot loader
        ; copies them and the vector below physically lands at $0038. (`ds.b` is
        ; not a Z80 mnemonic in AS — `error #1200`; a `rept` of `db 0` emits the
        ; gap explicitly. `$` under phase 0 is the current blob offset = 3 here.)
        rept    38h-$
          db    0
        endm
SndDrv_VBlank:                           ; $0038: RST 38h / IM1 VBlank vector
        jp      SndDrv_ISR_Drain         ; -> the VBlank drain handler

; --- entry ---
SndDrv_Init:
        ; 1B: the driver now runs WITH interrupts. The Genesis asserts the Z80
        ; /INT once per VBlank; `im 1` vectors that to RST 38h ($0038) where the
        ; DRAIN handler protects the DAC through the 68k's VDP/DMA window. `ei`
        ; is issued only AFTER the ring is primed (below) so no IRQ can land
        ; before the playback state is consistent.
        di
        im      1                        ; VBlank /INT -> RST 38h -> $0038
        ld      sp, 1FFEh                ; stack top (see z80-ram-map sub-design)

        ; YM ready: wait for busy flag (bit7 of $4000) to clear, then DAC off
        ld      ix, SND_Z80_YM_A0        ; ix = $4000
.wait_ym:
        bit     7, (ix+0)
        jr      nz, .wait_ym
        ld      (ix+0), SND_REG_DAC_ENABLE   ; select reg $2B
        ld      (ix+1), 00h                  ; DAC mode OFF at init

        ; (1B: YM Timer A setup REMOVED — the tempo tick was dropped from the
        ; loop, and per-frame work now lives in the VBlank ISR. The hardware
        ; VBlank /INT, not the YM timer, drives the drain.)

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
        ld      (SND_RING_WR), a         ; ring fill ptr low byte = 0
        ld      (SND_STAT_DAC_ACTIVE), a ; start with DAC inactive (play request enables)

        ; --- stream source: left INACTIVE until a play request ---
        ; (1B Task 4) The blip streams from banked ROM, not RAM. SND_ROM_PTR /
        ; SND_ROM_LEN are set up by the SND_REQ_SAMPLE handler from the
        ; build-time SND_BLIP_* constants. The old $1800 RAM source is gone.
        ; Force the first SetBank to switch: seed the cache with an impossible
        ; bank id ($FF) so the cached-no-op check never matches on the first play.
        ld      a, 0FFh
        ld      (SND_CUR_BANK), a

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

        ei                               ; ring is primed -> allow the VBlank IRQ
        ; falls into SndDrv_Main

; --- main loop: tight FILL+PLAY (1B audio path) ---
; SndDrv_Init falls through to here. Each pass: output ONE ring byte to the DAC,
; then fill TWO ROM bytes into the ring (2:1 catch-up). The FillOne ring-full guard
; no-ops the 2nd fill once the lead is recovered, so the cadence is 2:1 only while
; catching up (after the ISR drains the lead) and settles to 1:1 when the ring is
; full. This recovers the lead the VBlank drain consumes — without it the 1:1 fill
; could never refill what a long DMA frame drained, slowly starving the ring. `ei`
; opens a window for the VBlank /INT to land BETWEEN samples (never mid-fill); `di`
; then protects the banked ROM reads in SndDrv_FillOne from being interrupted by a
; bank switch.
; The mailbox poll and per-frame housekeeping moved OUT of this loop into the
; VBlank ISR (SndDrv_ISR_Drain) so the audio path stays a constant cadence.
; Helpers (FillOne, PollMailbox, ...) are defined AFTER this loop so init never
; falls into a `ret`-terminated routine with no matching `call`.
SndDrv_Main:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      z, SndDrv_Main           ; idle until a sample plays
        ei                               ; VBlank IRQ may land HERE (between samples)
        ; --- output one ring byte to the DAC ---
        ld      a, (SND_RING_RD)
        ld      l, a
        ld      h, SND_RING_PAGE
        ld      a, (hl)                  ; ring[rd]
        ld      (ix+0), SND_REG_DAC_DATA ; reg $2A
        ld      (ix+1), a                ; -> DAC
        inc     l                        ; advance read ptr (wraps within page)
        ld      a, l
        ld      (SND_RING_RD), a
        di                               ; protect the ROM reads below from the IRQ
        call    SndDrv_FillOne           ; fill byte 1
        call    SndDrv_FillOne           ; fill byte 2 (2:1 catch-up; guard no-ops when full)
        ld      b, SND_DAC_RATE          ; rate delay (controller tunes)
.rate:  djnz    .rate
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
        ; sample request -> enable DAC mode + start the blip from banked ROM
        ld      (ix+0), SND_REG_DAC_ENABLE   ; reg $2B
        ld      (ix+1), 80h                  ; DAC mode ON
        ; select the blip's ROM bank into the Z80 $8000 window (cached)
        ld      a, SND_BLIP_BANK
        call    SndDrv_SetBank
        ; point the stream source at the banked sample (window addr + length)
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
        ; reset ring ptrs so the fill starts fresh from the sample
        xor     a
        ld      (SND_RING_RD), a
        ld      (SND_RING_WR), a
        ld      a, 1
        ld      (SND_STAT_DAC_ACTIVE), a
        xor     a
        ld      (SND_REQ_SAMPLE), a          ; clear slot
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; --- VBlank ISR: drain the ring (NO ROM reads) through the 68k DMA window ---
; Entered via RST 38h ($0038 -> jp here) when the Genesis asserts the Z80 /INT
; at VBlank start. ALL of the engine's VDP/DMA work happens inside the 68k VBlank
; handler, so by entering DRAIN here we keep the DAC fed at constant cadence
; THROUGH the DMA window WITHOUT touching ROM (a ROM read during 68k->VDP DMA
; would stall the Z80 bus and drag the pitch — the bug 1B fixes). The 256-byte
; ring lead (~16ms @16kHz) hugely exceeds the VBlank/DMA window (~1.3ms).
;
; ADAPTIVE drain (vs the old fixed SND_DRAIN_SAMPLES window): on entry the ISR
; resets the ack byte (SND_CTRL_DMA_ACTIVE) to 0, then drains one ring byte per
; pass UNTIL the 68k flips that byte to 1 ("DMA done, ROM safe"). A safety cap of
; SND_DRAIN_MAX (< the ring lead) bounds the loop so a missed/late ack can never
; underrun the ring or hang the ISR. This tracks the ACTUAL DMA length each frame
; instead of a worst-case constant, so heavy frames stay protected and light
; frames return promptly. After draining we do the per-frame mailbox poll (out of
; the audio path), then `ei`/`ret`.
;
; `ix` invariant: init sets ix=$4000 and only the DAC-write paths + SetBank touch
; it; SetBank uses hl, not ix. ix therefore stays $4000. We reload it here anyway
; so the ISR is self-contained and robust against future main-loop edits.
SndDrv_ISR_Drain:
        push    af
        push    bc
        push    hl
        push    ix
        ld      ix, SND_Z80_YM_A0        ; ix = $4000 (self-contained; see note)
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      z, .done                 ; nothing playing -> just housekeep + return
        xor     a
        ld      (SND_CTRL_DMA_ACTIVE), a ; Z80 owns the reset (no entry race with the 68k ack)
        ld      b, SND_DRAIN_MAX         ; safety cap (< ring lead) — prevents underrun/hang
.loop:
        ld      a, (SND_RING_RD)         ; ring read low byte
        ld      l, a
        ld      h, SND_RING_PAGE         ; hl = $17xx
        ld      a, (hl)                  ; ring[rd]
        ld      (ix+0), SND_REG_DAC_DATA ; reg $2A
        ld      (ix+1), a                ; -> DAC
        inc     l                        ; advance (wraps within page)
        ld      a, l
        ld      (SND_RING_RD), a
        push    bc                       ; rate pad ~matching FILL+PLAY per-sample (tune)
        ld      c, SND_DRAIN_PAD
.drate: dec     c
        jr      nz, .drate
        pop     bc
        ; --- adaptive exit: did the 68k finish its DMA pipeline this frame? ---
        ld      a, (SND_CTRL_DMA_ACTIVE)
        or      a
        jr      nz, .done                ; acked -> stop draining, resume FILL+PLAY
        djnz    .loop                    ; else keep draining (until the safety cap)
.done:
        call    SndDrv_PollMailbox       ; per-frame housekeeping, OUT of the audio path
        pop     ix
        pop     hl
        pop     bc
        pop     af
        ei
        ret

; --- fill ONE ROM byte into the ring; never lap the read ptr ---
; (Reached only via `call` from SndDrv_Main, with the IRQ masked — the banked ROM
; read MUST NOT be interrupted by the VBlank ISR's bank state, hence `di` at the
; call site.) 1:1 cadence with the per-sample DAC output keeps the ring lead
; constant. Page-aligned ring (MegaPCM trick): RD/WR are low bytes, the high byte
; is the page, so distance math is a single byte op mod 256. Guard: stop when the
; free gap (rd - wr) & $FF drops below the guard band, so WR can never lap RD
; (which would clobber un-drained samples). When the ring is already full this is
; a no-op (the drain will open a gap next sample).
SndDrv_FillOne:
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ret     z                        ; idle -> nothing to stream
        ; ring-full guard: free = (rd - wr) & $FF ; if free < guard, stop
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
        ret     nz                       ; bytes remain -> done
        ; sample exhausted -> loop the blip from its banked ROM start. The bank
        ; never changes (one bank covers the whole bank-aligned sample), so no
        ; SetBank is needed here — just reset the window ptr + remaining length.
        ld      hl, SND_BLIP_PTR         ; loop: reset ptr + remaining
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
        ret

; --- select ROM bank in `a` into the Z80 $8000 window; no-op if already current ---
; (Reached only via `call` — never by fall-through.) MegaPCM set-bank trick:
; the bank latch at $6000 is a 9-bit shift register loaded LSB-first by 9 single-
; bit writes. We cache the last bank in SND_CUR_BANK and skip the 9 writes when
; the requested bank already matches (the common per-frame case while a sample
; plays). `a` is the bank id = (sample_addr & $7F8000) >> 15.
SndDrv_SetBank:
        ld      hl, SND_CUR_BANK
        cp      (hl)
        ret     z                        ; already current -> no I/O
        ld      (hl), a                  ; cache the new bank
        ld      hl, SND_Z80_BANKREG      ; $6000 bank latch
        rept 8
        ld      (hl), a                  ; write current LSB
        rrca                             ; rotate next bit into bit0
        endr
        ld      (hl), a                  ; 9th write (bit8)
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
