; ======================================================================
; BANKED in-frame Z80 routines (Phase-2 music expression).
;
; These routines are emitted in the Moving Trucks / SFX bank (main.asm's
; `cpu z80 / phase 08000h` block) — NOT the resident phase-0 blob — so they cost
; ZERO against the $16F0 resident-code ceiling. They run ONLY inside a sequencer
; frame (ModUpdate / Sequencer_Frame / the opcode dispatch / a note-on), where
; Run_SeqFrame_OnSongBank guarantees the song/table bank is in the $8000 window
; (under `di`, so no ISR re-banks mid-frame); a `call` from resident in-frame code
; therefore executes the window-resident body correctly. This is the same banking
; the engine tables already use — every song already co-locates with this bank, so
; there is no NEW lock-in.
;
; INVARIANTS (must hold for every routine here):
;   1. Never reached from a mailbox / ISR / idle-entry context — the SAMPLE bank is
;      in the window there, so the body would execute garbage.
;   2. Never SetBank while executing (it would unmap its own code from under the PC).
;
; Included under the phase block AFTER the data tables, so its labels resolve to
; $8xxx window addresses (contiguous from bank offset 0).
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
