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

; ----------------------------------------------------------------------
; Sound_PlayMusic — start a song (Task 6 + Sound 1D). The 68k pre-derives the
; song's bank + $8000-window ptr from SongTable (its own ROM, read directly — no
; bus hold), reads the song's SH_FLAGS byte (the FIRST header byte at the song
; address) and the song's FM-patch-bank window ptr (from the parallel
; SongPatchTable), then posts the SND_MUSIC_PARAM block AND the SND_REQ_MUSIC
; trigger under ONE Z80 bus hold (param FIRST, trigger LAST) so the Z80 can't read
; a half-updated param block. The Z80's SND_REQ_MUSIC handler (in the VBlank ISR,
; DAC paused) banks the song in, then either copies it to Z80 RAM (FM6=DAC, 1C) or
; streams it from ROM with the DAC off (FM6=FM, Sound 1D §5.1), and arms the
; sequencer. The flags MUST be forwarded by the 68k because the Z80 loader needs
; them BEFORE choosing the copy-vs-stream path (it can't read SND_SONG_BUF yet).
; In:  d0.b = song id (1..SONG_COUNT).
; Clobbers: d0/d1/d2/d3/d4/a0/a1; SR restored.
; ----------------------------------------------------------------------
Sound_PlayMusic:
        andi.l  #$FF, d0                    ; d0 = song id (1-based)
        move.l  d0, d2                       ; d2 = song id (preserved for the trigger)
        subq.l  #1, d0                        ; index = id-1
        lsl.l   #2, d0                        ; *4 (dc.l entries)
        ; --- song window ptr + flags from SongTable[id-1] ---
        movea.l #SongTable, a0
        adda.l  d0, a0
        movea.l (a0), a1                      ; a1 = song 68k ROM address (dc.l)
        move.b  (a1), d3                      ; d3.b = SH_FLAGS (header +0 = song address)
        ; bank = (addr & $7F8000) >> 15  ; window_ptr = (addr & $7FFF) | $8000
        ; (same addressing as DacSample — the Z80 reads ROM via the $8000 window).
        move.l  a1, d1
        andi.l  #$7F8000, d1
        lsr.l   #8, d1
        lsr.l   #7, d1                        ; d1 = bank id (>>15)
        move.l  a1, d4
        andi.l  #$7FFF, d4
        ori.l   #$8000, d4                    ; d4 = song window ptr (16 bits, +$8000)
        ; --- patch-bank window ptr from the parallel SongPatchTable[id-1]. USED by
        ; the Z80 ONLY on the stream path (the patch bank shares the song's bank);
        ; the copy path ignores it. window_ptr = (patch_addr & $7FFF) | $8000. ---
        movea.l #SongPatchTable, a0
        adda.l  d0, a0                         ; d0 still = index*4
        movea.l (a0), a1                      ; a1 = patch-bank 68k ROM address
        move.l  a1, d0
        andi.l  #$7FFF, d0
        ori.l   #$8000, d0                    ; d0 = patch-bank window ptr (16 bits)
        ; --- post the param block + trigger under one bus hold (SR-masked so the
        ; DEBUG mirror's stopZ80 can't nest and release the bus mid-write). ---
        move.w  sr, -(sp)
        move.w  #$2700, sr
        stopZ80
        ; param block FIRST. bank, song window_ptr (LE), flags, patch window_ptr (LE).
        move.b  d1, (SND_Z80_BASE+SND_MUSIC_PARAM_BANK).l
        move.b  d4, (SND_Z80_BASE+SND_MUSIC_PARAM_PTR).l    ; song window ptr low byte
        lsr.w   #8, d4
        move.b  d4, (SND_Z80_BASE+SND_MUSIC_PARAM_PTR+1).l  ; song window ptr high byte
        move.b  d3, (SND_Z80_BASE+SND_MUSIC_PARAM_FLAGS).l  ; song SH_FLAGS byte
        move.b  d0, (SND_Z80_BASE+SND_MUSIC_PARAM_PATCHPTR).l   ; patch window ptr low
        lsr.w   #8, d0
        move.b  d0, (SND_Z80_BASE+SND_MUSIC_PARAM_PATCHPTR+1).l ; patch window ptr high
        ; trigger LAST: the song id (1..$FE) tells the Z80 a load is pending.
        move.b  d2, (SND_Z80_BASE+SND_REQ_MUSIC).l
        startZ80
        move.w  (sp)+, sr
        rts

; ----------------------------------------------------------------------
; Sound_StopMusic — stop the song (Task 6). Posts the $FF stop sentinel into
; SND_REQ_MUSIC (single bus-held byte, like Sound_PostByte). The Z80 handler
; key-offs every FM channel, silences PSG, disables Timer A, and clears the
; sequencer-active flag. (The 1B DAC keeps running — DAC is owned by 1B.)
; Clobbers: d0; SR restored.
; ----------------------------------------------------------------------
Sound_StopMusic:
        move.b  #SND_MUSIC_STOP, d0          ; $FF (out of moveq's signed range)
        lea     (SND_Z80_BASE+SND_REQ_MUSIC).l, a0
        bra.w   Sound_PostByte
