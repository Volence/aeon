# Faithful PSG Noise Pitch/Color (HCZ2 hi-hat rate-3 coupling) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HCZ2's PSG noise hi-hat sound like S3K's by clocking the SN76489 noise from tone-channel-2's frequency (rate-3 mode) per note, instead of clocking at a stale value.

**Architecture:** A new zero-tick opcode `MEV_PSGNOISE` ($F2) owns the noise mode/rate (writes the SN76489 control byte + silences ch2's tone volume). Music noise notes carry a real PITCH; the engine writes that note's divisor to tone-2's frequency latch ($C0) = the noise clock (gated on rate==3, clamped ≥1) and shapes each hit with the existing per-note PSG volume envelope. SFX noise keeps its legacy fixed-rate path (the SFX transcoder drops `smpsPSGform`).

**Tech Stack:** Z80 assembly (engine), AS macro assembler, Python 3 (converter + packer), oracle (Exodus) MCP for verification (short chunked captures only — long runs froze it).

**Spec:** `docs/superpowers/specs/2026-06-26-hcz2-psg-noise-pitch-design.md`

**Build:** `timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/np_build.log 2>&1; echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/np_build.log | tail`. HCZ2 trigger = DEBUG **UP**.

**Key facts (researched):**
- SN76489: rate-3 (`$E7`/`$E3`) clocks the noise from tone-2's ($C0) frequency, independent of ch2's volume. Writing the control register ($E0-$EF) RESETS the LFSR; writing $C0 (freq) or $F0 (noise vol) does NOT. So write control on-change (not per-note → no click); write $C0 per note to retune.
- Reference consensus (S.C.E./Flamedriver, S2, Ristar, Gunstar, Alien Soldier, TF4): per-note $C0 write = the clock; control once; per-note PSG vol-env shapes each hit; silence ch2 *volume* ($DF).
- `Psg_NoteOn`/`Psg_EmitDivisor` (`engine/sound_psg.asm:147-265`): divisor from `PsgDivisorTableZ[pitch]`, latch=`$80|(ch<<5)|(div&$0F)` via `Psg_ChBase`, data=`(div>>4)&$3F`. `PsgDivisorTableZ` covers pitch 0..94; `nMaxPSG1`=$D3 → index 82 ✓.
- Current `Psg_Noise` (`sound_psg.asm:346-353`): `$E0|(pitch&7)` control + volume; no $C0.
- SFX noise: the SFX transcoder DROPS `smpsPSGform` (`sound_sfx.asm:428-432, 921-931`), so SFX noise is fixed-rate, gets its control from `Psg_Noise` pitch&7, never writes $C0. Keep that path for SFX.
- Opcode `$F2` = first free `Seq_BadOpcode` slot (`sound_sequencer.asm:1143`). New handler `Seq_Op_PsgNoise`.
- RAM: `SeqChannel` is 42 B (`sc_psgenv_out` +41). Add `sc_noise_mode` at +42 (SeqChannel-only; SfxChannel's +42 is `sc_mod_ctrl` — never cross-read: music-noise path vs SFX-mod path). Z80 headroom 644 B.
- Converter noise: `convert_channel` replaces note pitch with `st.noise_pitch` (`smps_import.py` ~304-310, 825-833); `_dispatch_flag smpsPSGform` sets `st.noise_pitch` (~617-633). `song_packer.PsgEnv` (`song_packer.py:210-220`) is the event pattern.

---

## Task 1: Engine — `MEV_PSGNOISE` constant + `sc_noise_mode` field + zero-init

**Files:** Modify `sound_constants.asm`, `engine/z80_sound_driver.asm`

- [ ] **Step 1: Add the opcode constant** in `sound_constants.asm` near the other MEV_ constants (after `MEV_SPINREV_RESET = $F1`):

```asm
MEV_PSGNOISE      = $F2   ; + ctrl : set the SN76489 noise control byte (mode+rate),
                          ; silence ch2 tone volume; zero-tick. Owns noise mode (the
                          ; note then carries PITCH for the rate-3 tone-2 clock).
```

- [ ] **Step 2: Add `sc_noise_mode` to `SeqChannel`** — after `sc_psgenv_out ds.b 1 ; +41`:

```asm
sc_noise_mode   ds.b 1   ; +42 SN76489 noise control byte ($E0|mode|rate) latched by
                         ; MEV_PSGNOISE. Music-noise channel only. (SfxChannel's +42 is
                         ; sc_mod_ctrl — different struct, never cross-read: the music
                         ; noise path reads this; the SFX mod path reads sc_mod_ctrl.)
SeqChannel endstruct      ; = 43 bytes
```

Update the assert: `if SeqChannel_len <> 43` / `error "...expected 43"`. Add the bare alias near the other SeqChannel aliases: `sc_noise_mode = SeqChannel_sc_noise_mode`.

- [ ] **Step 3: Build green**

Run the build command. Expected `EXIT=0`, `Build complete` (RAM: SND_SEQ_END $19D6→$19E1, still far below $1B00).

- [ ] **Step 4: Zero `sc_noise_mode` at song load** in `engine/z80_sound_driver.asm` `.chan_init`, right after the `ld (ix+sc_psgenv_out), 0` line added earlier:

```asm
        ld      (ix+sc_noise_mode), 0    ; noise mode unset until MEV_PSGNOISE
```

- [ ] **Step 5: Build green + commit**

```bash
git add sound_constants.asm engine/z80_sound_driver.asm
git commit -m "feat(sound): MEV_PSGNOISE opcode constant + sc_noise_mode field (+42)"
```

## Task 2: Engine — parameterize the divisor writer + add `Psg_EmitNoiseClock`

**Files:** Modify `engine/sound_psg.asm` (`Psg_EmitDivisor` ~239-265)

- [ ] **Step 1: Extract a latch-base-parameterized core.** Replace `Psg_EmitDivisor` with a thin wrapper + a `c`-parameterized core so the divisor-split exists once (DRY; the noise clock reuses it):

```asm
Psg_EmitDivisor:
        push    de                       ; save divisor across Psg_ChBase
        call    Psg_ChBase               ; a = ch<<5 ($00/$20/$40)
        or      SND_PSG_TONE_LATCH       ; a = $80 | (ch<<5)
        ld      c, a                     ; c = latch base
        pop     de
        ; fall into Psg_EmitDivisorTo
; Psg_EmitDivisorTo — write 10-bit divisor (d=hi,e=lo) to the PSG with latch BASE in c
; ($80|ch<<5 for a tone channel, $C0 for the rate-3 noise clock). latch=c|(div&$0F),
; data=(div>>4)&$3F. Clobbers af,b. Preserves c,hl,ix.
Psg_EmitDivisorTo:
        ld      a, e
        and     0Fh                      ; div & $0F
        or      c                        ; latch base | low nibble
        ld      (SND_Z80_PSG), a         ; latch byte
        ld      a, d
        add     a, a
        add     a, a
        add     a, a
        add     a, a                     ; d << 4
        ld      b, a
        ld      a, e
        srl     a
        srl     a
        srl     a
        srl     a                        ; e >> 4
        or      b
        and     3Fh
        ld      (SND_Z80_PSG), a         ; data byte
        ret
```

- [ ] **Step 2: Add `Psg_EmitNoiseClock`** (write the note's divisor to tone-2 = the rate-3 clock, clamped ≥1) right after `Psg_EmitDivisorTo`:

```asm
; ----------------------------------------------------------------------
; Psg_EmitNoiseClock — write a note's PSG divisor to tone-2's frequency latch ($C0).
; In rate-3 noise mode ($x7/$x3) the SN76489 clocks the noise from tone-2's frequency,
; so this sets the noise pitch/color. Divisor clamped >= 1 (hw breaks the noise clock
; at tone-2 freq 0). Writing $C0 does NOT reset the LFSR. In: a = pitch index 0..94.
; Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Psg_EmitNoiseClock:
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; pitch*2
        ld      de, PsgDivisorTableZ
        add     hl, de
        ld      e, (hl)
        inc     hl
        ld      d, (hl)                  ; de = 10-bit divisor
        ld      a, d
        or      e
        jr      nz, .nonzero
        inc     e                        ; divisor 0 -> 1 (hw clamp)
.nonzero:
        ld      c, 0C0h                  ; tone-2 frequency latch = the noise clock
        jr      Psg_EmitDivisorTo
```

- [ ] **Step 3: Build green + commit** (both unused so far; tone path byte-identical):

```bash
git add engine/sound_psg.asm
git commit -m "feat(sound): parameterize PSG divisor writer + Psg_EmitNoiseClock (tone-2 clock)"
```

## Task 3: Engine — `Seq_Op_PsgNoise` opcode handler + table entry

**Files:** Modify `engine/sound_sequencer.asm`

- [ ] **Step 1: Add the handler** (model on `Seq_Op_PsgEnv`). Place it near the other coordination handlers:

```asm
; $F2 MEV_PSGNOISE + ctrl : set the SN76489 noise control byte (mode+rate), store it
; for the per-note rate gate + steal re-arm, and silence tone-2's VOLUME so ch2 makes
; no audible tone while clocking the noise. Zero-tick. Writing the control register
; RESETS the LFSR, so this is on-change (the opcode), NOT per-note. Music channels only
; (the SFX transcoder never emits it); harmless if it ever lands on a non-noise channel.
Seq_Op_PsgNoise:
        ld      a, (hl)
        inc     hl                       ; consume operand (the $E0-$EF control byte)
        ld      (ix+sc_noise_mode), a    ; latch for the per-note rate-3 gate + re-arm
        ld      (SND_Z80_PSG), a         ; write the noise control (resets LFSR once)
        ld      a, SND_PSG_SILENCE_2     ; $DF = ch2 tone volume, max attenuation
        ld      (SND_Z80_PSG), a         ; silence ch2 tone (its freq still clocks noise)
        jp      Seq_ContinueFetch
```

- [ ] **Step 2: Add `SND_PSG_SILENCE_2 = $DF`** to `sound_constants.asm` near `SND_PSG_SILENCE_N` ($FF): `SND_PSG_SILENCE_2 = $DF   ; ch2 (tone-2) volume latch | max attenuation (silence its tone)`.

- [ ] **Step 3: Wire the table entry** — change `sound_sequencer.asm:1143` from `dw Seq_BadOpcode ; $F2 reserved` to:

```asm
        dw      Seq_Op_PsgNoise          ; $F2 MEV_PSGNOISE
```

- [ ] **Step 4: Build green + commit** (no song emits $F2 yet):

```bash
git add engine/sound_sequencer.asm sound_constants.asm
git commit -m "feat(sound): Seq_Op_PsgNoise ($F2) — set noise control + silence ch2 tone"
```

## Task 4: Engine — `Psg_Noise` rewrite (music tone-2 clock + SFX legacy)

**Files:** Modify `engine/sound_psg.asm` (`Psg_Noise` ~346-353)

- [ ] **Step 1: Replace `Psg_Noise`.** Music noise: control came from MEV_PSGNOISE; write the tone-2 clock from the real pitch (gated rate==3) + noise volume + retrigger the vol-env. SFX noise: unchanged legacy path (mode in pitch&7).

```asm
Psg_Noise:
        ; a = note value. MUSIC: a real pitch index -> tone-2 clock (rate-3). SFX:
        ; legacy mode-in-pitch (the SFX transcoder drops smpsPSGform, so SFX noise has
        ; no MEV_PSGNOISE control). Branch on channel class.
        push    af
        call    Snd_ChanClass            ; CARRY set => MUSIC channel
        pop     af
        jr      nc, .sfx
        ; --- MUSIC noise: tone-2 ($C0) clock + noise volume; control set by MEV_PSGNOISE ---
        set     SCF_KEYED_B, (ix+sc_flags)
        call    Psg_EnvCursorReset       ; retrigger the PSG vol-env (per-hit decay)
        ld      b, a                     ; b = pitch
        ld      a, (ix+sc_noise_mode)
        and     3                        ; rate bits (11 = clock-from-tone-2)
        cp      3
        jr      nz, .music_vol           ; preset rate -> don't perturb tone-2
        ld      a, b
        call    Psg_EmitNoiseClock       ; write divisor to $C0 (clamped >=1)
.music_vol:
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; noise volume ($F0) + envelope fold
.sfx:
        and     7                        ; legacy: low 3 bits = mode<<2 | rate
        or      SND_PSG_NOISE_CTRL       ; $E0 | (pitch & 7)
        ld      (SND_Z80_PSG), a         ; noise control byte
        set     SCF_KEYED_B, (ix+sc_flags)
        call    Psg_EnvCursorReset
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume
```

- [ ] **Step 2: Update the file header** (`sound_psg.asm:43-51`, "NOISE NOTE MAPPING") to describe the split: MUSIC noise note = pitch (tone-2 clock, mode via MEV_PSGNOISE); SFX noise note = legacy mode bits. Keep it accurate.

- [ ] **Step 3: Build green + commit** (music noise transiently wrong until the converter emits pitch+MEV_PSGNOISE in Task 6 — verified at Task 7):

```bash
git add engine/sound_psg.asm
git commit -m "feat(sound): Psg_Noise music path clocks tone-2 from note pitch (rate-3); SFX legacy kept"
```

## Task 5: Engine — re-arm noise control after an SFX steal (on-change)

**Files:** Modify `engine/sound_sfx.asm` (noise restore ~921-931)

- [ ] **Step 1: Re-write the music noise control on restore.** In the noise re-key restore path (where `ix` = the music noise channel, after the steal releases), add — before/at the re-key:

```asm
        ; Re-arm the music noise control: an SFX noise burst wrote its own $E_ control
        ; (resetting the LFSR); restore this channel's latched mode so the hat color
        ; returns. (sc_noise_mode is 0 if this channel never set a mode -> skip.)
        ld      a, (ix+sc_noise_mode)
        or      a
        jr      z, .no_noise_rearm
        ld      (SND_Z80_PSG), a         ; re-write the noise control byte
        ld      a, SND_PSG_SILENCE_2     ; $DF: re-silence ch2 tone
        ld      (SND_Z80_PSG), a
.no_noise_rearm:
```

(Place this in the existing noise-restore branch; `ix` already points at the music noise channel there per the current code's `pop ix`.)

- [ ] **Step 2: Build green + commit**

```bash
git add engine/sound_sfx.asm
git commit -m "feat(sound): re-arm music noise control after an SFX steal (on-change)"
```

## Task 6: Packer + converter — emit `MEV_PSGNOISE`, noise notes carry pitch

**Files:** Modify `tools/song_packer.py`, `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Add the packer event.** In `tools/song_packer.py` add `MEV_PSGNOISE = 0xF2` near the other MEV constants, and a `PsgNoise` event class (pattern from `PsgEnv`):

```python
class PsgNoise(Event):
    """MEV_PSGNOISE: set the SN76489 noise control byte (mode+rate)."""
    def __init__(self, ctrl):
        self.ctrl = ctrl
    def to_bytes(self):
        return bytes([MEV_PSGNOISE, self.ctrl & 0xFF])
    def validate(self):
        if not (0xE0 <= self.ctrl <= 0xEF):
            raise PackError(f"PsgNoise ctrl {self.ctrl:#x} out of range $E0..$EF")
```

- [ ] **Step 2: Write the failing converter tests** in `tools/test_smps_import.py`:

```python
from song_packer import PsgNoise

def test_smpspsgform_emits_psgnoise():
    # smpsPSGform $E7 -> PsgNoise($E7) (the control byte), not a noise_pitch fold.
    ev = convert_channel("PSG", ["\tsmpsPSGform $E7", "\tdc.b nMaxPSG1, $06"],
                         {}, _cfg(), ConvState(), noise=True)
    pn = [e for e in ev if isinstance(e, PsgNoise)]
    assert len(pn) == 1 and pn[0].ctrl == 0xE7

def test_noise_note_carries_real_pitch():
    # The noise note keeps the real pitch (nMaxPSG1 -> index 82), NOT the mode bits.
    from song_packer import Note, NoteDur
    ev = convert_channel("PSG", ["\tsmpsPSGform $E7", "\tdc.b nMaxPSG1, $06"],
                         {}, _cfg(), ConvState(), noise=True)
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert notes and notes[0].pitch == (0xD3 - 0x81)   # 82, not 7
```

- [ ] **Step 3: Run → FAIL.** `cd tools && python3 -m pytest test_smps_import.py -q -k "psgform or noise_note_carries"` → FAIL.

- [ ] **Step 4: Implement.** In `tools/smps_import.py`:
  - Import `PsgNoise` from `song_packer`.
  - In `_dispatch_flag`, change the `smpsPSGform` branch so that on a noise channel it emits `out.append(PsgNoise(form))` (the full `$E0-$EF` control byte) instead of setting `st.noise_pitch`. On a non-noise channel keep the existing warn-skip.
  - In `convert_channel`, REMOVE the noise-pitch replacement: a noise-channel note emits its REAL pitch (the same `pitch = (b - MEV_NOTE_BASE) + st.transpose` as a tone), not `st.noise_pitch`. Delete `st.noise_pitch` and the `if st.noise: pitch = st.noise_pitch` branch.
  - Keep `st.noise` / `_channel_reaches_noise_form` / `_assign_routes` (the channel still routes to `CHROUTE_PSGN`).

- [ ] **Step 5: Run → PASS.** `cd tools && python3 -m pytest test_smps_import.py -q` → all pass.

- [ ] **Step 6: Regenerate the song.** `python3 data/sound/song_hcz2.py 2>&1 | grep -iE "wrote|WARN"`. Confirm a `MEV_PSGNOISE`/`$F2` appears and the noise channel notes are real pitches.

- [ ] **Step 7: Build green + commit**

```bash
git add tools/song_packer.py tools/smps_import.py tools/test_smps_import.py data/sound/song_hcz2.asm
git commit -m "feat(tools): emit MEV_PSGNOISE from smpsPSGform + noise notes carry real pitch"
```

## Task 7: Oracle verification (short chunked captures)

**Files:** none

- [ ] **Step 1:** `cp s4.bin /tmp/np.bin && cp s4.lst /tmp/np.lst`; via MCP `emulator_reload_rom(/tmp/np.bin)`, `emulator_load_symbols(/tmp/np.lst)`.
- [ ] **Step 2:** `emulator_run_frames(240)`; `emulator_vgm_start(/tmp/np.vgm)`; `emulator_press(["up"],3)`; then **two** `emulator_run_frames(450)` chunks (NOT one long run — long runs froze the oracle); `emulator_vgm_stop`.
- [ ] **Step 3:** Confirm tone-2 frequency is now clocked: `python3 /tmp/psg_ch2freq.py /tmp/np.vgm` → ch2 frequency-latch writes **> 0** (was 0). Re-run `/tmp/psg_noise.py` + `/tmp/blast_detect.py` → still 0 blasts, decay intact. Optionally `audio_spectrum` (source 'psg') with only the noise channel enabled to compare the noise color.
- [ ] **Step 4:** Listen / confirm the hat timbre matches S3K and FM/PSG1/2 are unaffected.

## Task 8: Docs + finish

- [ ] **Step 1:** Update `docs/ENGINE_ARCHITECTURE.md` §6 (PSG noise now rate-3 tone-2-clocked for music) + the memory. Commit.
- [ ] **Step 2:** Per superpowers:finishing-a-development-branch — converter tests pass, build green, oracle-verified; decide with the user whether to FF-merge `feat/hcz2-import` → master (carries the drums fix + envelope fix + this).

---

## Self-review

- **Spec coverage:** MEV_PSGNOISE on-change + silence ch2 (Tasks 1,3) → spec §Engine.1; note=pitch folded via $C0 latch, rate-3 gate, clamp ≥1 (Tasks 2,4) → §Engine.2; converter (Task 6) → §Converter; steal re-arm (Task 5) → adjustment 1; verification (Task 7) → §Verification. All covered. Per-voice cadence flag deliberately deferred (spec scope).
- **No placeholders:** every code step shows the asm/python. SFX-restore exact placement (Task 5) keyed to the existing `pop ix`/noise branch.
- **Consistency:** `sc_noise_mode` +42; `MEV_PSGNOISE`=$F2 (constant + packer + table all agree); `SND_PSG_SILENCE_2`=$DF used by Tasks 3+5; `Psg_EmitDivisorTo`/`Psg_EmitNoiseClock` names match across Tasks 2+4; SeqChannel_len 42→43.
- **Ordering:** engine first (green, music noise transiently wrong), converter last (Task 6 makes it correct), verify Task 7. SFX path kept byte-identical (legacy `.sfx` branch + rate-3 gate is music-only).
