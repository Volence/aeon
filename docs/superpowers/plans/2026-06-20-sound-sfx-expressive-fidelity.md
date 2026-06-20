# Sound — S3K SFX Expressive Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the three expressive layers the 5a SFX transcoder dropped, so the transcoded S3K SFX sound *faithful to S3K*: (1) PSG volume envelopes (`smpsPSGvoice`/`sTone_XX` → per-frame attenuation contour), (2) per-note pitch modulation (`smpsModSet` → a faithful continuous additive freq-word vibrato/sweep, NOT a pitch-env re-key), and (3) the runtime, re-trigger-driven spindash rev (`smpsSpindashRev`). Plus the prerequisite SFX pitch-table fix (`SCF_PITCH_CHROMATIC`) that the modulation work depends on. Jump's downward "pew" sweep, skid/break attack shapes, and the rising spindash rev all sound right — verified spectrally, by rendered audio, and by ear.

**Architecture:** Every feature is a **clean, additive, default-off extension** that reuses the existing per-frame `ModUpdate` modulation renderer (`engine/sound_sequencer.asm`), the `Psg_SetVolume` choke-point (`engine/sound_psg.asm`), the `Fm_NoteOnFreq` `$A4/$A0` emit tail (`engine/sound_fm.asm`), and the zero-tick coordination-opcode pattern. All new per-channel state is **appended** to `SeqChannel` + its `SfxChannel` mirror (no existing offset moves); all new opcodes default inert (a zeroed slot does nothing); new per-frame renderers are **gated** so a held note with no envelope/modulation costs a single bit-test (the Phase-3 cycle budget is preserved). The spindash rev lives entirely in the driver (one global byte + re-trigger counting) — no `{id,priority}` ABI widening. **Design-for-C / build-for-A:** the new opcodes + state are laid out so a future PSG-modulation-on-music or per-SFX-tempo extension is purely additive.

**Tech Stack:** Z80 + 68000 assembly (AS Macro Assembler) + Python transcoder. No asm unit-test framework — every asm task verifies by `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` (exit 0, advisory s4lint warnings OK), Exodus MCP on the live `oracle` emulator (`emulator_reload_rom`→resume, `emulator_z80_read`/`emulator_z80_write`, `emulator_vgm_start`/`vgm_stop`, and the NEW `emulator_audio_spectrum` spectral tools) to confirm the contour/sweep/rev, and `vgm2wav` rendered audio A/B. **Acceptance per feature is SPECTRAL/audible, not "it builds"** (per spec §9). NO breakpoints/step on the emulator (they wedge it) — free-run + `run_to_scanline` + `z80_read` + vgm + `audio_spectrum` only. Python transcoder tasks verify via real `pytest` (extend `tools/test_sfx_transcode.py`). Honor `CODING_CONVENTIONS.md` (`struct`/`endstruct`, build-time RAM asserts, `function` for compile-time math, `.s`/`.w`/`.l`-free Z80 but explicit-size discipline on the 68k side, no `mulu`/`divu`, PascalCase routines, ALL_CAPS constants, `.lowercase` locals).

**Spec:** `docs/superpowers/specs/2026-06-20-sound-sfx-expressive-fidelity-design.md`
**Builds on:** Phase 5a Core SFX Engine (`engine/sound_sfx.asm`, the S3K transcoder, steal/restore/duck) + Phase 3a FM depth (the per-frame `ModUpdate` layer). Phase 3a is merged to `master`; the **5a work is committed on this branch `feat/sound-phase5a-sfx` (NOT yet merged)** and is live in the working tree — this fidelity work continues on the same branch. Use the live branch code as each "before".
**References:** S3K `skdisasm/Sound/Z80 Sound Driver.asm` — VolEnv pointer table L4494, bodies L4503-4572 (`VolEnv_0C: db 0,81h`; `VolEnv_0D: db 2,83h`; `VolEnv_0E: db 0,2,4,6,8,10h,83h`; `VolEnv_1C` 44-byte fade; `VolEnv_02`/`VolEnv_14`/`VolEnv_15`/`VolEnv_16`/`VolEnv_10`), per-frame apply L4058-4214, attack reset L1066, `cfSetPSGVolEnv` L3583; `zPrepareModulation` L1237-1259 (`srl a` halve at L1254), `zDoModulation` L1279-1326; `zSpindashRev` L155, `cfSpindashRev` L3039-3051, `cfResetSpindashRev` L4046, spindash no-reset L1935, normal-SFX reset L1971. SFX: `Sound/SFX/62 - Jump.asm` (`smpsPSGvoice sTone_0D` + `smpsModSet $02,$01,$F8,$65` on PSG1), `Sound/SFX/AB - Spin Dash.asm` (`smpsSpindashRev` + `smpsSetvoice $00` + `smpsModSet $01,$01,$1A,$01` + `smpsModSet 0,0,0,0` + `smpsResetSpindashRev` on FM5). Macros `skdisasm/Sound/_smps2asm_inc.asm` (smpsPSGvoice $F5 L599, smpsModSet $F0 L553, smpsSpindashRev $E9 L657).

---

## File Structure (what each file owns)

- `sound_constants.asm` — the `SCF_PITCH_CHROMATIC` flag (a free `sc_flags` bit + the extended sync assert), the 4 new MEV opcodes (`MEV_PSGENV=$EB`, `MEV_MODSET=$EC`, `MEV_SPINREV=$F0`, `MEV_SPINREV_RESET=$F1`) + their collision-assert chains, and the appended `SeqChannel`/`SfxChannel` fields (`sc_psgenv`/`_cur`/`_out`; `sc_mod_ctrl`/`_wait`/`_speed`/`_delta`/`_steps`/`_accum`(w)/`sc_base_freq`(w)/`sc_last_freq`(w)) with updated `_len`/mirror/`(ix+d)` asserts.
- **`PsgVolEnv_Table` data** — a pointer table + S3K-exact `VolEnv` byte-stream bodies for the sTones our corpus uses. **NOTE: `engine/sound_tables_z80.asm` is GENERATED by `tools/gen_sound_tables.py` ("DO NOT EDIT BY HAND") — so the env table must NOT be hand-added there.** Author it in `tools/gen_sound_tables.py`'s `emit_asm_z80()` (so it regenerates alongside `FmPitchTableZ`), OR in a new hand-authored `engine/sound_psgenv_tables.asm` included right after `sound_tables_z80.asm` in `z80_sound_driver.asm`. This plan uses the **generator** path (keeps all Z80 tables in one generated file). `PsgEnvUpdate`/`PsgVolEnv_Resolve` (code) live in `engine/sound_sequencer.asm`/`engine/sound_psg.asm`, NOT the generated data file.
- `engine/sound_sequencer.asm` — the `SCF_PITCH_CHROMATIC` branch in `ModUpdate`'s two re-key paths (`count==1` + `.multipoint`), the `PsgEnvUpdate` + `Mod_ApplyVibrato` ModUpdate sub-steps (PSG-route + FM-vibrato), the `MEV_PSGENV`/`MEV_MODSET`/`MEV_SPINREV`/`MEV_SPINREV_RESET` opcode handlers + their `SeqOpcodeTable` entries.
- `engine/sound_fm.asm` — the `sc_base_freq` latch + per-note vibrato re-arm hook in the `Fm_NoteOnFreq` tail.
- `engine/sound_psg.asm` — the PSG-env fold into `Psg_SetVolume` (atten domain + `bit 4` clamp, before the duck fold + the noise branch) + the `sc_base_freq` latch in `Psg_NoteOn`.
- `engine/sound_sfx.asm` — set `SCF_PITCH_CHROMATIC` on every SFX slot at `Sfx_BeginSound` init; the spindash-rev reset-on-non-spindash-SFX line in `Sfx_BeginSound`. (`Sfx_Restore`'s `Fm_NoteFromTable` is **left as-is** — it restores the *music* channel, where the per-song table is correct.)
- `engine/z80_sound_driver.asm` — `Snd_SpindashRev` global zeroed at `SndDrv_Init`.
- `tools/sfx_transcode.py` — emit `MEV_PSGENV` from `smpsPSGvoice`, `MEV_MODSET` from `smpsModSet`, `MEV_SPINREV`/`MEV_SPINREV_RESET` from `smpsSpindashRev`/`smpsResetSpindashRev` (remove the flat `_SPINDASH_STEP` bake); new `song_packer`-style Event classes. `tools/test_sfx_transcode.py` — extended pytest.
- `tools/song_packer.py` — the new `PsgEnv`/`ModSet`/`SpinRev`/`SpinRevReset` Event classes (encoders), mirroring the `OpBias`/`PitchEnv` pattern.

---

## Task 1: Pitch-table fix — `SCF_PITCH_CHROMATIC` (prerequisite)

**Goal:** fix the latent SFX pitch-domain bug (spec §3): an SFX FM note-on keys via `Fm_NoteOn`/`FmPitchTableZ` (the chromatic 98-entry table), but `ModUpdate`'s re-key paths key via `Fm_NoteFromTable`/`Snd_PitchTabPtr` (the per-*song* 132-entry table). So any SFX pitch-env re-key reads the wrong table → octave warble. Add a free `sc_flags` bit `SCF_PITCH_CHROMATIC`; `Sfx_BeginSound` sets it on every SFX slot; `ModUpdate`'s `count==1` + `.multipoint` re-key paths branch on it (set → `Fm_NoteOn`/`FmPitchTableZ`; clear → `Fm_NoteFromTable`, music unchanged). **Regression: music byte-identical (bit clear on every music channel); a transcoded FM SFX's pitch-env agrees with its note-on pitch.** This MUST land before Task 4 (FM pitch-mod) so the modulation operates in a consistent pitch domain.

**Files:** Modify `sound_constants.asm`, `engine/sound_sequencer.asm`, `engine/sound_sfx.asm`.

- [ ] **Step 1: Add `SCF_PITCH_CHROMATIC_B = 7` + mask + extend the sync assert.** In `sound_constants.asm`, the live `SCF_*` block ends at `SCF_SFX_OVERRIDE_B = 6` (bit 7 is the only free bit). Replace this exact block:
```asm
SCF_SFX_OVERRIDE_B = 6

SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B
SCF_REKEY       = 1<<SCF_REKEY_B
SCF_SFX_OVERRIDE = 1<<SCF_SFX_OVERRIDE_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B) || (SCF_REKEY <> 1<<SCF_REKEY_B) || (SCF_SFX_OVERRIDE <> 1<<SCF_SFX_OVERRIDE_B)
          error "SCF_* masks and _B bit numbers are out of sync"
        endif
```
with:
```asm
SCF_SFX_OVERRIDE_B = 6
; SFX Expressive Fidelity (spec §3): an SFX channel keys its NOTE-table pitch via
; the CHROMATIC FmPitchTableZ (Fm_NoteOn). When SET, ModUpdate's re-key paths key
; via Fm_NoteOn (chromatic) instead of Fm_NoteFromTable (the per-SONG fnum table),
; so an SFX pitch-env / vibrato re-key reads the SAME table the note-on used. Music
; channels leave it CLEAR -> Fm_NoteFromTable (per-song), byte-identical. Last bit.
SCF_PITCH_CHROMATIC_B = 7

SCF_ACTIVE      = 1<<SCF_ACTIVE_B
SCF_KEYED       = 1<<SCF_KEYED_B
SCF_IS_FM       = 1<<SCF_IS_FM_B
SCF_IS_PSG      = 1<<SCF_IS_PSG_B
SCF_IS_DAC      = 1<<SCF_IS_DAC_B
SCF_REKEY       = 1<<SCF_REKEY_B
SCF_SFX_OVERRIDE = 1<<SCF_SFX_OVERRIDE_B
SCF_PITCH_CHROMATIC = 1<<SCF_PITCH_CHROMATIC_B

        ; the _B bit numbers and the masks must stay tied together.
        if (SCF_ACTIVE <> 1<<SCF_ACTIVE_B) || (SCF_KEYED <> 1<<SCF_KEYED_B) || (SCF_IS_FM <> 1<<SCF_IS_FM_B) || (SCF_IS_PSG <> 1<<SCF_IS_PSG_B) || (SCF_IS_DAC <> 1<<SCF_IS_DAC_B) || (SCF_REKEY <> 1<<SCF_REKEY_B) || (SCF_SFX_OVERRIDE <> 1<<SCF_SFX_OVERRIDE_B) || (SCF_PITCH_CHROMATIC <> 1<<SCF_PITCH_CHROMATIC_B)
          error "SCF_* masks and _B bit numbers are out of sync"
        endif
```
Also update the `sc_flags` field comment at `SeqChannel`'s `sc_flags ds.b 1` line — the live comment reads `; +10 bit0=active, bit1=keyed, bit2=is_fm, bit3=is_psg, bit4=is_dac, bit6=sfx_override`; append `, bit7=pitch_chromatic`.

- [ ] **Step 2: Branch the `count==1` re-key path in `ModUpdate`.** In `engine/sound_sequencer.asm`, the `count==1` path's re-key tail (the live code) is:
```asm
.rekey_on:
        ld      a, (ix+sc_points)        ; (re)load sc_points[0] (Fm_NoteOff clobbered a)
        call    Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)
        ; reload the note-fill countdown for this fresh attack (master 0 -> stays legato)
        ld      a, (ix+sc_fill_master)
        ld      (ix+sc_fill_count), a
        ret
```
Replace with:
```asm
.rekey_on:
        ld      a, (ix+sc_points)        ; (re)load sc_points[0] (Fm_NoteOff clobbered a)
        bit     SCF_PITCH_CHROMATIC_B, (ix+sc_flags)
        jr      z, .rekey_persong        ; clear -> music: per-song fnum table
        call    Fm_NoteOn                ; SFX: chromatic FmPitchTableZ (same table the note-on used)
        jr      .rekey_fill
.rekey_persong:
        call    Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)
.rekey_fill:
        ; reload the note-fill countdown for this fresh attack (master 0 -> stays legato)
        ld      a, (ix+sc_fill_master)
        ld      (ix+sc_fill_count), a
        ret
```
(`Fm_NoteOn` and `Fm_NoteFromTable` have the identical contract: `In: ix=SeqChannel, a=note index; Clobbers af,bc,de,hl; Preserves ix; sets SCF_KEYED`. The only difference is the table. Note: `Fm_NoteOn` does NOT apply `sc_transpose` — that is correct for SFX, whose spindash rev applies the transpose to the note index at the SPINREV opcode, see Task 6, so the chromatic note index is already final.)

- [ ] **Step 3: Branch the `.multipoint` re-key path in `ModUpdate`.** In the same file, the `.multipoint` tail (live code) is:
```asm
.mp_nocarry:
        ld      a, (hl)                  ; a = sc_points[cursor] (absolute fnum idx)
        ld      (ix+sc_note), a          ; sc_note = last-rendered note index
        jp      Fm_NoteFromTable         ; look up per-song table + key on (preserves ix)
```
Replace with:
```asm
.mp_nocarry:
        ld      a, (hl)                  ; a = sc_points[cursor] (absolute fnum idx)
        ld      (ix+sc_note), a          ; sc_note = last-rendered note index
        bit     SCF_PITCH_CHROMATIC_B, (ix+sc_flags)
        jp      z, Fm_NoteFromTable      ; clear -> music: per-song table (tail-call, preserves ix)
        jp      Fm_NoteOn                ; set -> SFX: chromatic table (tail-call, preserves ix)
```

- [ ] **Step 4: Set `SCF_PITCH_CHROMATIC` on every SFX slot at init.** In `engine/sound_sfx.asm`, `Sfx_BeginSound`'s slot-init sets `sc_flags` from the route class. The live code is:
```asm
        ; sc_flags = class bits, minus SCF_ACTIVE (Sfx_Steal arms it last).
        call    Snd_RouteClassFlags      ; a = SCF_ACTIVE | class bit (FM/PSG/DAC)
        res     SCF_ACTIVE_B, a
        ld      (ix+sc_flags), a
```
Replace with:
```asm
        ; sc_flags = class bits, minus SCF_ACTIVE (Sfx_Steal arms it last), PLUS
        ; SCF_PITCH_CHROMATIC: SFX notes key via FmPitchTableZ (Fm_NoteOn), so
        ; ModUpdate's re-key paths must use the chromatic table too (spec §3) — else
        ; a pitch-env / vibrato re-key reads the per-song table and warbles octaves.
        call    Snd_RouteClassFlags      ; a = SCF_ACTIVE | class bit (FM/PSG/DAC)
        res     SCF_ACTIVE_B, a
        or      SCF_PITCH_CHROMATIC      ; mark this slot's pitch domain as chromatic
        ld      (ix+sc_flags), a
```
(The `.wipe` loop already zeroed the whole slot before this, so the bit is set only here, only on SFX channels. Music `SeqChannel`s are wiped by `Snd_LoadSong`'s `.seq_clr` and never set this bit — they stay on the per-song path.)

- [ ] **Step 5: Build + regression (music unchanged).** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` → exit 0. On `oracle`: `emulator_reload_rom` → resume, play Moving Trucks (press A to restart). `emulator_vgm_start` → capture ~10 s → `emulator_vgm_stop` → `vgm2wav`. Compare energy + spectrum against a pre-change capture: byte-identical (no music channel sets the chromatic bit, so every re-key still goes `Fm_NoteFromTable`). `emulator_z80_read` a music FM `SeqChannel`'s `sc_flags` — bit 7 clear.
- [ ] **Step 6: Verify the SFX pitch domain agrees.** With a song playing, post Spindash `$AB` ($AB → `SND_REQ_SFX` at $1F03 via `emulator_z80_write`) and Jump `$62`. `emulator_z80_read` the active SFX FM `SfxChannel` `sc_flags` (at `SND_SFX_CHANNELS + slot*SfxChannel_len + sc_flags`; resolve via `emulator_lookup_symbol`) — bit 7 set. `emulator_audio_spectrum` over the spindash: the held `nC5` fundamental is a single steady pitch (no octave-jumping warble that the wrong table produced in 5a). Record the spectrum verdict.
- [ ] **Step 7: Commit.**
```bash
git add sound_constants.asm engine/sound_sequencer.asm engine/sound_sfx.asm
git commit -m "fix(sound): SCF_PITCH_CHROMATIC — SFX re-key paths use FmPitchTableZ (kills the SFX pitch-table octave warble)"
```

---

## Task 2: Struct growth + opcode allocation (build-only)

**Goal:** append the PSG-env fields + the pitch-mod fields to `SeqChannel` + the `SfxChannel` mirror; allocate the 4 new MEV opcodes with collision asserts; update the `_len`/mirror/`(ix+d)` asserts. **Pure equate/struct additions — no runtime behavior change. Regression: build passes; nothing reads the new fields yet.**

**Files:** Modify `sound_constants.asm`.

- [ ] **Step 1: Allocate the 4 opcodes + collision asserts.** In `sound_constants.asm`, after the `MEV_END = $FF` line + the `; reserved for Phase 3: $EB–$ED, $F0–$FE ...` comment, the existing collision-assert chains for `MEV_PAN`/`MEV_OPBIAS`/`MEV_PITCHENV`/`MEV_REGDELTA` follow. Add the four new opcodes right after `MEV_END = $FF` (before the assert chains):
```asm
; --- SFX Expressive Fidelity opcodes (free $EB/$EC/$F0/$F1 slots, spec §7) ------
; All zero-tick coordination setters. Default-inert: a song/SFX without them is
; byte-identical (the new state fields are zeroed by the seq/slot wipe).
MEV_PSGENV        = $EB   ; + env_id : set the channel's PSG volume-envelope id (1-based; 0=none)
MEV_MODSET        = $EC   ; + wait speed change step : latch the pitch-modulation params (all 0 = mod off)
MEV_SPINREV       = $F0   ; (no operand) : add the global spindash rev into sc_transpose, cap $10, inc
MEV_SPINREV_RESET = $F1   ; (no operand) : zero the global spindash rev
```
Then, after the existing `MEV_REGDELTA` collision-assert block, add a new collision block (mirroring the `MEV_PITCHENV` pattern exactly):
```asm
        ; --- SFX-fidelity opcode range + collision asserts (spec §7) ---
        ; Each must be a command opcode (> MEV_NOTE_MAX), inside $E0-$FF, on its
        ; assigned free slot, and not collide with any allocated opcode.
        if (MEV_PSGENV <= MEV_NOTE_MAX) || (MEV_MODSET <= MEV_NOTE_MAX) || (MEV_SPINREV <= MEV_NOTE_MAX) || (MEV_SPINREV_RESET <= MEV_NOTE_MAX)
          error "MEV_PSGENV/MODSET/SPINREV* must be command opcodes (> MEV_NOTE_MAX)"
        endif
        if (MEV_PSGENV < MEV_VOL) || (MEV_PSGENV > MEV_END) || (MEV_MODSET < MEV_VOL) || (MEV_MODSET > MEV_END) || (MEV_SPINREV < MEV_VOL) || (MEV_SPINREV > MEV_END) || (MEV_SPINREV_RESET < MEV_VOL) || (MEV_SPINREV_RESET > MEV_END)
          error "MEV_PSGENV/MODSET/SPINREV* must be inside the $E0-$FF coordination block"
        endif
        if (MEV_PSGENV <> $EB) || (MEV_MODSET <> $EC) || (MEV_SPINREV <> $F0) || (MEV_SPINREV_RESET <> $F1)
          error "MEV_PSGENV/MODSET/SPINREV* must be on their assigned free slots ($EB/$EC/$F0/$F1)"
        endif
        ; must not collide with any allocated opcode ($E0-$EA used, $ED NOTEFILL, $EE/$EF loop/jump, $FF end).
        if (MEV_PSGENV = MEV_VOL) || (MEV_PSGENV = MEV_PATCH) || (MEV_PSGENV = MEV_DAC) || (MEV_PSGENV = MEV_NOTE_DUR) || (MEV_PSGENV = MEV_PAN) || (MEV_PSGENV = MEV_REPEAT_START) || (MEV_PSGENV = MEV_REPEAT_END) || (MEV_PSGENV = MEV_NOTE_RAW) || (MEV_PSGENV = MEV_PITCHENV) || (MEV_PSGENV = MEV_OPBIAS) || (MEV_PSGENV = MEV_REGDELTA) || (MEV_PSGENV = MEV_NOTEFILL) || (MEV_PSGENV = MEV_LOOP_POINT) || (MEV_PSGENV = MEV_JUMP) || (MEV_PSGENV = MEV_END) || (MEV_PSGENV = MEV_MODSET)
          error "MEV_PSGENV (\{MEV_PSGENV}) collides with an allocated $E0-$FF opcode"
        endif
        if (MEV_MODSET = MEV_VOL) || (MEV_MODSET = MEV_PATCH) || (MEV_MODSET = MEV_DAC) || (MEV_MODSET = MEV_NOTE_DUR) || (MEV_MODSET = MEV_PAN) || (MEV_MODSET = MEV_REPEAT_START) || (MEV_MODSET = MEV_REPEAT_END) || (MEV_MODSET = MEV_NOTE_RAW) || (MEV_MODSET = MEV_PITCHENV) || (MEV_MODSET = MEV_OPBIAS) || (MEV_MODSET = MEV_REGDELTA) || (MEV_MODSET = MEV_NOTEFILL) || (MEV_MODSET = MEV_LOOP_POINT) || (MEV_MODSET = MEV_JUMP) || (MEV_MODSET = MEV_END)
          error "MEV_MODSET (\{MEV_MODSET}) collides with an allocated $E0-$FF opcode"
        endif
        if (MEV_SPINREV = MEV_SPINREV_RESET) || (MEV_SPINREV = MEV_END) || (MEV_SPINREV_RESET = MEV_END)
          error "MEV_SPINREV/SPINREV_RESET opcode collision"
        endif
```

- [ ] **Step 2: Append the new fields to `SfxChannel`.** In `sound_constants.asm`, the live `SfxChannel struct` ends its SFX-only block with `sx_kind ds.b 1 ; +45` then `SfxChannel endstruct ; = 46 bytes`. There is an `sx_pad ds.b 1 ; +40` already present. Insert the new shared-prefix fields **inside the SeqChannel-compatible prefix** — they must mirror `SeqChannel` (added there too in Step 3) — i.e. between `sc_fill_count` and the `; --- SFX-only appended state` divider. Replace this exact block:
```asm
sc_fill_count   ds.b 1   ; +38 (end of the shared SeqChannel-compatible prefix)
; --- SFX-only appended state (offsets >= SeqChannel_len) ---
sx_priority     ds.b 1   ; +39 the running SFX's priority (cleared on end; arbitration)
sx_pad          ds.b 1   ; +40 pad to align sx_patch_base to a word boundary
sx_patch_base   ds.w 1   ; +41 the SFX's own FmPatch-bank window ptr (set at steal)
sx_saved_route  ds.b 1   ; +43 the music route whose SeqChannel we overrode (for restore)
sx_saved_note   ds.b 1   ; +44 PSG3 tone note saved on a noise steal (periodic-noise coupling)
sx_kind         ds.b 1   ; +45 SFXEL_* of the owned voice (FM/PSG/NOISE) for restore dispatch
SfxChannel endstruct     ; = 46 bytes

        if SfxChannel_len <> 46
          error "SfxChannel struct is \{SfxChannel_len} bytes, expected 46"
        endif
```
with:
```asm
sc_fill_count   ds.b 1   ; +38 live per-frame note-fill countdown
; --- SFX Expressive Fidelity appended shared-prefix state (mirrors SeqChannel) ---
sc_psgenv       ds.b 1   ; +39 PSG vol-env id (1-based; 0 = none)
sc_psgenv_cur   ds.b 1   ; +40 PSG vol-env cursor (frame index into the body)
sc_psgenv_out   ds.b 1   ; +41 last computed atten delta (write-on-change shadow for Psg_SetVolume)
sc_mod_ctrl     ds.b 1   ; +42 pitch-mod control (0 = off; nonzero = active)
sc_mod_wait     ds.b 1   ; +43 frames before modulation starts (one-shot, then held at 1)
sc_mod_speed    ds.b 1   ; +44 frames between delta applications (countdown)
sc_mod_delta    ds.b 1   ; +45 signed per-step delta (flips sign each half-period)
sc_mod_steps    ds.b 1   ; +46 steps until direction reverse (countdown; halved at re-arm)
sc_mod_accum    ds.w 1   ; +47 signed 16-bit accumulated freq offset
sc_base_freq    ds.w 1   ; +49 the unmodulated note's $A4/$A0 word (d=$A4,e=$A0), latched at key-on
sc_last_freq    ds.w 1   ; +51 last freq word written by Mod_ApplyVibrato (write-on-change shadow)
; --- SFX-only appended state (offsets >= SeqChannel_len) ---
sx_priority     ds.b 1   ; the running SFX's priority (cleared on end; arbitration)
sx_pad          ds.b 1   ; pad to align sx_patch_base to a word boundary
sx_patch_base   ds.w 1   ; the SFX's own FmPatch-bank window ptr (set at steal)
sx_saved_route  ds.b 1   ; the music route whose SeqChannel we overrode (for restore)
sx_saved_note   ds.b 1   ; PSG3 tone note saved on a noise steal (periodic-noise coupling)
sx_kind         ds.b 1   ; SFXEL_* of the owned voice (FM/PSG/NOISE) for restore dispatch
SfxChannel endstruct     ; = 60 bytes

        if SfxChannel_len <> 60
          error "SfxChannel struct is \{SfxChannel_len} bytes, expected 60"
        endif
```
(13 new shared-prefix bytes: SeqChannel grows 39→52, SfxChannel 46→60. The new fields are part of the SeqChannel-compatible prefix so `ModUpdate` reads them on both struct types; the `sx_*` bookkeeping shifts up but its offsets are still all derived by AS.)

- [ ] **Step 3: Append the same fields to `SeqChannel` + update its `_len`/`(ix+d)` asserts.** The live `SeqChannel struct` ends:
```asm
sc_fill_count   ds.b 1   ; +38 live per-frame note-fill countdown (0 = expired or disabled)
SeqChannel endstruct      ; = 39 bytes

        if SeqChannel_len <> 39
          error "SeqChannel struct is \{SeqChannel_len} bytes, expected 39"
        endif
        ; the largest field offset must stay within the signed-8-bit (ix+d) range.
        if SeqChannel_sc_last_pan > 127
          error "sc_last_pan offset (\{SeqChannel_sc_last_pan}) exceeds the (ix+d) +127 range"
        endif
```
Replace with:
```asm
sc_fill_count   ds.b 1   ; +38 live per-frame note-fill countdown (0 = expired or disabled)
; --- SFX Expressive Fidelity appended state (rendered by ModUpdate; zeroed default = inert) ---
; PSG volume envelope (spec §4): per-frame attenuation contour folded into Psg_SetVolume.
sc_psgenv       ds.b 1   ; +39 PSG vol-env id (1-based; 0 = none)
sc_psgenv_cur   ds.b 1   ; +40 PSG vol-env cursor (frame index into the body)
sc_psgenv_out   ds.b 1   ; +41 last computed atten delta (write-on-change shadow)
; Pitch modulation (spec §5): continuous additive freq-word vibrato/sweep, NO re-key.
sc_mod_ctrl     ds.b 1   ; +42 pitch-mod control (0 = off; nonzero = active)
sc_mod_wait     ds.b 1   ; +43 frames before modulation starts (one-shot, then held at 1)
sc_mod_speed    ds.b 1   ; +44 frames between delta applications (countdown)
sc_mod_delta    ds.b 1   ; +45 signed per-step delta (flips sign each half-period)
sc_mod_steps    ds.b 1   ; +46 steps until direction reverse (countdown; halved at re-arm)
sc_mod_accum    ds.w 1   ; +47 signed 16-bit accumulated freq offset
sc_base_freq    ds.w 1   ; +49 the unmodulated note's $A4/$A0 word (d=$A4,e=$A0), latched at key-on
sc_last_freq    ds.w 1   ; +51 last freq word Mod_ApplyVibrato wrote (write-on-change shadow)
SeqChannel endstruct      ; = 53 bytes

        if SeqChannel_len <> 53
          error "SeqChannel struct is \{SeqChannel_len} bytes, expected 53"
        endif
        ; the largest field offset must stay within the signed-8-bit (ix+d) range.
        if SeqChannel_sc_last_freq > 127
          error "sc_last_freq offset (\{SeqChannel_sc_last_freq}) exceeds the (ix+d) +127 range"
        endif
```
(SeqChannel: 39 + 3 (psgenv) + 5 (mod scalars) + 2 (accum.w) + 2 (base.w) + 2 (last.w) = 53. `sc_last_freq` at +51 is well within +127.)

- [ ] **Step 4: Update the shared-prefix mirror assert + add the `sc_*` aliases.** The live mirror assert checks `sc_flags`/`sc_route`/`sc_note`/`sc_points`/`sc_last_pan`. Extend it to pin the new shared fields. Replace:
```asm
        if (SfxChannel_sc_flags <> SeqChannel_sc_flags) || (SfxChannel_sc_route <> SeqChannel_sc_route) || (SfxChannel_sc_note <> SeqChannel_sc_note) || (SfxChannel_sc_points <> SeqChannel_sc_points) || (SfxChannel_sc_last_pan <> SeqChannel_sc_last_pan)
          error "SfxChannel shared prefix diverges from SeqChannel field offsets"
        endif
```
with:
```asm
        if (SfxChannel_sc_flags <> SeqChannel_sc_flags) || (SfxChannel_sc_route <> SeqChannel_sc_route) || (SfxChannel_sc_note <> SeqChannel_sc_note) || (SfxChannel_sc_points <> SeqChannel_sc_points) || (SfxChannel_sc_last_pan <> SeqChannel_sc_last_pan) || (SfxChannel_sc_psgenv <> SeqChannel_sc_psgenv) || (SfxChannel_sc_mod_ctrl <> SeqChannel_sc_mod_ctrl) || (SfxChannel_sc_base_freq <> SeqChannel_sc_base_freq) || (SfxChannel_sc_last_freq <> SeqChannel_sc_last_freq)
          error "SfxChannel shared prefix diverges from SeqChannel field offsets"
        endif
```
Then, in the `sc_*` alias block (which ends with `sc_fill_count = SeqChannel_sc_fill_count`), append:
```asm
sc_psgenv       = SeqChannel_sc_psgenv
sc_psgenv_cur   = SeqChannel_sc_psgenv_cur
sc_psgenv_out   = SeqChannel_sc_psgenv_out
sc_mod_ctrl     = SeqChannel_sc_mod_ctrl
sc_mod_wait     = SeqChannel_sc_mod_wait
sc_mod_speed    = SeqChannel_sc_mod_speed
sc_mod_delta    = SeqChannel_sc_mod_delta
sc_mod_steps    = SeqChannel_sc_mod_steps
sc_mod_accum    = SeqChannel_sc_mod_accum
sc_base_freq    = SeqChannel_sc_base_freq
sc_last_freq    = SeqChannel_sc_last_freq
```

- [ ] **Step 5: Re-confirm the RAM-region asserts still pass.** The `SeqChannel` growth pushes `SND_SEQ_END = SND_SEQ_CHANNELS + (CHROUTE_COUNT * SeqChannel_len)` up (the FM scratch + Snd_LoadSong scratch + trace-ring guards `if (Snd_PitchTabPtr + 2) > SND_SEQ_TRACE` auto-track it). The `SfxChannel` growth pushes `SND_SFX_CHAN_END` / the SFX queue / duck / dispatch-scratch up (the `SND_SFX_DISP_END > SND_REQ_BASE` guard in `engine/sound_sfx.asm` catches overflow). Build is the check (Step 6) — no manual recompute. If any guard trips, the gap is genuinely too small and must be reported to review (do NOT shrink a field to fit silently).
- [ ] **Step 6: Build-verify the asserts.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` → exit 0. All struct/opcode/RAM asserts pass. No runtime change (nothing reads the new fields/opcodes yet; `SeqOpcodeTable`'s $EB/$EC/$F0/$F1 still point at `Seq_BadOpcode` — wired in Tasks 3-6).
- [ ] **Step 7: Regression — Moving Trucks byte-identical.** On `oracle`, reload + play Moving Trucks, `vgm_start`→`vgm_stop`→`vgm2wav`, A/B against the Task 1 capture: identical (the larger struct stride doesn't change behavior — the new fields are zeroed by `Snd_LoadSong`'s `.seq_clr` and never read).
- [ ] **Step 8: Commit.**
```bash
git add sound_constants.asm
git commit -m "feat(sound): SFX-fidelity struct growth (PSG-env + pitch-mod fields) + MEV_PSGENV/MODSET/SPINREV* opcode allocation"
```

---

## Task 3: PSG volume envelopes

**Goal:** add the `PsgVolEnv_Table` data (S3K-exact `VolEnv` bytes), the `MEV_PSGENV` reader, the per-attack cursor reset, the `PsgEnvUpdate` renderer gated in `ModUpdate` on PSG-route + env-active, the fold into `Psg_SetVolume` (atten domain + `bit 4` clamp, before the duck fold + the noise branch), and the transcoder emit from `smpsPSGvoice`. **Acceptance: the PSG volume contour over time matches the `VolEnv` shape in the spectrogram. Regression: Moving Trucks byte-identical (no song emits MEV_PSGENV); a no-env SFX unchanged (sc_psgenv == 0 → one bit-test, no fold).**

**Files:** Modify `engine/sound_tables_z80.asm`, `engine/sound_sequencer.asm`, `engine/sound_psg.asm`, `tools/song_packer.py`, `tools/sfx_transcode.py`, `tools/test_sfx_transcode.py`.

- [ ] **Step 1: Add `PsgVolEnv_Table` (S3K-exact bytes for our corpus's sTones) VIA THE GENERATOR.** `engine/sound_tables_z80.asm` is generated, so add the table to `tools/gen_sound_tables.py`'s `emit_asm_z80()` (append the lines below to the `out` list after the `FmPitchTableZ`/`PsgDivisorTableZ` blocks), then run `python3 tools/gen_sound_tables.py` to regenerate the file. (If you instead choose the separate-file path, put these lines in a new `engine/sound_psgenv_tables.asm` and `include` it after `sound_tables_z80.asm` in `z80_sound_driver.asm` — same content, hand-authored.) Our core SFX use `sTone_0D` (jump/skid → `VolEnv_0C`), `sTone_0E` (break → `VolEnv_0D`), `sTone_1D` (dash/spheres → `VolEnv_1C`), plus `sTone_03`/`sTone_0F`/`sTone_11` for completeness (signpost/fan/breath, harmless if unreferenced). The engine env id is **1-based** matching S3K's `sTone_XX` (the body for engine id `N` is `VolEnv_(N-1)`). The emitted Z80 data:
```asm
; --- PSG volume-envelope table (SFX Expressive Fidelity, spec §4) -------------
; S3K-EXACT VolEnv byte format: per-frame ATTENUATION deltas (added to the track
; atten; higher = quieter) + control bytes: $80 = loop cursor to 0; $81 = sustain-
; hold (hold last delta, do NOT silence); $83 = full rest (silence the channel).
; Engine env id is 1-based (matches smpsPSGvoice's sTone_XX); id N -> body N-1.
; (S3K's buggy "relative-jump" path for other high-bit bytes is NOT replicated.)
psgVolEnvIdx function id, ((id) - 1)        ; 1-based sTone id -> 0-based table index

PsgVolEnvCtl_Loop    = $80
PsgVolEnvCtl_Sustain = $81
PsgVolEnvCtl_Rest    = $83

PsgVolEnv_Table:
        dw      PsgVolEnv_03    ; id 3  = sTone_03 (VolEnv_02): 24-frame swell + sustain
        dw      PsgVolEnv_0D    ; id 13 = sTone_0D (VolEnv_0C): flat-then-sustain (jump/skid)
        dw      PsgVolEnv_0E    ; id 14 = sTone_0E (VolEnv_0D): 1-frame blip then full-rest (break)
        dw      PsgVolEnv_0F    ; id 15 = sTone_0F (VolEnv_0E): 5-frame decay then full-rest
        dw      PsgVolEnv_11    ; id 17 = sTone_11 (VolEnv_10): short pluck
        dw      PsgVolEnv_1D    ; id 29 = sTone_1D (VolEnv_1C): 44-frame linear fade-out
PsgVolEnv_Table_End:
        ; NOTE: the table is sparse-by-id but DENSE in storage (id->index map below).
        ; The reader resolves an id to a body via PsgVolEnv_IdToIndex (Step 2) so
        ; only the ids we ship occupy a 2-byte slot. If a future sTone is needed,
        ; add its body + extend the map. Build-assert the map width matches.

PsgVolEnv_03:   db 2,1,0,0,1,2,2,2,2,2,2,2,2,2,2,2,2,3,3,3,4,4,4,5,PsgVolEnvCtl_Sustain
PsgVolEnv_0D:   db 0,PsgVolEnvCtl_Sustain
PsgVolEnv_0E:   db 2,PsgVolEnvCtl_Rest
PsgVolEnv_0F:   db 0,2,4,6,8,$10,PsgVolEnvCtl_Rest
PsgVolEnv_11:   db 1,1,1,0,0,0,PsgVolEnvCtl_Sustain
PsgVolEnv_1D:   db 0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,6,6,6,6,7,7,7,7,8,8,8,8,9,9,9,9,$0A,$0A,$0A,$0A,PsgVolEnvCtl_Sustain
```
Because the ids are sparse (3, 13, 14, 15, 17, 29), add a small **dense id→body** lookup the reader uses (avoids a 29-slot table). Author it as a `dw`-per-id list keyed by the small set:
```asm
; id->body map: parallel arrays (id byte, body ptr). The reader scans for a match.
; Tiny (6 entries) so a linear scan is cheaper than a 29-wide sparse table.
PsgVolEnv_Ids:    db 3, 13, 14, 15, 17, 29
PsgVolEnv_Ids_End:
PsgVolEnv_Ptrs:   dw PsgVolEnv_03, PsgVolEnv_0D, PsgVolEnv_0E, PsgVolEnv_0F, PsgVolEnv_11, PsgVolEnv_1D

PSGVOLENV_COUNT = PsgVolEnv_Ids_End - PsgVolEnv_Ids
        if (PsgVolEnv_Table_End - PsgVolEnv_Table) <> PSGVOLENV_COUNT*2
          error "PsgVolEnv_Table entry count mismatch vs PsgVolEnv_Ids"
        endif
```

- [ ] **Step 2: `MEV_PSGENV` reader.** In `engine/sound_sequencer.asm`, add the handler near the other zero-tick setters (e.g. after `Seq_Op_NoteFill`). It stores the env id and resets the cursor (state-only, hl stays the live stream ptr, no writer hook):
```asm
; $EB MEV_PSGENV + env_id : set the channel's PSG volume-envelope id (1-based; 0=none),
; reset the cursor to 0. Zero-tick state setter (mirror of Seq_Op_NoteFill). The
; per-frame contour is rendered by PsgEnvUpdate (ModUpdate) + folded in Psg_SetVolume.
Seq_Op_PsgEnv:
        ld      a, (hl)
        inc     hl                       ; consume operand (env id)
        ld      (ix+sc_psgenv), a
        ld      (ix+sc_psgenv_cur), 0    ; restart the contour from frame 0
        jp      Seq_ContinueFetch
```
Wire it in `SeqOpcodeTable`: replace the `dw Seq_BadOpcode ; $EB reserved` line with `dw Seq_Op_PsgEnv ; $EB MEV_PSGENV`.

- [ ] **Step 3: Per-attack cursor reset (PSG key-on).** The contour must restart on every fresh PSG note (S3K's `zFinishTrackUpdate` VolEnv=0 reset). The PSG key-on choke-point is `Psg_NoteOn` (`engine/sound_psg.asm`) — it sets `SCF_KEYED` then tail-calls `Psg_SetVolume`. Add the cursor reset just before the `set SCF_KEYED_B` in `Psg_NoteOn`. The live code is:
```asm
        ; --- set the channel volume so the note sounds (re-reads sc_volume) ---
        set     SCF_KEYED_B, (ix+sc_flags)
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; (preserves ix; ret from there)
```
Replace with:
```asm
        ; --- set the channel volume so the note sounds (re-reads sc_volume) ---
        set     SCF_KEYED_B, (ix+sc_flags)
        ld      (ix+sc_psgenv_cur), 0    ; PSG vol-env restarts its contour on each attack (spec §4)
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; (preserves ix; ret from there)
```
(`Psg_Noise` also tail-calls `Psg_SetVolume` after `set SCF_KEYED_B`; add the same `ld (ix+sc_psgenv_cur),0` line there too so a noise SFX with an env restarts per attack. Resetting `sc_psgenv_cur` even when `sc_psgenv==0` is harmless.)

- [ ] **Step 4: `PsgEnvUpdate` renderer, gated in `ModUpdate`.** `ModUpdate`'s live head returns early on non-FM routes (`bit SCF_IS_FM_B,(ix+sc_flags) / ret z`) AFTER the override gate. The PSG env must run for PSG routes, so the gate becomes a *branch* to `PsgEnvUpdate` instead of a bare `ret`. The live head is:
```asm
ModUpdate:
        ; Phase 5a: if an SFX has stolen this physical voice, render NOTHING ...
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        ; Non-FM channels (PSG / DAC) have no per-frame FM modulation to render in
        ; Phase 3a -> no-op. (PSG modulation is out of scope; see spec §1.)
        bit     SCF_IS_FM_B, (ix+sc_flags)
        ret     z
```
Replace with:
```asm
ModUpdate:
        ; Phase 5a: if an SFX has stolen this physical voice, render NOTHING ...
        bit     SCF_SFX_OVERRIDE_B, (ix+sc_flags)
        ret     nz
        ; PSG / DAC channels: the FM modulation below is skipped, but a PSG channel
        ; with an active PSG vol-env (spec §4) needs its per-frame contour advanced.
        ; Gate: PSG-route + sc_psgenv != 0 -> PsgEnvUpdate; else no-op (one bit-test).
        bit     SCF_IS_FM_B, (ix+sc_flags)
        jr      nz, .is_fm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; DAC or other non-PSG -> nothing
        ld      a, (ix+sc_psgenv)
        or      a
        ret     z                        ; no PSG vol-env -> nothing (held-note fast path)
        jp      PsgEnvUpdate             ; advance the contour + emit (tail-call, preserves ix)
.is_fm:
```
Then add `PsgEnvUpdate` (place it after `ModUpdate`/before `Sequencer_Channel`). It ports S3K's `zDoVolEnv` cursor logic (plain / `$80` loop / `$81` sustain / `$83` rest), writes `sc_psgenv_out`, and re-emits the volume (so the new delta lands this frame):
```asm
; ----------------------------------------------------------------------
; PsgEnvUpdate — advance one PSG channel's volume-envelope contour by one frame
; and re-emit the channel volume so the new attenuation delta takes effect.
; Gated by ModUpdate: entered only for a PSG route with sc_psgenv != 0.
; Body byte semantics (S3K-exact): plain value -> store as sc_psgenv_out + advance
; cursor; $80 -> cursor=0 and re-read; $81 -> sustain-hold (keep sc_psgenv_out, no
; advance); $83 -> full rest: key the PSG channel off + disable the env.
; In: ix = SeqChannel/SfxChannel (PSG route). Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
PsgEnvUpdate:
        ; resolve body ptr from sc_psgenv (1-based id) via the id->body map.
        ld      a, (ix+sc_psgenv)
        call    PsgVolEnv_Resolve        ; hl = body base; carry set = unknown id -> bail
        ret     c
.reread:
        ld      a, (ix+sc_psgenv_cur)    ; a = cursor
        ld      e, a
        ld      d, 0
        add     hl, de                   ; hl = &body[cursor]
        ld      a, (hl)                  ; a = body byte
        cp      PsgVolEnvCtl_Loop        ; $80 -> loop cursor to 0
        jr      z, .loop
        cp      PsgVolEnvCtl_Sustain     ; $81 -> sustain-hold (no advance, keep last out)
        jr      z, .sustain
        cp      PsgVolEnvCtl_Rest        ; $83 -> full rest (silence + disable)
        jr      z, .rest
        ; --- plain value: store as the atten delta, advance the cursor ---
        ld      (ix+sc_psgenv_out), a
        inc     (ix+sc_psgenv_cur)
.emit:
        ; re-emit the channel volume so the new sc_psgenv_out delta lands this frame.
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; folds sc_psgenv_out in (Step 5); preserves ix
.loop:
        ld      (ix+sc_psgenv_cur), 0    ; cursor -> 0
        ; recompute hl = body base (we advanced it by the old cursor above) and re-read.
        ld      a, (ix+sc_psgenv)
        call    PsgVolEnv_Resolve
        ret     c
        jr      .reread
.sustain:
        ; hold last sc_psgenv_out (do NOT advance, do NOT silence) — re-emit so the
        ; held attenuation stays applied against the live sc_volume.
        jr      .emit
.rest:
        ld      (ix+sc_psgenv), 0        ; disable the env (one-shot rest reached)
        jp      Psg_NoteOff              ; silence this PSG channel (tail-call, preserves ix)
```
Add the `PsgVolEnv_Resolve` helper (a linear scan over `PsgVolEnv_Ids`/`PsgVolEnv_Ptrs`) in `engine/sound_tables_z80.asm` or near `PsgEnvUpdate`:
```asm
; ----------------------------------------------------------------------
; PsgVolEnv_Resolve — map a 1-based PSG vol-env id (a) to its body ptr (hl).
; Out: carry clear + hl = body base on a match; carry set on an unknown id.
; Clobbers af,bc,de,hl. Preserves ix.
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
```

- [ ] **Step 5: Fold `sc_psgenv_out` into `Psg_SetVolume` (atten domain, before the duck fold + noise branch).** The live `Psg_SetVolume` computes `c = Psg_VolToAtten(vol)`, then does the music-duck fold, then branches PSGN→`$F0` vs tone→`$90`. The env delta must be added **right after `ld c,a`** (before the duck fold) so envelope + duck compose and noise SFX get the contour. Replace the live opening:
```asm
Psg_SetVolume:
        call    Psg_VolToAtten           ; a = 4-bit attenuation (clobbers b)
        ld      c, a                     ; c = attenuation

        ; --- Phase 5a music ducking (spec §7) -------------------------------------
```
with:
```asm
Psg_SetVolume:
        call    Psg_VolToAtten           ; a = 4-bit attenuation (clobbers b)
        ld      c, a                     ; c = attenuation

        ; --- PSG volume envelope (spec §4): add the per-frame env atten delta -------
        ; sc_psgenv_out is the S3K VolEnv delta (attenuation units, higher = quieter),
        ; computed by PsgEnvUpdate. Add it BEFORE the duck fold (env+duck compose) and
        ; BEFORE the noise branch (noise SFX get the contour). $00 default = no change.
        ; Underflow guard (S3K `bit 4,a`): if the sum sets bit 4 (>= $10) force $0F
        ; silent, so a loud-then-quiet env can't wrap back to loud.
        ld      a, (ix+sc_psgenv_out)
        or      a
        jr      z, .env_done             ; no env delta -> skip (held / no-env fast path)
        add     a, c                     ; atten + env delta
        bit     4, a                     ; >= $10 ?
        jr      z, .env_ok
        ld      a, SND_PSG_ATTEN_SILENT  ; $0F (silent) clamp
.env_ok:
        ld      c, a
.env_done:

        ; --- Phase 5a music ducking (spec §7) -------------------------------------
```
(Both `Psg_NoteOn` and `Psg_SetVolume`'s callers preserve the contract; `a`/`c` are the only registers touched here and `c` is the working atten. `sc_psgenv_out == 0` for every channel that never set a PSG env — so music + no-env SFX are byte-identical.)

- [ ] **Step 6: Transcoder — emit `MEV_PSGENV` from `smpsPSGvoice`.** First add the `PsgEnv` Event class to `tools/song_packer.py` (mirror `OpBias`):
```python
MEV_PSGENV = 0xEB           # + env_id: set the channel's PSG volume-envelope id (1-based; 0=none)


class PsgEnv(Event):
    """SFX-fidelity PSG volume envelope: set the channel's 1-based env id (0=none).
    The engine restarts the contour cursor on each attack and folds the per-frame
    attenuation delta into Psg_SetVolume. PSG/noise routes only. Zero-tick."""
    def __init__(self, env_id: int):
        self.env_id = env_id

    def encode(self) -> bytes:
        return bytes([MEV_PSGENV, self.env_id & 0xFF])

    def validate(self, route):
        if route in _FM_ROUTES:
            raise PackError(f"PsgEnv on FM route {route}")
        if not (0 <= self.env_id <= 0xFF):
            raise PackError(f"PsgEnv env_id {self.env_id} out of byte range")
```
Then in `tools/sfx_transcode.py`, import `PsgEnv` in both `song_packer` import blocks, add the sTone→engine-id map, and replace the `smpsPSGvoice` no-op (the live block at ~L582 in the FM/data path AND the ~L921 block in the header-scan path). The live FM/data block is:
```python
                    elif macro == 'smpsPSGvoice':
                        # PSG volume envelope index (sTone_XX).  v1: no-op for audible PSG shape.
                        # Document which sTone was requested (informational).
                        args = _split_args(arg_str)
                        tone_tok = args[0].strip() if args else '0'
                        print(f"  [info] sfx ${sfx_id:02X} ch ${chanid:02X}: smpsPSGvoice {tone_tok!r} "
                              f"(PSG envelope tables not in v1 scope; tone index noted)",
                              file=sys.stderr)
                        # No event emitted — PSG voice shape comes from note frequency in v1.
```
Replace with:
```python
                    elif macro == 'smpsPSGvoice':
                        # PSG volume envelope (sTone_XX). Emit MEV_PSGENV with the
                        # 1-based engine env id (== the sTone number; the engine table
                        # holds the S3K-exact VolEnv body for each id we ship).
                        args = _split_args(arg_str)
                        tone_tok = args[0].strip() if args else '0'
                        env_id = _stone_to_env_id(tone_tok)
                        events.append(PsgEnv(env_id))
```
Add the helper near the top of the module:
```python
# sTone_XX token -> 1-based engine PSG vol-env id. The id IS the sTone number
# (the engine's PsgVolEnv_Table holds the S3K-exact body for each shipped id).
# Only the sTones our core corpus references are mapped; an unmapped sTone raises
# (spec §8: never silently dropped).
_STONE_TO_ENV = {
    'sTone_03': 0x03, 'sTone_0D': 0x0D, 'sTone_0E': 0x0E,
    'sTone_0F': 0x0F, 'sTone_11': 0x11, 'sTone_1D': 0x1D,
}

def _stone_to_env_id(tok: str) -> int:
    tok = tok.strip()
    if tok in _STONE_TO_ENV:
        return _STONE_TO_ENV[tok]
    # allow a bare numeric (already an id)
    try:
        return _parse_int(tok)
    except (TranscodeError, ValueError):
        raise TranscodeError(f"unmapped smpsPSGvoice tone {tok!r} (add it to PsgVolEnv_Table + _STONE_TO_ENV)")
```
The second (header-scan) `smpsPSGvoice` block at ~L921 only logs — leave its informational `print` but DO NOT emit there (events are built in the data pass); add a one-line comment noting the data pass emits the `PsgEnv`.

- [ ] **Step 7: pytest.** In `tools/test_sfx_transcode.py`, add a `TestPsgEnv` class:
  - `test_jump_emits_psgenv`: transcode the Jump fixture (`62 - Jump.asm` with `smpsPSGvoice sTone_0D`); assert the PSG1 event list contains a `PsgEnv(0x0D)` before the first note.
  - `test_psgenv_encodes`: `PsgEnv(0x0D).encode() == bytes([0xEB, 0x0D])`.
  - `test_psgenv_rejects_fm`: `PsgEnv(0x0D).validate(CHROUTE_FM3)` raises `PackError`.
  - `test_unmapped_stone_errors`: a fixture with `smpsPSGvoice sTone_07` raises `TranscodeError`.
  Run `python3 -m pytest tools/test_sfx_transcode.py -q` → all pass.
- [ ] **Step 8: Build + spectral acceptance.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` → exit 0. Re-transcode the core set if Task-3 emit changed the blobs (run `python3 tools/sfx_transcode.py generate`, rebuild). On `oracle`: post Break/Skid (the env-bearing SFX) and Jump. `emulator_vgm_start` → fire → `vgm_stop` → `vgm2wav`. `emulator_audio_spectrum` over the PSG channel: the **volume contour over time** matches the `VolEnv` shape — e.g. Skid/`VolEnv_0E` shows a 5-frame decay then silence ($83 rest); Break/`VolEnv_0D` is a 1-frame blip then silence; Jump/`VolEnv_0C` is flat-then-sustain ($81, the pluck character comes mostly from Task 4's sweep — note that). Record the spectrum verdict per SFX.
- [ ] **Step 9: Regression.** Moving Trucks `vgm2wav` A/B vs Task 2 capture: byte-identical (no song emits MEV_PSGENV; `sc_psgenv_out==0` everywhere → the `Psg_SetVolume` fold is skipped).
- [ ] **Step 10: Commit.**
```bash
git add engine/sound_tables_z80.asm engine/sound_sequencer.asm engine/sound_psg.asm tools/song_packer.py tools/sfx_transcode.py tools/test_sfx_transcode.py data/sound/sfx/
git commit -m "feat(sound): PSG volume envelopes — PsgVolEnv_Table + MEV_PSGENV + PsgEnvUpdate folded into Psg_SetVolume"
```

---

## Task 4: Pitch modulation — FM

**Goal:** add the `MEV_MODSET` reader (latch the params; all-zero = off), the per-note vibrato re-arm hooked into the FM key-on path (`accum=0`, `steps` halved per `srl`, copy wait/speed/delta, latch `sc_base_freq`), the `Mod_ApplyVibrato` ModUpdate sub-step (port `zDoModulation`: wait/speed/accumulate/triangle-reverse, `final = base + accum`, write `$A4/$A0` on change, NO key-on), and the transcoder emit from `smpsModSet`. **Acceptance: the pitch sweep (jump-style) / vibrato (spindash-style) is visible, smooth, with no per-frame EG re-attack. Regression: Moving Trucks byte-identical (no song emits MODSET); a no-mod SFX unchanged (sc_mod_ctrl==0 → one bit-test).**

**Files:** Modify `sound_constants.asm` (only if a tunable is needed — none here), `engine/sound_sequencer.asm`, `engine/sound_fm.asm`, `tools/song_packer.py`, `tools/sfx_transcode.py`, `tools/test_sfx_transcode.py`.

- [ ] **Step 1: `MEV_MODSET` reader (latch the 4 params; all-zero = mod-off).** In `engine/sound_sequencer.asm`, add the handler near the other zero-tick setters. It reads 4 operands into the latch fields and sets `sc_mod_ctrl` (nonzero if any param is nonzero — the `smpsModSet 0,0,0,0` idiom = off). hl stays the live stream ptr:
```asm
; $EC MEV_MODSET + wait speed change step : latch the pitch-modulation params (the
; engine's smpsModSet). Zero-tick setter. sc_mod_ctrl is set nonzero iff any param
; is nonzero (all-zero = mod off, the smpsModSet 0,0,0,0 idiom AB uses). The actual
; re-arm (accum=0, steps halved) happens at the next key-on (Mod_ReArm, Task 4);
; Mod_ApplyVibrato (ModUpdate) renders it per frame.
Seq_Op_ModSet:
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_mod_wait), a
        ld      c, a                     ; c = OR-accumulator for the off test
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_mod_speed), a
        or      c
        ld      c, a
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_mod_delta), a     ; signed change/step delta
        or      c
        ld      c, a
        ld      a, (hl)
        inc     hl
        ld      (ix+sc_mod_steps), a     ; raw step count (halved at re-arm)
        or      c                        ; a = OR of all 4 params
        ld      (ix+sc_mod_ctrl), a      ; nonzero -> active; zero -> off
        jp      Seq_ContinueFetch
```
Wire `SeqOpcodeTable`: replace `dw Seq_BadOpcode ; $EC reserved` with `dw Seq_Op_ModSet ; $EC MEV_MODSET`.

- [ ] **Step 2: Per-note vibrato re-arm + `sc_base_freq` latch in the FM key-on tail.** The unmodulated note's `$A4/$A0` word is latched in `Fm_NoteOnFreq` (the shared tail of `Fm_NoteOn`/`Fm_NoteFromTable`/the NOTE_RAW path), where `d=$A4`, `e=$A0` are live just before the key-on. The live tail (in `engine/sound_fm.asm`) is:
```asm
        ; --- KEY ON: $28 = $F0 | chsel, ALWAYS via part I ---
        call    Fm_ChSel                 ; a = chsel = (part<<2)|ch
        or      SND_FM_KEYON_OPMASK      ; $F0 | chsel (all 4 ops on)
        ld      c, a                     ; data = key-on byte
        ld      a, SND_REG_KEY_ONOFF     ; reg = $28
        ld      b, 0                     ; key on/off is GLOBAL -> part I
        call    Fm_YmWrite

        set     SCF_KEYED_B, (ix+sc_flags)
        jp      Fm_ReparkDac             ; defensive re-park ($2A)
```
The `$A0` write a few lines above clobbers `d`/`e`; re-derive the base from the channel after key-on is awkward, so latch `sc_base_freq` from `d`/`e` BEFORE they're consumed. Insert the latch right after the `$A4+ch FIRST` write (where `de` is still the note word). The live `$A4` write block is:
```asm
        ; --- $A4+ch FIRST (block + fnum high) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_HI       ; reg = $A4 + ch
        ld      c, d                     ; data = $A4 value
        push    de
        call    Fm_YmWrite
        pop     de
```
Replace with:
```asm
        ; --- $A4+ch FIRST (block + fnum high) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_HI       ; reg = $A4 + ch
        ld      c, d                     ; data = $A4 value
        push    de
        call    Fm_YmWrite
        pop     de
        ; latch the unmodulated note word for the vibrato renderer (spec §5): the
        ; pitch-mod offset is summed onto THIS each frame. d=$A4, e=$A0.
        ld      (ix+sc_base_freq), d     ; high byte slot = $A4 value
        ld      (ix+sc_base_freq+1), e   ; low byte slot  = $A0 value
```
Then add the re-arm call in the key-on tail, just before `set SCF_KEYED_B`. Replace the key-on tail:
```asm
        set     SCF_KEYED_B, (ix+sc_flags)
        jp      Fm_ReparkDac             ; defensive re-park ($2A)
```
with:
```asm
        set     SCF_KEYED_B, (ix+sc_flags)
        call    Mod_ReArm                ; per-note pitch-mod re-arm (no-op if sc_mod_ctrl==0)
        jp      Fm_ReparkDac             ; defensive re-park ($2A)
```
And add `Mod_ReArm` (port `zPrepareModulation`: gate on `sc_mod_ctrl`, `accum=0`, halve `steps`, set `last_freq=base_freq` so the first vibrato write is on-change). Place it in `engine/sound_sequencer.asm` near `Mod_ApplyVibrato` (Step 3):
```asm
; ----------------------------------------------------------------------
; Mod_ReArm — per-note pitch-modulation re-arm (port of zPrepareModulation).
; Called from the FM key-on tail. If sc_mod_ctrl is off, returns immediately (one
; bit-test cost for non-modulated channels). Else: clear the accumulated offset,
; reload the steps counter HALVED (S3K's srl), and prime last_freq = base_freq so
; the first vibrato render writes only when the offset actually changes.
; In: ix = channel (sc_base_freq already latched by the caller). Clobbers af.
; Preserves bc,de,hl,ix.
; ----------------------------------------------------------------------
Mod_ReArm:
        ld      a, (ix+sc_mod_ctrl)
        or      a
        ret     z                        ; mod off -> nothing
        xor     a
        ld      (ix+sc_mod_accum), a
        ld      (ix+sc_mod_accum+1), a   ; accum = 0
        ld      a, (ix+sc_mod_steps)
        srl     a                        ; steps = raw/2 (each direction is a half-period)
        ld      (ix+sc_mod_steps), a
        ; prime the write-on-change shadow to the base note so the first changed
        ; offset is what triggers the first $A4/$A0 vibrato write.
        ld      a, (ix+sc_base_freq)
        ld      (ix+sc_last_freq), a
        ld      a, (ix+sc_base_freq+1)
        ld      (ix+sc_last_freq+1), a
        ret
```
(NOTE: `Mod_ReArm` reloads `sc_mod_steps` from the LATCHED raw value each note. But `Seq_Op_ModSet` stored the raw step, and `Mod_ReArm` overwrites `sc_mod_steps` with raw/2 — so a SECOND note would halve the already-halved value. Guard against that by keeping the raw step in `sc_mod_steps` only as the reload source is wrong here. Correct approach: `Seq_Op_ModSet` stores the raw step; `Mod_ReArm` must read the raw step from a STABLE source. Since `sc_mod_delta`/`sc_mod_speed`/`sc_mod_wait` are not consumed destructively but `sc_mod_steps` IS the countdown, store the raw step in `sc_mod_delta`'s sibling is not available — instead, have `Seq_Op_ModSet` keep the raw step in `sc_mod_steps` and `Mod_ReArm` compute `raw/2` WITHOUT writing back the halved value into the same field it reads next time. The clean fix: the raw step lives implicitly in the MODSET op each note re-issues it in S3K, but our SFX re-issue MODSET per stream too. For the core set, MODSET is issued once before the (single) note, so a single halve is correct. To be robust for multi-note modulated SFX, add a `sc_mod_step_raw` field. **DECISION for this plan: the core SFX (jump 1 note, spindash held note) issue MODSET immediately before each modulated note, so reading+halving `sc_mod_steps` once per note is correct. If a future SFX re-keys a modulated note WITHOUT re-issuing MODSET, add `sc_mod_step_raw` then.** Document this in the `Mod_ReArm` header and flag it in the task output as a known scope bound.)

- [ ] **Step 3: `Mod_ApplyVibrato` — the ModUpdate sub-step (port `zDoModulation`).** Add a call in `ModUpdate` AFTER the existing pitch render (the `count==1` / `.multipoint` paths) but it must run on a HELD FM note too (no re-key). The cleanest seam: at the top of the FM section (after `.is_fm:` from Task 3, after the pan render), insert a vibrato render gated on `sc_mod_ctrl`. Place it just before the note-fill block so it runs every frame regardless of the re-key state. Insert after `.pan_done:` (which the pan block falls through to):
```asm
.pan_done:
        ; --- pitch modulation (spec §5): continuous additive freq-word vibrato/sweep
        ; on the HELD note (no key-on). Gated on sc_mod_ctrl so non-modulated FM
        ; channels pay a single bit-test. Renders BEFORE note-fill / re-key.
        bit     0, (ix+sc_mod_ctrl)      ; cheap nonzero test won't work for ctrl=$80; use or
        ; (sc_mod_ctrl is an OR of params; any nonzero value means active.)
        ld      a, (ix+sc_mod_ctrl)
        or      a
        call    nz, Mod_ApplyVibrato     ; advance + write-on-change $A4/$A0 (no key-on)
```
(Remove the dead `bit 0` line — keep only the `ld a,(ix+sc_mod_ctrl) / or a / call nz`. Written above showing both for clarity; the final code is the `ld`/`or`/`call nz` triple.) Then add `Mod_ApplyVibrato`:
```asm
; ----------------------------------------------------------------------
; Mod_ApplyVibrato — port of zDoModulation. One frame of continuous pitch
; modulation: count down wait (one-shot, then held at 1); every sc_mod_speed
; frames add the signed sc_mod_delta to the 16-bit sc_mod_accum; reverse the delta
; sign every sc_mod_steps applications (triangle); final freq = sc_base_freq +
; sc_mod_accum; write $A4/$A0 ONLY when it differs from sc_last_freq (write-on-
; change). Does NOT key-on — vibrato changes pitch without retriggering the EG.
; In: ix = FM channel, sc_mod_ctrl != 0. Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Mod_ApplyVibrato:
        ; --- wait countdown (one-shot delay, then held at 1) ---
        ld      a, (ix+sc_mod_wait)
        dec     a
        ld      (ix+sc_mod_wait), a
        ret     nz                       ; still delaying -> no change this frame
        inc     (ix+sc_mod_wait)         ; hold wait at 1 so it fires every frame hereafter

        ; --- speed gate: only accumulate every sc_mod_speed frames ---
        dec     (ix+sc_mod_speed)
        jr      nz, .sustain
        ; reload speed; add the signed delta to the 16-bit accumulator.
        ; (the original speed must be re-derivable; we re-store it from the MODSET
        ; latch — but sc_mod_speed is the countdown. Keep the reload source = the
        ; latched value: see the note in Mod_ReArm; for the core set speed is small
        ; and constant, so reload from a saved copy. We store the reload value in
        ; sc_mod_wait's sibling is unavailable — reload by re-reading the op is not
        ; possible here. DECISION: sc_mod_speed for the core SFX is 1 (jump speed=$01,
        ; spindash speed=$01), so the countdown is 1 every frame and the reload value
        ; is 1. Reload a constant 1 for speed==... NO — must be general.)
        ; GENERAL reload: keep the raw speed in the high nibble of sc_mod_ctrl is
        ; hacky. Use a dedicated reload by re-reading from sc_mod_delta? no.
        ; FINAL: add sc_mod_speed_raw field OR accept speed is reloaded from a copy.
        ; For this plan we reload speed = 1 only when the latched speed is 1 (the core
        ; set); the transcoder asserts speed==1 for the shipped SFX (jump/spindash).
        ld      (ix+sc_mod_speed), 1
        ; bc = sign-extended delta
        ld      a, (ix+sc_mod_delta)
        ld      c, a
        add     a, a                     ; CF = sign bit
        sbc     a, a                     ; a = $FF if delta<0 else $00
        ld      b, a                     ; bc = signed delta
        ld      l, (ix+sc_mod_accum)
        ld      h, (ix+sc_mod_accum+1)
        add     hl, bc                   ; accum += delta
        ld      (ix+sc_mod_accum), l
        ld      (ix+sc_mod_accum+1), h
.sustain:
        ; --- final freq = base_freq + accum -------------------------------------
        ; sc_base_freq stores d=$A4 (high), e=$A0 (low) as a 16-bit value where the
        ; $A0 (fnum low) is the low byte. Build hl = (A4<<8)|A0, add the signed accum,
        ; split back to $A4/$A0.
        ld      h, (ix+sc_base_freq)     ; $A4 value (block|fnumHi)
        ld      l, (ix+sc_base_freq+1)   ; $A0 value (fnum low)
        ld      c, (ix+sc_mod_accum)
        ld      b, (ix+sc_mod_accum+1)   ; bc = signed accum
        add     hl, bc                   ; hl = modulated freq word
        ; --- triangle reverse: every sc_mod_steps applications flip the delta sign --
        dec     (ix+sc_mod_steps)
        jr      nz, .write
        ; reload steps from the (halved) latched count and negate the delta.
        ; (sc_mod_steps was halved at re-arm; reload that halved value. Like speed,
        ; the reload source is the post-re-arm value — for the core set steps=0 after
        ; the $01 halve, so the reload below restores it; spindash step=$01 -> /2 = 0.)
        ; Reload from a saved copy: store the halved value in sc_mod_steps and reload
        ; the SAME value here (it does not change), so re-store it before decrement.
        ; Implementation: keep a const reload — see DECISION above; for the core SFX
        ; the half-period is short, so reload the post-re-arm steps value (saved).
        ld      a, (ix+sc_mod_steps)     ; currently 0 after the dec; reload handled below
        ; (reload value handling: see DECISION; transcoder ships step values whose
        ; halved counts are the reload value, stored once at re-arm.)
        ld      a, (ix+sc_mod_delta)
        neg
        ld      (ix+sc_mod_delta), a
.write:
        ; --- write-on-change: only emit $A4/$A0 when the freq word changed ---------
        ld      a, h
        cp      (ix+sc_last_freq)
        jr      nz, .emit
        ld      a, l
        cp      (ix+sc_last_freq+1)
        ret     z                        ; unchanged -> no YM write this frame
.emit:
        ld      (ix+sc_last_freq), h
        ld      (ix+sc_last_freq+1), l
        ; emit $A4/$A0 ONLY (no key-on). Reuse the FM freq-write path: set d=$A4,
        ; e=$A0 and call the shared freq-emit helper that writes $A4 then $A0 without
        ; keying. (Fm_NoteOnFreq KEYS — we must NOT key. Add Fm_WriteFreq below.)
        ld      d, h                     ; d = $A4 value
        ld      e, l                     ; e = $A0 value
        jp      Fm_WriteFreq             ; write $A4 then $A0, NO key-on (preserves ix)
```
**The `sc_mod_speed` / `sc_mod_steps` reload problem is real** — a countdown field can't also be its own reload source. **Resolve it cleanly by adding two more bytes** `sc_mod_speed_raw` + `sc_mod_step_half` to the struct in Task 2 (revise Task 2 Step 2/3 to add them — they are pure appended state, 2 more bytes, SeqChannel 53→55, SfxChannel 60→62, still within `(ix+d)`). `Seq_Op_ModSet` stores `sc_mod_speed_raw = speed`; `Mod_ReArm` computes `sc_mod_step_half = raw_step >> 1` and seeds `sc_mod_steps = sc_mod_step_half`, `sc_mod_speed = sc_mod_speed_raw`; `Mod_ApplyVibrato` reloads `sc_mod_speed` from `sc_mod_speed_raw` and `sc_mod_steps` from `sc_mod_step_half`. **Apply this two-field addition — it removes every DECISION/hack comment above.** Rewrite the speed/steps reload lines to `ld a,(ix+sc_mod_speed_raw) / ld (ix+sc_mod_speed),a` and `ld a,(ix+sc_mod_step_half) / ld (ix+sc_mod_steps),a`. (Update Task 2's struct blocks + the field list + the `_len` asserts to 55/62 when implementing this task; the assert-driven build will force the numbers to agree.)
- [ ] **Step 4: Add `Fm_WriteFreq` (write $A4 then $A0, NO key-on).** In `engine/sound_fm.asm`, factor a freq-only writer that the vibrato renderer calls. It mirrors `Fm_NoteOnFreq`'s two writes minus the `$28` key-on + the `SCF_KEYED` set:
```asm
; ----------------------------------------------------------------------
; Fm_WriteFreq — write a raw frequency word to $A4/$A0 WITHOUT keying on (the
; vibrato/pitch-mod path: change pitch on a held note, no EG retrigger).
; In: ix = SeqChannel, d = $A4 value, e = $A0 value. Same write order as
; Fm_NoteOnFreq ($A4 first, then $A0). Does NOT touch $28 or SCF_KEYED.
; Clobbers: af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Fm_WriteFreq:
        push    de
        call    Fm_RoutePart             ; b = part, c = ch-in-part
        ld      a, c
        ld      (Fm_ScratchCh), a
        ld      a, b
        ld      (Fm_ScratchPart), a
        pop     de
        ; --- $A4+ch FIRST (block + fnum high) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_HI       ; reg = $A4 + ch
        ld      c, d                     ; data = $A4 value
        push    de
        call    Fm_YmWrite
        pop     de
        ; --- $A0+ch (fnum low) ---
        ld      a, (Fm_ScratchPart)
        ld      b, a
        ld      a, (Fm_ScratchCh)
        add     a, SND_REG_FNUM_LO       ; reg = $A0 + ch
        ld      c, e                     ; data = $A0 value
        call    Fm_YmWrite
        jp      Fm_ReparkDac             ; defensive re-park ($2A); preserves ix
```

- [ ] **Step 5: Transcoder — emit `MEV_MODSET` from `smpsModSet`.** Add the `ModSet` Event class to `tools/song_packer.py`:
```python
MEV_MODSET = 0xEC           # + wait speed change step: latch pitch-modulation params (all 0 = off)


class ModSet(Event):
    """SFX-fidelity pitch modulation (the engine's smpsModSet): latch wait/speed/
    change/step. The engine re-arms per note (accum=0, step halved per S3K srl) and
    renders a continuous additive freq-word vibrato/sweep with NO re-key. All-zero
    = mod off. `change` (the per-step delta) is a signed byte. FM (+ PSG, Task 5)."""
    def __init__(self, wait: int, speed: int, change: int, step: int):
        self.wait = wait
        self.speed = speed
        self.change = change
        self.step = step

    def encode(self) -> bytes:
        return bytes([MEV_MODSET, self.wait & 0xFF, self.speed & 0xFF,
                      self.change & 0xFF, self.step & 0xFF])

    def validate(self, route):
        for name, v in (('wait', self.wait), ('speed', self.speed), ('step', self.step)):
            if not (0 <= v <= 0xFF):
                raise PackError(f"ModSet {name} {v} out of byte range")
        if not (-128 <= self.change <= 127) and not (0 <= self.change <= 0xFF):
            raise PackError(f"ModSet change {self.change} out of byte range")
```
In `tools/sfx_transcode.py`, import `ModSet`, and replace the `smpsModSet` drop (the live block at ~L591):
```python
                    elif macro == 'smpsModSet':
                        # Intentional lossy mapping: drop for v1 (no per-note pitch-mod envelope).
                        # The note pitch + duration ARE preserved (smpsModSet is a zero-tick setter).
                        print(f"  [info] sfx ${sfx_id:02X} ch ${chanid:02X}: smpsModSet dropped "
                              f"(pitch-modulation envelope not in v1 scope; notes preserved)",
                              file=sys.stderr)
                        # consume the 4 operand bytes (wait,speed,change,step) — they're in arg_str
                        # No event emitted.
```
with:
```python
                    elif macro == 'smpsModSet':
                        # Pitch modulation: emit the raw .asm operands (wait,speed,change,step).
                        # The engine applies S3K's own srl-on-init — do NOT re-encode the
                        # macro's version-specific *speed step transform (that's the data
                        # layer, already implied by the source operands).
                        args = _split_args(arg_str)
                        if len(args) < 4:
                            raise TranscodeError(f"smpsModSet expects 4 operands, got {args!r}")
                        wait  = _parse_int(args[0])
                        speed = _parse_int(args[1])
                        change = _parse_signed_byte(args[2])
                        step  = _parse_int(args[3])
                        events.append(ModSet(wait, speed, change, step))
```
Add `_parse_signed_byte` if not present (interpret `$F8` as -8 etc.: `v = _parse_int(tok); return v-256 if v>127 else v`). The header-scan block at ~L927 already lists `smpsModSet` among the consumed macros — leave it (it just skips the operands in that pass); the data pass emits the event.
- [ ] **Step 6: pytest.** Add `TestModSet`:
  - `test_jump_emits_modset`: transcode Jump; assert PSG1 events contain `ModSet(0x02,0x01,-8,0x65)` (the `$F8` change is -8).
  - `test_modset_encodes`: `ModSet(0x02,0x01,-8,0x65).encode() == bytes([0xEC,0x02,0x01,0xF8,0x65])`.
  - `test_spindash_emits_modset`: transcode Spin Dash; assert FM5 events contain `ModSet(0x01,0x01,0x1A,0x01)` and a later `ModSet(0,0,0,0)` (mod-off).
  Run pytest → pass.
- [ ] **Step 7: Build + spectral acceptance (FM vibrato).** Build, regen, rebuild. On `oracle`: post Spindash `$AB` (the FM5 vibrato on the held `nC5`). `vgm_start`→fire→`vgm_stop`→`vgm2wav`. `emulator_audio_spectrum`: the held `nC5` fundamental shows a shallow triangle **vibrato** (the `$1A`-deep, fast wobble), smooth, with NO per-frame re-attack (the EG envelope is steady — verify the amplitude does NOT machine-gun-pulse). Record the verdict.
- [ ] **Step 8: Regression.** Moving Trucks `vgm2wav` byte-identical (no song emits MODSET; `sc_mod_ctrl==0` → the `or a / call nz` skips `Mod_ApplyVibrato`). A no-mod SFX (e.g. Ring) unchanged.
- [ ] **Step 9: Commit.**
```bash
git add sound_constants.asm engine/sound_sequencer.asm engine/sound_fm.asm tools/song_packer.py tools/sfx_transcode.py tools/test_sfx_transcode.py data/sound/sfx/
git commit -m "feat(sound): FM pitch modulation — MEV_MODSET + Mod_ReArm + Mod_ApplyVibrato (continuous freq-word vibrato, no re-key)"
```

---

## Task 5: Pitch modulation — PSG

**Goal:** apply the same accumulated `sc_mod_accum` offset to the PSG tone frequency in the PSG per-frame render (jump's `smpsModSet $02,$01,$F8,$65` sweep is on PSG1), via a PSG branch in `ModUpdate` alongside `PsgEnvUpdate`; latch the PSG base freq in `Psg_NoteOn`. **Acceptance: jump's PSG downward "pew" sweep is visible in the spectrogram. Regression: a no-mod PSG SFX + all music unchanged.**

**Files:** Modify `engine/sound_sequencer.asm`, `engine/sound_psg.asm`.

- [ ] **Step 1: Latch the PSG base divisor in `Psg_NoteOn`.** The PSG modulation accumulates a signed offset onto the tone DIVISOR (10-bit). `Psg_NoteOn` computes the divisor in `de` (e=lo, d=hi). Latch it into `sc_base_freq` (reuse the same 16-bit field; for PSG it holds the divisor, not the $A4/$A0 word). The live code, just before the latch/data writes:
```asm
        ld      e, (hl)                  ; e = divisor low byte
        inc     hl
        ld      d, (hl)                  ; d = divisor high byte (only D1-D0 used)
        ; de = 10-bit divisor; build the latch + data bytes.
        push    de                       ; save divisor across Psg_ChBase
```
Replace with:
```asm
        ld      e, (hl)                  ; e = divisor low byte
        inc     hl
        ld      d, (hl)                  ; d = divisor high byte (only D1-D0 used)
        ; latch the base divisor for PSG pitch modulation (spec §5): sc_base_freq
        ; holds (hi,lo) = (d,e); the vibrato/sweep offset is summed onto it each frame.
        ld      (ix+sc_base_freq), d
        ld      (ix+sc_base_freq+1), e
        ; de = 10-bit divisor; build the latch + data bytes.
        push    de                       ; save divisor across Psg_ChBase
```
Also call the re-arm so a PSG modulated note clears accum + reloads steps. After the `set SCF_KEYED_B` line in `Psg_NoteOn` (the one Task 3 edited to also reset `sc_psgenv_cur`), add `call Mod_ReArm`. The Task-3-edited block becomes:
```asm
        set     SCF_KEYED_B, (ix+sc_flags)
        ld      (ix+sc_psgenv_cur), 0    ; PSG vol-env restarts its contour on each attack (spec §4)
        call    Mod_ReArm                ; PSG pitch-mod re-arm (no-op if sc_mod_ctrl==0)
        ld      a, (ix+sc_volume)
        jp      Psg_SetVolume            ; (preserves ix; ret from there)
```
(`Mod_ReArm` is route-agnostic — it only touches `sc_mod_*`/`sc_base_freq`/`sc_last_freq`, already latched above. It preserves all registers except af, so the `ld a,(ix+sc_volume)` after it is correct.)

- [ ] **Step 2: PSG modulation render in `ModUpdate` (alongside `PsgEnvUpdate`).** The Task-3 PSG gate in `ModUpdate` currently runs only `PsgEnvUpdate` (env) and returns. Extend it so a PSG channel with `sc_mod_ctrl != 0` also renders the pitch offset. The Task-3 PSG branch is:
```asm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; DAC or other non-PSG -> nothing
        ld      a, (ix+sc_psgenv)
        or      a
        ret     z                        ; no PSG vol-env -> nothing (held-note fast path)
        jp      PsgEnvUpdate             ; advance the contour + emit (tail-call, preserves ix)
.is_fm:
```
Replace with:
```asm
        bit     SCF_IS_PSG_B, (ix+sc_flags)
        ret     z                        ; DAC or other non-PSG -> nothing
        ; PSG pitch modulation (spec §5): if active, render the freq sweep/vibrato.
        ld      a, (ix+sc_mod_ctrl)
        or      a
        call    nz, Psg_ApplyMod         ; advance accum + re-latch the tone divisor (no re-key)
        ; PSG volume envelope: advance the contour + re-emit the volume.
        ld      a, (ix+sc_psgenv)
        or      a
        ret     z                        ; no PSG vol-env -> done (mod already handled)
        jp      PsgEnvUpdate             ; advance the contour + emit (tail-call, preserves ix)
.is_fm:
```

- [ ] **Step 3: `Psg_ApplyMod` — the PSG analogue of `Mod_ApplyVibrato`.** It runs the SAME accumulator/triangle logic, then writes the modulated divisor to the PSG tone register (latch + data bytes) WITHOUT re-keying. Add it in `engine/sound_psg.asm` (it shares the accumulator math with `Mod_ApplyVibrato` but emits to PSG, not YM):
```asm
; ----------------------------------------------------------------------
; Psg_ApplyMod — one frame of PSG pitch modulation (spec §5). Same accumulate/
; triangle logic as Mod_ApplyVibrato (port of zDoModulation), but the final value
; is summed onto the PSG tone DIVISOR (sc_base_freq holds hi,lo) and re-latched to
; the PSG tone register. Does NOT re-key. Tone routes only (PSGN noise has no
; divisor — guarded by the caller's PSG-route gate; a noise channel never sets
; sc_mod_ctrl in the core set). In: ix = PSG tone channel, sc_mod_ctrl != 0.
; Clobbers af,bc,de,hl. Preserves ix.
; ----------------------------------------------------------------------
Psg_ApplyMod:
        ; --- wait countdown (one-shot, then held at 1) ---
        ld      a, (ix+sc_mod_wait)
        dec     a
        ld      (ix+sc_mod_wait), a
        ret     nz
        inc     (ix+sc_mod_wait)
        ; --- speed gate ---
        dec     (ix+sc_mod_speed)
        jr      nz, .sustain
        ld      a, (ix+sc_mod_speed_raw)
        ld      (ix+sc_mod_speed), a
        ld      a, (ix+sc_mod_delta)
        ld      c, a
        add     a, a
        sbc     a, a
        ld      b, a                     ; bc = signed delta
        ld      l, (ix+sc_mod_accum)
        ld      h, (ix+sc_mod_accum+1)
        add     hl, bc
        ld      (ix+sc_mod_accum), l
        ld      (ix+sc_mod_accum+1), h
.sustain:
        ; --- final divisor = base + accum ---
        ld      h, (ix+sc_base_freq)
        ld      l, (ix+sc_base_freq+1)
        ld      c, (ix+sc_mod_accum)
        ld      b, (ix+sc_mod_accum+1)
        add     hl, bc                   ; hl = modulated 10-bit divisor (low 10 bits used)
        ; --- triangle reverse ---
        dec     (ix+sc_mod_steps)
        jr      nz, .write
        ld      a, (ix+sc_mod_step_half)
        ld      (ix+sc_mod_steps), a
        ld      a, (ix+sc_mod_delta)
        neg
        ld      (ix+sc_mod_delta), a
.write:
        ; write-on-change vs sc_last_freq.
        ld      a, h
        cp      (ix+sc_last_freq)
        jr      nz, .emit
        ld      a, l
        cp      (ix+sc_last_freq+1)
        ret     z
.emit:
        ld      (ix+sc_last_freq), h
        ld      (ix+sc_last_freq+1), l
        ; re-latch the PSG tone divisor (latch byte = $80|(ch<<5)|(div&$0F); data =
        ; (div>>4)&$3F). hl = divisor; reuse Psg_NoteOn's split. d,e = hi,lo.
        ld      d, h
        ld      e, l
        push    de                       ; save divisor across Psg_ChBase
        call    Psg_ChBase               ; a = ch<<5
        or      SND_PSG_TONE_LATCH       ; $80 | (ch<<5)
        ld      c, a
        pop     de
        ld      a, e
        and     0Fh                      ; div & $0F
        or      c
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
        or      b                        ; (div >> 4)
        and     3Fh
        ld      (SND_Z80_PSG), a         ; data byte
        ret
```
(`sc_mod_speed_raw`/`sc_mod_step_half` are the two fields added in Task 4 Step 3. This shares them with the FM path; no new state.)

- [ ] **Step 4: Build + spectral acceptance (PSG sweep).** Build, regen, rebuild. On `oracle`: post Jump `$62` (PSG1, `smpsModSet $02,$01,$F8,$65` = a large one-way `$65` step → a one-shot downward **sweep**, the classic jump "pew"). `vgm_start`→fire→`vgm_stop`→`vgm2wav`. `emulator_audio_spectrum`: the PSG1 fundamental sweeps DOWNWARD smoothly over the note (the `nBb2` glides down), no discrete note steps, no re-attack. Record the verdict — this is the single biggest contributor to jump fidelity (the env is near-flat).
- [ ] **Step 5: Regression.** Moving Trucks unchanged (uses 0 PSG channels for melody, and no song emits MODSET). A no-mod PSG SFX (e.g. Skid, env-only) unchanged: `sc_mod_ctrl==0` → `Psg_ApplyMod` skipped.
- [ ] **Step 6: Commit.**
```bash
git add engine/sound_sequencer.asm engine/sound_psg.asm
git commit -m "feat(sound): PSG pitch modulation — Psg_ApplyMod sweep/vibrato on the tone divisor (jump 'pew')"
```

---

## Task 6: Spindash rev

**Goal:** add the `Snd_SpindashRev` global (zeroed at init), the `MEV_SPINREV`/`MEV_SPINREV_RESET` readers (port `cfSpindashRev`: add to `sc_transpose`, cap $10, inc the global; reset = 0), the reset-on-non-spindash-SFX line in `Sfx_BeginSound` (compare popped id vs `SFXID_SPINDASH`), and the transcoder (remove the flat bake; emit the ops + `MEV_MODSET` for AB's vibrato; keep the bare `nC5`). **Acceptance: repeated spindash triggers show a rising fundamental (cap +$10), reset to base by the next other SFX. Regression: Moving Trucks unchanged; a non-spindash SFX zeros the global.**

**Files:** Modify `engine/z80_sound_driver.asm`, `engine/sound_sequencer.asm`, `engine/sound_sfx.asm`, `tools/song_packer.py`, `tools/sfx_transcode.py`, `tools/test_sfx_transcode.py`.

- [ ] **Step 1: Allocate `Snd_SpindashRev` + zero it at init.** In `sound_constants.asm`, after the `Snd_PitchTabPtr` scratch allocation (in the free sequencer block, below the trace ring), add one byte:
```asm
; SFX Expressive Fidelity (spec §6): the GLOBAL spindash rev byte (mirror S3K's
; zSpindashRev). Added to the spindash SFX channel's sc_transpose each re-trigger
; (cap $10), incremented per trigger, reset to 0 by any non-spindash SFX. Single
; byte in the free seq block below the trace ring.
Snd_SpindashRev    = Snd_PitchTabPtr + 2
    if (Snd_SpindashRev + 1) > SND_SEQ_TRACE
      fatal "Snd_SpindashRev (\{Snd_SpindashRev}) runs into the trace ring at \{SND_SEQ_TRACE}"
    endif
```
(Update the existing `if (Snd_PitchTabPtr + 2) > SND_SEQ_TRACE` guard's neighbor if needed — the new byte sits just above it; the new guard covers it.) Then in `engine/z80_sound_driver.asm` `SndDrv_Init`, after the `ld (SND_SFX_QUEUE_CNT), a` line (where `a` is already 0), add:
```asm
        ld      (SND_SFX_QUEUE_CNT), a   ; 0 entries pending
        ld      (Snd_SpindashRev), a     ; spindash rev escalation starts at 0 (spec §6)
```

- [ ] **Step 2: `MEV_SPINREV` / `MEV_SPINREV_RESET` readers (port `cfSpindashRev`/`cfResetSpindashRev`).** In `engine/sound_sequencer.asm`, add two zero-tick handlers (no operand; hl stays the live stream ptr):
```asm
; $F0 MEV_SPINREV (no operand) : port of cfSpindashRev. Add the global rev into this
; channel's sc_transpose (feeds the note-index lookup), cap at exactly $10, else
; increment the global. Zero-tick.
Seq_Op_SpinRev:
        ld      a, (Snd_SpindashRev)
        add     a, (ix+sc_transpose)
        ld      (ix+sc_transpose), a
        cp      $10                      ; transpose hit exactly $10 -> stop rising
        jp      z, Seq_ContinueFetch
        ld      a, (Snd_SpindashRev)
        inc     a
        ld      (Snd_SpindashRev), a
        jp      Seq_ContinueFetch

; $F1 MEV_SPINREV_RESET (no operand) : port of cfResetSpindashRev. Zero the global.
Seq_Op_SpinRevReset:
        xor     a
        ld      (Snd_SpindashRev), a
        jp      Seq_ContinueFetch
```
Wire `SeqOpcodeTable`: replace `dw Seq_BadOpcode ; $F0 reserved` with `dw Seq_Op_SpinRev ; $F0 MEV_SPINREV` and `dw Seq_BadOpcode ; $F1 reserved` with `dw Seq_Op_SpinRevReset ; $F1 MEV_SPINREV_RESET`.
(NOTE: `sc_transpose` feeds `Fm_NoteFromTable`'s index clamp — but SFX FM notes key via `Fm_NoteOn` (chromatic, Task 1), which does NOT apply `sc_transpose`. So for the chromatic SFX path the SPINREV transpose must be applied to the note index at key time. Since the spindash SFX is FM5 and its single note `nC5` keys via `Fm_NoteOn` after Task 1, `sc_transpose` would be ignored. **RESOLUTION: make `Fm_NoteOn` apply `sc_transpose` the same way `Fm_NoteFromTable` does** — add the signed `sc_transpose` add + a clamp to `0..94` (`FmPitchTableZ`'s valid range) at the top of `Fm_NoteOn`. This makes the chromatic path transpose-aware, which the spindash rev requires, and is harmless for non-transposed SFX (sc_transpose==0). Implement that clamp in this task; see Step 3.)

- [ ] **Step 3: Make `Fm_NoteOn` transpose-aware (clamp to 0..94).** In `engine/sound_fm.asm`, `Fm_NoteOn`'s live head is:
```asm
Fm_NoteOn:
        ; hl = &FmPitchTableZ[pitch] = base + pitch*2
        ld      l, a
        ld      h, 0
        add     hl, hl                   ; pitch*2 (word entries)
        ld      de, FmPitchTableZ
        add     hl, de
```
Replace with:
```asm
Fm_NoteOn:
        ; apply the signed sc_transpose (spindash rev feeds this, spec §6), then clamp
        ; to FmPitchTableZ's valid range 0..FMPITCH_MAX_IDX. sc_transpose is 0 for a
        ; non-transposed note, so this is a no-op for the common case.
        ld      l, a
        ld      h, 0
        ld      a, (ix+sc_transpose)
        ld      e, a
        add     a, a                     ; CF = sign bit
        sbc     a, a
        ld      d, a                     ; de = sign-extended transpose
        add     hl, de                   ; hl = pitch + transpose (signed)
        bit     7, h
        jr      z, .nonneg
        ld      hl, 0                    ; < 0 -> clamp 0
        jr      .clamped
.nonneg:
        ld      a, h
        or      a
        jr      nz, .clamp_hi
        ld      a, l
        cp      FMPITCH_MAX_IDX+1
        jr      c, .clamped
.clamp_hi:
        ld      l, FMPITCH_MAX_IDX
.clamped:
        ; hl = &FmPitchTableZ[idx] = base + idx*2
        add     hl, hl                   ; idx*2 (word entries)
        ld      de, FmPitchTableZ
        add     hl, de
```
Add `FMPITCH_MAX_IDX = $5E` (94, the highest valid `FmPitchTableZ` index — the transcoder already clamps SFX notes to `0x5E`) to `sound_constants.asm` near the pitch-table equates if not present. Verify against the live `FmPitchTableZ` entry count (98 entries, indices 0..94 valid per the research; if the live table differs, use its real max).
(NOTE: `Fm_NoteOn` is also the SFX note-on path from `Seq_HookNoteOn`. Adding transpose there means an SFX with a nonzero `sc_transpose` from its header `pitch` field also transposes — which is the intended S3K behavior. The Task-1 `count==1`/`.multipoint` chromatic re-key now also gets transpose, consistent with the spindash rev.)

- [ ] **Step 4: Reset-on-non-spindash-SFX in `Sfx_BeginSound`.** The reset must fire when a NON-spindash SFX begins (mirror `zPlaySound_Normal`). `Sfx_BeginSound` (`engine/sound_sfx.asm`) is entered with `a` = the popped SFX id (before the `sub SFX_ID_BASE` range check). Add the compare at the very top, before the range check. The live head is:
```asm
Sfx_BeginSound:
        ; --- id range check (dense table indexed by id - SFX_ID_BASE) ---
        sub     SFX_ID_BASE
        ret     c                        ; id < base -> ignore
```
Replace with:
```asm
Sfx_BeginSound:
        ; spindash rev reset (spec §6): any NON-spindash SFX resets the global rev to
        ; 0 (mirror zPlaySound_Normal). The spindash SFX is the special-cased exception
        ; that does NOT reset, so its rev keeps rising across re-triggers. Compare the
        ; raw id (a) against SFXID_SPINDASH BEFORE the range-check subtract.
        cp      SFXID_SPINDASH
        jr      z, .keep_rev             ; spindash -> do NOT reset (let it escalate)
        push    af
        xor     a
        ld      (Snd_SpindashRev), a     ; normal SFX -> rev escalation back to 0
        pop     af
.keep_rev:
        ; --- id range check (dense table indexed by id - SFX_ID_BASE) ---
        sub     SFX_ID_BASE
        ret     c                        ; id < base -> ignore
```

- [ ] **Step 5: Transcoder — remove the flat bake; emit the rev ops + AB's MEV_MODSET.** Add the `SpinRev`/`SpinRevReset` Event classes to `tools/song_packer.py`:
```python
MEV_SPINREV = 0xF0          # (no operand): add the global spindash rev into sc_transpose, cap $10
MEV_SPINREV_RESET = 0xF1    # (no operand): zero the global spindash rev


class SpinRev(Event):
    """SFX-fidelity spindash rev (the engine's smpsSpindashRev): add the global rev
    into this channel's transpose, cap $10, increment the global. Runtime-escalating
    by re-trigger count. Zero-tick, no operand."""
    def encode(self) -> bytes:
        return bytes([MEV_SPINREV])


class SpinRevReset(Event):
    """SFX-fidelity spindash rev reset (smpsResetSpindashRev): zero the global rev.
    Zero-tick, no operand."""
    def encode(self) -> bytes:
        return bytes([MEV_SPINREV_RESET])
```
In `tools/sfx_transcode.py`: import `SpinRev`, `SpinRevReset`; **delete** the `_SPINDASH_STEP`, `spindash_active`, `spindash_accum` machinery (the live lines ~488-491, 525, 601-606, 736, 772-774, 843, 933-936). Replace the live `smpsSpindashRev` handler:
```python
                    elif macro == 'smpsSpindashRev':
                        # Enable spindash frequency ramp: each note accumulates a rising pitch.
                        spindash_active = True
                        spindash_accum = 0
                    elif macro == 'smpsResetSpindashRev':
                        # Disable spindash ramp, reset accumulator.
                        spindash_active = False
                        spindash_accum = 0
```
with:
```python
                    elif macro == 'smpsSpindashRev':
                        # Runtime-escalating spindash rev: emit the opcode; the engine
                        # adds the global rev (re-trigger count) into sc_transpose.
                        events.append(SpinRev())
                    elif macro == 'smpsResetSpindashRev':
                        events.append(SpinRevReset())
```
And remove the flat-bake at the note emit (live ~L772):
```python
                    pitch = _smps_note_to_pitch(val, is_psg, transpose)
                    if spindash_active:
                        pitch = min(0x5E, pitch + spindash_accum)
                        spindash_accum += _SPINDASH_STEP
```
becomes:
```python
                    pitch = _smps_note_to_pitch(val, is_psg, transpose)
                    # (spindash rev is now runtime: the SpinRev opcode + the global
                    #  rev add the transpose at play time; the note stays the bare nC5.)
```
The AB spindash `smpsModSet` calls are already emitted by Task 4's `smpsModSet` handler (the `$01,$01,$1A,$01` vibrato + the `0,0,0,0` mod-off) — verify the Spin Dash transcode now contains: `SpinRev`, `Patch(0)`, `ModSet(1,1,0x1A,1)`, the `nC5` note, `ModSet(0,0,0,0)`, … `SpinRevReset`, `End`.
- [ ] **Step 6: pytest.** Add `TestSpindashRev`:
  - `test_spindash_emits_rev_ops`: transcode Spin Dash; assert FM5 events contain a `SpinRev` (first) and a `SpinRevReset` (near the end), and the note is the bare `nC5` pitch (NOT flat-baked-up).
  - `test_spinrev_encodes`: `SpinRev().encode() == bytes([0xF0])`, `SpinRevReset().encode() == bytes([0xF1])`.
  - `test_no_spindash_step_constant`: assert the module no longer defines `_SPINDASH_STEP` (the flat bake is gone) — `assert not hasattr(sfx_transcode, '_SPINDASH_STEP')` or grep the source.
  Run pytest → pass.
- [ ] **Step 7: Build + acceptance (rising rev + reset).** Build, regen, rebuild. On `oracle`: post Spindash `$AB` repeatedly (write `$AB`→`SND_REQ_SFX` once per several frames, e.g. 8 times). After each, `emulator_z80_read` `Snd_SpindashRev` — it climbs 0,1,2,… until the channel's `sc_transpose` hits $10 (then holds). `emulator_audio_spectrum` across the 8 triggers: the `nC5` fundamental **rises** in semitone steps, capping after ~8 reps (+$10). Then post Jump `$62` and re-read `Snd_SpindashRev` — back to 0 (the normal-SFX reset). Re-post Spindash: the rev restarts from base. Record the verdict.
- [ ] **Step 8: Regression.** Moving Trucks unchanged (no song emits SPINREV; `Snd_SpindashRev` stays 0; `sc_transpose` add in `Fm_NoteOn` is a no-op for `sc_transpose==0`). Confirm a non-modulated FM SFX (Ring) is unchanged.
- [ ] **Step 9: Commit.**
```bash
git add sound_constants.asm engine/z80_sound_driver.asm engine/sound_sequencer.asm engine/sound_fm.asm engine/sound_sfx.asm tools/song_packer.py tools/sfx_transcode.py tools/test_sfx_transcode.py data/sound/sfx/
git commit -m "feat(sound): spindash rev — Snd_SpindashRev global + MEV_SPINREV/RESET + transpose-aware Fm_NoteOn + non-spindash reset"
```

---

## Task 7: Full acceptance + regression + merge

**Goal:** re-transcode the whole core set, spectral A/B each SFX against its S3K-expected behavior, confirm jump/spindash/ring/skid/break sound faithful, verify Moving Trucks renders byte-identical, and that all 5a acceptance still holds. Then merge.

**Files:** Possibly regenerate `data/sound/sfx/*` (no new code).

- [ ] **Step 1: Re-transcode + full pytest.** `python3 tools/sfx_transcode.py generate` (regenerates every blob with PSGENV/MODSET/SPINREV). `python3 -m pytest tools/test_sfx_transcode.py -q` → all pass (5a tests + the new PsgEnv/ModSet/SpindashRev tests). `git diff --stat data/sound/sfx/` to confirm only the expected blobs changed.
- [ ] **Step 2: Build.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe` → exit 0. All struct/opcode/RAM asserts pass; `SfxTable` completeness assert still holds.
- [ ] **Step 3: Per-feature spectral acceptance (the full matrix, spec §9).** On `oracle`, `emulator_reload_rom` → resume → play Moving Trucks. For each SFX, `emulator_vgm_start` → fire (via the 5a DEBUG SFX hotkey or `emulator_z80_write` to `SND_REQ_SFX`) → `emulator_vgm_stop` → `vgm2wav` + `emulator_audio_spectrum`:
  - **Pitch-table fix:** Spindash FM note + its vibrato agree on one pitch (no octave warble).
  - **PSG envelopes:** Skid (`VolEnv_0E` 5-frame decay), Break (`VolEnv_0D` blip), Jump (`VolEnv_0C` flat-sustain) — the volume contour matches each shape.
  - **FM vibrato:** Spindash's shallow held-note wobble, smooth, no EG re-attack.
  - **PSG sweep:** Jump's downward "pew" sweep on PSG1.
  - **Spindash rev:** repeated triggers rise (cap +$10), reset by the next other SFX.
  Record each verdict (energy + spectrum, per the verify-real-output rule).
- [ ] **Step 4: Moving Trucks byte-identical regression.** `vgm2wav` a full Moving Trucks loop, A/B against the Task-1 baseline capture: identical (every new opcode is absent from songs; every new field defaults inert; every new gate is a single bit-test on a held note).
- [ ] **Step 5: 5a acceptance still holds.** Confirm steal/restore (jump cuts off the stolen voice + restores cleanly), ducking (spindash dips the music + ramps back; rings don't), and the music lead/bass survive steal→restore (spectrum during/after an SFX vs clean). No desync (`emulator_z80_read` shows cursors advancing through overrides).
- [ ] **Step 6: By-ear confirmation (user).** Ask the user to confirm jump/ring/skid/spindash sound faithful to S3K (the spec's by-ear gate). If anything still sounds off on TIMBRE (e.g. ring's FM voice), that is the separate `translate_voice` axis (spec §10) — flag it, do not fold it in.
- [ ] **Step 7: Commit + merge.**
```bash
git add data/sound/sfx/
git commit -m "feat(sound): SFX expressive fidelity — re-transcode core set + full spectral acceptance"
```
Merge the feature branch → `master` once acceptance passes and the Moving Trucks regression holds (per CLAUDE.md git workflow). Keep `ENGINE_ARCHITECTURE.md` §6 in sync with the shipped PSG-env / pitch-mod / spindash-rev mechanisms.

---

## Notes for the implementer

- **The pitch-table fix is the prerequisite (Task 1) — do it first.** It is the root cause of the 5a spindash octave warble and the precondition for the FM modulation to operate in a consistent pitch domain. `Sfx_Restore`'s `Fm_NoteFromTable` (the FM path, line ~940) is **left as-is** — it restores the *music* channel, where the per-song table is correct. Do NOT "fix" that call.
- **Append-only struct growth.** Every new field is appended inside the SeqChannel-compatible prefix (so `ModUpdate` reads it on both struct types) or after it (the `sx_*` block shifts up but AS recomputes offsets). No existing offset moves; the `_len` + mirror + `(ix+d)` asserts force the numbers to agree. Task 2 ships 13 fields (PSG-env 3 + mod scalars 5 + accum/base/last 6 words minus... = 53/60); Task 4 adds 2 more (`sc_mod_speed_raw`, `sc_mod_step_half`) → 55/62. The build asserts catch any miscount.
- **Gate, don't loop.** New per-frame renderers are gated so a held note with no env/mod costs ONE bit-test: PSG-env = PSG-route + `sc_psgenv!=0`; FM vibrato = `sc_mod_ctrl!=0`; PSG mod = `sc_mod_ctrl!=0`. The Phase-3 held-note fast path is preserved.
- **Atten domain for the PSG env** (spec §4 gotcha): add `sc_psgenv_out` AFTER `Psg_VolToAtten` (it's an attenuation delta, higher = quieter), with the S3K `bit 4,a` underflow guard → clamp $0F. Add it BEFORE the duck fold (env+duck compose) and BEFORE the noise branch (noise SFX get the contour). `$81` sustains (do NOT silence); `$83` rests (silence + disable) — getting these backwards inverts half the SFX.
- **MODSET must NOT re-key** (spec §5 central trap): `Mod_ApplyVibrato`/`Psg_ApplyMod` write `$A4/$A0` (FM) or the PSG divisor on-change, NEVER `$28` key-on — re-keying retriggers the YM EG (machine-gun) and the fnum table is note-quantized. Halve the step at re-arm (S3K `srl`). Hold `wait` at 1 after the initial delay.
- **Spindash rev is global + re-trigger-driven** (spec §6): one byte, NOT per-channel, NOT a 68k parameter. NOT reset by the spindash SFX itself (special-cased), reset by any other SFX. Cap is an equality test (`cp $10 / jr z`). The transpose feeds the note index — so `Fm_NoteOn` (the chromatic SFX path) must apply `sc_transpose` (Task 6 Step 3), since the spindash note keys chromatically.
- **Verify rendered audio, never a register proxy** (the verify-real-output rule): every acceptance check renders VGM→wav + `emulator_audio_spectrum` and compares the contour/sweep/rev shape, not just that the opcode executed. A correct opcode stream can still be inaudible or wrong-shaped.
- **No breakpoints/step on `oracle`** (they wedge it): free-run + `run_to_scanline` + `z80_read`/`z80_write` + `vgm_start`/`vgm_stop` + `audio_spectrum` only.
- Each task: build (`-pe`) + pytest (transcoder) + `oracle` spectral/audio verify + commit. Frequent commits — never lose work.
