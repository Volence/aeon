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
; CYCLE-BALANCE PROOF — FILL == SKIP == DRAIN == 400 Z80 cycles
; (T-states per the AS/Zilog table in the task spec. The banked $8000-window
;  ROM read adds a bounded ~3.3-cyc bus penalty per byte under normal 68k load
;  — that lands ONLY on FILL's two `ld x,(hl)` reads and is inherent to the one
;  path that touches ROM; SKIP/DRAIN never read ROM. The DETERMINISTIC
;  instruction-cycle total is balanced exactly; the ROM penalty is noted, not
;  padded, because it is non-deterministic and unavoidable on FILL alone.)
;
; HISTORY: the deterministic total grew from the original 346 as the loop body
; gained constant per-pass cost, BOTH additions in the common prefix (so equal on
; all three paths — the pads need no rebalance):
;   (a) +24 : the consumer re-selects $2A on the addr port EVERY sample (the YM
;             address latch is not relied upon to hold), so the live consumer is
;             83 cyc, not the original 59.                          (346 -> 370)
;   (b) +30 : the Task-5 Timer-A overflow poll (K = 30).            (370 -> 400)
; The SkipPad (183) and DrainPad (204) are UNCHANGED — both additions live in the
; common prefix, which by construction lands equally on all three paths, so the
; pad-to-FILL balance is untouched. The poll's overflow handler (rearm + call
; Sequencer_Tick) fires only on overflow (tempo $C0 -> ~208 Hz for the loaded
; song, NOT per pass); that one
; pass is momentarily longer — a bounded micro-perturbation (see BOUNDING below).
;
; --- COMMON PREFIX (run by ALL three paths) -------------------------------
;   di                            4
;   ; -- CONSUMER (RAM ring only, never ROM; re-selects $2A every sample) --
;   ld a,(SND_RING_RD)           13
;   ld l,a                        4
;   ld h,SND_RING_PAGE            7
;   ld c,(hl)                     7   ; c = ring[rd] (RAM — never contended)
;   ld a,SND_REG_DAC_DATA         7   ; $2A
;   ld (SND_Z80_YM_A0),a         13   ; re-select DAC DATA reg on $4000
;   ld a,c                        4
;   ld (de),a                     7   ; -> YM $2A DATA ($4001)
;   inc l                         4
;   ld a,l                        4
;   ld (SND_RING_RD),a           13      [consumer subtotal = 83]
;   ; -- DISPATCH prefix --
;   ld a,(SND_RING_RD)           13
;   ld c,a                        4
;   ld a,(SND_RING_WR)           13
;   sub c                         4   ; a = (WR-RD)&$FF = lead
;   ld b,a                        4   ; stash lead
;   ; -- TIMER-A POLL (Task 5; K = 30) — placed BEFORE the DMA dispatch so ALL
;   ;    THREE paths (FILL/SKIP/DRAIN) run it -> K is common, no pad rebalance. --
;   ld a,($4000)                 13   ; YM status: bit0 = Timer A overflow
;   and SND_TIMERA_OVF_MASK       7   ; isolate overflow bit
;   jp nz,SndDrv_TimerATick      10   ; overflow -> rearm + tick (10 taken or not)
;   ld a,(SND_CTRL_DMA_ACTIVE)   13
;   or a                          4
;   jp nz,SndDrv_Drain           10   ; DMA active -> DRAIN  (10 taken or not)
;                                 -----  COMMON PREFIX = 4 + 83 + 30 + 65 = 182
; (poll K = 13+7+10 = 30; dispatch-prefix instrs = 13+4+13+4+4+13+4+10 = 65)
;
; --- DISPATCH TAIL (run by FILL and SKIP only; DRAIN jumped away) ----------
;   ld a,b                        4
;   cp  SND_RING_LEAD_CAP         7
;   jp nc,SndDrv_Skip            10   ; lead >= cap -> SKIP  (10 taken or not)
;                                 -----  TAIL = 21
;
; ============================ FILL =======================================
;   COMMON PREFIX ............... 182
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
;                                 =====  FILL = 182 + 21 + 183 + 4 + 10 = 400
;
; ============================ SKIP =======================================
;   COMMON PREFIX ............... 182
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
;                                 =====  SKIP = 182 + 21 + 183 + 4 + 10 = 400
;
; ============================ DRAIN ======================================
;   COMMON PREFIX ............... 182   (jp nz taken -> DrainPad; tail NOT run)
;   -- DrainPad (= 204 = 183 + the 21-cyc tail DRAIN skipped, no ROM read) --
;   ld b,15                       7
; .loop: djnz .loop            190   (14 taken*13 + 1 not-taken*8)
;   ld a,0                        7
;                                 -----  DrainPad = 7 + 190 + 7 = 204
;   ei                            4
;   jp SndDrv_Sample             10
;                                 =====  DRAIN = 182 + 204 + 4 + 10 = 400
;
; ALL THREE = 400 cyc EXACTLY (0-cyc spread). Effective DAC rate:
;   dac_rate_hz(400) = 3579545 / 400 = 8948 Hz (int div; see SND_DAC_RATE_HZ).
;
; --- BOUNDING the overflow handler (Task 5) --------------------------------
; On overflow the poll's `jp nz,SndDrv_TimerATick` is taken: re-arm Timer A + run
; Sequencer_Tick FULLY INLINE (no channel slicing). Worst-case tick (a patch-load
; ~2300-2600 cyc + the other channels, ~5000 cyc worst case) is ~12.5 sample-times.
; The ring lead budget is SND_RING_LEAD_CAP (250) samples x SND_LOOP_CYC (400) ~
; 100,000 cyc, so worst_tick_cyc (~5000) << that (~5%). The ring CANNOT underrun
; across a tick. (A "service half the channels per overflow" split is held in
; reserve and is NOT needed for 5 FM + 4 PSG.) The handler runs inside the loop's
; `di` window and rejoins the dispatch so the pass still ends at EXACTLY ONE `ei`.
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
        ld      (SND_SEQ_ACTIVE), a      ; sequencer idle until a song loads (Task 6)
        ld      (SND_SEQ_CHCOUNT), a     ; no channels until a song loads

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

        ; The sequencer starts IDLE. Timer A is NOT programmed here (Task 6): the
        ; song loader (Snd_LoadSong, from a SND_REQ_MUSIC request) clears the
        ; sequencer state, inits channels from the loaded SongHeader, programs
        ; Timer A from the header tempo, and arms SND_SEQ_ACTIVE. Until a song is
        ; loaded, SND_SEQ_ACTIVE = 0 (cleared by the RAM clear at boot) so the
        ; Timer-A poll's Sequencer_Tick is a no-op even if an overflow fires.

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
        jp      nz, SndDrv_Sample        ; sample started -> enter streaming loop
        ; --- Timer-A poll (sequencer tick clock while idle) ---
        ld      a, (SND_Z80_YM_A0)       ; YM status ($4000): bit0 = Timer A overflow
        and     SND_TIMERA_OVF_MASK
        call    nz, SndDrv_IdleTick      ; overflow -> rearm + Sequencer_Tick
        ld      a, SND_REG_DAC_DATA      ; re-select $2A on the ADDR port ($4000)
        ld      (SND_Z80_YM_A0), a
        ld      a, 80h
        ld      (de), a                  ; DAC <- $80 (DC center silence)
        ei                               ; VBlank IRQ may land here (between samples)
        jp      SndDrv_Idle

; --- Idle-context Timer-A tick: rearm + advance the song one tick, then restore
; de=$4001 (Sequencer_Tick clobbers de). Returns to the idle loop, which re-checks
; DAC_ACTIVE at the top so a $E2-armed sample enters the streaming loop next pass.
SndDrv_IdleTick:
        call    Snd_TimerA_Rearm         ; clear overflow, keep counting, re-park $2A
        call    Sequencer_Tick           ; advance the song (clobbers af,bc,de,hl,ix)
        ld      de, SND_Z80_YM_A1        ; restore de = $4001 (DAC DATA port invariant)
        ret

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
        ; --- TIMER-A POLL (Task 5): the sequencer-tick clock. Placed in the COMMON
        ; PREFIX *before* the DMA dispatch so ALL THREE paths (FILL/SKIP/DRAIN) run
        ; it -> the K=30 cyc cost is common to every path, no pad rebalance needed.
        ; Reads YM status off $4000 (the addr port, RAM-mapped I/O, never ROM —
        ; DMA-safe). On overflow: rearm + Sequencer_Tick, then rejoin at .afterPoll.
        ; `b` (the stashed lead) is re-derived after the handler (Sequencer_Tick
        ; clobbers b, so SndDrv_TimerATick re-reads the lead before .afterPoll).
.timerA_poll:
        ld      a, (SND_Z80_YM_A0)       ; read YM status ($4000): bit0 = Timer A overflow
        and     SND_TIMERA_OVF_MASK      ; isolate overflow bit
        jp      nz, SndDrv_TimerATick    ; overflow -> rearm + Sequencer_Tick, then rejoin
.afterPoll:
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
; DMA survival via the producer's DRAIN path). ROM-SAFETY (Task 6 nuance): the
; ping/sample request paths read Z80-RAM + the $6000 bank latch ONLY — never ROM
; — so they are DMA-safe even if the ISR fires mid-DMA. The MUSIC-LOAD path is
; the exception: Snd_LoadSong's `ldir` DOES read ROM through the $8000 window, so
; it is NOT ROM-free. It is safe instead because the DAC loop is paused while the
; ISR runs and the ~250-sample ring-lead budget (SND_RING_LEAD_CAP) vastly
; outlasts the few-hundred-byte song copy — the lead absorbs the load.
; Preserves every register it touches (it interrupts the main/idle loop).
; `de` ($4001) and `ix` are NOT touched here, so they survive untouched.
; ======================================================================
SndDrv_ISR:
        push    af
        push    bc
        push    de
        push    hl
        call    SndDrv_PollMailbox       ; RAM + $6000 latch only -> DMA-safe
        ; (Task 5: the per-VBlank Sequencer_Tick PUMP that lived here is REMOVED.
        ; Sequencer_Tick is now driven ONLY by the DAC-loop's Timer-A overflow poll
        ; -> SndDrv_TimerATick. Driving it from both would double-clock the song.)
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
        call    Snd_TimerA_Disable       ; stop Timer A so no more ticks fire
        xor     a
        ld      (SND_REQ_MUSIC), a       ; clear slot (consumed)
        ld      a, (SND_STAT_ACK_COUNT)
        inc     a
        ld      (SND_STAT_ACK_COUNT), a
.after_music:
.no_music:
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
; Snd_DacLookup — map a 1-based DAC sample id (in `a`) to its descriptor ptr.
; Out: hl = &DacSampleTable[id-1], carry CLEAR on success; carry SET (id 0 or
; id > DAC_SAMPLE_COUNT) on a bad id (hl undefined). Clobbers af, de, hl.
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
        ; hl = DacSampleTable + index*DacSample_len (8). index*8 = index<<3.
        ld      l, a
        ld      h, 0
        add     hl, hl
        add     hl, hl
        add     hl, hl                   ; hl = index*8
        ld      de, DacSampleTable
        add     hl, de                   ; hl = &DacSampleTable[index]
        or      a                        ; clear carry (success)
        ret

; ======================================================================
; Snd_StartSample — start DAC playback from a DacSample descriptor at `hl`
; (Task 6 refactor of the 1B SND_REQ_SAMPLE body). Reads bank/ptr/len from the
; 8-byte descriptor (ds_bank +0, ds_ptr +2, ds_length +4), re-asserts DAC mode
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
        ; --- Re-assert DAC mode ($2B bit7) WITHOUT toggling the edge, then re-park
        ; $2A. (One-time per trigger, not per loop -> no recurring click.) ---
        ld      a, SND_REG_DAC_ENABLE
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2B (select DAC-enable reg)
        ld      a, 80h
        ld      (SND_Z80_YM_A1), a       ; $4001 = $80 -> DAC mode ON
        ld      a, SND_REG_DAC_DATA
        ld      (SND_Z80_YM_A0), a       ; $4000 = $2A (re-park addr port on DAC DATA)
        pop     hl                       ; hl = descriptor base
        ; --- bank + stream pointers from the descriptor (ds_* offsets) ---
        ld      a, (hl)                  ; ds_bank (+0)
        call    SndDrv_SetBank           ; $6000 latch only (DMA-safe)
        push    hl
        ld      de, DacSample_ds_ptr     ; +2
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = ds_ptr (window ptr)
        ld      (SND_ROM_PTR), de
        pop     hl
        push    hl
        ld      de, DacSample_ds_length  ; +4
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = ds_length
        ld      (SND_ROM_LEN), de
        pop     hl

        ; Reset ring pointers + prime the lead. To avoid a start underrun WITHOUT
        ; reading ROM (which could land mid-DMA in the ISR context), we set WR
        ; ahead of RD by SND_RING_LEAD_PRIME and leave those lead bytes at the $80
        ; the ring was pre-filled with — a click-free DC-center lead-in while the
        ; FILL producer (2:1 catch-up) overwrites the ring with real sample data.
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
; SndDrv_TimerATick — the Timer-A overflow handler (Task 5). Reached ONLY from
; the common-prefix poll's `jp nz` when YM status bit0 (Timer A overflow) is set.
; Runs INSIDE the streaming loop's `di` window (so Sequencer_Tick is non-reentrant
; w.r.t. the VBlank ISR — the tick and the ISR can never interleave). Steps:
;   1. Snd_TimerA_Rearm  — clear the overflow flag (timer keeps counting from N).
;   2. call Sequencer_Tick — advance the song one tick (FULLY INLINE, no slicing;
;      see the BOUNDING note in the proof — worst tick << ring lead, no underrun).
;   3. re-read the lead into `b` (Sequencer_Tick clobbers b) and rejoin .afterPoll
;      so this pass still runs the DMA/SKIP/FILL dispatch and ends at the ONE `ei`.
; Re-parks reg $2A on $4000 after the rearm's $27 write (the consumer re-selects
; $2A every sample anyway, but Snd_TimerA_Rearm already re-parks — defensive).
; ======================================================================
SndDrv_TimerATick:
        call    Snd_TimerA_Rearm         ; $27 = $15 (clear overflow, keep counting), re-park $2A
        call    Sequencer_Tick           ; advance the song one tick (clobbers af,bc,de,hl,ix)
        ; Sequencer_Tick clobbered b (and de). Restore the loop invariants the
        ; dispatch tail needs: de = $4001, and b = the lead (WR-RD)&$FF.
        ld      de, SND_Z80_YM_A1        ; restore de = $4001 (DAC DATA port invariant)
        ld      a, (SND_RING_RD)
        ld      c, a
        ld      a, (SND_RING_WR)
        sub     c                        ; a = (WR-RD)&$FF = lead
        ld      b, a                     ; b = lead (for the FILL/SKIP dispatch)
        jp      SndDrv_Sample.afterPoll  ; rejoin the common prefix after the poll

; ======================================================================
; Snd_TimerA_Program — load + enable Timer A from a tempo byte in `a` (Task 5).
; tempo = the HIGH 8 bits of N (N = tempo<<2, low 2 bits 0). Writes:
;   $24 = tempo (N>>2, MSB first), $25 = 0 (N&3), $27 = $05 (LOAD:A | ENBL:A).
; ENBL:A (bit2) is REQUIRED — without it the overflow never raises the status
; flag and the common-prefix poll can't see ticks. Uses ABSOLUTE addressing
; ($4000 reg-select / $4001 data) so `de` (the DAC $4001 invariant) is untouched;
; re-parks reg $2A on $4000 at the end (like the FM writer's Fm_ReparkDac).
; Clobbers af, c (c stashes the tempo byte across the reg selects). Caller's
; `de`/`ix` (and `b`) preserved.
; ======================================================================
Snd_TimerA_Program:
        ld      c, a                     ; c = tempo byte (= N>>2); preserve across reg selects
        ; $24 = N>>2 (MSB) — write MSB before LSB.
        ld      a, SND_REG_TIMER_A_HI    ; $24
        ld      (SND_Z80_YM_A0), a       ; select $24 on $4000
        ld      a, c                     ; tempo byte = N>>2
        ld      (SND_Z80_YM_A1), a       ; $4001 = N bits 9..2
        ; $25 = N&3 (LSB) = 0 (tempo maps to N = tempo<<2, low 2 bits clear).
        ld      a, SND_REG_TIMER_A_LO    ; $25
        ld      (SND_Z80_YM_A0), a       ; select $25 on $4000
        xor     a
        ld      (SND_Z80_YM_A1), a       ; $4001 = N bits 1..0 = 0
        ; $27 = LOAD:A | ENBL:A -> start the counter and let overflow raise the flag.
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
        ; touches NO Timer-A state, so the Snd_TimerA_Program call later in this
        ; load fully owns the timer config — the ordering is correct.
        call    Sequencer_StopAll        ; key-off FM + silence PSG + clear active flag

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

        ; channel_count (SH_CHCOUNT) — read via iy = song base (RAM or window).
        ld      iy, (Snd_SongBase)
        ld      a, (iy+SH_CHCOUNT)
        cp      CHROUTE_COUNT+1          ; defensive guard: a corrupt count clamps to 0
        jr      c, .cc_ok                ;   (prevents the channel loop walking ix wild)
        xor     a
.cc_ok:
        ld      (SND_SEQ_CHCOUNT), a
        ld      c, a                     ; c = channel count (loop bound)
        or      a
        jp      z, .arm                  ; 0 channels -> nothing to init (still arm)

        ; iterate the per-channel header records, filling each SeqChannel.
        ; iy = header record ptr (3 bytes each, starting at base+SH_CHANNELS);
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
        ; stream_ptr: BIG-ENDIAN 16-bit OFFSET in the header -> add the song base.
        ld      h, (iy+SHC_PTR_HI)       ; high byte first (big-endian)
        ld      l, (iy+SHC_PTR_LO)
        ld      de, (Snd_SongBase)
        add     hl, de                   ; hl = base + offset (RAM or window address)
        ld      (ix+sc_stream_ptr), l
        ld      (ix+sc_stream_ptr+1), h
        ; flags: ACTIVE + route-class bit (FM / PSG / DAC) from the route value.
        ld      a, (iy+SHC_ROUTE)
        call    Snd_RouteClassFlags      ; a = SCF_ACTIVE | class bit (for this route)
        ld      (ix+sc_flags), a
        ; sensible default volume + first-tick-fetches-immediately.
        ld      (ix+sc_volume), 100
        ld      (ix+sc_dur_count), 1
        ; advance to the next header record + SeqChannel.
        ld      de, SHC_LEN
        add     iy, de
        ld      de, SeqChannel_len
        add     ix, de
        pop     bc
        dec     c
        jr      nz, .chan_init

.arm:
        ; (SND_SEQ_PATCHTAB was set per-path above: FmPatchInlineTable for the copy
        ; path, the song's patch-bank window ptr for the stream path.)
        ; DEBUG trace/visibility housekeeping.
        xor     a
        ld      (SND_SEQ_TRACE_WR), a
        ld      (SND_SEQ_BADOP), a
        ; tempo -> Timer A (the song's tick clock). Read via the song base.
        ld      iy, (Snd_SongBase)
        ld      a, (iy+SH_TEMPO)
        ld      (SND_SEQ_TEMPO), a
        call    Snd_TimerA_Program
        ; arm the sequencer.
        ld      a, 1
        ld      (SND_SEQ_ACTIVE), a
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
; Music sequencer core (Sound 1C, Task 2) — opcode interpreter.
; Included INSIDE the phase-0 blob so its labels (Sequencer_Tick, the jump
; table, the handlers) resolve into Z80 RAM. Hardware-agnostic; the writer
; hooks are `ret` stubs this task. (Comes after the helpers, before the
; even-pad, per the blob layout law.)
; ======================================================================
        include "engine/sound_sequencer.asm"

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

; --- Inline Z80-addressable FM tables (GENERATED) ---
; FmPitchTableZ / LogVolumeLutZ / CarrierMaskTableZ — read by the FM writer with
; direct Z80 addressing. Identical VALUES to the 68k ROM tables in
; data/sound/sound_tables.asm (decision 1: inline for 1C, not banked).
        include "engine/sound_tables_z80.asm"

; --- Inline FM patch table (Z80-addressable) ---
; Fm_PatchPtr indexes this by sc_patch (TEMP for 1C — Task 6 switches to the
; banked 68k ROM FmPatchTable in data/sound/fm_patches.asm). The patch BYTES are
; single-sourced from data/sound/fm_patches.inc (the SAME records the 68k ROM
; FmPatchTable includes), so the inline copy and the ROM copy can never drift.
; The .inc emits via a `pbyte` macro that selects `db` here (Z80) vs `dc.b` in
; the 68k ROM. CLEARLY-TEMP bring-up data; FmPatch_len = 26 bytes/record.
FmPatchInlineTable:
        include "data/sound/fm_patches.inc"
FmPatchInlineTable_End:

        if (FmPatchInlineTable_End-FmPatchInlineTable) <> 2*FmPatch_len
          fatal "inline FM patch table wrong size"
        endif

; --- Inline DAC sample descriptor table (Task 6 decision 3) ---
; Maps a 1-based sample id to an 8-byte DacSample record (see the struct in
; sound_constants.asm). For 1C, id 1 = the temp_blip; its bank/ptr/len are the
; build-time SND_BLIP_* constants (from data/sound/dac_samples.asm), so an INLINE
; descriptor in the Z80 blob needs no banking to read. rate/loop_ofs are 0 (the
; 1B FILL loop drives the rate via the loop trip-time, and re-triggers each $E2 —
; the FILL-exhaust restart still uses SND_BLIP_PTR/LEN, matching id 1).
DacSampleTable:
        ; id 1 = temp_blip
        db      SND_BLIP_BANK            ; ds_bank
        db      0                        ; ds_rate (unused — loop trip-time is the clock)
        dw      SND_BLIP_PTR             ; ds_ptr (little-endian dw)
        dw      SND_BLIP_LEN             ; ds_length
        dw      0                        ; ds_loop_ofs (0 = one-shot; FILL restart uses SND_BLIP_*)
DacSampleTable_End:

        if (DacSampleTable_End-DacSampleTable) <> DAC_SAMPLE_COUNT*DacSample_len
          fatal "DacSampleTable wrong size for DAC_SAMPLE_COUNT"
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
