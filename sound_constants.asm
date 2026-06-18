; ======================================================================
; sound_constants.asm — shared 68k/Z80 sound equates (single source of truth)
; See docs/superpowers/specs/2026-06-16-sound-command-api.md and -z80-ram-map.md
; ======================================================================

; --- Z80-space base addresses (as seen from the 68k bus) ---
SND_Z80_BASE            = Z80_RAM                ; $A00000 (from constants.asm)

; --- Request slots (Z80 offsets; 68k address = SND_Z80_BASE + offset) ---
; Per-command-type byte slots, Flamedriver model: 68k writes a nonzero value,
; the Z80 acts and clears the slot to 0 (latest-wins). No shared record, no
; pending flag, no wait-idle spin — different command types never clobber each
; other, so several can be posted in one frame. (1A audit, 2026-06-16.)
SND_REQ_BASE            = $1F00
SND_REQ_PING            = SND_REQ_BASE+$00       ; debug: echo this value (0 = idle)
SND_REQ_SAMPLE          = SND_REQ_BASE+$01       ; DAC sample id (0 = idle)
; SND_REQ_MUSIC encoding (Task 6): 0 = idle/nothing pending; 1..$FE = play
; SongTable[id-1]; $FF = STOP (a reserved sentinel — 0 cannot mean stop because
; 0 is the "no request" value in the latest-wins slot). The 68k posts the song
; id (or $FF) here AFTER posting the SND_MUSIC_PARAM block, under the SAME bus
; hold, so the Z80 never reads a half-updated param block.
SND_REQ_MUSIC           = SND_REQ_BASE+$02       ; music command (0 idle / 1..$FE play / $FF stop)
SND_REQ_SFX             = SND_REQ_BASE+$03       ; reserved (Phase 1C)
SND_MUSIC_STOP          = $FF                    ; SND_REQ_MUSIC stop sentinel

; --- Status / ack region (Z80 writes, 68k reads) ---
SND_STAT_BASE           = $1F10
SND_STAT_ALIVE          = SND_STAT_BASE+$00      ; driver writes SND_ALIVE_MARKER
SND_STAT_PING_ECHO      = SND_STAT_BASE+$01
SND_STAT_ACK_COUNT      = SND_STAT_BASE+$02      ; +1 per consumed request
SND_STAT_TICK           = SND_STAT_BASE+$03      ; scheduler tick counter
SND_STAT_DAC_ACTIVE     = SND_STAT_BASE+$04      ; 1 while a sample plays

SND_ALIVE_MARKER        = $5A

; --- Sample IDs ---
SND_SAMPLE_TEST         = 1                       ; Foundations test tone

; --- Playback state (Z80 RAM addresses in the state region) ---
SND_STATE_BASE          = $1600
SND_TEST_SAMPLE         = $1C00                  ; runtime-generated test sample
SND_TEST_SAMPLE_LEN     = 256
SND_PLAY_ACTIVE         = SND_STATE_BASE+$00     ; 1 = sample playing
SND_PLAY_PTR            = SND_STATE_BASE+$02      ; current sample read pointer
SND_PLAY_LEN            = SND_STATE_BASE+$04      ; bytes remaining
SND_DAC_RATE            = $10                     ; per-sample djnz delay (test tone)

; --- 1B: VBlank-ISR adaptive drain (samples output with NO ROM read while the
; 68k runs its VDP/DMA inside VBlank). The ISR drains UNTIL the 68k acks "DMA
; done" (SND_CTRL_DMA_ACTIVE -> 1), capped by SND_DRAIN_MAX so it can never
; underrun the ring lead or hang. SND_DRAIN_PAD pads each drained sample to ~match
; the FILL+PLAY per-sample cycle count so the pitch is identical across the seam.
; Controller tunes SND_DRAIN_PAD / SND_DRAIN_MAX against real DMA load. ---
SND_DRAIN_SAMPLES       = 32                      ; (legacy fixed window — unused by 1B adaptive drain)
SND_DRAIN_MAX           = 192                     ; safety cap (< the 252-byte ring lead) — bounds the adaptive drain
SND_DRAIN_PAD           = SND_DAC_RATE            ; per-drained-sample pad ~matching FILL+PLAY (controller tunes)

; --- YM2612 ports as seen from the Z80 ($4000-$4003) ---
SND_Z80_YM_A0           = $4000                  ; addr part I / status read (reg select)
SND_Z80_YM_A1           = $4001                  ; data part I — DAC $2A write target (de invariant)
SND_Z80_YM_A2           = $4002                  ; addr part II (FM ch 4-6 register select)
SND_Z80_YM_A3           = $4003                  ; data part II
SND_REG_DAC_DATA        = $2A                    ; YM reg: DAC sample byte (parked in the addr port)
SND_REG_DAC_ENABLE      = $2B                    ; YM reg: bit7 = DAC mode (written ONCE at init)

; --- YM2612 FM register bases (Task 3 FM voice writer) ---
; Per-channel regs add the channel-within-part index (0..2): e.g. $A0+ch.
; Per-operator regs add (op*4)+ch: e.g. $40+(op*4)+ch (op 0..3 = S1,S3,S2,S4).
SND_REG_KEY_ONOFF       = $28                    ; key on/off (GLOBAL, always via part I)
SND_REG_FNUM_LO         = $A0                    ; +ch : F-number low 8 bits
SND_REG_FNUM_HI         = $A4                    ; +ch : block(7..3) | F-number high(2..0) — write FIRST
SND_REG_ALG_FB          = $B0                    ; +ch : algorithm(0-2) | feedback(3-5)
SND_REG_LR_AMS_FMS      = $B4                    ; +ch : L/R(6-7) | AMS(4-5) | FMS(0-2)
SND_REG_OP_DT_MUL       = $30                    ; +(op*4)+ch : detune | multiple
SND_REG_OP_TL           = $40                    ; +(op*4)+ch : total level (volume-modulated on carriers)
SND_REG_OP_RS_AR        = $50                    ; +(op*4)+ch : rate scale | attack rate
SND_REG_OP_AM_D1R       = $60                    ; +(op*4)+ch : AM | first decay rate
SND_REG_OP_D2R          = $70                    ; +(op*4)+ch : second decay rate
SND_REG_OP_D1L_RR       = $80                    ; +(op*4)+ch : decay level | release rate
SND_FM_KEYON_OPMASK     = $F0                    ; key-on byte = $F0 | chsel (all 4 ops on)
SND_FM_TL_MAX           = $7F                    ; TL is 7-bit; $7F = silent, 0 = loud
; Timer A regs — the MegaPCM-2 streaming loop is still the SAMPLE clock (loop
; trip-time, req 9). Timer A is now the SEQUENCER TICK clock (Sound 1C Task 5):
; the DAC loop polls Timer A's overflow flag once per pass (common prefix) and on
; overflow re-arms + calls Sequencer_Tick. Timer A does NOT drive the DAC rate.
SND_REG_TIMER_A_HI      = $24                    ; Timer A value bits 9..2
SND_REG_TIMER_A_LO      = $25                    ; Timer A value bits 1..0
SND_REG_TIMER_CTRL      = $27                    ; load/enable/reset Timer A & B
; Timer A control-byte values written to $27 (Task 5):
;   LOAD:A (bit0) = start/reload counter from N, ENBL:A (bit2) = let the overflow
;   raise the status flag (WITHOUT it the poll never sees overflows), RST:A (bit4)
;   = one-shot strobe that CLEARS the overflow status flag (timer keeps counting).
SND_TIMERA_CTRL_BIT_LOAD = 0
SND_TIMERA_CTRL_BIT_ENBL = 2
SND_TIMERA_CTRL_BIT_RST  = 4
SND_TIMERA_CTRL_PROGRAM = (1<<SND_TIMERA_CTRL_BIT_LOAD)|(1<<SND_TIMERA_CTRL_BIT_ENBL)             ; $05 : LOAD:A | ENBL:A
SND_TIMERA_CTRL_REARM   = (1<<SND_TIMERA_CTRL_BIT_LOAD)|(1<<SND_TIMERA_CTRL_BIT_ENBL)|(1<<SND_TIMERA_CTRL_BIT_RST) ; $15 : LOAD:A | ENBL:A | RST:A
; DISABLE: strobe RST:A (bit4) to CLEAR the pending overflow status flag WHILE
; leaving LOAD:A (bit0) and ENBL:A (bit2) CLEAR so the timer stays off. A bare
; $27=0 disables the counter but does NOT clear an already-pending overflow flag,
; so the very next DAC/idle-loop poll would still see overflow and RE-ARM the
; timer (resurrecting it). $10 clears the flag AND keeps the timer disabled, so
; StopMusic durably stops the ticks.
SND_TIMERA_CTRL_DISABLE = (1<<SND_TIMERA_CTRL_BIT_RST)                                            ; $10 : RST:A only (clear flag, timer OFF)
SND_TIMERA_OVF_MASK     = 1                       ; $4000 status bit0 = Timer A overflow

        if SND_TIMERA_CTRL_PROGRAM <> $05
          error "SND_TIMERA_CTRL_PROGRAM must be $05 (LOAD:A|ENBL:A)"
        endif
        if SND_TIMERA_CTRL_REARM <> $15
          error "SND_TIMERA_CTRL_REARM must be $15 (LOAD:A|ENBL:A|RST:A)"
        endif
        if SND_TIMERA_CTRL_DISABLE <> $10
          error "SND_TIMERA_CTRL_DISABLE must be $10 (RST:A only)"
        endif

; --- Tempo: YM Timer A programming from the song-header tempo byte (Task 5) ---
; YM Timer A is a 10-bit value N (0..1023): reg $24 = N>>2 (bits 9..2), reg $25 =
; N&3 (bits 1..0). The counter COUNTS UP and overflows when it passes 1024, so the
; overflow PERIOD = 18.773us * (1024 - N) on NTSC.
;
; DECISION 1 — SongHeader `tempo` byte -> N mapping: tempo is the HIGH 8 bits of N
; (N = tempo << 2, low 2 bits 0). Then Snd_TimerA_Program writes $24 = tempo (the
; byte directly), $25 = 0, $27 = $05 — no shift at runtime, the 10-bit value is
; just the byte placed in the high register. DIRECTION (correcting the spec's
; wrong "bigger = slower"): N = tempo<<2, period = 18.773us*(1024 - N), so a
; BIGGER tempo byte => bigger N => SMALLER (1024-N) => SHORTER period => FASTER
; ticks. tempo $00 = slowest (N=0, ~19.2ms period ~52Hz), tempo $FF = fastest
; (N=1020, ~75us period ~13.3kHz). Musically useful range is the low-to-mid bytes.
;
; Build-time period/rate helpers (self-documenting, never hand-tuned literals;
; the 1A audit found $C0 had been misread as N=192 vs N=768):
; These document the LIVE mapping Snd_TimerA_Program implements at runtime (it
; writes the tempo byte straight to $24 = N>>2, $25 = 0). They are uncalled in
; the shipping build (the Task-5 dry-run tempo + the legacy ticks/frame timebase
; that used to consume them were removed when Task 6 wired the real song loader);
; AS `function` defs emit no bytes, so they stay purely as self-documenting math.
ym_timerA_n_from_tempo  function tb, ((tb) << 2)                          ; N = tempo<<2
ym_timerA_period_ns     function tb, ((1024 - ym_timerA_n_from_tempo(tb)) * 18773)
ym_timerA_hz            function tb, (1000000000 / ym_timerA_period_ns(tb)) ; ticks/sec (int div)

; --- 1B: ring buffer (page-aligned, 256 bytes) ---
SND_RING_BASE           = $1700                  ; Z80 addr; high byte $17 is the page
SND_RING_PAGE           = $17                     ; high byte for `inc l` wrap + full-check
SND_RING_LEN            = $100

; --- MegaPCM-2 streaming loop: read-ahead lead bounds (req 2, req 8) ---
; SND_RING_LEAD_CAP : lead = (WR-RD)&$FF at/above which the producer takes the
;   SKIP path (ring full, no ROM read). Kept a few bytes below 256 so the WR
;   pointer can never lap RD (guard band = 256 - CAP).
; SND_RING_LEAD_PRIME : lead established at sample start. The lead region is left
;   as the $80 the ring is pre-filled with, giving a brief click-free DC-center
;   lead-in (~PRIME samples) while the producer catches up — no ROM read in the
;   ISR (DMA-safe sample start). PRIME < CAP so the producer keeps filling.
SND_RING_LEAD_CAP       = 250                     ; ring-full guard (6-byte margin to 256)
SND_RING_LEAD_PRIME     = 128                     ; $80 lead-in length at sample start

; --- Effective DAC sample rate (build-time, self-documenting; req 9) ---
; The streaming loop is free-running: the loop trip-time IS the sample clock.
; Every balanced path (FILL/SKIP/DRAIN) costs SND_LOOP_CYC Z80 cycles, so the
; output rate = Z80 clock / loop cycles. This recomputes if the loop body
; changes — bump SND_LOOP_CYC to the new balanced FILL total and the rate (and
; any rate-derived math) follows. (S2/S3K pcmLoopCounter pattern.)
Z80_CLOCK_HZ            = 3579545                  ; NTSC Z80 clock (master/15)
dac_rate_hz  function cyc, (Z80_CLOCK_HZ / (cyc))
; 370 = consumer re-selects $2A each sample; +30 = the Task-5 Timer-A overflow
; poll in the common prefix (ld a,($4000) 13 + and 1 7 + jp nz 10 = K = 30 cyc,
; added EQUALLY to FILL/SKIP/DRAIN because it lives in the common prefix).
SND_LOOP_CYC            = 400                      ; balanced FILL/SKIP/DRAIN total (370 + 30-cyc Timer-A poll)
SND_DAC_RATE_HZ         = dac_rate_hz(SND_LOOP_CYC) ; = 8948 Hz (3579545/400, int div)

; --- 1B: 68k->Z80 control (68k writes, Z80 reads) ---
SND_CTRL_DMA_ACTIVE     = SND_REQ_BASE+$04        ; $1F04: 1 = 68k DMA in progress (no ROM reads)

; --- 1B: playback/stream state (Z80 RAM, state region) ---
SND_RING_RD             = SND_STATE_BASE+$06      ; ring read (drain) ptr low byte
SND_RING_WR             = SND_STATE_BASE+$07      ; ring fill ptr low byte
SND_ROM_PTR             = SND_STATE_BASE+$08      ; current ROM window ptr (2 bytes)
SND_ROM_LEN             = SND_STATE_BASE+$0A      ; bytes remaining in sample (2 bytes)
SND_ROM_BANK            = SND_STATE_BASE+$0C      ; sample's bank id
SND_CUR_BANK            = SND_STATE_BASE+$0D      ; cached current bank (SetBank no-op check)
SND_LOOP_OFS            = SND_STATE_BASE+$0E      ; loop restart offset within sample (0 = one-shot)
SND_PLAY_MODE           = SND_STATE_BASE+$0F      ; 0 = FILL+PLAY, 1 = DRAIN (no ROM reads)

; --- 1B: 8-byte ROM-resident sample descriptor ---
DacSample struct
ds_bank         ds.b 1          ; +0  bank id = (addr & $7F8000) >> 15
ds_rate         ds.b 1          ; +1  per-sample rate delay (pitch); 0 = max
ds_ptr          ds.w 1          ; +2  Z80-window ptr: (addr & $7FFF) | $8000, little-endian
ds_length       ds.w 1          ; +4  byte count
ds_loop_ofs     ds.w 1          ; +6  loop restart offset (0 = one-shot)
DacSample endstruct

        if DacSample_len <> 8
          error "DacSample struct is \{DacSample_len} bytes, expected 8"
        endif

; --- Z80 bank register (as seen from the Z80) ---
SND_Z80_BANKREG         = $6000

; --- SN76489 PSG port (as seen from the Z80) ---
; The PSG is mapped at $7F11 in the Z80 address space. Writes are single bytes
; with NO inter-byte delay (latch+data back-to-back, unlike the YM2612) and NO
; bus contention guard (the Z80 owns the bus; PSG writes never touch $4000-$4003
; or `de`, so the 1B DAC loop's de=$4001 invariant is untouched by construction).
SND_Z80_PSG             = $7F11                  ; PSG write port (Z80 view of the VDP PSG port)
; PSG command-byte bases. Latch byte D7=1 selects a register: D6-D5 = channel
; (00/01/10 tone1/2/3, 11 noise), D4 = type (0 = tone/freq-low, 1 = vol/noise-ctrl).
;   tone freq latch  = $80 | (ch<<5)            (ch 0/1/2 -> $80/$A0/$C0)
;   tone/noise volume = $90 | (ch<<5) | atten   (ch 0/1/2 -> $90/$B0/$D0, noise $F0)
;   noise control     = $E0 | (mode<<2) | rate
SND_PSG_TONE_LATCH      = $80                    ; +(ch<<5) : tone freq-low latch (data byte = freq-high)
SND_PSG_VOL_LATCH       = $90                    ; +(ch<<5)|atten : channel attenuation (atten $0F = silent)
SND_PSG_NOISE_CTRL      = $E0                    ; |(mode<<2)|rate : noise control byte
SND_PSG_NOISE_VOL       = $F0                    ; |atten : noise channel attenuation
SND_PSG_ATTEN_SILENT    = $0F                    ; 4-bit attenuation = silence
; PSG silence-all: max attenuation on tone1/tone2/tone3/noise ($9F/$BF/$DF/$FF).
SND_PSG_SILENCE_T1      = $9F
SND_PSG_SILENCE_T2      = $BF
SND_PSG_SILENCE_T3      = $DF
SND_PSG_SILENCE_N       = $FF

; ======================================================================
; Music format v0 (Sound 1C) — build-time contract shared 68k/Z80/Python.
; The Python tools (tools/gen_sound_tables.py, tools/song_packer.py) emit
; data that matches these equates; the Z80 sequencer (Task 2+) consumes it.
; ======================================================================

; --- Music event-list opcodes (v0) ---
; $00–$7F : set default duration = value (ticks)   [range-dispatched]
MEV_REST        = $80    ; rest for default duration (key-off + advance)
; $81–$DF : note, pitch index = byte-$81           [range-dispatched]
MEV_NOTE_BASE   = $81    ; pitch 0 = MEV_NOTE_BASE
MEV_NOTE_MAX    = $DF    ; highest note opcode (pitch index 0..$5E)
MEV_VOL         = $E0    ; + vv  : set channel volume (linear 0..127)
MEV_PATCH       = $E1    ; + pp  : set FM patch index
MEV_DAC         = $E2    ; + ss  : DAC trigger sample id (DAC channel only)
MEV_NOTE_DUR    = $E3    ; + nn dd : note nn with explicit duration dd
; $E4 reserved for MEV_PAN (Sound 1D Task 4 — do NOT define here).
MEV_NOTE_RAW    = $E7    ; + a4 a0 dd : key a RAW-frequency FM note (exact $A4/$A0
                         ; bytes) for duration dd, bypassing FmPitchTableZ. Lets a
                         ; VGM-derived song reproduce the original chip pitch
                         ; EXACTLY (incl. sub-C0 bass + microtuning the note table
                         ; can't reach). FM-only (PSG ignores). Sound 1D §5.2.
; Bounded-repeat opcodes (Sound 1D Task 1): a body wrapped in REPEAT_START..
; REPEAT_END replays `nn` total times WITHOUT being unrolled in the data. The
; packer encodes them now; the Z80 sequencer interprets them in a later engine
; task (a small repeat-counter stack per channel). They let Moving Trucks ship
; at ~8KB instead of the ~100KB a full unroll would cost.
MEV_REPEAT_START = $E5   ; (no operand) start of a repeatable body
MEV_REPEAT_END   = $E6   ; + nn : replay from matching REPEAT_START nn times (1..255)
MEV_LOOP_POINT  = $EE    ; loop-target marker (no operand)
MEV_JUMP        = $EF    ; jump to loop point
MEV_END         = $FF    ; end of stream (channel idle)
; reserved for Phase 3: $E4 (MEV_PAN, T4), $E8–$ED, $F0–$FE (unknown opcode = build/validation error)

        ; the bounded-repeat opcodes live in the reserved $E4–$ED command block,
        ; above the note range and clear of MEV_PAN ($E4) / the loop opcodes.
        if (MEV_REPEAT_START <= MEV_NOTE_MAX) || (MEV_REPEAT_END <= MEV_NOTE_MAX)
          error "MEV_REPEAT_* must be command opcodes (> MEV_NOTE_MAX)"
        endif
        if (MEV_REPEAT_START = MEV_REPEAT_END) || (MEV_REPEAT_START = MEV_LOOP_POINT) || (MEV_REPEAT_END = MEV_LOOP_POINT)
          error "MEV_REPEAT_* opcode collision"
        endif

        ; opcode ranges must not overlap: the top note opcode is below the
        ; first command opcode, so the range dispatch is unambiguous.
        if MEV_NOTE_MAX >= MEV_VOL
          error "MEV_NOTE_MAX (\{MEV_NOTE_MAX}) must be < MEV_VOL (\{MEV_VOL})"
        endif

; --- Channel-route enum ---
; Sound 1D: FM6 is now a routable FM voice (the "adaptive FM6 slot", §5.1). It
; maps to YM part II, channel-in-part 2, chsel $06 — which falls out NATURALLY
; from Fm_RoutePart/Fm_ChSel (route>=3 -> part II, ch = route-3; route 5 -> ch 2)
; with NO writer change, so CHROUTE_FM6 is inserted contiguously after FM5 (= 5)
; and the PSG/DAC routes shift up by one. FM6 and the DAC are mutually exclusive
; on the YM2612 (ch6 is shared via $2B bit7): a song declares which role FM6 plays
; (DAC by default; FM via the SongHeader flags byte — see SH_FLAGS below). The
; DAC route ($E2 trigger channel) still exists for FM6=DAC songs.
CHROUTE_FM1 = 0
CHROUTE_FM2 = 1
CHROUTE_FM3 = 2
CHROUTE_FM4 = 3
CHROUTE_FM5 = 4
CHROUTE_FM6 = 5    ; Sound 1D: 6th FM voice (part II ch2, chsel $06) — DAC-off songs
CHROUTE_PSG1 = 6
CHROUTE_PSG2 = 7
CHROUTE_PSG3 = 8
CHROUTE_PSGN = 9    ; PSG noise
CHROUTE_DAC  = 10   ; emits $E2 DAC triggers only
CHROUTE_COUNT = 11

        if CHROUTE_COUNT <> 11
          error "CHROUTE_COUNT (\{CHROUTE_COUNT}) must be 11"
        endif
        ; The route still fits the trace byte's high nibble (route<<4 | event):
        ; CHROUTE_COUNT-1 = 10 <= 15, no carry-out in Seq_Trace.
        if (CHROUTE_COUNT-1) > 15
          error "route no longer fits the trace byte high nibble"
        endif
        ; FM6 must resolve to part II ch 2 via Fm_RoutePart's route-3 split.
        if (CHROUTE_FM6 - 3) <> 2
          error "CHROUTE_FM6 must map to part II channel-in-part 2"
        endif

; --- FmPatch struct (the YM record) ---
; 4 operators × 6 per-op regs + 2 channel regs = 26 bytes.
;
; OPERATOR ORDERING (resolved by research — Task 3 writer must agree):
; The YM2612 register stride is +4 between operators within a channel, and the
; on-hardware operator order is S1, S3, S2, S4 — i.e. register offsets +0,+4,
; +8,+C map to operators S1,S3,S2,S4 respectively. The 4-byte per-op arrays
; below (fp_dt_mul etc.) are stored in PHYSICAL REGISTER ORDER: array index
; 0..3 = register offset +0,+4,+8,+C = operators S1,S3,S2,S4. The Task-3
; register writer emits them in this same order (just add the per-channel base
; address and stride by +4). carrier_mask_table bit i (i=0..3) likewise selects
; the operator at offset +i*4, so the mask and these arrays use one index space.
FmPatch struct
fp_alg_fb     ds.b 1          ; $B0 value: algorithm (bits0-2) + feedback (bits3-5)
fp_lr_ams_fms ds.b 1          ; $B4 value: L/R (bits6-7) + AMS (bits4-5) + FMS (bits0-2)
fp_dt_mul     ds.b 4          ; $30+ : DT/MUL per operator
fp_tl         ds.b 4          ; $40+ : TL per operator (carrier TL is volume-modulated)
fp_rs_ar      ds.b 4          ; $50+ : RS/AR per operator
fp_am_d1r     ds.b 4          ; $60+ : AM/D1R per operator
fp_d2r        ds.b 4          ; $70+ : D2R per operator
fp_d1l_rr     ds.b 4          ; $80+ : D1L/RR per operator
FmPatch endstruct             ; = 2 + 6*4 = 26 bytes

        if FmPatch_len <> 26
          error "FmPatch struct is \{FmPatch_len} bytes, expected 26"
        endif

; --- SeqChannel struct (per-channel sequencer state; Z80 RAM, indexed by ix) ---
; DECISION (resolved by research — keep 11 bytes, do NOT pad to 16): (ix+d)
; indexed access costs the same for any displacement d, and the tick loop
; iterates channels sequentially with `add ix,de` (de = SeqChannel_len) — the
; struct size is ADDED directly, never MULTIPLIED by an index, so there is no
; power-of-2 benefit to padding. (If a future path computes a channel base from
; an integer index at runtime, revisit; Task 2 never does.)
SeqChannel struct
sc_stream_ptr   ds.w 1   ; +0  current read ptr into the channel byte stream
sc_dur_count    ds.b 1   ; +2  ticks remaining on the current note/rest
sc_dur_default  ds.b 1   ; +3  default duration for bare notes
sc_patch        ds.b 1   ; +4  current FM patch index
sc_volume       ds.b 1   ; +5  current channel volume (linear 0..127)
sc_note         ds.b 1   ; +6  current pitch index (for key-off / debug)
sc_flags        ds.b 1   ; +7  bit0=active, bit1=keyed, bit2=is_fm, bit3=is_psg, bit4=is_dac
sc_route        ds.b 1   ; +8  channel route enum (CHROUTE_*) — selects the writer
sc_loop_ptr     ds.w 1   ; +9  saved loop-point ptr (set by $EE, used by $EF)
; --- bounded-repeat state (Sound 1D): one level, NO nesting. The transcoder
; emits FLAT, single-level REPEAT_START..REPEAT_END bodies, so a single ptr +
; count per channel is sufficient (nested repeats are UNSUPPORTED by design).
sc_repeat_ptr   ds.w 1   ; +11 body-start ptr saved by $E5, reloaded by $E6 on jump-back
sc_repeat_count ds.b 1   ; +13 reps remaining (0 = no active repeat / fresh-OR-done)
SeqChannel endstruct      ; = 14 bytes

        if SeqChannel_len <> 14
          error "SeqChannel struct is \{SeqChannel_len} bytes, expected 14"
        endif

; Short field-offset accessors (AS struct fields are exposed as
; SeqChannel_<field>; these `sc_*` aliases keep the Z80 (ix+d) code terse).
sc_stream_ptr   = SeqChannel_sc_stream_ptr
sc_dur_count    = SeqChannel_sc_dur_count
sc_dur_default  = SeqChannel_sc_dur_default
sc_patch        = SeqChannel_sc_patch
sc_volume       = SeqChannel_sc_volume
sc_note         = SeqChannel_sc_note
sc_flags        = SeqChannel_sc_flags
sc_route        = SeqChannel_sc_route
sc_loop_ptr     = SeqChannel_sc_loop_ptr
sc_repeat_ptr   = SeqChannel_sc_repeat_ptr
sc_repeat_count = SeqChannel_sc_repeat_count

; --- sc_flags bit numbers + masks ---
; Z80 bit/set/res take a bit INDEX, not a mask, so the sequencer uses the _B
; companions; the SCF_* masks are for 68k-style mask ops (e.g. SCF_ACTIVE|SCF_IS_FM).
; Single source of truth: each mask is derived from its _B bit number below.
SCF_ACTIVE_B    = 0       ; channel is playing its stream
SCF_KEYED_B     = 1       ; a note is currently keyed-on
SCF_IS_FM_B     = 2       ; route class: FM voice
SCF_IS_PSG_B    = 3       ; route class: PSG voice
SCF_IS_DAC_B    = 4       ; route class: DAC trigger channel
SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B)
          error "SCF_* masks and _B bit numbers are out of sync"
        endif

; --- Sequencer RAM block (Z80 space) ---
; Lives at $1800, ABOVE the 1B DAC ring at $1700. (The plan's illustrative guard
; `if SND_SEQ_END > SND_RING_BASE` is WRONG — the sequencer is above the ring,
; not below it. The real map: code $0000-$15FF, state $1600-$16FF, DAC ring
; $1700-$17FF, FREE $1800-$1EFF, mailbox/status $1F00-$1F1F, stack top $1FFE.
; We place the sequencer region at $1800 and guard its END against the mailbox
; base SND_REQ_BASE ($1F00), leaving stack headroom.)
SND_SEQ_BASE       = $1800          ; sequencer state region (free block above the DAC ring)
SND_SEQ_TEMPO      = SND_SEQ_BASE+$00   ; loaded song tempo (Timer-A selector)
SND_SEQ_CHCOUNT    = SND_SEQ_BASE+$01   ; active channel count (tick-loop djnz bound)
SND_SEQ_PATCHTAB   = SND_SEQ_BASE+$02   ; loaded patch table ptr (2)
SND_SEQ_ACTIVE     = SND_SEQ_BASE+$04   ; 1 = song playing
SND_SEQ_BADOP      = SND_SEQ_BASE+$05   ; DEBUG: last bad opcode seen (Seq_BadOpcode marker)
SND_SEQ_TRACE_WR   = SND_SEQ_BASE+$06   ; trace ring write index (0..31)
SND_SEQ_CHANNELS   = SND_SEQ_BASE+$08   ; CHROUTE_COUNT * SeqChannel_len
SND_SEQ_END        = SND_SEQ_CHANNELS + (CHROUTE_COUNT * SeqChannel_len)
SND_SEQ_TRACE      = $1A00          ; 32-byte trace ring of dispatched opcodes
SND_SEQ_TRACE_LEN  = 32

; --- FM voice writer scratch (Task 3) ---
; 4 bytes (part, ch-in-part, log-vol delta, carrier mask) in the free block
; ABOVE the per-channel array (SND_SEQ_END) and BELOW the trace ring ($1A00).
; Single-threaded: only Sequencer_Tick (in the VBlank ISR) reaches the FM writer,
; so static scratch is safe. DERIVED from SND_SEQ_END (was a hardcoded $1880 —
; the Sound 1D SeqChannel growth pushed SND_SEQ_END to $1894 and collided with
; it) so it auto-tracks any future per-channel-struct growth. The build-time
; guards below still assert it clears SND_SEQ_END and the trace ring.
SND_FM_SCRATCH     = SND_SEQ_END
SND_FM_SCRATCH_LEN = 4

    if (SND_FM_SCRATCH < SND_SEQ_END)
      fatal "FM scratch (\{SND_FM_SCRATCH}) overlaps sequencer channels (\{SND_SEQ_END})"
    endif
    if (SND_FM_SCRATCH + SND_FM_SCRATCH_LEN) > SND_SEQ_TRACE
      fatal "FM scratch runs into the trace ring at \{SND_SEQ_TRACE}"
    endif

; --- Snd_LoadSong scratch (Task 6 + Sound 1D) ---
; +0 (1 byte): the DAC bank saved across the song-load bank switch (SndDrv_SetBank
; overwrites SND_CUR_BANK, so the COPY path stashes it here and restores after).
; +1 (2 bytes, Sound 1D): the song BASE pointer the header/streams are read from —
; SND_SONG_BUF (Z80 RAM) on the copy path, or the $8000 window ptr on the stream
; path. The loader's shared header-parse/channel-init reads everything relative to
; this base, so one routine serves both paths. In the free block just past the FM
; scratch, below the trace ring.
Snd_SavedDacBank   = SND_FM_SCRATCH + SND_FM_SCRATCH_LEN
Snd_SongBase       = Snd_SavedDacBank + 1        ; 2 bytes: song base ptr (RAM or window)

    if (Snd_SongBase + 2) > SND_SEQ_TRACE
      fatal "Snd_LoadSong scratch (\{Snd_SongBase}) runs into the trace ring at \{SND_SEQ_TRACE}"
    endif

    if SND_SEQ_END > SND_REQ_BASE
      fatal "sequencer RAM (\{SND_SEQ_END}) overruns the mailbox at \{SND_REQ_BASE}"
    endif
    if (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN) > SND_REQ_BASE
      fatal "sequencer trace ring overruns the mailbox"
    endif
    ; the per-channel array must not run into the trace ring at $1A00.
    ; CHROUTE_COUNT(11) * SeqChannel_len(14) = 154 bytes -> $1808+154 = $18A2, clear.
    if SND_SEQ_END > SND_SEQ_TRACE
      fatal "sequencer channels (\{SND_SEQ_END}) overrun the trace ring at \{SND_SEQ_TRACE}"
    endif

; --- Music-load param block (Task 6 decision 2) + song RAM buffer (decision 1).
; The 68k pre-derives the song's bank + $8000-window ptr (same addressing as a
; DacSample) and posts them here (under the same bus hold as the SND_REQ_MUSIC
; trigger). The Z80 SND_REQ_MUSIC handler reads them, banks the song in, and
; copies a FIXED SND_SONG_BUF_SIZE bytes into SND_SONG_BUF (Z80 RAM) so the
; sequencer streams are RAM-resident (no $8000-window banking during playback —
; the 1B DAC owns the bank). The trace ring is $1A00..$1A1F (32 B), so the param
; block lives just above it at $1A20.
SND_MUSIC_PARAM         = $1A20                  ; music-load param block
SND_MUSIC_PARAM_BANK    = SND_MUSIC_PARAM+$00    ; song bank id (1 byte)
SND_MUSIC_PARAM_PTR     = SND_MUSIC_PARAM+$01    ; song $8000-window ptr (2 bytes, little-endian)
; Sound 1D: the song's SH_FLAGS byte, forwarded by the 68k (it reads the song's
; ROM header directly). The Z80 loader needs the FLAGS *before* deciding the
; copy-to-RAM vs stream-from-ROM path, so it cannot read them from SND_SONG_BUF
; (which only exists for the copy path). Posted in the same bus hold as bank/ptr.
SND_MUSIC_PARAM_FLAGS   = SND_MUSIC_PARAM+$03    ; song SH_FLAGS byte (1 byte)
; Sound 1D: the song's FM-patch-bank $8000-window ptr (2 bytes, little-endian),
; forwarded by the 68k from the song table's parallel patch-ptr entry. USED ONLY
; on the stream path (SH_F_STREAM): the patch bank lives in the song's bank, read
; through the same window. The copy path (1C) ignores it and uses the Z80-RAM
; inline FmPatchInlineTable. (window ptr = (patch_addr & $7FFF) | $8000.)
SND_MUSIC_PARAM_PATCHPTR = SND_MUSIC_PARAM+$04   ; song patch-bank window ptr (2 bytes, LE)
SND_MUSIC_PARAM_LEN     = 6

; The song RAM buffer: the loader copies a fixed SND_SONG_BUF_SIZE bytes from the
; banked window here once at load. Page-aligned ($1B00) so the loader copy + the
; sequencer's hl stream walk stay in one page family (no special alignment need,
; but keeps the map tidy). 512 bytes — generously covers the bring-up song; the
; streams self-terminate ($FF/$EF) so copying a little past the song into adjacent
; ROM is harmless (never interpreted). Song_Test's packed size is build-asserted
; <= SND_SONG_BUF_SIZE in data/sound/song_table.asm.
SND_SONG_BUF            = $1B00
SND_SONG_BUF_SIZE       = $200                   ; 512 bytes ($1B00..$1CFF)

    if (SND_MUSIC_PARAM + SND_MUSIC_PARAM_LEN) > SND_SONG_BUF
      fatal "music param block (\{SND_MUSIC_PARAM}) runs into the song buffer at \{SND_SONG_BUF}"
    endif
    if SND_MUSIC_PARAM < (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN)
      fatal "music param block (\{SND_MUSIC_PARAM}) overlaps the trace ring at \{SND_SEQ_TRACE}"
    endif
    if (SND_SONG_BUF + SND_SONG_BUF_SIZE) > SND_REQ_BASE
      fatal "song buffer (\{SND_SONG_BUF}+\{SND_SONG_BUF_SIZE}) overruns the mailbox at \{SND_REQ_BASE}"
    endif

; --- Trace event_code values (0..15) — the controller decodes the trace ring.
; Each trace byte is (sc_route << 4) | event_code: high nibble = CHROUTE_*,
; low nibble = SEQEV_* below. (Route fits in 4 bits: CHROUTE_COUNT = 10 <= 15.)
SEQEV_NOTEON    = 1     ; note-on (pitch in sc_note)
SEQEV_NOTEOFF   = 2     ; note-off / rest
SEQEV_VOL       = 3     ; set channel volume
SEQEV_PATCH     = 4     ; set FM patch index
SEQEV_DAC       = 5     ; DAC trigger
SEQEV_LOOP      = 6     ; loop-point marker ($EE)
SEQEV_JUMP      = 7     ; jump to loop point ($EF)
SEQEV_END       = 8     ; end of stream ($FF)
SEQEV_RPT_START = 9     ; bounded-repeat body start ($E5)
SEQEV_RPT_END   = 10    ; bounded-repeat body end ($E6) — fires on every pass

; --- SongHeader layout (emitted by tools/song_packer.py, read by the loader) ---
; SongHeader:
;   db  flags            ; Sound 1D: per-song playback mode (SH_F_* below)
;   db  tempo            ; Timer-A reload selector (N = tempo<<2; bigger = faster)
;   db  channel_count
;   ; per channel: route byte + 2-byte stream pointer (Z80-window-relative)
;   rept channel_count: db route ; dw stream_ptr ; endm
;   dw  patch_table_ptr  ; FM patch table for this song
; (No struct — the per-channel array length is variable. The packer back-patches
; each stream_ptr to its stream's offset within the packed song blob.)
;
; --- SongHeader field offsets (Task 6 loader; from SND_SONG_BUF base) ---
; Fixed-position fields (Sound 1D prepends SH_FLAGS at +0):
SH_FLAGS        = 0     ; +0  per-song playback-mode flags (SH_F_* below)
SH_TEMPO        = 1     ; +1  tempo byte (Timer-A selector)
SH_CHCOUNT      = 2     ; +2  channel count
SH_CHANNELS     = 3     ; +3  start of the per-channel array
; Per-channel record (3 bytes): route, stream_ptr (16-bit BIG-ENDIAN offset).
; The packer writes stream_ptr as (off>>8),(off&FF) — high byte FIRST. The loader
; must read it big-endian (NOT a plain Z80 little-endian 16-bit load).
SHC_ROUTE       = 0     ; +0  route byte
SHC_PTR_HI      = 1     ; +1  stream offset high byte (big-endian)
SHC_PTR_LO      = 2     ; +2  stream offset low byte
SHC_LEN         = 3     ; per-channel record length
; patch_table_ptr (2 bytes) follows the per-channel array; IGNORED in 1C (patches
; stay inline — SND_SEQ_PATCHTAB is set to FmPatchInlineTable by the loader).

; --- SongHeader flags byte (SH_FLAGS, Sound 1D §5.1) ----------------------
; bit0 SH_F_FM6_FM   : FM6 is a 6th FM SEQUENCER voice (DAC mode OFF, $2B=$00).
;                      CLEAR -> FM6 is the DAC (1C behavior, DAC mode ON, $2B=$80).
; bit1 SH_F_STREAM   : the song's streams + patch bank are read DIRECTLY through
;                      the banked $8000 window (the loader holds the song's bank
;                      and points sc_stream_ptr at window addresses — NO RAM copy).
;                      CLEAR -> copy a fixed SND_SONG_BUF_SIZE bytes to RAM (1C).
; Contract: Moving Trucks = SH_F_FM6_FM|SH_F_STREAM (FM6=FM voice, stream from ROM);
;           Song_Test / Ode demo = 0 (FM6=DAC, copy-to-RAM — the 1C path, regresses).
SH_F_FM6_FM_B   = 0
SH_F_STREAM_B   = 1
SH_F_FM6_FM     = 1<<SH_F_FM6_FM_B
SH_F_STREAM     = 1<<SH_F_STREAM_B

; --- DacSample id -> descriptor table (Task 6 decision 3) ---
; The $E2 operand (and SND_REQ_SAMPLE) is a 1-based sample id; the handler looks
; up DacSampleTable[id-1] (each DacSample_len = 8 bytes). For 1C, id 1 = the temp
; blip; the table is an INLINE descriptor in the Z80 blob (the blip's bank/ptr/len
; are build-time constants — no banking needed to read it). DAC_SAMPLE_COUNT is
; asserted against the table size in the blob.
DAC_SAMPLE_COUNT = 1
