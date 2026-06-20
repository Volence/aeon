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
SND_REG_LFO             = $22                    ; YM reg: GLOBAL low-freq osc — bit3 = enable, bits0-2 = freq.
                                                 ; Master switch for every channel's AMS(tremolo)/FMS(vibrato)
                                                 ; depth in $B4. Written ONCE at init ($08 = on, ~3.98Hz).

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
; overflow re-arms + calls Sequencer_Frame. Timer A does NOT drive the DAC rate.
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

; --- Phase 3: FIXED per-frame engine rate (Timer-A is now the FRAME clock) -----
; The Phase-3 engine runs one frame per Timer-A overflow at a FIXED ~59.4 Hz,
; region-independent. The 10-bit Timer-A reload N is computed at BUILD time from
; the target rate via a function (never a magic literal): the overflow period is
; 18.773us * (1024 - N), so N = 1024 - period/18.773us, and the period for `hz`
; is (1/hz) seconds = 1e9/hz ns. Hence N = 1024 - (1e9 / (hz * 18773)).
;   SND_FRAME_HZ = 59 -> N = 1024 - (1000000000 / (59*18773))
;                      = 1024 - (1000000000 / 1107607) = 1024 - 902 = 122,
;   period = 18.773us * (1024-122) = 16.93 ms -> 59.06 Hz (within ~0.6% of 59.4).
; This REPLACES the per-song tempo->Timer-A programming (Snd_TimerA_Program);
; musical tempo is now expressed per-channel via the tempo accumulator (Step 6),
; not by the Timer-A reload.
SND_FRAME_HZ            = 59
timerAReload            function hz, 1024 - (1000000000 / ((hz) * 18773))
SND_TIMERA_N           = timerAReload(SND_FRAME_HZ)

        ; N must be a valid 10-bit Timer-A value (0..1023) and well clear of the
        ; extremes; ~122 is expected for 59 Hz.
        if (SND_TIMERA_N < 0) || (SND_TIMERA_N > 1023)
          error "SND_TIMERA_N (\{SND_TIMERA_N}) out of the 10-bit Timer-A range 0..1023"
        endif

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
; --- Phase 3 Task 6: pan + per-operator TL bias --------------------------------
MEV_PAN         = $E4    ; + b4 : set channel pan/AMS/FMS. The operand is the raw
                         ; YM $B4 value (bits7-6 L/R, bits5-4 AMS, bits2-0 FMS).
                         ; The transcoder computes this byte from the Zyrinx
                         ; $30/$32/$34/$36 (off/R/L/C) pan commands -> L/R bits; the
                         ; opcode just CARRIES it. Stored in sc_pan, rendered to
                         ; $B4+chan by ModUpdate (write-on-change). Zero-tick. FM-only
                         ; effect (non-FM routes store it harmlessly; ModUpdate's FM
                         ; gate means nothing is written for them).
MEV_NOTE_RAW    = $E7    ; + a4 a0 dd : key a RAW-frequency FM note (exact $A4/$A0
                         ; bytes) for duration dd, bypassing FmPitchTableZ. Lets a
                         ; VGM-derived song reproduce the original chip pitch
                         ; EXACTLY (incl. sub-C0 bass + microtuning the note table
                         ; can't reach). FM-only (PSG ignores). Sound 1D §5.2.
; --- Phase 3: multi-point pitch envelope (Zyrinx-style note) -----------------
; $E8 + count(1..5) + count note-index bytes : set the channel's pitch-envelope
; points + key-on. Each note-index byte is an ABSOLUTE index 0..$83 into the
; per-song fnum table (Snd_PitchTabPtr; engine default when 0). The handler
; stores the points into sc_points[], sets sc_pt_count=count, sc_pt_cursor=0,
; sets SCF_KEYED + SCF_REKEY (arms ModUpdate to (re)articulate), and advances
; time like a bare note (reloads sc_dur_default). It writes the YM via ModUpdate,
; NOT directly. count==1 = a plain held note (Task 3); count>=2 = a trill/arp
; (cursor-cycled by ModUpdate in Task 4). FM-only.
MEV_PITCHENV    = $E8    ; + count + count idx bytes : pitch-envelope note + key-on
; --- Phase 3 Task 6: per-operator TL bias (Zyrinx OP1-4 $38-$3E -> IX+9/11/13/15)
; + op(0..3) + val : add a per-operator additive TL bias to the patch's $40-group.
; op is the PHYSICAL operator index (0..3 = reg offset +0/+4/+8/+C = S1,S3,S2,S4 —
; the same index space as FmPatch's per-op arrays). val is a SIGNED byte (-128..127):
; NEGATIVE brightens (reduces attenuation), POSITIVE darkens. It is added to the patch
; TL and CLAMPED to 7 bits on BOTH ends (< 0 -> $00 max brightness, > $7F -> $7F silent;
; TL is attenuation). Per
; the RE (/tmp/zyrinx_re_modulation.md §6) the op-mod is a per-note additive TL bias
; LATCHED at key-on / patch load and re-asserted as a CONSTANT (NOT a swept envelope),
; so the bias is applied in Fm_PatchLoad when the $40-group is uploaded and takes
; effect at the NEXT patch load / note — no per-frame cost. Stored in sc_opbias[op].
; Zero-tick. FM-only (the packer routes it only to FM channels).
MEV_OPBIAS      = $E9    ; + op(0..3) + val : per-operator additive TL bias
; --- Phase 3 Task 5: voice-stepping via mid-note minimal register deltas --------
; $EA + count + count*(reg_sel, value) : write `count` per-operator YM2612 registers
; IMMEDIATELY (mid-note), for the CURRENT channel, PART-AWARE. This is the
; voice-stepping primitive: a held note's timbre is swept by writing only the
; registers that CHANGE between voice steps — verified against the Zyrinx lead
; voice-step ($9C->$A0) which differs by EXACTLY ONE byte (operator S1's TL, the
; $40 group op0), so a rapid step = ONE MEV_REGDELTA with count=1. We do NOT do a
; full ~26-register patch reload per step (that is ~6,500 cyc — untenable per frame;
; see tools/cycle_budget_phase3.md). A genuine instrument change at a note onset
; still uses MEV_PATCH (full load); MEV_REGDELTA is the cheap mid-note sweep.
;
; reg_sel ENCODING (one byte) = (group_code << 2) | op:
;   bits 1-0  op        = PHYSICAL operator index 0..3 (reg offset +0/+4/+8/+C =
;                         S1,S3,S2,S4 — the same op index space as FmPatch's per-op
;                         arrays and the carrier mask).
;   bits 5-2  group_code= index 0..5 into RegDeltaGroupBase[] = the per-operator
;                         register-group base: 0=$30(DT/MUL) 1=$40(TL) 2=$50(RS/AR)
;                         3=$60(AM/D1R) 4=$70(D2R) 5=$80(D1L/RR). (Matches the
;                         SND_REG_OP_* bases + the FmPatch group order.)
;   bits 7-6  reserved (0).
; The engine resolves ym_reg = RegDeltaGroupBase[group_code] + op*4 + ch-in-part
; (ch-in-part + part from Fm_RoutePart) and writes `value` via Fm_YmWrite — so the
; SAME opcode targets FM1..FM6 correctly with no per-channel encoding.
;
; APPLIES IMMEDIATELY (a direct YM write when the opcode executes — NOT routed
; through ModUpdate; see the direct-write rationale in the handler comment), ZERO
; command-tick (paced by the surrounding WAITs, like the other zero-tick setters),
; and does NOT touch $28 (key) and does NOT arm SCF_REKEY — it is a pure TIMBRE
; change of the HELD note (the RE-KEY RULE: re-articulation happens ONLY on a pitch
; change via MEV_PITCHENV; voice/timbre changes never re-key). FM-only (the packer
; routes it only to FM channels; a non-FM route consumes the operands but skips the
; YM write via ModUpdate's/ the handler's FM gate).
MEV_REGDELTA    = $EA    ; + count + count*(reg_sel, value) : mid-note minimal reg writes
; --- Phase 3 Task 5: reg_sel field layout + the per-op register-group base table.
; reg_sel = (group_code << REGDELTA_GROUP_SHIFT) | op. The engine masks `op` with
; REGDELTA_OP_MASK and shifts out group_code to index RegDeltaGroupBase[] (defined
; in engine/sound_fm.asm; REGDELTA_GROUP_COUNT entries, the 6 per-op groups).
REGDELTA_OP_MASK     = $03      ; reg_sel bits 1-0 = op (0..3)
REGDELTA_GROUP_SHIFT = 2        ; reg_sel >> this = group_code
REGDELTA_GROUP_MASK  = $0F      ; group_code field width (bits 5-2 after the shift)
REGDELTA_GROUP_COUNT = 6        ; $30,$40,$50,$60,$70,$80
; Bounded-repeat opcodes (Sound 1D Task 1): a body wrapped in REPEAT_START..
; REPEAT_END replays `nn` total times WITHOUT being unrolled in the data. The
; packer encodes them now; the Z80 sequencer interprets them in a later engine
; task (a small repeat-counter stack per channel). They let Moving Trucks ship
; at ~8KB instead of the ~100KB a full unroll would cost.
MEV_REPEAT_START = $E5   ; (no operand) start of a repeatable body
MEV_REPEAT_END   = $E6   ; + nn : replay from matching REPEAT_START nn times (1..255)
MEV_LOOP_POINT  = $EE    ; loop-target marker (no operand)
MEV_JUMP        = $EF    ; jump to loop point
MEV_NOTEFILL    = $ED    ; + master : per-channel note-fill — # frames the note stays keyed
                         ;   from attack before an early key-off (0 = legato/off). Gate
                         ;   articulation / staccato (#4). Set per channel; persists.
MEV_END         = $FF    ; end of stream (channel idle)
; reserved for Phase 3: $EB–$ED, $F0–$FE (unknown opcode = build/validation error)

        ; --- MEV_PAN / MEV_OPBIAS range + collision asserts (Task 6) ---
        ; Both must be command opcodes (> MEV_NOTE_MAX), inside the $E0-$FF
        ; coordination block, and must not collide with any allocated opcode.
        if (MEV_PAN <= MEV_NOTE_MAX) || (MEV_OPBIAS <= MEV_NOTE_MAX)
          error "MEV_PAN/MEV_OPBIAS must be command opcodes (> MEV_NOTE_MAX)"
        endif
        if (MEV_PAN < MEV_VOL) || (MEV_PAN > MEV_END) || (MEV_OPBIAS < MEV_VOL) || (MEV_OPBIAS > MEV_END)
          error "MEV_PAN/MEV_OPBIAS must be inside the $E0-$FF coordination block"
        endif
        if MEV_PAN <> $E4
          error "MEV_PAN (\{MEV_PAN}) must be $E4 (the reserved pan slot)"
        endif
        if MEV_OPBIAS <> $E9
          error "MEV_OPBIAS (\{MEV_OPBIAS}) must be $E9 (the free Phase-3 slot)"
        endif
        ; must not collide with any other allocated $E0-$FF opcode.
        if (MEV_PAN = MEV_VOL) || (MEV_PAN = MEV_PATCH) || (MEV_PAN = MEV_DAC) || (MEV_PAN = MEV_NOTE_DUR) || (MEV_PAN = MEV_REPEAT_START) || (MEV_PAN = MEV_REPEAT_END) || (MEV_PAN = MEV_NOTE_RAW) || (MEV_PAN = MEV_PITCHENV) || (MEV_PAN = MEV_OPBIAS) || (MEV_PAN = MEV_LOOP_POINT) || (MEV_PAN = MEV_JUMP) || (MEV_PAN = MEV_END)
          error "MEV_PAN (\{MEV_PAN}) collides with an allocated $E0-$FF opcode"
        endif
        if (MEV_OPBIAS = MEV_VOL) || (MEV_OPBIAS = MEV_PATCH) || (MEV_OPBIAS = MEV_DAC) || (MEV_OPBIAS = MEV_NOTE_DUR) || (MEV_OPBIAS = MEV_PAN) || (MEV_OPBIAS = MEV_REPEAT_START) || (MEV_OPBIAS = MEV_REPEAT_END) || (MEV_OPBIAS = MEV_NOTE_RAW) || (MEV_OPBIAS = MEV_PITCHENV) || (MEV_OPBIAS = MEV_LOOP_POINT) || (MEV_OPBIAS = MEV_JUMP) || (MEV_OPBIAS = MEV_END)
          error "MEV_OPBIAS (\{MEV_OPBIAS}) collides with an allocated $E0-$FF opcode"
        endif

        ; the bounded-repeat opcodes live in the reserved $E4–$ED command block,
        ; above the note range and clear of MEV_PAN ($E4) / the loop opcodes.
        if (MEV_REPEAT_START <= MEV_NOTE_MAX) || (MEV_REPEAT_END <= MEV_NOTE_MAX)
          error "MEV_REPEAT_* must be command opcodes (> MEV_NOTE_MAX)"
        endif
        if (MEV_REPEAT_START = MEV_REPEAT_END) || (MEV_REPEAT_START = MEV_LOOP_POINT) || (MEV_REPEAT_END = MEV_LOOP_POINT)
          error "MEV_REPEAT_* opcode collision"
        endif

        ; MEV_PITCHENV ($E8) lives in the free Phase-3 opcode space ($E8-$ED /
        ; $F0-$FE). It must be a command opcode (> MEV_NOTE_MAX), inside the $E0-$FF
        ; coordination-flag block, and must NOT collide with any allocated opcode:
        ; $E0-$E7 (VOL/PATCH/DAC/NOTE_DUR/PAN/REPEAT_*/NOTE_RAW), $EE/$EF (LOOP/JUMP),
        ; or $FF (END).
        if MEV_PITCHENV <= MEV_NOTE_MAX
          error "MEV_PITCHENV (\{MEV_PITCHENV}) must be a command opcode (> MEV_NOTE_MAX)"
        endif
        if (MEV_PITCHENV < MEV_VOL) || (MEV_PITCHENV > MEV_END)
          error "MEV_PITCHENV (\{MEV_PITCHENV}) must be inside the $E0-$FF coordination block"
        endif
        if (MEV_PITCHENV = MEV_VOL) || (MEV_PITCHENV = MEV_PATCH) || (MEV_PITCHENV = MEV_DAC) || (MEV_PITCHENV = MEV_NOTE_DUR) || (MEV_PITCHENV = MEV_NOTE_RAW) || (MEV_PITCHENV = MEV_REPEAT_START) || (MEV_PITCHENV = MEV_REPEAT_END) || (MEV_PITCHENV = MEV_LOOP_POINT) || (MEV_PITCHENV = MEV_JUMP) || (MEV_PITCHENV = MEV_END)
          error "MEV_PITCHENV (\{MEV_PITCHENV}) collides with an allocated $E0-$FF opcode"
        endif
        ; $E4 (MEV_PAN, reserved) is the only other $E0-$E7 opcode; PITCHENV must
        ; not land on it either.
        if MEV_PITCHENV = $E4
          error "MEV_PITCHENV (\{MEV_PITCHENV}) collides with the reserved MEV_PAN ($E4)"
        endif

        ; --- MEV_REGDELTA ($EA) range + collision asserts (Task 5) ---
        ; A command opcode (> MEV_NOTE_MAX), inside the $E0-$FF coordination block,
        ; landing on the free Phase-3 slot $EA, clear of every allocated opcode.
        if MEV_REGDELTA <= MEV_NOTE_MAX
          error "MEV_REGDELTA (\{MEV_REGDELTA}) must be a command opcode (> MEV_NOTE_MAX)"
        endif
        if (MEV_REGDELTA < MEV_VOL) || (MEV_REGDELTA > MEV_END)
          error "MEV_REGDELTA (\{MEV_REGDELTA}) must be inside the $E0-$FF coordination block"
        endif
        if MEV_REGDELTA <> $EA
          error "MEV_REGDELTA (\{MEV_REGDELTA}) must be $EA (the free Phase-3 slot)"
        endif
        if (MEV_REGDELTA = MEV_VOL) || (MEV_REGDELTA = MEV_PATCH) || (MEV_REGDELTA = MEV_DAC) || (MEV_REGDELTA = MEV_NOTE_DUR) || (MEV_REGDELTA = MEV_PAN) || (MEV_REGDELTA = MEV_REPEAT_START) || (MEV_REGDELTA = MEV_REPEAT_END) || (MEV_REGDELTA = MEV_NOTE_RAW) || (MEV_REGDELTA = MEV_PITCHENV) || (MEV_REGDELTA = MEV_OPBIAS) || (MEV_REGDELTA = MEV_LOOP_POINT) || (MEV_REGDELTA = MEV_JUMP) || (MEV_REGDELTA = MEV_END)
          error "MEV_REGDELTA (\{MEV_REGDELTA}) collides with an allocated $E0-$FF opcode"
        endif
        ; the reg_sel group_code field must hold all REGDELTA_GROUP_COUNT groups
        ; AND fit beneath the bits the op field uses (no overlap of op vs group).
        if (REGDELTA_GROUP_COUNT-1) > REGDELTA_GROUP_MASK
          error "REGDELTA_GROUP_COUNT (\{REGDELTA_GROUP_COUNT}) overflows the reg_sel group_code field"
        endif
        if (1<<REGDELTA_GROUP_SHIFT) <> (REGDELTA_OP_MASK+1)
          error "REGDELTA_GROUP_SHIFT must clear the op field (op uses bits 0..REGDELTA_OP_MASK)"
        endif

        ; opcode ranges must not overlap: the top note opcode is below the
        ; first command opcode, so the range dispatch is unambiguous.
        if MEV_NOTE_MAX >= MEV_VOL
          error "MEV_NOTE_MAX (\{MEV_NOTE_MAX}) must be < MEV_VOL (\{MEV_VOL})"
        endif

; --- Phase 3: per-song fnum (pitch) table layout -----------------------------
; A note-index byte is an ABSOLUTE index 0..PITCHTAB_MAX_IDX into the per-song
; 132-entry chromatic fnum table (the exact Zyrinx Moving-Trucks table; see
; /tmp/zyrinx_re_timing_pitch.md §2.4). LAYOUT (chosen): TWO PARALLEL PAGES —
; the A4 page (PITCHTAB_COUNT bytes, the YM $A4 = (block<<3)|fnumHi values) FIRST,
; immediately followed by the A0 page (PITCHTAB_COUNT bytes, the YM $A0 = fnum-low
; values). So for index i: $A4 = page[i], $A0 = page[PITCHTAB_COUNT + i]. This
; mirrors Zyrinx's native $0F00 (A4) / $1000 (A0) split and makes the lookup two
; flat indexed byte reads. The engine-default table is MovingTrucks_PitchTable
; (inline in the Z80 blob, Z80-addressable); a per-song table is referenced via
; the SongHeader pitchtable_ptr (0 = engine default).
PITCHTAB_COUNT     = 132                  ; entries per page (idx $00..$83)
PITCHTAB_MAX_IDX   = PITCHTAB_COUNT-1     ; = $83 (the RE's saturating clamp ceiling)

        if PITCHTAB_MAX_IDX <> $83
          error "PITCHTAB_MAX_IDX (\{PITCHTAB_MAX_IDX}) must be $83 (132-entry Zyrinx table)"
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

; ======================================================================
; Phase 5a SFX engine — eligibility, ids, priority, ducking, RAM, structs.
; ======================================================================

; --- SFX channel eligibility (build-time data, spec §4) -----------------------
; Each PHYSICAL voice is either NEVER stealable (lead/bass/DAC) or stealable by an
; SFX. The stealable set sizes the SfxChannel array (3 FM + 3 PSG + noise = 7).
; FM6 is RESERVED in v1 (it is the DAC, or a music FM voice in DAC-off songs);
; opening it to SFX later for DAC-off songs is a one-line table edit (design-for-C).
; The table is indexed by CHROUTE_* and read by SfxDispatch's voice selector +
; the eligibility/kind asserts. SFXEL_NONE = not stealable; SFXEL_FM/SFXEL_PSG =
; stealable, with the kind (FM<->FM, PSG<->PSG dynamic substitution). Noise is its
; own kind (it cannot substitute for a tone PSG and vice versa).
SFXEL_NONE  = 0     ; never stealable (FM1, FM2, FM6, DAC)
SFXEL_FM    = 1     ; stealable FM voice (FM3, FM4, FM5)
SFXEL_PSG   = 2     ; stealable PSG tone voice (PSG1, PSG2, PSG3)
SFXEL_NOISE = 3     ; stealable PSG noise voice (PSGN)

SFX_VOICE_COUNT = 7 ; FM3,FM4,FM5,PSG1,PSG2,PSG3,PSGN — the stealable set

; --- Symbolic SFX ids (spec §9; ids posted to SND_REQ_SFX, disjoint from song ids)
; Values are the S3K source filenames so the transcoder's SfxTable index matches
; (id -> SfxTable[id-1] inside the contiguous SFX-id range; the transcoder densely
; renumbers, but these names are what gameplay refers to). See SfxIdRemap below.
SFXID_RING_RIGHT = $33
SFXID_RING_LEFT  = $34
SFXID_DEATH      = $35
SFXID_SKID       = $36
SFXID_ROLL       = $3C
SFXID_JUMP       = $62
SFXID_SPINDASH   = $AB
SFXID_DASH       = $B6
SFXID_RINGLOSS   = $B9

; --- Per-SFX priority tiers (authored; S3K has none — spec §6). Higher = wins.
; Seeded from S2 zSFXPriority for shared sounds: death/hurt > spindash > skid/roll
; > jump > ring/UI. The transcoder bakes a priority byte into each SfxHeader keyed
; by id; these tiers are the source of that map (mirrored in tools/sfx_transcode.py).
SFXPRI_RING     = $20    ; ring/UI — lowest; never ducks (below SFX_DUCK_THRESHOLD)
SFXPRI_JUMP     = $40
SFXPRI_ROLL     = $60
SFXPRI_SKID     = $60
SFXPRI_SPINDASH = $80
SFXPRI_DASH     = $80
SFXPRI_DEATH    = $C0    ; death/ring-loss — highest
SFXPRI_RINGLOSS = $C0

; --- Ducking (spec §7): a high-priority SFX transiently attenuates the music. A
; global duck-level byte ramps up on duck-eligible SFX and ramps back over N frames
; on SFX end. v1: fixed depth + linear ramp, all tunable.
SFX_DUCK_THRESHOLD = $80     ; SFX priority >= this ducks the music (spindash/dash/death)
SFX_DUCK_DEPTH     = $18     ; carrier-TL bump (attenuation units; bigger = quieter music)
SFX_DUCK_PSG_DEPTH = 3       ; PSG linear-volume drop applied while ducked
SFX_DUCK_RAMP_STEP = 4       ; duck-level change per frame (linear ramp up/down)

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

; --- SFX blob header (emitted by tools/sfx_transcode.py, prefixes the event-list).
; An SFX "is a tiny song": the SfxHeader is followed by a pack_song-style channel
; blob. The header carries the SFX-specific metadata the song format has no field
; for (preferred route, priority, own-voice ptr, flags). Big-endian ptr offsets,
; matching the SongHeader convention. design-for-C: SHF_* reserves continuous/loop
; bits 5b will consume without a format change.
SfxHeader struct
sfh_priority    ds.b 1   ; +0  authored priority byte (SFXPRI_*); higher wins
sfh_flags       ds.b 1   ; +1  SHF_* (continuous / stereo-alt / loop)
sfh_chcount     ds.b 1   ; +2  number of SFX channels (1 or 2 for the core set)
sfh_pad         ds.b 1   ; +3  align the per-channel records to even
; per channel: route(.b) + kind(.b) + cmd_ptr(.w BE off) + voice_ptr(.w BE off)
SfxHeader endstruct      ; = 4 bytes (fixed prefix; per-channel array follows)

SFXH_PRIORITY = SfxHeader_sfh_priority
SFXH_FLAGS    = SfxHeader_sfh_flags
SFXH_CHCOUNT  = SfxHeader_sfh_chcount
SFXH_CHANNELS = SfxHeader_len          ; per-channel array starts after the prefix
; per-channel record (6 bytes): route, kind, cmd_ptr(BE), voice_ptr(BE)
SFXHC_ROUTE   = 0
SFXHC_KIND    = 1
SFXHC_CMD_HI  = 2
SFXHC_CMD_LO  = 3
SFXHC_VOICE_HI = 4
SFXHC_VOICE_LO = 5
SFXHC_LEN     = 6

; --- SfxHeader flags (SHF_*). bits 3-7 reserved for 5b (continuous-loop interp).
SHF_CONTINUOUS_B = 0     ; held-loop SFX (5b interprets; 5a only honors extend-not-retrigger)
SHF_STEREO_ALT_B = 1     ; ring-style L/R alternation (resolved 68k-side; informational here)
SHF_LOOP_B       = 2     ; the blob self-loops (smpsLoop -> MEV_LOOP/JUMP)
SHF_CONTINUOUS   = 1<<SHF_CONTINUOUS_B
SHF_STEREO_ALT   = 1<<SHF_STEREO_ALT_B
SHF_LOOP         = 1<<SHF_LOOP_B

; --- SfxChannel struct (per-active-SFX-voice state; Z80 RAM, indexed by ix). It
; REUSES the SeqChannel field LAYOUT for the fields ModUpdate/Sequencer_Channel
; read (so the shared interpreter walks it with the same (ix+sc_*) addressing),
; then appends the SFX bookkeeping. The shared-prefix fields MUST keep the same
; offsets as SeqChannel — asserted below. The appended fields use sx_* names.
SfxChannel struct
sc_stream_ptr   ds.w 1   ; +0  command stream read ptr (shared with SeqChannel)
sc_mod_ptr      ds.w 1   ; +2  modulation stream (NULL in 5a)
sc_dur_count    ds.b 1   ; +4
sc_dur_default  ds.b 1   ; +5
sc_patch        ds.b 1   ; +6  SFX's own FM patch index (into its own bank)
sc_last_patch   ds.b 1   ; +7  ($FF = force reload)
sc_volume       ds.b 1   ; +8
sc_note         ds.b 1   ; +9
sc_flags        ds.b 1   ; +10 SCF_* (ACTIVE/KEYED/IS_FM/IS_PSG; never SFX_OVERRIDE)
sc_route        ds.b 1   ; +11 the PHYSICAL voice this SFX currently owns (CHROUTE_*)
sc_loop_ptr     ds.w 1   ; +12
sc_repeat_ptr   ds.w 1   ; +14
sc_repeat_count ds.b 1   ; +16
sc_tempo_base   ds.b 1   ; +17
sc_tempo_accum  ds.b 1   ; +18
sc_pt_count     ds.b 1   ; +19
sc_pt_cursor    ds.b 1   ; +20
sc_points       ds.b 5   ; +21
sc_transpose    ds.b 1   ; +26
sc_pan          ds.b 1   ; +27
sc_opbias       ds.b 4   ; +28
sc_porta_accum  ds.w 1   ; +32
sc_porta_incr   ds.w 1   ; +34
sc_last_pan     ds.b 1   ; +36
sc_fill_master  ds.b 1   ; +37
sc_fill_count   ds.b 1   ; +38 (end of the shared SeqChannel-compatible prefix)
; --- SFX-only appended state (offsets >= SeqChannel_len) ---
sx_priority     ds.b 1   ; +39 the running SFX's priority (cleared on end; arbitration)
sx_pad          ds.b 1   ; +40 pad to align sx_patch_base to a word boundary
sx_patch_base   ds.w 1   ; +41 the SFX's own FmPatch-bank window ptr (set at steal)
sx_saved_route  ds.b 1   ; +43 the music route whose SeqChannel we overrode (for restore)
sx_saved_note   ds.b 1   ; +44 PSG3 tone note saved on a noise steal (periodic-noise coupling)
sx_kind         ds.b 1   ; +45 SFXEL_* of the owned voice (FM/PSG/NOISE) for restore dispatch
SfxChannel endstruct     ; = 46 bytes

        if SfxChannel_len <> 46
          error "SfxChannel struct is \{SfxChannel_len} bytes, expected 46"
        endif
        ; largest field offset must stay within the (ix+d) signed-8-bit range.
        if SfxChannel_sx_kind > 127
          error "SfxChannel sx_kind offset (\{SfxChannel_sx_kind}) exceeds (ix+d) +127"
        endif

; sc_* aliases already exist (SeqChannel). Add sx_* aliases for the SFX fields.
sx_priority     = SfxChannel_sx_priority
sx_patch_base   = SfxChannel_sx_patch_base
sx_saved_route  = SfxChannel_sx_saved_route
sx_saved_note   = SfxChannel_sx_saved_note
sx_kind         = SfxChannel_sx_kind

; --- SeqChannel struct (per-channel sequencer state; Z80 RAM, indexed by ix) ---
; Phase 3 (per-frame engine): the v0/1C COMMAND-STREAM fields (sc_stream_ptr ..
; sc_repeat_count) are unchanged in MEANING; the struct now appends:
;   * the C-ready stream seam — sc_mod_ptr (slot[1], the independent modulation
;     stream; NULL for A / single-stream songs). The header descriptor commits a
;     {cmd_ptr, mod_ptr} pair NOW so reaching C (a second stream reader writing
;     the same MODULATION-STATE block) is purely additive — no layout migration.
;   * the per-frame tempo accumulator (sc_tempo_base / sc_tempo_accum) that gates
;     musical timing at the fixed ~59.4 Hz frame rate.
;   * the MODULATION-STATE block (pitch points/cursor, transpose, pan, per-op TL
;     bias, portamento, last-loaded patch) that ModUpdate renders to the YM —
;     STREAM-AGNOSTIC: ModUpdate only reads this state, never parses a stream.
; The real rendering of these fields lands in Tasks 3–7; Task 2 lays out the
; format + the held-note no-op path of ModUpdate. (ix+d) is a signed-8-bit
; displacement; the largest field offset (sc_last_pan, +36 after the Task-6
; growth) is well within +127, so the terse (ix+sc_*) addressing still applies to
; every field.
;
; The tick loop iterates channels with `add ix,de` (de = SeqChannel_len) — the
; struct size is ADDED directly, never MULTIPLIED by an index, so there is no
; power-of-2 benefit to padding; the layout stays packed.
SeqChannel struct
sc_stream_ptr   ds.w 1   ; +0  command stream (slot[0]) read ptr (v0/1C semantics)
sc_mod_ptr      ds.w 1   ; +2  modulation stream (slot[1]) read ptr; 0/NULL for A.
                         ;     C-ready seam — UNUSED in Phase 3a (single stream).
sc_dur_count    ds.b 1   ; +4  ticks remaining on the current note/rest
sc_dur_default  ds.b 1   ; +5  default duration for bare notes
sc_patch        ds.b 1   ; +6  current (commanded) FM patch index
sc_last_patch   ds.b 1   ; +7  last patch ModUpdate actually loaded ($FF = force reload)
sc_volume       ds.b 1   ; +8  current channel volume (linear 0..127)
sc_note         ds.b 1   ; +9  current pitch index (for key-off / debug)
sc_flags        ds.b 1   ; +10 bit0=active, bit1=keyed, bit2=is_fm, bit3=is_psg, bit4=is_dac, bit6=sfx_override
sc_route        ds.b 1   ; +11 channel route enum (CHROUTE_*) — selects the writer
sc_loop_ptr     ds.w 1   ; +12 saved loop-point ptr (set by $EE, used by $EF)
; --- bounded-repeat state (Sound 1D): one level, NO nesting. The transcoder
; emits FLAT, single-level REPEAT_START..REPEAT_END bodies, so a single ptr +
; count per channel is sufficient (nested repeats are UNSUPPORTED by design).
sc_repeat_ptr   ds.w 1   ; +14 body-start ptr saved by $E5, reloaded by $E6 on jump-back
sc_repeat_count ds.b 1   ; +16 reps remaining (0 = no active repeat / fresh-OR-done)
; --- per-frame tempo accumulator (Phase 3): tempo_accum -= 16 each frame; on
; borrow, tempo_accum += tempo_base and the channel consumes an event-tick. ---
sc_tempo_base   ds.b 1   ; +17 tempo "format code" (event-tick rate vs frame rate)
sc_tempo_accum  ds.b 1   ; +18 running accumulator (the per-channel musical clock)
; --- MODULATION-STATE block (Phase 3; rendered by ModUpdate, Tasks 3–7) -------
sc_pt_count     ds.b 1   ; +19 pitch-envelope point count (1 = plain note, >=2 = trill/arp)
sc_pt_cursor    ds.b 1   ; +20 pitch-envelope cursor (advanced per frame, wraps at count)
sc_points       ds.b 5   ; +21 up to 5 pitch point indices (note table indices)
sc_transpose    ds.b 1   ; +26 signed per-pattern transpose (added then clamped)
sc_pan          ds.b 1   ; +27 pan state (off/L/R/C) -> $B4 L/R bits
sc_opbias       ds.b 4   ; +28 per-operator SIGNED TL bias (added to patch TLs at load; neg=brighten)
sc_porta_accum  ds.w 1   ; +32 portamento Q-fixed accumulator
sc_porta_incr   ds.w 1   ; +34 portamento per-frame increment (0 = no glide)
; --- Task 6 write-on-change shadow (ModUpdate tracks the last-WRITTEN pan) ------
; sc_last_pan: the $B4 value ModUpdate last wrote to the chip. ModUpdate writes
; $B4 only when sc_pan != sc_last_pan, then copies sc_pan -> sc_last_pan. The seq
; clear zeroes BOTH sc_pan and sc_last_pan, so a song that never emits MEV_PAN has
; sc_pan == sc_last_pan == 0 -> ModUpdate writes NOTHING and the patch's own $B4
; (written by Fm_PatchLoad) stands (held pan = no write). The first MEV_PAN to any
; nonzero value differs from 0 -> written once, then held.
; Per-op TL bias has NO shadow: it is applied in Fm_PatchLoad (latched at patch
; load / note, matching the Zyrinx key-on latch), so ModUpdate never re-asserts it
; per frame — no write-on-change tracking is needed (zero per-frame cost).
sc_last_pan     ds.b 1   ; +36 last $B4 ModUpdate wrote (0 = none yet / matches default)
sc_fill_master  ds.b 1   ; +37 note-fill reload: # frames the note stays keyed from attack
                         ;     (0 = legato/off). Per-channel gate articulation (#4).
sc_fill_count   ds.b 1   ; +38 live per-frame note-fill countdown (0 = expired or disabled)
SeqChannel endstruct      ; = 39 bytes

        if SeqChannel_len <> 39
          error "SeqChannel struct is \{SeqChannel_len} bytes, expected 39"
        endif
        ; the largest field offset must stay within the signed-8-bit (ix+d) range.
        if SeqChannel_sc_last_pan > 127
          error "sc_last_pan offset (\{SeqChannel_sc_last_pan}) exceeds the (ix+d) +127 range"
        endif
        ; the shared interpreter prefix MUST mirror SeqChannel field offsets so
        ; ModUpdate/Sequencer_Channel walk an SfxChannel correctly.
        if (SfxChannel_sc_flags <> SeqChannel_sc_flags) || (SfxChannel_sc_route <> SeqChannel_sc_route) || (SfxChannel_sc_note <> SeqChannel_sc_note) || (SfxChannel_sc_points <> SeqChannel_sc_points) || (SfxChannel_sc_last_pan <> SeqChannel_sc_last_pan)
          error "SfxChannel shared prefix diverges from SeqChannel field offsets"
        endif

; Short field-offset accessors (AS struct fields are exposed as
; SeqChannel_<field>; these `sc_*` aliases keep the Z80 (ix+d) code terse).
sc_stream_ptr   = SeqChannel_sc_stream_ptr
sc_mod_ptr      = SeqChannel_sc_mod_ptr
sc_dur_count    = SeqChannel_sc_dur_count
sc_dur_default  = SeqChannel_sc_dur_default
sc_patch        = SeqChannel_sc_patch
sc_last_patch   = SeqChannel_sc_last_patch
sc_volume       = SeqChannel_sc_volume
sc_note         = SeqChannel_sc_note
sc_flags        = SeqChannel_sc_flags
sc_route        = SeqChannel_sc_route
sc_loop_ptr     = SeqChannel_sc_loop_ptr
sc_repeat_ptr   = SeqChannel_sc_repeat_ptr
sc_repeat_count = SeqChannel_sc_repeat_count
sc_tempo_base   = SeqChannel_sc_tempo_base
sc_tempo_accum  = SeqChannel_sc_tempo_accum
sc_pt_count     = SeqChannel_sc_pt_count
sc_pt_cursor    = SeqChannel_sc_pt_cursor
sc_points       = SeqChannel_sc_points
sc_transpose    = SeqChannel_sc_transpose
sc_pan          = SeqChannel_sc_pan
sc_opbias       = SeqChannel_sc_opbias
sc_porta_accum  = SeqChannel_sc_porta_accum
sc_porta_incr   = SeqChannel_sc_porta_incr
sc_last_pan     = SeqChannel_sc_last_pan
sc_fill_master  = SeqChannel_sc_fill_master
sc_fill_count   = SeqChannel_sc_fill_count

; --- sc_flags bit numbers + masks ---
; Z80 bit/set/res take a bit INDEX, not a mask, so the sequencer uses the _B
; companions; the SCF_* masks are for 68k-style mask ops (e.g. SCF_ACTIVE|SCF_IS_FM).
; Single source of truth: each mask is derived from its _B bit number below.
SCF_ACTIVE_B    = 0       ; channel is playing its stream
SCF_KEYED_B     = 1       ; a note is currently keyed-on
SCF_IS_FM_B     = 2       ; route class: FM voice
SCF_IS_PSG_B    = 3       ; route class: PSG voice
SCF_IS_DAC_B    = 4       ; route class: DAC trigger channel
; Phase 3: ModUpdate (re)key arming. MEV_PITCHENV sets SCF_REKEY to tell ModUpdate
; to (re)articulate the note on the NEXT frame even if the rendered note index is
; unchanged (a same-pitch re-trigger). ModUpdate clears it after it renders. The
; finalized re-key RULE is Task 5; for Task 3 a count==1 note keys once when armed
; (or when the rendered index changes) and then holds (write-on-change).
SCF_REKEY_B     = 5       ; ModUpdate should (re)key this channel's note next frame

; --- Phase 3 Task 5: the re-key STYLE (calibration lever) ---------------------
; THE RE-KEY RULE: a note re-articulates ONLY on a PITCH change (via MEV_PITCHENV,
; which arms SCF_REKEY). Voice/timbre changes (MEV_PATCH/MEV_OPBIAS/MEV_REGDELTA)
; never re-key. When ModUpdate honors a SCF_REKEY arm on a count==1 single note, it
; can re-articulate two ways:
;   1 (DEFAULT) = CLEAN RE-KEY: key-OFF then key-ON. The YM2612 retriggers the
;       envelope generator on the 0->1 key transition, so the note re-ATTACKS — the
;       audible, oracle-faithful behavior (Zyrinx keys off->on per articulation; the
;       NOTE_RAW path already does this). Without the key-off, a same-pitch re-arm
;       would write $F0|chsel while the key is already 1 (no 0->1 edge -> no
;       re-attack), and a held voice would decay to silence after the first note.
;   0           = KEY-ON ONLY: skip the key-off (re-write $A4/$A0 + key-on; the EG
;       does NOT retrigger if already keyed). Left as a one-line lever so the
;       controller can A/B the re-key density/attack against the oracle.
; (count>=2 trills/arps always re-key per frame — they change pitch each frame — so
; this lever governs only the count==1 re-articulation; the trill path keys-on each
; new point, which IS a fresh 0->1 edge because the pitch genuinely changed.)
SND_REKEY_OFF_THEN_ON = 1
; Phase 5a: SFX channel-steal override. When SET on a music SeqChannel, the music
; interpreter keeps advancing its cursor (so the song never desyncs) but every
; chip-write site early-returns — an SfxChannel owns this physical voice. Cleared
; on SFX restore (which also re-uploads the music patch + re-keys a held note).
; bit7 stays free.
SCF_SFX_OVERRIDE_B = 6

SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B
SCF_REKEY       = 1<<SCF_REKEY_B
SCF_SFX_OVERRIDE = 1<<SCF_SFX_OVERRIDE_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B) || (SCF_REKEY <> 1<<SCF_REKEY_B) || (SCF_SFX_OVERRIDE <> 1<<SCF_SFX_OVERRIDE_B)
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
SND_SEQ_TEMPO      = SND_SEQ_BASE+$00   ; loaded song tempo (LEGACY Timer-A selector; unused Phase 3)
SND_SEQ_CHCOUNT    = SND_SEQ_BASE+$01   ; active channel count (frame-loop djnz bound)
SND_SEQ_PATCHTAB   = SND_SEQ_BASE+$02   ; loaded patch table ptr (2)
SND_SEQ_ACTIVE     = SND_SEQ_BASE+$04   ; 1 = song playing
SND_SEQ_BADOP      = SND_SEQ_BASE+$05   ; DEBUG: last bad opcode seen (Seq_BadOpcode marker)
SND_SEQ_TRACE_WR   = SND_SEQ_BASE+$06   ; trace ring write index (0..31)
SND_SEQ_TEMPO_BASE = SND_SEQ_BASE+$07   ; Phase 3: cached song tempo_base (per-frame accumulator base)
SND_SEQ_CHANNELS   = SND_SEQ_BASE+$08   ; CHROUTE_COUNT * SeqChannel_len
SND_SEQ_END        = SND_SEQ_CHANNELS + (CHROUTE_COUNT * SeqChannel_len)
SND_SEQ_TRACE      = $1A00          ; 32-byte trace ring of dispatched opcodes
SND_SEQ_TRACE_LEN  = 32

; --- FM voice writer scratch (Task 3) ---
; 4 bytes (part, ch-in-part, log-vol delta, carrier mask) in the free block
; ABOVE the per-channel array (SND_SEQ_END) and BELOW the trace ring ($1A00).
; Single-threaded: only Sequencer_Frame (driven by the Timer-A poll in the
; DAC/idle loop) reaches the FM writer, so static scratch is safe. DERIVED from
; SND_SEQ_END (was a hardcoded $1880 —
; the Sound 1D SeqChannel growth pushed SND_SEQ_END to $1894 and collided with
; it) so it auto-tracks any future per-channel-struct growth. The build-time
; guards below still assert it clears SND_SEQ_END and the trace ring.
SND_FM_SCRATCH     = SND_SEQ_END
SND_FM_SCRATCH_LEN = 5                    ; Part,Ch,Log,Mask + Task-6 Op index

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
; Phase 3: the loaded song's per-song PITCH TABLE ptr, cached by Snd_LoadSong from
; the SongHeader's pitchtable_ptr field (0 = engine default). ModUpdate's pitch
; renderer (Task 3) reads it; cached as an absolute Z80 ptr (base + header offset).
Snd_PitchTabPtr    = Snd_SongBase + 2            ; 2 bytes: per-song pitch table ptr

    if (Snd_PitchTabPtr + 2) > SND_SEQ_TRACE
      fatal "Snd_LoadSong scratch (\{Snd_PitchTabPtr}) runs into the trace ring at \{SND_SEQ_TRACE}"
    endif

    ; Phase 3 RAM-budget assert: the seq block (header + all CHROUTE_COUNT slots)
    ; must fit between SND_SEQ_BASE ($1800) and the mailbox base ($1F00). The seq
    ; header is (SND_SEQ_CHANNELS - SND_SEQ_BASE) bytes; the per-channel array is
    ; CHROUTE_COUNT slots * SeqChannel_len. The SeqChannel growth (14 -> 36 bytes)
    ; makes this the binding RAM check, so assert it explicitly against $1F00.
SND_SEQ_HEADER_LEN = SND_SEQ_CHANNELS - SND_SEQ_BASE
    if SND_SEQ_BASE + SND_SEQ_HEADER_LEN + CHROUTE_COUNT*SeqChannel_len > SND_REQ_BASE
      error "seq RAM overflow: \{SND_SEQ_BASE + SND_SEQ_HEADER_LEN + CHROUTE_COUNT*SeqChannel_len} > mailbox \{SND_REQ_BASE}"
    endif
    if SND_SEQ_END > SND_REQ_BASE
      fatal "sequencer RAM (\{SND_SEQ_END}) overruns the mailbox at \{SND_REQ_BASE}"
    endif
    if (SND_SEQ_TRACE + SND_SEQ_TRACE_LEN) > SND_REQ_BASE
      fatal "sequencer trace ring overruns the mailbox"
    endif
    ; the per-channel array must not run into the trace ring at $1A00.
    ; CHROUTE_COUNT(11) * SeqChannel_len(37, Phase 3 Task 6) = 407 bytes -> $1808+407
    ; = $19A7, clear of the trace ring at $1A00.
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

; --- Phase 5a SFX RAM region (the free $1D00..$1EFF gap, below the mailbox) ----
; Mirrors the seq-region asserts: guard the END against the mailbox ($1F00) above
; and against the song-buffer END ($1D00) below so it can't collide with either.
SND_SFX_BASE       = SND_SONG_BUF + SND_SONG_BUF_SIZE   ; = $1D00 (right after the song buffer)
SND_SFX_CHANNELS   = SND_SFX_BASE                       ; the 7-slot SfxChannel array
SND_SFX_CHAN_END   = SND_SFX_CHANNELS + (SFX_VOICE_COUNT * SfxChannel_len)
; SFX request queue (spec §9): a small priority-gated ring. 3 entries * 2 bytes
; (id, priority) + head/tail/count. SfxDispatch enqueues; the per-frame drain pops.
SND_SFX_QUEUE      = SND_SFX_CHAN_END
SFX_QUEUE_DEPTH    = 3
SFX_QUEUE_ENTRY    = 2                                  ; id + priority
SND_SFX_QUEUE_HEAD = SND_SFX_QUEUE + (SFX_QUEUE_DEPTH * SFX_QUEUE_ENTRY)
SND_SFX_QUEUE_TAIL = SND_SFX_QUEUE_HEAD + 1
SND_SFX_QUEUE_CNT  = SND_SFX_QUEUE_TAIL + 1
; Global music duck level (ramped envelope, spec §7) + the active-duck target.
SND_SFX_DUCK_LEVEL = SND_SFX_QUEUE_CNT + 1              ; current applied duck (0 = none)
SND_SFX_DUCK_TARGET = SND_SFX_DUCK_LEVEL + 1           ; target (set while a duck-SFX runs)
SND_SFX_RAM_END    = SND_SFX_DUCK_TARGET + 1

    if SND_SFX_BASE <> $1D00
      error "SND_SFX_BASE (\{SND_SFX_BASE}) must be $1D00 (right after the song buffer)"
    endif
    if SND_SFX_RAM_END > SND_REQ_BASE
      fatal "SFX RAM (\{SND_SFX_RAM_END}) overruns the mailbox at \{SND_REQ_BASE}"
    endif
    if SND_SFX_BASE < (SND_SONG_BUF + SND_SONG_BUF_SIZE)
      fatal "SFX RAM (\{SND_SFX_BASE}) collides with the song buffer below it"
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
; Phase 3 C-ready header. Each channel descriptor now commits a {cmd_ptr, mod_ptr}
; PAIR (the C-ready stream seam): cmd_ptr = the command stream (slot[0], always
; present), mod_ptr = the independent modulation stream (slot[1], 0/NULL for A /
; single-stream songs). The header also gains a per-frame tempo_base and a per-song
; pitchtable_ptr (0 = engine default). Reaching the full dual-stream end state is
; then purely additive (populate mod_ptr + add a reader) — no header migration.
; SongHeader:
;   db  flags            ; Sound 1D: per-song playback mode (SH_F_* below). +0 — the
;                        ; 68k forwards THIS byte (sound_api.asm reads header[+0]);
;                        ; it MUST stay at offset 0.
;   db  tempo            ; LEGACY Timer-A selector (Phase 3: UNUSED — Timer-A is a
;                        ; fixed frame clock; kept for layout stability). +1
;   db  tempo_base       ; Phase 3 per-frame tempo accumulator base. +2
;   db  channel_count    ; +3
;   dw  pitchtable_ptr   ; Phase 3 per-song pitch table BE offset (0 = engine default). +4
;   ; per channel: route + cmd_ptr (BE off) + mod_ptr (BE off, 0 for A)
;   rept channel_count: db route ; dw cmd_ptr ; dw mod_ptr ; endm
;   dw  patch_table_ptr  ; FM patch table for this song (IGNORED in 1C copy path)
; (No struct — the per-channel array length is variable. The packer back-patches
; each cmd_ptr to its stream's offset within the packed song blob; mod_ptr = 0.)
;
; --- SongHeader field offsets (loader; from the song base) ---
; Fixed-position fields (SH_FLAGS stays at +0 — the 68k forwards it):
SH_FLAGS        = 0     ; +0  per-song playback-mode flags (SH_F_* below)
SH_TEMPO        = 1     ; +1  LEGACY Timer-A selector (Phase 3: unused)
SH_TEMPO_BASE   = 2     ; +2  per-frame tempo accumulator base (Phase 3)
SH_CHCOUNT      = 3     ; +3  channel count
SH_PITCHTAB_HI  = 4     ; +4  pitch table offset high byte (big-endian; 0 = default)
SH_PITCHTAB_LO  = 5     ; +5  pitch table offset low byte
SH_CHANNELS     = 6     ; +6  start of the per-channel array
; Per-channel record (5 bytes): route, cmd_ptr (16-bit BE offset), mod_ptr (16-bit
; BE offset; 0 for single-stream A). The packer writes each ptr as (off>>8),(off&FF)
; — high byte FIRST — so the loader reads them big-endian (NOT a plain Z80 LE load).
SHC_ROUTE       = 0     ; +0  route byte
SHC_CMD_HI      = 1     ; +1  command-stream offset high byte (big-endian)
SHC_CMD_LO      = 2     ; +2  command-stream offset low byte
SHC_MOD_HI      = 3     ; +3  modulation-stream offset high byte (0 for A)
SHC_MOD_LO      = 4     ; +4  modulation-stream offset low byte
SHC_LEN         = 5     ; per-channel record length
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
