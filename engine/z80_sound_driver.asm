; ======================================================================
; engine/z80_sound_driver.asm — Z80-autonomous DAC streaming driver
; (MegaPCM-2 model: free-running, every-path-equal-cost streaming loop)
;
; Assembled inline in 68k ROM via `cpu z80 / phase 0`. Loaded into Z80 RAM
; over the idle program at boot when SOUND_DRIVER_ENABLED is defined.
;
; DESIGN (Layer 6: register-resident 1:1 loop, raw 8-bit PCM):
;   * The LOOP TRIP-TIME is the sample clock. There is no per-sample YM Timer A
;     gate. Every pass through the streaming loop outputs exactly one ring byte
;     to the YM2612 DAC ($2A data port at $4001) and costs the IDENTICAL Z80
;     cycles regardless of which playback path it takes — so the DAC output
;     rate is rock-steady and load-independent.
;   * CONSUMER (the $2A write) reads the RAM RING ONLY, never ROM. RAM is
;     never bus-contended, so the $2A cadence cannot sag when the 68k holds
;     the cartridge bus for a VDP DMA. `de` is pre-loaded to $4001 and reg
;     $2A is pre-selected once at init, so every `ld (de),a` is a DAC write.
;   * PRODUCER (read-ahead) copies exactly ONE raw 8-bit ROM byte/pass from the
;     banked $8000 window into the ring (1:1: emit one, fill one), so the lead
;     is CONSTANT in steady state. There is no SKIP path and no pad waste —
;     which is what lets the rate run ~3x the old 2:1 DPCM form.
;   * THREE EQUAL-COST PATHS, selected with `jp cc` (constant 10 cyc taken or
;     not — never `jr cc`, which is 12/7 and would itself be a jitter source):
;       FILL          — read-ahead 1 ROM byte (the reference path)
;       DRAIN         — 68k DMA in progress (SND_CTRL_DMA_ACTIVE != 0): no ROM
;                       read, padded to equal FILL
;       DRAINING_TAIL — producer exhausted: emit the buffered tail, padded ~to
;                       FILL, then stop at lead 0
;     Pads are explicit cycle-counted blocks; see the balance proof below.
;   * The loop runs `di` for the WHOLE sample with ALL streaming state held in
;     registers. The Z80 VBlank IRQ (RST 38h) does NOT fire during streaming —
;     its once-per-frame /INT never lands in the long di window — so there is no
;     per-pass `ei` and no per-pass RAM round-trip. The mailbox is serviced by
;     the Timer-A tick (SndDrv_TimerATick) instead, not the IRQ.
;   * DMA SURVIVAL is a 68k FLAG BRACKET: the 68k sets SND_CTRL_DMA_ACTIVE=1 at
;     the very top of its VInt handler and clears it =0 after the last DMA. The
;     producer takes DRAIN (emit-only, no ROM read) while the flag is set; the
;     lead the consumer burns during the DMA is recovered by the Timer-A tick's
;     bulk-refill, which tops the ring back up to SND_RING_LEAD_TARGET every
;     frame AND runs THROUGH the DMA, so a sustained DMA cannot starve it. The
;     ~200-sample ring lead (~11 ms at 18 kHz) vastly outlasts any VBlank/DMA.
; ======================================================================
Z80_Sound_Start:
        save
        cpu z80
        phase 0

; ======================================================================
; CYCLE-BALANCE PROOF — the REGISTER-RESIDENT 1:1 streaming loop (Layer 6, raw 8-bit).
; (T-states per the AS/Zilog table. The banked $8000-window ROM read adds a bounded
;  ~3.3-cyc bus penalty under 68k load; it lands ONLY on FILL's single `ld a,(ix+0)`
;  and is inherent to the one path that touches ROM — noted, not padded.)
;
; The loop holds ALL streaming state in registers and runs `di` for the whole sample:
; the VBlank ISR does NOT fire during streaming (its once-per-frame /INT never lands in
; the long di window — the mailbox is serviced by the Timer-A tick instead), so the old
; per-pass `ei` + RAM round-trips are gone. Register map (held all streaming; the
; Timer-A tick spills->RAM / reloads around Sequencer_Frame, which clobbers everything):
;   de = $4001 (DAC data)   h = SND_RING_PAGE ($17)
;   c  = ring RD   b = ring WR   ix = ROM window ptr   hl' (shadow) = ROM len
;
; 1:1 STREAMING: every pass emits ONE ring byte AND fills ONE raw ROM byte, so the ring
; lead is CONSTANT -> there is NO SKIP path (no pad waste — that is what makes the rate
; ~3x the old 2:1 DPCM form). DMA-stall recovery (the lead the consumer burns while a
; 68k DMA blocks the producer's ROM read) is the Timer-A tick's bulk-refill, OFF the
; hot path.
;
; --- FILL pass (steady state; every normal pass) --------------------------
;   ld l,c / ld a,(hl) / ld (de),a / inc c              22  ; CONSUMER: ring[rd]->$2A; RD++
;   ld a,(SND_Z80_YM_A0) / and mask / jp nz,tick        30  ; TIMER-A poll
;   ld a,(SND_DAC_PHASE) / cp 2 / jp z,.draining        30  ; DRAINING_TAIL check
;   ld a,(SND_CTRL_DMA_ACTIVE) / or a / jp nz,.drain     27 ; 68k DMA -> DRAIN (no ROM read)
;   ld a,(ix+0) / ld l,b / ld (hl),a / inc b / inc ix    44 ; FILL: ROM->ring[wr]; WR++,ROM++
;   exx / dec hl / ld a,h / or l / exx                   22 ; len-- (shadow); exhaust test
;   jp z,.exhaust  +  jp .loop                           20
;                                                ----- FILL = 195 cyc
;   SND_LOOP_CYC = 195 -> dac_rate_hz(195) = 3579545/195 = 18356 Hz (the streaming/pitch
;   rate; measured in Exodus as a ~2.43-sample-@44.1k $2A cadence = ~18.2 kHz, byte-exact).
;
; --- DRAIN (68k DMA active): emit-only, no ROM read -----------------------
;   consumer(22)+poll(30)+phase(30,not taken)+DMA(27, jp nz taken) + 19*nop(76) + jp(10)
;                                                ----- DRAIN = 195 (lead recovered at the tick)
;
; --- DRAINING_TAIL (PHASE==2; the sample tail only) -----------------------
;   consumer(22)+poll(30)+phase(30, jp z taken) + [ld a,b/sub c/jp z,.stop = 18]
;     + 21*nop(84) + jp(10)                      ----- DRAINING = 194 (1 cyc under FILL;
;   tail-only -> inaudible). .stop is a one-shot terminal event (DC-center + idle).
;
; --- INHERENT PITCH ASYMMETRY (silicon-only, accepted) --------------------
; The ~3.3-cyc banked-ROM bus penalty (above) lands ONLY on FILL's `ld a,(ix+0)`;
; DRAIN and DRAINING_TAIL read no ROM, so they never pay it. FILL's true period is
; therefore ~195+3.3 cyc while DRAIN/DRAINING run at 195/194 -> during a 68k DMA
; (DRAIN) or the sample tail (DRAINING) the output pitch runs SHARP vs the FILL steady
; state: DRAIN ~29 cents (3.3/195 ~= 1.7%, = 1200*log2(198.3/195)), DRAINING ~38 cents
; (194 cyc, tail-only -> inaudible). It CANNOT be padded out: matching
; the penalty on DRAIN would require a ROM read, which is exactly what DRAIN must
; avoid while the 68k holds the cartridge bus. The effect is silicon-only (Exodus
; does not model cartridge-bus contention, so it is invisible there) and transient
; (DRAIN spans only a DMA window, DRAINING only the buffered tail) -> ACCEPTED, not
; fixed.
;
; --- BOUNDING the Timer-A tick (once per ~59 Hz frame) --------------------
; On overflow the poll's `jp nz,SndDrv_TimerATick` is taken: spill regs->RAM, rearm +
; Sequencer_Frame (B1) + mailbox poll, reload regs, bulk-refill the ring to
; SND_RING_LEAD_TARGET (200; len-bounded; runs THROUGH an active DMA, not deferred —
; fix B), re-park $2A, rejoin .afterPoll.
; During the tick the DAC holds its last sample (the Sequencer_Frame gap, pre-existing) —
; that lengthens wall-clock duration, NOT the streaming/pitch rate. The ~200-sample lead
; (~11 ms at 18 kHz) outlasts any real 68k DMA (<3 ms) with margin.
; ======================================================================

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
        jp      SndDrv_ISR               ; -> the minimal VBlank ISR (mailbox poll)

; --- entry ---
SndDrv_Init:
        ; The driver runs WITH interrupts. The Genesis asserts the Z80 /INT once
        ; per VBlank; `im 1` vectors it to RST 38h ($0038) where the MINIMAL ISR
        ; polls the mailbox and returns. DMA survival is NOT the ISR's job — it
        ; is the producer's DRAIN path, gated on the 68k's SND_CTRL_DMA_ACTIVE
        ; flag bracket. `ei` is issued only AFTER the ring is primed (below).
        di
        im      1                        ; VBlank /INT -> RST 38h -> $0038
        ld      sp, 1FFEh                ; stack top (see z80-ram-map sub-design)

        ; de = $4001 = YM2612 part-I DATA port. Held INVARIANT for the whole
        ; driver lifetime: the steady-state DAC write is `ld (de),a` (7 cyc),
        ; not an ix-indexed write (19 cyc). Nothing else writes $4000/$4001 in
        ; the steady state (SetBank uses $6000; the only $4000 writes are the
        ; one-time init sequence below).
        ld      de, SND_Z80_YM_A1        ; de = $4001 (DATA port)

        ; YM ready: wait for busy flag (bit7 of $4000) to clear.
        ld      hl, SND_Z80_YM_A0        ; hl = $4000 (ADDR/status port)
.wait_ym:
        bit     7, (hl)
        jr      nz, .wait_ym

        ; --- HARDWARE LFO ENABLE ONCE: $22 = $08 (LFO on, freq 0 = 3.82 Hz). The
        ; YM2612's GLOBAL low-freq oscillator drives every channel's AMS (tremolo)
        ; and FMS (vibrato) depth bits carried in each patch's $B4 (fp_lr_ams_fms).
        ; Without this master switch those depth bits are inert -> flat/static
        ; voices. The Zyrinx/B&R driver runs the LFO at $22=$08; matching it brings
        ; our held notes alive. Set ONCE (the reg persists; nothing else writes $22)
        ; and BEFORE the addr port parks on $2A below. ($4000=reg via hl, $4001=data
        ; via de — same idiom as the DAC enable.)
        ld      (hl), SND_REG_LFO        ; $4000 = $22 (select LFO reg)
        ld      a, 08h                   ; LFO enable (bit3) + freq 0 (= 3.82 Hz)
        ld      (de), a                  ; $4001 = $08

        ; --- DAC ENABLE ONCE (req 7): $2B = $80 (DAC mode on), then SELECT $2A
        ; once, then PRIME the $2A latch to $80 (DC center). After this the addr
        ; port stays parked on $2A forever, so every `ld (de),a` writes DAC data.
        ; $2B is NEVER toggled again (no per-play / per-loop enable edge -> no
        ; click). Reg select uses $4000 (hl); data uses $4001 (de).
        ld      (hl), SND_REG_DAC_ENABLE ; $4000 = $2B (select DAC-enable reg)
        ld      a, 80h
        ld      (de), a                  ; $4001 = $80 -> DAC mode ON
        ld      (hl), SND_REG_DAC_DATA   ; $4000 = $2A (select DAC DATA reg — parked here)
        ld      a, 80h
        ld      (de), a                  ; $4001 = $80 -> prime latch to DC center

        ; --- clear request slots + status region ---
        xor     a
        ld      (SND_REQ_PING), a
        ld      (SND_REQ_SAMPLE), a
        ld      (SND_REQ_MUSIC), a
        ld      (SND_REQ_SFX), a
        ld      (SND_REQ_FADE), a        ; Phase 2: master-fade request slot
        ld      (SND_REQ_TEMPO), a       ; Phase 2: tempo request slot
        ld      (SND_CTRL_DMA_ACTIVE), a ; flag bracket clear (no DMA in progress)
        ld      (SND_DAC_PHASE), a       ; PHASE = idle (0) — two-stage stop SM
        ld      (SND_SONG_BANK), a       ; B1 bracket reads this on pre-song idle ticks
        ld      (SND_ROM_BANK), a        ; (Snd_LoadSong sets both to the real song bank)
        ld      (SND_FM6_ADAPTIVE), a    ; Layer 7: non-adaptive until a song sets it
        ld      (SND_FM6_CHAN_PTR), a    ; null the FM6 channel ptr (defensive; set per load)
        ld      (SND_FM6_CHAN_PTR+1), a
        ld      (SND_STAT_PING_ECHO), a
        ld      (SND_STAT_ACK_COUNT), a
        ld      (SND_STAT_TICK), a
        ld      (SND_SEQ_ACTIVE), a      ; sequencer idle until a song loads (Task 6)
        ld      (SND_SEQ_CHCOUNT), a     ; no channels until a song loads
        ; Task 9: clear the SFX queue so CNT starts at 0 (Z80 RAM is undefined at power-on).
        ld      (SND_SFX_QUEUE_CNT), a   ; 0 entries pending
        ld      (Snd_SpindashRev), a     ; spindash rev escalation starts at 0 (spec §6)
        ; Phase 2: fade = full volume (0), idle; tempo = normal-speed default (16).
        ld      (SND_MASTER_FADE), a
        ld      (SND_FADE_TARGET), a
        ld      (SND_FADE_DIRTY), a
        ld      (SND_FADE_DELAY_CTR), a
        ld      a, SND_TEMPO_DECR_DEFAULT
        ld      (SND_TEMPO_CUR), a
        ld      (SND_TEMPO_TARGET), a
        ld      (SND_TEMPO_BASE), a

        ; --- PRE-FILL the whole 256-byte ring with $80 (req 7) so the idle and
        ; sample lead-in output is DC-center silence (no click, no garbage). ---
        ld      hl, SND_RING_BASE
        ld      b, 0                     ; 256 bytes (b=0 -> djnz runs 256x)
        ld      a, 80h
.fill_ring:
        ld      (hl), a
        inc     hl
        djnz    .fill_ring

        ; ring pointers idle at 0; no sample active yet.
        xor     a
        ld      (SND_RING_RD), a
        ld      (SND_RING_WR), a
        ld      (SND_STAT_DAC_ACTIVE), a ; DAC inactive until a play request

        ; Seed the SetBank cache with an impossible bank id ($FF) so the first
        ; play's SetBank always switches (the cached-no-op check never matches).
        ld      a, 0FFh
        ld      (SND_CUR_BANK), a

        ; announce we are alive
        ld      a, SND_ALIVE_MARKER
        ld      (SND_STAT_ALIVE), a

        ; --- Phase 3: program Timer A to the FIXED frame rate ONCE, here at init.
        ; Timer A is now the per-frame engine clock (SND_TIMERA_N -> ~59.06 Hz),
        ; region-independent, NOT a per-song tempo selector. The DAC/idle-loop
        ; Timer-A overflow poll fires Sequencer_Frame once per frame. The song
        ; loader no longer (re)programs Timer A; musical tempo is per-channel via
        ; the tempo accumulator. SND_SEQ_ACTIVE = 0 until a song loads, so the
        ; per-frame engine is a no-op (returns early) even though the timer ticks.
        call    Snd_TimerA_ProgramFixed

        ei                               ; state consistent -> allow the VBlank IRQ
        ; falls into the IDLE loop

; ======================================================================
; IDLE loop — DAC inactive. NOT cycle-balanced (it is silence). Keeps the
; `ei` window alive so the VBlank ISR's mailbox poll can flip DAC_ACTIVE=1
; and start a sample. Feeds $80 (DC center) every pass so the output never
; clicks while idle. de=$4001 and reg $2A stay selected, so `ld (de),a`
; lands on the DAC. When a sample starts, jumps into the streaming loop.
;
; TASK 6: the idle loop MUST ALSO poll Timer A so the SEQUENCER ticks while the
; DAC is silent. A song whose first DAC trigger is its $E2 can't start the DAC
; until a tick runs (the tick emits the $E2 -> Snd_StartSample -> DAC_ACTIVE=1).
; Without an idle-side poll the song would deadlock (no tick -> no $E2 -> no DAC
; -> never enters the streaming loop -> never polls). The FM/PSG voices also need
; ticks immediately, before any DAC ever plays. On overflow we rearm + tick, then
; re-check DAC_ACTIVE (a $E2 may have armed it) to enter the streaming loop.
; (No cycle balancing here — idle is silence; the tick rate while idle is set by
; Timer A exactly as in the streaming loop.)
; ======================================================================
SndDrv_Idle:
        di
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      z, .stay_idle            ; DAC idle -> run the idle body below
        ; B4: a mailbox/ISR SND_REQ_SAMPLE armed a sample (Snd_StartSample stashed
        ; SND_ROM_BANK, B2-stash-only). Latch the sample bank on the idle->streaming
        ; entry so the first FILL reads the right bank. With the DAC-aware B3 this is
        ; usually already done (the arming ISR latched SND_ROM_BANK on exit), so this is
        ; a cheap cached-no-op local guarantee. ($E2 triggers are covered by B1's tail.)
        ld      a, (SND_ROM_BANK)
        call    SndDrv_SetBank           ; B4: enter streaming on the sample bank
        jp      SndDrv_Sample            ; sample armed -> enter streaming loop
.stay_idle:
        ; --- Timer-A poll (sequencer tick clock while idle) ---
        ld      a, (SND_Z80_YM_A0)       ; YM status ($4000): bit0 = Timer A overflow
        and     SND_TIMERA_OVF_MASK
        jr      z, .idle_settled         ; no tick -> DAC latch already holds $80, $2A parked
        call    SndDrv_IdleTick          ; overflow -> rearm + Sequencer_Frame
        ; A tick ran: Sequencer_Frame's FM/PSG writes moved the $4000 addr latch, so
        ; re-park $2A and re-assert DC center ONCE here. Between ticks the DAC latch
        ; holds $80 and $2A stays parked, so re-writing $80 every idle spin is pure
        ; VGM-logger flood (tens of kHz x3 at emu speed) with no audible effect — it
        ; over-runs the emulator's $2A logger and breaks the cross-correlation verify.
        ; Gating the write to the ~59 Hz tick keeps DC-center silence and lets the VGM
        ; capture stay faithful for the rest of the DAC phase.
        ld      a, SND_REG_DAC_DATA      ; re-select $2A on the ADDR port ($4000)
        ld      (SND_Z80_YM_A0), a
        ld      a, 80h
        ld      (de), a                  ; DAC <- $80 (DC center silence)
.idle_settled:
        ei                               ; VBlank IRQ may land here (between samples)
        jp      SndDrv_Idle

; --- Idle-context Timer-A frame: rearm + run the per-frame engine, then restore
; de=$4001 (Sequencer_Frame clobbers de). Returns to the idle loop, which re-checks
; DAC_ACTIVE at the top so a $E2-armed sample enters the streaming loop next pass.
SndDrv_IdleTick:
        call    Snd_TimerA_Rearm         ; clear overflow, keep counting, re-park $2A
        call    Run_SeqFrame_OnSongBank  ; B1: frame on song bank, restore sample bank
        ld      de, SND_Z80_YM_A1        ; restore de = $4001 (DAC DATA port invariant)
        ret

; ======================================================================
; SndDrv_Sample — the free-running, every-path-equal-cost streaming loop.
; ONE straight-line iteration per sample. See the balance proof at the top.
; Live registers across iterations: ALL streaming state (de=$4001, h=ring page,
; c=RD, b=WR, ix=ROM ptr, hl'=ROM len) is held in registers for the whole sample.
; This is safe WITHOUT per-pass spills because the loop runs `di` end to end and
; the VBlank ISR does not fire during streaming — only the Timer-A tick
; (SndDrv_TimerATick) interrupts the loop, and it spills/reloads these registers
; itself around Sequencer_Frame. `de` ($4001) and reg-$2A-selected are invariants.
; ======================================================================
SndDrv_Sample:
        ; --- ENTRY (from SndDrv_Idle once a sample is armed): load the streaming state
        ; into REGISTERS, held across every pass. The loop runs `di` for the WHOLE
        ; sample — the VBlank ISR does not fire during streaming (the long di window
        ; misses the once-per-frame /INT; the mailbox is serviced by the Timer-A tick
        ; instead), so the old per-pass `ei` + RAM round-trips were dead weight. With
        ; state register-resident the per-sample cost drops ~3x (587 -> 195). Register
        ; map (held all streaming; the Timer-A tick spills->RAM / reloads around
        ; Sequencer_Frame, which clobbers everything):
        ;   de = $4001 (DAC data)        h  = SND_RING_PAGE ($17, ring page)
        ;   c  = ring RD   b = ring WR   ix = ROM window ptr   hl' (shadow) = ROM len
        ; 1:1 STREAMING: each pass emits ONE ring byte AND fills ONE ROM byte, so the
        ; lead is constant -> NO SKIP path, no pad waste (that is what lets the rate
        ; ~3x). DMA-stall recovery (the lead the consumer burns while a 68k DMA blocks
        ; the producer's ROM read) is the Timer-A tick's bulk-refill, not an in-loop
        ; 2:1 catch-up. See the balance proof header. ---
        di
        ld      de, SND_Z80_YM_A1        ; de = $4001 (DAC data port; held all streaming)
        ld      h, SND_RING_PAGE         ; h  = $17 (ring page; held all streaming)
        ld      a, (SND_RING_RD)
        ld      c, a                     ; c = ring RD
        ld      a, (SND_RING_WR)
        ld      b, a                     ; b = ring WR
        ld      ix, (SND_ROM_PTR)        ; ix = ROM window ptr
        exx
        ld      hl, (SND_ROM_LEN)        ; hl' = ROM len (shadow set)
        exx

.loop:
        ; --- CONSUMER: emit ring[rd] -> $2A ($4001). NO per-sample $2A re-select; the
        ; addr port stays parked on $2A (re-parked only by the tick / .stop /
        ; Snd_StartSample — the sole $4000-touching paths). RAM ring read — DMA-safe. ---
        ld      l, c                     ; l = RD (h = $17)
        ld      a, (hl)                  ; ring[rd]
        ld      (de), a                  ; -> YM $2A DATA ($4001)
        inc     c                        ; RD++

        ; --- TIMER-A poll (the sequencer-tick clock; the only thing that pauses
        ; streaming, for one Sequencer_Frame + bulk-refill, once per ~59 Hz frame). ---
        ld      a, (SND_Z80_YM_A0)       ; YM status: bit0 = Timer A overflow
        and     SND_TIMERA_OVF_MASK
        jp      nz, SndDrv_TimerATick    ; overflow -> tick (spill/frame/refill/reload), rejoin
.afterPoll:
        ; --- DRAINING_TAIL? (PHASE==2: producer exhausted, emit the buffered tail) ---
        ld      a, (SND_DAC_PHASE)
        cp      2
        jp      z, .draining
        ; --- 68k DMA in progress? -> DRAIN (consumer keeps emitting from the RAM ring;
        ; the producer must NOT read ROM while the 68k holds the bus). ---
        ld      a, (SND_CTRL_DMA_ACTIVE)
        or      a
        jp      nz, .drain
        ; --- FILL one RAW 8-bit byte: ROM(ix) -> ring[wr]; WR++, ROM++, len-- (1:1). ---
        ld      a, (ix+0)                ; raw 8-bit sample (banked $8000 window)
        ld      l, b                     ; l = WR
        ld      (hl), a                  ; ring[wr] = sample
        inc     b                        ; WR++
        inc     ix                       ; ROM++
        exx
        dec     hl                       ; len-- (shadow)
        ld      a, h
        or      l
        exx
        jp      z, .exhaust              ; len == 0 -> enter DRAINING_TAIL
        jp      .loop

.exhaust:
        ; Producer done: switch to DRAINING_TAIL (emit the buffered lead, no more ROM).
        ; One-shot per sample — the small extra cost here is not rate-critical.
        ld      a, 2
        ld      (SND_DAC_PHASE), a       ; PHASE = 2 (DRAINING_TAIL)
        jp      .loop

; --- DRAINING_TAIL (PHASE==2): the producer exhausted; the consumer (loop top) just
; --- emitted a buffered tail byte. Stop once the lead drains to 0. Register-resident
; --- (b=WR, c=RD; lead = WR-RD). Padded ~to the FILL pass (194 vs 195) — DRAINING
; --- runs only for the sample tail (the buffered lead at the very end), so the 1-cyc
; --- rounding is on those tail passes only and is inaudible. Pad reg-safe (a dead;
; --- ix/hl' unused while draining). ---
.draining:
        ld      a, b                     ; WR
        sub     c                        ; lead = (WR - RD) & $FF
        jp      z, .stop                 ; lead 0 -> fully drained -> stop
        rept    21
          nop
        endm
        jp      .loop

.stop:
        ; One-shot terminal event (once per sample). DC-center the DAC, clear active,
        ; PHASE=idle, return to the idle loop (which re-enables interrupts). RD/WR are
        ; final (lead 0); the next Snd_StartSample re-primes them in RAM.
        ld      a, SND_REG_DAC_DATA      ; re-park $2A on $4000
        ld      (SND_Z80_YM_A0), a
        ld      a, 80h
        ld      (SND_Z80_YM_A1), a       ; $2A = $80 (DC center silence)
        ; --- Layer 7 adaptive: hand ch6 back to FM6 music. ORDER MATTERS (research
        ; click-avoidance): $2A is ALREADY centered ($80) above, so disabling the DAC now
        ; flips ch6 to FM with no DC step. Then re-key FM6's held note so music resumes
        ; immediately (the trigger keyed it off, so $28=$F6 is a real 0->1 EG edge; ch6's
        ; $A4/$A0 + patch are already current — the Layer-4 gate kept writing them through
        ; the drum). Re-key ONLY if FM6 holds a note (SCF_KEYED) — a rest stays silent.
        ; Gated on SND_FM6_ADAPTIVE (dedicate leaves $2B armed -> FM6 stays DAC-owned). ---
        ld      a, (SND_FM6_ADAPTIVE)
        or      a
        jr      z, .stop_done
        ld      a, SND_REG_DAC_ENABLE    ; $2B
        ld      (SND_Z80_YM_A0), a
        xor     a
        ld      (SND_Z80_YM_A1), a       ; $2B = $00 -> ch6 returns to FM (output was centered)
        ld      ix, (SND_FM6_CHAN_PTR)
        push    ix
        pop     hl
        ld      a, h
        or      l
        jr      z, .stop_repark          ; no FM6 channel (defensive) -> just re-park $2A
        bit     SCF_KEYED_B, (ix+sc_flags)
        jr      z, .stop_repark          ; FM6 resting -> leave it silent
        ld      a, SND_REG_KEY_ONOFF     ; $28 (key on/off, part I)
        ld      (SND_Z80_YM_A0), a
        ld      a, SND_FM_KEYON_OPMASK|6 ; $F0 | chsel(FM6 = $06) = $F6 -> key ON (all ops)
        ld      (SND_Z80_YM_A1), a       ; real 0->1 edge -> EG re-attacks FM6's held note
.stop_repark:
        ld      a, SND_REG_DAC_DATA      ; re-park $2A on $4000 (the FM writes moved the addr port)
        ld      (SND_Z80_YM_A0), a
.stop_done:
        xor     a
        ld      (SND_STAT_DAC_ACTIVE), a ; clear active
        ld      (SND_DAC_PHASE), a       ; PHASE = idle (0)
        jp      SndDrv_Idle              ; idle loop re-enables interrupts

; --- DRAIN (68k DMA in progress): the consumer already emitted at the loop top; the
; --- producer must NOT read ROM while the 68k holds the bus. Pad to the FILL pass
; --- (195) so the rate never jitters during a DMA; the lead burned here is recovered
; --- by the Timer-A tick's bulk-refill. Pure nop pad (reg-safe). 76 = 19 nops. ---
.drain:
        rept    19
          nop
        endm
        jp      .loop

; ======================================================================
; SndDrv_ISR — minimal VBlank ISR (RST 38h $0038 -> jp here).
; Mailbox poll ONLY, then ei/ret. NO draining (the 68k flag bracket handles
; DMA survival via the producer's DRAIN path). ROM-SAFETY (Task 6 nuance): the
; ping/sample request paths read Z80-RAM + the $6000 bank latch ONLY — never ROM
; — so they are DMA-safe even if the ISR fires mid-DMA. The MUSIC-LOAD path is
; the exception: Snd_LoadSong's `ldir` DOES read ROM through the $8000 window, so
; it is NOT ROM-free. It is safe instead because the DAC loop is paused while the
; ISR runs and the ~200-sample ring-lead budget (SND_RING_LEAD_TARGET) vastly
; outlasts the few-hundred-byte song copy — the lead absorbs the load.
; Preserves af/bc/de/hl via push/pop (it interrupts the main/idle loop). It does
; NOT save ix/iy, and SndDrv_PollMailbox DOES clobber them (SfxDispatch/Snd_LoadSong
; use ix for channel state). That is SAFE for two distinct reasons, one per context
; the ISR can interrupt: (1) the IDLE loop holds NO live ix/iy across its `ei`, so a
; clobber there is harmless; (2) the SAMPLE loop DOES hold live ix (ROM ptr) and the
; hl' shadow (ROM len) but it runs `di` end to end, so the VBlank ISR never fires during
; streaming and cannot clobber them (the Timer-A tick services the mailbox there instead,
; and it spills/reloads ix and the hl' shadow itself). de=$4001 survives via the push/pop below, not by being
; untouched. INVARIANT: idle-context loop code must never keep a live ix/iy across `ei`.
; ======================================================================
SndDrv_ISR:
        push    af
        push    bc
        push    de
        push    hl
        ; B3: poll the mailbox bank-transparently (Snd_PollMailbox_Banked saves the
        ; pre-call bank, runs PollMailbox, and restores the bank the resumed context
        ; needs). The VBlank IRQ services the mailbox while the driver is IDLE;
        ; SndDrv_TimerATick services it during DAC streaming (the IRQ does NOT fire
        ; then — its brief per-iteration `ei` window misses the once-per-frame /INT).
        ; Same helper from both so the bank-transparency is identical.
        call    Snd_PollMailbox_Banked
        ; The per-frame engine (Sequencer_Frame) is driven ONLY by the DAC/idle-loop
        ; Timer-A overflow poll -> SndDrv_TimerATick/SndDrv_IdleTick (not from here).
        ; Driving it from both would double-clock the song.
        pop     hl
        pop     de
        pop     bc
        pop     af
        ei
        ret

; ======================================================================
; Snd_PollMailbox_Banked — run SndDrv_PollMailbox bank-transparently. PollMailbox may
; SetBank (a song load's `ldir`, an SFX-blob dispatch, and a mailbox sample re-stash
; all bank the $8000 window). On return, leave the window banked for the caller's
; resumed context: the SAMPLE bank (SND_ROM_BANK) if a DAC sample is streaming — which
; a mid-stream cross-bank retrigger may have just changed to a NEW bank, so we must NOT
; blindly restore the pre-call bank or the next FILL decodes the new sample through the
; old window; otherwise (idle/song context) the pre-call bank. Both restores are cached
; (no-op if unchanged). SND_CUR_BANK == the live $6000 latch at entry (SetBank is its
; sole writer). Called from BOTH the VBlank ISR (idle context) and SndDrv_TimerATick
; (streaming context — the IRQ doesn't fire during streaming, so the Timer-A tick is
; the only mailbox service there). Clobbers af,bc,de,hl,ix (PollMailbox's set).
; ======================================================================
Snd_PollMailbox_Banked:
        ld      a, (SND_CUR_BANK)
        push    af                       ; save the pre-call bank
        call    SndDrv_PollMailbox       ; RAM + $6000 latch only -> DMA-safe (may SetBank)
        pop     af                       ; a = saved pre-call bank
        ld      c, a                     ; stash it
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        ld      a, c                     ; default (DAC idle): the pre-call bank
        jr      z, .pmb_restore
        ld      a, (SND_ROM_BANK)        ; DAC streaming: the (possibly new) sample bank
.pmb_restore:
        jp      SndDrv_SetBank           ; tail-call (cached); leaves the window banked

; ======================================================================
; SndDrv_PollMailbox — act on any nonzero request slot, then clear it. Reached via
; Snd_PollMailbox_Banked from the VBlank ISR (idle) AND the Timer-A tick (streaming).
; Does NOT read ROM directly (the SFX-blob/song-load sub-paths read it through the
; $8000 window — Snd_PollMailbox_Banked + the ring lead handle that). Clobbers de; the
; callers save/restore the de=$4001 streaming invariant.
; ======================================================================
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
        ; --- music request? (Task 6: 1..$FE play SongTable[id-1], $FF stop) ---
        ld      a, (SND_REQ_MUSIC)
        or      a
        jr      z, .no_music             ; 0 -> nothing pending
        cp      SND_MUSIC_STOP           ; $FF -> stop
        jp      z, .music_stop
        call    Snd_LoadSong             ; 1..$FE -> load + arm the song (clears the slot)
        jr      .after_music
.music_stop:
        call    Sequencer_StopAll        ; key-off FM + silence PSG + clear active flag
        call    Sfx_StopAll              ; Phase 5a: clear overrides + kill SfxChannels + queue/duck
        call    Snd_TimerA_Disable       ; stop Timer A so no more ticks fire
        xor     a
        ld      (SND_REQ_MUSIC), a       ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.after_music:
.no_music:
        ; --- SFX request? (Phase 5a: id -> SfxDispatch steal + per-frame interp) ---
        ; Inserted BEFORE the SAMPLE block's `ret z` so a frame with only an SFX
        ; request still dispatches. SfxDispatch reads the SFX blob via the $8000
        ; window (banks it in, leaves it set) and steals a voice — DAC-paused ISR
        ; context, same ROM-read safety as Snd_LoadSong (the ring lead absorbs it).
        ; (Task 11 adds the 68k Sound_PlaySFX + ring stereo-alternation around this.)
        ld      a, (SND_REQ_SFX)
        or      a
        jr      z, .no_sfx
        call    SfxDispatch              ; resolve blob + init slot 0 + steal voice
        xor     a
        ld      (SND_REQ_SFX), a         ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_sfx:
        ; --- fade request? (1 = out, 2 = in) ---
        ld      a, (SND_REQ_FADE)
        or      a
        jr      z, .no_fade
        call    Snd_FadeCommand          ; set target + seed delay ctr (RAM only; bank-safe)
        xor     a
        ld      (SND_REQ_FADE), a        ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_fade:
        ; --- tempo request? (1..$FE target decrement; $FF restore authored base) ---
        ld      a, (SND_REQ_TEMPO)
        or      a
        jr      z, .no_tempo
        call    Snd_TempoCommand         ; set SND_TEMPO_TARGET (RAM only; bank-safe here)
        xor     a
        ld      (SND_REQ_TEMPO), a
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.no_tempo:
        ; --- sample request? (Task 6: id -> DacSampleTable[id-1] -> Snd_StartSample) ---
        ld      a, (SND_REQ_SAMPLE)
        or      a
        ret     z                        ; nothing else pending
        call    Snd_DacLookup            ; a = id -> hl = descriptor (or carry set if bad id)
        jr      c, .sample_done          ; bad id -> ignore (still clear the slot below)
        call    Snd_StartSample          ; start DAC playback from the descriptor at hl
.sample_done:
        xor     a
        ld      (SND_REQ_SAMPLE), a      ; clear slot
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; ======================================================================
; Snd_TempoCommand — a = $FF (restore authored base) or a target decrement
; (1..$FE). Sets SND_TEMPO_TARGET; Tempo_Ramp glides cur toward it. 0 -> default
; (never freeze). Clobbers af. RESIDENT: reached from SndDrv_PollMailbox (mailbox /
; ISR / streaming context — SAMPLE bank in the window), and touches only RAM, so it
; must NOT live in the $8000 song-bank window.
; ======================================================================
Snd_TempoCommand:
        cp      SND_TEMPO_RESTORE        ; $FF -> restore authored base
        jr      nz, .have
        ld      a, (SND_TEMPO_BASE)
.have:
        or      a
        jr      nz, .ok
        ld      a, SND_TEMPO_DECR_DEFAULT ; 0 -> normal (defensive)
.ok:
        ld      (SND_TEMPO_TARGET), a
        ret

; ======================================================================
; Snd_FadeCommand — a = SND_FADE_CMD_OUT (1) or SND_FADE_CMD_IN (2). OUT: ramp the
; scalar UP to silence. IN: snap to silence, ramp DOWN to full. Seeds the step-delay
; counter so Fade_Ramp steps on the next frame. Clobbers af. RESIDENT (same reason as
; Snd_TempoCommand: reached from the mailbox/streaming context; RAM only).
; ======================================================================
Snd_FadeCommand:
        cp      SND_FADE_CMD_IN
        jr      z, .fade_in
        ld      a, SND_FADE_SILENCE      ; fade out: target = silent
        ld      (SND_FADE_TARGET), a
        jr      .seed
.fade_in:
        ld      a, SND_FADE_SILENCE
        ld      (SND_MASTER_FADE), a     ; start silent
        xor     a
        ld      (SND_FADE_TARGET), a     ; target = full volume
.seed:
        ld      a, SND_FADE_DELAY
        ld      (SND_FADE_DELAY_CTR), a
        ret

; ======================================================================
; Snd_DacLookup — map a 1-based DAC sample id (in `a`) to its descriptor ptr.
; Out: hl = &DacSampleTable[id-1], carry CLEAR on success; carry SET (id 0 or
; id > DAC_SAMPLE_COUNT) on a bad id (hl undefined). Clobbers af, de, hl.
; (Stride is DacSample_len = 9; index*9 computed as index*8 + index.)
; ======================================================================
Snd_DacLookup:
        or      a
        scf
        ret     z                        ; id 0 -> bad (carry set)
        cp      DAC_SAMPLE_COUNT+1       ; carry SET iff id <= COUNT (valid)
        jr      c, .valid
        scf                              ; id > COUNT -> bad (carry set)
        ret
.valid:
        dec     a                        ; index = id-1
        ; hl = DacSampleTable + index*DacSample_len (9). index*9 = index*8 + index.
        ld      l, a
        ld      h, 0
        ld      e, l                     ; save index
        ld      d, h
        add     hl, hl
        add     hl, hl
        add     hl, hl                   ; hl = index*8
        add     hl, de                   ; hl = index*9
        ld      de, DacSampleTable
        add     hl, de                   ; hl = &DacSampleTable[index]
        or      a                        ; clear carry (success)
        ret

; ======================================================================
; Snd_StartSample — start DAC playback from a DacSample descriptor at `hl`
; (Task 6 refactor of the 1B SND_REQ_SAMPLE body). Reads bank/ptr/len from the
; 9-byte descriptor (ds_bank +0, ds_ptr +3, ds_length +5), re-asserts DAC mode
; WITHOUT toggling the $2B edge (no click), banks the sample in, resets the ring
; RD=0 + re-primes the $80 lead + WR=LEAD_PRIME, and sets SND_STAT_DAC_ACTIVE=1.
;
; TWO CALL CONTEXTS:
;   (a) mailbox SND_REQ_SAMPLE — runs in the VBlank ISR (DAC paused), de saved.
;   (b) sequencer $E2 (Seq_HookDac) — runs in SndDrv_TimerATick, inside the DAC
;       loop's `di` window (DAC NOT paused, but between samples).
; It touches ONLY RAM + the $6000 latch + the $2B/$2A YM regs — it reads NO ROM
; (banking is just the $6000 latch). It re-parks reg $2A on $4000 and restores
; de=$4001 at the END so both contexts leave the DAC consumer's invariants intact.
; Clobbers af, bc, de, hl. Preserves ix (the sequencer channel loop relies on it).
; ======================================================================
Snd_StartSample:
        push    ix                       ; preserve the sequencer channel ptr
        push    hl                       ; descriptor ptr (we re-read fields below)
        ; --- Layer 7 adaptive: key OFF FM6's music note BEFORE the DAC takes ch6, so the
        ; exhaust re-key ($28=$F6) is a real 0->1 edge that re-attacks FM6's EG (a re-key
        ; on a still-keyed channel is a chip no-op). Pure chip key-off ($28 part I = chsel
        ; FM6 $06, op-mask 0); SCF_KEYED is LEFT set — the sequencer's held-note
        ; bookkeeping + the Layer-4 gate keep it consistent through the drum, and the
        ; exhaust path reads it to decide whether to re-key. Gated: dedicate songs (and
        ; the bare $1F01 sample path) have no FM6 music -> SND_FM6_ADAPTIVE = 0 -> skip. ---
        ld      a, (SND_FM6_ADAPTIVE)
        or      a
        jr      z, .ss_no_fm6_keyoff
        ld      a, SND_REG_KEY_ONOFF     ; $28 (key on/off, part I)
        ld      (SND_Z80_YM_A0), a
        ld      a, 6                     ; chsel FM6 = $06, op-mask 0 -> key OFF
        ld      (SND_Z80_YM_A1), a
.ss_no_fm6_keyoff:
        ; --- Re-assert DAC mode ($2B bit7), then re-park $2A. (One-time per trigger, not
        ; per loop -> no recurring click. Dedicate: a no-edge re-assert of $80. Adaptive:
        ; the $00->$80 enable edge is click-free — DAC replaces ch6 instantly and the ring
        ; is primed to $80; the click risk is the RETURN edge, handled at .stop.) ---
        ld      a, SND_REG_DAC_ENABLE
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2B (select DAC-enable reg)
        ld      a, 80h
        ld      (SND_Z80_YM_A1), a       ; $4001 = $80 -> DAC mode ON
        ld      a, SND_REG_DAC_DATA
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2A (re-park addr port on DAC DATA)
        ; --- FM6 force DAC stereo on ch6 = $B6 = $C0. With $2B bit7 set the DAC REPLACES
        ; FM6's output and inherits FM6's $B6 L/R panning. DEDICATE (Layer 4): the song
        ; never plays FM6 music, so its $B6 may be muted ($B6 L=R=0) or one-sided -> force
        ; $C0 (L+R on, AMS=FMS=0) so the DAC is centered + audible. ADAPTIVE (Layer 7):
        ; FM6 IS a music voice — Fm_PatchLoad already set a real $B6 (its L/R pan + any
        ; AMS/FMS hardware LFO), and the exhaust does NOT restore $B6, so forcing $C0 here
        ; would PERMANENTLY clobber that pan/LFO after the first hit. So SKIP the force for
        ; adaptive: the drum inherits FM6's music pan (the Echo model — leave panning as the
        ; music set it) and FM6's pan/LFO survive the time-share untouched. FM6 = part II
        ; reg $B4+2; select on $4002, data on $4003. (The part-II addr port is left on $B6
        ; — harmless; every FM writer re-selects its target reg before its data.) ---
        ld      a, (SND_FM6_ADAPTIVE)
        or      a
        jr      nz, .ss_skip_b6_force    ; adaptive -> keep FM6's music $B6 (pan/LFO)
        ld      a, SND_REG_LR_AMS_FMS+2  ; $B6 (ch6 L/R/AMS/FMS), part II
        ld      (SND_Z80_YM_A2), a       ; $4002 = reg select (part II)
        nop                              ; inter-write delay (no busy-poll), as Fm_YmWrite
        ld      a, 0C0h                  ; L+R on, AMS=FMS=0 -> force DAC stereo
        ld      (SND_Z80_YM_A3), a       ; $4003 = data
.ss_skip_b6_force:
        pop     hl                       ; hl = descriptor base
        ; --- Read ALL descriptor fields BEFORE banking. SndDrv_SetBank CLOBBERS hl
        ; (it loads hl=SND_CUR_BANK, then hl=$6000); calling it first and then re-
        ; using hl as the descriptor base reads ds_ptr/ds_length off the $6000 bank-
        ; register region (floating garbage) -> runaway sample. (Latent since 1B: the
        ; sample-load path was never verified end-to-end until the DAC drum phase.) ---
        ld      a, (hl)                  ; ds_bank (+0)
        ld      (SND_ROM_BANK), a        ; stash the sample bank (banked in below)
        push    hl
        ld      de, DacSample_ds_ptr     ; +3
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = ds_ptr (window ptr)
        ld      (SND_ROM_PTR), de
        pop     hl
        ; --- raw 8-bit PCM: no decode setup (no DecTable, no running predictor). hl is
        ; still the descriptor base (from the pop above); read ds_length (+5) below. ---
        ld      de, DacSample_ds_length  ; +5
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = ds_length
        ld      (SND_ROM_LEN), de
        ; B2: stash-only. The sample bank was stashed to SND_ROM_BANK above; do NOT
        ; SetBank here. Snd_StartSample reads NO sample ROM (only sets up pointers), AND
        ; in the $E2 context it runs mid-Sequencer_Frame, where the window MUST stay on
        ; the SONG bank — a SetBank here would corrupt the rest of that frame's song
        ; reads (which is why this is stash-only, not a SetBank). The brackets latch the
        ; sample at the right moment instead: B1 (Run_SeqFrame_OnSongBank) re-latches
        ; SND_ROM_BANK after every sequencer frame (the $E2 path); B3 latches it on ISR
        ; exit while DAC is active (the mailbox path, incl. a mid-stream cross-bank
        ; retrigger); B4 re-latches it on the idle->streaming entry (a local backstop —
        ; usually a cached no-op now that B3 is DAC-aware).

        ; Reset ring pointers + prime the lead. To avoid a start underrun WITHOUT
        ; reading ROM (which could land mid-DMA in the ISR context), we set WR
        ; ahead of RD by SND_RING_LEAD_PRIME and leave those lead bytes at the $80
        ; the ring was pre-filled with — a click-free DC-center lead-in while the
        ; FILL producer (1:1) overwrites the ring with real sample data.
        xor     a
        ld      (SND_RING_RD), a         ; RD = 0
        ld      hl, SND_RING_BASE        ; ring page base
        ld      b, SND_RING_LEAD_PRIME
        ld      a, 80h
.prime_lead:
        ld      (hl), a
        inc     hl
        djnz    .prime_lead
        ld      a, SND_RING_LEAD_PRIME
        ld      (SND_RING_WR), a         ; WR = LEAD_PRIME -> lead bytes of $80 ready

        ld      a, 1
        ld      (SND_STAT_DAC_ACTIVE), a ; arm streaming (idle loop jumps in)
        ld      (SND_DAC_PHASE), a       ; PHASE = 1 (playing) — two-stage stop SM
        ; --- restore the DAC consumer's invariants for BOTH call contexts:
        ; re-park reg $2A on $4000, and de = $4001 (the streaming-loop DATA port).
        ld      a, SND_REG_DAC_DATA
        ld      (SND_Z80_YM_A0), a       ; re-park $2A on the addr port
        ld      de, SND_Z80_YM_A1        ; de = $4001 (DAC DATA port invariant)
        pop     ix
        ret

; ======================================================================
; SndDrv_SetBank — select ROM bank in `a` into the Z80 $8000 window; no-op if
; already current. (Reached only via `call`.) MegaPCM 9-bit set-bank trick: the
; latch at $6000 is a 9-bit shift register loaded LSB-first by 9 single-bit
; writes. We cache the last bank in SND_CUR_BANK and skip the 9 writes when the
; requested bank already matches. `a` = (sample_addr & $7F8000) >> 15. Touches
; the $6000 latch only — NEVER ROM — so it is DMA-safe.
; CLOBBERS af AND hl (hl ends at SND_CUR_BANK on the cached-no-op path, or $6000
; otherwise) — callers MUST NOT rely on hl surviving this call.
; ======================================================================
SndDrv_SetBank:
        ld      hl, SND_CUR_BANK
        cp      (hl)
        ret     z                        ; already current -> no I/O
        ld      (hl), a                  ; cache the new bank
        ld      hl, SND_Z80_BANKREG      ; $6000 bank latch
        rept 8
        ld      (hl), a                  ; write current LSB (b0..b7), LSB-first
        rrca                             ; rotate next bit into bit0
        endr
        ; 9th write = bit8 (the latch is 9-bit). `rrca` is an 8-bit rotate, so after
        ; 8 rotations `a` is back to the ORIGINAL bank — its bit0 is b0, NOT b8.
        ; Writing `a` here set b8 = bank's b0, which corrupts ODD banks (e.g. bank
        ; $0D -> latch $10D -> maps off-ROM -> reads $FF). All our banks are < $100,
        ; so b8 = 0; write 0 explicitly. (Latent until Sound 1D: 1A/1B/1C only ever
        ; used EVEN banks, where b0=0 happened to give the right b8.)
        xor     a                        ; b8 = 0 (banks < $100)
        ld      (hl), a                  ; 9th write (bit8)
        ret

; ======================================================================
; Run_SeqFrame_OnSongBank — B1 bracket. Run one sequencer frame with the $8000
; window on the SONG bank, then restore it to the SAMPLE bank. The frame engine
; streams the song through the window (STREAM songs) — or reads RAM (COPY songs,
; bank irrelevant) — so it MUST see the song bank; the DAC FILL reads the sample
; payload through the same window, so the bank is restored to SND_ROM_BANK after.
; Both SetBanks are cached (no-op when already current), so for a DAC-off song
; (SND_SONG_BANK == SND_ROM_BANK) this is two cached no-ops — no per-frame cost.
; During a DAC sample the two real switches ($6000 latch only — DMA-safe) cost a
; bounded ~200 cyc on the once-per-frame tick, absorbed by the ring lead.
; Clobbers af,bc,de,hl,ix (= Sequencer_Frame's set; SetBank's af/hl are a subset).
; The tail-call does NOT re-park reg $2A or restore de=$4001 — CALLERS must:
; SndDrv_TimerATick re-loads de + re-derives the lead then rejoins .afterPoll;
; SndDrv_IdleTick re-loads de; the DAC consumer re-selects $2A every sample.
; ======================================================================
Run_SeqFrame_OnSongBank:
        ld      a, (SND_SONG_BANK)
        call    SndDrv_SetBank           ; window -> song bank (cached no-op if current)
        call    Sequencer_Frame          ; one per-frame engine pass (reads the song stream)
        ld      a, (SND_ROM_BANK)
        jp      SndDrv_SetBank           ; window -> sample bank (tail-call; cached no-op if current)

; ======================================================================
; SndDrv_TimerATick — the Timer-A overflow handler (the PER-FRAME tick). Reached
; ONLY from the hot loop's poll `jp nz` at the FIXED frame rate, inside the loop's
; `di` window. The hot loop is REGISTER-RESIDENT (1:1), and Sequencer_Frame +
; PollMailbox clobber EVERYTHING (incl. ix and the shadow set), so this tick:
;   1. SPILL the live ring/ROM state (b=WR, c=RD, ix=ROM ptr, hl'=len) to RAM — so a
;      mailbox-retrigger's Snd_StartSample sees + resets the right RAM fields.
;   2. Snd_TimerA_Rearm (clear overflow) + Run_SeqFrame_OnSongBank (B1) +
;      Snd_PollMailbox_Banked (the only mid-sample mailbox service — the VBlank ISR
;      does not fire during streaming).
;   3. RELOAD the register-resident state (a retrigger may have reset it).
;   4. BULK-REFILL the ring lead the consumer burned while 68k DMAs blocked the
;      producer this frame (the 1:1 loop's catch-up, kept OUT of the per-pass hot
;      path). Small (only the DMA deficit), len-bounded; runs THROUGH an active DMA
;      (not deferred — fix B).
;   5. re-park $2A and rejoin .afterPoll (which runs this pass's phase/DMA/FILL).
; ======================================================================
SndDrv_TimerATick:
        ; 1. SPILL the register-resident state to RAM (RD already includes this pass's
        ; consumer inc; the frame/poll/retrigger operate on RAM).
        ld      a, c
        ld      (SND_RING_RD), a
        ld      a, b
        ld      (SND_RING_WR), a
        ld      (SND_ROM_PTR), ix
        exx
        ld      (SND_ROM_LEN), hl
        exx
        ; 2. rearm + per-frame engine (B1) + mailbox service.
        call    Snd_TimerA_Rearm         ; $27 (clear overflow, keep counting), re-park $2A
        call    Run_SeqFrame_OnSongBank  ; B1: frame on song bank, restore sample bank
        call    Snd_PollMailbox_Banked   ; mid-sample SFX/music service (bank-transparent)
        ; 3. RELOAD the register-resident state (StartSample may have re-primed it).
        ld      a, (SND_RING_RD)
        ld      c, a
        ld      a, (SND_RING_WR)
        ld      b, a
        ld      ix, (SND_ROM_PTR)
        exx
        ld      hl, (SND_ROM_LEN)
        exx
        ld      h, SND_RING_PAGE         ; restore h = $17 (frame clobbered it)
        ld      de, SND_Z80_YM_A1        ; restore de = $4001
        ; 4. BULK-REFILL: top the lead up to SND_RING_LEAD_TARGET every frame, then stop
        ; at sample end. NOTE: this does NOT defer on an active 68k DMA. The 1:1 hot loop
        ; only restores lead at this tick, so deferring during a DMA lets a sustained-DMA
        ; frame run drain the lead unrecovered until RD laps WR (a wedge — code-review
        ; finding). The refill runs inside the Timer-A tick where the DAC is already
        ; holding (the Sequencer_Frame gap), so a $8000-window ROM read stalling on the
        ; 68k bus only stretches that hold (benign — NOT the consumer pitch sag the
        ; hot-loop DRAIN guards); the read still returns correct data. So filling THROUGH
        ; the DMA recovers the lead every frame and prevents the underrun. The window is
        ; on the sample bank (B1 tail); reads via ix.
.refill:
        ld      a, b
        sub     c                        ; lead = WR - RD
        cp      SND_RING_LEAD_TARGET
        jr      nc, .refillDone          ; lead >= target -> topped up
        exx
        ld      a, h
        or      l                        ; len == 0 (sample exhausted)?
        exx
        jr      z, .refillDone
        ld      a, (ix+0)                ; fill 1 byte: ROM(ix) -> ring[wr]
        ld      l, b
        ld      (hl), a
        inc     b                        ; WR++
        inc     ix                       ; ROM++
        exx
        dec     hl                       ; len--
        exx
        jr      .refill
.refillDone:
        ; if the refill (or a prior pass) exhausted the sample, enter DRAINING_TAIL so
        ; .afterPoll routes to .draining instead of FILLing past the sample.
        exx
        ld      a, h
        or      l
        exx
        jr      nz, .reparkDac
        ld      a, 2
        ld      (SND_DAC_PHASE), a       ; len 0 -> PHASE = DRAINING_TAIL
.reparkDac:
        ld      a, SND_REG_DAC_DATA      ; re-park $2A on $4000 (frame/refill moved it)
        ld      (SND_Z80_YM_A0), a
        jp      SndDrv_Sample.afterPoll  ; rejoin the hot loop's dispatch

; ======================================================================
; Snd_TimerA_ProgramFixed — load + enable Timer A at the FIXED Phase-3 frame
; rate (SND_TIMERA_N, build-time-computed from SND_FRAME_HZ). Writes the full
; 10-bit N: $24 = N>>2 (bits 9..2), $25 = N&3 (bits 1..0), $27 = $05
; (LOAD:A | ENBL:A). Phase 3 replaced per-song tempo-byte Timer-A programming
; with this fixed-rate program (musical tempo is now per-channel via the tempo
; accumulator), so it writes both N bytes from the build-time constant and the
; frame rate is exact and region-independent. ENBL:A (bit2) is REQUIRED so the
; overflow raises the status flag the common-prefix poll reads. ABSOLUTE
; addressing (preserve de = $4001); re-parks reg $2A on $4000. Clobbers af.
; ======================================================================
Snd_TimerA_ProgramFixed:
        ; $24 = N>>2 (MSB) — write MSB before LSB.
        ld      a, SND_REG_TIMER_A_HI    ; $24
        ld      (SND_Z80_YM_A0), a       ; select $24 on $4000
        ld      a, SND_TIMERA_N>>2       ; N bits 9..2 (build-time constant)
        ld      (SND_Z80_YM_A1), a       ; $4001 = N>>2
        ; $25 = N&3 (LSB).
        ld      a, SND_REG_TIMER_A_LO    ; $25
        ld      (SND_Z80_YM_A0), a       ; select $25 on $4000
        ld      a, SND_TIMERA_N&3        ; N bits 1..0
        ld      (SND_Z80_YM_A1), a       ; $4001 = N&3
        ; $27 = LOAD:A | ENBL:A -> start the counter, let overflow raise the flag.
        ld      a, SND_REG_TIMER_CTRL    ; $27
        ld      (SND_Z80_YM_A0), a       ; select $27 on $4000
        ld      a, SND_TIMERA_CTRL_PROGRAM ; $05 = LOAD:A | ENBL:A
        ld      (SND_Z80_YM_A1), a       ; $4001 = program Timer A
        ; re-park reg $2A on the addr port for the DAC consumer.
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a
        ret

; ======================================================================
; Snd_TimerA_Rearm — clear the Timer-A overflow status flag, keeping the timer
; loaded + enabled (Task 5). The 10-bit value N auto-reloads and the counter
; keeps running; we only strobe RST:A. A SINGLE $27 write of $15
; (= LOAD:A | ENBL:A | RST:A) does it: RST:A (bit4) is a one-shot strobe that
; clears the overflow flag without disturbing the count. ABSOLUTE addressing
; (preserve `de`); re-parks reg $2A on $4000 at the end. Clobbers af.
; ======================================================================
Snd_TimerA_Rearm:
        ld      a, SND_REG_TIMER_CTRL    ; $27
        ld      (SND_Z80_YM_A0), a       ; select $27 on $4000
        ld      a, SND_TIMERA_CTRL_REARM ; $15 = LOAD:A | ENBL:A | RST:A (clear overflow flag)
        ld      (SND_Z80_YM_A1), a       ; $4001 = re-arm Timer A
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a       ; re-park addr port on DAC DATA
        ret

; ======================================================================
; Snd_TimerA_Disable — durably stop Timer A (Task 6 StopMusic). Writes $27 = $10
; (= SND_TIMERA_CTRL_DISABLE: RST:A bit4 SET to STROBE-CLEAR the pending overflow
; status flag; LOAD:A bit0 + ENBL:A bit2 CLEAR so the counter stays disabled).
; A bare $27=0 would leave a STALE overflow flag set: the very next DAC/idle-loop
; poll (`ld a,($4000)/and 1/jp nz`) would take the overflow branch -> Rearm writes
; $27=$15 -> the timer is RESURRECTED. $10 clears the flag AND keeps the timer off,
; so the next poll sees no overflow and the timer stays dead. ABSOLUTE addressing
; (preserve de); re-parks reg $2A on $4000. Clobbers af.
; ======================================================================
Snd_TimerA_Disable:
        ld      a, SND_REG_TIMER_CTRL    ; $27
        ld      (SND_Z80_YM_A0), a       ; select $27 on $4000
        ld      a, SND_TIMERA_CTRL_DISABLE ; $10 = RST:A only (clear overflow flag, timer OFF)
        ld      (SND_Z80_YM_A1), a       ; $4001 = strobe RST:A, leave LOAD/ENBL clear
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a       ; re-park addr port on DAC DATA
        ret

; ======================================================================
; Snd_LoadSong — load + arm the song the 68k posted (Task 6 + Sound 1D §5.1).
; REACHED ONLY from SndDrv_PollMailbox in the VBlank ISR, so the DAC streaming
; loop is PAUSED (it runs only at the loop's single `ei`, between samples) — the
; bank switch below cannot corrupt an in-flight DAC FILL (none runs while paused),
; and the ~100k-cyc ring lead vastly outlasts the work here. (Banking decision A.)
;
; TWO PATHS, selected by the song's SH_FLAGS byte (forwarded in SND_MUSIC_PARAM_
; FLAGS by the 68k, which read it from the song's ROM header):
;
;  (A) COPY / FM6=DAC (1C path, SH_F_STREAM clear — Song_Test / Ode demo):
;       DAC mode stays ON; the song is COPIED to SND_SONG_BUF (Z80 RAM) so the
;       sequencer streams are RAM-resident while the 1B DAC owns the bank.
;       1. Save the DAC bank; SetBank to the song bank.
;       2. ldir SND_SONG_BUF_SIZE bytes window-ptr -> SND_SONG_BUF.
;       3. Restore the DAC bank.
;       4. Song base = SND_SONG_BUF; SND_SEQ_PATCHTAB = FmPatchInlineTable (RAM).
;
;  (B) STREAM / FM6=FM (Sound 1D, SH_F_STREAM set — Moving Trucks):
;       NO RAM copy. The FM6=FM song runs with the DAC OFF, so the bank is free:
;       the sequencer reads its streams + patch bank DIRECTLY through the banked
;       $8000 window. Steps:
;       1. Write $2B=$00 (DAC mode OFF — absolute addressing, re-park $2A) and set
;          SND_STAT_DAC_ACTIVE=0. The idle loop's per-pass $2A writes are now
;          harmless (DAC disabled); it never touches the bank latch, so the song's
;          bank persists for every sequencer ROM read.
;       2. SetBank(song bank) and LEAVE it set (no save/restore — the song's bank
;          IS the playback bank now; nothing else re-banks).
;       3. Song base = the $8000 window ptr (SND_MUSIC_PARAM_PTR); SND_SEQ_PATCHTAB
;          = the song's patch-bank window ptr (SND_MUSIC_PARAM_PATCHPTR — same bank).
;       4. Init channels with sc_stream_ptr = window_base + per-channel offset.
;
; Both paths then SHARE .parse_header: read tempo/chcount/per-channel records
; relative to Snd_SongBase, program Timer A, arm. The DAC-OFF song ticks from the
; idle loop's Timer-A poll (SndDrv_IdleTick) once SND_SEQ_ACTIVE=1 — no DAC sample
; ever starts, so the streaming loop is never entered for an FM6=FM song.
;
; TIMING: this whole load runs once in the ISR (DAC paused). The mode switch
; ($2B write) is a single absolute write; no per-loop $2B toggle (no click). After
; the load returns, the idle loop resumes and its Timer-A poll drives the song.
; Clobbers af,bc,de,hl,ix,iy. (Runs in the ISR, which saved af/bc/de/hl; ix/iy are
; not used by the streaming loop across iterations.)
; ======================================================================
Snd_LoadSong:
        ; 0. SILENCE THE PREVIOUS SONG'S HARDWARE before clobbering its RAM state.
        ; A PlayMusic-while-playing switch (or a coalesced Stop+Play) reaches here
        ; with FM notes keyed-on and PSG tones sustaining from the OLD song. The
        ; .seq_clr wipe below loses every SCF_KEYED bit, so without an explicit
        ; hardware silence those voices would HANG on any physical channel the new
        ; song doesn't immediately re-key. Sequencer_StopAll is a blanket hardware
        ; silence: key-off all 6 FM channels via $28 + Psg_SilenceAll + clears
        ; SND_SEQ_ACTIVE. It uses ABSOLUTE YM addressing (preserves de=$4001) and
        ; touches NO Timer-A state, so the fixed-rate Timer-A program (armed once at
        ; init) keeps owning the timer config — the ordering is correct.
        call    Sequencer_StopAll        ; key-off FM + silence PSG + clear active flag

        ; Phase 5a: a PlayMusic-while-an-SFX-runs switch reaches here with an
        ; SfxChannel still ACTIVE, owning (overriding) a physical voice the new
        ; song's channels will fight over. The .seq_clr wipe below zeroes every
        ; SeqChannel (clearing stale override bits), but the SfxChannels themselves
        ; still hold SCF_ACTIVE + a steal target. Sfx_StopAll deactivates all 7
        ; SfxChannels, drops their priority, drains the queue, and resets the duck —
        ; so loading a new song cancels any in-flight SFX (the v1-simple choice; SFX
        ; are short. Sfx_Reconcile — re-overriding the NEW song's matching channels
        ; so in-flight SFX survive a music change — is the 5b upgrade). The hardware
        ; voices those SFX held were just silenced by Sequencer_StopAll above, so no
        ; voice hangs. Sfx_StopAll touches only RAM (no chip writes; preserves the
        ; de=$4001 invariant the loader relies on) — it does not fight the per-path
        ; init that follows.
        call    Sfx_StopAll              ; cancel in-flight SFX so the new song starts clean

        ; Clear the sequencer header + channel block FIRST (before the per-path setup
        ; below), so the SND_SEQ_PATCHTAB + base each path writes are NOT zeroed by it.
        ; (Bug: the clear used to live in .parse_header, AFTER the paths set PATCHTAB,
        ; so PATCHTAB ended up $0000 -> Fm_PatchPtr read garbage patches from $0000.)
        ld      hl, SND_SEQ_BASE
        ld      bc, SND_SEQ_END-SND_SEQ_BASE
.seq_clr:
        ld      (hl), 0
        inc     hl
        dec     bc
        ld      a, b
        or      c
        jr      nz, .seq_clr

        ; B1/B2 banking: record this song's bank for the per-frame bracket. Seed the
        ; sample bank to it too (so Run_SeqFrame_OnSongBank is two cached no-ops until a
        ; $E2 arms a sample) — but ONLY when no DAC sample is in flight. A music change
        ; can land mid-drum (the loader does NOT stop the DAC); clobbering SND_ROM_BANK
        ; then would make B1's tail yank the window to the new song's bank while the
        ; dying sample still FILLs from its own bank -> garbage tail. Leaving it lets the
        ; in-flight sample finish on its real bank (Snd_PollMailbox_Banked restores the
        ; sample bank after the poll; the new song reads via B1's head
        ; SetBank(SND_SONG_BANK)); the next $E2 re-stashes it. This case IS reachable —
        ; the Timer-A tick polls the mailbox during streaming — so the guard is live.
        ld      a, (SND_MUSIC_PARAM_BANK)
        ld      (SND_SONG_BANK), a
        ld      b, a                     ; stash the song bank across the DAC-active test
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jr      nz, .keep_sample_bank    ; a DAC drum is mid-flight -> keep its own bank
        ld      a, b
        ld      (SND_ROM_BANK), a        ; idle -> seed sample bank = song bank (B1 no-op)
.keep_sample_bank:

        ; --- branch on the streaming flag (forwarded from the song's SH_FLAGS) ---
        ld      a, (SND_MUSIC_PARAM_FLAGS)
        bit     SH_F_STREAM_B, a
        jp      nz, .stream_path

; ---------- PATH A: COPY / FM6=DAC (1C behavior, unchanged) ----------
        ; 1. save the DAC bank (so we can restore it after reading the song).
        ld      a, (SND_CUR_BANK)
        ld      (Snd_SavedDacBank), a
        ; 2. SetBank to the song's bank.
        ld      a, (SND_MUSIC_PARAM_BANK)
        call    SndDrv_SetBank           ; $6000 latch only
        ; 3. copy SND_SONG_BUF_SIZE bytes window-ptr -> SND_SONG_BUF (ldir). The
        ;    copy may read a little past the song into adjacent ROM (harmless —
        ;    streams self-terminate). The song's window region must NOT cross
        ;    $10000 (else ldir's hl would wrap past $FFFF into Z80 RAM and copy
        ;    garbage); guaranteed by the build assert in song_table.asm.
        ld      hl, (SND_MUSIC_PARAM_PTR) ; source = $8000-window ptr (little-endian in RAM)
        ld      de, SND_SONG_BUF          ; dest = Z80 RAM song buffer
        ld      bc, SND_SONG_BUF_SIZE
        ldir
        ; 4. restore the DAC bank (re-latches $6000; mismatch vs the cached song
        ;    bank forces the 9 writes).
        ld      a, (Snd_SavedDacBank)
        call    SndDrv_SetBank
        ; song base = SND_SONG_BUF (RAM); patches stay INLINE (FmPatchInlineTable).
        ld      hl, SND_SONG_BUF
        ld      (Snd_SongBase), hl
        ld      hl, FmPatchInlineTable
        ld      (SND_SEQ_PATCHTAB), hl
        jp      .parse_header

; ---------- PATH B: STREAM / FM6=FM (Sound 1D, DAC OFF) ----------
.stream_path:
        ; 1. DAC mode OFF: $2B = $00. ABSOLUTE addressing (preserve de=$4001), then
        ;    re-park $2A on the addr port. The idle loop's per-pass $2A writes are
        ;    harmless once the DAC is disabled. (One write; no per-loop toggle.)
        ld      a, SND_REG_DAC_ENABLE    ; $2B
        ld      (SND_Z80_YM_A0), a       ; select $2B on $4000
        xor     a
        ld      (SND_Z80_YM_A1), a       ; $4001 = $00 -> DAC mode OFF
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a       ; re-park addr port on DAC data
        xor     a
        ld      (SND_STAT_DAC_ACTIVE), a ; DAC not streaming (idle loop ticks the song)
        ; 2. SetBank(song bank) and LEAVE it set — the song's bank is the playback
        ;    bank now; the idle loop never re-banks, so it persists for ROM reads.
        ld      a, (SND_MUSIC_PARAM_BANK)
        call    SndDrv_SetBank           ; $6000 latch only
        ; 3. song base = the $8000 window ptr; patch bank = its window ptr (same bank).
        ld      hl, (SND_MUSIC_PARAM_PTR)
        ld      (Snd_SongBase), hl
        ld      hl, (SND_MUSIC_PARAM_PATCHPTR)
        ld      (SND_SEQ_PATCHTAB), hl
        ; fall into .parse_header

; ---------- SHARED: parse the header + init channels (base in Snd_SongBase) ----
; (the seq region was already cleared at the top of Snd_LoadSong, BEFORE the
; per-path setup, so the SND_SEQ_PATCHTAB + Snd_SongBase the paths set survive.)
.parse_header:
        ; Layer 7: cache the per-song adaptive-FM6 flag + null the FM6 channel ptr (set
        ; below in .chan_init when CHROUTE_FM6 is found). The DAC trigger/exhaust paths
        ; branch on these to time-share ch6 between FM6 music and the drum.
        xor     a
        ld      (SND_FM6_CHAN_PTR), a
        ld      (SND_FM6_CHAN_PTR+1), a  ; null FIRST (set in .chan_init when CHROUTE_FM6 is found)
        ld      a, (SND_MUSIC_PARAM_FLAGS)
        and     SH_F_FM6_ADAPTIVE
        ld      (SND_FM6_ADAPTIVE), a    ; THEN arm the gate (0 = dedicate/none, nonzero = time-share)

        ; channel_count (SH_CHCOUNT) — read via iy = song base (RAM or window).
        ld      iy, (Snd_SongBase)
        ld      a, (iy+SH_CHCOUNT)
        cp      CHROUTE_COUNT+1          ; defensive guard: a corrupt count clamps to 0
        jr      c, .cc_ok                ;   (prevents the channel loop walking ix wild)
        xor     a
.cc_ok:
        ld      (SND_SEQ_CHCOUNT), a
        ld      c, a                     ; c = channel count (loop bound)

        ; --- Phase 3: cache the header tempo_base + per-song pitch-table ptr (iy
        ; still = song base). tempo_base seeds each channel's accumulator below;
        ; the pitch-table ptr (BE offset; 0 = engine default) is cached for
        ; ModUpdate's pitch renderer (Task 3) — a 0 offset stays 0 (use default). ---
        ld      a, (iy+SH_TEMPO_BASE)
        ld      (SND_SEQ_TEMPO_BASE), a
        ld      h, (iy+SH_PITCHTAB_HI)   ; BE: high byte first
        ld      l, (iy+SH_PITCHTAB_LO)
        ld      a, h
        or      l
        jr      z, .pitchtab_default     ; offset 0 -> leave Snd_PitchTabPtr = 0 (default)
        ld      de, (Snd_SongBase)
        add     hl, de                   ; absolute ptr = base + offset
.pitchtab_default:
        ld      (Snd_PitchTabPtr), hl    ; 0 (default) or base+offset
        ld      a, c                     ; restore a = channel count (clobbered above)

        or      a
        jp      z, .arm                  ; 0 channels -> nothing to init (still arm)

        ; iterate the per-channel header records, filling each SeqChannel.
        ; iy = header record ptr (SHC_LEN bytes each, from base+SH_CHANNELS);
        ; ix = SeqChannel ptr.
        ld      ix, SND_SEQ_CHANNELS
        ld      bc, SH_CHANNELS
        add     iy, bc                   ; iy = base + SH_CHANNELS (first record)
        ld      a, (SND_SEQ_CHCOUNT)
        ld      c, a                     ; restore c = channel count (add iy clobbered bc)
.chan_init:
        push    bc                       ; preserve channel counter
        ; route byte.
        ld      a, (iy+SHC_ROUTE)
        ld      (ix+sc_route), a
        ; Layer 7: cache the FM6 SeqChannel ptr (channels are in DECLARATION order, so the
        ; exhaust re-key needs this to find FM6 scan-free). a still = the route byte.
        cp      CHROUTE_FM6
        jr      nz, .not_fm6
        ld      (SND_FM6_CHAN_PTR), ix
.not_fm6:
        ; cmd_ptr (slot[0]): BIG-ENDIAN 16-bit OFFSET in the header -> add the base.
        ld      h, (iy+SHC_CMD_HI)       ; high byte first (big-endian)
        ld      l, (iy+SHC_CMD_LO)
        ld      de, (Snd_SongBase)
        add     hl, de                   ; hl = base + offset (RAM or window address)
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
        ; mod_ptr (slot[1], C-ready seam): BIG-ENDIAN offset; 0 = NULL (single
        ; stream A). A 0 offset stays 0 (NULL) — only a nonzero offset is rebased
        ; to base+offset. Phase 3a never reads it; it is committed for C.
        ld      h, (iy+SHC_MOD_HI)
        ld      l, (iy+SHC_MOD_LO)
        ld      a, h
        or      l
        jr      z, .mod_null             ; offset 0 -> leave sc_mod_ptr = NULL (0)
        ld      de, (Snd_SongBase)
        add     hl, de
        ld      (ix+sc_mod_ptr), l
        ld      (ix+sc_mod_ptr+1), h
        ld      (ix+sc_macro_active), 1  ; sc_macro_active mirrors sc_mod_ptr != 0 (header-arm path)
.mod_null:
        ; flags: ACTIVE + route-class bit (FM / PSG / DAC) from the route value.
        ld      a, (iy+SHC_ROUTE)
        call    Snd_RouteClassFlags      ; a = SCF_ACTIVE | class bit (for this route)
        ld      (ix+sc_flags), a
        ; sensible default volume + first-tick-fetches-immediately.
        ld      (ix+sc_volume), 100
        ld      (ix+sc_dur_count), 1
        ; sc_dur_default seeds to 1 (not the zeroed 0): a channel that issues a note
        ; BEFORE any set-default-duration ($00-$7F) opcode reloads sc_dur_count from
        ; this. At 0 the next `dec (ix+sc_dur_count)` wraps 0->255 = a multi-second
        ; stuck note. 1 = "advance every tick" until the stream sets a real default.
        ld      (ix+sc_dur_default), 1
        ; PSG vol-env starts disabled (id 0); cursor/out cleared so a no-env PSG
        ; channel folds a 0 delta (byte-identical to no envelope). Set ONLY by the
        ; MEV_PSGENV opcode + PsgEnvUpdate. .chan_init sets fields individually (no
        ; bulk clear), so these MUST be cleared here or a stale env id from a prior
        ; song/SFX would spuriously shape a music PSG channel.
        ld      (ix+sc_psgenv), 0
        ld      (ix+sc_psgenv_cur), 0
        ld      (ix+sc_psgenv_out), 0
        ld      (ix+sc_noise_mode), 0    ; noise mode unset until MEV_PSGNOISE
        ; pitch-mod block: zero ONLY the gate field — sc_mod_ctrl==0 keeps every Mod_*
        ; path inert. Without this a stale sc_mod_ctrl from a prior song would spuriously
        ; enable vibrato once the gates are removed (later task).
        ld      (ix+sc_mod_ctrl), 0
        ld      (ix+sc_detune), 0        ; fine-detune neutral (reserved)
        ; --- Phase 3 per-channel state ---
        ; tempo accumulator: base from the header (SH_TEMPO_BASE), accum seeded =
        ; base so the FIRST frame's `sub 16` starts counting toward an event-tick.
        ; For tempo_base=16, frame 0 yields accum=0 with NO borrow, so the first
        ; event-tick lands on frame 1 (~17 ms later), not frame 0 — harmless and
        ; inaudible (matches the dur_count=1 "fetch on the first tick" intent).
        ld      a, (SND_SEQ_TEMPO_BASE)  ; cached header tempo_base
        ld      (ix+sc_tempo_base), a
        ld      (ix+sc_tempo_accum), a
        ; ModUpdate held-note no-op path needs a known baseline: a single plain
        ; note (pt_count=1) and a forced first patch load (last_patch=$FF != any
        ; real patch index, so the first ModUpdate patch render would reload).
        ld      (ix+sc_pt_count), 1
        ld      (ix+sc_last_patch), 0FFh
        ; sc_note force sentinel ($FF): the Phase-3 re-key rule (ModUpdate count==1)
        ; gives a FRESH attack only when the rendered index differs from sc_note (the
        ; last-keyed index); a SAME index is a held no-attack (the WAIT/voice-step
        ; case). $FF is not a valid fnum-table index (0..$83), so the FIRST
        ; MEV_PITCHENV on any channel ALWAYS differs -> the first note always attacks
        ; (no silent-first-note if the song opens on index 0). Mirrors the $FF
        ; force-reload sentinel used for sc_last_patch above.
        ld      (ix+sc_note), 0FFh
        ; advance to the next header record + SeqChannel.
        ld      de, SHC_LEN
        add     iy, de
        ld      de, SeqChannel_len
        add     ix, de
        pop     bc
        dec     c
        jp      nz, .chan_init           ; jr out-ranged when loop body > 127B; jp is safe

.arm:
        ; (SND_SEQ_PATCHTAB was set per-path above: FmPatchInlineTable for the copy
        ; path, the song's patch-bank window ptr for the stream path.)
        ; DEBUG trace/visibility housekeeping.
        xor     a
        ld      (SND_SEQ_TRACE_WR), a
        ld      (SND_SEQ_BADOP), a
        ; Phase 3: Timer A is the FIXED frame clock, programmed ONCE at driver init
        ; (Snd_TimerA_ProgramFixed); the song loader no longer (re)programs it.
        ; Musical tempo is per-channel via the tempo accumulator (sc_tempo_base,
        ; seeded above from the cached SH_TEMPO_BASE). We still cache the legacy
        ; SH_TEMPO byte into SND_SEQ_TEMPO for visibility (it is otherwise unused).
        ld      iy, (Snd_SongBase)
        ld      a, (iy+SH_TEMPO)
        ld      (SND_SEQ_TEMPO), a
        ; arm the sequencer.
        ld      a, 1
        ld      (SND_SEQ_ACTIVE), a
        ; Phase 2: reset global expression state for the new song. Fade -> full
        ; volume (else a song after a fade-out would play SILENT). Tempo -> normal
        ; (the song's MEV_TEMPO, if any, overrides on its first tick).
        xor     a
        ld      (SND_MASTER_FADE), a
        ld      (SND_FADE_TARGET), a
        ld      (SND_FADE_DIRTY), a
        ld      (SND_FADE_DELAY_CTR), a
        ld      a, SND_TEMPO_DECR_DEFAULT
        ld      (SND_TEMPO_CUR), a
        ld      (SND_TEMPO_TARGET), a
        ld      (SND_TEMPO_BASE), a
        ; clear the request slot (consumed) + bump the ack count.
        xor     a
        ld      (SND_REQ_MUSIC), a
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; ======================================================================
; Snd_RouteClassFlags — map a route byte (in `a`) to its sc_flags init value:
; SCF_ACTIVE | (SCF_IS_FM for FM1..FM6 / SCF_IS_PSG for PSG1..PSGN / SCF_IS_DAC
; for the DAC route). Clobbers af. (Sound 1D CHROUTE order: FM1..FM6 = 0..5,
; PSG1..PSGN = 6..9, DAC = 10.) The comparisons use the named CHROUTE_* equates,
; so the boundaries track the enum automatically — FM6 now classifies as FM.
; ======================================================================
Snd_RouteClassFlags:
        cp      CHROUTE_PSG1             ; < PSG1 (6) -> FM route (0..5 incl. FM6)
        jr      c, .fm
        cp      CHROUTE_DAC              ; < DAC (10) -> PSG route (6..9)
        jr      c, .psg
        ld      a, SCF_ACTIVE|SCF_IS_DAC
        ret
.fm:
        ld      a, SCF_ACTIVE|SCF_IS_FM
        ret
.psg:
        ld      a, SCF_ACTIVE|SCF_IS_PSG
        ret

; ======================================================================
; Music sequencer core — opcode interpreter + the Phase-3 per-frame engine.
; Included INSIDE the phase-0 blob so its labels (Sequencer_Frame, ModUpdate, the
; jump table, the handlers) resolve into Z80 RAM. Hardware-agnostic; the writer
; hooks call the Fm_*/Psg_* writers. (Comes after the helpers, before the
; even-pad, per the blob layout law.)
; ======================================================================
        include "engine/sound_sequencer.asm"

; ======================================================================
; Phase 5a SFX engine — steal/restore + the per-frame SfxChannel interpreter.
; Included INSIDE the phase-0 blob (after the sequencer whose ModUpdate/
; Sequencer_Channel it reuses, before the FM/PSG writers it calls).
; ======================================================================
        include "engine/sound_sfx.asm"

; ======================================================================
; FM voice writer (Sound 1C, Task 3) — real YM2612 register writes for FM
; routes. Included INSIDE the phase-0 blob so its labels resolve into Z80 RAM
; and it reaches the inline tables/patch below with direct Z80 addressing
; (no $8000-window banking). Comes after the sequencer (whose hooks call it),
; before the inline tables it reads and the even-pad.
; ======================================================================
        include "engine/sound_fm.asm"

; ======================================================================
; PSG voice writer (Sound 1C, Task 4) — real SN76489 register writes for PSG
; tone + noise routes. Included INSIDE the phase-0 blob so its labels resolve
; into Z80 RAM and it reaches the inline PsgDivisorTableZ below with direct Z80
; addressing (no $8000-window banking). Comes after the FM writer, before the
; inline tables it reads and the even-pad.
; ======================================================================
        include "engine/sound_psg.asm"

; --- Engine-default FM/PSG tables + per-song PITCH table (CO-LOCATED, F5 redo) ---
; FmPitchTableZ / LogVolumeLutZ / CarrierMaskTableZ / PsgDivisorTableZ /
; PsgVolEnv_* and the engine-default MovingTrucks_PitchTable USED to be included
; INSIDE this phase-0 blob. They now live at the START of Moving Trucks' OWN
; streamed bank (main.asm, right after `align $8000` before song_movingtrucks.asm).
; MT reads its stream/patch/pitch through the $8000 window every frame, so the
; tables are read from the SAME bank already in the window — NO separate table
; bank, NO per-frame swap (the first F5 attempt's swap broke MT's stream reads).
; That block is emitted under `phase 08000h`, so every table label EQUALS its
; $8000-window pointer; the FM/PSG voice writers reference the bare labels directly.
; This recovered ~998 bytes of code headroom in the blob. (The MovingTrucks_-
; PitchTable two-page size assertion now lives at that bank block in main.asm, where
; the labels are defined — a blob `if` over those forward-refs can't evaluate in
; AS's 1st pass.)

; --- Inline FM patch table (Z80-addressable) ---
; Fm_PatchPtr indexes this by sc_patch (TEMP for 1C — Task 6 switches to the
; banked 68k ROM FmPatchTable in data/sound/fm_patches.asm). The patch BYTES are
; single-sourced from data/sound/fm_patches.inc (the SAME records the 68k ROM
; FmPatchTable includes), so the inline copy and the ROM copy can never drift.
; The .inc emits via a `pbyte` macro that selects `db` here (Z80) vs `dc.b` in
; the 68k ROM. CLEARLY-TEMP bring-up data; FmPatch_len = 32 bytes/record.
FmPatchInlineTable:
        include "data/sound/fm_patches.inc"
FmPatchInlineTable_End:

        if (FmPatchInlineTable_End-FmPatchInlineTable) <> 2*FmPatch_len
          fatal "inline FM patch table wrong size"
        endif

; --- Inline DAC sample descriptor table (Task 6 decision 3) ---
; Maps a 1-based sample id to a 9-byte DacSample record (see the struct in
; sound_constants.asm). For 1C, id 1 = the temp_blip; its bank/ptr/len are the
; build-time SND_BLIP_* constants (from data/sound/dac_samples.asm), so an INLINE
; descriptor in the Z80 blob needs no banking to read. rate/loop_ofs are 0 (the
; 1B FILL loop drives the rate via the loop trip-time). One-shot: the producer
; now exhausts into DRAINING_TAIL (no FILL re-loop), so the sample plays once.
; ds_codec = 0 (raw 8-bit PCM; the reserved codec-selector slot).
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

; (The DPCM DecTable was removed with the codec — drums are raw 8-bit PCM, no decode.
; The inline-table / bank-free rationale is moot; the $8000 window holds the raw
; payload during FILL. DPCM could return for future long samples — see the spec
; amendment + the reserved ds_codec hook.)

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

        message "Z80 sound budget: \{Z80_SOUND_SIZE} / \{SND_STATE_BASE} bytes (\{SND_STATE_BASE-Z80_SOUND_SIZE} free)"

        ; code must not grow into the playback-state region
        if Z80_SOUND_SIZE > SND_STATE_BASE
          fatal "Z80 sound driver code (\{Z80_SOUND_SIZE} bytes) overruns state region at \{SND_STATE_BASE}"
        endif
