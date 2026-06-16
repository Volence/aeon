; ======================================================================
; engine/sound_api.asm — 68k-side sound API (Phase 1)
; Posts commands into Z80 RAM. 68k access to Z80 RAM ($A00000+) is only
; reliable while the Z80 bus is held (stopZ80) — reads return garbage
; otherwise. So every transaction stops the Z80, and masks interrupts so
; the DEBUG VBlank state-mirror (which also stopЗ80s) cannot nest the stop.
; See docs/superpowers/specs/2026-06-16-sound-command-api.md.
; ======================================================================

; ----------------------------------------------------------------------
; Sound_Init — block until the Z80 driver has finished its own init.
; The driver clears the mailbox + writes STAT_ALIVE during SndDrv_Init;
; the 68k must not post until that marker appears, or the driver's init
; clear races with (and wipes) the posted command. Each probe holds the
; Z80 bus (the only way the 68k reads Z80 RAM reliably).
; Clobbers: nothing (SR preserved).
; ----------------------------------------------------------------------
Sound_Init:
        move.w  sr, -(sp)
.wait_alive:
        move.w  #$2700, sr                  ; mask interrupts (no mirror nesting)
        stopZ80
        cmp.b   #SND_ALIVE_MARKER, (SND_Z80_BASE+SND_STAT_ALIVE).l
        startZ80
        bne.s   .wait_alive
        move.w  (sp)+, sr
        rts

; ----------------------------------------------------------------------
; Sound_PostCommand — atomically post a command record to the mailbox.
; Waits (bus-held) until the Z80 has consumed any prior command (PENDING==0)
; so back-to-back posts can't clobber an unconsumed record (atomicity rule).
; Then writes the record while the Z80 is stopped, so args + cmd are in place
; before PENDING is set — the Z80 can never latch a half-written record.
; In:  d0.b = cmd id, d1.b = arg0, d2.b = arg1.  Preserves d0-d2 (clobbers d3).
; ----------------------------------------------------------------------
Sound_PostCommand:
        move.w  sr, -(sp)                   ; save caller's SR once
.wait_idle:
        move.w  #$2700, sr                  ; mask interrupts (no mirror nesting)
        stopZ80
        move.b  (SND_Z80_BASE+SND_MBX_PENDING).l, d3   ; sample PENDING (bus held)
        startZ80                            ; balanced release; retry outside stop
        move.w  (sp), sr
        tst.b   d3
        bne.s   .wait_idle                  ; prior command not yet consumed
        ; mailbox idle -> post the record atomically
        move.w  #$2700, sr
        stopZ80
        move.b  d1, (SND_Z80_BASE+SND_MBX_ARG0).l
        move.b  d2, (SND_Z80_BASE+SND_MBX_ARG1).l
        move.b  d0, (SND_Z80_BASE+SND_MBX_CMD).l
        move.b  #1, (SND_Z80_BASE+SND_MBX_PENDING).l    ; commit (Z80 resumes & sees it)
        startZ80
        move.w  (sp)+, sr
        rts

; ----------------------------------------------------------------------
; Sound_Ping — ask the driver to echo d1.b into STAT_PING_ECHO.
; In:  d1.b = echo token value.  Preserves d1.
; ----------------------------------------------------------------------
Sound_Ping:
        move.b  #SND_CMD_PING, d0
        moveq   #0, d2
        bra.w   Sound_PostCommand
