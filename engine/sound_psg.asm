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
;     writes it. PSG writes touch NO YM port ($4000-$4003), so they never disturb
;     the parked-$2A address latch and need no Fm_ReparkDac. They DO clobber `de`,
;     however (Psg_NoteOn/Psg_EmitDivisor load the divisor-table base into de): the
;     DAC loop's de=$4001 invariant is re-established by the Timer-A tick CALLER
;     (SndDrv_IdleTick reloads de; Snd_TimerA_Rearm re-parks $2A), NOT by PSG code
;     preserving de.
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
; Psg_EnvCursorReset — restart the PSG vol-env contour (sc_psgenv_cur=0) on a
; fresh attack, but ONLY for an SFX channel. The sc_psgenv* fields are SfxChannel-
; only (Task 2 deviation): sc_psgenv_cur is at offset +40, which is PAST a music
; SeqChannel (39 bytes) but INSIDE SfxChannel (60 bytes). Writing it on a music PSG
; channel would corrupt the adjacent channel's RAM — so gate on ix >= SND_SFX_BASE
; ($1D00, the same high-byte test Psg_SetVolume's duck fold uses). Music PSG
; channels are below $1D00 -> no-op (byte-identical).
; In: ix = SeqChannel/SfxChannel. Clobbers af. Preserves bc, de, hl, ix.
; ----------------------------------------------------------------------
Psg_EnvCursorReset:
        push    hl                       ; preserve hl (contract; Snd_ChanClass clobbers hl)
        call    Snd_ChanClass            ; CARRY set => ix < $1D00 => music channel
        pop     hl                       ; restore caller's hl
        ret     c                        ; music PSG -> no env fields, leave it alone
        ld      (ix+sc_psgenv_cur), 0    ; SFX: restart the contour from frame 0
        ret

; ----------------------------------------------------------------------
; PsgVolEnv_Resolve — map a 1-based PSG vol-env id (a) to its body ptr (hl) via the
; tiny PsgVolEnv_Ids/PsgVolEnv_Ptrs parallel-array map (engine/sound_tables_z80.asm).
; Out: carry clear + hl = body base on a match; carry set on an unknown id.
; In: a = 1-based env id. Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
PsgVolEnv_Resolve:
        ld      b, PSGVOLENV_COUNT
        ld      hl, PsgVolEnv_Ids
        ld      de, PsgVolEnv_Ptrs
.scan:
        cp      (hl)
        jr      z, .found
        inc     hl                       ; next id byte
        inc     de
        inc     de                       ; next ptr (2 bytes)
        djnz    .scan
        scf                              ; not found
        ret
.found:
        ex      de, hl                   ; hl = &ptr entry
        ld      e, (hl)
        inc     hl
        ld      d, (hl)
        ex      de, hl                   ; hl = body base
        or      a                        ; carry clear
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
        ; --- latch the base divisor for PSG pitch modulation (spec §5) ---
        ; sc_base_freq holds (hi,lo) = (d,e); Psg_ApplyMod sums the vibrato/sweep
        ; offset onto it each frame. SfxChannel-ONLY (sc_base_freq at +51 is PAST a
        ; 39-byte music SeqChannel) -> gate on ix >= SND_SFX_BASE so a music PSG note
        ; never writes adjacent RAM (and stays byte-identical). hl holds the table ptr
        ; (must survive), so test ix's high byte without disturbing hl.
        push    hl                       ; preserve the divisor table ptr (Snd_ChanClass clobbers hl)
        call    Snd_ChanClass            ; CARRY set => ix < $1D00 => music channel
        pop     hl                       ; restore the table ptr
        jr      c, .skip_base_latch      ; music PSG -> no mod fields, don't latch
        ld      (ix+sc_base_freq), d
        ld      (ix+sc_base_freq+1), e
.skip_base_latch:
        ; de = 10-bit divisor; latch it (shared with Psg_ApplyMod's re-latch).
        call    Psg_EmitDivisor          ; write latch + data bytes (Clobbers af,bc,de)

        ; --- set the channel volume so the note sounds (re-reads sc_volume) ---
        set     SCF_KEYED_B, (ix+sc_flags)
        call    Psg_EnvCursorReset       ; SFX: restart the vol-env contour on this attack (spec §4)
        ; --- per-note pitch-mod re-arm (spec §5) — SFX channels only -----------------
        ; Mod_ReArm clears accum + reloads steps for this fresh attack; it reads
        ; sc_mod_*/sc_base_freq/sc_last_freq (SfxChannel-only, latched above), so GATE
        ; on the SFX-channel test exactly like the FM key-on does (a music PSG note
        ; would otherwise read adjacent RAM). No-op when sc_mod_ctrl==0.
        call    Snd_ChanClass            ; CARRY set => ix < $1D00 => MUSIC channel
        jr      c, .skip_rearm           ; music PSG -> no mod re-arm (byte-identical)
        call    Mod_ReArm                ; PSG pitch-mod re-arm (preserves bc/de/hl/ix)
.skip_rearm:
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
; Psg_ApplyMod — one frame of PSG pitch modulation (spec §5). The PSG analogue of
; Mod_ApplyVibrato: both call the SHARED Mod_Advance triangle core (sound_sequencer.asm)
; — the accumulate/speed/steps-reversal/write-on-change logic lives there ONCE (no
; duplication; the $16F0 ceiling has no room for a second copy). The only difference
; is the WRITE TARGET: Mod_Advance returns the modulated 16-bit word = sc_base_freq +
; sc_mod_accum, and here that word is the PSG tone DIVISOR (10 bits used). It is
; re-latched to the SN76489 tone register WITHOUT re-keying. Faithful to S3K's
; zDoModulation, which modulates the PSG note's PERIOD word the same way it modulates
; the FM fnum (the period is the INVERSE of pitch — higher divisor = lower note — and
; we keep that inversion intact; a downward sweep adds to the divisor). Tone routes
; only (noise has no divisor — guaranteed by the caller's PSG-tone-route gate; noise
; channels never set sc_mod_ctrl in the core set).
; In: ix = PSG TONE channel (SFX), sc_mod_ctrl != 0. Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Psg_ApplyMod:
        call    Mod_Advance              ; advance triangle; CF set => no write this frame
        ret     c
        ; de = modulated divisor (d=hi, e=lo). Re-latch via the shared emit helper
        ; (no re-key — pitch only). Falls into Psg_EmitDivisor (tail), which rets.
; ----------------------------------------------------------------------
; Psg_EmitDivisor — write a 10-bit tone DIVISOR to the SN76489 tone register for the
; current channel (latch + data bytes), WITHOUT keying/volume. Shared by Psg_NoteOn
; (fresh note) and Psg_ApplyMod (per-frame pitch sweep) so the divisor-split exists
; once (the $16F0 code ceiling has no room for two copies).
;   latch byte = $80 | (ch<<5) | (div & $0F);   data byte = (div >> 4) & $3F.
; In: ix = PSG tone channel, d = div hi, e = div lo. Clobbers af,bc,de. Preserves hl,ix.
; ----------------------------------------------------------------------
Psg_EmitDivisor:
        push    de                       ; save divisor across Psg_ChBase
        call    Psg_ChBase               ; a = ch<<5 ($00/$20/$40)
        or      SND_PSG_TONE_LATCH       ; a = $80 | (ch<<5)
        ld      c, a                     ; c = latch base (no freq nibble yet)
        pop     de                       ; e = div lo, d = div hi
        ld      a, e
        and     0Fh                      ; a = div & $0F (freq low 4 bits)
        or      c                        ; a = $80 | (ch<<5) | (div & $0F)
        ld      (SND_Z80_PSG), a         ; latch byte

        ; data byte = (div >> 4) & $3F : div bits 9..4 (e>>4 | d<<4).
        ld      a, d
        add     a, a
        add     a, a
        add     a, a
        add     a, a                     ; a = d << 4 (div bits 9..8 land in D5..D4)
        ld      b, a
        ld      a, e
        srl     a
        srl     a
        srl     a
        srl     a                        ; a = e >> 4 = div bits 7..4
        or      b                        ; a = ((d<<4)|(e>>4)) = (div >> 4)
        and     3Fh                      ; data byte is 6 bits
        ld      (SND_Z80_PSG), a         ; data byte (freq high)
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

        ; --- PSG volume envelope (spec §4): add the per-frame env atten delta -------
        ; sc_psgenv_out is the S3K VolEnv delta (attenuation units, higher = quieter),
        ; computed by PsgEnvUpdate. Add it BEFORE the duck fold (env+duck compose) and
        ; BEFORE the noise branch (noise SFX get the contour too). SFX ONLY: sc_psgenv_out
        ; is an SfxChannel-only field (+41) — reading it on a music SeqChannel (39 bytes)
        ; would read adjacent RAM, so gate on ix >= SND_SFX_BASE ($1D00). Music PSG volume
        ; is therefore byte-identical (never touches the env path). Underflow guard (S3K
        ; `bit 4,a`): if the sum sets bit 4 (>= $10) force $0F silent, so a loud-then-quiet
        ; env can't wrap back to loud. hl preserved by contract -> save around the ix test.
        push    hl                       ; (Snd_ChanClass clobbers hl)
        call    Snd_ChanClass            ; CARRY set => ix < $1D00 => MUSIC channel
        pop     hl                       ; restore caller's hl (contract)
        jr      c, .env_done             ; music PSG -> no env field, skip the fold
        ld      a, (ix+sc_psgenv_out)
        or      a
        jr      z, .env_done             ; no env delta -> skip (no-env SFX fast path)
        add     a, c                     ; atten + env delta
        bit     4, a                     ; >= $10 ?
        jr      z, .env_ok
        ld      a, SND_PSG_ATTEN_SILENT  ; $0F (silent) clamp
.env_ok:
        ld      c, a
.env_done:

        ; --- Phase 5a music ducking (spec §7) -------------------------------------
        ; Fold the GLOBAL music duck level into the PSG attenuation so EVERY music
        ; volume write ducks automatically (same rationale as Fm_SetVolume). MUSIC
        ; ONLY: SfxChannels live at/above SND_SFX_BASE ($1D00) and must NOT duck.
        ; Music SeqChannels are strictly below $1D00, so ix's high byte separates
        ; them. Clamp the summed attenuation to $0F (silent) so it can't wrap.
        ; hl is preserved by contract — save it around the ix high-byte test.
        push    hl                       ; (Snd_ChanClass clobbers hl)
        call    Snd_ChanClass            ; CARRY set => ix < $1D00 => MUSIC channel
        pop     hl                       ; restore caller's hl (contract)
        jr      nc, .no_duck             ; SFX channel -> never duck
        ld      a, (SND_SFX_DUCK_LEVEL)
        or      a
        jr      z, .no_duck              ; duck level 0 -> nothing to add
        ; map the carrier-TL-units duck level to PSG attenuation units. The duck
        ; level ramps in SFX_DUCK_RAMP_STEP TL units; PSG attenuation is 4-bit
        ; (>>3 like Psg_VolToAtten). At full SFX_DUCK_DEPTH this yields ~the
        ; authored SFX_DUCK_PSG_DEPTH drop; scale-then-clamp keeps the ramp smooth.
        srl     a
        srl     a
        srl     a                        ; a = duck level >> 3 (TL units -> atten units)
        add     a, c                     ; atten + ducked attenuation
        cp      SND_PSG_ATTEN_SILENT+1   ; clamp to $0F (silent)
        jr      c, .duck_ok
        ld      a, SND_PSG_ATTEN_SILENT
.duck_ok:
        ld      c, a                     ; ducked attenuation
.no_duck:

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
        call    Psg_EnvCursorReset       ; SFX: restart the vol-env contour on this attack (spec §4)
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
