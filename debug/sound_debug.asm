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
        lea     (Z80_RAM+SND_MBX_BASE).l, a0     ; $A01F00 source (Z80 RAM)
        lea     (Sound_Dbg_Mirror).w, a1         ; 68k RAM dest
        moveq   #64-1, d0
.copy:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy
        startZ80
        rts
      endif
    endif
