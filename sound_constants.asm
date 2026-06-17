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
SND_REQ_MUSIC           = SND_REQ_BASE+$02       ; reserved (Phase 1C)
SND_REQ_SFX             = SND_REQ_BASE+$03       ; reserved (Phase 1C)

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
SND_REG_DAC_DATA        = $2A                    ; YM reg: DAC sample byte (parked in the addr port)
SND_REG_DAC_ENABLE      = $2B                    ; YM reg: bit7 = DAC mode (written ONCE at init)
; Timer A regs — RETAINED as names only; the MegaPCM-2 streaming loop no longer
; programs or waits on Timer A (the loop trip-time IS the sample clock, req 9).
SND_REG_TIMER_A_HI      = $24                    ; Timer A value bits 9..2
SND_REG_TIMER_A_LO      = $25                    ; Timer A value bits 1..0
SND_REG_TIMER_CTRL      = $27

; --- Tempo: build-time YM Timer A programming from a target ticks/frame ---
; YM Timer A is a 10-bit value N: reg $24 = N>>2 (bits 9..2), reg $25 = N&3 (bits
; 1..0). Period = 18.773us * (1024 - N) on NTSC (tick base = 144/(master/7)).
; For T overflows/frame (NTSC frame = 16688us):
;   N = 1024 - (16688000ns) / (T * 18773ns)
; A build-time function so the timer value is computed + self-documenting, never
; a hand-tuned magic literal. (1A audit found $C0 was misread as N=192 vs N=768.)
ym_timerA_n  function tpf, (1024 - (16688000 / ((tpf) * 18773)))
SND_TEMPO_TPF           = 6                       ; design tempo timebase (ticks/frame);
                                                  ;   finalize when music sequencing lands
SND_TIMERA_N            = ym_timerA_n(SND_TEMPO_TPF)
SND_TIMERA_HI           = (SND_TIMERA_N >> 2) & $FF
SND_TIMERA_LO           = SND_TIMERA_N & 3

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
SND_LOOP_CYC            = 370                      ; balanced FILL/SKIP/DRAIN total (consumer re-selects $2A each sample)
SND_DAC_RATE_HZ         = dac_rate_hz(SND_LOOP_CYC) ; = 10345 Hz (3579545/346, int div)

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
MEV_LOOP_POINT  = $EE    ; loop-target marker (no operand)
MEV_JUMP        = $EF    ; jump to loop point
MEV_END         = $FF    ; end of stream (channel idle)
; reserved for Phase 3: $E4–$ED, $F0–$FE (unknown opcode = build/validation error)

        ; opcode ranges must not overlap: the top note opcode is below the
        ; first command opcode, so the range dispatch is unambiguous.
        if MEV_NOTE_MAX >= MEV_VOL
          error "MEV_NOTE_MAX (\{MEV_NOTE_MAX}) must be < MEV_VOL (\{MEV_VOL})"
        endif

; --- Channel-route enum ---
CHROUTE_FM1 = 0
CHROUTE_FM2 = 1
CHROUTE_FM3 = 2
CHROUTE_FM4 = 3
CHROUTE_FM5 = 4
; (FM6 is permanently the DAC in 1C — not a sequencer FM channel)
CHROUTE_PSG1 = 5
CHROUTE_PSG2 = 6
CHROUTE_PSG3 = 7
CHROUTE_PSGN = 8    ; PSG noise
CHROUTE_DAC  = 9    ; emits $E2 DAC triggers only
CHROUTE_COUNT = 10

        if CHROUTE_COUNT <> 10
          error "CHROUTE_COUNT (\{CHROUTE_COUNT}) must be 10"
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

; --- SongHeader layout (emitted by tools/song_packer.py, read by the loader) ---
; SongHeader:
;   db  tempo            ; Timer-A period selector (bigger = slower)
;   db  channel_count
;   ; per channel: route byte + 2-byte stream pointer (Z80-window-relative)
;   rept channel_count: db route ; dw stream_ptr ; endm
;   dw  patch_table_ptr  ; FM patch table for this song
; (No struct — the per-channel array length is variable. The packer back-patches
; each stream_ptr to its stream's offset within the packed song blob.)
