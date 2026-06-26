# HCZ2 SMPS Import — Design Spec

**Date:** 2026-06-25
**Status:** Approved (brainstorm), pending implementation plan
**Branch:** `feat/hcz2-import` (worktree `s4_engine-hcz2`, off `master` @ `ac518b6`)

## 1. Goal

Import **Hydrocity Zone Act 2** (HCZ2) from the Sonic 3 & Knuckles disassembly into the s4_engine
custom sound driver, as the first real-content end-to-end test of the music sequencer + the DAC drum
path. Build it as a **reusable SMPS(S3K) → music-format-v0 converter**, with HCZ2 as the first
customer. Fidelity target: **recognizable v1, no engine changes** — cosmetic SMPS features that v0
can't represent degrade gracefully or are handled at convert time.

Success criteria:
- HCZ2 plays in the engine (oracle), recognizable as the original, exercising FM1–5 melody + 3 PSG +
  the real S3K DAC drum kit.
- The converter is a reusable tool (`tools/smps_import.py`) that turns a skdisasm SMPS song into a
  format-v0 song, not a one-off.
- No new engine features required; HCZ2 uses the existing **STREAM + FM6=DAC dedicate** path.

Non-goals (this spec): perfect note-for-note fidelity, the Music-Expression backlog (portamento /
FM-vol-env / SSG-EG / a slur opcode), a general SMPS assembler, importing other zones (the tool will
support them, but only HCZ2 is validated here).

## 2. Source analysis (verified against skdisasm)

- **File:** `skdisasm/Sound/Music/HCZ2.asm` — raw disassembled SMPS, driver **version 3** (S&K),
  `smpsHeaderVoiceUVB` (Universal Voice Bank). Distinct music from HCZ1.
- **Header:** `smpsHeaderChan $06,$03` = 6 "FM-class" tracks (DAC + FM1–5; **FM6 is the DAC**, not a
  music voice) + 3 PSG. `smpsHeaderTempo $01,$25` → divider `$01`, tempo-mod `$25`.
- **Channels:** DAC (`Snd_HCZ2_DAC`), FM1–5 (voices `$0F/$0A/$13/$0F/$0C`, per-channel pitch/transpose
  `$18/$18/$18/$0C/$0C`), PSG1–3 (`sTone_0C`).
- **Coordination flags used:** `$E0` pan (4), `$E1` detune (10), `$E7` no-attack/legato (26, esp.
  PSG3), `$EF` voice (9), `$F0` modSet (9), `$F2` stop (11), `$F3` PSG form (1), `$F5` PSG voice (72),
  `$F6` jump (10), `$F7` loop (8), `$F8` call (11), `$F9` return (5). **No** FM3-special, conditional
  jump, copy-data, or mid-song tempo change.
- **DAC kit (6 drums):** `dKickS3 $86`, `dSnareS3 $81`, `dHighTom $82`, `dMidTomS3 $83`,
  `dLowTomS3 $84`, `dFloorTomS3 $85`. Busy track with stereo pan on tom fills. S3K stores samples as
  4-bit DPCM, but **`.wav` sources are in `skdisasm/Sound/DAC/`** — encode those directly.
- **Voices:** 5 distinct from the UVB (`skdisasm/Sound/Z80 Sound Driver.asm`), SMPS 25-ish-byte voice
  format.

## 3. Engine target configuration

HCZ2 slots into the existing **STREAM + FM6=DAC dedicate** path (the DrumTest-dedicate shape, with real
music): FM1–5 melodic + DAC drums on ch6 + PSG1–3. `SH_F_STREAM` set; `SH_F_FM6_FM` / `SH_F_FM6_ADAPTIVE`
clear (FM6 is never a music voice). The stream loader sets `$2B=$00` at load and `Snd_StartSample`
re-arms `$2B=$80` per `$E2` (dedicate). The song lives in its **own ROM bank** with a per-song FM patch
table (`HCZ2_Patches`, via `SongPatchTable`). No engine code changes.

## 4. Converter architecture — `tools/smps_import.py`

A macro-level SMPS parser that emits a `SongDesc` consumed by the existing `tools/song_packer.py`
(reusing all its validation). Pipeline:

1. **Parse** the SMPS2ASM macro source (`HCZ2.asm` + the macro/constant defs in `Sound/_smps2asm_inc.asm`
   + the voice bank) into the song header + per-channel event lists. Parse the *macro* form (keeps
   symbolic labels for calls/loops). Resolve note-name / pan / DAC-sample constants from the SMPS2ASM
   tables.
2. **Per-channel stateful pass:**
   - **Inline** every `smpsCall` body (v0 has no call/return) and consume the matching `smpsReturn`.
   - **Flatten** `smpsLoop` → `REPEAT_START/END` when the body is contiguous and well-nested; otherwise
     unroll. Channel loop-back (`smpsJump`) → `LOOP_POINT` + `JUMP`.
   - **Track** running transpose (`smpsSetNote`/`smpsChangeTransposition` + header pitch byte) and
     volume (`smpsSetVol` + `smpsAlterVol`/`smpsPSGAlterVol` deltas) — fold into absolute values.
   - **Map flags** per §5.
3. **Notes/durations:** SMPS note `$81+i` → `MEV_NOTE` pitch index `i` (+ folded transpose); rest
   `$80` → `MEV_REST`. Duration = `raw × divider` (HCZ2 divider 1 → pass-through); `tempo_base = 256 −
   mod = $DB`. Durations > `$7F` emit `NoteDur` (8-bit) instead of `SetDur`+bare-note.
4. **Emit** a `SongDesc` → `song_packer.write_asm` → `data/sound/song_hcz2.asm` (+ a generated
   `HCZ2_Patches` voice table and, if needed, a per-song pitch table).

Reusability: the parser is song-agnostic; HCZ2-specific facts (which voices, which DAC samples) fall out
of the parse. Any SMPS feature HCZ2 doesn't use is **warn-and-skip**, not silently dropped (no
speculative implementation of the full SMPS spec).

## 5. SMPS → format-v0 mapping (the verified table)

| SMPS | → v0 | Notes |
|---|---|---|
| note `$81+i` + dur | `MEV_NOTE` (or `NoteDur`) | pitch index isomorphic; fold transpose |
| rest `$80` | `MEV_REST` | + `SetDur` if it carries a duration |
| `$E0` pan | `MEV_PAN` (FM); **drop on DAC** | raw `$B4` byte passes through |
| `$E1` detune | **`NOTE_RAW`** on affected notes | compute detuned `$A4/$A0` (≈exact) |
| `$E4` setVol / `$E5/$E6` Δvol | `MEV_VOL` (absolute) | converter tracks running volume |
| `$E7` no-attack (legato) | merge same-pitch ties; **re-attack on pitch-changing slur** (accepted gap) | |
| `$E8` note-fill | `MEV_NOTEFILL` | ×divider |
| `$EA` DAC trigger | `MEV_DAC` (DAC route only) | HCZ2 keeps DAC on the DAC track |
| `$EF` voice | `MEV_PATCH` (FM) / `MEV_PSGENV` (PSG) | remap voice index → v0 patch table |
| `$F0` modSet | `MEV_MODSET` | 4-param exact match |
| `$F2`/`$E3` stop | `MEV_END` | |
| `$F5` PSG voice | `MEV_PSGENV` | env id == sTone |
| `$F6` jump (loop-back) | `LOOP_POINT` + `JUMP` | other jumps flatten |
| `$F7` loop | `REPEAT_START/END` (or unroll) | |
| `$F8`/`$F9` call/return | **inline-expand** | structural; HCZ2 uses these |
| `$ED`/`$FB` transpose | fold into pitch index | converter state |
| `$F3` PSG noise mode | set at channel setup; mid-stream changes dropped (cosmetic) | |
| `$E2` fade, `$FF 01/02` play/halt, `$FC` cont-SFX | drop (cosmetic, music/SFX flow) | |
| `$FF 05` SSG-EG, `$FF 06` FM-vol-env | drop → static voice (cosmetic) | not critical in HCZ2 |

DAC: `v0_sample_id = smps_dac_note & $7F` via a remap table `{S3K id → v0 DAC table id}`.

## 6. Voices, pitch, DAC kit

- **Voices:** extract HCZ2's 5 UVB voices → convert to our `FmPatch` (26-byte) format, handling the
  S2↔S3 operator-order swap (`OP_REORDER`, as the SFX transcoder documents) → `HCZ2_Patches`. Remap the
  SMPS voice indices to the new table.
- **Pitch:** try the engine-default chromatic table (`FmPitchTableZ`) first. If S3K's tuning differs
  audibly, generate a per-song table from S3K's `zFMFrequencies`/`zPSGFrequencies` (the loader supports
  `pitchtable_ptr`).
- **DAC kit:** encode the 6 S3K drum `.wav` sources through `tools/dac_encode.py` (raw-8-bit), resampled
  to the engine's fixed ~18.4 kHz playback (resample so each drum's pitch/duration ≈ its S3K playback).
  Add to the shared DAC bank with descriptors; bank-fit check (6 drums ≈ 15–20 KB < 32 KB window). Keep
  the existing kick/snare/hat; add the S3K kit alongside (decision: additive, not replacement).

## 7. Engine integration

- `data/sound/song_hcz2.asm` (generated) + `HCZ2_Patches` in HCZ2's own bank.
- `data/sound/song_table.asm`: add `SONG_HCZ2` (id 3), `SongTable` + `SongPatchTable` entries, bank-fit
  asserts. `main.asm`: include HCZ2's bank.
- DEBUG trigger: a button in `engine/game_loop.asm` (TBD which — proposed: **B**, alongside C=DrumTest,
  START=Moving Trucks). All under `__DEBUG__`.
- DAC sample table (`engine/z80_sound_driver.asm` `DacSampleTable` / `data/sound/dac_samples.asm`):
  add the 6 S3K drums with descriptor ids.

## 8. Testing / verification (oracle, no real hardware)

- Converter unit tests (`tools/test_smps_import.py`): a known HCZ2 channel snippet → expected MEV bytes;
  call-inline + loop-flatten + transpose-fold cases.
- Build `SOUND_DRIVER_ENABLED=1 DEBUG=1`; load a `/tmp` ROM snapshot into oracle.
- VGM-parse the FM/PSG key-on + DAC `$2A` streams over a loop; confirm channel activity, the drum
  pattern, and loop-back. `audio_spectrum` per isolated channel for spot pitch checks.
- **Primary acceptance: it sounds recognizably like HCZ2** with the real drum kit (the point of the
  test). Document any audible fidelity gaps (slur re-attacks, dropped SSG-EG/vol-env).

## 9. Risks / open items

- **smpsCall/smpsLoop correctness** — the main converter risk (inline + flatten); covered by unit tests.
- **Voice conversion** — operator-order + TL/level scaling between SMPS and our `FmPatch`; verify by ear
  + spectrum.
- **DAC resampling rate** — drums are transient/noise-like, so small pitch error is inaudible; tune if a
  drum sounds off.
- **Pitch table** — default-vs-per-song decided empirically at implementation.
- **Trigger button** — confirm with user (proposed B).

## 10. Scope guard

The converter implements exactly the SMPS subset HCZ2 exercises; unsupported features warn-and-skip. No
engine code changes. No Music-Expression-backlog work. Other zones can be imported later through the same
tool but are out of scope for validation here.
