; ======================================================================
; engine/z80_sound_driver.asm — Z80-autonomous DAC streaming driver
; (MegaPCM-2 model: free-running, every-path-equal-cost streaming loop)
;
; Assembled inline in 68k ROM via `cpu z80 / phase 0`. Loaded into Z80 RAM
; over the idle program at boot when SOUND_DRIVER_ENABLED is defined.
;
; DESIGN (replaces the old Timer-A producer/consumer):
;   * The LOOP TRIP-TIME is the sample clock. There is no YM Timer A. Every
;     pass through the streaming loop outputs exactly one ring byte to the
;     YM2612 DAC ($2A data port at $4001) and costs the IDENTICAL number of
;     Z80 cycles regardless of which of the three playback paths it takes —
;     so the DAC output rate is rock-steady and load-independent.
;   * CONSUMER (the $2A write) reads the RAM RING ONLY, never ROM. RAM is
;     never bus-contended, so the $2A cadence cannot sag when the 68k holds
;     the cartridge bus for a VDP DMA. `de` is pre-loaded to $4001 and reg
;     $2A is pre-selected once at init, so every `ld (de),a` is a DAC write.
;   * PRODUCER (read-ahead) copies up to 2 ROM bytes/sample from the banked
;     $8000 window into the ring (2:1 catch-up so it recovers the lead a DMA
;     drain consumes), bounded by a lead cap so WR can never lap RD.
;   * THREE EQUAL-COST PATHS, selected with `jp cc` (constant 10 cyc taken or
;     not — never `jr cc`, which is 12/7 and would itself be a jitter source):
;       FILL  — read-ahead 2 ROM bytes (the reference path)
;       SKIP  — ring full (lead >= cap): no ROM read, padded to equal FILL
;       DRAIN — 68k DMA in progress (SND_CTRL_DMA_ACTIVE != 0): no ROM read,
;               padded to equal FILL
;     Pads are explicit cycle-counted blocks; see the balance proof below.
;   * EXACTLY ONE `ei` per iteration, immediately before the back-jump, so the
;     Z80 VBlank IRQ (RST 38h) lands ONLY between samples, never mid-ROM-read.
;     `di` at the top protects the whole iteration (incl. the ROM reads).
;   * DMA SURVIVAL is a 68k FLAG BRACKET: the 68k sets SND_CTRL_DMA_ACTIVE=1 at
;     the very top of its VInt handler and clears it =0 after the last DMA. The
;     producer takes DRAIN while the flag is set — no ISR drain loop, no ack
;     handshake. The 256-byte ring lead vastly outlasts the VBlank/DMA window.
; ======================================================================
Z80_Sound_Start:
        save
        cpu z80
        phase 0

; ======================================================================
; CYCLE-BALANCE PROOF — FILL == SKIP == DRAIN == 346 Z80 cycles
; (T-states per the AS/Zilog table in the task spec. The banked $8000-window
;  ROM read adds a bounded ~3.3-cyc bus penalty per byte under normal 68k load
;  — that lands ONLY on FILL's two `ld x,(hl)` reads and is inherent to the one
;  path that touches ROM; SKIP/DRAIN never read ROM. The DETERMINISTIC
;  instruction-cycle total is balanced exactly; the ROM penalty is noted, not
;  padded, because it is non-deterministic and unavoidable on FILL alone.)
;
; --- COMMON PREFIX (run by ALL three paths) -------------------------------
;   di                            4
;   ; -- CONSUMER (RAM ring only, never ROM) --
;   ld a,(SND_RING_RD)           13
;   ld l,a                        4
;   ld h,SND_RING_PAGE            7
;   ld a,(hl)                     7
;   ld (de),a                     7   ; -> YM $2A DATA ($4001)
;   inc l                         4
;   ld a,l                        4
;   ld (SND_RING_RD),a           13      [consumer subtotal = 59]
;   ; -- DISPATCH prefix --
;   ld a,(SND_RING_RD)           13
;   ld c,a                        4
;   ld a,(SND_RING_WR)           13
;   sub c                         4   ; a = (WR-RD)&$FF = lead
;   ld b,a                        4   ; stash lead
;   ld a,(SND_CTRL_DMA_ACTIVE)   13
;   or a                          4
;   jp nz,SndDrv_Drain           10   ; DMA active -> DRAIN  (10 taken or not)
;                                 -----  COMMON PREFIX = 4 + 59 + 65 = 128
; (the 8 dispatch-prefix instrs above sum to 13+4+13+4+4+13+4+10 = 65)
;
; --- DISPATCH TAIL (run by FILL and SKIP only; DRAIN jumped away) ----------
;   ld a,b                        4
;   cp  SND_RING_LEAD_CAP         7
;   jp nc,SndDrv_Skip            10   ; lead >= cap -> SKIP  (10 taken or not)
;                                 -----  TAIL = 21
;
; ============================ FILL =======================================
;   COMMON PREFIX ............... 128
;   DISPATCH TAIL ...............  21
;   -- producer (2-byte read-ahead) --
;   ld hl,(SND_ROM_PTR)          16
;   ld b,(hl)                     7   (+~3.3 ROM penalty)
;   inc hl                        6
;   ld c,(hl)                     7   (+~3.3 ROM penalty)
;   inc hl                        6
;   ld (SND_ROM_PTR),hl          16
;   ld a,(SND_RING_WR)           13
;   ld h,SND_RING_PAGE            7
;   ld l,a                        4
;   ld (hl),b                     7
;   inc l                         4
;   ld (hl),c                     7
;   inc l                         4
;   ld a,l                        4
;   ld (SND_RING_WR),a           13
;   ld hl,(SND_ROM_LEN)          16
;   dec hl                        6
;   dec hl                        6
;   ld (SND_ROM_LEN),hl          16
;   ld a,h                        4
;   or l                          4
;   jp nz,.fillDone              10   ; bytes remain -> skip restart (common)
;                                 -----  producer = 183  (+~6.6 ROM penalty)
;   -- tail --
;   ei                            4
;   jp SndDrv_Sample             10
;                                 =====  FILL = 128 + 21 + 183 + 4 + 10 = 346
;
; ============================ SKIP =======================================
;   COMMON PREFIX ............... 128
;   DISPATCH TAIL ...............  21   (then jp nc taken -> SkipPad)
;   -- SkipPad (= 183, no ROM read) --
;   ld b,13                       7
; .loop: djnz .loop            164   (12 taken*13 + 1 not-taken*8)
;   nop                           4
;   nop                           4
;   nop                           4
;                                 -----  SkipPad = 7 + 164 + 12 = 183
;   ei                            4
;   jp SndDrv_Sample             10
;                                 =====  SKIP = 128 + 21 + 183 + 4 + 10 = 346
;
; ============================ DRAIN ======================================
;   COMMON PREFIX ............... 128   (jp nz taken -> DrainPad; tail NOT run)
;   -- DrainPad (= 204 = 183 + the 21-cyc tail DRAIN skipped, no ROM read) --
;   ld b,15                       7
; .loop: djnz .loop            190   (14 taken*13 + 1 not-taken*8)
;   ld a,0                        7
;                                 -----  DrainPad = 7 + 190 + 7 = 204
;   ei                            4
;   jp SndDrv_Sample             10
;                                 =====  DRAIN = 128 + 204 + 4 + 10 = 346
;
; ALL THREE = 346 cyc EXACTLY (0-cyc spread). Effective DAC rate:
;   dac_rate_hz(346) = 3579545 / 346 = 10345 Hz (int div; see SND_DAC_RATE_HZ).
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
        ld      (SND_CTRL_DMA_ACTIVE), a ; flag bracket clear (no DMA in progress)
        ld      (SND_STAT_PING_ECHO), a
        ld      (SND_STAT_ACK_COUNT), a
        ld      (SND_STAT_TICK), a

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

    ifdef __DEBUG__
        ; ==============================================================
        ; TASK-2 DRY-RUN PUMP — initialise the sequencer with two test
        ; channels (FM1-route + PSG1-route) pointing at the inline test
        ; streams, then arm it. Sequencer_Tick is driven once per VBlank
        ; from SndDrv_ISR (below). NO Timer-A, NO FM/PSG writes — this is a
        ; bounded manual pump that Task 5/6 replaces. REMOVE WITH THE STREAMS.
        ; ==============================================================
        ; clear the whole sequencer header + channel block ($1800..SND_SEQ_END)
        ld      hl, SND_SEQ_BASE
        ld      bc, SND_SEQ_END-SND_SEQ_BASE
.seq_clr:
        ld      (hl), 0
        inc     hl
        dec     bc
        ld      a, b
        or      c
        jr      nz, .seq_clr

        ; --- channel 0: FM1 route ---
        ld      ix, SND_SEQ_CHANNELS
        ld      (ix+sc_stream_ptr), SeqTest_StreamFM & 0FFh
        ld      (ix+sc_stream_ptr+1), SeqTest_StreamFM >> 8
        ld      (ix+sc_route), CHROUTE_FM1
        ld      (ix+sc_flags), SCF_ACTIVE|SCF_IS_FM
        ld      (ix+sc_volume), 127
        ld      (ix+sc_dur_count), 1     ; first tick fetches immediately

        ; --- channel 1: PSG1 route ---
        ld      de, SeqChannel_len
        add     ix, de
        ld      (ix+sc_stream_ptr), SeqTest_StreamPSG & 0FFh
        ld      (ix+sc_stream_ptr+1), SeqTest_StreamPSG >> 8
        ld      (ix+sc_route), CHROUTE_PSG1
        ld      (ix+sc_flags), SCF_ACTIVE|SCF_IS_PSG
        ld      (ix+sc_volume), 127
        ld      (ix+sc_dur_count), 1     ; first tick fetches immediately

        ld      a, 2
        ld      (SND_SEQ_CHCOUNT), a     ; 2 test channels
        xor     a
        ld      (SND_SEQ_TRACE_WR), a    ; trace ring starts empty
        ld      (SND_SEQ_BADOP), a
        inc     a
        ld      (SND_SEQ_ACTIVE), a      ; arm the sequencer (1)
    endif

        ei                               ; state consistent -> allow the VBlank IRQ
        ; falls into the IDLE loop

; ======================================================================
; IDLE loop — DAC inactive. NOT cycle-balanced (it is silence). Keeps the
; `ei` window alive so the VBlank ISR's mailbox poll can flip DAC_ACTIVE=1
; and start a sample. Feeds $80 (DC center) every pass so the output never
; clicks while idle. de=$4001 and reg $2A stay selected, so `ld (de),a`
; lands on the DAC. When a sample starts, jumps into the streaming loop.
; ======================================================================
SndDrv_Idle:
        di
        ld      a, (SND_STAT_DAC_ACTIVE)
        or      a
        jp      nz, SndDrv_Sample        ; sample started -> enter streaming loop
        ld      a, SND_REG_DAC_DATA      ; re-select $2A on the ADDR port ($4000)
        ld      (SND_Z80_YM_A0), a
        ld      a, 80h
        ld      (de), a                  ; DAC <- $80 (DC center silence)
        ei                               ; VBlank IRQ may land here (between samples)
        jp      SndDrv_Idle

; ======================================================================
; SndDrv_Sample — the free-running, every-path-equal-cost streaming loop.
; ONE straight-line iteration per sample. See the balance proof at the top.
; Live registers across iterations: NONE — every value is reloaded from RAM
; at the top of the loop, so the pads and the ISR may clobber any register.
; `de` ($4001) and reg-$2A-selected are invariants maintained outside the loop.
; ======================================================================
SndDrv_Sample:
        di                               ; protect the whole iteration (incl. ROM reads)

        ; --- CONSUMER: re-select $2A on the ADDR port, then output one ring byte.
        ; (Re-selecting every sample is what the proven driver did; the YM2612
        ; address latch is not relied upon to hold across data-only writes — the
        ; data was landing on the wrong reg otherwise. Cost is constant in ALL
        ; three paths, so the balance is preserved.) RAM ring read only — no ROM.
        ld      a, (SND_RING_RD)
        ld      l, a
        ld      h, SND_RING_PAGE
        ld      c, (hl)                  ; c = ring[rd] sample (RAM — never contended)
        ld      a, SND_REG_DAC_DATA      ; $2A
        ld      (SND_Z80_YM_A0), a       ; select DAC DATA reg on the ADDR port ($4000)
        ld      a, c
        ld      (de), a                  ; sample -> YM $2A DATA ($4001)
        inc     l                        ; advance read ptr (wraps within page)
        ld      a, l
        ld      (SND_RING_RD), a

        ; --- DISPATCH: lead = (WR - RD) & $FF, then pick FILL / SKIP / DRAIN ---
        ld      a, (SND_RING_RD)
        ld      c, a
        ld      a, (SND_RING_WR)
        sub     c                        ; a = (WR - RD) & $FF = lead (bytes buffered)
        ld      b, a                     ; stash lead
        ld      a, (SND_CTRL_DMA_ACTIVE)
        or      a
        jp      nz, SndDrv_Drain         ; 68k DMA in progress -> DRAIN (no ROM read)
        ld      a, b
        cp      SND_RING_LEAD_CAP
        jp      nc, SndDrv_Skip          ; ring full (lead >= cap) -> SKIP (no ROM read)
        ; fall through to FILL

        ; --- FILL: read-ahead 2 ROM bytes from the banked window into the ring ---
        ld      hl, (SND_ROM_PTR)
        ld      b, (hl)                  ; ROM byte 1 (banked $8000 window)
        inc     hl
        ld      c, (hl)                  ; ROM byte 2
        inc     hl
        ld      (SND_ROM_PTR), hl
        ld      a, (SND_RING_WR)
        ld      h, SND_RING_PAGE
        ld      l, a
        ld      (hl), b                  ; ring[wr]   = byte 1
        inc     l
        ld      (hl), c                  ; ring[wr+1] = byte 2
        inc     l
        ld      a, l
        ld      (SND_RING_WR), a
        ld      hl, (SND_ROM_LEN)
        dec     hl
        dec     hl                       ; len -= 2 (we consumed 2 ROM bytes)
        ld      (SND_ROM_LEN), hl
        ld      a, h
        or      l
        jp      nz, .fillDone            ; bytes remain (common) -> no restart
        ; --- sample exhausted (rare, once per sample length): loop the blip.
        ; NOT cycle-balanced (req 10) — a small one-off spike, no $2B toggle, no
        ; gap, same continuous stream. Bank never changes (bank-aligned sample).
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
.fillDone:
        ei                               ; THE ONLY ei — IRQ lands here, between samples
        jp      SndDrv_Sample

; --- SKIP path: ring full. Skip the ROM read; burn EXACTLY 183 cyc so the ---
; --- iteration equals FILL. (Pure pad, register-clobber-safe: a,b dead.)   ---
SndDrv_Skip:
        ld      b, 13                    ; 7
.skip_pad:
        djnz    .skip_pad                ; 12*13 + 1*8 = 164
        nop                              ; 4
        nop                              ; 4
        nop                              ; 4    -> pad = 7+164+12 = 183
        ei
        jp      SndDrv_Sample

; --- DRAIN path: 68k DMA in progress. Skip the ROM read (a banked read would ---
; --- stall the Z80 bus for the whole DMA burst — the under-load sag bug);    ---
; --- burn EXACTLY 204 cyc (= FILL producer 183 + the 21-cyc dispatch tail    ---
; --- DRAIN skipped) so the iteration equals FILL. (a,b dead -> safe.)        ---
SndDrv_Drain:
        ld      b, 15                    ; 7
.drain_pad:
        djnz    .drain_pad               ; 14*13 + 1*8 = 190
        ld      a, 0                     ; 7    -> pad = 7+190+7 = 204
        ei
        jp      SndDrv_Sample

; ======================================================================
; SndDrv_ISR — minimal VBlank ISR (RST 38h $0038 -> jp here).
; Mailbox poll ONLY, then ei/ret. NO draining (the 68k flag bracket handles
; DMA survival via the producer's DRAIN path). The poll reads Z80-RAM + the
; $6000 bank latch only — NEVER ROM — so it is DMA-safe even if it fires mid-
; DMA. Preserves every register it touches (it interrupts the main/idle loop).
; `de` ($4001) and `ix` are NOT touched here, so they survive untouched.
; ======================================================================
SndDrv_ISR:
        push    af
        push    bc
        push    de
        push    hl
        call    SndDrv_PollMailbox       ; RAM + $6000 latch only -> DMA-safe
    ifdef __DEBUG__
        ; TASK-2 DRY-RUN PUMP: advance the sequencer one tick per VBlank so the
        ; trace ring fills over frames. RAM-only (writer hooks are stubs), so
        ; DMA-safe. ix is saved/restored to honour the ISR's no-clobber contract.
        ; (Task 5 replaces this with the Timer-A sub-tick poll.)
        push    ix
        call    Sequencer_Tick
        pop     ix
    endif
        pop     hl
        pop     de
        pop     bc
        pop     af
        ei
        ret

; ======================================================================
; SndDrv_PollMailbox — act on any nonzero request slot, then clear it.
; (Reached only via `call` from the ISR.) Does NOT read ROM. Note: this
; routine clobbers de, but the ISR saves/restores it, so the streaming
; loop's de=$4001 invariant is preserved across the interrupt.
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
        ; --- sample request? (Phase 1: any nonzero id -> the test blip) ---
        ld      a, (SND_REQ_SAMPLE)
        or      a
        ret     z                        ; nothing else pending

        ; --- SAMPLE START. Re-assert DAC mode ($2B bit7) in case the 68k's YM
        ; init cleared the once-at-init enable, then re-park the addr port on $2A.
        ; (One-time per sample TRIGGER, not per loop, so no recurring click.) ---
        ld      a, SND_REG_DAC_ENABLE
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2B (select DAC-enable reg)
        ld      a, 80h
        ld      (SND_Z80_YM_A1), a       ; $4001 = $80 -> DAC mode ON
        ld      a, SND_REG_DAC_DATA
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2A (re-park addr port on DAC DATA)
        ; Point the stream source at the banked sample.
        ld      a, SND_BLIP_BANK
        call    SndDrv_SetBank           ; $6000 latch only (DMA-safe)
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl

        ; Reset ring pointers + prime the lead. To avoid a start underrun WITHOUT
        ; reading ROM in the ISR (which could land mid-DMA), we set WR ahead of RD
        ; by SND_RING_LEAD_PRIME and leave those lead bytes at the $80 the ring was
        ; pre-filled with. The consumer therefore plays a brief $80 DC-center
        ; lead-in (~SND_RING_LEAD_PRIME samples) while the FILL producer (2:1
        ; catch-up) overwrites the ring ahead of RD with real sample data — a
        ; click-free lead-in, no ROM read here. (Documented choice, req 8.)
        xor     a
        ld      (SND_RING_RD), a         ; RD = 0
        ; re-stamp the lead region with $80 so the lead-in is clean even after a
        ; prior sample left non-$80 bytes there. RAM-only loop (DMA-safe).
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
        xor     a
        ld      (SND_REQ_SAMPLE), a      ; clear slot
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
        ret

; ======================================================================
; SndDrv_SetBank — select ROM bank in `a` into the Z80 $8000 window; no-op if
; already current. (Reached only via `call`.) MegaPCM 9-bit set-bank trick: the
; latch at $6000 is a 9-bit shift register loaded LSB-first by 9 single-bit
; writes. We cache the last bank in SND_CUR_BANK and skip the 9 writes when the
; requested bank already matches. `a` = (sample_addr & $7F8000) >> 15. Touches
; the $6000 latch only — NEVER ROM — so it is DMA-safe.
; ======================================================================
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

; ======================================================================
; Music sequencer core (Sound 1C, Task 2) — opcode interpreter.
; Included INSIDE the phase-0 blob so its labels (Sequencer_Tick, the jump
; table, the handlers) resolve into Z80 RAM. Hardware-agnostic; the writer
; hooks are `ret` stubs this task. (Comes after the helpers, before the
; even-pad, per the blob layout law.)
; ======================================================================
        include "engine/sound_sequencer.asm"

    ifdef __DEBUG__
; ======================================================================
; TASK-2 DRY-RUN TEST STREAMS (DEBUG only; REMOVE/REPLACE when Task 6 lands
; the real ROM-banked Song_Test). These live in the phase-0 blob so they load
; into Z80 RAM at boot and are directly addressable (no banking, no $8000
; window) — sc_stream_ptr points straight at these labels.
;
; Notes are `db MEV_NOTE_BASE+<pitch>`. The two streams use different routes
; (FM1 vs PSG1) so the trace's high nibble distinguishes them, and exercise:
; set-duration, note, rest, vol, patch, loop-point, jump (FM1 -> loops forever)
; and MEV_END (PSG1 -> goes idle, so the active-flag-clear path is observable).
; ======================================================================
SeqTest_StreamFM:
        db      MEV_PATCH, 1             ; set patch 1            (zero tick)
        db      MEV_VOL, 100             ; set volume 100         (zero tick)
        db      4                        ; set default duration = 4 ticks
        db      MEV_NOTE_BASE+12         ; note pitch 12          (4 ticks)
        db      MEV_NOTE_BASE+16         ; note pitch 16          (4 ticks)
        db      MEV_REST                 ; rest                   (4 ticks)
SeqTest_FM_Loop:
        db      MEV_LOOP_POINT           ; loop target            (zero tick)
        db      MEV_NOTE_BASE+19         ; note pitch 19          (4 ticks)
        db      MEV_NOTE_DUR, 24, 8      ; note 24, explicit dur 8 (8 ticks)
        db      MEV_VOL, 80              ; set volume 80          (zero tick)
        db      MEV_JUMP                 ; jump back to loop point (zero tick)

SeqTest_StreamPSG:
        db      MEV_VOL, 60              ; set volume 60          (zero tick)
        db      3                        ; set default duration = 3 ticks
        db      MEV_NOTE_BASE+24         ; note pitch 24          (3 ticks)
        db      MEV_REST                 ; rest                   (3 ticks)
        db      MEV_NOTE_BASE+28         ; note pitch 28          (3 ticks)
        db      MEV_END                  ; end -> channel goes idle
    endif

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
