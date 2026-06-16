; ======================================================================
; engine/sound_api.asm — 68k-side sound API (Phase 1)
; Posts commands into Z80 RAM with read-back-verified writes.
; See docs/superpowers/specs/2026-06-16-sound-command-api.md.
; ======================================================================

; ----------------------------------------------------------------------
; Sound_VerifiedWrite — write d0.b to (a0), retry until read-back matches.
; In:  d0.b = value, a0 = 68k address of a Z80 RAM byte.
; Out: byte at (a0) == d0.b (verified). Preserves d0/a0.
; ----------------------------------------------------------------------
Sound_VerifiedWrite:
        move.b  d0, (a0)
        cmp.b   (a0), d0
        bne.s   Sound_VerifiedWrite
        rts

; ----------------------------------------------------------------------
; Sound_Init — clear the mailbox command + pending bytes (mailbox idle).
; Clobbers: d0, a0.
; ----------------------------------------------------------------------
Sound_Init:
        lea     (SND_Z80_BASE+SND_MBX_CMD).l, a0
        moveq   #0, d0
        bsr.s   Sound_VerifiedWrite
        lea     (SND_Z80_BASE+SND_MBX_PENDING).l, a0
        moveq   #0, d0
        bra.s   Sound_VerifiedWrite      ; tail call (writes + rts)

; ----------------------------------------------------------------------
; Sound_PostCommand — wait until idle, write args, then commit pending.
; Write order: ARG0, ARG1, CMD, then PENDING LAST (commit invariant).
; In:  d0.b = cmd id, d1.b = arg0, d2.b = arg1.
; Out: command posted. Preserves d0-d2.
; ----------------------------------------------------------------------
Sound_PostCommand:
.wait_idle:
        tst.b   (SND_Z80_BASE+SND_MBX_PENDING).l
        bne.s   .wait_idle
        movem.l d0-d2/a0, -(sp)
        ; arg0
        move.b  d1, d0
        lea     (SND_Z80_BASE+SND_MBX_ARG0).l, a0
        bsr.s   Sound_VerifiedWrite
        ; arg1
        move.b  d2, d0
        lea     (SND_Z80_BASE+SND_MBX_ARG1).l, a0
        bsr.s   Sound_VerifiedWrite
        movem.l (sp)+, d0-d2/a0          ; d0 = cmd id again
        movem.l d0-d2/a0, -(sp)
        ; cmd id
        lea     (SND_Z80_BASE+SND_MBX_CMD).l, a0
        bsr.s   Sound_VerifiedWrite
        ; pending commit — LAST
        moveq   #1, d0
        lea     (SND_Z80_BASE+SND_MBX_PENDING).l, a0
        bsr.s   Sound_VerifiedWrite
        movem.l (sp)+, d0-d2/a0
        rts

; ----------------------------------------------------------------------
; Sound_Ping — ask the driver to echo d1.b into STAT_PING_ECHO.
; In:  d1.b = echo token value.
; Out: ping posted. Preserves d1.
; ----------------------------------------------------------------------
Sound_Ping:
        move.b  #SND_CMD_PING, d0
        moveq   #0, d2
        bra.w   Sound_PostCommand
