# Sound — S3K SFX Expressive Fidelity (PSG envelopes + pitch modulation + spindash rev)

**Date:** 2026-06-20
**Status:** Design approved (brainstorming, 2026-06-20)
**Branch:** TBD (continues on / branches from `feat/sound-phase5a-sfx`)
**Builds on:** Phase 5a Core SFX Engine (steal/restore/priority/ducking, the S3K transcoder,
`Sound_PlaySFX`, game seams) + Phase 3a FM depth (the per-frame `ModUpdate` modulation layer).
**Drives / acceptance test:** the transcoded Sonic 3&K SFX (jump, ring, skid, roll, spindash,
dash) sound **faithful to S3K** — the right attack/decay shape (PSG envelopes), the right pitch
sweeps/vibrato (`smpsModSet`), and the rising spindash rev — verified spectrally + by ear.

---

## 1. Goal & guiding principle

The 5a SFX engine plays the *right base notes* but the SFX sound "off" because the transcoder
**dropped S3K's expressive layers**: PSG volume envelopes (`smpsPSGvoice`/`sTone_XX`), per-note
pitch modulation (`smpsModSet`), and the runtime spindash rev (`smpsSpindashRev`). This spec adds
faithful reproductions of all three.

**North star (non-negotiable): "don't diminish the engine."** Every feature is a **clean,
additive, default-off extension** that reuses existing layers (the per-frame `ModUpdate`
modulation renderer, the `Psg_SetVolume` choke-point, the zero-tick coordination-opcode pattern).
The structural guarantee: all new per-channel state is *appended* (no existing field offset
moves), all new opcodes default to inert (a zeroed slot does nothing), and **every existing path
— music FM modulation, pan, ducking, note-fill, the 5a SFX engine — is byte-for-byte unchanged
when the new ops are absent.** New per-frame renderers are gated so a held note with no
envelope/modulation costs a single bit-test (preserving the Phase-3 cycle budget).

**Verification upgrade:** the emulator MCP now exposes spectrum/spectrogram tools
(`emulator_audio_spectrum`). Each feature is accepted **spectrally** (the volume contour, the
pitch sweep/vibrato, the rising rev visible in the spectrogram) against S3K's expected behavior,
plus rendered-audio A/B and by-ear — not "it builds."

## 2. Reverse-engineering basis (done)

S3K's three mechanisms, traced in `skdisasm/Sound/Z80 Sound Driver.asm` + `Sound/_smps2asm_inc.asm`:

- **PSG volume envelopes.** `smpsPSGvoice sTone_XX` (`$F5,voice`) stores a 1-based index; the
  driver `dec`s it and indexes `z80_VolEnvPointers` → `VolEnv_XX`, a byte stream of **per-frame
  attenuation deltas** added to the track volume, with control bytes: `$80` = loop cursor to 0,
  `$81` = sustain-hold (rest flag, but **do NOT silence**, holds last value), `$83` = full rest
  (silence the channel). The per-frame apply (`zUpdatePSGTrack`/`zDoVolEnv`, ~L4058-4214) advances
  a per-track cursor, adds the delta to volume with an **underflow guard** (`bit 4,a` → force `$0F`
  silent), and writes the PSG latch. The cursor is **reset to 0 on every fresh attack**
  (`zFinishTrackUpdate`, L1066) unless "no attack" is set. (Examples: jump `VolEnv_0C: db 0,81h`;
  break `VolEnv_0D: db 2,83h`; a decay `VolEnv_01: db 0,2,4,6,8,$10,83h`.)

- **Pitch modulation (`smpsModSet`).** `$F0 + {wait,speed,change,step}`. Per-note init
  (`zPrepareModulation`, L1237-1259) copies wait/speed/change into RAM, **halves `step`** (`srl a`,
  L1254) into `ModulationSteps`, and clears the accumulated offset. Per-frame
  (`zDoModulation`, L1279-1326): count down `wait` (one-shot delay; then held at 1 so it fires
  every frame), and every `speed` frames **add the signed `delta` to a 16-bit accumulated offset**;
  the final frequency = note freq + accumulated offset (summed onto the raw `$A4/$A0` word, **no
  re-key**); every `step/2` applications **reverse the delta sign** (triangle vibrato). A large
  one-way `step` (e.g. jump's `$65`) makes it a one-shot **sweep** rather than a sustained vibrato.
  It modulates the **frequency word** (sub-semitone), NOT a note-index re-key.

- **Spindash rev (`smpsSpindashRev`).** `$E9` (apply) / `smpsResetSpindashRev` `$FF,$07`. A single
  **global** byte `zSpindashRev` (NOT per-track, NOT a 68k input). `cfSpindashRev` (L3039-3051):
  add `zSpindashRev` into this track's `Transpose` (which feeds the note-index lookup), **cap at
  exactly `$10`**, else `inc zSpindashRev`. The global is reset to 0 only by playing a **normal
  (non-spindash) SFX** (`zPlaySound_Normal`, L1971) or by `$FF07` — the spindash SFX itself is
  special-cased to NOT reset it (L1935). So the rev rises by **re-trigger count** (how many times
  spindash was re-played since the last other SFX) — the 68k passes no charge level.

Our 5a transcoder currently drops `smpsPSGvoice`/`smpsModSet` and bakes spindash flat with a
guessed `_SPINDASH_STEP=6` (`tools/sfx_transcode.py`).

## 3. Prerequisite — fix the SFX pitch-table inconsistency

**The latent bug (root cause of the spindash octave-warble observed in 5a):** an SFX FM note-on
goes `Seq_HookNoteOn → Fm_NoteOn → FmPitchTableZ` (the chromatic 98-entry table, indices 0..94).
But `ModUpdate`'s pitch re-key path goes `Fm_NoteFromTable → Snd_PitchTabPtr` — the **per-song**
132-entry table (Moving Trucks' fnum table, different numbering), which `Snd_LoadSong` set for the
*music*. So any SFX pitch-modulation that re-keys via `ModUpdate` reads the wrong table → wrong
pitch, and a bare SFX note vs its own pitch-mod wouldn't even agree.

**Fix:** a free `sc_flags` bit `SCF_PITCH_CHROMATIC`. `SfxDispatch`/slot-init sets it on every SFX
channel. `ModUpdate`'s re-key paths (count==1 and `.multipoint`) branch on it: set → key via
`Fm_NoteOn`/`FmPitchTableZ` (the SFX's own chromatic numbering); clear → `Fm_NoteFromTable` (music,
unchanged). `Sfx_Restore`'s `Fm_NoteFromTable` call is **left as-is** (it restores the *music*
channel, where the per-song table is correct). This must land before §5 (pitch modulation) so the
SFX modulation operates in a consistent pitch domain.

## 4. PSG volume envelopes

- **Data (`engine/sound_tables_z80.asm`):** `PsgVolEnv_Table` — a pointer table + byte-stream
  bodies in **S3K's exact `VolEnv` format** (per-frame atten deltas + `$80` loop / `$81`
  sustain-hold / `$83` full-rest). Copy the exact bytes for the ~10 distinct `sTone` envelopes our
  corpus uses (jump/skid `sTone_0D`=`VolEnv_0C`, break `sTone_0E`, dash/etc. `sTone_1D`, …). Use a
  `function` for the 1-based→0-based index math at build time.
- **State (appended to `SeqChannel` + the `SfxChannel` mirror):** `sc_psgenv` (1-based env id,
  0=none), `sc_psgenv_cur` (cursor), `sc_psgenv_out` (last computed delta — the write-on-change
  shadow). Update `SeqChannel_len`/`SfxChannel_len` asserts + the shared-prefix mirror assert;
  verify the largest offset stays within the `(ix+d)` signed-8-bit range.
- **Opcode `MEV_PSGENV` (`$EB`, a free slot):** zero-tick setter — store `sc_psgenv` from the
  operand, set `sc_psgenv_cur=0`. Add the build-time collision assert alongside the existing
  `MEV_PITCHENV` pattern.
- **Attack reset:** on every PSG note key-on, zero `sc_psgenv_cur` (mirror S3K's per-attack reset)
  so the contour restarts per note. Hook the same event that sets `SCF_KEYED`.
- **Renderer `PsgEnvUpdate`:** called from `ModUpdate`'s per-channel pass, **gated on `sc_route` ∈
  {PSG1..3, noise} AND `sc_psgenv != 0`** (keeps `ModUpdate` stream-agnostic; FM/no-env channels
  pay one bit-test). Cursor logic = S3K's: plain value → store to `sc_psgenv_out`, advance cursor;
  `$80` → cursor=0 and re-read; `$81` → hold last `sc_psgenv_out` (no advance); `$83` → key-off the
  PSG channel + disable the env. Do NOT replicate S3K's buggy "relative-jump" (negative non-command
  byte) path — only plain/loop/sustain/rest.
- **Apply seam:** in `Psg_SetVolume` (the single choke-point), after `Psg_VolToAtten`, **add
  `sc_psgenv_out` in the attenuation domain** (matching S3K, avoiding a volume↔atten sign flip),
  with the `bit 4` underflow guard → clamp to `$0F` silent, **before** the existing duck fold (so
  envelope + duck compose). The add must happen before the noise-route (`$F0`) branch so noise SFX
  get the contour too. No new per-frame loop — `ModUpdate` already runs once/channel/frame and
  `Psg_SetVolume` is already called per keyed PSG note.
- **Transcoder:** replace the `smpsPSGvoice` no-op with `MEV_PSGENV, env_id` emission (a small
  `sTone_XX → engine env id` map for the sTones our corpus uses).

## 5. Pitch modulation (`smpsModSet`) — faithful, FM + PSG

- **State (appended):** `sc_mod_ctrl` (0=off), `sc_mod_wait`, `sc_mod_speed`, `sc_mod_delta`
  (signed), `sc_mod_steps`, `sc_mod_accum` (signed 16-bit), and `sc_base_freq` (the unmodulated
  note's `$A4/$A0` word, latched at key-on) + a `sc_last_freq` shadow for write-on-change.
- **Opcode `MEV_MODSET` (`$EC`):** 4 params `{wait, speed, change, step}` — latch the `sc_mod_*`
  fields (zero-tick setter, the engine's `smpsModSet`). All-zero params = mod-off (the
  `smpsModOff` idiom `AB` uses with `smpsModSet 0,0,0,0`).
- **Per-note re-arm:** mirror `zPrepareModulation` — on key-on (attack, not no-attack/tied), if
  `sc_mod_ctrl` is on: `sc_mod_accum=0`, reload `sc_mod_steps` **halved** (`srl`), copy
  wait/speed/delta from the latched op fields. Gate behind a `sc_mod_ctrl` test (non-modulated
  channels pay one bit-test). Latch `sc_base_freq` in the note-on path (FM: `Fm_NoteOn`/
  `Fm_NoteFromTable` tail; PSG: `Psg_NoteOn`).
- **Renderer `Mod_ApplyVibrato`:** a new `ModUpdate` sub-step that ports `zDoModulation` 1:1 — count
  down `wait` (one-shot, then held at 1); every `sc_mod_speed` frames add signed `sc_mod_delta` to
  `sc_mod_accum`; reverse `sc_mod_delta` every `sc_mod_steps` (triangle); compute `final =
  sc_base_freq + sc_mod_accum`; write `$A4/$A0` **only when `final != sc_last_freq`** (write-on-
  change — a held note with active vibrato writes only every `speed`-th frame); **do NOT key-on**
  (vibrato changes pitch without retriggering the EG). Reuse the existing `$A4/$A0` emit helper.
- **PSG modulation:** the same accumulated offset is added to the PSG frequency divisor in the PSG
  per-frame render (jump's `smpsModSet $02,$01,$F8,$65` sweep is on PSG1). Since `ModUpdate`
  currently `ret z` on non-FM channels, add a PSG branch (alongside `PsgEnvUpdate` from §4) that
  applies the modulation to the PSG tone register. (This is the one genuinely new PSG-modulation
  capability; keep it off the FM held-note fast path.)
- **Transcoder:** replace the `smpsModSet` drop with `MEV_MODSET {wait,speed,change,step}` emission
  (the raw `.asm` operands; the engine applies S3K's own `srl`-on-init — do NOT also apply the
  macro's version-specific `*speed` re-encoding, which is the data layer already in the source).

## 6. Spindash rev (`smpsSpindashRev`) — faithful, re-trigger-driven

- **State:** one **global** byte `Snd_SpindashRev` in driver RAM (mirror `zSpindashRev`), zeroed at
  driver init.
- **Opcode `MEV_SPINREV` (`$F0`):** port `cfSpindashRev` — `a = Snd_SpindashRev`,
  add into `sc_transpose` (which already feeds the note-index lookup), store; if `sc_transpose ==
  $10` skip, else `inc Snd_SpindashRev`. Zero-tick. **`MEV_SPINREV_RESET` (`$F1`):** `Snd_SpindashRev = 0`.
- **Reset-on-normal-SFX (load-bearing):** in `Sfx_DrainQueue`/the SFX begin path, when the
  dispatched id is **not** `SFXID_SPINDASH`, `Snd_SpindashRev = 0` (mirror `zPlaySound_Normal`).
  Requires a `SFXID_SPINDASH` compare in the queue drain. This is the only new code in the queue
  path; **no `{id,priority}` ABI widening** (the rev escalation lives entirely in the driver — more
  faithful AND a smaller change than a 68k charge parameter).
- **Transcoder:** remove the flat `_SPINDASH_STEP` bake; emit `MEV_SPINREV` / `MEV_SPINREV_RESET` at
  the `smpsSpindashRev`/`smpsResetSpindashRev` positions, keep the bare `nC5` note. The rise becomes
  runtime.

## 7. Opcode allocation

New zero-tick coordination opcodes in the free `$E0-$FF` block. Used today: `$E0-$EA`, `$ED`
(`MEV_NOTEFILL`), `$EE`/`$EF` (loop/jump), `$FF` (end). **Free: `$EB`, `$EC`, `$F0-$FE`.** Assign:
`MEV_PSGENV = $EB`, `MEV_MODSET = $EC`, `MEV_SPINREV = $F0`, `MEV_SPINREV_RESET = $F1` — and add each
to the collision-assert chain (mirroring the `MEV_PAN`/`MEV_OPBIAS`/`MEV_REGDELTA` pattern).
`SCF_PITCH_CHROMATIC` takes a free `sc_flags` bit (bit 7 is free; bit 6 is `SCF_SFX_OVERRIDE`).
Re-confirm against `sound_constants.asm`'s live asserts at implementation time.

## 8. "Don't diminish" guarantees (acceptance for the principle)

- All new `SeqChannel`/`SfxChannel` fields are **appended** — no existing offset moves; the
  `_len` + shared-prefix + `(ix+d)`-range asserts updated and passing.
- All new opcodes are **zeroed-default inert**: a song/SFX without them produces byte-identical
  chip output. (Regression: Moving Trucks renders byte-identical; a 5a SFX with no envelope/mod is
  unchanged — the slot wipe zeroes the new fields.)
- New per-frame renderers are **gated** (PSG-env: PSG-route + env-active; vibrato: `sc_mod_ctrl`)
  so the FM held-note fast path keeps its single-bit-test cost.
- Build-time collision asserts for every new opcode; `function`-computed table math.

## 9. Testing / verification (per-feature, spectral)

Build (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe`) + pytest (transcoder). Then on the live
emulator, per feature, using `emulator_audio_spectrum` + VGM→wav A/B:
- **Pitch-table fix:** an SFX FM note + a pitch-env on it agree on the same pitch (chromatic table);
  no octave warble.
- **PSG envelopes:** the PSG channel's volume **contour over time** matches the `VolEnv` shape
  (decay/swell/sustain/rest) in the spectrogram; jump/break/skid have their attack shape.
- **Pitch modulation:** the **pitch sweep/vibrato** is visible in the spectrogram (jump's downward
  "pew" sweep; spindash's shallow vibrato) — smooth, no per-frame EG re-attack.
- **Spindash rev:** repeated spindash triggers show a **rising fundamental** (cap +$10), reset to
  base by the next other SFX.
- **Regression:** Moving Trucks unchanged; all 5a acceptance (steal/restore/duck, jump cuts off,
  music foundation intact) still holds.
- **By-ear:** the user confirms jump/ring/skid/spindash sound faithful to S3K.

## 10. Scope notes / deferrals

- **FM voice (timbre) fidelity** of the FM SFX (e.g. ring's `smpsSetvoice $00`) is a *separate*
  axis — if ring still sounds "off" on timbre after this work, the `translate_voice` conversion is
  the lever; flag it, don't fold it in here unless the spectral A/B shows a voice mismatch.
- **SFX tempo:** the engine hardcodes `sc_tempo_base=16` (1 tick/frame); S3K's `smpsHeaderTempoSFX
  $01` is ignored. Verify the durations land right after the envelopes/mod are in; if timing is off,
  honor the SFX tempo header — small transcoder/init change, tracked here.
- S3K's buggy VolEnv "relative-jump" path and the macro-version-specific `step` re-encoding are
  **not** replicated (documented dead/data-layer behavior).

## 11. References

- S3K: `skdisasm/Sound/Z80 Sound Driver.asm` — VolEnv tables L4494/L4503-4572, apply
  L4058-4214, attack reset L1066, `cfSetPSGVolEnv` L3583; `zPrepareModulation` L1237-1259 (`srl`
  L1254), `zDoModulation` L1279-1326; `zSpindashRev` L155, `cfSpindashRev` L3039-3051,
  `cfResetSpindashRev` L4046, spindash no-reset L1935, normal-SFX reset L1971. Macros:
  `skdisasm/Sound/_smps2asm_inc.asm` (smpsPSGvoice $F5 L599, smpsModSet $F0 L553, smpsSpindashRev
  $E9 L657). SFX: `Sound/SFX/62 - Jump.asm` (sTone_0D + modSet $02,$01,$F8,$65), `AB - Spin
  Dash.asm` (spindashRev + modSet $01,$01,$1A,$01).
- Our engine: `engine/sound_sequencer.asm` `ModUpdate` (134-263), `Fm_NoteFromTable` vs `Fm_NoteOn`
  `engine/sound_fm.asm` (579/632), `Psg_SetVolume` `engine/sound_psg.asm` (177), `Sfx_Frame`/queue
  `engine/sound_sfx.asm`, `sound_constants.asm` (MEV opcodes + free slots + structs + asserts),
  `tools/sfx_transcode.py` (the current drops/flat-bake).
- 5a design + plan: `docs/superpowers/specs/2026-06-20-sound-phase5a-sfx-engine-design.md`,
  `docs/superpowers/plans/2026-06-20-sound-phase5a-sfx-engine.md`.
