# PSG Volume Envelopes for Music Channels (HCZ2 hi-hat) — Design

**Date:** 2026-06-26
**Branch:** `feat/hcz2-import`
**Status:** approved (design), pending implementation plan

## Problem

HCZ2's PSG noise channel (the hi-hat) plays as a continuous wash of white noise instead of distinct percussive "ts" hits. Measured in the oracle (VGM, `/tmp/hcz2_long.vgm`): the SN76489 noise attenuation is pinned at a **constant value 3** for all 735 hits (only dropping to 15/silent 10 times). The notes are correctly timed and spaced (~0.12 s apart, the `$06` durations) but every note keys noise at the same volume and holds it, so back-to-back notes merge into a wash.

A real hi-hat's percussive shape comes from a per-hit **volume-envelope decay**. The same gap also flattens the PSG1/PSG2 tone leads (they get no envelope either).

## Root cause

Two layers:

1. **Converter** (`tools/smps_import.py`): maps every `smpsPSGvoice sTone_NN → PsgEnv(0)` (no envelope) — a documented v1 fidelity gap (`_warn_psg_env_once`).
2. **Engine**: an S3K-exact PSG volume-envelope engine already exists (`PsgEnvUpdate`, `engine/sound_sequencer.asm`; body-byte semantics `$80` loop / `$81` sustain / `$83` rest / plain = atten delta), fed by a **global id-keyed envelope bank** (`PsgVolEnv_Ids`/`PsgVolEnv_Ptrs`/bodies in `engine/sound_tables_z80.asm`, already holding 6 imported S3K envelopes: ids `03,0D,0E,0F,11,1D`). But it is wired for **SFX channels only**. The music `SeqChannel` is 39 bytes and lacks the three envelope fields (`sc_psgenv`/`sc_psgenv_cur`/`sc_psgenv_out` at +39/+40/+41, which exist only on the 62-byte `SfxChannel`). Three gates therefore skip music:
   - `ModUpdate` (`sound_sequencer.asm`): runs `PsgEnvUpdate` only for an SFX PSG channel with `sc_psgenv != 0`.
   - `Psg_SetVolume` (`sound_psg.asm`): folds `sc_psgenv_out` only when `ix >= SND_SFX_BASE` (music skips).
   - Key-on cursor reset (`Psg_EnvCursorReset`): SFX-only.

So music PSG channels can *store* an envelope id but never *run* one.

## Research confirmed

- **Banking is solved.** `main.asm:303` documents that `PsgVolEnv_*` (and the other voice tables) live **at the start of the song bank**, and HCZ2 is co-located in that bank. When HCZ2 plays, its bank is windowed in via `$8000`, so the music sequencer reads the envelope table exactly like it reads the song stream — no bank-bracketing needed.
- **Import precedent exists.** 6 S3K envelopes are already in `PsgVolEnv_*`, each tagged with its S3K source (`PsgVolEnv_03 ; sTone_03 (S3K VolEnv_02)` → engine `sTone_NN` = S3K `VolEnv_(NN-1)`).
- **HCZ2's envelopes are not yet imported.** HCZ2 references **5** sTones — `sTone_01/02/08/0A/0C` (counts 36/1/34/1/3); none are in the table → import from S3K `VolEnv_00/01/07/09/0B` (all clean: plain deltas + `$81`/`$83`, no unsupported control bytes).
- **The drums fix composes correctly.** After the standalone-duration fix, distinct noise notes re-key (fresh envelope = a "ts") and tied notes are one merged `NoteDur` (one key-on = one envelope = sustain) — exactly S3K's prevent-attack semantics.

## Design

### 1. Engine — `SeqChannel` carries the envelope
Grow `SeqChannel` 39 → 42 bytes, adding `sc_psgenv` (+39), `sc_psgenv_cur` (+40), `sc_psgenv_out` (+41) — the same offsets they occupy in `SfxChannel`, so the shared `(ix+sc_*)` prefix still matches (it extends 3 bytes further). Zeroed at channel init → default-inert. Update the `SeqChannel_len` assert and verify the music-channel RAM array still fits the Z80 RAM map (+3 bytes × N music channels).

### 2. Engine — flip 3 gates SFX-only → PSG-with-envelope
- `ModUpdate`: run `PsgEnvUpdate` for any PSG-route channel with `sc_psgenv != 0` (drop the SFX-only test; the field is now in-bounds for music).
- `Psg_SetVolume`: fold `sc_psgenv_out` for any channel that has the field (drop the `Snd_ChanClass` music-skip).
- Key-on cursor reset: reset the contour on attack for music PSG too.

`PsgEnvUpdate` and `PsgVolEnv_Resolve` are reused unchanged.

### 3. Data — import HCZ2's 5 envelopes
Add `sTone_01/02/08/0A/0C` (S3K `VolEnv_00/01/07/09/0B`) via `tools/gen_sound_tables.py` `_PSG_VOL_ENVS` (the existing 6 were imported the same way; bodies verbatim from `skdisasm/Sound/Z80 Sound Driver.asm:4503-4525`), then regenerate `engine/sound_tables_z80.asm`; `PSGVOLENV_COUNT` 6 → 11.

### 4. Converter — stop dropping envelopes
Map `smpsPSGvoice sTone_NN → PsgEnv(NN)` instead of `PsgEnv(0)`. Validate the referenced `sTone` is present in the engine table (a build-time/convert-time check), so a missing import fails loudly rather than silently degrading to no envelope. Regenerate `song_hcz2.asm`.

### 5. Testing / verification
- Converter unit test: `smpsPSGvoice sTone_08` emits `PsgEnv(8)`, not `PsgEnv(0)`; the noise channel and PSG1/2 carry nonzero env ids.
- Build green (`SOUND_DRIVER_ENABLED=1 DEBUG=1`).
- Oracle: VGM noise-attenuation contour now **decays per hit** (not constant 3); PSG1/2 show envelope shaping. Listen to confirm distinct hi-hat hits.

## Scope

In scope: all music PSG channels (noise hi-hat + PSG1/2 tone leads). Out of scope (separate concern): the noise *pitch/color* gap (S3K `smpsPSGform` rate-3 tone-3 frequency coupling — the converter forces fixed white noise). Timing of the hits is already correct (drums fix).

## Open items — RESOLVED during planning
- **RAM headroom:** confirmed. `SND_SEQ_END` = `$1808 + 11*SeqChannel_len` → 39:$19B5, 42:$19D6, far below the FIXED `SND_SONG_BUF=$1B00`/`SND_SFX_BASE=$1D00`; build-time `fatal` guards backstop. Growing the array does NOT move `$1D00`, so the music-vs-SFX high-byte gate is unaffected.
- **S3K source + importer:** S3K bodies at `Z80 Sound Driver.asm:4503-4525`; generator is `tools/gen_sound_tables.py` `_PSG_VOL_ENVS` (extend + regenerate).
- **No hard-coded `SeqChannel_len`:** the channel-array walk uses symbolic `ld de, SeqChannel_len`; the music/SFX split uses the fixed `SND_SFX_BASE` ($1D00), not the struct size.
- **Two refinements found:** (a) the `ModUpdate` PSG gate must SPLIT (music = env-only, since `sc_mod_*` stay SFX-only at +42), not blanket-ungate; (b) the channel init sets fields individually (no bulk clear), so the 3 new fields need explicit zeroing at load. Both are in the plan.
