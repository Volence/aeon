; ======================================================================
; (LEGACY) banked in-frame Z80 routine — Phase-2 music expression.
;
; Emitted in the Moving Trucks / SFX bank (main.asm's `cpu z80 / phase 08000h`
; block) so it costs ZERO against the $16F0 resident-code ceiling.
;
; ⚠ KNOWN-UNSAFE — DO NOT ADD ROUTINES HERE. Banking in-frame CODE is a latent
; crash hazard, NOT a "proven 0-cost lever" as the recovery doc claimed.
; Z80 instruction fetches from $8000-$FFFF traverse the 68k bus (cartridge ROM via
; the bank latch). When such a fetch coincides with 68k bus activity — VRAM
; DMA-from-ROM and/or the DEBUG VBlank state-mirror's stopZ80/BUSREQ — the fetched
; OPCODE is corrupted, derailing the instruction stream → wild PC → the Z80 falls
; into its own init (no 68k watchdog). `di` does NOT help (it masks the Z80 INT
; line, not 68k-asserted BUSREQ). Banked DATA reads (pitch/volume tables) tolerate
; this (one-frame glitch), but banked CODE fetches do not. PROVEN 2026-06-28: a
; banked per-frame Porta_Apply crashed the Z80 with 2+ gliding channels (two live
; freezes traced the PC running into bank data from inside the banked execution);
; Tempo_Ramp/Fade_Ramp showed the same and are RESIDENT.
;
; Fm_FnumApplyDelta below is here for HISTORICAL reasons only (fine-detune shipped
; before this was understood). It is reached from the FM note-on path (per-note, so
; the contention-alignment probability is low — it has not crashed in practice), but
; it carries the same latent hazard and MUST be relocated RESIDENT. That move is
; bundled with the deferred portamento work (Porta_Apply is also per-frame and was
; reverted for exactly this reason — see docs/superpowers/plans/porta-b1-WIP.patch
; and the porta-resume plan; both need ~300 B of resident budget recovered first).
;
; INVARIANTS while it stays here: never SetBank while executing; only reached from
; the note-on voice-write path (the FM bank is in the window there).
; ======================================================================

; ----------------------------------------------------------------------
; Fm_FnumApplyDelta — add a SIGNED 16-bit delta to the 11-bit fnum of a packed FM
; word, applying the SAME single-step block-boundary correction as Mod_Advance
; (spec §4) so the result crosses an octave seamlessly (halve fnum + block++ is the
; same chip pitch). Shared by fine-detune (note-on, Group A) and portamento
; (per-frame, Group B) so the block math exists once outside the verified Mod_Advance.
; In:  d = $A4 value ((block<<3)|fnumHi3), e = $A0 value (fnum low), hl = signed delta.
; Out: d = $A4 value, e = $A0 value (normalized). Clobbers af,bc,hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_FnumApplyDelta:
        ld      a, d
        rrca
        rrca
        rrca
        and     007h
        ld      c, a                     ; c = block (0..7)
        ld      a, d
        and     007h                     ; a = fnumHi3
        ld      b, a
        ld      a, e
        ex      de, hl                   ; de = signed delta; (hl free)
        ld      h, b
        ld      l, a                     ; hl = 11-bit fnum
        add     hl, de                   ; hl = fnum + delta
        ; --- hi correction: fnum >= FNUM_HI and block<7 -> fnum>>=1, block++ --------
        ld      a, c
        cp      007h
        jr      z, .lo
        ld      a, h
        cp      FNUM_HI>>8
        jr      c, .lo
        jr      nz, .hi_do
        ld      a, l
        cp      FNUM_HI&0FFh
        jr      c, .lo
.hi_do:
        srl     h
        rr      l                        ; fnum >>= 1
        inc     c                        ; block += 1
        jr      .pack
.lo:
        ; --- lo correction: fnum < FNUM_LO and block>0 -> fnum<<=1, block-- ----------
        ld      a, c
        or      a
        jr      z, .pack
        ld      a, h
        cp      FNUM_LO>>8
        jr      c, .lo_do
        jr      nz, .pack
        ld      a, l
        cp      FNUM_LO&0FFh
        jr      nc, .pack
.lo_do:
        add     hl, hl                   ; fnum <<= 1
        dec     c                        ; block -= 1
.pack:
        ld      a, c
        add     a, a
        add     a, a
        add     a, a                     ; block << 3
        or      h                        ; (block<<3)|fnumHi3 (h is 0..7)
        ld      d, a                     ; d = $A4 value
        ld      e, l                     ; e = $A0 value
        ret
