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
; Phase 3: SeqChannel grew 14 -> 36 bytes (the modulation-state block), so we can
; no longer mirror FULL channel slots within the 176-byte Sound_Dbg_Mirror. The
; mirror is a DEBUG observability window, not a faithful struct copy, so we mirror
; a PREFIX of each channel (SEQ_MIRROR_CHBYTES bytes) that captures the controller-
; observed liveness fields — through sc_tempo_accum (+18), which proves the
; per-frame tempo accumulator is advancing. The shipping test song (song_test.py)
; has 3 channels (FM1, FM2, PSG1), so 3 slots is the window.
;
; Per-channel mirror prefix (offsets within the 20-byte slot, from SeqChannel +0):
;   +0/+1 sc_stream_ptr, +2/+3 sc_mod_ptr, +4 sc_dur_count, +5 sc_dur_default,
;   +6 sc_patch, +7 sc_last_patch, +8 sc_volume, +9 sc_note, +10 sc_flags,
;   +11 sc_route, +12/+13 sc_loop_ptr, +14/+15 sc_repeat_ptr, +16 sc_repeat_count,
;   +17 sc_tempo_base, +18 sc_tempo_accum, +19 sc_pt_count.
; Mirror layout (offsets from Sound_Dbg_Mirror): header [64..71], ch0 [72..91],
; ch1 [92..111], ch2 [112..131]; trace ring [132..163]. Upper window = 64 + 8 +
; 3*20 + 32 = 164 <= 176.
SEQ_MIRROR_CHANNELS = 3
SEQ_MIRROR_CHBYTES  = 20                          ; per-channel prefix copied (<= SeqChannel_len)
SEQ_MIRROR_HDRCH = 8 + (SEQ_MIRROR_CHANNELS*SEQ_MIRROR_CHBYTES)   ; header + 3*20 = 68 bytes
        if SEQ_MIRROR_CHBYTES > SeqChannel_len
          fatal "SEQ_MIRROR_CHBYTES (\{SEQ_MIRROR_CHBYTES}) exceeds SeqChannel_len (\{SeqChannel_len})"
        endif
Sound_DebugMirror:
        stopZ80
        lea     (Sound_Dbg_Mirror).w, a1         ; 68k RAM dest
        lea     (Z80_RAM+SND_REQ_BASE).l, a0     ; [0..47] = $1F00..$1F2F (req slots + status)
        ; This 48-byte copy already covers SND_STAT_TICK ($1F13 -> mirror byte 19),
        ; the Task-5 scheduler tick counter the controller reads to verify the
        ; Timer-A overflow rate (tempo $C0 -> ~208/sec). No extra mirror entry needed.
        moveq   #48-1, d0
.copy1:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy1
        lea     (Z80_RAM+SND_STATE_BASE).l, a0   ; [48..63] = $1600..$160F (playback state)
        moveq   #16-1, d0
.copy2:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy2
        ; --- [64..] sequencer window (Phase 3) ---
        ; a1 now points at Sound_Dbg_Mirror+64. Copy the 8-byte sequencer header,
        ; then a SEQ_MIRROR_CHBYTES-byte PREFIX of each of SEQ_MIRROR_CHANNELS
        ; channels (the full 36-byte SeqChannel no longer fits), then the 32-byte
        ; trace ring at $1A00. Mirror layout (offsets from Sound_Dbg_Mirror):
        ;   [64] SND_SEQ_TEMPO      [65] SND_SEQ_CHCOUNT
        ;   [66..67] SND_SEQ_PATCHTAB
        ;   [68] SND_SEQ_ACTIVE     [69] SND_SEQ_BADOP
        ;   [70] SND_SEQ_TRACE_WR   [71] SND_SEQ_TEMPO_BASE
        ;   [72..] channel prefixes (SEQ_MIRROR_CHBYTES each) — see the field map above.
        ;   [...] SND_SEQ_TRACE ring (32 bytes); each = (route<<4)|event_code.
        ; Fit guard: 64 + (header + N*prefix) + trace <= 176.
        if (64 + SEQ_MIRROR_HDRCH + SND_SEQ_TRACE_LEN) > 176
          fatal "sound debug mirror window (\{64 + SEQ_MIRROR_HDRCH + SND_SEQ_TRACE_LEN}) exceeds Sound_Dbg_Mirror (176 bytes)"
        endif
        ; 8-byte sequencer header.
        lea     (Z80_RAM+SND_SEQ_BASE).l, a0     ; $1800.. (header)
        moveq   #8-1, d0
.copy3h:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy3h
        ; per-channel prefixes: copy SEQ_MIRROR_CHBYTES, then skip the rest of the
        ; Z80 SeqChannel slot. a0 already at SND_SEQ_CHANNELS ($1808) after the
        ; header copy (the header is exactly the 8 bytes $1800..$1807).
        moveq   #SEQ_MIRROR_CHANNELS-1, d1
.copy3c:
        moveq   #SEQ_MIRROR_CHBYTES-1, d0
.copy3cb:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy3cb
        lea     (SeqChannel_len-SEQ_MIRROR_CHBYTES)(a0), a0   ; skip the unmirrored tail
        dbf     d1, .copy3c
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
