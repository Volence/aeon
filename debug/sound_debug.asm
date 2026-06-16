; DEBUG-only sound driver state mirror — exposes Z80 mailbox+status to MCP

    ifdef __DEBUG__
      ifdef SOUND_DRIVER_ENABLED
; ----------------------------------------------------------------------
; Sound_DebugMirror — copy Z80 mailbox+status ($A01F00..$A01F3F) into
; Sound_Dbg_Mirror (68k RAM) so the Exodus MCP can observe driver state.
; The MCP's emulator_read_memory routes 68k RAM ($FF0000+) and ROM but
; errors on $A00000, so we snapshot the Z80 region into 68k RAM each frame.
; DEBUG only. Stops the Z80 for the copy, then restarts it.
; Clobbers: d0/a0/a1
; ----------------------------------------------------------------------
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
        startZ80
        rts
      endif
    endif
