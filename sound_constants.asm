; ======================================================================
; sound_constants.asm — shared 68k/Z80 sound equates (single source of truth)
; See docs/superpowers/specs/2026-06-16-sound-command-api.md and -z80-ram-map.md
; ======================================================================

; --- Z80-space base addresses (as seen from the 68k bus) ---
SND_Z80_BASE            = Z80_RAM                ; $A00000 (from constants.asm)

; --- Mailbox record (Z80 offsets; 68k address = SND_Z80_BASE + offset) ---
SND_MBX_BASE            = $1F00
SND_MBX_CMD             = SND_MBX_BASE+$00
SND_MBX_ARG0            = SND_MBX_BASE+$01
SND_MBX_ARG1            = SND_MBX_BASE+$02
SND_MBX_PENDING         = SND_MBX_BASE+$03       ; written last = commit

; --- Status / ack region (Z80 writes, 68k reads) ---
SND_STAT_BASE           = $1F10
SND_STAT_ALIVE          = SND_STAT_BASE+$00      ; driver writes SND_ALIVE_MARKER
SND_STAT_PING_ECHO      = SND_STAT_BASE+$01
SND_STAT_ACK_COUNT      = SND_STAT_BASE+$02
SND_STAT_TICK           = SND_STAT_BASE+$03

SND_ALIVE_MARKER        = $5A

; --- Command IDs ---
SND_CMD_NONE            = 0
SND_CMD_PING            = 1
SND_CMD_PLAY_SAMPLE     = 2

; --- Playback state (Z80 offsets) ---
SND_STATE_BASE          = $1600
SND_TEST_SAMPLE         = $1C00                  ; runtime-generated test sample (Foundations)
SND_TEST_SAMPLE_LEN     = 256
SND_PLAY_ACTIVE         = SND_STATE_BASE+$00     ; 1 = sample playing
SND_PLAY_PTR            = SND_STATE_BASE+$02      ; current sample read pointer
SND_PLAY_LEN            = SND_STATE_BASE+$04      ; bytes remaining
SND_DAC_RATE            = $10                     ; per-sample djnz delay (test tone)
SND_STAT_DAC_ACTIVE     = SND_STAT_BASE+$04       ; $1F14 -> mirror $FFB216 (DAC active flag)

; --- YM2612 ports as seen from the Z80 ($4000-$4003) ---
SND_Z80_YM_A0           = $4000                  ; addr part I / status read
SND_Z80_YM_D0           = $4001                  ; data part I
SND_REG_DAC_DATA        = $2A                    ; YM reg: DAC sample byte
SND_REG_DAC_ENABLE      = $2B                    ; YM reg: bit7 = DAC mode
SND_REG_TIMER_A_HI      = $24
SND_REG_TIMER_A_LO      = $25
SND_REG_TIMER_CTRL      = $27
