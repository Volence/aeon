; ======================================================================
; engine/sound_api.asm — 68k-side sound API (Phase 1)
; Posts commands into per-type Z80 RAM request slots. 68k access to Z80 RAM
; ($A00000+) is only valid while the Z80 bus is held — reads return garbage AND
; writes are silently ignored otherwise (confirmed real hardware, gen-hw.txt /
; plutiedev). So every transaction holds the bus, with interrupts masked so the
; DEBUG VBlank state-mirror (which also stopZ80s, non-nestable) can't release the
; bus mid-write. A single-byte slot is atomic under the bus hold, so there is no
; pending flag and no wait-idle spin (latest-wins, Flamedriver model).
; See docs/superpowers/specs/2026-06-16-sound-command-api.md.
; ======================================================================

; ----------------------------------------------------------------------
; Sound_PostByte — write d0.b into the Z80 RAM request slot at (a0).
; In:  d0.b = value (nonzero = request, 0 = idle), a0 = 68k addr of the slot.
; Clobbers: SR restored; nothing else.
; ----------------------------------------------------------------------
Sound_PostByte:
        move.w  sr, -(sp)
        move.w  #$2700, sr                  ; mask interrupts (no mirror nesting)
        stopZ80
        move.b  d0, (a0)
        startZ80
        move.w  (sp)+, sr
        rts

; ----------------------------------------------------------------------
; Sound_Init — block until the Z80 driver has finished its own init.
; The driver clears its slots + writes STAT_ALIVE during SndDrv_Init; the 68k
; must not post until that marker appears. Each probe holds the Z80 bus (the
; only way the 68k reads Z80 RAM reliably).
; Clobbers: nothing (SR preserved).
; ----------------------------------------------------------------------
Sound_Init:
        move.w  sr, -(sp)
.wait_alive:
        move.w  #$2700, sr
        stopZ80
        cmp.b   #SND_ALIVE_MARKER, (SND_Z80_BASE+SND_STAT_ALIVE).l
        startZ80
        bne.s   .wait_alive
        move.w  (sp)+, sr
        rts

; ----------------------------------------------------------------------
; Sound_Ping — debug: ask the driver to echo d0.b into STAT_PING_ECHO.
; In:  d0.b = nonzero echo token value.
; ----------------------------------------------------------------------
Sound_Ping:
        lea     (SND_Z80_BASE+SND_REQ_PING).l, a0
        bra.w   Sound_PostByte

; ----------------------------------------------------------------------
; Sound_PlaySample — start DAC playback of a sample id.
; In:  d0.b = sample id (nonzero).
; ----------------------------------------------------------------------
Sound_PlaySample:
        lea     (SND_Z80_BASE+SND_REQ_SAMPLE).l, a0
        bra.w   Sound_PostByte
