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
- **HCZ2's envelopes are not yet imported.** HCZ2 references `sTone_01/02/08/0C` (header `sTone_0C`; body `sTone_01/02/08`); none are in the table → import from S3K `VolEnv_00/01/07/0B`.
- **The drums fix composes correctly.** After the standalone-duration fix, distinct noise notes re-key (fresh envelope = a "ts") and tied notes are one merged `NoteDur` (one key-on = one envelope = sustain) — exactly S3K's prevent-attack semantics.

## Design

### 1. Engine — `SeqChannel` carries the envelope
Grow `SeqChannel` 39 → 42 bytes, adding `sc_psgenv` (+39), `sc_psgenv_cur` (+40), `sc_psgenv_out` (+41) — the same offsets they occupy in `SfxChannel`, so the shared `(ix+sc_*)` prefix still matches (it extends 3 bytes further). Zeroed at channel init → default-inert. Update the `SeqChannel_len` assert and verify the music-channel RAM array still fits the Z80 RAM map (+3 bytes × N music channels).

### 2. Engine — flip 3 gates SFX-only → PSG-with-envelope
- `ModUpdate`: run `PsgEnvUpdate` for any PSG-route channel with `sc_psgenv != 0` (drop the SFX-only test; the field is now in-bounds for music).
- `Psg_SetVolume`: fold `sc_psgenv_out` for any channel that has the field (drop the `Snd_ChanClass` music-skip).
- Key-on cursor reset: reset the contour on attack for music PSG too.

`PsgEnvUpdate` and `PsgVolEnv_Resolve` are reused unchanged.

### 3. Data — import HCZ2's 4 envelopes
Add `sTone_01/02/08/0C` (S3K `VolEnv_00/01/07/0B`) to `PsgVolEnv_Ids`/`Ptrs`/bodies in the engine's body format; bump `PSGVOLENV_COUNT` 6 → 10. Locate the S3K `VolEnv` source data and reuse whatever path produced the existing 6 (find/confirm the importer).

### 4. Converter — stop dropping envelopes
Map `smpsPSGvoice sTone_NN → PsgEnv(NN)` instead of `PsgEnv(0)`. Validate the referenced `sTone` is present in the engine table (a build-time/convert-time check), so a missing import fails loudly rather than silently degrading to no envelope. Regenerate `song_hcz2.asm`.

### 5. Testing / verification
- Converter unit test: `smpsPSGvoice sTone_08` emits `PsgEnv(8)`, not `PsgEnv(0)`; the noise channel and PSG1/2 carry nonzero env ids.
- Build green (`SOUND_DRIVER_ENABLED=1 DEBUG=1`).
- Oracle: VGM noise-attenuation contour now **decays per hit** (not constant 3); PSG1/2 show envelope shaping. Listen to confirm distinct hi-hat hits.

## Scope

In scope: all music PSG channels (noise hi-hat + PSG1/2 tone leads). Out of scope (separate concern): the noise *pitch/color* gap (S3K `smpsPSGform` rate-3 tone-3 frequency coupling — the converter forces fixed white noise). Timing of the hits is already correct (drums fix).

## Open items for the plan
- Confirm Z80 RAM-map headroom for `SeqChannel` +3 bytes/channel.
- Find the S3K `VolEnv` source table + the importer used for the existing 6 (the earlier grep for `zVolEnvelopes`/`VolEnvs` found nothing — locate the real label).
- Confirm no other code hard-codes `SeqChannel_len == 39`.
