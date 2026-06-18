; ======================================================================
; engine/sound_psg.asm — SN76489 PSG voice writer (Sound 1C, Task 4)
;
; Assembled INLINE inside the z80_sound_driver.asm `phase 0` blob (after the
; FM voice writer include, before the inline tables and the even-pad), so its
; labels resolve into Z80 RAM and it reaches PsgDivisorTableZ with direct Z80
; addressing (no $8000-window banking). Turns the sequencer's PSG-route hooks
; into real SN76489 register writes: the three tone channels + the noise
; channel become audible.
;
; --- PSG PORT + COEXISTENCE WITH THE 1B DAC LOOP --------------------------
; The PSG is a single write port at $7F11 (SND_Z80_PSG). Every write is a plain
; `ld (SND_Z80_PSG),a`. Unlike the YM2612:
;   * NO inter-byte delay — latch + data bytes are written back-to-back.
;   * NO busy-poll, NO bus-contention guard — the Z80 owns the PSG; nothing else
;     writes it. PSG writes touch NEITHER $4000-$4003 NOR `de`, so the DAC loop's
;     de=$4001 invariant (and its parked-$2A address latch) are preserved BY
;     CONSTRUCTION. No Fm_ReparkDac is needed here.
;
; --- CHANNEL-INDEX DERIVATION (route -> hardware ch / command bytes) -------
;   route  CHROUTE_  hw ch  tone latch  vol latch   used bytes
;     5      PSG1       0      $80         $90       tone freq + atten
;     6      PSG2       1      $A0         $B0        "
;     7      PSG3       2      $C0         $D0        "
;     8      PSGN     (noise)   —          $F0        noise ctrl ($E0..) + atten
; For the three tone channels the hardware ch index = route - CHROUTE_PSG1
; (0..2); ch<<5 gives the latch/vol base offset. PSGN is the dedicated noise
; channel (its own control + volume bytes), routed to Psg_Noise by the hook.
;
; --- VOLUME MAP (decision 1: linear->attenuation by SHIFT, no LUT) ---------
;   atten = ($7F - vol) >> 3        ; linear 0..127 -> 4-bit attenuation 0..15
; Endpoints: vol 127 -> atten 0 (loudest), vol 0 -> atten $0F (silent). The PSG
; attenuation ladder is ALREADY logarithmic (~2 dB/step), so a LINEAR-domain
; subtract+shift is the correct mapping — we deliberately do NOT route PSG volume
; through the FM 256-byte LogVolumeLutZ (that would double-log and crush the low
; end). Z80 sequence: `ld a,$7F / sub <vol> / srl a / srl a / srl a` (the
; subtract can't underflow for vol<=$7F; vol>$7F clamps to atten 0 since the
; high bits are masked off by the final `and $0F`).
;
; --- NOISE NOTE MAPPING (decision 2: pitch picks the mode/rate) ------------
; Our event format sends `note` opcodes to the noise route (CHROUTE_PSGN). A
; noise "note" is mapped as: control byte = $E0 | (pitch & 7), so the note's low
; 3 bits choose the SN76489 noise mode+rate (D2 = mode 0 periodic / 1 white;
; D1-D0 = rate 00 clk/512, 01 clk/1024, 10 clk/2048, 11 track tone-ch3 freq).
; The control byte stays latched; note-on/off is via the noise VOLUME byte.
; A noise note-on then sets the noise volume from sc_volume; a rest (note-off)
; sets the noise volume to silence ($FF). Useful presets a composer can pick:
;   $E1 periodic mid, $E5 white mid, $E7 white tracking tone-ch3 frequency.
;
; --- ix PRESERVATION (project-critical contract) --------------------------
; Every routine here PRESERVES ix (the SeqChannel pointer the channel loop
; relies on) — none of them touch ix at all. Each routine's `Clobbers:` line is
; accurate (verified: a false clobber comment caused a prior bug).
; ======================================================================

; ----------------------------------------------------------------------
; Psg_HwCh — derive the hardware tone-channel index (0..2) from sc_route.
; In:  ix = SeqChannel (uses sc_route, CHROUTE_PSG1..3).
; Out: a = hw ch (0..2). (PSGN never reaches here — the hook routes it to
;      Psg_Noise before any tone-channel math.)
; Clobbers: af. Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Psg_HwCh:
        ld      a, (ix+sc_route)
        sub     CHROUTE_PSG1             ; route 5/6/7 -> hw ch 0/1/2
        ret

; ----------------------------------------------------------------------
; Psg_ChBase — derive ch<<5 (the latch/vol base offset) for a tone channel.
; In:  ix = SeqChannel.  Out: a = ch<<5 ($00/$20/$40 for hw ch 0/1/2).
; Clobbers: af. Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Psg_ChBase:
        call    Psg_HwCh                 ; a = hw ch (0..2)
        rrca                             ; ch<<5: rotate right 3 == <<5 mod 256
        rrca                             ;   (ch<=2 -> bits land in D6-D5, no wrap
        rrca                             ;    into D7 since ch fits in 2 bits)
        ret

; ----------------------------------------------------------------------
; Psg_VolToAtten — map a linear volume (0..127) to 4-bit PSG attenuation.
; In:  a = linear volume.  Out: a = attenuation (0..15; 0 loudest, $0F silent).
; atten = (($7F - vol) >> 3) & $0F   (decision 1; see file header).
; Clobbers: af, b. Preserves c, de, hl, ix.
; ----------------------------------------------------------------------
Psg_VolToAtten:
        ld      b, a                     ; b = vol
        ld      a, SND_FM_TL_MAX         ; $7F
        sub     b                        ; a = $7F - vol (no underflow for vol<=$7F)
        srl     a
        srl     a
        srl     a                        ; a = ($7F - vol) >> 3
        and     SND_PSG_ATTEN_SILENT     ; clamp to 4 bits ($0F); guards vol>$7F
        ret

; ----------------------------------------------------------------------
; Psg_NoteOn — key a tone note on a PSG tone channel.
; In:  ix = SeqChannel (PSG1..3), a = pitch index (0..94).
; PsgDivisorTableZ[pitch] = 10-bit divisor (little-endian word). Emit:
;   latch = $80 | (ch<<5) | (div & $0F)   then   data = (div >> 4) & $3F.
; Then set the channel volume from sc_volume so the note is audible.
; Sets SCF_KEYED.
; Clobbers: af, bc, de, hl. Preserves ix.
; ----------------------------------------------------------------------
Psg_NoteOn:
        ; hl = &PsgDivisorTableZ[pitch] = base + pitch*2
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; pitch*2 (word entries)
        ld      de, PsgDivisorTableZ
        add     hl, de
        ld      e, (hl)                  ; e = divisor low byte
        inc     hl
        ld      d, (hl)                  ; d = divisor high byte (only D1-D0 used)
        ; de = 10-bit divisor; build the latch + data bytes.
        push    de                       ; save divisor across Psg_ChBase

        call    Psg_ChBase               ; a = ch<<5 ($00/$20/$40)
        or      SND_PSG_TONE_LATCH       ; a = $80 | (ch<<5)
        ld      c, a                     ; c = latch base (no freq nibble yet)
        pop     de                       ; e = div lo, d = div hi
        ld      a, e
        and     0Fh                      ; a = div & $0F (freq low 4 bits)
        or      c                        ; a = $80 | (ch<<5) | (div & $0F)
        ld      (SND_Z80_PSG), a         ; latch byte

        ; data byte = (div >> 4) & $3F : take div bits 9..4 (e>>4 | d<<4).
        ld      a, d
        add     a, a
        add     a, a
        add     a, a
        add     a, a                     ; a = d << 4 (div bits 9..8 land in D5..D4)
        ld      b, a                     ; b = (d & 3) << 4 -> div bits 5..4 region
        ld      a, e
        srl     a
        srl     a
        srl     a
        srl     a                        ; a = e >> 4 = div bits 7..4
        or      b                        ; a = ((d<<4)|(e>>4)) = (div >> 4)
        and     3Fh                      ; data byte is 6 bits
        ld      (SND_Z80_PSG), a         ; data byte (freq high)

        ; --- set the channel volume so the note sounds (re-reads sc_volume) ---
        set     SCF_KEYED_B, (ix+sc_flags)
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; (preserves ix; ret from there)

; ----------------------------------------------------------------------
; Psg_NoteOff — silence a PSG channel (tone OR noise) via its attenuation.
; In:  ix = SeqChannel.  Clears SCF_KEYED.
; Tone:  vol byte = $90 | (ch<<5) | $0F.   Noise: $F0 | $0F = $FF.
; Clobbers: af. Preserves bc, de, hl, ix. (Tone path calls Psg_ChBase, which
; clobbers af only; the noise path is a single ld a,$FF/store — no tail-call,
; so unlike Psg_Noise this routine does NOT fold in Psg_SetVolume's bc clobber.)
; ----------------------------------------------------------------------
Psg_NoteOff:
        res     SCF_KEYED_B, (ix+sc_flags)
        ld      a, (ix+sc_route)
        cp      CHROUTE_PSGN
        jr      z, .noise
        call    Psg_ChBase               ; a = ch<<5
        or      SND_PSG_VOL_LATCH        ; $90 | (ch<<5)
        or      SND_PSG_ATTEN_SILENT     ; | $0F  -> silent
        ld      (SND_Z80_PSG), a
        ret
.noise:
        ld      a, SND_PSG_SILENCE_N     ; $FF = noise vol, max attenuation
        ld      (SND_Z80_PSG), a
        ret

; ----------------------------------------------------------------------
; Psg_SetVolume — set the channel attenuation from a linear volume.
; In:  ix = SeqChannel (PSG1..3 OR PSGN), a = linear vol (0..127).
; Tone:  emit $90 | (ch<<5) | atten.   Noise: emit $F0 | atten.
; Clobbers: af, bc. Preserves de, hl, ix.
; ----------------------------------------------------------------------
Psg_SetVolume:
        call    Psg_VolToAtten           ; a = 4-bit attenuation (clobbers b)
        ld      c, a                     ; c = attenuation
        ld      a, (ix+sc_route)
        cp      CHROUTE_PSGN
        jr      z, .noise
        call    Psg_ChBase               ; a = ch<<5
        or      SND_PSG_VOL_LATCH        ; $90 | (ch<<5)
        or      c                        ; | atten
        ld      (SND_Z80_PSG), a
        ret
.noise:
        ld      a, SND_PSG_NOISE_VOL     ; $F0
        or      c                        ; | atten
        ld      (SND_Z80_PSG), a
        ret

; ----------------------------------------------------------------------
; Psg_Noise — handle a `note` on the noise route (CHROUTE_PSGN).
; In:  ix = SeqChannel, a = pitch index. Sets the noise control byte from the
; pitch's low 3 bits ($E0 | (pitch & 7)) — see decision 2 in the file header —
; then sets the noise volume from sc_volume so the hit sounds. Sets SCF_KEYED.
; Clobbers: af, bc. Preserves de, hl, ix.
; ----------------------------------------------------------------------
Psg_Noise:
        and     7                        ; pitch low 3 bits = mode<<2 | rate
        or      SND_PSG_NOISE_CTRL       ; $E0 | (pitch & 7)
        ld      (SND_Z80_PSG), a         ; noise control byte (stays latched)
        set     SCF_KEYED_B, (ix+sc_flags)
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; noise volume path (preserves ix; ret)

; ----------------------------------------------------------------------
; Psg_SilenceAll — emit the four PSG silence latches ($9F/$BF/$DF/$FF) so all
; three tone channels + the noise channel go to max attenuation. Used by
; Sequencer_StopAll (StopMusic, Task 6).
; Clobbers: af. Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Psg_SilenceAll:
        ld      a, SND_PSG_SILENCE_T1    ; $9F
        ld      (SND_Z80_PSG), a
        ld      a, SND_PSG_SILENCE_T2    ; $BF
        ld      (SND_Z80_PSG), a
        ld      a, SND_PSG_SILENCE_T3    ; $DF
        ld      (SND_Z80_PSG), a
        ld      a, SND_PSG_SILENCE_N     ; $FF
        ld      (SND_Z80_PSG), a
        ret
