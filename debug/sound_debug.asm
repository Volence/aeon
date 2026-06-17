; DEBUG-only sound driver state mirror — exposes Z80 mailbox+status to MCP

    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
        ifdef SOUND_DBG_MIRROR
; ----------------------------------------------------------------------
; Sound_DebugMirror — copy Z80 mailbox+status ($A01F00..$A01F3F) into
; Sound_Dbg_Mirror (68k RAM) so the Exodus MCP can observe driver state.
; The MCP's emulator_read_memory routes 68k RAM ($FF0000+) and ROM but
; errors on $A00000, so we snapshot the Z80 region into 68k RAM each frame.
; DEBUG only. Stops the Z80 for the copy, then restarts it.
; Clobbers: d0/a0/a1
; ----------------------------------------------------------------------
SEQ_MIRROR_HDRCH = 8 + (2*SeqChannel_len)        ; header + 2 test channels = 30 bytes
Sound_DebugMirror:
        stopZ80
        lea     (Sound_Dbg_Mirror).w, a1         ; 68k RAM dest
        lea     (Z80_RAM+SND_REQ_BASE).l, a0     ; [0..47] = $1F00..$1F2F (req slots + status)
        moveq   #48-1, d0
.copy1:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy1
        lea     (Z80_RAM+SND_STATE_BASE).l, a0   ; [48..63] = $1600..$160F (playback state)
        moveq   #16-1, d0
.copy2:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy2
        ; --- [64..] sequencer window (Sound 1C Task 2) ---
        ; a1 now points at Sound_Dbg_Mirror+64. Copy the sequencer header + the
        ; per-channel state block (header $1800 .. SND_SEQ_END), then the 32-byte
        ; trace ring at $1A00. Mirror layout (offsets from Sound_Dbg_Mirror):
        ;   [64] SND_SEQ_TEMPO      [65] SND_SEQ_CHCOUNT
        ;   [66..67] SND_SEQ_PATCHTAB
        ;   [68] SND_SEQ_ACTIVE     [69] SND_SEQ_BADOP
        ;   [70] SND_SEQ_TRACE_WR   [71] (unused header byte)
        ;   [72..] SND_SEQ_CHANNELS: per channel (11 B) =
        ;          +0/+1 sc_stream_ptr, +2 sc_dur_count, +3 sc_dur_default,
        ;          +4 sc_patch, +5 sc_volume, +6 sc_note, +7 sc_flags,
        ;          +8 sc_route, +9/+10 sc_loop_ptr.
        ;          ch0 (FM1) at [72..82], ch1 (PSG1) at [83..93].
        ;   [94..125] SND_SEQ_TRACE ring (32 bytes); each = (route<<4)|event_code.
        ; We copy the 8-byte header + the FIRST 2 channel slots (the dry-run test
        ; channels) = 30 bytes, keeping the whole window inside the 64-byte upper
        ; half of the 128-byte mirror.
        lea     (Z80_RAM+SND_SEQ_BASE).l, a0     ; [64..] = $1800.. (header + 2 channels)
        moveq   #SEQ_MIRROR_HDRCH-1, d0
.copy3:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy3
        lea     (Z80_RAM+SND_SEQ_TRACE).l, a0    ; trace ring ($1A00, 32 B)
        moveq   #SND_SEQ_TRACE_LEN-1, d0
.copy4:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy4
        startZ80
        rts
        endif
      endif
    endif
