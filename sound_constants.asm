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

; --- YM2612 ports as seen from the Z80 ($4000-$4003) ---
SND_Z80_YM_A0           = $4000                  ; addr part I / status read
SND_REG_DAC_DATA        = $2A                    ; YM reg: DAC sample byte
SND_REG_DAC_ENABLE      = $2B                    ; YM reg: bit7 = DAC mode
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
